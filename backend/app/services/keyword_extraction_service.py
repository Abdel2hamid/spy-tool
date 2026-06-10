"""
Keyword Extraction Service — v2
================================
Extracts high-value ASO keyword phrases from an app's metadata and enriches
each with iTunes Search API market intelligence.

Key improvements over v1
------------------------
• Phrase-first scoring — bigrams 2.5×, trigrams 4× weight over unigrams
• Frequency counting — same phrase across multiple sources scores higher
• Position weights — title 3.0 > subtitle 2.0 > competitor 1.5 > description 1.0
• Competitor signals — extracts phrases from top-5 rival app titles/subtitles
• Weak unigram suppression — drops unigrams already covered by an included
  bi/trigram, unless the word appears in the app's own title
• 120-candidate cap (was 60); ~42 s total enrichment time at 0.35 s/request
• Aggressive cross-phrase deduplication before enrichment

Pipeline
--------
1. Collect raw n-grams from title, subtitle, description, competitor metadata
2. Score each candidate: frequency × phrase_length_bonus × best_position_weight
3. Sort phrases first, then filtered unigrams; take top 120
4. Enrich each keyword via iTunes Search API
5. Upsert results into app_keyword_intelligence table
"""

from __future__ import annotations

import logging
import math
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

from app.services.apple_http_client import apple_fetch_json, ITUNES_SEARCH_URL

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stopwords — extended for app store context
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
    "no", "not", "only", "same", "than", "too", "very", "just",
    "any", "about", "get", "got", "also", "even", "now", "one",
    "use", "using", "used", "make", "makes", "made", "way", "like",
    "amp", "free", "new",
    # generic app-store filler words that add no keyword value:
    "app", "apps", "best", "easy", "fast", "great", "good", "amazing",
    "awesome", "simple", "top", "pro", "plus", "premium",
}

# ---------------------------------------------------------------------------
# Position weights — reflect ASO signal strength of each source
# ---------------------------------------------------------------------------
_POS_WEIGHT: Dict[str, float] = {
    "title": 3.0,
    "subtitle": 2.0,
    "competitor": 1.5,
    "description": 1.0,
}

# ---------------------------------------------------------------------------
# Phrase-length scoring bonus — heavily favours multi-word phrases
# ---------------------------------------------------------------------------
_LENGTH_BONUS: Dict[int, float] = {1: 1.0, 2: 2.5, 3: 4.0}

# ---------------------------------------------------------------------------
# CTR curve — click-through rate by iTunes search rank
# ---------------------------------------------------------------------------
_CTR_BY_RANK: Dict[int, float] = {1: 30.0, 2: 15.0, 3: 10.0, 4: 7.0, 5: 7.0}


def _ctr(rank: Optional[int]) -> float:
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
# Internal candidate representation
# ---------------------------------------------------------------------------
@dataclass
class _Candidate:
    text: str
    source: str           # best source label for display
    n: int                # phrase length in words (1 / 2 / 3)
    frequency: int = 1    # occurrences across all sources
    pos_weight: float = 1.0   # best position weight seen
    in_title: bool = False    # appears in the app's own title

    @property
    def score(self) -> float:
        """phrase_length_bonus × frequency × position_weight"""
        return _LENGTH_BONUS.get(self.n, 1.0) * self.frequency * self.pos_weight


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------
class KeywordExtractionService:
    """
    Extracts and enriches keyword intelligence for a single app.

    Usage::
        svc = KeywordExtractionService(db)
        keywords = svc.extract_keywords_for_app(app_id)   # blocking
        cached   = svc.get_stored(app_id)
    """

    _REQUEST_DELAY = 0.35       # polite delay between iTunes requests (s)
    _MAX_KEYWORDS = 120         # candidates to enrich
    _TIMEOUT = 12               # HTTP timeout per request (s)
    _STALE_HOURS = 24

    def __init__(self, db: Session):
        self.db = db

    # ── Public API ────────────────────────────────────────────────────────────

    def is_stale(self, app_id: int) -> bool:
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
        """Full pipeline: extract → score → select → enrich → save."""
        from app.models.models import App

        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return []

        candidates = self._build_candidates(app)
        logger.info(
            f"[KeywordExtraction] app={app.app_id} ({app.name!r}) → "
            f"{len(candidates)} scored candidates, enriching top {self._MAX_KEYWORDS}"
        )

        enriched: List[Dict] = []
        for c in candidates[: self._MAX_KEYWORDS]:
            try:
                result = self._enrich(c.text, c.source, str(app.app_id))
                enriched.append(result)
                time.sleep(self._REQUEST_DELAY)
            except Exception as exc:
                logger.warning(f"[KeywordExtraction] enrich failed for {c.text!r}: {exc}")

        self._save(app_id, enriched)
        logger.info(
            f"[KeywordExtraction] app={app.app_id} → saved {len(enriched)} keywords"
        )
        return enriched

    # ── Candidate construction ────────────────────────────────────────────────

    def _build_candidates(self, app) -> List[_Candidate]:
        """
        Full extraction pipeline:
        1. Collect n-grams from all sources into a scored pool
        2. Fetch competitor titles/subtitles and add their n-grams
        3. Sort: phrases first (by score), then unigrams (filtered)
        4. Deduplicate: remove unigrams already covered by a phrase
        """
        title_text = (app.name or "").lower()
        title_tokens = set(self._tokenize(title_text))

        pool: Dict[str, _Candidate] = {}

        # ── Own metadata sources ──────────────────────────────────────────
        own_sources = [
            (app.name or "",         "title"),
            (app.subtitle or "",     "subtitle"),
            (app.description[:3000] if app.description else "", "description"),
        ]
        for text, source in own_sources:
            self._collect_ngrams(text, source, title_tokens, pool)

        # ── Competitor signals ────────────────────────────────────────────
        try:
            competitor_phrases = self._fetch_competitor_phrases(app)
            for phrase in competitor_phrases:
                self._add_to_pool(phrase, "competitor", title_tokens, pool)
        except Exception as exc:
            logger.debug(f"[KeywordExtraction] competitor fetch failed: {exc}")

        # ── Score, split, filter, merge ───────────────────────────────────
        phrases   = [c for c in pool.values() if c.n >= 2]
        unigrams  = [c for c in pool.values() if c.n == 1]

        phrases.sort(key=lambda c: c.score, reverse=True)
        unigrams.sort(key=lambda c: c.score, reverse=True)

        # Words covered by selected phrases — used to suppress redundant unigrams
        covered_words: Set[str] = set()
        for c in phrases:
            covered_words.update(c.text.split())

        # Keep unigrams only if:
        #   • the word is in the app title (direct ASO relevance), OR
        #   • the word isn't already covered by a selected phrase
        kept_unigrams = [
            c for c in unigrams
            if c.in_title or c.text not in covered_words
        ]

        return phrases + kept_unigrams

    def _collect_ngrams(
        self,
        text: str,
        source: str,
        title_tokens: Set[str],
        pool: Dict[str, _Candidate],
    ) -> None:
        """Generate all n-grams from text and merge into pool."""
        tokens = self._tokenize(text)
        if not tokens:
            return

        # Unigrams
        for tok in tokens:
            if len(tok) >= 3 and tok not in _STOPWORDS:
                self._add_to_pool(tok, source, title_tokens, pool)

        # Bigrams — no leading/trailing stopword
        for i in range(len(tokens) - 1):
            a, b = tokens[i], tokens[i + 1]
            if a in _STOPWORDS or b in _STOPWORDS:
                continue
            phrase = f"{a} {b}"
            self._add_to_pool(phrase, source, title_tokens, pool)

        # Trigrams — no leading/trailing stopword
        for i in range(len(tokens) - 2):
            a, b, c = tokens[i], tokens[i + 1], tokens[i + 2]
            if a in _STOPWORDS or c in _STOPWORDS:
                continue
            phrase = f"{a} {b} {c}"
            self._add_to_pool(phrase, source, title_tokens, pool)

    def _add_to_pool(
        self,
        phrase: str,
        source: str,
        title_tokens: Set[str],
        pool: Dict[str, _Candidate],
    ) -> None:
        """Merge one phrase into the pool, updating frequency and weights."""
        words = phrase.split()
        n = len(words)
        pos_w = _POS_WEIGHT.get(source, 1.0)
        in_title = n == 1 and phrase in title_tokens

        if phrase in pool:
            c = pool[phrase]
            c.frequency += 1
            if pos_w > c.pos_weight:
                c.pos_weight = pos_w
                c.source = source   # promote to higher-priority source label
            c.in_title = c.in_title or in_title
        else:
            pool[phrase] = _Candidate(
                text=phrase,
                source=source,
                n=n,
                frequency=1,
                pos_weight=pos_w,
                in_title=in_title,
            )

    # ── Competitor extraction ─────────────────────────────────────────────────

    def _fetch_competitor_phrases(self, app) -> List[str]:
        """
        Search iTunes for the app's category/title and extract bigrams +
        trigrams from the top-5 competitor trackName + subtitle fields.
        Returns a flat list of phrase strings.
        """
        # Build search query: use primary_category or first 2 title words
        if app.primary_category:
            query = app.primary_category.lower()
        else:
            words = self._tokenize(app.name or "")
            query = " ".join(words[:2])

        if not query:
            return []

        data = self._itunes_search(query, limit=10)
        competitors = [
            item for item in data.get("results", [])
            if str(item.get("trackId", "")) != str(app.app_id)
        ][:5]

        phrases: List[str] = []
        for item in competitors:
            text = " ".join(filter(None, [
                item.get("trackName", ""),
                item.get("subtitle", ""),
            ]))
            tokens = self._tokenize(text)

            # Bigrams from competitor titles
            for i in range(len(tokens) - 1):
                a, b = tokens[i], tokens[i + 1]
                if a not in _STOPWORDS and b not in _STOPWORDS:
                    phrases.append(f"{a} {b}")

            # Trigrams from competitor titles
            for i in range(len(tokens) - 2):
                a, b, c = tokens[i], tokens[i + 1], tokens[i + 2]
                if a not in _STOPWORDS and c not in _STOPWORDS:
                    phrases.append(f"{a} {b} {c}")

        return phrases

    # ── Enrichment ────────────────────────────────────────────────────────────

    def _enrich(self, keyword: str, source: str, current_app_id: str) -> Dict:
        data = self._itunes_search(keyword)
        items = data.get("results", [])
        result_count = data.get("resultCount", len(items))

        app_rank: Optional[int] = None
        for i, item in enumerate(items):
            if str(item.get("trackId", "")) == current_app_id:
                app_rank = i + 1
                break

        search_volume = self._estimate_volume(keyword, items, result_count)
        difficulty    = self._estimate_difficulty(items)
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
        data = apple_fetch_json(
            ITUNES_SEARCH_URL,
            params={
                "term": keyword,
                "country": country,
                "entity": "software",
                "limit": limit,
                "lang": "en_us",
            },
            timeout=self._TIMEOUT,
        )
        return data or {}

    # ── Score heuristics ──────────────────────────────────────────────────────

    # Generic single words that appear in countless app names and must not
    # inflate volume scores via title/subtitle hits.
    _GENERIC_TERMS: Set[str] = {
        "official", "world", "best", "free", "easy", "top", "app",
        "new", "pro", "plus", "premium", "lite", "go", "one",
    }

    @classmethod
    def _estimate_volume(
        cls, keyword: str, items: List[Dict], result_count: int
    ) -> int:
        """
        Heuristic search volume 0-100.

        • iTunes result count  (log-scaled)                     → 0-40 pts
        • Exact-token matches in top-10 names/subtitles         → 0-30 pts
          (unigram +2, bigram +5, trigram +8 per hit;
           generic unigrams multiplied by 0.4)
        • Avg userRatingCount of top-5 apps (log-scaled)        → 0-30 pts
        """
        score = 0.0

        # ── Component 1: result count (unchanged) ──────────────────────────
        if result_count > 0:
            score += min(math.log10(result_count + 1) / math.log10(1001) * 40, 40)

        # ── Component 2: exact-token title/subtitle hits ───────────────────
        kw_words = keyword.lower().split()
        phrase_len = len(kw_words)

        # Per-hit point value by phrase length
        if phrase_len == 1:
            hit_pts = 2.0
        elif phrase_len == 2:
            hit_pts = 5.0
        else:
            hit_pts = 8.0

        # Dampen generic unigrams to avoid inflation from ubiquitous words
        if phrase_len == 1 and keyword.lower() in cls._GENERIC_TERMS:
            hit_pts *= 0.4

        title_score = 0.0
        for item in items[:10]:
            name_tokens = set(re.findall(r"[a-z0-9]+", (item.get("trackName") or "").lower()))
            sub_tokens  = set(re.findall(r"[a-z0-9]+", (item.get("subtitle")   or "").lower()))
            all_tokens  = name_tokens | sub_tokens

            if phrase_len == 1:
                # Single keyword must be an exact token
                matched = kw_words[0] in all_tokens
            else:
                # Multi-word: all constituent words must appear as tokens
                # (order-independent — close enough for a heuristic)
                matched = all(w in all_tokens for w in kw_words)

            if matched:
                title_score += hit_pts

        score += min(title_score, 30)

        # ── Component 3: rating count signal (unchanged) ───────────────────
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
        Heuristic difficulty 0-100.

        • Avg rating of top-10 apps       → 0-40 pts
        • Avg review count of top-10 apps → 0-40 pts
        • Result saturation               → 0-20 pts
        """
        score = 0.0
        top = items[:10]
        if not top:
            return 0.0

        ratings = [
            item.get("averageUserRating", 0)
            for item in top if item.get("averageUserRating")
        ]
        if ratings:
            score += (sum(ratings) / len(ratings) / 5.0) * 40

        counts = [
            item.get("userRatingCount", 0)
            for item in top if item.get("userRatingCount")
        ]
        if counts:
            avg = sum(counts) / len(counts)
            score += min(math.log10(avg + 1) / math.log10(50_001) * 40, 40)

        score += min(len(items) / 50 * 20, 20)

        return min(round(score, 1), 100)

    # ── Tokenization ─────────────────────────────────────────────────────────

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        text = text.lower()
        text = re.sub(r"[^\w\s-]", " ", text)
        text = re.sub(r"[-_]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return [t for t in text.split() if t.isalpha() and len(t) >= 2]

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save(self, app_id: int, enriched: List[Dict]) -> None:
        from app.models.models import Keyword, KeywordStatus, AppKeywordIntelligence
        from app.services.global_keyword_sink import GlobalKeywordSink

        if not enriched:
            return

        sink = GlobalKeywordSink(self.db)
        terms = [item["keyword"] for item in enriched]
        sink.push(keywords=terms, source="extraction", discovered_from=None)

        now = datetime.now(timezone.utc)
        for item in enriched:
            try:
                kw = self.db.query(Keyword).filter(Keyword.term == item["keyword"]).first()
                if not kw:
                    continue

                aki = (
                    self.db.query(AppKeywordIntelligence)
                    .filter(
                        AppKeywordIntelligence.app_id == app_id,
                        AppKeywordIntelligence.keyword_id == kw.id,
                    )
                    .first()
                )
                if aki:
                    aki.source        = item["source"]
                    aki.search_volume = item["search_volume"]
                    aki.difficulty    = item["difficulty"]
                    aki.traffic_score = item["traffic_score"]
                    aki.app_rank      = item["app_rank"]
                    aki.result_count  = item["result_count"]
                    aki.extracted_at  = now
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
                    f"[KeywordExtraction] save failed for {item['keyword']!r}: {exc}"
                )
                self.db.rollback()

        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.error(f"[KeywordExtraction] final commit failed: {exc}")
