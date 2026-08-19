"""Architecture and runtime analysis analyzers."""

from weblens.analyzers.architecture.platform import ArchitecturePlatformAnalyzer
from weblens.analyzers.architecture.rendering import ArchitectureRenderingAnalyzer
from weblens.analyzers.architecture.runtime import ArchitectureRuntimeAnalyzer

__all__ = [
    "ArchitecturePlatformAnalyzer",
    "ArchitectureRenderingAnalyzer",
    "ArchitectureRuntimeAnalyzer",
]
