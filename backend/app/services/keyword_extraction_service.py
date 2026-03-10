"""
Keyword Extraction Service
==========================
Extracts keywords from an app's title, subtitle, and description, then
enriches each keyword with market intelligence via the iTunes Search API.

Pipeline
--------
1. Normalize text (lowercase, strip punctuation)
2. Tokenize and remove stopwords
3. Generate unigrams, bigrams, trigrams
4. Deduplicate and rank by source priority (title > subtitle > description)
5. For each keyword (capped at MAX_KEYWORDS):
   - Search iTunes API → find this app's rank, result count, top-app signals
   - Compute heuristic search_volume (0-100), difficulty (0-100), traffic_score
6. Upsert results into app_keyword_intelligence table
"""

import json
import logging
import math
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# English stopwords
# ---------------------------------------------------------------------------
_STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "but", "nor", "for", "yet", "so",
    "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall", "can",
    "to", "of", "in", "on", "at", "by", "for", "with", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "up", "down", "off", "over", "under",
    "again", "further", "then", "once",
    "this", "that", "these", "those", "it", "its",
    "he", "she", "we", "they", "you", "i", "me", "him", "her", "us", "them",
    "your", "my", "our", "their", "his",
    "what", "which", "who", "whom", "whose", "where", "when", "why", "how",
    "all", "both", "each", "few", "more", "most", "other", "some", "such",
    "no", "not", "only", "same", "so", "than", "too", "very", "just",
    "any", "about", "get", "got", "also", "even", "now", "one",
    "use", "using", "used", "make", "makes", "made", "way", "like",
    "amp", "app", "apps",  # too generic for app store
}

# ---------------------------------------------------------------------------
# CTR curve — estimated click-through rate by rank position
# ---------------------------------------------------------------------------
_CTR_BY_RANK: Dict[int, float] = {
    1: 30.0,
    2: 15.0,
    3: 10.0,
    4: 7.0,
    5: 7.0,
}


def _ctr(rank: Optional[int]) -> float:
    """Return estimated CTR % for a given iTunes search rank."""
    if rank is None:
        return 0.5
    if rank in _CTR_BY_RANK:
        return _CTR_BY_RANK[rank]
    if rank <= 10:
        return 4.0
    if rank <= 20:
        return 2.0
    return 0.5


# ---------------------------------------------------------------------------
# Source priority for deduplication (lower = higher priority)
# ---------------------------------------------------------------------------
_SOURCE_PRIORITY = {"title": 0, "subtitle": 1, "description": 2}


class KeywordExtractionService:
    """
    Extracts and enriches keyword intelligence for a single app.

    Usage::
        svc = KeywordExtractionService(db)
        keywords = svc.extract_keywords_for_app(app_id)   # blocking — run in thread
        cached   = svc.get_stored(app_id)                 # reads from DB
    """

    _ITUNES_SEARCH = "https://itunes.apple.com/search"
    _REQUEST_DELAY = 0.35       # polite delay between iTunes requests (seconds)
    _MAX_KEYWORDS = 60          # cap to keep enrichment time reasonable
    _TIMEOUT = 12               # seconds per HTTP request
    _STALE_HOURS = 24           # re-extract after this many hours

    def __init__(self, db: Session):
        self.db = db

    # ── Public API ────────────────────────────────────────────────────────────

    def is_stale(self, app_id: int) -> bool:
        """Return True if there is no stored data or data is older than STALE_HOURS."""
        from app.models.models import AppKeywordIntelligence
        row = (
            self.db.query(AppKeywordIntelligence.extracted_at)
            .filter(AppKeywordIntelligence.app_id == app_id)
            .order_by(AppKeywordIntelligence.extracted_at.desc())
            .first()
        )
        if not row:
            return True
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self._STALE_HOURS)
        ts = row[0]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts < cutoff

    def get_stored(self, app_id: int) -> List[Dict]:
        """Return previously extracted + enriched data from DB, sorted by traffic_score."""
        from app.models.models import AppKeywordIntelligence, Keyword as KW

        rows = (
            self.db.query(AppKeywordIntelligence, KW)
            .join(KW, KW.id == AppKeywordIntelligence.keyword_id)
            .filter(AppKeywordIntelligence.app_id == app_id)
            .order_by(AppKeywordIntelligence.traffic_score.desc())
            .all()
        )
        return [
            {
                "keyword": kw.term,
                "source": aki.source,
                "search_volume": aki.search_volume,
                "difficulty": aki.difficulty,
                "traffic_score": aki.traffic_score,
                "app_rank": aki.app_rank,
                "result_count": aki.result_count,
                "extracted_at": aki.extracted_at,
            }
            for aki, kw in rows
        ]

    def extract_keywords_for_app(self, app_id: int) -> List[Dict]:
        """
        Full pipeline: extract → enrich → save → return.
        Blocking — intended to run inside asyncio.to_thread().
        """
        from app.models.models import App

        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return []

        candidates = self._extract_candidates(app)
        logger.info(
            f"[KeywordExtraction] app={app.app_id} ({app.name!r}) → "
            f"{len(candidates)} candidates, enriching top {self._MAX_KEYWORDS}"
        )

        enriched: List[Dict] = []
        for kw, source in candidates[: self._MAX_KEYWORDS]:
            try:
                result = self._enrich(kw, source, str(app.app_id))
                enriched.append(result)
                time.sleep(self._REQUEST_DELAY)
            except Exception as exc:
                logger.warning(f"[KeywordExtraction] enrich failed for {kw!r}: {exc}")

        self._save(app_id, enriched)
        logger.info(
            f"[KeywordExtraction] app={app.app_id} → "
            f"saved {len(enriched)} enriched keywords"
        )
        return enriched

    # ── Keyword Extraction ────────────────────────────────────────────────────

    def _extract_candidates(self, app) -> List[Tuple[str, str]]:
        """
        Return (keyword, source) pairs, deduped, ordered by source priority.
        Title > subtitle > description (first 2 000 chars).
        """
        seen: Set[str] = set()
        # Collect per-source n-grams
        by_source: Dict[str, List[str]] = {"title": [], "subtitle": [], "description": []}

        sources = [
            (app.name or "", "title"),
            (app.subtitle or "", "subtitle"),
            (app.description[:2000] if app.description else "", "description"),
        ]

        for text, source in sources:
            for kw in self._generate_ngrams(text):
                if kw not in seen:
                    seen.add(kw)
                    by_source[source].append(kw)

        # Interleave: one from title, one from subtitle, one from description, repeat
        result: List[Tuple[str, str]] = []
        queues = [
            (by_source["title"], "title"),
            (by_source["subtitle"], "subtitle"),
            (by_source["description"], "description"),
        ]
        max_len = max(len(q) for q, _ in queues) if any(queues) else 0
        for i in range(max_len):
            for q, src in queues:
                if i < len(q):
                    result.append((q[i], src))

        return result

    def _generate_ngrams(self, text: str) -> List[str]:
        """Return deduped unigrams + bigrams + trigrams from text."""
        tokens = self._tokenize(text)
        ngrams: List[str] = []

        # Unigrams — at least 3 chars, not a stopword
        for tok in tokens:
            if len(tok) >= 3 and tok not in _STOPWORDS:
                ngrams.append(tok)

        # Bigrams — no leading/trailing stopword, min 6 chars total
        for i in range(len(tokens) - 1):
            a, b = tokens[i], tokens[i + 1]
            if a in _STOPWORDS or b in _STOPWORDS:
                continue
            phrase = f"{a} {b}"
            if len(phrase) >= 6:
                ngrams.append(phrase)

        # Trigrams — no leading/trailing stopword, min 8 chars total
        for i in range(len(tokens) - 2):
            a, b, c = tokens[i], tokens[i + 1], tokens[i + 2]
            if a in _STOPWORDS or c in _STOPWORDS:
                continue
            phrase = f"{a} {b} {c}"
            if len(phrase) >= 8:
                ngrams.append(phrase)

        # Dedupe preserving first occurrence
        seen: Set[str] = set()
        deduped: List[str] = []
        for ng in ngrams:
            if ng not in seen:
                seen.add(ng)
                deduped.append(ng)

        return deduped

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        text = text.lower()
        text = re.sub(r"[^\w\s-]", " ", text)    # keep hyphens
        text = re.sub(r"[-_]", " ", text)          # hyphens → space
        text = re.sub(r"\s+", " ", text).strip()
        return [t for t in text.split() if t.isalpha() and len(t) >= 2]

    # ── Enrichment ────────────────────────────────────────────────────────────

    def _enrich(self, keyword: str, source: str, current_app_id: str) -> Dict:
        """Call iTunes Search API and compute scores for one keyword."""
        data = self._itunes_search(keyword)
        items = data.get("results", [])
        result_count = data.get("resultCount", len(items))

        # Find current app's rank in results (1-based; None if not in top N)
        app_rank: Optional[int] = None
        for i, item in enumerate(items):
            if str(item.get("trackId", "")) == current_app_id:
                app_rank = i + 1
                break

        search_volume = self._estimate_volume(keyword, items, result_count)
        difficulty = self._estimate_difficulty(items)
        traffic_score = round(search_volume * _ctr(app_rank) / 100, 1)

        return {
            "keyword": keyword,
            "source": source,
            "search_volume": search_volume,
            "difficulty": difficulty,
            "traffic_score": traffic_score,
            "app_rank": app_rank,
            "result_count": result_count,
        }

    def _itunes_search(
        self, keyword: str, country: str = "us", limit: int = 50
    ) -> Dict:
        params = urllib.parse.urlencode({
            "term": keyword,
            "country": country,
            "entity": "software",
            "limit": limit,
            "lang": "en_us",
        })
        url = f"{self._ITUNES_SEARCH}?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "AppStoreSpy/1.0"})
        with urllib.request.urlopen(req, timeout=self._TIMEOUT) as resp:
            return json.loads(resp.read())

    # ── Score heuristics ──────────────────────────────────────────────────────

    @staticmethod
    def _estimate_volume(
        keyword: str, items: List[Dict], result_count: int
    ) -> int:
        """
        Heuristic search volume score 0-100.

        Factors (each capped):
        • iTunes result count — proxy for market size          (0-40 pts, log-scaled)
        • Keyword in top-10 app names/subtitles — demand signal (0-30 pts)
        • Average userRatingCount of top 5 apps — popularity   (0-30 pts, log-scaled)
        """
        score = 0.0

        # 1. Result count (log-scaled)
        if result_count > 0:
            score += min(math.log10(result_count + 1) / math.log10(1001) * 40, 40)

        # 2. Presence in top-10 app names/subtitles
        kw_lower = keyword.lower()
        title_hits = sum(
            1
            for item in items[:10]
            if kw_lower in (item.get("trackName") or "").lower()
            or kw_lower in (item.get("subtitle") or "").lower()
        )
        score += min(title_hits * 6, 30)

        # 3. Average userRatingCount of top-5 apps (log-scaled)
        counts = [
            item.get("userRatingCount", 0)
            for item in items[:5]
            if item.get("userRatingCount")
        ]
        if counts:
            avg = sum(counts) / len(counts)
            score += min(math.log10(avg + 1) / math.log10(100_001) * 30, 30)

        return min(round(score), 100)

    @staticmethod
    def _estimate_difficulty(items: List[Dict]) -> float:
        """
        Heuristic difficulty score 0-100.

        Factors:
        • Average rating of top 10 apps — polish of competition (0-40 pts)
        • Average review count of top 10 apps — established players (0-40 pts)
        • Number of returned results — market saturation         (0-20 pts)
        """
        score = 0.0
        top = items[:10]
        if not top:
            return 0.0

        # 1. Average rating
        ratings = [
            item.get("averageUserRating", 0)
            for item in top
            if item.get("averageUserRating")
        ]
        if ratings:
            score += (sum(ratings) / len(ratings) / 5.0) * 40

        # 2. Average review count (log-scaled)
        counts = [
            item.get("userRatingCount", 0)
            for item in top
            if item.get("userRatingCount")
        ]
        if counts:
            avg = sum(counts) / len(counts)
            score += min(math.log10(avg + 1) / math.log10(50_001) * 40, 40)

        # 3. Saturation (number of items returned, max 50 via API)
        score += min(len(items) / 50 * 20, 20)

        return min(round(score, 1), 100)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save(self, app_id: int, enriched: List[Dict]) -> None:
        """Upsert enriched keyword intelligence into DB."""
        from app.models.models import Keyword, KeywordStatus, AppKeywordIntelligence

        if not enriched:
            return

        now = datetime.now(timezone.utc)

        for item in enriched:
            try:
                # Upsert Keyword row
                kw = self.db.query(Keyword).filter(Keyword.term == item["keyword"]).first()
                if not kw:
                    kw = Keyword(
                        term=item["keyword"],
                        keyword_source="extraction",
                        first_seen_at=now,
                        status=KeywordStatus.RAW.value,
                    )
                    self.db.add(kw)
                    self.db.flush()

                # Upsert AppKeywordIntelligence row
                aki = (
                    self.db.query(AppKeywordIntelligence)
                    .filter(
                        AppKeywordIntelligence.app_id == app_id,
                        AppKeywordIntelligence.keyword_id == kw.id,
                    )
                    .first()
                )
                if aki:
                    aki.source = item["source"]
                    aki.search_volume = item["search_volume"]
                    aki.difficulty = item["difficulty"]
                    aki.traffic_score = item["traffic_score"]
                    aki.app_rank = item["app_rank"]
                    aki.result_count = item["result_count"]
                    aki.extracted_at = now
                else:
                    self.db.add(AppKeywordIntelligence(
                        app_id=app_id,
                        keyword_id=kw.id,
                        source=item["source"],
                        search_volume=item["search_volume"],
                        difficulty=item["difficulty"],
                        traffic_score=item["traffic_score"],
                        app_rank=item["app_rank"],
                        result_count=item["result_count"],
                        extracted_at=now,
                    ))
            except Exception as exc:
                logger.warning(
                    f"[KeywordExtraction] save row failed for {item['keyword']!r}: {exc}"
                )
                self.db.rollback()
                continue

        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.error(f"[KeywordExtraction] final commit failed: {exc}")
