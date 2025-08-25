"""PubMed/NCBI E-utilities harvesting module.

This module provides functions to search and retrieve academic works
from PubMed using the NCBI E-utilities API.
"""

import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote

import pandas as pd
import requests
import xmltodict

from ..config import config
from ..utils_io import (
    log_api_call,
    rate_limited_request,
    save_dataframe,
    save_jsonl,
    setup_session,
)

logger = logging.getLogger(__name__)


class PubMedHarvester:
    """PubMed E-utilities API client for harvesting academic works."""
    
    def __init__(self):
        """Initialize the PubMed harvester."""
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.session = setup_session()
        self.rate_limit = config.rate_limits["pubmed"]
        self.email = config.pubmed_email
        
    def build_search_url(
        self,
        query: str,
        year_from: int,
        year_to: int,
        retmax: int = 200,
        retstart: int = 0
    ) -> str:
        """Build PubMed ESearch URL.
        
        Args:
            query: Search query string
            year_from: Start year for filtering
            year_to: End year for filtering
            retmax: Maximum number of results
            retstart: Starting position
            
        Returns:
            Complete search URL
        """
        # Add date range to query
        date_filter = f"AND ({year_from}[PDAT]:{year_to}[PDAT])"
        full_query = f"{query} {date_filter}"
        
        params = {
            "db": "pubmed",
            "term": full_query,
            "retmax": retmax,
            "retstart": retstart,
            "retmode": "xml",
            "email": self.email,
            "tool": "lit-review-pipeline"
        }
        
        param_string = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
        return f"{self.base_url}/esearch.fcgi?{param_string}"
    
    def build_fetch_url(self, pmids: List[str]) -> str:
        """Build PubMed EFetch URL.
        
        Args:
            pmids: List of PubMed IDs
            
        Returns:
            Complete fetch URL
        """
        id_string = ",".join(pmids)
        params = {
            "db": "pubmed",
            "id": id_string,
            "retmode": "xml",
            "email": self.email,
            "tool": "lit-review-pipeline"
        }
        
        param_string = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
        return f"{self.base_url}/efetch.fcgi?{param_string}"
    
    def search_pmids(
        self,
        query: str,
        year_from: int,
        year_to: int,
        max_results: int = 2000
    ) -> List[str]:
        """Search for PMIDs using ESearch.
        
        Args:
            query: Search query string
            year_from: Start year for filtering
            year_to: End year for filtering
            max_results: Maximum number of results
            
        Returns:
            List of PubMed IDs
        """
        logger.info(f"Searching PubMed for PMIDs: '{query}' ({year_from}-{year_to})")
        
        all_pmids = []
        retstart = 0
        retmax = 200  # PubMed's recommended maximum
        
        while len(all_pmids) < max_results:
            try:
                # Build search URL
                url = self.build_search_url(
                    query=query,
                    year_from=year_from,
                    year_to=year_to,
                    retmax=min(retmax, max_results - len(all_pmids)),
                    retstart=retstart
                )
                
                logger.info(f"Fetching PMIDs starting at {retstart}...")
                
                # Make rate-limited request
                response = rate_limited_request(
                    self.session,
                    url,
                    delay=1.0 / self.rate_limit
                )
                
                # Parse XML response
                root = ET.fromstring(response.text)
                pmids = [id_elem.text for id_elem in root.findall(".//Id")]
                
                if not pmids:
                    logger.info("No more PMIDs available")
                    break
                
                all_pmids.extend(pmids)
                logger.info(f"Retrieved {len(all_pmids)} PMIDs so far")
                
                # Check if we've reached the end
                count_elem = root.find(".//Count")
                total_count = int(count_elem.text) if count_elem is not None else 0
                
                if retstart + retmax >= total_count:
                    break
                
                retstart += retmax
                
            except Exception as e:
                logger.error(f"Error searching PMIDs: {e}")
                break
        
        logger.info(f"PubMed search completed: {len(all_pmids)} PMIDs found")
        return all_pmids
    
    def parse_article(self, article_dict: Dict) -> Dict:
        """Parse a single article from PubMed XML.
        
        Args:
            article_dict: Article data from XML (converted to dict)
            
        Returns:
            Standardized work dictionary
        """
        try:
            # Navigate the complex PubMed XML structure
            medline_citation = article_dict.get("MedlineCitation", {})
            article = medline_citation.get("Article", {})
            
            # Extract PMID
            pmid = str(medline_citation.get("PMID", {}).get("#text", ""))
            
            # Extract title
            title = ""
            if article.get("ArticleTitle"):
                title_data = article["ArticleTitle"]
                if isinstance(title_data, dict):
                    title = title_data.get("#text", "")
                else:
                    title = str(title_data)
            
            # Extract abstract
            abstract = ""
            if article.get("Abstract", {}).get("AbstractText"):
                abstract_data = article["Abstract"]["AbstractText"]
                if isinstance(abstract_data, list):
                    abstract_parts = []
                    for part in abstract_data:
                        if isinstance(part, dict):
                            abstract_parts.append(part.get("#text", ""))
                        else:
                            abstract_parts.append(str(part))
                    abstract = " ".join(abstract_parts)
                elif isinstance(abstract_data, dict):
                    abstract = abstract_data.get("#text", "")
                else:
                    abstract = str(abstract_data)
            
            # Extract authors
            authors = []
            author_list = article.get("AuthorList", {}).get("Author", [])
            if not isinstance(author_list, list):
                author_list = [author_list]
            
            for author in author_list:
                if isinstance(author, dict):
                    last_name = author.get("LastName", "")
                    fore_name = author.get("ForeName", "")
                    initials = author.get("Initials", "")
                    
                    if last_name:
                        if fore_name:
                            authors.append(f"{last_name}, {fore_name}")
                        elif initials:
                            authors.append(f"{last_name}, {initials}")
                        else:
                            authors.append(last_name)
            
            authors_str = "; ".join(authors)
            
            # Extract journal
            journal = ""
            journal_data = article.get("Journal", {})
            if journal_data.get("Title"):
                journal = journal_data["Title"]
            elif journal_data.get("ISOAbbreviation"):
                journal = journal_data["ISOAbbreviation"]
            
            # Extract year
            year = None
            pub_date = article.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {})
            if pub_date.get("Year"):
                year = int(pub_date["Year"])
            elif pub_date.get("MedlineDate"):
                # Handle date ranges like "2023 Jan-Feb"
                medline_date = pub_date["MedlineDate"]
                try:
                    year = int(medline_date.split()[0])
                except (IndexError, ValueError):
                    pass
            
            # Extract DOI
            doi = ""
            article_ids = medline_citation.get("Article", {}).get("ELocationID", [])
            if not isinstance(article_ids, list):
                article_ids = [article_ids]
            
            for article_id in article_ids:
                if isinstance(article_id, dict) and article_id.get("@EIdType") == "doi":
                    doi = article_id.get("#text", "")
                    break
            
            # Build URL
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
            
            # Extract publication types
            pub_types = article.get("PublicationTypeList", {}).get("PublicationType", [])
            if not isinstance(pub_types, list):
                pub_types = [pub_types]
            
            doc_type = "journal-article"  # Default
            for pub_type in pub_types:
                if isinstance(pub_type, dict):
                    pub_type_text = pub_type.get("#text", "").lower()
                    if "review" in pub_type_text:
                        doc_type = "review"
                    elif "case report" in pub_type_text:
                        doc_type = "case-report"
                    elif "editorial" in pub_type_text:
                        doc_type = "editorial"
            
            return {
                "source": "pubmed",
                "id": pmid,
                "doi": doi,
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "authors": authors_str,
                "journal": journal,
                "year": year,
                "doc_type": doc_type,
                "lang": "",  # Language detection will be done later
                "url": url,
                "pdf_url": "",  # Will be enriched later
                "oa_status": "unknown",  # Will be enriched later
                "cited_by": 0,  # PubMed doesn't provide citation counts
            }
            
        except Exception as e:
            logger.error(f"Error parsing article: {e}")
            return {}
    
    def fetch_articles(self, pmids: List[str]) -> List[Dict]:
        """Fetch full article data using EFetch.
        
        Args:
            pmids: List of PubMed IDs
            
        Returns:
            List of parsed article dictionaries
        """
        logger.info(f"Fetching {len(pmids)} articles from PubMed...")
        
        articles = []
        batch_size = 200  # Process in batches to avoid timeout
        
        # Prepare raw data storage
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_file = config.data_dir / "raw" / f"pubmed_{timestamp}.jsonl"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        
        for i in range(0, len(pmids), batch_size):
            batch_pmids = pmids[i:i + batch_size]
            
            try:
                # Build fetch URL
                url = self.build_fetch_url(batch_pmids)
                
                logger.info(f"Fetching batch {i//batch_size + 1}/{(len(pmids)-1)//batch_size + 1}...")
                
                # Make rate-limited request
                response = rate_limited_request(
                    self.session,
                    url,
                    delay=1.0 / self.rate_limit
                )
                
                # Parse XML to dict
                xml_dict = xmltodict.parse(response.text)
                
                # Extract articles
                pubmed_data = xml_dict.get("PubmedArticleSet", {})
                pubmed_articles = pubmed_data.get("PubmedArticle", [])
                
                if not isinstance(pubmed_articles, list):
                    pubmed_articles = [pubmed_articles]
                
                # Save raw data
                save_jsonl(pubmed_articles, raw_file, append=True)
                
                # Parse articles
                for article_data in pubmed_articles:
                    parsed_article = self.parse_article(article_data)
                    if parsed_article:
                        articles.append(parsed_article)
                
                # Log API call
                log_api_call(
                    logger,
                    "pubmed",
                    url,
                    {"pmids_count": len(batch_pmids)},
                    {"status": response.status_code, "articles": len(pubmed_articles)}
                )
                
            except Exception as e:
                logger.error(f"Error fetching batch starting at {i}: {e}")
                continue
        
        logger.info(f"Fetched {len(articles)} articles from PubMed")
        return articles
    
    def search_and_fetch(
        self,
        query: str,
        year_from: int,
        year_to: int,
        max_results: int = 2000
    ) -> pd.DataFrame:
        """Search and fetch articles from PubMed.
        
        Args:
            query: Search query string
            year_from: Start year for filtering
            year_to: End year for filtering
            max_results: Maximum number of results
            
        Returns:
            DataFrame with standardized work data
        """
        # Step 1: Search for PMIDs
        pmids = self.search_pmids(query, year_from, year_to, max_results)
        
        if not pmids:
            logger.warning("No PMIDs found")
            return pd.DataFrame()
        
        # Step 2: Fetch full article data
        articles = self.fetch_articles(pmids)
        
        # Convert to DataFrame
        df = pd.DataFrame(articles)
        
        # Save processed data
        if not df.empty:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            processed_file = config.data_dir / "interim" / f"pubmed_{timestamp}.csv"
            save_dataframe(df, processed_file)
            logger.info(f"Saved {len(df)} works to {processed_file}")
        
        logger.info(f"PubMed search completed: {len(df)} works retrieved")
        return df


def search_and_fetch(
    query: str,
    year_from: int = 2015,
    year_to: int = 2025,
    max_results: int = 2000
) -> pd.DataFrame:
    """Convenience function to search and fetch PubMed articles.
    
    Args:
        query: Search query string
        year_from: Start year for filtering
        year_to: End year for filtering
        max_results: Maximum number of results
        
    Returns:
        DataFrame with standardized work data
    """
    harvester = PubMedHarvester()
    return harvester.search_and_fetch(
        query=query,
        year_from=year_from,
        year_to=year_to,
        max_results=max_results
    )
