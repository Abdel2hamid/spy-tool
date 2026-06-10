"""
Global Keyword Sink
===================
Reusable helper that upserts keyword strings into the global ``keywords`` table
(dictionary only — no metrics) and optionally writes app-keyword relations into
the normalised ``app_keywords`` table.

3-table architecture
--------------------
keywords        — dictionary: id, term, created_at (+ legacy provenance cols)
keyword_metrics — intelligence: search_volume, difficulty, trend_score, …
app_keywords    — relations:  app_id, keyword_id, rank, traffic, opportunity_score

Usage::
    from app.services.global_keyword_sink import GlobalKeywordSink

    sink = GlobalKeywordSink(db)

    # 1. Insert terms into keyword dictionary
    inserted, skipped = sink.push(
        keywords=["focus timer", "deep work app", "pomodoro"],
        source="discovered",
        discovered_from="focus timer",
    )

    # 2. Wire app→keyword relations with enrichment signals
    sink.push_app_keywords(
        app_id=42,
        kw_data={
            "focus timer":  {"rank": 5,  "traffic": 12.3, "opportunity_score": 74.1},
            "deep work app": {"rank": None, "traffic": 0.5, "opportunity_score": 61.0},
        },
        source="discovered",
    )
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import AppKeyword, Keyword

logger = logging.getLogger(__name__)

# Batch size for bulk inserts (keywords dictionary)
_BATCH_SIZE = 500

# Hard limits — unified with keyword_quality_engine.py thresholds
_MAX_GLOBAL_KEYWORDS    = 1_000_000   # absolute ceiling (hard stop for all tiers)
_TIER_C_STOP_THRESHOLD  =   900_000   # above this: reject Tier-C keywords
_TIER_B_STOP_THRESHOLD  = 1_050_000   # above this: reject Tier-B too (Tier-A only)
_MAX_PER_APP = 100


class GlobalKeywordSink:
    """
    Two-phase writer for the 3-table keyword architecture.

    push()             → inserts into ``keywords`` (dictionary only, no metrics)
    push_app_keywords() → inserts into ``app_keywords`` (app→keyword relations)

    Both methods use ON CONFLICT DO NOTHING so they are safe to call repeatedly.
    """

    def __init__(self, db: Session):
        self.db = db

    # ── Phase 1: keyword dictionary ──────────────────────────────────────────

    def push(
        self,
        keywords: List[str],
        source: str,
        discovered_from: Optional[str] = None,
    ) -> Tuple[int, int]:
        """
        Upsert keyword terms into the ``keywords`` dictionary table.

        Only inserts: term, keyword_source, discovered_from, first_seen_at.
        Metric columns (search_volume, difficulty, etc.) are left at defaults
        so the intelligence pipeline can fill them in later.

        Returns
        -------
        (inserted, skipped)
        """
        if not keywords:
            return 0, 0

        from app.services.keyword_quality_engine import KeywordQualityEngine

        # ── Global count (single query, reused for all tier decisions) ────────
        global_count = self.db.query(func.count(Keyword.id)).scalar() or 0

        if global_count >= _MAX_GLOBAL_KEYWORDS:
            logger.warning(
                f"[KeywordSink] global_count={global_count:,} reached hard ceiling "
                f"({_MAX_GLOBAL_KEYWORDS:,}) — skipping all insertions (source={source!r})"
            )
            return 0, 0

        # Determine admission threshold based on current fill level.
        #
        # Because push() receives bare terms with no Apple/Trends enrichment yet,
        # we use *partial* quality scores (term + source only, max ~45).  The
        # thresholds below are calibrated to approximate the intended tier gates:
        #
        #   fill > 1,050,000  → partial >= 42  ≈ Tier-A/B sources (title/subtitle/competitor)
        #   fill >   900,000  → partial >= 35  ≈ block alphabet noise, pass trusted sources
        #   fill <=  900,000  → no threshold   (pruning job handles cleanup post-enrichment)
        #
        # Enriched keywords with accurate quality_tier are maintained by
        # keyword_quality_engine.prune_tier_c_to_target() which runs daily.
        if global_count >= _TIER_B_STOP_THRESHOLD:
            min_partial_score = 42.0   # blocks low-value sources at extreme fill
        elif global_count >= _TIER_C_STOP_THRESHOLD:
            min_partial_score = 35.0   # blocks alphabet noise, passes title/competitor
        else:
            min_partial_score = 0.0    # all terms accepted below 900k

        # ── Normalise + hard gate + canonical dedup ───────────────────────────
        # Build canonical dedup set ONLY for the canonicals of incoming keywords
        # (instead of loading ALL 1M+ canonical_terms into memory).
        existing_canonicals: set = set()
        if global_count >= _TIER_C_STOP_THRESHOLD:
            try:
                from app.services.keyword_quality_engine import KeywordQualityEngine as _KQE
                incoming_canonicals = set()
                for raw in keywords:
                    if raw:
                        c = _KQE.canonicalize(raw.strip().lower())
                        if c:
                            incoming_canonicals.add(c)
                _CHUNK = 1000
                incoming_list = list(incoming_canonicals)
                for ci in range(0, len(incoming_list), _CHUNK):
                    chunk = incoming_list[ci : ci + _CHUNK]
                    found = {
                        r[0] for r in
                        self.db.query(Keyword.canonical_term)
                        .filter(Keyword.canonical_term.in_(chunk))
                        .all()
                        if r[0]
                    }
                    existing_canonicals.update(found)
            except Exception:
                pass  # fail open — dedup is best-effort

        accepted_terms: List[str] = []
        rejected_tier_c = 0
        rejected_tier_b = 0

        seen_in_batch: set = set()

        for raw in keywords:
            if not raw:
                continue
            term = raw.strip().lower()
            if len(term) < 3:
                continue

            # Deduplicate within this call
            if term in seen_in_batch:
                continue
            seen_in_batch.add(term)

            # Skip tier-based admission check when no pressure
            if min_partial_score > 0.0:
                # Canonical dedup: if canonical already in DB, bump times_seen instead
                canonical = KeywordQualityEngine.canonicalize(term)
                if canonical and canonical in existing_canonicals:
                    # Term's canonical form already exists — treat as dedup, skip insert
                    continue

                # Compute partial quality score (term + source only; no Apple enrichment yet)
                q_score, _, _ = KeywordQualityEngine.compute_quality_score(
                    term=term,
                    keyword_source=source,
                )
                tier = KeywordQualityEngine.assign_tier(q_score)

                if q_score < min_partial_score:
                    if global_count >= _TIER_B_STOP_THRESHOLD:
                        rejected_tier_b += 1
                    else:
                        rejected_tier_c += 1
                    continue

            accepted_terms.append(term)

        # Cap to remaining slots in the table
        remaining = _MAX_GLOBAL_KEYWORDS - global_count
        if len(accepted_terms) > remaining:
            accepted_terms = accepted_terms[:remaining]

        inserted = 0
        skipped = 0
        now = datetime.now(timezone.utc)

        for i in range(0, len(accepted_terms), _BATCH_SIZE):
            batch = accepted_terms[i : i + _BATCH_SIZE]
            try:
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                stmt = (
                    pg_insert(Keyword.__table__)
                    .values(
                        [
                            {
                                "term": kw,
                                "keyword_source": source,
                                "discovered_from": discovered_from,
                                "first_seen_at": now,
                                "last_seen_at": now,
                                "canonical_term": KeywordQualityEngine.canonicalize(kw),
                                "times_seen": 1,
                            }
                            for kw in batch
                        ]
                    )
                    .on_conflict_do_nothing(index_elements=["term"])
                )
                result = self.db.execute(stmt)
                self.db.commit()
                batch_inserted = result.rowcount or 0
                inserted += batch_inserted
                skipped += len(batch) - batch_inserted
            except Exception as exc:
                self.db.rollback()
                logger.error(
                    f"[GlobalKeywordSink] push batch failed "
                    f"(source={source!r}, batch_start={i}): {exc}",
                    exc_info=True,
                )

        logger.info(
            f"[KeywordSink] global_count={global_count:,}, "
            f"accepted={len(accepted_terms)}, "
            f"rejected_tier_c={rejected_tier_c}, "
            f"rejected_tier_b={rejected_tier_b}, "
            f"inserted={inserted}, skipped={skipped} (source={source!r})"
        )
        return inserted, skipped

    # ── Phase 2: app→keyword relations ───────────────────────────────────────

    def push_app_keywords(
        self,
        app_id: int,
        kw_data: Dict[str, Dict],
        source: str,
    ) -> int:
        """
        Upsert app→keyword relations into the ``app_keywords`` table.

        Parameters
        ----------
        app_id:   DB primary key of the app.
        kw_data:  ``{term: {"rank": int|None, "traffic": float, "opportunity_score": float}}``
                  Terms that are not yet in the ``keywords`` table are silently skipped
                  (call ``push()`` first to ensure they exist).
        source:   provenance label, e.g. ``"discovered"``, ``"alphabet"``, ``"competitor"``.

        Enforces per-app limit of ``_MAX_PER_APP`` rows in ``app_keywords``.

        Returns
        -------
        Count of newly inserted rows.
        """
        if not kw_data or not app_id:
            return 0

        # ── Per-app limit guard ───────────────────────────────────────────────
        current = (
            self.db.query(func.count(AppKeyword.id))
            .filter(AppKeyword.app_id == app_id)
            .scalar() or 0
        )
        if current >= _MAX_PER_APP:
            logger.info(
                f"[KeywordLimit] app {app_id} already has {current} app_keywords "
                f"(limit={_MAX_PER_APP}) — skipping app_keywords insertion"
            )
            return 0

        slots = _MAX_PER_APP - current
        terms = list(kw_data.keys())[:slots]

        # Look up keyword IDs for these terms (only those already in `keywords`)
        id_map: Dict[str, int] = {
            row.term: row.id
            for row in (
                self.db.query(Keyword.id, Keyword.term)
                .filter(Keyword.term.in_(terms))
                .all()
            )
        }

        if not id_map:
            return 0

        now = datetime.now(timezone.utc)
        inserted = 0

        for term, keyword_id in id_map.items():
            d = kw_data.get(term, {})
            try:
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                stmt = (
                    pg_insert(AppKeyword.__table__)
                    .values(
                        app_id=app_id,
                        keyword_id=keyword_id,
                        rank=d.get("rank"),
                        traffic=float(d.get("traffic", 0.0)),
                        opportunity_score=float(d.get("opportunity_score", 0.0)),
                        source=source,
                        created_at=now,
                    )
                    .on_conflict_do_nothing(index_elements=["app_id", "keyword_id"])
                )
                result = self.db.execute(stmt)
                self.db.commit()
                inserted += result.rowcount or 0
            except Exception as exc:
                self.db.rollback()
                logger.error(
                    f"[GlobalKeywordSink] push_app_keywords failed for "
                    f"app={app_id} term={term!r}: {exc}",
                    exc_info=True,
                )

        logger.info(
            f"[GlobalKeywordSink] app {app_id}: {inserted} app_keywords inserted "
            f"(source={source!r})"
        )
        return inserted

    # ── Utility ───────────────────────────────────────────────────────────────

    def get_keyword_ids(self, terms: List[str]) -> Dict[str, int]:
        """Return {term: keyword_id} for all terms that exist in ``keywords``."""
        if not terms:
            return {}
        return {
            row.term: row.id
            for row in (
                self.db.query(Keyword.id, Keyword.term)
                .filter(Keyword.term.in_(terms))
                .all()
            )
        }
