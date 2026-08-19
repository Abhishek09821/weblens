"""Design analysis analyzers."""

from weblens.analyzers.design.color import DesignColorAnalyzer
from weblens.analyzers.design.layout import DesignLayoutAnalyzer
from weblens.analyzers.design.media import DesignMediaAnalyzer
from weblens.analyzers.design.motion import DesignMotionAnalyzer
from weblens.analyzers.design.typography import DesignTypographyAnalyzer

__all__ = [
    "DesignColorAnalyzer",
    "DesignLayoutAnalyzer",
    "DesignMediaAnalyzer",
    "DesignMotionAnalyzer",
    "DesignTypographyAnalyzer",
]
