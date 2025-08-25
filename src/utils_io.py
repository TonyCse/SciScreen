"""Input/Output utilities for the Literature Review Pipeline.

This module provides common utilities for:
- File operations (reading/writing JSON, CSV, Excel)
- Data serialization and deserialization
- Logging helpers
- HTTP request utilities with retry logic
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import config


def setup_session(
    max_retries: int = 3,
    backoff_factor: float = 1.0,
    status_forcelist: Optional[List[int]] = None,
) -> requests.Session:
    """Create a requests session with retry strategy.
    
    Args:
        max_retries: Maximum number of retries
        backoff_factor: Backoff factor for exponential backoff
        status_forcelist: List of HTTP status codes to retry on
        
    Returns:
        Configured requests Session
    """
    if status_forcelist is None:
        status_forcelist = [429, 500, 502, 503, 504]
    
    session = requests.Session()
    
    retry_strategy = Retry(
        total=max_retries,
        read=max_retries,
        connect=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def rate_limited_request(
    session: requests.Session,
    url: str,
    delay: float = 1.0,
    **kwargs
) -> requests.Response:
    """Make a rate-limited HTTP request.
    
    Args:
        session: Requests session to use
        url: URL to request
        delay: Delay in seconds between requests
        **kwargs: Additional arguments for requests
        
    Returns:
        Response object
        
    Raises:
        requests.RequestException: If request fails after retries
    """
    time.sleep(delay)
    response = session.get(url, **kwargs)
    response.raise_for_status()
    return response


def save_jsonl(data: List[Dict[str, Any]], filepath: Path, append: bool = False) -> None:
    """Save data as JSON Lines format.
    
    Args:
        data: List of dictionaries to save
        filepath: Path to output file
        append: Whether to append to existing file
    """
    mode = "a" if append else "w"
    with open(filepath, mode, encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def load_jsonl(filepath: Path) -> List[Dict[str, Any]]:
    """Load data from JSON Lines format.
    
    Args:
        filepath: Path to input file
        
    Returns:
        List of dictionaries
    """
    data = []
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data.append(json.loads(line))
    return data


def save_dataframe(
    df: pd.DataFrame,
    filepath: Path,
    format_type: Optional[str] = None,
    **kwargs
) -> None:
    """Save DataFrame in various formats.
    
    Args:
        df: DataFrame to save
        filepath: Output file path
        format_type: File format ('csv', 'xlsx', 'json'). If None, infer from extension
        **kwargs: Additional arguments for pandas save methods
    """
    if format_type is None:
        format_type = filepath.suffix.lower()[1:]  # Remove the dot
    
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    if format_type == "csv":
        df.to_csv(filepath, index=False, **kwargs)
    elif format_type == "xlsx":
        df.to_excel(filepath, index=False, **kwargs)
    elif format_type == "json":
        df.to_json(filepath, orient="records", **kwargs)
    else:
        raise ValueError(f"Unsupported format: {format_type}")


def load_dataframe(
    filepath: Path,
    format_type: Optional[str] = None,
    **kwargs
) -> pd.DataFrame:
    """Load DataFrame from various formats.
    
    Args:
        filepath: Input file path
        format_type: File format ('csv', 'xlsx', 'json'). If None, infer from extension
        **kwargs: Additional arguments for pandas load methods
        
    Returns:
        Loaded DataFrame
    """
    if not filepath.exists():
        return pd.DataFrame()
    
    if format_type is None:
        format_type = filepath.suffix.lower()[1:]  # Remove the dot
    
    if format_type == "csv":
        return pd.read_csv(filepath, **kwargs)
    elif format_type == "xlsx":
        return pd.read_excel(filepath, **kwargs)
    elif format_type == "json":
        return pd.read_json(filepath, **kwargs)
    else:
        raise ValueError(f"Unsupported format: {format_type}")


def log_api_call(
    logger: logging.Logger,
    api_name: str,
    endpoint: str,
    params: Dict[str, Any],
    response_info: Dict[str, Any]
) -> None:
    """Log API call information.
    
    Args:
        logger: Logger instance
        api_name: Name of the API
        endpoint: API endpoint
        params: Request parameters
        response_info: Response information (status, count, etc.)
    """
    log_data = {
        "api": api_name,
        "endpoint": endpoint,
        "params": params,
        "response": response_info,
        "timestamp": time.time()
    }
    
    if config.log_format.lower() == "json":
        logger.info(json.dumps(log_data))
    else:
        logger.info(
            f"API Call - {api_name}: {endpoint} "
            f"(params: {params}, response: {response_info})"
        )


def ensure_dir(path: Union[str, Path]) -> Path:
    """Ensure directory exists, create if not.
    
    Args:
        path: Directory path
        
    Returns:
        Path object
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_timestamp() -> str:
    """Get current timestamp string for filenames.
    
    Returns:
        Timestamp in YYYYMMDD_HHMMSS format
    """
    return time.strftime("%Y%m%d_%H%M%S")


def clean_filename(filename: str) -> str:
    """Clean filename by removing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Cleaned filename
    """
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")
    return filename.strip()


def merge_dataframes(
    dataframes: List[pd.DataFrame],
    source_names: Optional[List[str]] = None
) -> pd.DataFrame:
    """Merge multiple DataFrames with source tracking.
    
    Args:
        dataframes: List of DataFrames to merge
        source_names: Optional list of source names to add to each DataFrame
        
    Returns:
        Merged DataFrame
    """
    if not dataframes:
        return pd.DataFrame()
    
    if source_names and len(source_names) == len(dataframes):
        for df, source in zip(dataframes, source_names):
            if not df.empty and "source" not in df.columns:
                df["source"] = source
    
    # Ensure all DataFrames have the same columns
    all_columns = set()
    for df in dataframes:
        all_columns.update(df.columns)
    
    standardized_dfs = []
    for df in dataframes:
        if df.empty:
            continue
        # Add missing columns with NaN values
        for col in all_columns:
            if col not in df.columns:
                df[col] = pd.NA
        standardized_dfs.append(df)
    
    if not standardized_dfs:
        return pd.DataFrame()
    
    return pd.concat(standardized_dfs, ignore_index=True)
