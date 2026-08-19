"""Domain enumerations.

``StrEnum`` throughout so the wire format is a readable string rather than an integer that
needs a lookup table on the client.
"""

from __future__ import annotations

from enum import StrEnum


class SectionKey(StrEnum):
    """The eight report sections. Order here is the canonical presentation order."""

    DESIGN = "design"
    TECHNOLOGY = "technology"
    SECURITY = "security"
    PERFORMANCE = "performance"
    ACCESSIBILITY = "accessibility"
    SEO = "seo"
    ARCHITECTURE = "architecture"
    NETWORK = "network"


class FindingStatus(StrEnum):
    """User-facing certainty of a finding.

    The three negative states are deliberately distinct: they answer different questions
    and conflating them is how a tool starts making things up.
    """

    VERIFIED = "verified"
    """Directly observed in collected evidence."""

    INFERRED = "inferred"
    """Derived from indirect or weak signals. The signal is always shown alongside."""

    NOT_DETECTED = "not_detected"
    """Evidence was available and the signal was absent. Not the same as 'not used'."""

    NOT_DETERMINABLE = "not_determinable"
    """Not observable from outside the target, by nature."""

    UNABLE_TO_VERIFY = "unable_to_verify"
    """Required evidence was not collected (stage failed, skipped, or out of budget)."""


class Confidence(StrEnum):
    """Internal reasoning metadata.

    Used only to derive :class:`FindingStatus`. Never rendered next to a claim: a
    percentage or grade beside an uncertain statement reads as authority and launders a
    guess into a fact.
    """

    DEFINITIVE = "definitive"
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class EvidenceKind(StrEnum):
    """What kind of observation an :class:`~weblens.domain.evidence.EvidenceRef` points at."""

    HTTP_HEADER = "http_header"
    HTTP_STATUS = "http_status"
    REDIRECT_HOP = "redirect_hop"
    HTML_ELEMENT = "html_element"
    HTML_ATTRIBUTE = "html_attribute"
    META_TAG = "meta_tag"
    INLINE_SCRIPT = "inline_script"
    SCRIPT_URL = "script_url"
    STYLESHEET_URL = "stylesheet_url"
    RUNTIME_GLOBAL = "runtime_global"
    COMPUTED_STYLE = "computed_style"
    LOADED_FONT = "loaded_font"
    COOKIE = "cookie"
    TLS_CONNECTION = "tls_connection"
    DNS_RECORD = "dns_record"
    ROBOTS_DIRECTIVE = "robots_directive"
    NETWORK_REQUEST = "network_request"
    PERFORMANCE_ENTRY = "performance_entry"
    AXE_RESULT = "axe_result"
    CONSOLE_MESSAGE = "console_message"
    DOM_MEASUREMENT = "dom_measurement"


class EvidenceSlot(StrEnum):
    """Top-level sections of :class:`~weblens.domain.evidence.RawEvidence`.

    Analyzers declare the slots they need; the pipeline can then skip an analyzer with a
    precise reason instead of letting it throw on missing data.
    """

    TARGET = "target"
    HTTP = "http"
    TLS = "tls"
    DNS = "dns"
    ROBOTS = "robots"
    DOM = "dom"
    RUNTIME = "runtime"
    STYLES = "styles"
    NETWORK = "network"
    PERFORMANCE = "performance"
    ACCESSIBILITY = "accessibility"
    VIEWPORTS = "viewports"
    SCREENSHOTS = "screenshots"
    CONSOLE = "console"


class SectionStatus(StrEnum):
    COMPLETE = "complete"
    """Every analyzer for this section ran successfully."""

    PARTIAL = "partial"
    """Some analyzers ran; others failed, timed out, or lacked evidence."""

    UNAVAILABLE = "unavailable"
    """No analyzer could produce output. ``unavailable_reason`` explains why."""

    NOT_IMPLEMENTED = "not_implemented"
    """No analyzer for this section ships in this build yet."""

    SKIPPED = "skipped"
    """Excluded by the scan request."""


class ScanStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL_SCAN_STATUSES


_TERMINAL_SCAN_STATUSES = frozenset(
    {
        ScanStatus.COMPLETED,
        ScanStatus.COMPLETED_WITH_ERRORS,
        ScanStatus.FAILED,
        ScanStatus.CANCELLED,
    }
)


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageKey(StrEnum):
    """Collection and analysis stages, in execution order."""

    VALIDATE = "validate"
    DNS = "dns"
    ROBOTS = "robots"
    HTTP_PROBE = "http_probe"
    TLS = "tls"
    BROWSER_LAUNCH = "browser_launch"
    NAVIGATE = "navigate"
    DOM_CAPTURE = "dom_capture"
    RUNTIME_CAPTURE = "runtime_capture"
    STYLE_CAPTURE = "style_capture"
    PERF_CAPTURE = "perf_capture"
    NETWORK_CAPTURE = "network_capture"
    A11Y_CAPTURE = "a11y_capture"
    RESPONSIVE_PROBE = "responsive_probe"
    SCREENSHOT = "screenshot"
    ANALYZE = "analyze"
    ASSEMBLE = "assemble"


class AnalyzerRunStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    NOT_IMPLEMENTED = "not_implemented"


class ErrorCode(StrEnum):
    """Machine-readable error identity, shared by problem responses and scan errors."""

    INVALID_REQUEST = "INVALID_REQUEST"
    """The request body did not match the schema. Distinct from a URL we can parse but refuse."""

    INVALID_URL = "INVALID_URL"
    BLOCKED_TARGET = "BLOCKED_TARGET"
    ROBOTS_DISALLOWED = "ROBOTS_DISALLOWED"
    DNS_FAILURE = "DNS_FAILURE"
    CONNECT_FAILURE = "CONNECT_FAILURE"
    TLS_FAILURE = "TLS_FAILURE"
    NAVIGATION_TIMEOUT = "NAVIGATION_TIMEOUT"
    BROWSER_UNAVAILABLE = "BROWSER_UNAVAILABLE"
    ACCESS_RESTRICTED = "ACCESS_RESTRICTED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    ANALYZER_FAILED = "ANALYZER_FAILED"
    ANALYZER_TIMEOUT = "ANALYZER_TIMEOUT"
    SCAN_NOT_FOUND = "SCAN_NOT_FOUND"
    RESULT_EXPIRED = "RESULT_EXPIRED"
    SCAN_IN_PROGRESS = "SCAN_IN_PROGRESS"
    RATE_LIMITED = "RATE_LIMITED"
    AI_DISABLED = "AI_DISABLED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class RuleOutcome(StrEnum):
    """Outcome of one security scoring rule."""

    PASS = "pass"  # noqa: S105 - rule outcome, not a credential
    PARTIAL = "partial"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    """Excluded from the score: the rule does not apply to this target."""

    UNKNOWN = "unknown"
    """Excluded from the score: the required observation was not available."""


class SecurityCategory(StrEnum):
    TRANSPORT = "transport"
    HEADERS = "headers"
    COOKIES = "cookies"
    CONTENT_INTEGRITY = "content_integrity"
    EXPOSURE = "exposure"


class PostureBand(StrEnum):
    """Descriptive bands. Never 'secure'/'insecure' - see docs/blueprint/11."""

    STRONG = "strong"
    GOOD = "good"
    MODERATE = "moderate"
    LIMITED = "limited"
    MINIMAL = "minimal"


class DomSource(StrEnum):
    """Where a DOM observation came from.

    Static HTML and the rendered DOM are different objects, and a claim based on one must
    not be presented as if it came from the other.
    """

    STATIC_HTML = "static_html"
    RENDERED_DOM = "rendered_dom"
