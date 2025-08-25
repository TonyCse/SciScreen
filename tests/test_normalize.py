"""Tests for the normalization module."""

import pytest
import pandas as pd
from src.pipeline.normalize import (
    clean_title,
    normalize_title,
    clean_authors,
    normalize_authors,
    normalize_doc_type,
    normalize_year,
    normalize_dataframe
)


class TestTitleNormalization:
    """Test cases for title normalization functions."""
    
    def test_clean_title(self):
        """Test basic title cleaning."""
        # Test HTML removal
        assert clean_title("<b>Machine Learning</b>") == "Machine Learning"
        
        # Test whitespace normalization
        assert clean_title("Machine    Learning\n\t") == "Machine Learning"
        
        # Test punctuation stripping
        assert clean_title("...Machine Learning!!!") == "Machine Learning"
        
        # Test empty/None handling
        assert clean_title("") == ""
        assert clean_title(None) == ""
    
    def test_normalize_title(self):
        """Test title normalization for comparison."""
        # Test case conversion and punctuation removal
        title = "Machine Learning: A Comprehensive Review"
        normalized = normalize_title(title)
        assert normalized == "machine learning a comprehensive review"
        
        # Test special characters
        title = "Deep Learning & Neural Networks (2020)"
        normalized = normalize_title(title)
        assert normalized == "deep learning neural networks 2020"
        
        # Test consistency
        title1 = "Machine Learning Applications"
        title2 = "Machine Learning Applications."
        assert normalize_title(title1) == normalize_title(title2)


class TestAuthorNormalization:
    """Test cases for author normalization functions."""
    
    def test_clean_authors(self):
        """Test basic author cleaning."""
        # Test separator normalization
        authors = "Smith, J.; Jones, M., Brown, K."
        cleaned = clean_authors(authors)
        assert ";" in cleaned
        assert cleaned.count(";") == 2
        
        # Test HTML removal
        authors = "<i>Smith, J.</i>; Jones, M."
        cleaned = clean_authors(authors)
        assert "<i>" not in cleaned
    
    def test_normalize_authors(self):
        """Test author format normalization."""
        # Test "First Last" to "Last, F." conversion
        authors = "John Smith; Mary Jones"
        normalized = normalize_authors(authors)
        assert "Smith, J." in normalized
        assert "Jones, M." in normalized
        
        # Test preservation of existing format
        authors = "Smith, John; Jones, Mary"
        normalized = normalize_authors(authors)
        assert "Smith, John" in normalized
        assert "Jones, Mary" in normalized
        
        # Test empty input
        assert normalize_authors("") == ""
        assert normalize_authors(None) == ""


class TestDocTypeNormalization:
    """Test cases for document type normalization."""
    
    def test_normalize_doc_type(self):
        """Test document type normalization."""
        # Test exact matches
        assert normalize_doc_type("journal-article") == "journal-article"
        assert normalize_doc_type("review") == "review"
        assert normalize_doc_type("preprint") == "preprint"
        
        # Test partial matches
        assert normalize_doc_type("research-article") == "journal-article"
        assert normalize_doc_type("systematic-review") == "review"
        assert normalize_doc_type("conference-paper") == "proceedings-article"
        
        # Test case insensitive
        assert normalize_doc_type("JOURNAL-ARTICLE") == "journal-article"
        assert normalize_doc_type("Review Article") == "review"
        
        # Test unknown types
        assert normalize_doc_type("unknown-type") == "unknown"
        assert normalize_doc_type("") == "unknown"
        assert normalize_doc_type(None) == "unknown"


class TestYearNormalization:
    """Test cases for year normalization."""
    
    def test_normalize_year(self):
        """Test year normalization."""
        # Test integer input
        assert normalize_year(2020) == 2020
        
        # Test string input
        assert normalize_year("2020") == 2020
        assert normalize_year("2020-01-01") == 2020
        
        # Test date ranges
        assert normalize_year("2020-2021") == 2020
        
        # Test invalid inputs
        assert normalize_year("invalid") is None
        assert normalize_year("") is None
        assert normalize_year(None) is None
        
        # Test boundary validation
        assert normalize_year(1800) is None  # Too old
        assert normalize_year(2050) is None  # Too new
        assert normalize_year(2020) == 2020  # Valid


class TestDataFrameNormalization:
    """Test cases for complete DataFrame normalization."""
    
    def test_normalize_dataframe_basic(self):
        """Test basic DataFrame normalization."""
        df = pd.DataFrame([
            {
                'title': '  Machine Learning Review  ',
                'authors': 'John Smith; Mary Jones',
                'year': '2020',
                'doc_type': 'research-article',
                'abstract': '  This is an abstract.  '
            },
            {
                'title': 'Deep Learning Applications',
                'authors': 'Brown, K.; Wilson, L.',
                'year': 2021,
                'doc_type': 'journal-article',
                'abstract': 'Another abstract.'
            }
        ])
        
        normalized_df = normalize_dataframe(df)
        
        # Check that data is normalized
        assert normalized_df.iloc[0]['title'] == 'Machine Learning Review'
        assert normalized_df.iloc[0]['year'] == 2020
        assert normalized_df.iloc[0]['doc_type'] == 'journal-article'
        
        # Check that normalized title column is added
        assert 'title_normalized' in normalized_df.columns
        assert normalized_df.iloc[0]['title_normalized'] == 'machine learning review'
    
    def test_normalize_dataframe_missing_columns(self):
        """Test normalization with missing columns."""
        df = pd.DataFrame([
            {
                'title': 'Test Paper',
                'custom_field': 'custom_value'
            }
        ])
        
        normalized_df = normalize_dataframe(df)
        
        # Should add missing standard columns
        expected_columns = [
            'source', 'id', 'doi', 'pmid', 'title', 'abstract', 'authors',
            'journal', 'year', 'doc_type', 'lang', 'url', 'pdf_url',
            'oa_status', 'cited_by'
        ]
        
        for col in expected_columns:
            assert col in normalized_df.columns
        
        # Should preserve custom fields
        assert 'custom_field' in normalized_df.columns
    
    def test_normalize_dataframe_language_detection(self):
        """Test language detection in normalization."""
        df = pd.DataFrame([
            {
                'title': 'Machine Learning Applications',
                'abstract': 'This is an English abstract about machine learning.',
                'lang': ''  # Missing language
            },
            {
                'title': 'Apprentissage Automatique',
                'abstract': 'Ceci est un résumé en français sur l\'apprentissage automatique.',
                'lang': ''  # Missing language
            }
        ])
        
        normalized_df = normalize_dataframe(df)
        
        # Language should be detected
        assert normalized_df.iloc[0]['lang'] != ''
        assert normalized_df.iloc[1]['lang'] != ''
        
        # Note: Exact language detection may vary, so we just check it's not empty
    
    def test_normalize_dataframe_empty(self):
        """Test normalization with empty DataFrame."""
        df = pd.DataFrame()
        
        normalized_df = normalize_dataframe(df)
        
        assert len(normalized_df) == 0
        assert isinstance(normalized_df, pd.DataFrame)
    
    def test_normalize_dataframe_metadata(self):
        """Test that processing metadata is added."""
        df = pd.DataFrame([
            {
                'title': 'Test Paper',
                'abstract': 'Test abstract'
            }
        ])
        
        normalized_df = normalize_dataframe(df)
        
        # Should add processing timestamp
        assert 'processing_date' in normalized_df.columns
        assert not pd.isna(normalized_df.iloc[0]['processing_date'])


if __name__ == "__main__":
    pytest.main([__file__])
