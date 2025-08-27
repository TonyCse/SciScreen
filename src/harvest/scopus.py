"""Scopus API harvesting module.

This module provides functions to search and retrieve academic works
from Scopus using their API.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote

import pandas as pd
import requests

from ..config import config
from ..utils_io import (
    log_api_call,
    rate_limited_request,
    save_dataframe,
    save_jsonl,
    setup_session,
)

logger = logging.getLogger(__name__)


class ScopusHarvester:
    """Scopus API client for harvesting academic works."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Scopus harvester.
        
        Args:
            api_key: Scopus API key (optional, can be set in config)
        """
        self.base_url = "https://api.elsevier.com/content/search/scopus"
        self.session = setup_session()
        self.rate_limit = 2  # Scopus allows 2 requests per second
        self.api_key = api_key or getattr(config, 'scopus_api_key', '')
        
        if not self.api_key:
            logger.warning("No Scopus API key configured. Scopus search will be disabled.")
            return
        
        # Set headers
        self.session.headers.update({
            "X-ELS-APIKey": self.api_key,
            "Accept": "application/json",
            "User-Agent": "LitReviewPipeline/1.0"
        })
    
    def search_works(
        self,
        query: str,
        year_from: int,
        year_to: int,
        max_results: int = 200,
        count: int = 25
    ) -> pd.DataFrame:
        """Search for works in Scopus.
        
        Args:
            query: Search query string
            year_from: Start year for filtering
            year_to: End year for filtering
            max_results: Maximum number of results to retrieve
            count: Number of results per request (max 200)
            
        Returns:
            DataFrame with standardized work data
        """
        if not self.api_key:
            logger.warning("Scopus API key not available, skipping search")
            return pd.DataFrame()
        
        logger.info(f"Starting Scopus search: '{query}' ({year_from}-{year_to})")
        
        all_works = []
        start = 0
        
        # Prepare raw data storage
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_file = config.data_dir / "raw" / f"scopus_{timestamp}.jsonl"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        
        while start < max_results:
            try:
                # Build search parameters
                params = {
                    "query": f"{query} AND PUBYEAR > {year_from-1} AND PUBYEAR < {year_to+1}",
                    "start": start,
                    "count": min(count, max_results - start),
                    "field": "doi,title,creator,publicationName,coverDate,abstract,citedby-count,openaccess,eid,prism:issn",
                    "sort": "relevancy"
                }
                
                logger.info(f"Fetching Scopus results starting at {start}...")
                
                # Make rate-limited request
                response = rate_limited_request(
                    self.session,
                    self.base_url,
                    delay=1.0 / self.rate_limit,
                    params=params
                )
                
                data = response.json()
                
                # Check for errors
                if "search-results" not in data:
                    error_msg = data.get("error-response", {}).get("error-message", "Unknown error")
                    logger.error(f"Scopus API error: {error_msg}")
                    break
                
                search_results = data["search-results"]
                entries = search_results.get("entry", [])
                
                if not entries:
                    logger.info("No more results available")
                    break
                
                # Log API call
                total_results = int(search_results.get("opensearch:totalResults", 0))
                log_api_call(
                    logger,
                    "scopus",
                    self.base_url,
                    params,
                    {
                        "status": response.status_code,
                        "results": len(entries),
                        "total": total_results
                    }
                )
                
                # Save raw data
                save_jsonl(entries, raw_file, append=True)
                
                # Parse and add to collection
                for entry in entries:
                    parsed_work = self.parse_work(entry)
                    if parsed_work:
                        all_works.append(parsed_work)
                
                logger.info(f"Retrieved {len(all_works)} works so far")
                
                # Check if we've reached the end
                if len(entries) < count or start + count >= total_results:
                    break
                
                start += count
                
            except requests.RequestException as e:
                logger.error(f"Error fetching from Scopus: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                break
        
        # Convert to DataFrame
        df = pd.DataFrame(all_works)
        
        # Save processed data
        if not df.empty:
            processed_file = config.data_dir / "interim" / f"scopus_{timestamp}.csv"
            save_dataframe(df, processed_file)
            logger.info(f"Saved {len(df)} works to {processed_file}")
        
        logger.info(f"Scopus search completed: {len(df)} works retrieved")
        return df
    
    def parse_work(self, entry: Dict) -> Optional[Dict]:
        """Parse a single work from Scopus response.
        
        Args:
            entry: Raw work data from Scopus
            
        Returns:
            Standardized work dictionary or None if parsing fails
        """
        try:
            # Extract DOI
            doi = entry.get("prism:doi", "")
            
            # Extract title
            title = entry.get("dc:title", "")
            
            # Extract authors
            authors = entry.get("dc:creator", "")
            if isinstance(authors, list):
                authors = "; ".join(authors)
            
            # Extract journal
            journal = entry.get("prism:publicationName", "")
            
            # Extract year
            year = None
            cover_date = entry.get("prism:coverDate", "")
            if cover_date:
                try:
                    year = int(cover_date.split("-")[0])
                except (ValueError, IndexError):
                    pass
            
            # Extract abstract (may not always be available)
            abstract = entry.get("dc:description", "")
            
            # Extract citations
            cited_by = entry.get("citedby-count", 0)
            try:
                cited_by = int(cited_by)
            except (ValueError, TypeError):
                cited_by = 0
            
            # Extract open access info
            oa_flag = entry.get("openaccess", "0")
            oa_status = "gold" if oa_flag == "1" else "closed"
            
            # Build URL
            eid = entry.get("eid", "")
            url = f"https://www.scopus.com/record/display.uri?eid={eid}" if eid else ""
            if doi:
                url = f"https://doi.org/{doi}"
            
            return {
                "source": "scopus",
                "id": eid,
                "doi": doi,
                "pmid": "",  # Scopus doesn't directly provide PMID
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "journal": journal,
                "year": year,
                "doc_type": "journal-article",  # Default, could be refined
                "lang": "",  # Language detection will be done later
                "url": url,
                "pdf_url": "",  # Will be enriched later via Unpaywall
                "oa_status": oa_status,
                "cited_by": cited_by,
            }
            
        except Exception as e:
            logger.error(f"Error parsing Scopus entry: {e}")
            return None


def search_scopus(
    query: str,
    year_from: int = 2015,
    year_to: int = 2025,
    max_results: int = 200,
    api_key: Optional[str] = None
) -> pd.DataFrame:
    """Convenience function to search Scopus.
    
    Args:
        query: Search query string
        year_from: Start year for filtering
        year_to: End year for filtering
        max_results: Maximum number of results to retrieve
        api_key: Scopus API key (optional)
        
    Returns:
        DataFrame with standardized work data
    """
    harvester = ScopusHarvester(api_key)
    return harvester.search_works(
        query=query,
        year_from=year_from,
        year_to=year_to,
        max_results=max_results
    )

