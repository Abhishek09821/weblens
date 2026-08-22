"""Version constants.

Two independent versions travel with every result:

``ENGINE_VERSION``
    The detection logic version. Two scans of the same site are only meaningfully
    comparable when this matches.

``SCHEMA_VERSION``
    The shape of :class:`weblens.domain.scan.AnalysisResult`. IndexedDB migrations on
    the client key off this value, so it must change whenever the payload shape changes
    in a non-additive way.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version

SCHEMA_VERSION = "2.0"

try:  # installed package (the normal case)
    ENGINE_VERSION = _package_version("weblens")
except PackageNotFoundError:  # running from a source tree without installation
    ENGINE_VERSION = "0.1.0"

USER_AGENT = (
    f"WebLens/{ENGINE_VERSION} (+https://github.com/weblens; passive website analyzer; "
    "respects robots.txt)"
)
