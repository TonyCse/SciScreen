"""Unpaywall API enrichment module.

This module provides functions to enrich papers with open access
information using the Unpaywall API.
"""

import logging
import time
from typing import Dict, List, Optional

import pandas as pd
import requests

from ..config import config
from ..utils_io import log_api_call, rate_limited_request, setup_session

logger = logging.getLogger(__name__)


class UnpaywallEnricher:
    """Unpaywall API client for enriching papers with OA information."""
    
    def __init__(self):
        """Initialize the Unpaywall enricher."""
        self.base_url = "https://api.unpaywall.org/v2"
        self.session = setup_session()
        self.rate_limit = config.rate_limits["unpaywall"]
        self.email = config.unpaywall_email
        
        if not self.email:
            logger.warning("No Unpaywall email configured. OA enrichment will be skipped.")
    
    def get_oa_info(self, doi: str) -> Dict[str, any]:
        """Get open access information for a DOI.
        
        Args:
            doi: DOI to look up
            
        Returns:
            Dictionary with OA information
        """
        if not self.email or not doi:
            return {}
        
        try:
            # Clean DOI
            clean_doi = doi.strip().replace("https://doi.org/", "")
            
            # Build URL
            url = f"{self.base_url}/{clean_doi}?email={self.email}"
            
            # Make rate-limited request
            response = rate_limited_request(
                self.session,
                url,
                delay=1.0 / self.rate_limit
            )
            
            data = response.json()
            
            # Log API call
            log_api_call(
                logger,
                "unpaywall",
                url,
                {"doi": clean_doi},
                {"status": response.status_code, "is_oa": data.get("is_oa", False)}
            )
            
            return data
            
        except requests.RequestException as e:
            logger.debug(f"Error fetching Unpaywall data for {doi}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error with Unpaywall for {doi}: {e}")
            return {}
    
    def parse_oa_info(self, oa_data: Dict) -> Dict[str, any]:
        """Parse Unpaywall response into standardized format.
        
        Args:
            oa_data: Raw Unpaywall response
            
        Returns:
            Dictionary with parsed OA information
        """
        if not oa_data:
            return {
                "is_oa": False,
                "oa_status": "closed",
                "pdf_url": "",
                "oa_locations": []
            }
        
        # Extract basic OA status
        is_oa = oa_data.get("is_oa", False)
        
        # Map OA status
        oa_status = "closed"
        if is_oa:
            journal_is_oa = oa_data.get("journal_is_oa", False)
            has_repository_copy = oa_data.get("has_repository_copy", False)
            
            if journal_is_oa:
                oa_status = "gold"
            elif has_repository_copy:
                oa_status = "green"
            else:
                oa_status = "hybrid"
        
        # Extract best PDF URL
        pdf_url = ""
        best_oa_location = oa_data.get("best_oa_location")
        if best_oa_location:
            pdf_url = best_oa_location.get("url_for_pdf", "") or best_oa_location.get("url", "")
        
        # Extract all OA locations
        oa_locations = []
        for location in oa_data.get("oa_locations", []):
            oa_locations.append({
                "host_type": location.get("host_type", ""),
                "url": location.get("url", ""),
                "url_for_pdf": location.get("url_for_pdf", ""),
                "version": location.get("version", ""),
                "license": location.get("license", "")
            })
        
        return {
            "is_oa": is_oa,
            "oa_status": oa_status,
            "pdf_url": pdf_url,
            "oa_locations": oa_locations
        }
    
    def enrich_dataframe(
        self,
        df: pd.DataFrame,
        doi_column: str = "doi",
        batch_size: int = 100
    ) -> pd.DataFrame:
        """Enrich a DataFrame with Unpaywall data.
        
        Args:
            df: DataFrame to enrich
            doi_column: Name of the DOI column
            batch_size: Number of DOIs to process in each batch
            
        Returns:
            Enriched DataFrame
        """
        if df.empty or not self.email:
            logger.info("Skipping Unpaywall enrichment (no email or empty DataFrame)")
            return df
        
        logger.info(f"Enriching {len(df)} papers with Unpaywall data...")
        
        # Create copy to avoid modifying original
        enriched_df = df.copy()
        
        # Initialize new columns
        enriched_df["is_oa"] = False
        enriched_df["unpaywall_pdf_url"] = ""
        enriched_df["oa_locations_count"] = 0
        
        # Process DOIs in batches
        dois = enriched_df[doi_column].dropna().unique()
        logger.info(f"Processing {len(dois)} unique DOIs...")
        
        for i in range(0, len(dois), batch_size):
            batch_dois = dois[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(dois)-1)//batch_size + 1}")
            
            for doi in batch_dois:
                # Get Unpaywall data
                oa_data = self.get_oa_info(doi)
                parsed_oa = self.parse_oa_info(oa_data)
                
                # Update rows with this DOI
                mask = enriched_df[doi_column] == doi
                enriched_df.loc[mask, "is_oa"] = parsed_oa["is_oa"]
                enriched_df.loc[mask, "unpaywall_pdf_url"] = parsed_oa["pdf_url"]
                enriched_df.loc[mask, "oa_locations_count"] = len(parsed_oa["oa_locations"])
                
                # Update existing oa_status if it was unknown
                if "oa_status" in enriched_df.columns:
                    unknown_mask = mask & (enriched_df["oa_status"].isin(["unknown", "", pd.NA]))
                    enriched_df.loc[unknown_mask, "oa_status"] = parsed_oa["oa_status"]
                
                # Update existing pdf_url if empty
                if "pdf_url" in enriched_df.columns:
                    empty_pdf_mask = mask & (enriched_df["pdf_url"].isin(["", pd.NA]))
                    enriched_df.loc[empty_pdf_mask, "pdf_url"] = parsed_oa["pdf_url"]
        
        # Log results
        oa_count = enriched_df["is_oa"].sum()
        logger.info(f"Unpaywall enrichment completed: {oa_count}/{len(enriched_df)} papers are open access")
        
        return enriched_df


def enrich_with_oa_info(
    df: pd.DataFrame,
    doi_column: str = "doi",
    batch_size: int = 100
) -> pd.DataFrame:
    """Convenience function to enrich DataFrame with Unpaywall data.
    
    Args:
        df: DataFrame to enrich
        doi_column: Name of the DOI column
        batch_size: Number of DOIs to process in each batch
        
    Returns:
        Enriched DataFrame
    """
    enricher = UnpaywallEnricher()
    return enricher.enrich_dataframe(df, doi_column, batch_size)


def get_oa_info(doi: str) -> Dict[str, any]:
    """Convenience function to get OA info for a single DOI.
    
    Args:
        doi: DOI to look up
        
    Returns:
        Dictionary with parsed OA information
    """
    enricher = UnpaywallEnricher()
    oa_data = enricher.get_oa_info(doi)
    return enricher.parse_oa_info(oa_data)
