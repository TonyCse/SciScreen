"""Zotero Web API client for the Literature Review Pipeline.

This module provides functions to interact with Zotero Web API
for creating collections, adding items, and managing attachments.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests

from ..config import config
from ..utils_io import log_api_call, rate_limited_request, setup_session

logger = logging.getLogger(__name__)


class ZoteroClient:
    """Zotero Web API client."""
    
    def __init__(self):
        """Initialize Zotero client."""
        self.user_id = config.zotero_user_id
        self.api_key = config.zotero_api_key
        self.base_url = "https://api.zotero.org"
        self.session = setup_session()
        self.rate_limit = config.rate_limits["zotero"]
        
        if not self.user_id or not self.api_key:
            logger.warning("Zotero credentials not configured. Integration will be disabled.")
            return
        
        # Set authentication header
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
        
        # Validate credentials
        self._validate_credentials()
    
    def _validate_credentials(self) -> bool:
        """Validate Zotero API credentials.
        
        Returns:
            True if credentials are valid, False otherwise
        """
        try:
            url = f"{self.base_url}/users/{self.user_id}/items"
            params = {"limit": 1}
            
            response = rate_limited_request(
                self.session,
                url,
                delay=1.0 / self.rate_limit,
                params=params
            )
            
            logger.info("Zotero credentials validated successfully")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Invalid Zotero credentials: {e}")
            return False
    
    def get_collections(self) -> List[Dict]:
        """Get all collections for the user.
        
        Returns:
            List of collection dictionaries
        """
        if not self.user_id or not self.api_key:
            return []
        
        try:
            url = f"{self.base_url}/users/{self.user_id}/collections"
            
            response = rate_limited_request(
                self.session,
                url,
                delay=1.0 / self.rate_limit
            )
            
            collections = response.json()
            logger.info(f"Retrieved {len(collections)} collections")
            
            return collections
            
        except requests.RequestException as e:
            logger.error(f"Error fetching collections: {e}")
            return []
    
    def find_collection_by_name(self, collection_name: str) -> Optional[Dict]:
        """Find a collection by name.
        
        Args:
            collection_name: Name of the collection to find
            
        Returns:
            Collection dictionary if found, None otherwise
        """
        collections = self.get_collections()
        
        for collection in collections:
            if collection.get("data", {}).get("name") == collection_name:
                return collection
        
        return None
    
    def create_collection(self, collection_name: str, parent_collection: Optional[str] = None) -> Optional[str]:
        """Create a new collection.
        
        Args:
            collection_name: Name of the new collection
            parent_collection: Key of parent collection (optional)
            
        Returns:
            Collection key if successful, None otherwise
        """
        if not self.user_id or not self.api_key:
            return None
        
        try:
            url = f"{self.base_url}/users/{self.user_id}/collections"
            
            collection_data = {
                "name": collection_name,
                "parentCollection": parent_collection or False
            }
            
            payload = [collection_data]
            
            response = self.session.post(
                url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            # Parse response to get collection key
            result = response.json()
            if result.get("successful"):
                collection_key = list(result["successful"].keys())[0]
                logger.info(f"Created collection '{collection_name}' with key {collection_key}")
                return collection_key
            else:
                logger.error(f"Failed to create collection: {result}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error creating collection: {e}")
            return None
    
    def ensure_collection(self, collection_name: str) -> Optional[str]:
        """Ensure a collection exists, create if it doesn't.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Collection key if successful, None otherwise
        """
        # First, try to find existing collection
        existing_collection = self.find_collection_by_name(collection_name)
        
        if existing_collection:
            collection_key = existing_collection.get("key")
            logger.info(f"Found existing collection '{collection_name}' with key {collection_key}")
            return collection_key
        
        # Create new collection
        return self.create_collection(collection_name)
    
    def create_item_from_paper(self, paper: Dict) -> Dict:
        """Create Zotero item data from paper dictionary.
        
        Args:
            paper: Paper data dictionary
            
        Returns:
            Zotero item data dictionary
        """
        # Map document types to Zotero item types
        type_mapping = {
            'journal-article': 'journalArticle',
            'proceedings-article': 'conferencePaper',
            'book-chapter': 'bookSection',
            'book': 'book',
            'thesis': 'thesis',
            'report': 'report',
            'preprint': 'preprint',
            'review': 'journalArticle',
            'editorial': 'journalArticle',
            'letter': 'journalArticle',
            'case-report': 'journalArticle'
        }
        
        doc_type = paper.get('doc_type', 'journal-article')
        item_type = type_mapping.get(doc_type, 'journalArticle')
        
        # Parse authors
        authors = []
        authors_str = paper.get('authors', '')
        if authors_str:
            author_list = authors_str.split(';')
            for author in author_list:
                author = author.strip()
                if author:
                    if ',' in author:
                        # "Last, First" format
                        parts = author.split(',', 1)
                        last_name = parts[0].strip()
                        first_name = parts[1].strip() if len(parts) > 1 else ""
                    else:
                        # "First Last" format
                        parts = author.split()
                        if len(parts) >= 2:
                            first_name = ' '.join(parts[:-1])
                            last_name = parts[-1]
                        else:
                            first_name = ""
                            last_name = author
                    
                    authors.append({
                        "creatorType": "author",
                        "firstName": first_name,
                        "lastName": last_name
                    })
        
        # Create item data
        item_data = {
            "itemType": item_type,
            "title": paper.get('title', ''),
            "creators": authors,
            "abstractNote": paper.get('abstract', ''),
            "publicationTitle": paper.get('journal', ''),
            "date": str(paper.get('year', '')) if paper.get('year') else '',
            "DOI": paper.get('doi', ''),
            "url": paper.get('url', ''),
            "language": paper.get('lang', ''),
            "extra": f"PMID: {paper.get('pmid', '')}" if paper.get('pmid') else ""
        }
        
        # Add source-specific fields
        source = paper.get('source', '')
        if source:
            if item_data['extra']:
                item_data['extra'] += f"\nSource: {source}"
            else:
                item_data['extra'] = f"Source: {source}"
        
        # Clean empty fields
        item_data = {k: v for k, v in item_data.items() if v}
        
        return item_data
    
    def add_items_to_collection(
        self,
        papers: List[Dict],
        collection_key: str,
        tags: Optional[List[str]] = None
    ) -> Dict:
        """Add papers as items to a Zotero collection.
        
        Args:
            papers: List of paper dictionaries
            collection_key: Zotero collection key
            tags: Optional list of tags to add to items
            
        Returns:
            Dictionary with results (successful, failed, etc.)
        """
        if not self.user_id or not self.api_key or not papers:
            return {"successful": 0, "failed": 0, "errors": []}
        
        logger.info(f"Adding {len(papers)} papers to Zotero collection {collection_key}")
        
        results = {"successful": 0, "failed": 0, "errors": []}
        
        # Process in batches (Zotero API limit is 50 items per request)
        batch_size = 50
        
        for i in range(0, len(papers), batch_size):
            batch_papers = papers[i:i + batch_size]
            
            try:
                # Prepare items for this batch
                items_data = []
                
                for paper in batch_papers:
                    item_data = self.create_item_from_paper(paper)
                    
                    # Add collection
                    item_data["collections"] = [collection_key]
                    
                    # Add tags
                    if tags:
                        item_data["tags"] = [{"tag": tag} for tag in tags]
                    
                    # Add processing metadata as tags
                    processing_tags = [
                        f"imported-{datetime.now().strftime('%Y-%m-%d')}",
                        f"source-{paper.get('source', 'unknown')}"
                    ]
                    
                    if "tags" not in item_data:
                        item_data["tags"] = []
                    
                    for tag in processing_tags:
                        item_data["tags"].append({"tag": tag})
                    
                    items_data.append(item_data)
                
                # Send batch to Zotero
                url = f"{self.base_url}/users/{self.user_id}/items"
                
                response = self.session.post(
                    url,
                    data=json.dumps(items_data),
                    headers={"Content-Type": "application/json"}
                )
                
                time.sleep(1.0 / self.rate_limit)  # Rate limiting
                
                if response.status_code == 200:
                    batch_result = response.json()
                    
                    successful_count = len(batch_result.get("successful", {}))
                    failed_count = len(batch_result.get("failed", {}))
                    
                    results["successful"] += successful_count
                    results["failed"] += failed_count
                    
                    if batch_result.get("failed"):
                        results["errors"].extend(batch_result["failed"].values())
                    
                    logger.info(f"Batch {i//batch_size + 1}: {successful_count} successful, {failed_count} failed")
                
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    results["failed"] += len(batch_papers)
                    results["errors"].append(error_msg)
                    logger.error(f"Error adding batch to Zotero: {error_msg}")
                
            except Exception as e:
                error_msg = f"Error processing batch: {e}"
                results["failed"] += len(batch_papers)
                results["errors"].append(error_msg)
                logger.error(error_msg)
        
        logger.info(f"Zotero import completed: {results['successful']} successful, {results['failed']} failed")
        
        return results
    
    def attach_pdf_to_item(self, item_key: str, pdf_url: str, filename: str) -> bool:
        """Attach PDF to a Zotero item.
        
        Args:
            item_key: Zotero item key
            pdf_url: URL of the PDF
            filename: Filename for the attachment
            
        Returns:
            True if successful, False otherwise
        """
        if not self.user_id or not self.api_key:
            return False
        
        try:
            # Create attachment item
            attachment_data = {
                "itemType": "attachment",
                "linkMode": "imported_url",
                "title": filename,
                "url": pdf_url,
                "parentItem": item_key,
                "contentType": "application/pdf"
            }
            
            url = f"{self.base_url}/users/{self.user_id}/items"
            
            response = self.session.post(
                url,
                data=json.dumps([attachment_data]),
                headers={"Content-Type": "application/json"}
            )
            
            time.sleep(1.0 / self.rate_limit)  # Rate limiting
            
            if response.status_code == 200:
                result = response.json()
                if result.get("successful"):
                    logger.debug(f"PDF attached to item {item_key}")
                    return True
            
            logger.warning(f"Failed to attach PDF to item {item_key}")
            return False
            
        except Exception as e:
            logger.error(f"Error attaching PDF: {e}")
            return False
    
    def push_papers(
        self,
        df: pd.DataFrame,
        collection_name: str,
        tags: Optional[List[str]] = None,
        attach_pdfs: bool = True
    ) -> Dict:
        """Push papers from DataFrame to Zotero.
        
        Args:
            df: DataFrame with papers to push
            collection_name: Name of Zotero collection
            tags: Optional list of tags to add
            attach_pdfs: Whether to attempt PDF attachment
            
        Returns:
            Dictionary with results
        """
        if not self.user_id or not self.api_key:
            logger.error("Zotero credentials not configured")
            return {"successful": 0, "failed": 0, "errors": ["No credentials"]}
        
        if df.empty:
            logger.warning("No papers to push to Zotero")
            return {"successful": 0, "failed": 0, "errors": []}
        
        # Ensure collection exists
        collection_key = self.ensure_collection(collection_name)
        if not collection_key:
            error_msg = f"Failed to create/find collection '{collection_name}'"
            logger.error(error_msg)
            return {"successful": 0, "failed": 0, "errors": [error_msg]}
        
        # Convert DataFrame to list of dictionaries
        papers = df.to_dict('records')
        
        # Add items to collection
        results = self.add_items_to_collection(papers, collection_key, tags)
        
        # Log detailed results
        log_file = config.logs_dir / f"zotero_push_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"Zotero Push Report - {datetime.now()}\n")
            f.write(f"Collection: {collection_name} (key: {collection_key})\n")
            f.write(f"Papers processed: {len(papers)}\n")
            f.write(f"Successful: {results['successful']}\n")
            f.write(f"Failed: {results['failed']}\n")
            
            if results['errors']:
                f.write("\nErrors:\n")
                for error in results['errors']:
                    f.write(f"  - {error}\n")
        
        logger.info(f"Zotero push log saved to {log_file}")
        
        return results


def push_papers_to_zotero(
    df: pd.DataFrame,
    collection_name: str,
    tags: Optional[List[str]] = None
) -> Dict:
    """Convenience function to push papers to Zotero.
    
    Args:
        df: DataFrame with papers to push
        collection_name: Name of Zotero collection
        tags: Optional list of tags to add
        
    Returns:
        Dictionary with results
    """
    client = ZoteroClient()
    return client.push_papers(df, collection_name, tags)


def test_zotero_connection() -> bool:
    """Test Zotero API connection.
    
    Returns:
        True if connection successful, False otherwise
    """
    client = ZoteroClient()
    if not client.user_id or not client.api_key:
        logger.error("Zotero credentials not configured")
        return False
    
    try:
        collections = client.get_collections()
        logger.info(f"Zotero connection successful. Found {len(collections)} collections.")
        return True
    except Exception as e:
        logger.error(f"Zotero connection failed: {e}")
        return False
