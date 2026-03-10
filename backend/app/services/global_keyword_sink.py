"""
Global Keyword Sink
===================
Reusable helper that upserts keyword strings into the global ``keywords`` table
with provenance metadata (keyword_source, discovered_from, first_seen_at).

All app-specific discovery pipelines (KeywordDiscoveryService,
AlphabetMiningService, CompetitorKeywordService) write their candidates to
``app_discovered_keywords`` first, then call this sink so the terms also show
up in the global table where the intelligence pipeline can enrich them.

Usage::
    from app.services.global_keyword_sink import GlobalKeywordSink

    sink = GlobalKeywordSink(db)
    inserted, skipped = sink.push(
        keywords=["focus timer", "deep work app", "pomodoro"],
        source="discovered",
        discovered_from="focus timer",   # optional: which seed led here
    )
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Maximum number of keywords to push in a single call (protection against
# very large batches blocking the DB too long).
_BATCH_SIZE = 500


class GlobalKeywordSink:
    """
    Upserts keyword terms into the global ``keywords`` table.

    Only the ``term``, ``keyword_source``, ``discovered_from``, and
    ``first_seen_at`` columns are set on INSERT — other enrichment columns
    (trend_score, difficulty, etc.) are left at their defaults so the
    intelligence pipeline can fill them in later.

    Rows that already exist (unique on ``term``) are silently skipped via
    ON CONFLICT DO NOTHING.
    """

    def __init__(self, db: Session):
        self.db = db

    def push(
        self,
        keywords: List[str],
        source: str,
        discovered_from: Optional[str] = None,
    ) -> Tuple[int, int]:
        """
        Upsert *keywords* into the global keywords table.

        Parameters
        ----------
        keywords:       Raw keyword strings (will be normalised to lowercase + stripped).
        source:         provenance label, e.g. ``"discovered"``, ``"alphabet"``,
                        ``"competitor"``, ``"opportunity"``.
        discovered_from: Optional seed term that produced these keywords.

        Returns
        -------
        (inserted, skipped): counts of newly-inserted vs already-existing rows.
        """
        from app.models.models import Keyword

        if not keywords:
            return 0, 0

        # Normalise: lowercase, strip whitespace, deduplicate, min length 3
        normalised = list({kw.strip().lower() for kw in keywords if len(kw.strip()) >= 3})

        inserted = 0
        skipped = 0
        now = datetime.now(timezone.utc)

        for i in range(0, len(normalised), _BATCH_SIZE):
            batch = normalised[i : i + _BATCH_SIZE]
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
                    f"[GlobalKeywordSink] batch insert failed "
                    f"(source={source!r}, batch_start={i}): {exc}",
                    exc_info=True,
                )

        logger.info(
            f"[GlobalKeywordSink] source={source!r}: "
            f"{inserted} inserted, {skipped} skipped (already existed)"
        )
        return inserted, skipped
