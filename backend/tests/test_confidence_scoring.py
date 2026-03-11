"""
Tests for confidence-aware keyword opportunity scoring.

Verifies that:
1. High base score + low confidence → lower final rank
2. Medium base score + high confidence → higher final rank
3. Stale keyword signals are penalized
4. Missing metrics reduce confidence
5. Estimated metrics reduce confidence
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scoring.engine import ScoringEngine
from app.models.models import Keyword


class TestSignalConfidenceCalculation:
    """Tests for signal confidence calculation."""

    def _create_engine(self):
        """Create ScoringEngine with mocked db."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db
        return engine

    def test_complete_fresh_observed_data_high_confidence(self):
        """Complete, fresh, observed data should have high confidence."""
        engine = self._create_engine()
        
        kw = MagicMock(spec=Keyword)
        kw.search_volume = 1000
        kw.difficulty = 30.0
        kw.trend_score = 50.0
        kw.trend_growth = 10.0
        kw.last_enriched = datetime.utcnow() - timedelta(days=2)
        kw.last_updated = datetime.utcnow() - timedelta(days=2)
        kw.status = "enriched"
        kw.quality_tier = 'A'
        
        confidence = engine.calculate_keyword_signal_confidence(kw)
        
        assert confidence >= 0.8

    def test_stale_data_penalized(self):
        """Stale data (>90 days) should have lower confidence."""
        engine = self._create_engine()
        
        kw = MagicMock(spec=Keyword)
        kw.search_volume = 1000
        kw.difficulty = 30.0
        kw.trend_score = 50.0
        kw.trend_growth = 10.0
        kw.last_enriched = datetime.utcnow() - timedelta(days=100)
        kw.last_updated = datetime.utcnow() - timedelta(days=100)
        kw.status = "enriched"
        kw.quality_tier = 'A'
        
        confidence = engine.calculate_keyword_signal_confidence(kw)
        
        assert confidence < 0.5

    def test_missing_metrics_reduce_confidence(self):
        """Missing metrics should reduce confidence."""
        engine = self._create_engine()
        
        kw = MagicMock(spec=Keyword)
        kw.search_volume = 0
        kw.difficulty = 0
        kw.trend_score = 0
        kw.trend_growth = None
        kw.last_enriched = None
        kw.last_updated = None
        kw.status = "raw"
        kw.quality_tier = None
        
        confidence = engine.calculate_keyword_signal_confidence(kw)
        
        assert confidence < 0.3

    def test_raw_status_reduces_confidence(self):
        """Raw status should have lower confidence than enriched."""
        engine = self._create_engine()
        
        kw = MagicMock(spec=Keyword)
        kw.search_volume = 500
        kw.difficulty = 40.0
        kw.trend_score = 30.0
        kw.trend_growth = 5.0
        kw.last_enriched = datetime.utcnow() - timedelta(days=10)
        kw.last_updated = datetime.utcnow() - timedelta(days=10)
        kw.status = "raw"
        kw.quality_tier = None
        
        confidence = engine.calculate_keyword_signal_confidence(kw)
        
        assert confidence < 0.7

    def test_quality_tier_affects_confidence(self):
        """Quality tier should affect confidence."""
        engine = self._create_engine()
        
        kw = MagicMock()
        kw.search_volume = 500
        kw.difficulty = 40.0
        kw.trend_score = 30.0
        kw.trend_growth = 5.0
        kw.last_enriched = datetime.utcnow() - timedelta(days=10)
        kw.last_updated = datetime.utcnow() - timedelta(days=10)
        kw.status = "enriched"
        
        kw_A = MagicMock()
        kw_A.quality_tier = 'A'
        
        kw_B = MagicMock()
        kw_B.quality_tier = 'B'
        
        kw_C = MagicMock()
        kw_C.quality_tier = 'C'
        
        for kw in [kw_A, kw_B, kw_C]:
            kw.search_volume = 500
            kw.difficulty = 40.0
            kw.trend_score = 30.0
            kw.trend_growth = 5.0
            kw.last_enriched = datetime.utcnow() - timedelta(days=10)
            kw.last_updated = datetime.utcnow() - timedelta(days=10)
            kw.status = "enriched"
        
        conf_A = engine.calculate_keyword_signal_confidence(kw_A)
        conf_B = engine.calculate_keyword_signal_confidence(kw_B)
        conf_C = engine.calculate_keyword_signal_confidence(kw_C)
        
        assert conf_A >= conf_B >= conf_C


class TestAdjustedOpportunityScore:
    """Tests for adjusted opportunity scoring."""

    def test_high_base_low_confidence_ranks_lower(self):
        """High base score with low confidence should rank lower than medium with high."""
        engine = ScoringEngine.__new__(ScoringEngine)
        mock_db = MagicMock()
        engine.db = mock_db
        
        keyword_high_base = MagicMock()
        keyword_high_base.id = 1
        keyword_high_base.term = "high base"
        keyword_high_base.search_volume = 5000
        keyword_high_base.difficulty = 10.0
        keyword_high_base.trend = 80.0
        keyword_high_base.trend_score = 80.0
        keyword_high_base.trend_growth = 20.0
        keyword_high_base.last_enriched = None
        keyword_high_base.last_updated = None
        keyword_high_base.status = "raw"
        keyword_high_base.quality_tier = None
        
        keyword_med_high_conf = MagicMock()
        keyword_med_high_conf.id = 2
        keyword_med_high_conf.term = "medium high conf"
        keyword_med_high_conf.search_volume = 1000
        keyword_med_high_conf.difficulty = 30.0
        keyword_med_high_conf.trend = 40.0
        keyword_med_high_conf.trend_score = 40.0
        keyword_med_high_conf.trend_growth = 10.0
        keyword_med_high_conf.last_enriched = datetime.utcnow() - timedelta(days=5)
        keyword_med_high_conf.last_updated = datetime.utcnow() - timedelta(days=5)
        keyword_med_high_conf.status = "enriched"
        keyword_med_high_conf.quality_tier = 'A'
        
        def mock_query_side_effect(*args):
            if Keyword in args:
                m = MagicMock()
                m.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
                    keyword_high_base, keyword_med_high_conf
                ]
                return m
            return MagicMock()
        
        mock_db.query.side_effect = mock_query_side_effect
        
        base_high = (
            (100 - 10.0) * 0.3 +
            80.0 * 0.4 +
            (5000 / 1000) * 0.2 +
            (1 / 1) * 10
        )
        
        base_medium = (
            (100 - 30.0) * 0.3 +
            40.0 * 0.4 +
            (1000 / 1000) * 0.2 +
            (1 / 1) * 10
        )
        
        confidence_high_base = engine.calculate_keyword_signal_confidence(keyword_high_base)
        confidence_med_high = engine.calculate_keyword_signal_confidence(keyword_med_high_conf)
        
        adjusted_high = base_high * confidence_high_base
        adjusted_medium = base_medium * confidence_med_high
        
        assert adjusted_medium > adjusted_high, f"Medium with high confidence ({adjusted_medium}) should rank higher than high base with low ({adjusted_high})"

    def test_confidence_includes_freshness_factor(self):
        """Freshness factor should penalize old data."""
        engine = self._create_engine()
        
        kw_recent = MagicMock()
        kw_recent.search_volume = 1000
        kw_recent.difficulty = 30.0
        kw_recent.trend_score = 50.0
        kw_recent.trend_growth = 10.0
        kw_recent.last_enriched = datetime.utcnow() - timedelta(days=3)
        kw_recent.last_updated = datetime.utcnow() - timedelta(days=3)
        kw_recent.status = "enriched"
        kw_recent.quality_tier = 'A'
        
        kw_old = MagicMock()
        kw_old.search_volume = 1000
        kw_old.difficulty = 30.0
        kw_old.trend_score = 50.0
        kw_old.trend_growth = 10.0
        kw_old.last_enriched = datetime.utcnow() - timedelta(days=60)
        kw_old.last_updated = datetime.utcnow() - timedelta(days=60)
        kw_old.status = "enriched"
        kw_old.quality_tier = 'A'
        
        conf_recent = engine.calculate_keyword_signal_confidence(kw_recent)
        conf_old = engine.calculate_keyword_signal_confidence(kw_old)
        
        assert conf_recent > conf_old

    def test_missing_metrics_affects_confidence(self):
        """Missing metrics should reduce confidence score."""
        engine = self._create_engine()
        
        kw_complete = MagicMock()
        kw_complete.search_volume = 1000
        kw_complete.difficulty = 30.0
        kw_complete.trend_score = 50.0
        kw_complete.trend_growth = 10.0
        kw_complete.last_enriched = datetime.utcnow() - timedelta(days=5)
        kw_complete.last_updated = datetime.utcnow() - timedelta(days=5)
        kw_complete.status = "enriched"
        kw_complete.quality_tier = 'A'
        
        kw_incomplete = MagicMock()
        kw_incomplete.search_volume = None
        kw_incomplete.difficulty = None
        kw_incomplete.trend_score = None
        kw_incomplete.trend_growth = None
        kw_incomplete.last_enriched = None
        kw_incomplete.last_updated = None
        kw_incomplete.status = "raw"
        kw_incomplete.quality_tier = None
        
        conf_complete = engine.calculate_keyword_signal_confidence(kw_complete)
        conf_incomplete = engine.calculate_keyword_signal_confidence(kw_incomplete)
        
        assert conf_complete > conf_incomplete

    def _create_engine(self):
        """Create ScoringEngine with mocked db."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db
        return engine


class TestCompletenessFactor:
    """Tests for completeness factor calculation."""

    def test_all_metrics_present_max_score(self):
        """All metrics present should give max completeness."""
        engine = self._create_engine()
        
        kw = MagicMock()
        kw.search_volume = 1000
        kw.difficulty = 30.0
        kw.trend_score = 50.0
        kw.trend_growth = 10.0
        kw.last_enriched = datetime.utcnow()
        
        completeness = engine._calculate_completeness_factor(kw)
        
        assert completeness == 1.0

    def test_no_metrics_present_min_score(self):
        """No metrics present should give min completeness."""
        engine = self._create_engine()
        
        kw = MagicMock()
        kw.search_volume = None
        kw.difficulty = None
        kw.trend_score = None
        kw.trend_growth = None
        kw.last_enriched = None
        
        completeness = engine._calculate_completeness_factor(kw)
        
        assert completeness == 0.0

    def _create_engine(self):
        """Create ScoringEngine with mocked db."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db
        return engine


class TestFreshnessFactor:
    """Tests for freshness factor calculation."""

    def test_fresh_data_high_score(self):
        """Data <7 days old should have high freshness."""
        engine = self._create_engine()
        
        kw = MagicMock()
        kw.last_enriched = datetime.utcnow() - timedelta(days=3)
        kw.last_updated = datetime.utcnow() - timedelta(days=3)
        
        freshness = engine._calculate_freshness_factor(kw)
        
        assert freshness == 1.0

    def test_stale_data_low_score(self):
        """Data >90 days old should have low freshness."""
        engine = self._create_engine()
        
        kw = MagicMock()
        kw.last_enriched = datetime.utcnow() - timedelta(days=100)
        kw.last_updated = datetime.utcnow() - timedelta(days=100)
        
        freshness = engine._calculate_freshness_factor(kw)
        
        assert freshness == 0.4

    def test_no_date_low_score(self):
        """No date should give low freshness."""
        engine = self._create_engine()
        
        kw = MagicMock()
        kw.last_enriched = None
        kw.last_updated = None
        
        freshness = engine._calculate_freshness_factor(kw)
        
        assert freshness == 0.4

    def _create_engine(self):
        """Create ScoringEngine with mocked db."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db
        return engine


class TestSourceReliabilityFactor:
    """Tests for source reliability factor calculation."""

    def test_enriched_status_high_reliability(self):
        """ENRICHED status should have high reliability."""
        engine = self._create_engine()
        
        kw = MagicMock()
        kw.status = "enriched"
        kw.quality_tier = None
        
        reliability = engine._calculate_source_reliability_factor(kw)
        
        assert reliability == 1.0

    def test_raw_status_low_reliability(self):
        """RAW status should have low reliability."""
        engine = self._create_engine()
        
        kw = MagicMock()
        kw.status = "raw"
        kw.quality_tier = None
        
        reliability = engine._calculate_source_reliability_factor(kw)
        
        assert reliability == 0.5

    def _create_engine(self):
        """Create ScoringEngine with mocked db."""
        mock_db = MagicMock()
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = mock_db
        return engine
