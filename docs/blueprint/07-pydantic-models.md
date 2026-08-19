# 7. Pydantic models (backend domain)

Pydantic v2. All models are `frozen=True` where they represent observations (evidence, findings) so
an analyzer cannot mutate shared state. `extra="forbid"` everywhere: an unexpected key is a bug.

These listings are the specification; `backend/src/weblens/domain/` implements them verbatim.

## Enums (`domain/enums.py`)

```python
class SectionKey(StrEnum):
    DESIGN = "design"; TECHNOLOGY = "technology"; SECURITY = "security"
    PERFORMANCE = "performance"; ACCESSIBILITY = "accessibility"; SEO = "seo"
    ARCHITECTURE = "architecture"; NETWORK = "network"

class FindingStatus(StrEnum):
    VERIFIED = "verified"                    # directly observed in evidence
    INFERRED = "inferred"                    # derived from weaker/indirect signals
    NOT_DETECTED = "not_detected"            # evidence available, signal absent
    NOT_DETERMINABLE = "not_determinable"    # not observable from outside, by nature
    UNABLE_TO_VERIFY = "unable_to_verify"    # required evidence was not collected

class Confidence(StrEnum):                   # INTERNAL reasoning metadata only (A5)
    DEFINITIVE = "definitive"; STRONG = "strong"; MODERATE = "moderate"; WEAK = "weak"

class EvidenceKind(StrEnum):
    HTTP_HEADER = "http_header"; HTTP_STATUS = "http_status"; REDIRECT_HOP = "redirect_hop"
    HTML_ELEMENT = "html_element"; HTML_ATTRIBUTE = "html_attribute"; META_TAG = "meta_tag"
    INLINE_SCRIPT = "inline_script"; SCRIPT_URL = "script_url"; STYLESHEET_URL = "stylesheet_url"
    RUNTIME_GLOBAL = "runtime_global"; COMPUTED_STYLE = "computed_style"; LOADED_FONT = "loaded_font"
    COOKIE = "cookie"; TLS_CONNECTION = "tls_connection"; DNS_RECORD = "dns_record"
    ROBOTS_DIRECTIVE = "robots_directive"; NETWORK_REQUEST = "network_request"
    PERFORMANCE_ENTRY = "performance_entry"; AXE_RESULT = "axe_result"
    CONSOLE_MESSAGE = "console_message"; DOM_MEASUREMENT = "dom_measurement"

class EvidenceSlot(StrEnum):                 # declared analyzer dependencies
    TARGET = "target"; HTTP = "http"; TLS = "tls"; DNS = "dns"; ROBOTS = "robots"
    DOM = "dom"; RUNTIME = "runtime"; STYLES = "styles"; NETWORK = "network"
    PERFORMANCE = "performance"; ACCESSIBILITY = "accessibility"; VIEWPORTS = "viewports"
    SCREENSHOTS = "screenshots"; CONSOLE = "console"

class SectionStatus(StrEnum):
    COMPLETE = "complete"; PARTIAL = "partial"; UNAVAILABLE = "unavailable"
    NOT_IMPLEMENTED = "not_implemented"; SKIPPED = "skipped"

class ScanStatus(StrEnum):
    QUEUED = "queued"; RUNNING = "running"; COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"; FAILED = "failed"; CANCELLED = "cancelled"

class StageStatus(StrEnum):
    PENDING = "pending"; RUNNING = "running"; COMPLETED = "completed"
    FAILED = "failed"; SKIPPED = "skipped"

class StageKey(StrEnum):
    VALIDATE = "validate"; DNS = "dns"; ROBOTS = "robots"; HTTP_PROBE = "http_probe"
    TLS = "tls"; BROWSER_LAUNCH = "browser_launch"; NAVIGATE = "navigate"
    DOM_CAPTURE = "dom_capture"; RUNTIME_CAPTURE = "runtime_capture"
    STYLE_CAPTURE = "style_capture"; PERF_CAPTURE = "perf_capture"
    NETWORK_CAPTURE = "network_capture"; A11Y_CAPTURE = "a11y_capture"
    RESPONSIVE_PROBE = "responsive_probe"; SCREENSHOT = "screenshot"
    ANALYZE = "analyze"; ASSEMBLE = "assemble"

class ErrorCode(StrEnum):
    INVALID_URL; BLOCKED_TARGET; ROBOTS_DISALLOWED; DNS_FAILURE; CONNECT_FAILURE
    TLS_FAILURE; NAVIGATION_TIMEOUT; BROWSER_UNAVAILABLE; ACCESS_RESTRICTED
    BUDGET_EXHAUSTED; MISSING_EVIDENCE; ANALYZER_FAILED; ANALYZER_TIMEOUT
    SCAN_NOT_FOUND; RESULT_EXPIRED; SCAN_IN_PROGRESS; RATE_LIMITED
    AI_DISABLED; INTERNAL_ERROR                      # (values are the lowercase-free names)
```

## Evidence references (`domain/evidence.py`)

```python
MAX_EXCERPT_CHARS = 400

class EvidenceRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: EvidenceKind
    source: str                      # machine path, e.g. "http.final.headers.content-security-policy"
    excerpt: str | None = None       # sanitized + truncated raw value
    location: str | None = None      # absolute URL / CSS selector / header name
    detail: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("excerpt")
    def _truncate(cls, v): ...        # hard-truncates to MAX_EXCERPT_CHARS with an ellipsis marker
```

`EvidenceRef` is intentionally *not* a pointer into a separate evidence store: findings are consumed
standalone in reports and in IndexedDB, so each carries its own quotable excerpt. `RawEvidence`
itself is not returned by the API (too large, and it can contain page content); only these bounded,
sanitized excerpts are.

## Findings (`domain/findings.py`)

```python
FindingValue = str | int | float | bool | None

class Finding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str                          # "<analyzer_id>:<slug>", unique within a result
    category: str                    # grouping within a section, e.g. "response_headers"
    name: str                        # human label, e.g. "Content-Security-Policy"
    status: FindingStatus
    detected: bool | None            # None when the notion of detection does not apply
    value: FindingValue = None
    values: list[str] = Field(default_factory=list)
    unit: str | None = None          # "ms", "bytes", "px", "%" — no unit-less magic numbers
    confidence: Confidence | None = None     # internal metadata (A5)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    source: str                      # analyzer id that produced this finding
    details: dict[str, JsonValue] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    reason: str | None = None        # REQUIRED for not_detected/not_determinable/unable_to_verify

    @model_validator(mode="after")
    def _enforce_provenance(self):
        if self.status in (FindingStatus.VERIFIED, FindingStatus.INFERRED) and not self.evidence:
            raise ValueError(f"{self.id}: {self.status} finding must carry evidence")
        if self.status in (FindingStatus.NOT_DETECTED, FindingStatus.NOT_DETERMINABLE,
                           FindingStatus.UNABLE_TO_VERIFY) and not self.reason:
            raise ValueError(f"{self.id}: negative finding must state a reason")
        return self
```

That validator is axiom A2 turned into a runtime invariant: a "verified" claim without evidence
cannot be constructed, so it cannot reach the UI. Unit tests assert the validator fires.

```python
class Interpretation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    statement: str                   # subjective, e.g. "dark, gradient-forward SaaS visual language"
    basis: list[str]                 # finding ids, min_length=1 (enforced)
    source: str                      # analyzer id
    caveat: str = "Interpretation derived from observed values, not a directly observed fact."
```

## Section payloads (`domain/sections.py`)

```python
class AnalyzerRun(BaseModel):
    id: str; version: str
    status: Literal["completed", "failed", "skipped", "timeout", "not_implemented"]
    duration_ms: float | None = None
    error_code: ErrorCode | None = None
    error_detail: str | None = None

class SectionMeta(BaseModel):
    key: SectionKey
    status: SectionStatus
    analyzers: list[AnalyzerRun] = []
    limitations: list[str] = []
    unavailable_reason: str | None = None      # required when status != complete/partial

class Section(BaseModel, Generic[TPayload]):
    meta: SectionMeta
    findings: list[Finding] = []
    interpretations: list[Interpretation] = []
    data: TPayload | None = None
```

Typed payloads carry the structured extras that would be awkward as flat findings — always
*alongside* findings, never instead of them:

| Payload | Notable fields |
|---------|----------------|
| `DesignPayload` | `palette: list[ColorObservation]`, `typography: TypographyObservation`, `spacing_scale: list[ScaleEntry]`, `radius_scale`, `shadows`, `layout: LayoutObservation`, `responsive: list[ViewportMetrics]`, `media: MediaInventory`, `sample_coverage: SampleCoverage` |
| `TechnologyPayload` | `products: list[DetectedProduct]` (name, categories, version, status, signals) |
| `SecurityPayload` | `score: SecurityScore \| None`, `headers: list[HeaderObservation]`, `cookies: list[CookieObservation]`, `tls: TlsObservation \| None`, `mixed_content: MixedContentReport` |
| `PerformancePayload` | `timings: TimingMetrics`, `resource_summary: ResourceSummary`, `run_context: RunContext` |
| `AccessibilityPayload` | `violations: list[AxeViolation]`, `rule_engine: EngineInfo \| None`, `structure: StructureObservation`, `coverage_note: str` |
| `SeoPayload` | `metadata: MetadataObservation`, `indexability: IndexabilityObservation`, `structured_data: list[StructuredDataBlock]` |
| `ArchitecturePayload` | `rendering: RenderingObservation`, `platform_indicators: list[PlatformIndicator]`, `runtime: RuntimeObservation` |
| `NetworkPayload` | `requests: list[NetworkRequestRecord]`, `by_domain: list[DomainSummary]`, `protocol_mix`, `totals: TransferTotals` |

```python
class SectionSet(BaseModel):          # explicit fields, not dict[str, Section] (typed both sides)
    design: Section[DesignPayload]
    technology: Section[TechnologyPayload]
    security: Section[SecurityPayload]
    performance: Section[PerformancePayload]
    accessibility: Section[AccessibilityPayload]
    seo: Section[SeoPayload]
    architecture: Section[ArchitecturePayload]
    network: Section[NetworkPayload]
```

## Security score (`domain/security.py`)

```python
class RuleOutcome(StrEnum):
    PASS = "pass"; PARTIAL = "partial"; FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"; UNKNOWN = "unknown"

class SecurityRuleResult(BaseModel):
    id: str; title: str; category: SecurityCategory
    outcome: RuleOutcome
    weight: float                      # max points when applicable
    awarded: float                     # 0..weight
    rationale: str                     # why this outcome, in observable terms
    evidence: list[EvidenceRef] = []
    recommendation: str | None = None
    reference: str | None = None       # spec/doc URL

class SecurityScore(BaseModel):
    methodology_version: str
    points_awarded: float
    points_applicable: float           # excludes not_applicable/unknown rules
    percentage: float                  # round(awarded/applicable*100, 1); 0 when applicable == 0
    band: PostureBand                  # strong|good|moderate|limited|minimal
    label: str = "Observable Security Posture"
    disclaimer: str                    # fixed text, see doc 11
    rules: list[SecurityRuleResult]
    excluded_rules: list[ExcludedRule] # id + reason, so the denominator is auditable
```

## Scan-level models (`domain/scan.py`)

```python
class ScanOptions(BaseModel):
    include_screenshot: bool = True
    include_full_page_screenshot: bool = False
    viewport: Viewport = Viewport(width=1440, height=900)
    responsive_widths: list[int] = [390, 768, 1440]
    sections: list[SectionKey] | None = None

class ScanRequest(BaseModel):
    url: str                           # validated by collection/target.py, not by AnyUrl alone
    options: ScanOptions = ScanOptions()

class RedirectHop(BaseModel):
    url: str; status: int; location: str | None; scheme: str

class TargetInfo(BaseModel):
    requested_url: str; normalized_url: str; final_url: str | None
    host: str; port: int; scheme: str
    resolved_ips: list[str] = []
    redirect_chain: list[RedirectHop] = []
    http_status: int | None = None
    document_title: str | None = None
    robots: RobotsInfo | None = None

class RunContext(BaseModel):            # makes measurements interpretable
    browser_name: str | None; browser_version: str | None
    user_agent: str; viewport: Viewport; device_scale_factor: float
    wait_strategy: str; settle_reached: bool
    network_throttling: str = "none"; cpu_throttling: str = "none"
    locale: str = "en-US"; timezone: str = "UTC"

class StageRun(BaseModel):
    key: StageKey; label: str; status: StageStatus
    started_at: datetime | None; duration_ms: float | None
    error_code: ErrorCode | None = None; error_detail: str | None = None
    skip_reason: str | None = None

class ScanError(BaseModel):
    code: ErrorCode; scope: Literal["scan", "stage", "analyzer"]
    subject: str                        # stage key or analyzer id
    message: str; detail: str | None = None; occurred_at: datetime

class ScanMetadata(BaseModel):
    scan_id: str; status: ScanStatus
    created_at: datetime; started_at: datetime | None; finished_at: datetime | None
    duration_ms: float | None
    engine_version: str; schema_version: str
    options: ScanOptions; run_context: RunContext | None
    stages: list[StageRun]

class AnalysisResult(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    scan: ScanMetadata
    target: TargetInfo
    sections: SectionSet
    errors: list[ScanError] = []
    screenshots: list[ScreenshotRef] = []   # data URLs or omitted; see doc 9 for storage split
    limitations: list[str] = []             # scan-wide caveats
```

## Job/progress models (transport only)

```python
class StageProgress(BaseModel):
    current_stage: StageKey | None; current_stage_label: str | None
    completed_weight: int; total_weight: int
    stages_completed: int; stages_total: int

class ScanJobState(BaseModel):
    scan_id: str; status: ScanStatus
    created_at: datetime; started_at: datetime | None; finished_at: datetime | None
    progress: StageProgress
    stages: list[StageRun]
    problem: ProblemDetail | None = None

class ScanAcceptedResponse(BaseModel):
    scan_id: str; status: ScanStatus; requested_url: str; normalized_url: str
    created_at: datetime; links: dict[str, str]
```

## RawEvidence (internal, `domain/evidence.py`)

`RawEvidence` is a Pydantic model too — not because it crosses the API boundary (it does not), but so
it can be dumped to JSON and committed as a test fixture. That single decision is what makes the
analyzer test strategy in doc 12 possible.

The observation models it is composed of live in `domain/observations/` (`transport.py`, `page.py`,
`measurement.py`) rather than one file, so each stays reviewable.

```python
class RawEvidence(BaseModel):
    collected_at: datetime
    target: TargetObservation
    http: HttpObservation | None = None
    tls: TlsObservation | None = None
    dns: DnsObservation | None = None
    robots: RobotsObservation | None = None
    dom: DomObservation | None = None
    runtime: RuntimeObservation | None = None
    styles: StyleObservation | None = None
    network: NetworkObservation | None = None
    performance: PerformanceObservation | None = None
    accessibility: AxeObservation | None = None
    viewports: list[ViewportMetrics] | None = None
    console: list[ConsoleMessage] | None = None
    screenshots: list[ScreenshotArtifact] | None = None

    def has(self, slot: EvidenceSlot) -> bool: ...
    def missing(self, slots: Iterable[EvidenceSlot]) -> list[EvidenceSlot]: ...
```

Note that the list-valued slots are `list[...] | None`, not `list[...]`. The same distinction as
everywhere else applies: `None` means the stage did not run, `[]` means it ran and found nothing.

Stage outcomes are **not** on `RawEvidence`. They are pipeline metadata rather than observations
about the target, and they live on `ScanMetadata.stages`, which keeps evidence fixtures free of
run-specific timings that would otherwise churn on every capture.

`DomObservation` carries a `source` field (`static_html` or `rendered_dom`). Phase 0 fills the DOM
slot by parsing the served HTML; Phase 1 fills it from the rendered page. Analyzers branch on
`source` so a conclusion drawn from served HTML is never presented as an observation of the rendered
page.

`None` on a slot means "not collected" and is distinguishable from an empty collection ("collected,
nothing found"). Analyzers must branch on that difference: the first yields `unable_to_verify`, the
second `not_detected`. Conflating them is the single most common way a tool like this starts lying.
