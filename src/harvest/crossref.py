"""Crossref API harvesting module.

This module provides functions to search and retrieve academic works
from the Crossref database using their REST API.
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


class CrossrefHarvester:
    """Crossref API client for harvesting academic works."""
    
    def __init__(self):
        """Initialize the Crossref harvester."""
        self.base_url = "https://api.crossref.org"
        self.session = setup_session()
        self.rate_limit = config.rate_limits["crossref"]
        
        # Set User-Agent and mailto headers
        self.session.headers.update({
            "User-Agent": f"LitReviewPipeline/1.0 (mailto:{config.crossref_mailto or 'example@example.com'})",
        })
        
    def build_query_url(
        self,
        query: str,
        year_from: int,
        year_to: int,
        rows: int = 200,
        offset: int = 0,
        filters: Optional[Dict[str, str]] = None
    ) -> str:
        """Build Crossref query URL.
        
        Args:
            query: Search query string
            year_from: Start year for filtering
            year_to: End year for filtering
            rows: Number of results per page
            offset: Starting offset
            filters: Additional filters to apply
            
        Returns:
            Complete query URL
        """
        # Build base URL
        url = f"{self.base_url}/works"
        
        # Build parameters
        params = {
            "query": query,
            "filter": f"from-pub-date:{year_from},until-pub-date:{year_to}",
            "rows": rows,
            "offset": offset,
            "sort": "relevance",
            "order": "desc",
        }
        
        # Add additional filters
        if filters:
            existing_filter = params.get("filter", "")
            additional_filters = ",".join([f"{k}:{v}" for k, v in filters.items()])
            if existing_filter:
                params["filter"] = f"{existing_filter},{additional_filters}"
            else:
                params["filter"] = additional_filters
        
        # Build complete URL
        param_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{url}?{param_string}"
    
    def parse_work(self, work: Dict) -> Dict:
        """Parse a single work from Crossref response.
        
        Args:
            work: Raw work data from Crossref
            
        Returns:
            Standardized work dictionary
        """
        # Extract DOI
        doi = work.get("DOI", "")
        
        # Extract title
        title = ""
        if work.get("title"):
            title = work["title"][0] if isinstance(work["title"], list) else work["title"]
        
        # Extract authors
        authors = []
        if work.get("author"):
            for author in work["author"]:
                given = author.get("given", "")
                family = author.get("family", "")
                if family:
                    if given:
                        authors.append(f"{family}, {given}")
                    else:
                        authors.append(family)
        authors_str = "; ".join(authors)
        
        # Extract journal
        journal = ""
        if work.get("container-title"):
            journal = work["container-title"][0] if isinstance(work["container-title"], list) else work["container-title"]
        
        # Extract year
        year = None
        if work.get("published-print", {}).get("date-parts"):
            year = work["published-print"]["date-parts"][0][0]
        elif work.get("published-online", {}).get("date-parts"):
            year = work["published-online"]["date-parts"][0][0]
        elif work.get("created", {}).get("date-parts"):
            year = work["created"]["date-parts"][0][0]
        
        # Extract abstract (rarely available in Crossref)
        abstract = work.get("abstract", "")
        
        # Extract URL
        url = work.get("URL", f"https://doi.org/{doi}" if doi else "")
        
        # Extract document type
        doc_type = work.get("type", "")
        
        # Extract language
        lang = work.get("language", "")
        
        # Extract citation count (if available)
        cited_by = work.get("is-referenced-by-count", 0)
        
        return {
            "source": "crossref",
            "id": doi,
            "doi": doi,
            "pmid": "",  # Crossref doesn't directly provide PMID
            "title": title,
            "abstract": abstract,
            "authors": authors_str,
            "journal": journal,
            "year": year,
            "doc_type": doc_type,
            "lang": lang,
            "url": url,
            "pdf_url": "",  # Will be enriched later via Unpaywall
            "oa_status": "unknown",  # Will be enriched later
            "cited_by": cited_by,
        }
    
    def search_works(
        self,
        query: str,
        year_from: int,
        year_to: int,
        max_results: int = 2000,
        rows: int = 200
    ) -> pd.DataFrame:
        """Search for works in Crossref.
        
        Args:
            query: Search query string
            year_from: Start year for filtering
            year_to: End year for filtering
            max_results: Maximum number of results to retrieve
            rows: Number of results per page
            
        Returns:
            DataFrame with standardized work data
        """
        logger.info(f"Starting Crossref search: '{query}' ({year_from}-{year_to})")
        
        all_works = []
        offset = 0
        total_retrieved = 0
        
        # Prepare raw data storage
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_file = config.data_dir / "raw" / f"crossref_{timestamp}.jsonl"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        
        while total_retrieved < max_results:
            try:
                # Build URL for this page
                url = self.build_query_url(
                    query=query,
                    year_from=year_from,
                    year_to=year_to,
                    rows=rows,
                    offset=offset
                )
                
                logger.info(f"Fetching offset {offset} from Crossref...")
                
                # Make rate-limited request
                response = rate_limited_request(
                    self.session,
                    url,
                    delay=1.0 / self.rate_limit
                )
                
                data = response.json()
                
                # Check for API errors
                if data.get("status") != "ok":
                    logger.error(f"Crossref API error: {data}")
                    break
                
                # Log API call
                message = data.get("message", {})
                log_api_call(
                    logger,
                    "crossref",
                    url,
                    {"query": query, "offset": offset, "rows": rows},
                    {
                        "status": response.status_code,
                        "results": len(message.get("items", [])),
                        "total": message.get("total-results", 0)
                    }
                )
                
                # Parse results
                works = message.get("items", [])
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
                if len(works) < rows or total_retrieved >= max_results:
                    break
                
                offset += rows
                
            except requests.RequestException as e:
                logger.error(f"Error fetching offset {offset}: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error at offset {offset}: {e}")
                break
        
        # Convert to DataFrame
        df = pd.DataFrame(all_works)
        
        # Save processed data
        if not df.empty:
            processed_file = config.data_dir / "interim" / f"crossref_{timestamp}.csv"
            save_dataframe(df, processed_file)
            logger.info(f"Saved {len(df)} works to {processed_file}")
        
        logger.info(f"Crossref search completed: {len(df)} works retrieved")
        return df


def search_works(
    query: str,
    year_from: int = 2015,
    year_to: int = 2025,
    max_results: int = 2000,
    rows: int = 200
) -> pd.DataFrame:
    """Convenience function to search Crossref works.
    
    Args:
        query: Search query string
        year_from: Start year for filtering
        year_to: End year for filtering
        max_results: Maximum number of results to retrieve
        rows: Number of results per page
        
    Returns:
        DataFrame with standardized work data
    """
    harvester = CrossrefHarvester()
    return harvester.search_works(
        query=query,
        year_from=year_from,
        year_to=year_to,
        max_results=max_results,
        rows=rows
    )
