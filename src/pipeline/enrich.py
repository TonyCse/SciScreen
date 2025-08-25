"""Enrichment module for the Literature Review Pipeline.

This module provides functions to enrich paper metadata using
various APIs like Unpaywall and additional Crossref lookups.
"""

import logging
import time
from typing import Dict, List, Optional

import pandas as pd
import requests

from ..config import config
from ..harvest.unpaywall import UnpaywallEnricher
from ..utils_io import log_api_call, rate_limited_request, setup_session

logger = logging.getLogger(__name__)


class MetadataEnricher:
    """Engine for enriching paper metadata from various sources."""
    
    def __init__(self):
        """Initialize the enricher."""
        self.unpaywall = UnpaywallEnricher()
        self.crossref_session = setup_session()
        self.crossref_session.headers.update({
            "User-Agent": f"LitReviewPipeline/1.0 (mailto:{config.crossref_mailto or 'example@example.com'})",
        })
        
        # Track enrichment metrics
        self.metrics = {
            "total_input": 0,
            "unpaywall_enriched": 0,
            "crossref_enriched": 0,
            "missing_metadata_filled": 0,
            "pdf_urls_found": 0,
            "oa_status_updated": 0,
        }
    
    def enrich_with_crossref(self, df: pd.DataFrame) -> pd.DataFrame:
        """Enrich missing metadata using Crossref API.
        
        Args:
            df: DataFrame to enrich
            
        Returns:
            Enriched DataFrame
        """
        if df.empty:
            return df
        
        logger.info("Enriching with Crossref data...")
        
        enriched_df = df.copy()
        crossref_count = 0
        
        # Find papers with DOI but missing metadata
        needs_enrichment = (
            enriched_df['doi'].notna() &
            (enriched_df['doi'] != "") &
            (
                (enriched_df['journal'].isna() | (enriched_df['journal'] == "")) |
                (enriched_df['abstract'].isna() | (enriched_df['abstract'] == "")) |
                (enriched_df['year'].isna())
            )
        )
        
        dois_to_enrich = enriched_df[needs_enrichment]['doi'].unique()
        logger.info(f"Found {len(dois_to_enrich)} papers needing Crossref enrichment")
        
        for doi in dois_to_enrich:
            try:
                # Query Crossref
                url = f"https://api.crossref.org/works/{doi}"
                response = rate_limited_request(
                    self.crossref_session,
                    url,
                    delay=1.0 / config.rate_limits["crossref"]
                )
                
                data = response.json()
                work = data.get("message", {})
                
                # Update rows with this DOI
                mask = enriched_df['doi'] == doi
                
                # Journal
                if work.get("container-title") and enriched_df.loc[mask, 'journal'].isna().any():
                    journal = work["container-title"][0] if isinstance(work["container-title"], list) else work["container-title"]
                    enriched_df.loc[mask & (enriched_df['journal'].isna() | (enriched_df['journal'] == "")), 'journal'] = journal
                
                # Year
                if work.get("published-print", {}).get("date-parts") and enriched_df.loc[mask, 'year'].isna().any():
                    year = work["published-print"]["date-parts"][0][0]
                    enriched_df.loc[mask & enriched_df['year'].isna(), 'year'] = year
                elif work.get("published-online", {}).get("date-parts") and enriched_df.loc[mask, 'year'].isna().any():
                    year = work["published-online"]["date-parts"][0][0]
                    enriched_df.loc[mask & enriched_df['year'].isna(), 'year'] = year
                
                # Publisher
                if work.get("publisher"):
                    if 'publisher' not in enriched_df.columns:
                        enriched_df['publisher'] = ""
                    enriched_df.loc[mask, 'publisher'] = work["publisher"]
                
                # ISSN
                if work.get("ISSN"):
                    if 'issn' not in enriched_df.columns:
                        enriched_df['issn'] = ""
                    issn = work["ISSN"][0] if isinstance(work["ISSN"], list) else work["ISSN"]
                    enriched_df.loc[mask, 'issn'] = issn
                
                crossref_count += 1
                
                # Log API call
                log_api_call(
                    logger,
                    "crossref_enrich",
                    url,
                    {"doi": doi},
                    {"status": response.status_code, "enriched": True}
                )
                
            except requests.RequestException as e:
                logger.debug(f"Error enriching DOI {doi} with Crossref: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error enriching DOI {doi}: {e}")
                continue
        
        self.metrics["crossref_enriched"] = crossref_count
        logger.info(f"Enriched {crossref_count} papers with Crossref data")
        
        return enriched_df
    
    def enrich_with_unpaywall(self, df: pd.DataFrame) -> pd.DataFrame:
        """Enrich with open access information from Unpaywall.
        
        Args:
            df: DataFrame to enrich
            
        Returns:
            Enriched DataFrame
        """
        if df.empty:
            return df
        
        logger.info("Enriching with Unpaywall data...")
        
        # Use Unpaywall enricher
        enriched_df = self.unpaywall.enrich_dataframe(df)
        
        # Count successful enrichments
        if 'is_oa' in enriched_df.columns:
            oa_count = enriched_df['is_oa'].sum()
            self.metrics["unpaywall_enriched"] = len(enriched_df)
            self.metrics["oa_status_updated"] = oa_count
            
            # Count PDF URLs found
            if 'unpaywall_pdf_url' in enriched_df.columns:
                pdf_count = (enriched_df['unpaywall_pdf_url'] != "").sum()
                self.metrics["pdf_urls_found"] = pdf_count
        
        return enriched_df
    
    def merge_pdf_urls(self, df: pd.DataFrame) -> pd.DataFrame:
        """Merge PDF URLs from different sources into main pdf_url column.
        
        Args:
            df: DataFrame with potentially multiple PDF URL columns
            
        Returns:
            DataFrame with consolidated PDF URLs
        """
        if df.empty:
            return df
        
        enriched_df = df.copy()
        
        # Ensure pdf_url column exists
        if 'pdf_url' not in enriched_df.columns:
            enriched_df['pdf_url'] = ""
        
        # Merge Unpaywall PDF URLs
        if 'unpaywall_pdf_url' in enriched_df.columns:
            # Use Unpaywall URL if main pdf_url is empty
            mask = (enriched_df['pdf_url'].isna() | (enriched_df['pdf_url'] == "")) & \
                   (enriched_df['unpaywall_pdf_url'].notna() & (enriched_df['unpaywall_pdf_url'] != ""))
            enriched_df.loc[mask, 'pdf_url'] = enriched_df.loc[mask, 'unpaywall_pdf_url']
        
        return enriched_df
    
    def add_metadata_completeness_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add a metadata completeness score to help with quality assessment.
        
        Args:
            df: DataFrame to score
            
        Returns:
            DataFrame with completeness scores
        """
        if df.empty:
            return df
        
        enriched_df = df.copy()
        
        # Define fields and their weights
        fields_weights = {
            'title': 3,      # Essential
            'abstract': 3,   # Essential
            'authors': 2,    # Important
            'journal': 2,    # Important
            'year': 2,       # Important
            'doi': 2,        # Important
            'pdf_url': 1,    # Nice to have
            'cited_by': 1,   # Nice to have
        }
        
        scores = []
        max_score = sum(fields_weights.values())
        
        for _, row in enriched_df.iterrows():
            score = 0
            for field, weight in fields_weights.items():
                if field in row and row[field] and not pd.isna(row[field]) and str(row[field]).strip() != "":
                    score += weight
            
            # Normalize to 0-100 scale
            normalized_score = (score / max_score) * 100
            scores.append(normalized_score)
        
        enriched_df['metadata_completeness'] = scores
        
        return enriched_df
    
    def enrich_dataframe(
        self,
        df: pd.DataFrame,
        use_crossref: bool = True,
        use_unpaywall: bool = True
    ) -> pd.DataFrame:
        """Perform complete enrichment of a DataFrame.
        
        Args:
            df: DataFrame to enrich
            use_crossref: Whether to use Crossref for enrichment
            use_unpaywall: Whether to use Unpaywall for enrichment
            
        Returns:
            Enriched DataFrame with metrics
        """
        logger.info(f"Starting enrichment of {len(df)} papers...")
        
        self.metrics["total_input"] = len(df)
        
        if df.empty:
            return df
        
        enriched_df = df.copy()
        
        # Enrich with Crossref
        if use_crossref:
            enriched_df = self.enrich_with_crossref(enriched_df)
        
        # Enrich with Unpaywall
        if use_unpaywall:
            enriched_df = self.enrich_with_unpaywall(enriched_df)
        
        # Merge PDF URLs from different sources
        enriched_df = self.merge_pdf_urls(enriched_df)
        
        # Add metadata completeness score
        enriched_df = self.add_metadata_completeness_score(enriched_df)
        
        # Count missing metadata filled
        original_missing = df.isna().sum().sum()
        enriched_missing = enriched_df.isna().sum().sum()
        self.metrics["missing_metadata_filled"] = max(0, original_missing - enriched_missing)
        
        logger.info(f"Enrichment completed: {self.metrics}")
        
        return enriched_df


def enrich_dataframe(
    df: pd.DataFrame,
    use_crossref: bool = True,
    use_unpaywall: bool = True
) -> pd.DataFrame:
    """Convenience function to enrich a DataFrame.
    
    Args:
        df: DataFrame to enrich
        use_crossref: Whether to use Crossref for enrichment
        use_unpaywall: Whether to use Unpaywall for enrichment
        
    Returns:
        Enriched DataFrame
    """
    enricher = MetadataEnricher()
    return enricher.enrich_dataframe(df, use_crossref, use_unpaywall)


def get_enrichment_report(metrics: Dict) -> str:
    """Generate a human-readable enrichment report.
    
    Args:
        metrics: Enrichment metrics dictionary
        
    Returns:
        Formatted report string
    """
    report = []
    report.append("Enrichment Report")
    report.append("=" * 17)
    report.append(f"Input papers: {metrics['total_input']}")
    report.append(f"Crossref enriched: {metrics['crossref_enriched']}")
    report.append(f"Unpaywall enriched: {metrics['unpaywall_enriched']}")
    report.append(f"PDF URLs found: {metrics['pdf_urls_found']}")
    report.append(f"OA papers identified: {metrics['oa_status_updated']}")
    report.append(f"Missing fields filled: {metrics['missing_metadata_filled']}")
    
    return "\n".join(report)
