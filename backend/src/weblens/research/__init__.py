"""Public research layer.

Provides a pluggable adapter for searching public information about a target domain.
The scan pipeline calls into this layer between collection and analysis. When no provider
is configured, the phase is skipped gracefully and no research findings are produced.

The application MUST NOT pretend research happened when no provider is available.
"""

from weblens.research.base import (
    NullSearchProvider,
    SearchProvider,
    SearchResult,
    SourceType,
    classify_source,
    get_provider,
)

__all__ = [
    "NullSearchProvider",
    "SearchProvider",
    "SearchResult",
    "SourceType",
    "classify_source",
    "get_provider",
]
