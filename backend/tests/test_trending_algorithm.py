"""
Unit tests for the new Multi-Factor Trending Algorithm.

Tests prove the new algorithm reduces false positives by:
1. Confidence penalty for sparse data
2. Consistency bonus for sustained movers  
3. Bounded review growth for tiny apps
4. Absolute rank bonus for strong positions
"""

import pytest
import sys
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfidenceScore:
    """Tests for confidence penalty."""

    def test_sparse_history_confidence_penalty(self):
        """App with only 2-3 snapshots should receive clear confidence penalty."""
        from app.scoring.engine import ScoringEngine
        
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = MagicMock()
        
        now = datetime.now(timezone.utc)
        
        def mock_query(model):
            mock_result = MagicMock()
            
            if model.__name__ == 'Ranking':
                results = [
                    type('Ranking', (), {
                        'rank': 50,
                        'previous_rank': 55,
                        'recorded_at': now - timedelta(days=i)
                    })()
                    for i in range(3)
                ]
                mock_result.order_by.return_value.all.return_value = results
                mock_result.filter.return_value = mock_result
                
            return mock_result
        
        engine.db.query = mock_query
        
        result = engine.compute_confidence_score(1)
        
        assert result < 0.7

    def test_ample_history_confidence(self):
        """App with many snapshots should have high confidence."""
        from app.scoring.engine import ScoringEngine
        
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = MagicMock()
        
        now = datetime.now(timezone.utc)
        
        def mock_query(model):
            mock_result = MagicMock()
            
            if model.__name__ == 'Ranking':
                results = [
                    type('Ranking', (), {
                        'rank': 50,
                        'previous_rank': 55,
                        'recorded_at': now - timedelta(hours=i*6)
                    })()
                    for i in range(14)
                ]
                mock_result.order_by.return_value.all.return_value = results
                mock_result.filter.return_value = mock_result
                
            return mock_result
        
        engine.db.query = mock_query
        
        result = engine.compute_confidence_score(1)
        
        assert result > 0.5


class TestConsistencyScore:
    """Tests for consistency scoring."""

    def test_consistent_upward_movement(self):
        """App with consistent upward movement should have high consistency."""
        from app.scoring.engine import ScoringEngine
        
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = MagicMock()
        
        now = datetime.now(timezone.utc)
        
        def mock_query(model):
            mock_result = MagicMock()
            
            if model.__name__ == 'Ranking':
                results = [
                    type('Ranking', (), {
                        'rank': 100 - i * 5,
                        'previous_rank': 100 - i * 5 + 1,
                        'recorded_at': now - timedelta(days=14-i)
                    })()
                    for i in range(14)
                ]
                mock_result.order_by.return_value.all.return_value = results
                mock_result.filter.return_value = mock_result
                
            return mock_result
        
        engine.db.query = mock_query
        
        result = engine.compute_consistency_score(1)
        
        assert result > 50


class TestAbsoluteRankBonus:
    """Tests for absolute rank bonus."""

    def test_top_rank_improvement_bonus(self):
        """Mover near top ranks should get bonus."""
        from app.scoring.engine import ScoringEngine
        
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = MagicMock()
        
        now = datetime.now(timezone.utc)
        
        def mock_query(model):
            mock_result = MagicMock()
            
            if model.__name__ == 'Ranking':
                results = [
                    type('Ranking', (), {
                        'rank': 15 - i,
                        'previous_rank': 15 - i + 1,
                        'recorded_at': now - timedelta(days=7-i)
                    })()
                    for i in range(7)
                ]
                mock_result.order_by.return_value.all.return_value = results
                mock_result.filter.return_value = mock_result
                
            return mock_result
        
        engine.db.query = mock_query
        
        result = engine.compute_absolute_rank_bonus(1)
        
        assert result > 0


class TestBoundedReviewMomentum:
    """Tests for review momentum with damping."""

    def test_tiny_app_dampening(self):
        """Tiny app with few reviews should have dampened review momentum."""
        from app.scoring.engine import ScoringEngine
        
        engine = ScoringEngine.__new__(ScoringEngine)
        
        mock_app = MagicMock()
        mock_app.current_reviews = 50
        
        engine.db = MagicMock()
        engine.db.query.return_value.filter.return_value.first.return_value = mock_app
        engine.db.query.return_value.filter.return_value.all.return_value = []
        
        with patch.object(engine, 'calculate_review_growth', return_value=50.0):
            result = engine.compute_bounded_review_momentum(1)
            
            assert result < 25


class TestFormulaStructure:
    """Tests for formula structure."""

    def test_confidence_multiplier_range(self):
        """Confidence factor should always be between 0 and 1."""
        from app.scoring.engine import ScoringEngine
        
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = MagicMock()
        
        now = datetime.now(timezone.utc)
        
        def mock_query(model):
            mock_result = MagicMock()
            
            if model.__name__ == 'Ranking':
                results = [
                    type('Ranking', (), {
                        'rank': 50,
                        'previous_rank': 55,
                        'recorded_at': now - timedelta(hours=i*6)
                    })()
                    for i in range(10)
                ]
                mock_result.order_by.return_value.all.return_value = results
                mock_result.filter.return_value = mock_result
                
            return mock_result
        
        engine.db.query = mock_query
        
        confidence = engine.compute_confidence_score(1)
        
        assert 0 <= confidence <= 1.0

    def test_momentum_returns_multi_window(self):
        """Momentum should return multiple window scores."""
        from app.scoring.engine import ScoringEngine
        
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = MagicMock()
        
        now = datetime.now(timezone.utc)
        
        def mock_query(model):
            mock_result = MagicMock()
            
            if model.__name__ == 'Ranking':
                results = [
                    type('Ranking', (), {
                        'rank': 50 - i * 2,
                        'previous_rank': 50 - i * 2 + 1,
                        'recorded_at': now - timedelta(days=14-i)
                    })()
                    for i in range(14)
                ]
                mock_result.order_by.return_value.all.return_value = results
                mock_result.filter.return_value = mock_result
                
            return mock_result
        
        engine.db.query = mock_query
        
        result = engine.compute_momentum_score(1)
        
        assert 'momentum_3d' in result
        assert 'momentum_7d' in result
        assert 'momentum_14d' in result
        assert 'momentum_weighted' in result


class TestConsistencyBonus:
    """Tests for consistency scoring."""

    def test_all_positive_days_high_consistency(self):
        """All positive movement days should score high on consistency."""
        from app.scoring.engine import ScoringEngine
        
        engine = ScoringEngine.__new__(ScoringEngine)
        engine.db = MagicMock()
        
        now = datetime.now(timezone.utc)
        
        def mock_query(model):
            mock_result = MagicMock()
            
            if model.__name__ == 'Ranking':
                # Consistent improvement every day
                results = [
                    type('Ranking', (), {
                        'rank': 100 - i * 5,
                        'previous_rank': 100 - i * 5 + 5,
                        'recorded_at': now - timedelta(days=14-i)
                    })()
                    for i in range(14)
                ]
                mock_result.order_by.return_value.all.return_value = results
                mock_result.filter.return_value = mock_result
                
            return mock_result
        
        engine.db.query = mock_query
        
        consistency = engine.compute_consistency_score(1)
        
        # All positive days should yield high consistency
        assert consistency > 60


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
