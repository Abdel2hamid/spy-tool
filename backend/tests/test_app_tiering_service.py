"""
Tests for AppTieringService — HOT/WARM/COLD classification logic.
"""
from unittest.mock import MagicMock, patch, call

import pytest

from app.services.app_tiering_service import AppTieringService, _RECLASSIFY_SQL, _RECLASSIFY_SQL_NO_BUS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(rowcount1=5, rowcount2=3):
    """Create a mock DB session that simulates two successful UPDATE runs."""
    db = MagicMock()
    result1 = MagicMock()
    result1.rowcount = rowcount1
    result2 = MagicMock()
    result2.rowcount = rowcount2
    db.execute.side_effect = [result1, result2]
    return db


# ---------------------------------------------------------------------------
# SQL content
# ---------------------------------------------------------------------------

class TestSQLContent:
    def test_hot_rank_condition(self):
        assert "current_rank <= 200" in _RECLASSIFY_SQL

    def test_hot_freshness_condition(self):
        assert "freshness_score >= 80" in _RECLASSIFY_SQL

    def test_hot_new_app_condition(self):
        assert "3 days" in _RECLASSIFY_SQL

    def test_hot_blowing_up_condition(self):
        assert "blowing_up_score >= 60" in _RECLASSIFY_SQL

    def test_warm_rank_condition(self):
        assert "current_rank <= 2000" in _RECLASSIFY_SQL

    def test_warm_freshness_condition(self):
        assert "freshness_score >= 40" in _RECLASSIFY_SQL

    def test_warm_reviews_condition(self):
        assert "current_reviews >= 100" in _RECLASSIFY_SQL

    def test_warm_age_condition(self):
        assert "30 days" in _RECLASSIFY_SQL

    def test_cold_fallback(self):
        assert "cold" in _RECLASSIFY_SQL.lower()

    def test_staleness_guard(self):
        assert "6 hours" in _RECLASSIFY_SQL

    def test_no_bus_sql_lacks_blowing_up_join(self):
        # NO_BUS SQL excludes apps that *have* a blowing_up_scores row via NOT IN
        # (not a JOIN) — verifies it uses the subquery exclusion pattern
        assert "NOT IN" in _RECLASSIFY_SQL_NO_BUS
        # No FROM-JOIN to app_blowing_up_scores (the join alias 'abs_score' used in pass 1)
        assert "abs_score" not in _RECLASSIFY_SQL_NO_BUS


# ---------------------------------------------------------------------------
# reclassify_all()
# ---------------------------------------------------------------------------

class TestReclassifyAll:
    def test_returns_sum_of_both_passes(self):
        db = _make_db(rowcount1=7, rowcount2=3)
        svc = AppTieringService(db)
        total = svc.reclassify_all()
        assert total == 10

    def test_both_commits_called(self):
        db = _make_db()
        AppTieringService(db).reclassify_all()
        assert db.commit.call_count == 2

    def test_pass1_sql_uses_join(self):
        db = _make_db()
        AppTieringService(db).reclassify_all()
        first_call_sql = str(db.execute.call_args_list[0][0][0])
        assert "app_blowing_up_scores" in first_call_sql

    def test_pass2_sql_uses_not_in(self):
        db = _make_db()
        AppTieringService(db).reclassify_all()
        second_call_sql = str(db.execute.call_args_list[1][0][0])
        assert "NOT IN" in second_call_sql

    def test_pass1_failure_rolls_back_and_continues(self):
        """If pass 1 fails, rollback is called and pass 2 still runs."""
        db = MagicMock()
        result2 = MagicMock()
        result2.rowcount = 5
        db.execute.side_effect = [Exception("DB error"), result2]

        svc = AppTieringService(db)
        total = svc.reclassify_all()

        db.rollback.assert_called_once()
        assert total == 5  # pass 1 contributed 0 (failed), pass 2 contributed 5

    def test_pass2_failure_rolls_back(self):
        """If pass 2 fails, rollback is called; total = pass1 rows only."""
        db = MagicMock()
        result1 = MagicMock()
        result1.rowcount = 4
        db.execute.side_effect = [result1, Exception("DB error 2")]

        svc = AppTieringService(db)
        total = svc.reclassify_all()

        assert db.rollback.call_count == 1
        assert total == 4

    def test_negative_rowcount_treated_as_zero(self):
        """Some DB drivers return -1 for rowcount; treat as 0."""
        db = MagicMock()
        result1 = MagicMock()
        result1.rowcount = -1
        result2 = MagicMock()
        result2.rowcount = -1
        db.execute.side_effect = [result1, result2]

        total = AppTieringService(db).reclassify_all()
        assert total == 0

    def test_both_passes_fail_returns_0(self):
        db = MagicMock()
        db.execute.side_effect = [Exception("err1"), Exception("err2")]
        total = AppTieringService(db).reclassify_all()
        assert total == 0
        assert db.rollback.call_count == 2

    def test_execute_called_twice(self):
        db = _make_db()
        AppTieringService(db).reclassify_all()
        assert db.execute.call_count == 2


# ---------------------------------------------------------------------------
# Tier SQL correctness smoke test
# ---------------------------------------------------------------------------

class TestTierSQLSmokeTest:
    """Verify tier rules are encoded in correct CASE WHEN order (HOT > WARM > COLD)."""

    def test_hot_appears_before_warm(self):
        hot_pos = _RECLASSIFY_SQL.index("'hot'")
        warm_pos = _RECLASSIFY_SQL.index("'warm'")
        assert hot_pos < warm_pos, "HOT must be checked before WARM in CASE WHEN"

    def test_warm_appears_before_cold(self):
        warm_pos = _RECLASSIFY_SQL.index("'warm'")
        cold_pos = _RECLASSIFY_SQL.index("'cold'")
        assert warm_pos < cold_pos, "WARM must be checked before COLD in CASE WHEN"

    def test_tier_computed_at_updated(self):
        assert "tier_computed_at = NOW()" in _RECLASSIFY_SQL
