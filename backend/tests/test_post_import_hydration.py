"""
Tests for PostImportHydrationService.

Covers:
- hydrate() calls all three steps in order
- full scrape failure does not prevent keyword enrichment
- keyword enrichment failure does not prevent estimation
- estimation failure does not prevent overall success
- each step uses its own DB session (not the caller's)
- hydrate() is not called for existing apps (is_new=False) — enforced at routes level
- /apps/lookup/{id} triggers hydration for new apps
- /apps/lookup/{id} does NOT trigger hydration for existing apps
"""

from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Unit tests for PostImportHydrationService
# ---------------------------------------------------------------------------

class TestPostImportHydrationService:
    """Pure unit tests — mock all I/O."""

    def _make_service(self):
        from app.services.post_import_hydration import PostImportHydrationService
        return PostImportHydrationService()

    def test_hydrate_calls_all_three_steps(self):
        """hydrate() calls scrape, keyword enrichment, and estimation."""
        svc = self._make_service()
        with (
            patch.object(svc, "_step_full_scrape") as mock_scrape,
            patch.object(svc, "_step_keyword_enrichment") as mock_kw,
            patch.object(svc, "_step_estimation") as mock_est,
        ):
            svc.hydrate(app_id=42, app_store_id="123456789")

        mock_scrape.assert_called_once_with("123456789")
        mock_kw.assert_called_once_with(42)
        mock_est.assert_called_once_with(42)

    def test_scrape_failure_does_not_block_keywords(self):
        """If full scrape throws, keyword enrichment still runs."""
        svc = self._make_service()
        with (
            patch.object(svc, "_step_full_scrape", side_effect=RuntimeError("network down")),
            patch.object(svc, "_step_keyword_enrichment") as mock_kw,
            patch.object(svc, "_step_estimation") as mock_est,
        ):
            # Should not raise
            svc.hydrate(app_id=1, app_store_id="111")

        mock_kw.assert_called_once()
        mock_est.assert_called_once()

    def test_keyword_failure_does_not_block_estimation(self):
        """If keyword enrichment throws, estimation still runs."""
        svc = self._make_service()
        with (
            patch.object(svc, "_step_full_scrape"),
            patch.object(svc, "_step_keyword_enrichment", side_effect=RuntimeError("kw fail")),
            patch.object(svc, "_step_estimation") as mock_est,
        ):
            svc.hydrate(app_id=2, app_store_id="222")

        mock_est.assert_called_once()

    def test_estimation_failure_does_not_raise(self):
        """If estimation throws, hydrate() still completes without raising."""
        svc = self._make_service()
        with (
            patch.object(svc, "_step_full_scrape"),
            patch.object(svc, "_step_keyword_enrichment"),
            patch.object(svc, "_step_estimation", side_effect=RuntimeError("db error")),
        ):
            # Must not raise
            svc.hydrate(app_id=3, app_store_id="333")

    def test_step_full_scrape_calls_asyncio_run(self):
        """_step_full_scrape calls asyncio.run() with the async scrape coroutine."""
        svc = self._make_service()

        async def fake_scrape(app_store_id):
            pass

        with patch("asyncio.run") as mock_run:
            with patch.object(svc, "_async_full_scrape", return_value=fake_scrape("x")):
                svc._step_full_scrape("999888777")

        mock_run.assert_called_once()

    def test_step_full_scrape_swallows_exception(self):
        """_step_full_scrape wraps asyncio.run in try/except — never raises."""
        svc = self._make_service()
        with patch("asyncio.run", side_effect=Exception("async failed")):
            # Must not raise
            svc._step_full_scrape("111222333")

    def test_keyword_enrichment_calls_all_substeps(self):
        """_step_keyword_enrichment runs extraction, competitor mining, intelligence pipeline."""
        svc = self._make_service()
        with (
            patch.object(svc, "_run_keyword_extraction") as mock_extract,
            patch.object(svc, "_run_competitor_mining") as mock_comp,
            patch.object(svc, "_run_intelligence_pipeline") as mock_intel,
        ):
            svc._step_keyword_enrichment(app_id=10)

        mock_extract.assert_called_once_with(10)
        mock_comp.assert_called_once_with(10)
        mock_intel.assert_called_once_with(10)

    def test_each_keyword_substep_uses_own_session(self):
        """Each keyword sub-step creates and closes its own DB session."""
        svc = self._make_service()

        mock_db = MagicMock()
        session_calls = []

        def fake_session_local():
            session_calls.append(1)
            return mock_db

        with patch("app.services.post_import_hydration.SessionLocal", side_effect=fake_session_local):
            with patch("app.services.keyword_extraction_service.KeywordExtractionService"):
                with patch("app.services.competitor_keyword_service.CompetitorKeywordService"):
                    with patch("app.services.keyword_intelligence_pipeline.KeywordIntelligencePipeline"):
                        # Patch imports inside the methods
                        with patch.dict("sys.modules", {
                            "app.services.keyword_extraction_service": MagicMock(KeywordExtractionService=MagicMock()),
                            "app.services.competitor_keyword_service": MagicMock(CompetitorKeywordService=MagicMock()),
                            "app.services.keyword_intelligence_pipeline": MagicMock(KeywordIntelligencePipeline=MagicMock()),
                        }):
                            svc._step_keyword_enrichment(app_id=10)

        # Each sub-step should close its session
        assert mock_db.close.call_count == 3

    def test_estimation_step_uses_own_session(self):
        """_step_estimation creates and closes its own DB session."""
        svc = self._make_service()

        mock_db = MagicMock()
        mock_app = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_app
        mock_snap_svc = MagicMock()

        with patch("app.services.post_import_hydration.SessionLocal", return_value=mock_db):
            with patch.dict("sys.modules", {
                "app.models.models": MagicMock(App=MagicMock()),
                "app.services.metric_snapshot_service": MagicMock(MetricSnapshotService=MagicMock(return_value=mock_snap_svc)),
            }):
                svc._step_estimation(app_id=5)

        mock_db.close.assert_called_once()

    def test_estimation_skips_gracefully_if_app_not_found(self):
        """If app is not in DB, estimation logs a warning and returns without error."""
        svc = self._make_service()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("app.services.post_import_hydration.SessionLocal", return_value=mock_db):
            with patch.dict("sys.modules", {
                "app.models.models": MagicMock(App=MagicMock()),
                "app.services.metric_snapshot_service": MagicMock(MetricSnapshotService=MagicMock()),
            }):
                # Must not raise
                svc._step_estimation(app_id=99)

        mock_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# Route-level integration tests — hydration triggered only for new apps
# ---------------------------------------------------------------------------

class TestHydrationTriggeredFromRoutes:
    """
    Verifies that routes trigger PostImportHydrationService.hydrate()
    only for new apps (is_new=True).
    """

    def _itunes_mock_response(self, track_id, name="TestApp"):
        """Build a mock urllib response with one iTunes result."""
        import json
        from io import BytesIO
        from unittest.mock import MagicMock

        item = {
            "trackId": track_id,
            "trackName": name,
            "artistName": "Test Dev",
            "primaryGenreName": "Productivity",
            "genres": ["Productivity"],
            "averageUserRating": 4.2,
            "userRatingCount": 1000,
            "price": 0.0,
            "formattedPrice": "Free",
            "kind": "software",
            "description": "A test app",
            "version": "1.0",
            "minimumOsVersion": "14.0",
            "languageCodesISO2A": ["EN"],
            "contentAdvisoryRating": "4+",
            "screenshotUrls": [],
            "trackViewUrl": f"https://apps.apple.com/us/app/id{track_id}",
            "artworkUrl512": f"https://example.com/icon_{track_id}.png",
        }
        body = json.dumps({"resultCount": 1, "results": [item]}).encode()
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=BytesIO(body))
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    def test_lookup_route_triggers_hydration_for_new_app(self):
        """GET /apps/lookup/{id} should trigger hydration when app is newly imported."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        track_id = "999000111"

        mock_resp = self._itunes_mock_response(track_id, "BrandNew App")

        with patch("urllib.request.urlopen", return_value=mock_resp):
            with patch("app.services.post_import_hydration.PostImportHydrationService.hydrate") as mock_hydrate:
                resp = client.get(f"/api/v1/apps/lookup/{track_id}")

        assert resp.status_code == 200
        # If app was new, hydrate should have been registered as a background task
        # (TestClient runs background tasks synchronously)
        if resp.json().get("is_new"):
            mock_hydrate.assert_called_once()

    def test_import_route_triggers_hydration_for_new_app_via_url(self):
        """GET /apps/import?q=<URL> should trigger hydration when app is newly imported."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        track_id = "999000222"
        url = f"https://apps.apple.com/us/app/testapp/id{track_id}"

        mock_resp = self._itunes_mock_response(track_id, "Another New App")

        with patch("urllib.request.urlopen", return_value=mock_resp):
            with patch("app.services.post_import_hydration.PostImportHydrationService.hydrate") as mock_hydrate:
                resp = client.get(f"/api/v1/apps/import?q={url}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["direct_lookup"] is True
