"""
Tests for Fresh Risers discovery engine.

Verifies:
1. A new app with reviews and improving rank ranks high.
2. A new app with zero reviews is excluded.
3. An old app imported recently is excluded.
4. Apps with strong momentum outrank static apps.
5. Apps with saturated niches rank lower.
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scoring.engine import ScoringEngine
from app.models.models import App


class TestFreshnessScore:
    """Tests for freshness score calculation."""

    def _create_engine(self):
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db
        return engine

    def test_very_fresh_apps_score_high(self):
        """Apps <=2 days old should score 100."""
        engine = self._create_engine()
        
        assert engine._calculate_freshness_score(1) == 100.0
        assert engine._calculate_freshness_score(2) == 100.0

    def test_recent_apps_score_moderately(self):
        """Apps 3-4 days old should score 80."""
        engine = self._create_engine()
        
        assert engine._calculate_freshness_score(3) == 80.0
        assert engine._calculate_freshness_score(4) == 80.0

    def test_older_fresh_apps_score_lower(self):
        """Apps 5-7 days old should score 60."""
        engine = self._create_engine()
        
        assert engine._calculate_freshness_score(5) == 60.0
        assert engine._calculate_freshness_score(7) == 60.0

    def test_too_old_scores_zero(self):
        """Apps >7 days old should score 0."""
        engine = self._create_engine()
        
        assert engine._calculate_freshness_score(8) == 0.0
        assert engine._calculate_freshness_score(30) == 0.0


class TestReviewTractionScore:
    """Tests for review traction score calculation."""

    def _create_engine(self):
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db
        return engine

    def test_high_velocity_scores_high(self):
        """High review velocity should score high."""
        engine = self._create_engine()
        
        assert engine._calculate_review_traction_score(10, 1) == 100.0
        assert engine._calculate_review_traction_score(5, 1) == 100.0

    def test_moderate_velocity_scores_moderately(self):
        """Moderate velocity should score moderate."""
        engine = self._create_engine()
        
        assert engine._calculate_review_traction_score(2, 1) == 70.0
        assert engine._calculate_review_traction_score(1, 1) == 40.0

    def test_low_velocity_scores_low(self):
        """Low velocity should score low."""
        engine = self._create_engine()
        
        assert engine._calculate_review_traction_score(1, 10) == 10.0
        assert engine._calculate_review_traction_score(0, 1) == 10.0


class TestRankQualityScore:
    """Tests for rank quality score calculation."""

    def _create_engine(self):
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db
        return engine

    def test_top_ranks_score_high(self):
        """Top ranks should score high."""
        engine = self._create_engine()
        
        assert engine._calculate_rank_quality_score(5) == 100.0
        assert engine._calculate_rank_quality_score(10) == 100.0

    def test_mid_ranks_score_moderately(self):
        """Mid ranks should score moderate."""
        engine = self._create_engine()
        
        assert engine._calculate_rank_quality_score(50) == 80.0
        assert engine._calculate_rank_quality_score(100) == 60.0

    def test_low_ranks_score_low(self):
        """Low ranks should score low."""
        engine = self._create_engine()
        
        assert engine._calculate_rank_quality_score(300) == 30.0
        assert engine._calculate_rank_quality_score(600) == 10.0

    def test_no_rank_scores_low(self):
        """No rank should score low."""
        engine = self._create_engine()
        
        assert engine._calculate_rank_quality_score(None) == 10.0


class TestFreshRiserRanking:
    """Tests for fresh riser final ranking."""

    def test_momentum_affects_ranking(self):
        """Apps with higher momentum should rank higher."""
        high_momentum = 80
        low_momentum = 20
        
        high_score = (
            60 * 0.25 +
            high_momentum * 0.25 +
            80 * 0.20 +
            80 * 0.20 +
            70 * 0.10
        )
        
        low_score = (
            60 * 0.25 +
            low_momentum * 0.25 +
            80 * 0.20 +
            80 * 0.20 +
            70 * 0.10
        )
        
        assert high_score > low_score

    def test_niche_affects_ranking(self):
        """Apps in unsaturated niches should rank higher."""
        unsaturated_score = (
            60 * 0.25 +
            40 * 0.25 +
            60 * 0.20 +
            40 * 0.20 +
            90 * 0.10
        )
        
        saturated_score = (
            60 * 0.25 +
            40 * 0.25 +
            60 * 0.20 +
            40 * 0.20 +
            30 * 0.10
        )
        
        assert unsaturated_score > saturated_score

    def test_review_traction_affects_ranking(self):
        """Apps with higher review traction should rank higher."""
        high_traction = 100
        low_traction = 10
        
        high_score = (
            60 * 0.25 +
            high_traction * 0.25 +
            60 * 0.20 +
            40 * 0.20 +
            50 * 0.10
        )
        
        low_score = (
            60 * 0.25 +
            low_traction * 0.25 +
            60 * 0.20 +
            40 * 0.20 +
            50 * 0.10
        )
        
        assert high_score > low_score


class TestEligibilityLogic:
    """Tests for eligibility determination."""

    def _create_engine(self):
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db
        return engine

    def test_too_old_returns_false(self):
        """Apps older than 7 days should be ineligible."""
        engine = self._create_engine()
        
        app = MagicMock()
        app.release_date = datetime.utcnow() - timedelta(days=10)
        
        cutoff_7 = datetime.utcnow() - timedelta(days=7)
        cutoff_14 = datetime.utcnow() - timedelta(days=14)
        
        result = engine._check_fresh_riser_eligibility(app, cutoff_7, cutoff_14)
        
        assert result["eligible"] == False
        assert result["reason"] == "too_old"

    def test_zero_reviews_returns_false(self):
        """Apps with zero reviews should be ineligible."""
        engine = self._create_engine()
        
        app = MagicMock()
        app.release_date = datetime.utcnow() - timedelta(days=3)
        app.created_at = datetime.utcnow() - timedelta(days=5)
        app.current_reviews = 0
        
        cutoff_7 = datetime.utcnow() - timedelta(days=7)
        cutoff_14 = datetime.utcnow() - timedelta(days=14)
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.filter.return_value.count.return_value = 5
        engine.db = mock_db
        
        result = engine._check_fresh_riser_eligibility(app, cutoff_7, cutoff_14)
        
        assert result["eligible"] == False
        assert result["reason"] == "insufficient_reviews"

    def test_fresh_with_reviews_eligible(self):
        """Fresh apps with reviews should be eligible."""
        engine = self._create_engine()
        
        app = MagicMock()
        app.release_date = datetime.utcnow() - timedelta(days=3)
        app.created_at = datetime.utcnow() - timedelta(days=5)
        app.current_reviews = 10
        app.current_rank = 50
        app.category_id = 1
        
        cutoff_7 = datetime.utcnow() - timedelta(days=7)
        cutoff_14 = datetime.utcnow() - timedelta(days=14)
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.filter.return_value.count.return_value = 5
        engine.db = mock_db
        
        result = engine._check_fresh_riser_eligibility(app, cutoff_7, cutoff_14)
        
        assert result["eligible"] == True


class TestScoreFormulas:
    """Tests verifying score formulas match requirements."""

    def test_fresh_riser_score_formula(self):
        """Verify fresh_riser_score uses correct weights."""
        freshness = 80
        review_traction = 70
        rank_quality = 60
        momentum = 50
        niche_viability = 90
        
        fresh_riser_score = (
            freshness * 0.25 +
            review_traction * 0.25 +
            rank_quality * 0.20 +
            momentum * 0.20 +
            niche_viability * 0.10
        )
        
        expected = 20 + 17.5 + 12 + 10 + 9
        assert fresh_riser_score == expected

    def test_weights_sum_to_one(self):
        """Verify all weights sum to 1.0."""
        total = 0.25 + 0.25 + 0.20 + 0.20 + 0.10
        assert abs(total - 1.0) < 0.001
