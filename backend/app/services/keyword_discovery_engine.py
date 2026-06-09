"""
Keyword Discovery Engine
========================
Generates 10k–100k keyword candidates from Apple App Store signals.

Discovery phases
----------------
A  Static expansion   — alphabet suffixes/prefixes + common modifiers (no network)
B  Apple suggestions  — MZSearchHints autocomplete API (fast, no auth)
C  App metadata       — iTunes search → bigram/trigram phrase extraction

All phases feed a shared normalise → deduplicate → upsert pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import re
import string
import urllib.parse
import urllib.request
import json
from datetime import datetime, timezone
from itertools import product
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Built-in seed keywords (≥130 across 15 categories)
# ---------------------------------------------------------------------------

_BUILTIN_SEEDS: List[str] = [
    # Productivity
    "productivity app", "task manager", "to-do list", "note taking", "calendar app",
    "time tracker", "habit tracker", "goal setting", "daily planner", "project manager",
    "focus timer", "pomodoro timer", "kanban board", "reminders app", "journal app",
    # Health & Fitness
    "fitness tracker", "workout app", "running app", "yoga app", "meditation app",
    "calorie counter", "diet tracker", "weight loss app", "sleep tracker", "step counter",
    "gym tracker", "meal planner", "water tracker", "mental health app", "breathing exercise",
    # Finance
    "budget app", "expense tracker", "personal finance", "money manager", "investment app",
    "stock tracker", "crypto tracker", "savings app", "bill tracker", "net worth tracker",
    "spending tracker", "financial planner", "tax calculator", "invoice app", "receipt scanner",
    # Education
    "language learning", "flashcard app", "study planner", "quiz app", "math tutor",
    "reading app", "vocabulary app", "grammar app", "coding app", "science app",
    "history app", "geography app", "kids learning", "homework helper", "typing tutor",
    # Entertainment
    "music player", "podcast app", "video streaming", "photo editor", "video editor",
    "game app", "puzzle game", "trivia game", "word game", "brain game",
    "music discovery", "playlist maker", "album art", "lyrics app", "karaoke app",
    # Social
    "social media", "chat app", "dating app", "community app", "forum app",
    "friend finder", "event planning", "group chat", "video call", "voice chat",
    # Travel
    "travel planner", "trip planner", "flight tracker", "hotel finder", "map app",
    "offline maps", "language translator", "travel guide", "currency converter", "packing list",
    # Food & Drink
    "recipe app", "restaurant finder", "food delivery", "coffee app", "cooking app",
    "grocery list", "wine app", "cocktail app", "nutrition app", "food diary",
    # Business
    "crm app", "invoicing app", "time billing", "client management", "sales tracker",
    "business card scanner", "document scanner", "e-signature", "contract manager", "proposal app",
    # Utilities
    "password manager", "vpn app", "file manager", "qr code scanner", "barcode scanner",
    "flashlight app", "calculator app", "unit converter", "weather app", "alarm clock",
    "screen recorder", "clipboard manager", "reminder app", "contact manager", "backup app",
    # Kids
    "kids game", "children app", "toddler app", "baby app", "parenting app",
    "kids education", "bedtime stories", "drawing app kids", "coloring app", "abc app",
    # Sports
    "sports tracker", "golf app", "cycling app", "swimming tracker", "hiking app",
    "football app", "basketball app", "tennis app", "soccer app", "baseball app",
    # Creative
    "drawing app", "painting app", "photo collage", "logo maker", "design app",
    "animation app", "comic creator", "writing app", "story builder", "art app",
    # Home
    "smart home", "home automation", "home inventory", "home design", "interior design",
    "moving app", "cleaning schedule", "shopping list", "home budget", "utility tracker",
    # Medical
    "medication tracker", "symptom checker", "doctor appointment", "health record",
    "blood pressure monitor", "blood sugar tracker", "pregnancy app", "baby tracker",
]

# Static expansion modifiers
_SUFFIXES = [
    "free", "pro", "plus", "lite", "offline", "ai", "tracker",
    "planner", "manager", "organizer", "2024", "2025", "for iphone",
    "for ipad", "ios", "apple watch",
]

_PREFIXES = [
    "best", "simple", "easy", "smart", "daily", "fast", "free",
    "new", "top", "mini",
]

# Apple MZSearchHints autocomplete endpoint
_SUGGESTIONS_URL = (
    "https://search.itunes.apple.com/WebObjects/MZSearchHints.woa/wa/hints"
    "?media=software&term={term}"
)

# iTunes search endpoint (to pull app names for phrase extraction)
_ITUNES_SEARCH_URL = (
    "https://itunes.apple.com/search"
    "?media=software&entity=software&country=us&limit=50&term={term}"
)

# Stop words for phrase extraction
_STOP_WORDS: Set[str] = {
    "the", "a", "an", "and", "or", "for", "of", "in", "on", "at", "to",
    "by", "is", "it", "my", "me", "your", "our", "with", "from", "app",
    "apps", "ios", "iphone", "ipad", "apple", "free", "pro", "lite",
    "best", "new", "top", "get", "use", "can", "all", "you", "your",
    "i", "he", "she", "we", "they", "be", "do", "did", "has", "have",
    "had", "will", "would", "could", "should", "may", "might", "this",
    "that", "these", "those", "so", "if", "but", "not", "no", "yes",
}

# ---------------------------------------------------------------------------
# Async HTTP helper (no external deps — urllib only)
# ---------------------------------------------------------------------------

async def _fetch_json(url: str, timeout: int = 8) -> Optional[dict]:
    """Fetch a JSON URL asynchronously via asyncio thread executor."""
    def _get():
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                        "Mobile/15E148 Safari/604.1"
                    ),
                    "Accept": "application/json",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            logger.debug(f"_fetch_json error for {url[:80]}: {exc}")
            return None

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get)


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class KeywordDiscoveryEngine:
    """
    Discovers new keyword candidates through three phases and persists them.

    Usage::

        engine = KeywordDiscoveryEngine(db)
        stats = await engine.run_keyword_discovery()
    """

    def __init__(self, db: Session, concurrency: int = 8):
        self.db = db
        self._sem = asyncio.Semaphore(concurrency)
        self._now = datetime.now(timezone.utc)

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------

    async def run_keyword_discovery(self) -> Dict[str, int]:
        """
        Run all three discovery phases and persist results incrementally.

        Each phase stores its results immediately — so Phase A keywords reach
        the DB even if Phase B or C time out on Railway.

        Phase B uses only _BUILTIN_SEEDS (not DB terms) to keep the API call
        count manageable (~115 seeds × 27 = ~3,100 queries vs 13,000+).

        Returns a stats dict with keys:
          seeds, phase_a, phase_b, phase_c, candidates, inserted, updated, skipped
        """
        logger.info("[KeywordDiscovery] Starting keyword discovery run")

        seeds = self._load_seeds()
        logger.info(f"[KeywordDiscovery] Seeds loaded: {len(seeds)}")

        total_inserted = 0
        total_updated = 0
        total_skipped = 0

        # ── Phase A — static expansion (fast, no I/O) ────────────────────────
        phase_a = self._static_expand(seeds)
        logger.info(f"[KeywordDiscovery] Phase A (static expand): {len(phase_a)} candidates")
        phase_a_norm = self._normalize_batch(list(phase_a))
        ins, upd, skp = await asyncio.to_thread(self._store_keywords, phase_a_norm)
        total_inserted += ins
        total_updated += upd
        total_skipped += skp
        logger.info(f"[KeywordDiscovery] Phase A stored: inserted={ins}, skipped={skp}")

        # ── Phase B — Apple autocomplete suggestions ──────────────────────────
        # Use only _BUILTIN_SEEDS (not full DB) to keep queries bounded:
        # ~115 seeds × 27 queries = ~3,100 API calls (vs 13,000+ with DB terms).
        phase_b = await self._run_suggestions_phase(_BUILTIN_SEEDS)
        logger.info(f"[KeywordDiscovery] Phase B (Apple suggestions): {len(phase_b)} candidates")
        phase_b_norm = self._normalize_batch(list(phase_b))
        ins, upd, skp = await asyncio.to_thread(self._store_keywords, phase_b_norm)
        total_inserted += ins
        total_updated += upd
        total_skipped += skp
        logger.info(f"[KeywordDiscovery] Phase B stored: inserted={ins}, skipped={skp}")

        # ── Phase C — App metadata phrase extraction ──────────────────────────
        # Use a smaller subset of seeds to keep runtime reasonable.
        phase_c_seeds = _BUILTIN_SEEDS[: min(60, len(_BUILTIN_SEEDS))]
        phase_c = await self._run_metadata_phase(phase_c_seeds)
        logger.info(f"[KeywordDiscovery] Phase C (metadata phrases): {len(phase_c)} candidates")
        phase_c_norm = self._normalize_batch(list(phase_c))
        ins, upd, skp = await asyncio.to_thread(self._store_keywords, phase_c_norm)
        total_inserted += ins
        total_updated += upd
        total_skipped += skp
        logger.info(f"[KeywordDiscovery] Phase C stored: inserted={ins}, skipped={skp}")

        stats = {
            "seeds": len(seeds),
            "phase_a": len(phase_a),
            "phase_b": len(phase_b),
            "phase_c": len(phase_c),
            "candidates": len(phase_a) + len(phase_b) + len(phase_c),
            "inserted": total_inserted,
            "updated": total_updated,
            "skipped": total_skipped,
        }
        logger.info(
            f"[KeywordDiscovery] Done — inserted={total_inserted}, "
            f"updated={total_updated}, skipped={total_skipped}"
        )
        return stats

    # -----------------------------------------------------------------------
    # Seed loading
    # -----------------------------------------------------------------------

    def _load_seeds(self) -> List[str]:
        """Return builtin seeds + top DB keywords by quality_score (bounded to 5000)."""
        from app.models.models import Keyword

        db_terms = [
            row.term for row in
            self.db.query(Keyword.term)
            .order_by(Keyword.quality_score.desc().nullslast())
            .limit(5000)
            .all()
        ]
        combined = list(dict.fromkeys(_BUILTIN_SEEDS + db_terms))  # preserve order, dedup
        return combined

    # -----------------------------------------------------------------------
    # Phase A — static expansion
    # -----------------------------------------------------------------------

    def _static_expand(self, seeds: List[str]) -> Set[str]:
        """
        Generate variants without any network calls:
        - seed + single letter (a–z)
        - seed + each suffix modifier
        - prefix + seed
        """
        results: Set[str] = set()
        letters = list(string.ascii_lowercase)

        for seed in seeds:
            # alphabet expansion: "fitness " + "a" … "z"
            for letter in letters:
                results.add(f"{seed} {letter}")

            # suffix modifiers
            for suffix in _SUFFIXES:
                results.add(f"{seed} {suffix}")

            # prefix modifiers
            for prefix in _PREFIXES:
                results.add(f"{prefix} {seed}")

        return results

    # -----------------------------------------------------------------------
    # Phase B — Apple MZSearchHints suggestions
    # -----------------------------------------------------------------------

    async def _run_suggestions_phase(self, seeds: List[str]) -> Set[str]:
        """
        Query Apple's autocomplete API for each seed (and each seed + letter).
        Rate-limited to `concurrency` concurrent requests.
        """
        results: Set[str] = set()
        queries: List[str] = []

        # seed itself + seed+letter expansions
        for seed in seeds:
            queries.append(seed)
            for letter in string.ascii_lowercase:
                queries.append(f"{seed} {letter}")

        async def fetch_suggestions(term: str) -> List[str]:
            async with self._sem:
                url = _SUGGESTIONS_URL.format(
                    term=urllib.parse.quote_plus(term)
                )
                data = await _fetch_json(url)
                if not data:
                    return []
                # Response: {"hints": [{"term": "..."}, ...]}
                hints = data.get("hints", [])
                return [h.get("term", "").strip() for h in hints if h.get("term")]

        tasks = [fetch_suggestions(q) for q in queries]
        raw = await asyncio.gather(*tasks, return_exceptions=True)

        success = 0
        errors = 0
        for item in raw:
            if isinstance(item, Exception):
                errors += 1
            else:
                results.update(item)
                if item:
                    success += 1

        logger.info(
            f"[KeywordDiscovery] Phase B: {len(queries)} queries, "
            f"{success} with results, {errors} errors, {len(results)} unique suggestions"
        )
        return results

    # -----------------------------------------------------------------------
    # Phase C — App metadata phrase extraction
    # -----------------------------------------------------------------------

    async def _run_metadata_phase(self, seeds: List[str]) -> Set[str]:
        """
        For each seed, fetch iTunes search results and extract n-grams
        from app names, subtitles, and descriptions.
        """
        results: Set[str] = set()

        async def fetch_app_phrases(term: str) -> List[str]:
            async with self._sem:
                url = _ITUNES_SEARCH_URL.format(
                    term=urllib.parse.quote_plus(term)
                )
                data = await _fetch_json(url)
                if not data:
                    return []
                phrases: List[str] = []
                for app in data.get("results", []):
                    name = app.get("trackName", "")
                    subtitle = app.get("subtitle", "")
                    for text in (name, subtitle):
                        if text:
                            phrases.extend(self._extract_phrases(text))
                return phrases

        tasks = [fetch_app_phrases(seed) for seed in seeds]
        raw = await asyncio.gather(*tasks, return_exceptions=True)

        success = 0
        errors = 0
        for item in raw:
            if isinstance(item, Exception):
                errors += 1
            else:
                results.update(item)
                if item:
                    success += 1

        logger.info(
            f"[KeywordDiscovery] Phase C: {len(seeds)} seeds, "
            f"{success} with phrases, {errors} errors, {len(results)} unique phrases"
        )
        return results

    # -----------------------------------------------------------------------
    # Phrase extraction (n-grams)
    # -----------------------------------------------------------------------

    @staticmethod
    def _extract_phrases(text: str) -> List[str]:
        """Extract unigrams, bigrams, and trigrams from text, filtering stop words."""
        # Lowercase, remove punctuation
        clean = re.sub(r"[^\w\s]", " ", text.lower())
        tokens = [t for t in clean.split() if len(t) >= 3 and t not in _STOP_WORDS]

        phrases: List[str] = []
        # Unigrams
        phrases.extend(tokens)
        # Bigrams
        for i in range(len(tokens) - 1):
            phrases.append(f"{tokens[i]} {tokens[i+1]}")
        # Trigrams
        for i in range(len(tokens) - 2):
            phrases.append(f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}")

        return phrases

    # -----------------------------------------------------------------------
    # Normalisation + deduplication
    # -----------------------------------------------------------------------

    @staticmethod
    def _normalize_batch(candidates: List[str]) -> List[str]:
        """
        Normalize, enforce length limits, apply hard quality gate, deduplicate.
        Returns a list of unique, clean keyword strings that pass all checks.
        """
        from app.services.keyword_quality_engine import KeywordQualityEngine

        seen: Set[str] = set()
        result: List[str] = []
        rejected = 0

        for raw in candidates:
            if not raw:
                continue
            # Normalize via quality engine
            term = KeywordQualityEngine.normalize(raw)
            if not term:
                continue
            # ASCII-ish guard
            if re.search(r"[^\x20-\x7e]", term):
                rejected += 1
                continue
            # Hard quality gate
            passes, reason = KeywordQualityEngine.passes_hard_gate(term)
            if not passes:
                rejected += 1
                continue
            if term not in seen:
                seen.add(term)
                result.append(term)

        total = len(candidates)
        logger.info(
            f"[KeywordDiscovery] normalize_batch: generated={total}, "
            f"hard_gate_rejected={rejected}, proceeding={len(result)}"
        )
        return result

    # -----------------------------------------------------------------------
    # Database persistence
    # -----------------------------------------------------------------------

    def _store_keywords(self, candidates: List[str]) -> tuple[int, int, int]:
        """
        Upsert keyword candidates into the keywords table AND enqueue them
        in keyword_queue for the enrichment pipeline to drain.
        
        Uses GlobalKeywordSink to enforce the global keyword limit of 1M.

        - New keywords: insert via GlobalKeywordSink (enforces limit)
        - Existing canonical match: UPDATE times_seen += 1, last_seen_at = now
        - Exact existing term: skip (do NOT overwrite user-managed data)
        - keyword_queue: INSERT ... ON CONFLICT DO NOTHING (idempotent)

        Returns (inserted, updated, skipped).
        """
        from app.models.models import Keyword, KeywordQueue
        from app.services.keyword_quality_engine import KeywordQualityEngine
        from app.services.global_keyword_sink import GlobalKeywordSink

        if not candidates:
            return 0, 0, 0

        sink = GlobalKeywordSink(self.db)

        inserted = 0
        updated = 0
        skipped = 0
        batch_size = 500

        # Build lookup sets for deduplication.
        # Use EXISTS checks per-batch for terms instead of loading all into memory.
        # For canonical mapping, load only non-null entries (typically much smaller).
        from sqlalchemy import exists as sa_exists

        existing_terms: Set[str] = set()
        # Pre-load terms only for the candidates we're about to insert
        candidate_set = set(candidates)
        # Check in batches of 1000 to avoid oversized IN clauses
        _check_batch = 1000
        candidate_list = list(candidate_set)
        for ci in range(0, len(candidate_list), _check_batch):
            chunk = candidate_list[ci : ci + _check_batch]
            found = {
                row.term for row in
                self.db.query(Keyword.term).filter(Keyword.term.in_(chunk)).all()
            }
            existing_terms.update(found)

        canonical_to_id: dict = {
            row.canonical_term: row.id
            for row in self.db.query(Keyword.id, Keyword.canonical_term)
            .filter(Keyword.canonical_term.isnot(None))
            .all()
        }

        for i in range(0, len(candidates), batch_size):
            batch = candidates[i : i + batch_size]
            new_queue_terms = []
            canonical_updates: list = []

            terms_to_insert = []
            for term in batch:
                canonical = KeywordQualityEngine.canonicalize(term)

                if term in existing_terms:
                    if canonical in canonical_to_id:
                        canonical_updates.append(canonical_to_id[canonical])
                    skipped += 1
                    continue

                if canonical in canonical_to_id:
                    canonical_updates.append(canonical_to_id[canonical])
                    existing_terms.add(term)
                    updated += 1
                    continue

                terms_to_insert.append(term)
                new_queue_terms.append(term)
                existing_terms.add(term)

            if canonical_updates:
                try:
                    from sqlalchemy import text
                    ids_str = ",".join(str(x) for x in set(canonical_updates))
                    self.db.execute(text(
                        f"UPDATE keywords SET times_seen = COALESCE(times_seen,0)+1, "
                        f"last_seen_at = NOW() WHERE id IN ({ids_str})"
                    ))
                    self.db.commit()
                except Exception as exc:
                    logger.warning(f"[KeywordDiscovery] canonical update failed: {exc}")
                    try:
                        self.db.rollback()
                    except Exception:
                        pass

            if terms_to_insert:
                sink_inserted, sink_skipped = sink.push(
                    keywords=terms_to_insert,
                    source="discovery_engine",
                    discovered_from=None,
                )
                inserted += sink_inserted
                skipped += sink_skipped

                if sink_inserted > 0:
                    logger.debug(
                        f"[KeywordDiscovery] Stored batch {i // batch_size + 1}: "
                        f"+{sink_inserted} keywords"
                    )

            if new_queue_terms:
                try:
                    from sqlalchemy.dialects.postgresql import insert as pg_insert
                    stmt = pg_insert(KeywordQueue.__table__).values([
                        {"term": t, "source": "discovery_engine", "priority": 1}
                        for t in new_queue_terms
                    ]).on_conflict_do_nothing(index_elements=["term"])
                    self.db.execute(stmt)
                    self.db.commit()
                except Exception as exc:
                    self.db.rollback()
                    logger.warning(f"[KeywordDiscovery] Queue insert failed: {exc}")

        logger.info(
            f"[KeywordDiscovery] _store_keywords: inserted={inserted}, "
            f"canonical_dedup_updated={updated}, skipped={skipped}"
        )
        return inserted, updated, skipped
