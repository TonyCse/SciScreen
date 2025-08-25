"""OpenAlex API harvesting module.

This module provides functions to search and retrieve academic works
from the OpenAlex database using their REST API.
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


class OpenAlexHarvester:
    """OpenAlex API client for harvesting academic works."""
    
    def __init__(self):
        """Initialize the OpenAlex harvester."""
        self.base_url = config.openalex_base
        self.session = setup_session()
        self.rate_limit = config.rate_limits["openalex"]
        
    def build_query_url(
        self,
        query: str,
        year_from: int,
        year_to: int,
        per_page: int = 200,
        page: int = 1,
        filters: Optional[Dict[str, str]] = None
    ) -> str:
        """Build OpenAlex query URL.
        
        Args:
            query: Search query string
            year_from: Start year for filtering
            year_to: End year for filtering
            per_page: Number of results per page
            page: Page number
            filters: Additional filters to apply
            
        Returns:
            Complete query URL
        """
        # Encode the query
        encoded_query = quote(query)
        
        # Build base URL
        url = f"{self.base_url}/works"
        
        # Build filter string
        filter_parts = [
            f"publication_year:{year_from}-{year_to}",
        ]
        
        if filters:
            for key, value in filters.items():
                filter_parts.append(f"{key}:{value}")
        
        filter_string = ",".join(filter_parts)
        
        # Build complete URL
        params = {
            "search": query,
            "filter": filter_string,
            "per-page": per_page,
            "page": page,
            "mailto": config.crossref_mailto or "example@example.com",
        }
        
        param_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{url}?{param_string}"
    
    def parse_work(self, work: Dict) -> Dict:
        """Parse a single work from OpenAlex response.
        
        Args:
            work: Raw work data from OpenAlex
            
        Returns:
            Standardized work dictionary
        """
        # Extract DOI
        doi = ""
        if work.get("doi"):
            doi = work["doi"].replace("https://doi.org/", "")
        
        # Extract authors
        authors = []
        if work.get("authorships"):
            for authorship in work["authorships"]:
                author = authorship.get("author", {})
                if author.get("display_name"):
                    authors.append(author["display_name"])
        authors_str = "; ".join(authors) if authors else ""
        
        # Extract journal
        journal = ""
        if work.get("primary_location", {}).get("source"):
            journal = work["primary_location"]["source"].get("display_name", "")
        
        # Extract URL
        url = work.get("doi", "") or work.get("id", "")
        
        # Extract PDF URL from locations
        pdf_url = ""
        if work.get("open_access", {}).get("oa_url"):
            pdf_url = work["open_access"]["oa_url"]
        elif work.get("best_oa_location", {}).get("pdf_url"):
            pdf_url = work["best_oa_location"]["pdf_url"]
        
        # Extract OA status
        oa_status = "closed"
        if work.get("open_access", {}).get("is_oa"):
            oa_status = work.get("open_access", {}).get("oa_status", "unknown")
        
        return {
            "source": "openalex",
            "id": work.get("id", ""),
            "doi": doi,
            "pmid": "",  # OpenAlex doesn't directly provide PMID
            "title": work.get("title", ""),
            "abstract": work.get("abstract", "") or work.get("abstract_inverted_index", ""),
            "authors": authors_str,
            "journal": journal,
            "year": work.get("publication_year"),
            "doc_type": work.get("type", "").replace("https://openalex.org/", ""),
            "lang": work.get("language", ""),
            "url": url,
            "pdf_url": pdf_url,
            "oa_status": oa_status,
            "cited_by": work.get("cited_by_count", 0),
        }
    
    def search_works(
        self,
        query: str,
        year_from: int,
        year_to: int,
        max_results: int = 2000,
        per_page: int = 200
    ) -> pd.DataFrame:
        """Search for works in OpenAlex.
        
        Args:
            query: Search query string
            year_from: Start year for filtering
            year_to: End year for filtering
            max_results: Maximum number of results to retrieve
            per_page: Number of results per page
            
        Returns:
            DataFrame with standardized work data
        """
        logger.info(f"Starting OpenAlex search: '{query}' ({year_from}-{year_to})")
        
        all_works = []
        page = 1
        total_retrieved = 0
        max_pages = max_results // per_page + 1
        
        # Prepare raw data storage
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_file = config.data_dir / "raw" / f"openalex_{timestamp}.jsonl"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        
        while total_retrieved < max_results and page <= max_pages:
            try:
                # Build URL for this page
                url = self.build_query_url(
                    query=query,
                    year_from=year_from,
                    year_to=year_to,
                    per_page=per_page,
                    page=page
                )
                
                logger.info(f"Fetching page {page} from OpenAlex...")
                
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
                    "openalex",
                    url,
                    {"query": query, "page": page, "per_page": per_page},
                    {
                        "status": response.status_code,
                        "results": len(data.get("results", [])),
                        "total": data.get("meta", {}).get("count", 0)
                    }
                )
                
                # Parse results
                works = data.get("results", [])
                if not works:
                    logger.info("No more results available")
                    break
                
                # Save raw data
                save_jsonl(works, raw_file, append=True)
                
                # Parse and add to collection
                for work in works:
                    parsed_work = self.parse_work(work)
                    all_works.append(parsed_work)
                
                total_retrieved += len(works)
                logger.info(f"Retrieved {total_retrieved} works so far")
                
                # Check if we've reached the end
                meta = data.get("meta", {})
                if page >= meta.get("count", 0) / per_page:
                    break
                
                page += 1
                
            except requests.RequestException as e:
                logger.error(f"Error fetching page {page}: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error on page {page}: {e}")
                break
        
        # Convert to DataFrame
        df = pd.DataFrame(all_works)
        
        # Save processed data
        if not df.empty:
            processed_file = config.data_dir / "interim" / f"openalex_{timestamp}.csv"
            save_dataframe(df, processed_file)
            logger.info(f"Saved {len(df)} works to {processed_file}")
        
        logger.info(f"OpenAlex search completed: {len(df)} works retrieved")
        return df


def get_works(
    query: str,
    year_from: int = 2015,
    year_to: int = 2025,
    max_results: int = 2000,
    per_page: int = 200
) -> pd.DataFrame:
    """Convenience function to search OpenAlex works.
    
    Args:
        query: Search query string
        year_from: Start year for filtering
        year_to: End year for filtering
        max_results: Maximum number of results to retrieve
        per_page: Number of results per page
        
    Returns:
        DataFrame with standardized work data
    """
    harvester = OpenAlexHarvester()
    return harvester.search_works(
        query=query,
        year_from=year_from,
        year_to=year_to,
        max_results=max_results,
        per_page=per_page
    )
