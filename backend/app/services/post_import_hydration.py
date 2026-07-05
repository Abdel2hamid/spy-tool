"""
PostImportHydrationService
==========================
Run after a new app is imported to fill in reviews, version history,
keyword intelligence, and download/revenue estimates.

Design rules:
- Launched in a daemon thread (threading.Thread) so the HTTP response returns immediately.
- Creates its own DB sessions — never reuses the request session.
- Uses asyncio.run() to call async scrapers from the background thread (safe: each thread
  creates its own event loop and asyncio.run() is called in a fresh thread with no running loop).
- Partial failures are logged but never propagate (import stays valid).
- Only runs full hydration for is_new=True; existing apps skip the heavy scrape.
"""

import asyncio
import logging
from typing import Optional

from app.database import SessionLocal

logger = logging.getLogger(__name__)


class PostImportHydrationService:
    """
    Launched in a daemon thread immediately after a successful app import.

    Usage:
        threading.Thread(
            target=PostImportHydrationService().hydrate,
            args=(result["id"], result.get("app_id", "")),
            daemon=True,
        ).start()
    """

    def hydrate(self, app_id: int, app_store_id: str) -> None:
        """
        Run the full post-import hydration pipeline for a newly imported app.

        Steps (each in its own try/except):
          1. Full scrape: metadata refresh + reviews + version history
          2. Keyword enrichment: extraction + competitor mining + intelligence pipeline
          3. Estimation: download + revenue metric snapshot
        """
        logger.info(f"[hydration] Starting hydration for app {app_id} (store_id={app_store_id})")

        try:
            self._step_full_scrape(app_store_id)
        except Exception as exc:
            logger.warning(f"[hydration] Full scrape step failed for app {app_id}: {exc}")

        try:
            self._step_keyword_enrichment(app_id)
        except Exception as exc:
            logger.warning(f"[hydration] Keyword enrichment step failed for app {app_id}: {exc}")

        try:
            self._step_estimation(app_id)
        except Exception as exc:
            logger.warning(f"[hydration] Estimation step failed for app {app_id}: {exc}")

        logger.info(f"[hydration] Completed hydration for app {app_id}")

    # ------------------------------------------------------------------
    # Step 1: Full scrape (metadata + reviews + versions)
    # ------------------------------------------------------------------

    def _step_full_scrape(self, app_store_id: str) -> None:
        """Run the async scraper synchronously via asyncio.run()."""
        try:
            asyncio.run(self._async_full_scrape(app_store_id))
            logger.info(f"[hydration] Full scrape complete for {app_store_id}")
        except Exception as exc:
            logger.warning(f"[hydration] Full scrape failed for {app_store_id}: {exc}")

    async def _async_full_scrape(self, app_store_id: str) -> None:
        from app.workers.tasks import ScraperWorker

        worker = ScraperWorker()
        await worker.initialize()
        try:
            await worker.scrape_app_full_details(app_store_id)
        finally:
            await worker.cleanup()

    # ------------------------------------------------------------------
    # Step 2: Keyword enrichment
    # ------------------------------------------------------------------

    def _step_keyword_enrichment(self, app_id: int) -> None:
        """
        Run keyword extraction, competitor mining, and intelligence pipeline.
        Each sub-step uses its own session to avoid partial-commit leakage.
        """
        self._run_keyword_extraction(app_id)
        self._run_competitor_mining(app_id)
        self._run_intelligence_pipeline(app_id)

    def _run_keyword_extraction(self, app_id: int) -> None:
        db = SessionLocal()
        try:
            from app.services.keyword_extraction_service import KeywordExtractionService
            svc = KeywordExtractionService(db)
            svc.extract_keywords_for_app(app_id)
            logger.info(f"[hydration] Keyword extraction done for app {app_id}")
        except Exception as exc:
            logger.warning(f"[hydration] Keyword extraction failed for app {app_id}: {exc}")
        finally:
            db.close()

    def _run_competitor_mining(self, app_id: int) -> None:
        db = SessionLocal()
        try:
            from app.services.competitor_keyword_service import CompetitorKeywordService
            svc = CompetitorKeywordService(db)
            svc.mine_for_app(app_id)
            logger.info(f"[hydration] Competitor mining done for app {app_id}")
        except Exception as exc:
            logger.warning(f"[hydration] Competitor mining failed for app {app_id}: {exc}")
        finally:
            db.close()

    def _run_intelligence_pipeline(self, app_id: int) -> None:
        db = SessionLocal()
        try:
            from app.services.keyword_intelligence_pipeline import KeywordIntelligencePipeline
            svc = KeywordIntelligencePipeline(db)
            svc.enrich_app(app_id)
            logger.info(f"[hydration] Intelligence pipeline done for app {app_id}")
        except Exception as exc:
            logger.warning(f"[hydration] Intelligence pipeline failed for app {app_id}: {exc}")
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Step 3: Estimation
    # ------------------------------------------------------------------

    def _step_estimation(self, app_id: int) -> None:
        """Compute download + revenue metric snapshot."""
        db = SessionLocal()
        try:
            from app.models.models import App
            from app.services.metric_snapshot_service import MetricSnapshotService

            app = db.query(App).filter(App.id == app_id).first()
            if not app:
                logger.warning(f"[hydration] App {app_id} not found for estimation")
                return

            svc = MetricSnapshotService(db)
            svc.compute_for_app(app)
            db.commit()
            logger.info(f"[hydration] Estimation snapshot done for app {app_id}")
        except Exception as exc:
            logger.warning(f"[hydration] Estimation failed for app {app_id}: {exc}")
        finally:
            db.close()
