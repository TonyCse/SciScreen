"""Data normalization module for the Literature Review Pipeline.

This module provides functions to normalize and clean harvested academic works
from different sources into a standardized format.
"""

import logging
import re
import string
from typing import Dict, List, Optional

import pandas as pd
from langdetect import detect, DetectorFactory

from ..config import config

# Set seed for consistent language detection
DetectorFactory.seed = 0

logger = logging.getLogger(__name__)


def clean_title(title: str) -> str:
    """Clean and normalize a title string.
    
    Args:
        title: Raw title string
        
    Returns:
        Cleaned title string
    """
    if not title or pd.isna(title):
        return ""
    
    # Convert to string and strip
    title = str(title).strip()
    
    # Remove HTML tags
    title = re.sub(r'<[^>]+>', '', title)
    
    # Replace multiple whitespace with single space
    title = re.sub(r'\s+', ' ', title)
    
    # Remove leading/trailing punctuation but preserve internal punctuation
    title = title.strip(string.punctuation + string.whitespace)
    
    return title


def normalize_title(title: str) -> str:
    """Normalize title for deduplication comparison.
    
    Args:
        title: Title to normalize
        
    Returns:
        Normalized title for comparison
    """
    if not title or pd.isna(title):
        return ""
    
    # Clean first
    title = clean_title(title)
    
    # Convert to lowercase
    title = title.lower()
    
    # Remove all punctuation except spaces
    title = re.sub(r'[^\w\s]', ' ', title)
    
    # Replace multiple spaces with single space
    title = re.sub(r'\s+', ' ', title)
    
    # Strip whitespace
    title = title.strip()
    
    return title


def clean_authors(authors: str) -> str:
    """Clean and normalize author string.
    
    Args:
        authors: Raw authors string
        
    Returns:
        Cleaned authors string
    """
    if not authors or pd.isna(authors):
        return ""
    
    # Convert to string
    authors = str(authors).strip()
    
    # Remove HTML tags
    authors = re.sub(r'<[^>]+>', '', authors)
    
    # Normalize separators
    authors = re.sub(r'[,;]\s*', '; ', authors)
    
    # Remove multiple spaces
    authors = re.sub(r'\s+', ' ', authors)
    
    # Remove leading/trailing punctuation
    authors = authors.strip(string.punctuation + string.whitespace)
    
    return authors


def parse_authors(authors: str) -> List[str]:
    """Parse authors string into individual author names.
    
    Args:
        authors: Authors string (various formats)
        
    Returns:
        List of individual author names
    """
    if not authors or pd.isna(authors):
        return []
    
    # Clean first
    authors = clean_authors(authors)
    
    # Split on common separators
    author_list = re.split(r'[;,]\s*', authors)
    
    # Clean individual authors
    cleaned_authors = []
    for author in author_list:
        author = author.strip()
        if author:
            cleaned_authors.append(author)
    
    return cleaned_authors


def normalize_authors(authors: str) -> str:
    """Normalize authors into consistent format.
    
    Args:
        authors: Raw authors string
        
    Returns:
        Normalized authors string in "Last, F.; ..." format
    """
    author_list = parse_authors(authors)
    if not author_list:
        return ""
    
    normalized_authors = []
    for author in author_list:
        # Try to parse "First Last" or "Last, First" format
        if ',' in author:
            # Already in "Last, First" format
            normalized_authors.append(author.strip())
        else:
            # Try to convert "First Last" to "Last, First"
            parts = author.strip().split()
            if len(parts) >= 2:
                last_name = parts[-1]
                first_names = ' '.join(parts[:-1])
                # Take only first initial of first names
                initials = ''.join([name[0] + '.' for name in first_names.split() if name])
                normalized_authors.append(f"{last_name}, {initials}")
            else:
                normalized_authors.append(author.strip())
    
    return "; ".join(normalized_authors)


def clean_abstract(abstract: str) -> str:
    """Clean and normalize abstract text.
    
    Args:
        abstract: Raw abstract text
        
    Returns:
        Cleaned abstract text
    """
    if not abstract or pd.isna(abstract):
        return ""
    
    # Convert to string
    abstract = str(abstract).strip()
    
    # Remove HTML tags
    abstract = re.sub(r'<[^>]+>', '', abstract)
    
    # Remove excessive whitespace
    abstract = re.sub(r'\s+', ' ', abstract)
    
    # Remove common abstract prefixes
    prefixes = [
        r'^abstract[:\s]*',
        r'^summary[:\s]*',
        r'^background[:\s]*',
    ]
    for prefix in prefixes:
        abstract = re.sub(prefix, '', abstract, flags=re.IGNORECASE)
    
    return abstract.strip()


def detect_language(text: str) -> str:
    """Detect language of text.
    
    Args:
        text: Text to analyze
        
    Returns:
        ISO 639-1 language code (e.g., 'en', 'fr')
    """
    if not text or pd.isna(text) or len(text.strip()) < 10:
        return ""
    
    try:
        # Use title + abstract for better detection
        detected = detect(text)
        return detected
    except Exception:
        return ""


def normalize_doc_type(doc_type: str, source: str = "") -> str:
    """Normalize document type to standard categories.
    
    Args:
        doc_type: Raw document type
        source: Source of the document (for context)
        
    Returns:
        Normalized document type
    """
    if not doc_type or pd.isna(doc_type):
        return "unknown"
    
    doc_type = str(doc_type).lower().strip()
    
    # Remove source-specific prefixes
    doc_type = re.sub(r'^https?://[^/]+/', '', doc_type)
    
    # Mapping to standard types
    type_mapping = {
        # Journal articles
        'journal-article': 'journal-article',
        'article': 'journal-article',
        'research-article': 'journal-article',
        'original-research': 'journal-article',
        
        # Reviews
        'review': 'review',
        'review-article': 'review',
        'systematic-review': 'review',
        'meta-analysis': 'review',
        'literature-review': 'review',
        
        # Conference papers
        'proceedings-article': 'proceedings-article',
        'conference-paper': 'proceedings-article',
        'conference': 'proceedings-article',
        'inproceedings': 'proceedings-article',
        
        # Books
        'book': 'book',
        'book-chapter': 'book-chapter',
        'chapter': 'book-chapter',
        'incollection': 'book-chapter',
        
        # Preprints
        'preprint': 'preprint',
        'posted-content': 'preprint',
        
        # Other types
        'editorial': 'editorial',
        'letter': 'letter',
        'case-report': 'case-report',
        'thesis': 'thesis',
        'report': 'report',
        'dataset': 'dataset',
    }
    
    # Check for exact matches first
    if doc_type in type_mapping:
        return type_mapping[doc_type]
    
    # Check for partial matches
    for key, value in type_mapping.items():
        if key in doc_type or doc_type in key:
            return value
    
    return "unknown"


def normalize_year(year: any) -> Optional[int]:
    """Normalize year to integer.
    
    Args:
        year: Year value (various formats)
        
    Returns:
        Normalized year as integer, or None if invalid
    """
    if pd.isna(year) or year == "":
        return None
    
    try:
        # Convert to string first
        year_str = str(year).strip()
        
        # Extract first 4-digit number
        match = re.search(r'\b(19|20)\d{2}\b', year_str)
        if match:
            year_int = int(match.group())
            # Validate reasonable range
            if 1900 <= year_int <= 2030:
                return year_int
    except (ValueError, TypeError):
        pass
    
    return None


def clean_url(url: str) -> str:
    """Clean and validate URL.
    
    Args:
        url: Raw URL
        
    Returns:
        Cleaned URL or empty string if invalid
    """
    if not url or pd.isna(url):
        return ""
    
    url = str(url).strip()
    
    # Remove HTML tags
    url = re.sub(r'<[^>]+>', '', url)
    
    # Ensure it looks like a URL
    if not re.match(r'^https?://', url):
        if url.startswith('doi.org/') or url.startswith('www.'):
            url = f"https://{url}"
        elif url.startswith('10.') and '/' in url:  # Looks like a DOI
            url = f"https://doi.org/{url}"
        else:
            return ""
    
    return url


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a DataFrame of harvested works.
    
    Args:
        df: DataFrame with raw harvested data
        
    Returns:
        DataFrame with normalized data
    """
    if df.empty:
        return df
    
    logger.info(f"Normalizing {len(df)} works...")
    
    # Create copy to avoid modifying original
    normalized_df = df.copy()
    
    # Ensure all required columns exist
    required_columns = config.standard_columns
    for col in required_columns:
        if col not in normalized_df.columns:
            normalized_df[col] = ""
    
    # Clean and normalize each field
    if 'title' in normalized_df.columns:
        normalized_df['title'] = normalized_df['title'].apply(clean_title)
        # Add normalized title for deduplication
        normalized_df['title_normalized'] = normalized_df['title'].apply(normalize_title)
    
    if 'authors' in normalized_df.columns:
        normalized_df['authors'] = normalized_df['authors'].apply(normalize_authors)
    
    if 'abstract' in normalized_df.columns:
        normalized_df['abstract'] = normalized_df['abstract'].apply(clean_abstract)
    
    if 'year' in normalized_df.columns:
        normalized_df['year'] = normalized_df['year'].apply(normalize_year)
    
    if 'doc_type' in normalized_df.columns:
        if 'source' in normalized_df.columns:
            normalized_df['doc_type'] = normalized_df.apply(
                lambda row: normalize_doc_type(row['doc_type'], row.get('source', '')), 
                axis=1
            )
        else:
            normalized_df['doc_type'] = normalized_df['doc_type'].apply(normalize_doc_type)
    
    # Clean URLs
    for url_col in ['url', 'pdf_url']:
        if url_col in normalized_df.columns:
            normalized_df[url_col] = normalized_df[url_col].apply(clean_url)
    
    # Clean DOI
    if 'doi' in normalized_df.columns:
        normalized_df['doi'] = normalized_df['doi'].apply(
            lambda x: re.sub(r'^https?://doi\.org/', '', str(x).strip()) if x and not pd.isna(x) else ""
        )
    
    # Detect language if missing
    if 'lang' in normalized_df.columns:
        # Detect language for missing values
        missing_lang = normalized_df['lang'].isin(['', 'unknown', pd.NA]) | normalized_df['lang'].isna()
        
        if missing_lang.any():
            logger.info(f"Detecting language for {missing_lang.sum()} works...")
            
            # Combine title and abstract for language detection
            text_for_detection = normalized_df.loc[missing_lang].apply(
                lambda row: f"{row.get('title', '')} {row.get('abstract', '')}", axis=1
            )
            
            detected_langs = text_for_detection.apply(detect_language)
            normalized_df.loc[missing_lang, 'lang'] = detected_langs
    
    # Fill missing values
    string_columns = ['title', 'abstract', 'authors', 'journal', 'lang', 'url', 'pdf_url', 'oa_status', 'doi', 'pmid', 'id']
    for col in string_columns:
        if col in normalized_df.columns:
            normalized_df[col] = normalized_df[col].fillna("")
    
    # Fill numeric columns
    if 'cited_by' in normalized_df.columns:
        normalized_df['cited_by'] = normalized_df['cited_by'].fillna(0)
    
    # Add processing metadata
    normalized_df['processing_date'] = pd.Timestamp.now()
    
    logger.info(f"Normalization completed for {len(normalized_df)} works")
    
    return normalized_df
