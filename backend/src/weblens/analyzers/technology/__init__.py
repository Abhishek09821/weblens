"""Technology detection analyzers."""

from weblens.analyzers.technology.framework import TechFrameworkAnalyzer
from weblens.analyzers.technology.language import TechLanguageAnalyzer
from weblens.analyzers.technology.stack import TechStackAnalyzer
from weblens.analyzers.technology.styling import TechStylingAnalyzer

__all__ = [
    "TechFrameworkAnalyzer",
    "TechLanguageAnalyzer",
    "TechStackAnalyzer",
    "TechStylingAnalyzer",
]
