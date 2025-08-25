"""Tests for the filter rules module."""

import pytest
import pandas as pd
from src.pipeline.filter_rules import FilterEngine, apply_filter_rules


class TestFilterEngine:
    """Test cases for the FilterEngine class."""
    
    def test_filter_by_language(self):
        """Test filtering by language."""
        df = pd.DataFrame([
            {'title': 'Paper 1', 'lang': 'en'},
            {'title': 'Paper 2', 'lang': 'fr'},
            {'title': 'Paper 3', 'lang': 'de'},
            {'title': 'Paper 4', 'lang': ''},  # Missing language
            {'title': 'Paper 5', 'lang': 'en'},
        ])
        
        filter_engine = FilterEngine()
        filtered_df = filter_engine.filter_by_language(df, ['en', 'fr'])
        
        # Should keep en, fr, and missing language papers
        assert len(filtered_df) == 4
        assert 'de' not in filtered_df['lang'].values
        assert filter_engine.metrics['excluded_by_rule']['language'] == 1
    
    def test_filter_by_doc_type_allowed(self):
        """Test filtering by allowed document types."""
        df = pd.DataFrame([
            {'title': 'Paper 1', 'doc_type': 'journal-article'},
            {'title': 'Paper 2', 'doc_type': 'review'},
            {'title': 'Paper 3', 'doc_type': 'editorial'},
            {'title': 'Paper 4', 'doc_type': 'journal-article'},
        ])
        
        filter_engine = FilterEngine()
        filtered_df = filter_engine.filter_by_doc_type(
            df, 
            allowed_types=['journal-article', 'review']
        )
        
        assert len(filtered_df) == 3
        assert 'editorial' not in filtered_df['doc_type'].values
        assert filter_engine.metrics['excluded_by_rule']['doc_type'] == 1
    
    def test_filter_by_doc_type_excluded(self):
        """Test filtering by excluded document types."""
        df = pd.DataFrame([
            {'title': 'Paper 1', 'doc_type': 'journal-article'},
            {'title': 'Paper 2', 'doc_type': 'review'},
            {'title': 'Paper 3', 'doc_type': 'editorial'},
            {'title': 'Paper 4', 'doc_type': 'preprint'},
        ])
        
        filter_engine = FilterEngine()
        filtered_df = filter_engine.filter_by_doc_type(
            df, 
            excluded_types=['editorial', 'preprint']
        )
        
        assert len(filtered_df) == 2
        assert 'editorial' not in filtered_df['doc_type'].values
        assert 'preprint' not in filtered_df['doc_type'].values
        assert filter_engine.metrics['excluded_by_rule']['doc_type'] == 2
    
    def test_filter_by_year(self):
        """Test filtering by publication year."""
        df = pd.DataFrame([
            {'title': 'Paper 1', 'year': 2015},
            {'title': 'Paper 2', 'year': 2020},
            {'title': 'Paper 3', 'year': 2025},
            {'title': 'Paper 4', 'year': 2030},  # Too recent
            {'title': 'Paper 5', 'year': 2010},  # Too old
        ])
        
        filter_engine = FilterEngine()
        filtered_df = filter_engine.filter_by_year(df, year_from=2015, year_to=2025)
        
        assert len(filtered_df) == 3
        years = filtered_df['year'].tolist()
        assert 2030 not in years
        assert 2010 not in years
        assert filter_engine.metrics['excluded_by_rule']['year'] == 2
    
    def test_filter_preprints(self):
        """Test filtering preprints."""
        df = pd.DataFrame([
            {'title': 'Paper 1', 'doc_type': 'journal-article'},
            {'title': 'Paper 2', 'doc_type': 'preprint'},
            {'title': 'Paper 3', 'doc_type': 'posted-content'},
            {'title': 'Paper 4', 'doc_type': 'review'},
        ])
        
        filter_engine = FilterEngine()
        filtered_df = filter_engine.filter_preprints(df, allow_preprints=False)
        
        assert len(filtered_df) == 2
        assert 'preprint' not in filtered_df['doc_type'].values
        assert 'posted-content' not in filtered_df['doc_type'].values
        assert filter_engine.metrics['excluded_by_rule']['preprints'] == 2
    
    def test_filter_missing_essential_fields(self):
        """Test filtering papers with missing essential fields."""
        df = pd.DataFrame([
            {
                'title': 'Valid Paper 1',
                'abstract': 'Has abstract',
                'doi': '',
                'pmid': ''
            },
            {
                'title': 'Valid Paper 2',
                'abstract': '',
                'doi': '10.1000/test',
                'pmid': ''
            },
            {
                'title': '',  # Missing title
                'abstract': 'Has abstract',
                'doi': '',
                'pmid': ''
            },
            {
                'title': 'Missing Everything',
                'abstract': '',
                'doi': '',
                'pmid': ''
            }
        ])
        
        filter_engine = FilterEngine()
        filtered_df = filter_engine.filter_missing_essential_fields(df)
        
        assert len(filtered_df) == 2
        assert filter_engine.metrics['excluded_by_rule']['missing_essential'] == 2
    
    def test_apply_all_filters(self):
        """Test applying all filters together."""
        df = pd.DataFrame([
            {
                'title': 'Valid Paper 1',
                'abstract': 'Good abstract',
                'lang': 'en',
                'doc_type': 'journal-article',
                'year': 2020,
                'doi': '10.1000/test1'
            },
            {
                'title': 'Valid Paper 2',
                'abstract': 'Another abstract',
                'lang': 'fr',
                'doc_type': 'review',
                'year': 2021,
                'pmid': '12345'
            },
            {
                'title': 'Invalid Language',
                'abstract': 'Good abstract',
                'lang': 'de',  # Not allowed
                'doc_type': 'journal-article',
                'year': 2020,
                'doi': '10.1000/test2'
            },
            {
                'title': 'Too Old',
                'abstract': 'Good abstract',
                'lang': 'en',
                'doc_type': 'journal-article',
                'year': 2010,  # Too old
                'doi': '10.1000/test3'
            },
            {
                'title': 'Preprint',
                'abstract': 'Good abstract',
                'lang': 'en',
                'doc_type': 'preprint',  # Not allowed
                'year': 2020,
                'doi': '10.1000/test4'
            }
        ])
        
        filter_engine = FilterEngine()
        filtered_df, metrics = filter_engine.apply_filters(
            df,
            langs=['en', 'fr'],
            year_from=2015,
            year_to=2025,
            allow_preprints=False,
            require_essential_fields=True
        )
        
        assert len(filtered_df) == 2  # Only first two papers should pass
        assert metrics['total_input'] == 5
        assert metrics['final_count'] == 2
        
        # Check that correct papers are kept
        titles = filtered_df['title'].tolist()
        assert 'Valid Paper 1' in titles
        assert 'Valid Paper 2' in titles
    
    def test_empty_dataframe(self):
        """Test filtering with empty DataFrame."""
        df = pd.DataFrame()
        
        filtered_df, metrics = apply_filter_rules(df)
        
        assert len(filtered_df) == 0
        assert metrics['total_input'] == 0
        assert metrics['final_count'] == 0


class TestFilterHelpers:
    """Test helper functions for filtering."""
    
    def test_apply_filter_rules_function(self):
        """Test the convenience function."""
        df = pd.DataFrame([
            {
                'title': 'Paper 1',
                'abstract': 'Abstract',
                'lang': 'en',
                'year': 2020
            },
            {
                'title': 'Paper 2',
                'abstract': 'Abstract',
                'lang': 'de',
                'year': 2020
            }
        ])
        
        filtered_df, metrics = apply_filter_rules(
            df,
            langs=['en'],
            require_essential_fields=True
        )
        
        assert len(filtered_df) == 1
        assert 'total_input' in metrics
        assert 'excluded_by_rule' in metrics


if __name__ == "__main__":
    pytest.main([__file__])
