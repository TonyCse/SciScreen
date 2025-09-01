"""Top level package for the Literature Review Pipeline.

This module used to eagerly import a large number of submodules so that they
were available as top level attributes of :mod:`src`.  Many of those imports
pull in optional third party dependencies (for example ``xmltodict`` for the
PubMed harvester).  Importing :mod:`src` would therefore fail on systems where
those heavy dependencies were not installed, even if the caller only needed a
small subset of the functionality such as the lightweight pipeline utilities.

To make the package more robust and to keep import times low we avoid importing
subpackages at module import time.  Submodules can still be accessed using the
standard package notation (e.g. ``from src.pipeline import deduplicate``) and
they will be imported lazily when first accessed.
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Dict

__version__ = "0.1.0"
__author__ = "Literature Review Pipeline Team"
__email__ = "contact@example.com"

# -- Lazy loading -----------------------------------------------------------

_LAZY_MODULES: Dict[str, str] = {
    "config": "src.config",
    "utils_io": "src.utils_io",
    "openalex": "src.harvest.openalex",
    "crossref": "src.harvest.crossref",
    "pubmed": "src.harvest.pubmed",
    "unpaywall": "src.harvest.unpaywall",
    "normalize": "src.pipeline.normalize",
    "deduplicate": "src.pipeline.deduplicate",
    "filter_rules": "src.pipeline.filter_rules",
    "enrich": "src.pipeline.enrich",
    "scoring": "src.pipeline.scoring",
    "prisma": "src.pipeline.prisma",
    "report": "src.pipeline.report",
    "zotero_client": "src.zotero.zotero_client",
}


def __getattr__(name: str) -> ModuleType:
    """Dynamically import optional submodules.

    This hook is triggered the first time an attribute defined in
    ``_LAZY_MODULES`` is accessed.  It allows ``import src`` to succeed even if
    some optional dependencies required by the submodules are missing.  The
    submodule will only be imported when explicitly requested.
    """

    if name in _LAZY_MODULES:
        module = import_module(_LAZY_MODULES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = sorted(_LAZY_MODULES)

