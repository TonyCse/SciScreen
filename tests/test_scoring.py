"""Tests for the scoring module."""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.pipeline.scoring import ScreeningModel, QueryBasedScorer, PaperScorer, score_papers


class TestScreeningModel:
    """Test cases for the ScreeningModel class."""
    
    def test_prepare_text_features(self):
        """Test text feature preparation."""
        df = pd.DataFrame([
            {'title': 'Machine Learning', 'abstract': 'ML is great'},
            {'title': 'Deep Learning', 'abstract': 'DL is better'},
            {'title': '', 'abstract': 'No title paper'}
        ])
        
        model = ScreeningModel()
        features = model.prepare_text_features(df)
        
        assert len(features) == 3
        assert 'Machine Learning' in features.iloc[0]
        assert 'ML is great' in features.iloc[0]
        # Title should appear twice for emphasis
        assert features.iloc[0].count('Machine Learning') == 2
    
    def test_train_model(self):
        """Test model training."""
        # Create sample training data
        training_data = pd.DataFrame([
            {'title': 'Machine Learning Review', 'abstract': 'ML techniques', 'label': 1},
            {'title': 'Deep Learning Study', 'abstract': 'DL applications', 'label': 1},
            {'title': 'Cooking Recipes', 'abstract': 'How to cook', 'label': 0},
            {'title': 'Sports News', 'abstract': 'Football scores', 'label': 0},
            {'title': 'AI Research', 'abstract': 'Artificial intelligence', 'label': 1},
            {'title': 'Weather Report', 'abstract': 'Today is sunny', 'label': 0},
        ] * 5)  # Repeat to have enough samples
        
        model = ScreeningModel()
        metrics = model.train(training_data)
        
        assert model.is_trained
        assert 'accuracy' in metrics
        assert 'auc' in metrics
        assert metrics['accuracy'] >= 0.0
        assert metrics['auc'] >= 0.0
    
    def test_predict_without_training(self):
        """Test that prediction fails without training."""
        df = pd.DataFrame([
            {'title': 'Test Paper', 'abstract': 'Test abstract'}
        ])
        
        model = ScreeningModel()
        
        with pytest.raises(ValueError, match="Model must be trained"):
            model.predict(df)
    
    def test_predict_with_training(self):
        """Test prediction with trained model."""
        # Train model
        training_data = pd.DataFrame([
            {'title': 'Machine Learning', 'abstract': 'ML techniques', 'label': 1},
            {'title': 'Cooking Recipe', 'abstract': 'How to cook', 'label': 0},
        ] * 10)
        
        model = ScreeningModel()
        model.train(training_data)
        
        # Test prediction
        test_df = pd.DataFrame([
            {'title': 'AI Research', 'abstract': 'Artificial intelligence study'},
            {'title': 'Cooking Tips', 'abstract': 'Kitchen advice'}
        ])
        
        predictions, probabilities = model.predict(test_df)
        
        assert len(predictions) == 2
        assert len(probabilities) == 2
        assert all(pred in [0, 1] for pred in predictions)
        assert all(0 <= prob <= 1 for prob in probabilities)


class TestQueryBasedScorer:
    """Test cases for the QueryBasedScorer class."""
    
    def test_score_papers(self):
        """Test query-based scoring."""
        query = "machine learning artificial intelligence"
        scorer = QueryBasedScorer(query)
        
        df = pd.DataFrame([
            {'title': 'Machine Learning Study', 'abstract': 'AI and ML techniques'},
            {'title': 'Cooking Recipes', 'abstract': 'How to prepare food'},
            {'title': 'Deep Learning Research', 'abstract': 'Neural networks and AI'}
        ])
        
        predictions, similarities = scorer.score_papers(df)
        
        assert len(predictions) == 3
        assert len(similarities) == 3
        assert all(pred in [0, 1] for pred in predictions)
        assert all(0 <= sim <= 1 for sim in similarities)
        
        # First and third papers should be more similar to query than second
        assert similarities[0] > similarities[1]
        assert similarities[2] > similarities[1]
    
    def test_score_empty_dataframe(self):
        """Test scoring with empty DataFrame."""
        query = "test query"
        scorer = QueryBasedScorer(query)
        
        df = pd.DataFrame()
        predictions, similarities = scorer.score_papers(df)
        
        assert len(predictions) == 0
        assert len(similarities) == 0


class TestPaperScorer:
    """Test cases for the PaperScorer class."""
    
    def test_generate_reasons(self):
        """Test reason generation."""
        df = pd.DataFrame([
            {'title': 'machine learning study', 'abstract': 'ai techniques'},
            {'title': 'cooking recipe', 'abstract': 'kitchen tips'}
        ])
        
        predictions = np.array([1, 0])
        probabilities = np.array([0.8, 0.2])
        
        scorer = PaperScorer("machine learning")
        reasons = scorer.generate_reasons(df, predictions, probabilities)
        
        assert len(reasons) == 2
        assert isinstance(reasons[0], str)
        assert isinstance(reasons[1], str)
        assert len(reasons[0]) > 0
        assert len(reasons[1]) > 0
    
    def test_score_dataframe(self):
        """Test complete DataFrame scoring."""
        df = pd.DataFrame([
            {'title': 'Machine Learning Review', 'abstract': 'Comprehensive ML study'},
            {'title': 'Deep Learning Applications', 'abstract': 'DL in healthcare'},
            {'title': 'Cooking Instructions', 'abstract': 'How to prepare meals'}
        ])
        
        scorer = PaperScorer("machine learning")
        scored_df = scorer.score_dataframe(df)
        
        # Check that scoring columns are added
        assert 'ai_label' in scored_df.columns
        assert 'confidence' in scored_df.columns
        assert 'reason' in scored_df.columns
        assert 'priority' in scored_df.columns
        
        # Check data types and ranges
        assert all(label in [0, 1] for label in scored_df['ai_label'])
        assert all(0 <= conf <= 1 for conf in scored_df['confidence'])
        assert all(isinstance(reason, str) for reason in scored_df['reason'])
        assert all(priority >= 1 for priority in scored_df['priority'])
    
    def test_score_empty_dataframe(self):
        """Test scoring with empty DataFrame."""
        df = pd.DataFrame()
        
        scorer = PaperScorer("test query")
        scored_df = scorer.score_dataframe(df)
        
        assert len(scored_df) == 0
        assert isinstance(scored_df, pd.DataFrame)


class TestScoringHelpers:
    """Test helper functions for scoring."""
    
    def test_score_papers_function(self):
        """Test the convenience function."""
        df = pd.DataFrame([
            {'title': 'AI Research', 'abstract': 'Machine learning study'},
            {'title': 'Cooking Guide', 'abstract': 'Food preparation tips'}
        ])
        
        scored_df = score_papers(df, "artificial intelligence")
        
        assert len(scored_df) == 2
        assert 'ai_label' in scored_df.columns
        assert 'confidence' in scored_df.columns
        assert 'reason' in scored_df.columns
    
    @patch('src.pipeline.scoring.config')
    def test_prepare_screening_excel(self, mock_config):
        """Test Excel file preparation."""
        from src.pipeline.scoring import prepare_screening_excel
        
        # Mock config
        mock_config.screening_columns = [
            'include', 'title', 'abstract', 'confidence', 'ai_label'
        ]
        
        df = pd.DataFrame([
            {
                'title': 'Paper 1',
                'abstract': 'Abstract 1',
                'confidence': 0.8,
                'ai_label': 1,
                'extra_column': 'extra'
            },
            {
                'title': 'Paper 2',
                'abstract': 'Abstract 2',
                'confidence': 0.3,
                'ai_label': 0,
                'extra_column': 'extra'
            }
        ])
        
        # Use temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            output_path = Path(tmp.name)
        
        try:
            prepare_screening_excel(df, output_path)
            
            # Check that file was created
            assert output_path.exists()
            
            # Load and check content
            loaded_df = pd.read_excel(output_path)
            assert len(loaded_df) == 2
            
            # Should be sorted by confidence (highest first)
            assert loaded_df.iloc[0]['confidence'] == 0.8
            assert loaded_df.iloc[1]['confidence'] == 0.3
            
        finally:
            # Clean up
            if output_path.exists():
                output_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__])
