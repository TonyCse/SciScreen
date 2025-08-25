"""Literature Review Pipeline - Harvesting Module.

This module contains all the harvesting functionality for different academic databases:
- OpenAlex: Open database of scholarly works
- Crossref: DOI registration agency with metadata
- PubMed: Biomedical literature database
- Unpaywall: Open access article finder
"""

from . import crossref, openalex, pubmed, unpaywall

__all__ = ["openalex", "crossref", "pubmed", "unpaywall"]
