"""
Unit tests for KeywordQualityEngine.compute_quality_score()

Tests the semantic distinction between:
- apps_count: raw iTunes result count (how many apps appear for this keyword)
- search_volume: derived score (0-100) based on various signals

These are fundamentally different metrics and should not be confused.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.keyword_quality_engine import KeywordQualityEngine


class TestComputeQualityScoreSemantics:
    """Tests for compute_quality_score to verify correct semantics."""

    def test_high_search_volume_low_apps_count(self):
        """
        Scenario: Keyword has high search interest but few actual apps.
        Example: "AI lawyer" - high trending interest, but few apps.
        
        Expected: validation_score should be LOW because apps_count is low.
        """
        q_score, v_score, r_score = KeywordQualityEngine.compute_quality_score(
            term="ai lawyer",
            keyword_source="seed",
            apps_count=3,  # Only 3 apps returned
            search_volume=85,  # High trending interest
        )
        
        # validation_score should be low (3 apps = 5.0 points)
        assert v_score == 5.0
        # quality_score includes other factors (source, phrase, volume), 
        # but validation should be low

    def test_low_search_volume_high_apps_count(self):
        """
        Scenario: Keyword has many apps but low search interest.
        Example: "game" - millions of apps, but very generic.
        
        Expected: validation_score should be HIGH because apps_count is high.
        """
        q_score, v_score, r_score = KeywordQualityEngine.compute_quality_score(
            term="game",
            keyword_source="seed",
            apps_count=5000,  # Many apps returned
            search_volume=20,  # Low trending interest
        )
        
        # validation_score should be high (5000 apps = 20.0 points)
        assert v_score == 20.0

    def test_apps_count_vs_search_volume_distinction(self):
        """
        Verify that apps_count and search_volume are used correctly.
        
        apps_count affects validation_score (0-25)
        search_volume affects volume_score (0-15)
        """
        # Case 1: High apps, low volume
        q1, v1, _ = KeywordQualityEngine.compute_quality_score(
            term="photo editor",
            keyword_source="title",
            apps_count=1000,
            search_volume=10,
        )
        
        # Case 2: Low apps, high volume  
        q2, v2, _ = KeywordQualityEngine.compute_quality_score(
            term="photo editor",
            keyword_source="title",
            apps_count=10,
            search_volume=100,
        )
        
        # validation_score should differ based on apps_count
        assert v1 > v2  # More apps = higher validation
        
        # Both should have same source/term, so phrase_score same
        # But total quality should differ

    def test_zero_apps_count(self):
        """
        Edge case: No apps found for keyword.
        """
        q_score, v_score, r_score = KeywordQualityEngine.compute_quality_score(
            term="xyzabc123nonexistent",
            keyword_source="seed",
            apps_count=0,
            search_volume=0,
        )
        
        # validation_score should be 0 when no apps
        assert v_score == 0.0

    def test_apps_count_brackets(self):
        """
        Test the apps_count brackets for validation_score:
        0 → 0.0
        1-5 → 5.0
        6-20 → 10.0
        21-100 → 15.0
        100+ → 20.0
        """
        # 0 apps
        _, v0, _ = KeywordQualityEngine.compute_quality_score("test", apps_count=0)
        assert v0 == 0.0
        
        # 1-5 apps
        _, v3, _ = KeywordQualityEngine.compute_quality_score("test", apps_count=3)
        assert v3 == 5.0
        
        # 6-20 apps
        _, v10, _ = KeywordQualityEngine.compute_quality_score("test", apps_count=10)
        assert v10 == 10.0
        
        # 21-100 apps
        _, v50, _ = KeywordQualityEngine.compute_quality_score("test", apps_count=50)
        assert v50 == 15.0
        
        # 100+ apps
        _, v200, _ = KeywordQualityEngine.compute_quality_score("test", apps_count=200)
        assert v200 == 20.0


class TestQualityScoreWithDifferentSources:
    """Test quality score calculation with different keyword sources."""

    def test_title_source_high_weight(self):
        """Title source should have high weight (14 points)."""
        q1, _, _ = KeywordQualityEngine.compute_quality_score(
            term="photo editor",
            keyword_source="title",
            apps_count=50,
            search_volume=50,
        )
        
        q2, _, _ = KeywordQualityEngine.compute_quality_score(
            term="photo editor",
            keyword_source="alphabet",
            apps_count=50,
            search_volume=50,
        )
        
        # Title should score higher than alphabet
        assert q1 > q2


class TestBackwardCompatibility:
    """Test that the function still works without explicit apps_count."""

    def test_default_apps_count(self):
        """When apps_count not provided, should default to 0."""
        q_score, v_score, r_score = KeywordQualityEngine.compute_quality_score(
            term="test app",
            keyword_source="seed",
            # No apps_count provided
        )
        
        # Should still compute without error
        assert q_score >= 0
        assert v_score == 0.0  # Default 0 apps

    def test_validation_override(self):
        """validation_score_override should bypass apps_count calculation."""
        q1, v1, _ = KeywordQualityEngine.compute_quality_score(
            term="test",
            keyword_source="seed",
            apps_count=0,
            validation_score_override=25.0,
        )
        
        assert v1 == 25.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
