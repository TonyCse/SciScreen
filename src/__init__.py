"""Literature Review Pipeline - Main Package.

A comprehensive tool for automated literature review workflows including:
- Multi-source paper harvesting (OpenAlex, Crossref, PubMed)
- Automated deduplication and filtering
- AI-powered screening and scoring
- Zotero integration
- PRISMA flow diagram generation
"""

__version__ = "0.1.0"
__author__ = "Literature Review Pipeline Team"
__email__ = "contact@example.com"

# Import main modules for convenience
from . import config, utils_io
from .harvest import crossref, openalex, pubmed, unpaywall
from .pipeline import deduplicate, enrich, filter_rules, normalize, prisma, report, scoring
from .zotero import zotero_client

__all__ = [
    "config",
    "utils_io", 
    "openalex",
    "crossref",
    "pubmed",
    "unpaywall",
    "normalize",
    "deduplicate",
    "filter_rules",
    "enrich",
    "scoring",
    "prisma",
    "report",
    "zotero_client",
]
