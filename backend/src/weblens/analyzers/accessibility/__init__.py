"""Accessibility analysis analyzers."""

from weblens.analyzers.accessibility.axe import AccessibilityAxeAnalyzer
from weblens.analyzers.accessibility.structure import AccessibilityStructureAnalyzer

__all__ = ["AccessibilityAxeAnalyzer", "AccessibilityStructureAnalyzer"]
