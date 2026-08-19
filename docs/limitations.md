# WebLens limitations

Canonical, user-facing list. Rendered in the app under `/about`, embedded in generated reports, and
mirrored by the `limitations[]` fields on results and sections. Every limitation has a stable id so
code can reference it instead of duplicating prose.

| id | Scope | Limitation |
|----|-------|-----------|
| `L-SCOPE-01` | scan | One URL per scan. No crawling: findings describe the analyzed page, not the whole site. |
| `L-SCOPE-02` | scan | A single cold run, one moment in time, one network location, one viewport, one browser (Chromium). Repeat runs will differ. |
| `L-SCOPE-03` | scan | Publicly reachable, unauthenticated content only. Logged-in, paywalled, and geo-restricted states are not analyzed. |
| `L-SCOPE-04` | scan | Passive observation only. WebLens does not submit forms, log in, click consent walls, fuzz inputs, or attempt to bypass access controls. |
| `L-SCOPE-05` | scan | Sites behind bot protection or consent interstitials may serve a challenge page; when detected, affected sections report restricted access rather than describing the interstitial. |
| `L-TECH-01` | technology | Detection requires an observable signal. "Not detected" never means "not used" — server-rendered, self-hosted, or heavily bundled technologies are often invisible externally. |
| `L-TECH-02` | technology | Versions are reported only when a signature captures one explicitly; otherwise the version is "not determinable". |
| `L-TECH-03` | technology | Server-side languages, frameworks, databases, and infrastructure topology are generally not determinable from outside. When a header discloses them, the disclosure itself is the finding. |
| `L-DESIGN-01` | design | Style values come from a capped, deterministic element sample; the sample size and whether the cap was hit are reported with the findings. |
| `L-DESIGN-02` | design | Responsive behaviour is observed by resizing the viewport without reloading, so load-time-only branching may not be exercised. |
| `L-DESIGN-03` | design | Style classifications are interpretations derived from measured values, labelled as interpretations, never presented as facts. |
| `L-DESIGN-04` | design | Only fonts the page actually loaded are reported; local fallbacks and unused `@font-face` declarations are distinguished where observable. |
| `L-SEC-01` | security | Passive and external: observable configuration and headers only. Application logic, dependencies, server-side controls, and data handling are out of scope. |
| `L-SEC-02` | security | The Observable Security Posture score reflects configuration on one page. It cannot establish that a site is secure or insecure, and it is not a compliance rating or a vulnerability assessment. |
| `L-SEC-03` | security | TLS observations describe one negotiated connection from this client, not a full cipher suite or certificate chain audit. |
| `L-SEC-04` | security | Cookie values are never captured; only names and attribute flags are observed. |
| `L-SEC-05` | security | Source-map references are reported as observed references. The `.map` files are not fetched or parsed. |
| `L-SEC-06` | security | Rules that cannot be evaluated are excluded from the score and listed explicitly, so the denominator is auditable. |
| `L-PERF-01` | performance | Lab measurement, not field data. No real-user metrics, no network or CPU throttling by default, and no comparability with Lighthouse scores. |
| `L-PERF-02` | performance | No performance score or grade is produced, by design. |
| `L-PERF-03` | performance | Metrics are captured at a bounded settle point; interaction-dependent metrics (such as INP) are out of scope. |
| `L-PERF-04` | performance | Measured resource sizes reflect what this client received, including CDN and cache behaviour at scan time. |
| `L-A11Y-01` | accessibility | Automated rules detect a subset of WCAG issues. A clean result does not mean a site is accessible; conformance requires manual testing with assistive technologies and expert review. |
| `L-A11Y-02` | accessibility | Only the initial rendered state is evaluated. Modals, menus, and form-error states are not exercised. |
| `L-A11Y-03` | accessibility | No accessibility score is produced. Violation counts are not a conformance measure. |
| `L-SEO-01` | seo | Metadata and indexability are read as served. Search engine treatment, rankings, and index status are not observable and are not claimed. |
| `L-SEO-02` | seo | Structured data is checked for syntactic validity and type inventory, not for eligibility for any specific search feature. |
| `L-ARCH-01` | architecture | Rendering strategy is inferred from the delta between served HTML and rendered DOM plus hydration signals. Distinguishing SSR from SSG is often impossible externally and is reported as not determinable. |
| `L-ARCH-02` | architecture | Hosting, CDN, and edge indicators come from headers and DNS observations, which can be proxied, cached, or absent. |
| `L-NET-01` | network | The request ledger covers requests observed during one navigation and bounded settle window, capped at a documented request count. |
| `L-STORE-01` | persistence | Scans are stored in this browser profile only. They are not synced or shared, and deletion is permanent — no server copy exists. |
| `L-AI-01` | ai | AI explanations, when enabled, are a presentation layer over verified findings. They never create findings, and statements that cannot be traced to a finding are dropped and reported. |
