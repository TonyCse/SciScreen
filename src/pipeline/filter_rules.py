"""Filtering rules module for the Literature Review Pipeline.

This module provides configurable filtering rules to exclude papers
based on various criteria such as language, document type, year, etc.
"""

import logging
from typing import Dict, List, Optional, Tuple

import pandas as pd

from ..config import config

logger = logging.getLogger(__name__)


class FilterEngine:
    """Engine for applying filtering rules to academic works."""
    
    def __init__(self):
        """Initialize the filter engine."""
        # Track filtering metrics
        self.metrics = {
            "total_input": 0,
            "excluded_by_rule": {},
            "final_count": 0,
            "exclusion_details": []
        }
    
    def filter_by_language(self, df: pd.DataFrame, allowed_langs: List[str]) -> pd.DataFrame:
        """Filter papers by language.
        
        Args:
            df: Input DataFrame
            allowed_langs: List of allowed language codes (e.g., ['en', 'fr'])
            
        Returns:
            Filtered DataFrame
        """
        if df.empty or not allowed_langs:
            return df
        
        # Convert to lowercase for comparison
        allowed_langs = [lang.lower().strip() for lang in allowed_langs]
        
        # Filter
        if 'lang' in df.columns:
            before_count = len(df)
            # Include papers with missing language info or in allowed languages
            mask = (
                df['lang'].isna() |
                (df['lang'] == "") |
                df['lang'].str.lower().isin(allowed_langs)
            )
            filtered_df = df[mask].copy()
            
            excluded_count = before_count - len(filtered_df)
            self.metrics["excluded_by_rule"]["language"] = excluded_count
            
            if excluded_count > 0:
                logger.info(f"Excluded {excluded_count} papers by language filter (allowed: {allowed_langs})")
                self.metrics["exclusion_details"].append({
                    "rule": "language",
                    "excluded_count": excluded_count,
                    "criteria": f"Not in {allowed_langs}"
                })
        else:
            filtered_df = df
        
        return filtered_df
    
    def filter_by_doc_type(
        self,
        df: pd.DataFrame,
        allowed_types: Optional[List[str]] = None,
        excluded_types: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Filter papers by document type.
        
        Args:
            df: Input DataFrame
            allowed_types: List of allowed document types (if None, all types allowed)
            excluded_types: List of excluded document types
            
        Returns:
            Filtered DataFrame
        """
        if df.empty or 'doc_type' not in df.columns:
            return df
        
        before_count = len(df)
        filtered_df = df.copy()
        
        # Apply allowed types filter
        if allowed_types:
            allowed_types = [t.lower().strip() for t in allowed_types]
            mask = (
                filtered_df['doc_type'].isna() |
                (filtered_df['doc_type'] == "") |
                filtered_df['doc_type'].str.lower().isin(allowed_types)
            )
            filtered_df = filtered_df[mask]
        
        # Apply excluded types filter
        if excluded_types:
            excluded_types = [t.lower().strip() for t in excluded_types]
            mask = ~filtered_df['doc_type'].str.lower().isin(excluded_types)
            filtered_df = filtered_df[mask]
        
        excluded_count = before_count - len(filtered_df)
        if excluded_count > 0:
            self.metrics["excluded_by_rule"]["doc_type"] = excluded_count
            criteria_parts = []
            if allowed_types:
                criteria_parts.append(f"not in {allowed_types}")
            if excluded_types:
                criteria_parts.append(f"in excluded {excluded_types}")
            criteria = " or ".join(criteria_parts)
            
            logger.info(f"Excluded {excluded_count} papers by document type filter")
            self.metrics["exclusion_details"].append({
                "rule": "doc_type",
                "excluded_count": excluded_count,
                "criteria": criteria
            })
        
        return filtered_df
    
    def filter_by_year(
        self,
        df: pd.DataFrame,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None
    ) -> pd.DataFrame:
        """Filter papers by publication year.
        
        Args:
            df: Input DataFrame
            year_from: Minimum year (inclusive)
            year_to: Maximum year (inclusive)
            
        Returns:
            Filtered DataFrame
        """
        if df.empty or 'year' not in df.columns:
            return df
        
        if year_from is None and year_to is None:
            return df
        
        before_count = len(df)
        filtered_df = df.copy()
        
        # Convert year column to numeric, errors to NaN
        filtered_df['year'] = pd.to_numeric(filtered_df['year'], errors='coerce')
        
        # Apply year filters
        if year_from is not None:
            # Include papers with missing year or year >= year_from
            mask = filtered_df['year'].isna() | (filtered_df['year'] >= year_from)
            filtered_df = filtered_df[mask]
        
        if year_to is not None:
            # Include papers with missing year or year <= year_to
            mask = filtered_df['year'].isna() | (filtered_df['year'] <= year_to)
            filtered_df = filtered_df[mask]
        
        excluded_count = before_count - len(filtered_df)
        if excluded_count > 0:
            self.metrics["excluded_by_rule"]["year"] = excluded_count
            criteria = f"outside range {year_from}-{year_to}"
            
            logger.info(f"Excluded {excluded_count} papers by year filter ({year_from}-{year_to})")
            self.metrics["exclusion_details"].append({
                "rule": "year",
                "excluded_count": excluded_count,
                "criteria": criteria
            })
        
        return filtered_df
    
    def filter_preprints(self, df: pd.DataFrame, allow_preprints: bool = True) -> pd.DataFrame:
        """Filter preprints.
        
        Args:
            df: Input DataFrame
            allow_preprints: Whether to allow preprints
            
        Returns:
            Filtered DataFrame
        """
        if df.empty or allow_preprints or 'doc_type' not in df.columns:
            return df
        
        before_count = len(df)
        
        # Exclude preprints
        preprint_types = ['preprint', 'posted-content']
        mask = ~df['doc_type'].str.lower().isin(preprint_types)
        filtered_df = df[mask].copy()
        
        excluded_count = before_count - len(filtered_df)
        if excluded_count > 0:
            self.metrics["excluded_by_rule"]["preprints"] = excluded_count
            
            logger.info(f"Excluded {excluded_count} preprints")
            self.metrics["exclusion_details"].append({
                "rule": "preprints",
                "excluded_count": excluded_count,
                "criteria": "preprint or posted-content"
            })
        
        return filtered_df
    
    def filter_missing_essential_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter papers missing essential fields.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Filtered DataFrame
        """
        if df.empty:
            return df
        
        before_count = len(df)
        
        # Safely access columns that may be missing
        title_col = df.get('title', pd.Series(index=df.index, dtype=object))
        abstract_col = df.get('abstract', pd.Series(index=df.index, dtype=object))
        doi_col = df.get('doi', pd.Series(index=df.index, dtype=object))
        pmid_col = df.get('pmid', pd.Series(index=df.index, dtype=object))

        # Require title and at least one of: abstract, DOI, PMID
        mask = (
            title_col.notna() &
            (title_col != "") &
            (title_col.astype(str).str.strip() != "") &
            (
                (abstract_col.notna() & (abstract_col != "")) |
                (doi_col.notna() & (doi_col != "")) |
                (pmid_col.notna() & (pmid_col != ""))
            )
        )
        
        filtered_df = df[mask].copy()
        
        excluded_count = before_count - len(filtered_df)
        if excluded_count > 0:
            self.metrics["excluded_by_rule"]["missing_essential"] = excluded_count
            
            logger.info(f"Excluded {excluded_count} papers missing essential fields")
            self.metrics["exclusion_details"].append({
                "rule": "missing_essential",
                "excluded_count": excluded_count,
                "criteria": "missing title or (abstract and DOI and PMID)"
            })
        
        return filtered_df
    
    def filter_by_custom_rules(self, df: pd.DataFrame, custom_rules: Dict) -> pd.DataFrame:
        """Apply custom filtering rules.
        
        Args:
            df: Input DataFrame
            custom_rules: Dictionary of custom rules
            
        Returns:
            Filtered DataFrame
        """
        # This can be extended for specific project needs
        # Example custom rules:
        # - Minimum citation count
        # - Specific journals to include/exclude
        # - Author requirements
        # etc.
        
        filtered_df = df.copy()
        
        # Example: minimum citation count
        if 'min_citations' in custom_rules:
            min_cites = custom_rules['min_citations']
            before_count = len(filtered_df)
            
            mask = (
                filtered_df['cited_by'].isna() |
                (filtered_df['cited_by'] >= min_cites)
            )
            filtered_df = filtered_df[mask]
            
            excluded_count = before_count - len(filtered_df)
            if excluded_count > 0:
                self.metrics["excluded_by_rule"]["min_citations"] = excluded_count
                logger.info(f"Excluded {excluded_count} papers with < {min_cites} citations")
        
        # Example: excluded journals
        if 'excluded_journals' in custom_rules:
            excluded_journals = [j.lower() for j in custom_rules['excluded_journals']]
            before_count = len(filtered_df)
            
            mask = ~filtered_df['journal'].str.lower().isin(excluded_journals)
            filtered_df = filtered_df[mask]
            
            excluded_count = before_count - len(filtered_df)
            if excluded_count > 0:
                self.metrics["excluded_by_rule"]["excluded_journals"] = excluded_count
                logger.info(f"Excluded {excluded_count} papers from excluded journals")
        
        return filtered_df
    
    def apply_filters(
        self,
        df: pd.DataFrame,
        langs: Optional[List[str]] = None,
        allowed_types: Optional[List[str]] = None,
        excluded_types: Optional[List[str]] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        allow_preprints: bool = True,
        require_essential_fields: bool = True,
        custom_rules: Optional[Dict] = None
    ) -> Tuple[pd.DataFrame, Dict]:
        """Apply all filtering rules.
        
        Args:
            df: Input DataFrame
            langs: Allowed languages
            allowed_types: Allowed document types
            excluded_types: Excluded document types
            year_from: Minimum year
            year_to: Maximum year
            allow_preprints: Whether to allow preprints
            require_essential_fields: Whether to require essential fields
            custom_rules: Custom filtering rules
            
        Returns:
            Tuple of (filtered DataFrame, metrics dictionary)
        """
        logger.info(f"Starting filtering of {len(df)} papers...")
        
        self.metrics["total_input"] = len(df)
        
        if df.empty:
            self.metrics["final_count"] = 0
            return df, self.metrics
        
        filtered_df = df.copy()
        
        # Apply filters in sequence
        if langs:
            filtered_df = self.filter_by_language(filtered_df, langs)
        
        if allowed_types or excluded_types:
            filtered_df = self.filter_by_doc_type(filtered_df, allowed_types, excluded_types)
        
        if year_from is not None or year_to is not None:
            filtered_df = self.filter_by_year(filtered_df, year_from, year_to)
        
        if not allow_preprints:
            filtered_df = self.filter_preprints(filtered_df, allow_preprints)
        
        if require_essential_fields:
            filtered_df = self.filter_missing_essential_fields(filtered_df)
        
        if custom_rules:
            filtered_df = self.filter_by_custom_rules(filtered_df, custom_rules)
        
        self.metrics["final_count"] = len(filtered_df)
        
        # Log summary
        total_excluded = self.metrics["total_input"] - self.metrics["final_count"]
        exclusion_rate = (total_excluded / self.metrics["total_input"]) * 100 if self.metrics["total_input"] > 0 else 0
        
        logger.info(
            f"Filtering completed: {self.metrics['total_input']} → {self.metrics['final_count']} papers "
            f"({total_excluded} excluded, {exclusion_rate:.1f}% exclusion rate)"
        )
        
        return filtered_df, self.metrics


def apply_filter_rules(
    df: pd.DataFrame,
    langs: Optional[List[str]] = None,
    allowed_types: Optional[List[str]] = None,
    excluded_types: Optional[List[str]] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    allow_preprints: bool = True,
    require_essential_fields: bool = True,
    custom_rules: Optional[Dict] = None
) -> Tuple[pd.DataFrame, Dict]:
    """Convenience function to apply filtering rules.
    
    Args:
        df: Input DataFrame
        langs: Allowed languages
        allowed_types: Allowed document types
        excluded_types: Excluded document types
        year_from: Minimum year
        year_to: Maximum year
        allow_preprints: Whether to allow preprints
        require_essential_fields: Whether to require essential fields
        custom_rules: Custom filtering rules
        
    Returns:
        Tuple of (filtered DataFrame, metrics dictionary)
    """
    filter_engine = FilterEngine()
    return filter_engine.apply_filters(
        df=df,
        langs=langs,
        allowed_types=allowed_types,
        excluded_types=excluded_types,
        year_from=year_from,
        year_to=year_to,
        allow_preprints=allow_preprints,
        require_essential_fields=require_essential_fields,
        custom_rules=custom_rules
    )


def get_filter_report(metrics: Dict) -> str:
    """Generate a human-readable filtering report.
    
    Args:
        metrics: Filtering metrics dictionary
        
    Returns:
        Formatted report string
    """
    report = []
    report.append("Filtering Report")
    report.append("=" * 16)
    report.append(f"Input papers: {metrics['total_input']}")
    
    for rule, excluded_count in metrics['excluded_by_rule'].items():
        report.append(f"Excluded by {rule}: {excluded_count}")
    
    report.append(f"Final count: {metrics['final_count']}")
    
    total_excluded = metrics['total_input'] - metrics['final_count']
    if metrics['total_input'] > 0:
        exclusion_rate = (total_excluded / metrics['total_input']) * 100
        report.append(f"Exclusion rate: {exclusion_rate:.1f}%")
    
    if metrics['exclusion_details']:
        report.append("\nDetailed exclusions:")
        for detail in metrics['exclusion_details']:
            report.append(f"  {detail['rule']}: {detail['excluded_count']} ({detail['criteria']})")
    
    return "\n".join(report)
