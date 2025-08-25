"""Configuration management for the Literature Review Pipeline.

This module handles all configuration settings including:
- Environment variables loading
- API credentials and endpoints
- Processing parameters
- Output settings
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

try:
    from dotenv import load_dotenv
    # Load environment variables from .env file
    load_dotenv()
except ImportError:
    # python-dotenv not available, continue without it
    def load_dotenv():
        pass
    load_dotenv()


class Config:
    """Central configuration class for the literature review pipeline."""
    
    def __init__(self):
        """Initialize configuration with environment variables and defaults."""
        # Project paths
        self.project_root = Path(__file__).parent.parent
        self.data_dir = self.project_root / "data"
        self.models_dir = self.project_root / "models"
        self.outputs_dir = self.data_dir / "outputs"
        self.logs_dir = self.data_dir / "logs"
        
        # Ensure directories exist
        for dir_path in [self.data_dir, self.models_dir, self.outputs_dir, self.logs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # API Configuration
        self.openalex_base = os.getenv("OPENALEX_BASE", "https://api.openalex.org")
        self.unpaywall_email = os.getenv("UNPAYWALL_EMAIL", "")
        self.zotero_user_id = os.getenv("ZOTERO_USER_ID", "")
        self.zotero_api_key = os.getenv("ZOTERO_API_KEY", "")
        self.pubmed_email = os.getenv("PUBMED_EMAIL", "")
        self.crossref_mailto = os.getenv("CROSSREF_MAILTO", "")
        
        # Search Parameters
        self.query = os.getenv("QUERY", "cognitive behavioral therapy AND depression")
        self.year_from = int(os.getenv("YEAR_FROM", "2015"))
        self.year_to = int(os.getenv("YEAR_TO", "2025"))
        self.langs = os.getenv("LANGS", "en,fr").split(",")
        self.allow_preprints = os.getenv("ALLOW_PREPRINTS", "false").lower() == "true"
        self.project_name = os.getenv("PROJECT_NAME", "My Literature Review")
        self.zotero_collection = os.getenv("ZOTERO_COLLECTION", "Literature Review Collection")
        self.top_n = int(os.getenv("TOP_N", "2000"))
        
        # Processing Configuration
        self.max_workers = int(os.getenv("MAX_WORKERS", "4"))
        self.batch_size = int(os.getenv("BATCH_SIZE", "100"))
        self.rate_limit_delay = float(os.getenv("RATE_LIMIT_DELAY", "1.0"))
        
        # Deduplication Settings
        self.title_similarity_threshold = float(os.getenv("TITLE_SIMILARITY_THRESHOLD", "0.85"))
        self.levenshtein_threshold = int(os.getenv("LEVENSHTEIN_THRESHOLD", "3"))
        self.year_tolerance = int(os.getenv("YEAR_TOLERANCE", "1"))
        
        # Scoring Model
        self.model_path = self.models_dir / os.getenv("MODEL_PATH", "screening_model.joblib")
        self.confidence_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
        
        # Output Settings
        self.output_format = os.getenv("OUTPUT_FORMAT", "xlsx")
        self.include_abstracts = os.getenv("INCLUDE_ABSTRACTS", "true").lower() == "true"
        self.include_fulltext = os.getenv("INCLUDE_FULLTEXT", "false").lower() == "true"
        
        # Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_format = os.getenv("LOG_FORMAT", "json")
        
        # R Integration
        self.r_enabled = os.getenv("R_ENABLED", "false").lower() == "true"
        self.renv_restore = os.getenv("RENV_RESTORE", "false").lower() == "true"
        
        # API Rate Limits (requests per second)
        self.rate_limits = {
            "openalex": 10,
            "crossref": 50,
            "pubmed": 3,
            "unpaywall": 100,
            "zotero": 1,
        }
        
        # Default columns for output files
        self.standard_columns = [
            "source", "id", "doi", "pmid", "title", "abstract", "authors", 
            "journal", "year", "doc_type", "lang", "url", "pdf_url", 
            "oa_status", "cited_by"
        ]
        
        # Screening columns for Excel output
        self.screening_columns = [
            "include", "title", "abstract", "year", "journal", "authors", 
            "doi", "source", "ai_label", "confidence", "reason", "doc_type", 
            "lang", "url", "pdf_url", "oa_status"
        ]
    
    def validate_api_credentials(self) -> Dict[str, bool]:
        """Validate that required API credentials are present."""
        credentials = {
            "unpaywall_email": bool(self.unpaywall_email),
            "zotero_user_id": bool(self.zotero_user_id),
            "zotero_api_key": bool(self.zotero_api_key),
            "pubmed_email": bool(self.pubmed_email),
            "crossref_mailto": bool(self.crossref_mailto),
        }
        return credentials
    
    def get_missing_credentials(self) -> List[str]:
        """Get list of missing required credentials."""
        credentials = self.validate_api_credentials()
        return [key for key, valid in credentials.items() if not valid]
    
    def setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logger = logging.getLogger("lit_review_pipeline")
        logger.setLevel(getattr(logging, self.log_level.upper()))
        
        if not logger.handlers:
            # Create file handler
            log_file = self.logs_dir / "pipeline.log"
            file_handler = logging.FileHandler(log_file)
            
            # Create console handler
            console_handler = logging.StreamHandler()
            
            # Create formatter
            if self.log_format.lower() == "json":
                formatter = logging.Formatter(
                    '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                    '"module": "%(name)s", "message": "%(message)s"}'
                )
            else:
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
        
        return logger


# Global configuration instance
config = Config()
