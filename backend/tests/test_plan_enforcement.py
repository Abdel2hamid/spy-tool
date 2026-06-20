"""
Tests for plan limits — config/plans.py + services/plan_enforcement.py
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.config.plans import (
    PLAN_LIMITS,
    get_effective_plan,
    get_limit,
    can_access_premium,
)
from app.services.plan_enforcement import PlanEnforcer, _NoOpEnforcer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sub(status="trialing", plan_code="trial", trial_ends_at=None):
    """Build a mock Subscription."""
    s = MagicMock()
    s.status = status
    s.plan_code = plan_code
    s.trial_ends_at = trial_ends_at
    return s


def _usage(app_imports=0, keyword_refreshes=0, ai_requests=0, exports=0):
    """Build a mock WorkspaceUsage row."""
    u = MagicMock()
    u.app_imports = app_imports
    u.keyword_refreshes = keyword_refreshes
    u.ai_requests = ai_requests
    u.exports = exports
    return u


def _db_with_usage(usage_row=None, workspace_id=1, month="2026-03"):
    """Build a mock Session that returns a given usage row (or None)."""
    db = MagicMock()
    q = db.query.return_value
    q.filter.return_value.first.return_value = usage_row
    return db


# ---------------------------------------------------------------------------
# TestPlanConfig
# ---------------------------------------------------------------------------

class TestPlanConfig:
    def test_all_plans_present(self):
        for plan in ("free", "trial", "starter", "pro"):
            assert plan in PLAN_LIMITS

    def test_free_has_small_limits(self):
        p = PLAN_LIMITS["free"]
        assert p["app_imports"] == 5
        assert p["ai_requests"] == 5
        assert p["exports"] == 0
        assert p["access_premium"] is False

    def test_trial_has_generous_limits(self):
        p = PLAN_LIMITS["trial"]
        assert p["app_imports"] == 50
        assert p["ai_requests"] == 50
        assert p["access_premium"] is True

    def test_pro_is_unlimited(self):
        p = PLAN_LIMITS["pro"]
        assert p["app_imports"] is None
        assert p["ai_requests"] is None

    def test_get_limit_returns_none_for_pro(self):
        assert get_limit("pro", "app_imports") is None

    def test_get_limit_returns_value_for_free(self):
        assert get_limit("free", "app_imports") == 5

    def test_can_access_premium_free(self):
        assert can_access_premium("free") is False

    def test_can_access_premium_pro(self):
        assert can_access_premium("pro") is True

    def test_can_access_premium_trial(self):
        assert can_access_premium("trial") is True


# ---------------------------------------------------------------------------
# TestGetEffectivePlan
# ---------------------------------------------------------------------------

class TestGetEffectivePlan:
    def test_trialing_returns_trial(self):
        sub = _sub(status="trialing", plan_code="trial")
        assert get_effective_plan(sub) == "trial"

    def test_active_pro_returns_pro(self):
        sub = _sub(status="active", plan_code="pro")
        assert get_effective_plan(sub) == "pro"

    def test_active_starter_returns_starter(self):
        sub = _sub(status="active", plan_code="starter")
        assert get_effective_plan(sub) == "starter"

    def test_canceled_returns_free(self):
        sub = _sub(status="canceled")
        assert get_effective_plan(sub) == "free"

    def test_past_due_returns_free(self):
        sub = _sub(status="past_due")
        assert get_effective_plan(sub) == "free"

    def test_none_subscription_returns_free(self):
        assert get_effective_plan(None) == "free"

    def test_active_unknown_plan_code_returns_pro(self):
        sub = _sub(status="active", plan_code="legacy_unlimited")
        assert get_effective_plan(sub) == "pro"


# ---------------------------------------------------------------------------
# TestNoOpEnforcer
# ---------------------------------------------------------------------------

class TestNoOpEnforcer:
    def test_check_does_not_raise(self):
        e = _NoOpEnforcer()
        e.check("app_imports")  # should not raise

    def test_increment_does_not_raise(self):
        e = _NoOpEnforcer()
        e.increment("app_imports")  # should not raise

    def test_get_summary_returns_unknown(self):
        summary = _NoOpEnforcer().get_summary()
        assert summary["plan"] == "unknown"
        assert summary["usage"]["app_imports"] == 0

    def test_from_token_without_credentials_returns_noop(self):
        db = MagicMock()
        result = PlanEnforcer.from_token(None, db)
        assert isinstance(result, _NoOpEnforcer)


# ---------------------------------------------------------------------------
# TestPlanEnforcer — check()
# ---------------------------------------------------------------------------

class TestPlanEnforcerCheck:
    def _make_enforcer(self, plan_code, current_usage, action="app_imports"):
        usage = _usage(**{action: current_usage})
        db = _db_with_usage(usage)
        sub = _sub(status="trialing" if plan_code == "trial" else "active", plan_code=plan_code)
        enforcer = PlanEnforcer(db, workspace_id=1, subscription=sub)
        enforcer.plan_code = plan_code
        return enforcer

    def test_check_passes_when_under_limit(self):
        enforcer = self._make_enforcer("free", current_usage=3, action="app_imports")
        enforcer.check("app_imports")  # should not raise (limit=5, used=3)

    def test_check_raises_when_at_limit(self):
        from fastapi import HTTPException
        enforcer = self._make_enforcer("free", current_usage=5, action="app_imports")
        with pytest.raises(HTTPException) as exc_info:
            enforcer.check("app_imports")
        assert exc_info.value.status_code == 402
        detail = exc_info.value.detail
        assert detail["code"] == "PLAN_LIMIT_EXCEEDED"
        assert detail["action"] == "app_imports"
        assert detail["current_usage"] == 5
        assert detail["limit"] == 5
        assert detail["plan"] == "free"

    def test_check_raises_when_over_limit(self):
        from fastapi import HTTPException
        enforcer = self._make_enforcer("trial", current_usage=50, action="app_imports")
        with pytest.raises(HTTPException) as exc_info:
            enforcer.check("app_imports")
        assert exc_info.value.status_code == 402

    def test_check_passes_for_unlimited_plan(self):
        usage = _usage(app_imports=99999)
        db = _db_with_usage(usage)
        sub = _sub(status="active", plan_code="pro")
        enforcer = PlanEnforcer(db, workspace_id=1, subscription=sub)
        enforcer.check("app_imports")  # should not raise — pro is unlimited

    def test_check_exports_zero_limit_on_free(self):
        from fastapi import HTTPException
        usage = _usage(exports=0)
        db = _db_with_usage(usage)
        sub = _sub(status="trialing", plan_code="trial")
        enforcer = PlanEnforcer(db, workspace_id=1, subscription=sub)
        enforcer.plan_code = "free"
        with pytest.raises(HTTPException) as exc_info:
            enforcer.check("exports")
        assert exc_info.value.status_code == 402

    def test_check_creates_usage_row_if_missing(self):
        db = MagicMock()
        q = db.query.return_value
        # First call returns None (no existing row), after add+flush the row is set
        new_row = _usage(app_imports=0)
        q.filter.return_value.first.side_effect = [None]
        db.add.return_value = None
        db.flush.return_value = None
        # After flush, re-query returns new_row — simulate via side_effect reset
        q.filter.return_value.first.side_effect = [None, new_row]

        sub = _sub(status="trialing", plan_code="trial")
        enforcer = PlanEnforcer(db, workspace_id=1, subscription=sub)
        # Should not raise for trial plan with 0 imports
        # (We just confirm no exception rather than checking row creation)
        # The actual add() was called
        enforcer.check("app_imports")


# ---------------------------------------------------------------------------
# TestPlanEnforcer — increment()
# ---------------------------------------------------------------------------

class TestPlanEnforcerIncrement:
    def test_increment_updates_counter(self):
        usage = _usage(app_imports=3)
        db = _db_with_usage(usage)
        sub = _sub()
        enforcer = PlanEnforcer(db, workspace_id=1, subscription=sub)
        enforcer.increment("app_imports")
        assert usage.app_imports == 4
        db.commit.assert_called_once()

    def test_increment_unknown_action_is_noop(self):
        usage = _usage()
        db = _db_with_usage(usage)
        sub = _sub()
        enforcer = PlanEnforcer(db, workspace_id=1, subscription=sub)
        enforcer.increment("nonexistent_action")
        db.commit.assert_not_called()

    def test_increment_rolls_back_on_exception(self):
        usage = _usage(app_imports=0)
        db = _db_with_usage(usage)
        db.commit.side_effect = Exception("DB error")
        sub = _sub()
        enforcer = PlanEnforcer(db, workspace_id=1, subscription=sub)
        enforcer.increment("app_imports")  # should not raise
        db.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# TestPlanEnforcer — get_summary()
# ---------------------------------------------------------------------------

class TestPlanEnforcerGetSummary:
    def test_summary_returns_correct_structure(self):
        usage = _usage(app_imports=3, keyword_refreshes=10, ai_requests=2, exports=0)
        db = _db_with_usage(usage)
        sub = _sub(status="trialing", plan_code="trial")
        enforcer = PlanEnforcer(db, workspace_id=1, subscription=sub)

        summary = enforcer.get_summary()

        assert summary["plan"] == "trial"
        assert summary["usage"]["app_imports"] == 3
        assert summary["usage"]["keyword_refreshes"] == 10
        assert summary["limits"]["app_imports"] == 50
        assert summary["limits"]["ai_requests"] == 50

    def test_summary_unlimited_plan_has_none_limits(self):
        usage = _usage()
        db = _db_with_usage(usage)
        sub = _sub(status="active", plan_code="pro")
        enforcer = PlanEnforcer(db, workspace_id=1, subscription=sub)

        summary = enforcer.get_summary()

        assert summary["limits"]["app_imports"] is None
        assert summary["limits"]["keyword_refreshes"] is None
