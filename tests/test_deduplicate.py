"""Tests for the deduplication module."""

import pytest
import pandas as pd
from src.pipeline.deduplicate import Deduplicator, deduplicate_dataframe


class TestDeduplicator:
    """Test cases for the Deduplicator class."""
    
    def test_find_exact_duplicates_by_doi(self):
        """Test finding exact duplicates by DOI."""
        df = pd.DataFrame([
            {'doi': '10.1000/test1', 'title': 'Paper 1', 'source': 'source1'},
            {'doi': '10.1000/test1', 'title': 'Paper 1 Duplicate', 'source': 'source2'},
            {'doi': '10.1000/test2', 'title': 'Paper 2', 'source': 'source1'},
        ])
        
        deduplicator = Deduplicator()
        duplicates = deduplicator.find_exact_duplicates(df)
        
        assert len(duplicates) == 1
        assert 'doi:10.1000/test1' in duplicates
        assert len(duplicates['doi:10.1000/test1']) == 2
    
    def test_find_exact_duplicates_by_pmid(self):
        """Test finding exact duplicates by PMID."""
        df = pd.DataFrame([
            {'pmid': '12345678', 'title': 'Paper 1', 'source': 'pubmed'},
            {'pmid': '12345678', 'title': 'Paper 1 Duplicate', 'source': 'crossref'},
            {'pmid': '87654321', 'title': 'Paper 2', 'source': 'pubmed'},
        ])
        
        deduplicator = Deduplicator()
        duplicates = deduplicator.find_exact_duplicates(df)
        
        assert len(duplicates) == 1
        assert 'pmid:12345678' in duplicates
        assert len(duplicates['pmid:12345678']) == 2
    
    def test_choose_best_duplicate(self):
        """Test choosing the best duplicate from a group."""
        df = pd.DataFrame([
            {
                'title': 'Paper 1',
                'abstract': 'Short abstract',
                'pdf_url': '',
                'cited_by': 5
            },
            {
                'title': 'Paper 1',
                'abstract': 'Much longer abstract with more detailed information',
                'pdf_url': 'http://example.com/paper.pdf',
                'cited_by': 10
            },
            {
                'title': 'Paper 1',
                'abstract': 'Medium length abstract',
                'pdf_url': '',
                'cited_by': 3
            }
        ])
        
        deduplicator = Deduplicator()
        best_idx = deduplicator.choose_best_duplicate(df, [0, 1, 2])
        
        # Should choose index 1 (has PDF URL and higher citations)
        assert best_idx == 1
    
    def test_are_titles_similar(self):
        """Test title similarity detection."""
        deduplicator = Deduplicator()
        
        # Very similar titles
        title1 = "machine learning for healthcare applications"
        title2 = "machine learning for healthcare application"
        assert deduplicator.are_titles_similar(title1, title2, 2020, 2020)
        
        # Different titles
        title1 = "machine learning for healthcare"
        title2 = "deep learning for finance"
        assert not deduplicator.are_titles_similar(title1, title2, 2020, 2020)
        
        # Similar titles but different years (beyond tolerance)
        title1 = "machine learning applications"
        title2 = "machine learning applications"
        assert not deduplicator.are_titles_similar(title1, title2, 2020, 2023)
    
    def test_remove_exact_duplicates(self):
        """Test removing exact duplicates."""
        df = pd.DataFrame([
            {'doi': '10.1000/test1', 'title': 'Paper 1', 'abstract': 'Short'},
            {'doi': '10.1000/test1', 'title': 'Paper 1', 'abstract': 'Longer abstract'},
            {'doi': '10.1000/test2', 'title': 'Paper 2', 'abstract': 'Another paper'},
        ])
        
        deduplicator = Deduplicator()
        cleaned_df = deduplicator.remove_exact_duplicates(df)
        
        assert len(cleaned_df) == 2
        assert deduplicator.metrics['exact_duplicates_removed'] == 1
        
        # Should keep the one with longer abstract
        kept_paper1 = cleaned_df[cleaned_df['doi'] == '10.1000/test1'].iloc[0]
        assert kept_paper1['abstract'] == 'Longer abstract'
    
    def test_deduplicate_complete_process(self):
        """Test the complete deduplication process."""
        df = pd.DataFrame([
            {
                'doi': '10.1000/test1',
                'title': 'Machine Learning Applications',
                'title_normalized': 'machine learning applications',
                'year': 2020,
                'abstract': 'Short abstract'
            },
            {
                'doi': '10.1000/test1',  # Exact duplicate
                'title': 'Machine Learning Applications',
                'title_normalized': 'machine learning applications',
                'year': 2020,
                'abstract': 'Much longer abstract with detailed information'
            },
            {
                'doi': '10.1000/test2',
                'title': 'Machine Learning Application',  # Fuzzy duplicate
                'title_normalized': 'machine learning application',
                'year': 2020,
                'abstract': 'Another abstract'
            },
            {
                'doi': '10.1000/test3',
                'title': 'Deep Learning for Finance',
                'title_normalized': 'deep learning for finance',
                'year': 2021,
                'abstract': 'Different paper'
            }
        ])
        
        deduplicator = Deduplicator()
        cleaned_df, metrics = deduplicator.deduplicate(df)
        
        assert len(cleaned_df) == 2  # Should have 2 unique papers
        assert metrics['total_input'] == 4
        assert metrics['exact_duplicates_removed'] >= 1
        assert metrics['final_count'] == 2
    
    def test_empty_dataframe(self):
        """Test deduplication with empty DataFrame."""
        df = pd.DataFrame()
        
        deduplicated_df, metrics = deduplicate_dataframe(df)
        
        assert len(deduplicated_df) == 0
        assert metrics['total_input'] == 0
        assert metrics['final_count'] == 0


class TestDeduplicationHelpers:
    """Test helper functions for deduplication."""
    
    def test_deduplicate_dataframe_function(self):
        """Test the convenience function."""
        df = pd.DataFrame([
            {'doi': '10.1000/test1', 'title': 'Paper 1'},
            {'doi': '10.1000/test1', 'title': 'Paper 1 Duplicate'},
            {'doi': '10.1000/test2', 'title': 'Paper 2'},
        ])
        
        cleaned_df, metrics = deduplicate_dataframe(df)
        
        assert len(cleaned_df) == 2
        assert 'total_input' in metrics
        assert 'final_count' in metrics


if __name__ == "__main__":
    pytest.main([__file__])
