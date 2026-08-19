# 11. Security scoring methodology

`methodology_version: 1.0`. Implemented in `backend/src/weblens/analyzers/security/rules.py` (rule
table) and `scoring.py` (aggregation). This document and that code must stay in step; a test asserts
the rule ids, weights, and category totals declared here match the code.

## What the score is and is not

The score is labelled **Observable Security Posture** everywhere it appears.

- It measures **presence and quality of publicly observable, defensive configuration** on one page,
  from outside, at one point in time.
- It is **not** a vulnerability assessment, a penetration test, a compliance rating, or a statement
  about the application's internals.
- A missing header is not proof of exploitability. A complete header set is not proof of safety.

Fixed disclaimer emitted with every score, in the API payload, the UI, and `security.md`:

> This is a passive assessment of externally observable configuration for a single page at a single
> point in time. It does not evaluate application logic, server-side controls, dependencies, or data
> handling, and it cannot establish that a site is secure or insecure.

Language rules enforced in the renderer: the words "secure", "insecure", "safe", and "vulnerable" are
never applied to the target as a verdict. Bands are phrased as posture descriptions.

## Rule table

Weights sum to 100. Each rule declares its own partial-credit fraction; there is no implicit math.

### Transport — 25 points

| id | Title | Weight | Pass | Partial | Fail | Not applicable / Unknown |
|----|-------|-------:|------|---------|------|--------------------------|
| `TLS-01` | Final document served over HTTPS | 7 | final URL scheme is `https` | — | scheme is `http` | never |
| `TLS-02` | HTTP requests redirect to HTTPS | 4 | single HEAD to the `http://` origin returns 301/308 to `https://` same host | 302/307 redirect to https (non-permanent) → 0.5 | no redirect, or redirects to http | probe disabled or failed → `unknown` |
| `TLS-03` | HSTS header present | 4 | `Strict-Transport-Security` on the HTTPS response | — | absent | site not on HTTPS → `not_applicable` |
| `TLS-04` | HSTS `max-age` ≥ 180 days | 2 | `max-age ≥ 15552000` | ≥ 86400 → 0.5 | `max-age` < 86400 or 0 | no HSTS → `not_applicable` |
| `TLS-05` | Negotiated TLS protocol version | 5 | TLS 1.3 | TLS 1.2 → 0.6 | TLS ≤ 1.1 | handshake data unavailable → `unknown` |
| `TLS-06` | Certificate validity window | 3 | valid now and > 14 days remaining | ≤ 14 days remaining → 0.5 | expired or not yet valid | certificate data unavailable → `unknown` |

`TLS-02` costs exactly one extra HEAD request per scan and is controlled by
`settings.probe_http_downgrade` (default on). When off, the rule is `unknown` and leaves the
denominator — the score never silently assumes an unobserved behaviour.

### Response headers — 35 points

| id | Title | Weight | Pass | Partial | Fail |
|----|-------|-------:|------|---------|------|
| `HDR-01` | Content-Security-Policy present | 8 | header present and non-empty | report-only header only → 0.25 | absent |
| `HDR-02` | CSP restricts script execution | 5 | effective `script-src` has neither `'unsafe-inline'` nor `'unsafe-eval'`, or uses nonce/hash with `'strict-dynamic'` | one of the two unsafe keywords present → 0.4; `'unsafe-inline'` neutralised by nonce/hash → 0.75 | wildcard `*` script source, or both unsafe keywords |
| `HDR-03` | CSP defines a default or script fallback | 2 | `default-src` or `script-src` present | only unrelated directives → 0.5 | no CSP |
| `HDR-04` | Framing controlled | 5 | CSP `frame-ancestors` present | `X-Frame-Options: DENY`/`SAMEORIGIN` only (legacy) → 0.7 | neither |
| `HDR-05` | `X-Content-Type-Options: nosniff` | 4 | exact value `nosniff` | — | absent or other value |
| `HDR-06` | Referrer-Policy | 4 | present and not `unsafe-url` | `no-referrer-when-downgrade` (browser default) → 0.5 | absent or `unsafe-url` |
| `HDR-07` | Permissions-Policy | 3 | present and non-empty | — | absent |
| `HDR-08` | Cross-Origin-Opener-Policy | 2 | `same-origin` | `same-origin-allow-popups` → 0.6 | absent |
| `HDR-09` | Cross-Origin-Resource-Policy or COEP | 2 | either present with a restrictive value | — | absent |

CSP is parsed into directives before evaluation (`analyzers/security/csp.py`), never regex-matched
against the raw string. Directive fallback semantics (`script-src` → `default-src`) are implemented,
because judging a policy without them produces wrong answers.

### Cookies — 15 points (whole category `not_applicable` when no cookies observed)

| id | Title | Weight | Pass | Partial | Fail |
|----|-------|-------:|------|---------|------|
| `CK-01` | All cookies marked `Secure` | 6 | every observed cookie has `Secure` | ≥ half do → 0.5 | none do |
| `CK-02` | All cookies marked `HttpOnly` | 5 | every observed cookie has `HttpOnly` | ≥ half do → 0.5 | none do |
| `CK-03` | `SameSite` set appropriately | 4 | every cookie declares `SameSite`, and any `None` is paired with `Secure` | some declare it → 0.5 | none declare it, or `SameSite=None` without `Secure` |

Cookie `Domain` scope, `Path`, and lifetime are recorded as unscored observations. Judging them from
outside requires knowing the application's intent, and a public-suffix list we deliberately do not
ship in V1. Cookie **values are never captured** — only names and attribute flags.

### Content integrity — 15 points

| id | Title | Weight | Pass | Partial | Fail |
|----|-------|-------:|------|---------|------|
| `CI-01` | No active mixed content | 6 | zero `http://` script/iframe/fetch/XHR subresources on an HTTPS document | — | one or more |
| `CI-02` | No passive mixed content | 3 | zero `http://` image/media/font/style subresources | — | one or more |
| `CI-03` | Subresource Integrity on cross-origin scripts and styles | 3 | all cross-origin `<script>`/`<link rel=stylesheet>` carry `integrity` | some carry it → proportional, rounded to 0.25 steps | none carry it |
| `CI-04` | Form submission targets | 3 | all form actions are HTTPS (or same-page) | some insecure → 0.5 | any `http://` action on an HTTPS page |

`CI-01`, `CI-02`, `CI-04` are `not_applicable` when the document itself is served over HTTP (there is
nothing to mix), and `CI-03` is `not_applicable` when there are no cross-origin subresources.

### Information exposure — 10 points

| id | Title | Weight | Pass | Partial | Fail |
|----|-------|-------:|------|---------|------|
| `EX-01` | Server software version not disclosed | 3 | no version token in `Server` | product without version → 0.6 | product + version |
| `EX-02` | Framework/runtime version not disclosed | 3 | no `X-Powered-By`/`X-AspNet-Version`/`X-Generator`-style version | product without version → 0.6 | product + version |
| `EX-03` | No publicly referenced source maps | 2 | no `sourceMappingURL` reference observed in loaded scripts | — | one or more references observed |
| `EX-04` | No debug/diagnostic headers exposed | 2 | none of the known debug header names present | one present without internal detail → 0.5 | present with internal paths/hostnames/timings |

`EX-03` is based on references observed in loaded script bodies. WebLens does **not** fetch the `.map`
files to confirm they resolve — that would be probing for content, not observing what the page
already told us. The finding says exactly what was observed: a reference exists.

## Aggregation

```
applicable_rules = [r for r in rules if r.outcome in {PASS, PARTIAL, FAIL}]
points_applicable = sum(r.weight for r in applicable_rules)
points_awarded    = sum(r.awarded for r in applicable_rules)     # awarded = weight * fraction
percentage        = 0.0 if points_applicable == 0 else round(points_awarded / points_applicable * 100, 1)
```

Rules with outcome `not_applicable` or `unknown` are excluded from **both** sides of the ratio and
listed in `excluded_rules` with a machine-readable reason. This is what keeps the score fair for a
site that legitimately sets no cookies, and auditable when TLS data could not be captured.

If `points_applicable` is below `minimum_applicable_points` (default 40, i.e. fewer than 40% of the
rule surface could be evaluated), no score is emitted at all: `SecurityScore` is `None` and the
section reports `partial` with the reason. A score computed from a handful of rules would be more
misleading than no score.

## Bands and caps

| Band | Percentage | Phrasing used in output |
|------|-----------:|-------------------------|
| `strong` | ≥ 85 | Strong observable posture |
| `good` | 70–84.9 | Good observable posture |
| `moderate` | 50–69.9 | Moderate observable posture |
| `limited` | 30–49.9 | Limited observable posture |
| `minimal` | < 30 | Minimal observable posture |

Two deterministic caps override the band, because some observations dominate everything else:

- `TLS-01` fails (document served over HTTP) → band capped at `limited`.
- `CI-01` fails (active mixed content on an HTTPS document) → band capped at `moderate`.

Caps are recorded on the score as `applied_caps: [{rule_id, cap}]` so the report can explain why a
band is lower than the percentage suggests.

## Change control

Any change to weights, thresholds, or bands requires a `methodology_version` bump. Results carry the
version they were scored with, so a stored scan is always interpretable against the rules that
produced it, and comparing scores across versions is explicitly flagged in the UI.
