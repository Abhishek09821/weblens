# 2. Frontend architecture

React 19 + TypeScript + Vite + Tailwind CSS v4 + shadcn/ui. No global state library.

## Layering

```
routes/            URL-addressable screens, no business logic
  └─ features/     use-cases: scan lifecycle, history, reports
       └─ lib/     infrastructure: api client, IndexedDB, prefs, formatting
            └─ types/  contracts (generated + hand-authored zod schemas)
components/        presentation. sections/ are pure functions of AnalysisResult
```

Rule: a component never imports from `lib/db` or `lib/api` directly. It consumes a hook from
`features/*`. This keeps section components trivially testable with a fixture object.

## State model

Three distinct kinds of state, deliberately kept apart:

| Kind | Where | Why |
|------|-------|-----|
| Server/async state (scan job polling, capabilities) | TanStack Query | retries, cancellation, dedupe, no hand-rolled effects |
| Persistent scan data (records, results, screenshots) | IndexedDB via `lib/db`, exposed through Query with `queryKey: ['scan', id]` | survives refresh/restart; Query is only a cache over it |
| UI preferences (theme, density, last-used options, section order) | localStorage via `lib/prefs` | tiny, synchronous, non-critical |

There is no Redux/Zustand store. The only cross-tree UI state is theme, which lives in a small
context backed by `lib/prefs`.

## Scan lifecycle (frontend view)

```
idle → validating → submitting → running(stage stream) → persisting → ready
                        ↘ failed(problem)        ↘ ready-with-errors
```

- `validating` is local: URL syntax + scheme + obvious-non-public host check, so the user gets
  feedback without a round trip. The backend re-validates authoritatively.
- `running` consumes **real** stage events over SSE (`GET /scans/{id}/events`). Progress is derived
  from `completed_weight / total_weight` of declared stages returned by the backend. If SSE is
  unavailable, it falls back to polling `GET /scans/{id}`. There is **no** timer-driven fake
  progress bar; when the backend reports no change, the UI shows the current stage and an elapsed
  timer only.
- `persisting`: on terminal status the client fetches the result once, validates it with zod, writes
  it to IndexedDB, then calls `DELETE /scans/{id}` to release the server-side copy. The server is a
  transport buffer, not a store.

## Routes

| Path | Screen | Notes |
|------|--------|-------|
| `/` | Analyze + local scan library | URL input, options, recent scans from IndexedDB |
| `/scan/:id` | Report dashboard | section nav, read from IndexedDB (works offline) |
| `/scan/:id/:section` | Deep link to one section | section keys are stable strings |
| `/about` | Methodology + limitations | renders `docs/limitations.md` content, security scoring rules |

Deep links must work after a browser restart with the backend stopped. That is the acceptance test
for the persistence layer.

## Dashboard composition

```
<ReportShell>            target url, scan time, engine version, status banner, export menu
  <SectionNav>           8 sections + per-section status dot (complete/partial/unavailable)
  <SectionOutlet>
     <TechnologySection/>  card grid, grouped by category, evidence popover per card
     <DesignSection/>      color swatches, type scale, spacing/radius/shadow tables, facts vs interpretation
     <SecuritySection/>    posture score + rule table (pass/partial/fail/not-applicable) + methodology link
     <PerformanceSection/> metric cards w/ units + "single lab run" caveat, resource breakdown
     <AccessibilitySection/> violations by impact, structural observations, coverage caveat
     <SeoSection/>         metadata table, canonical/robots, social preview, structured data
     <ArchitectureSection/> rendering strategy signals, hosting/CDN indicators, runtime observations
     <NetworkSection/>     request table (domain, type, size, timing), third-party domain summary
```

Cross-cutting presentation components (the pieces that keep A2/A3/A5 honest):

- `<FindingRow>` — renders `status` as a label (`Verified`, `Inferred`, `Not detected`,
  `Not determinable`, `Unable to verify`). Never renders `confidence`.
- `<EvidencePopover>` — shows `EvidenceRef` list: kind, source path, excerpt, location.
- `<InterpretationCallout>` — visually distinct block, always prefixed "Interpretation", lists the
  findings it derives from.
- `<UnavailableSection>` — reason + limitations, used when `SectionStatus` is
  `unavailable`/`not_implemented`.
- `<LimitationList>` — per-section limitations, also embedded in generated reports.

## Design language of the tool itself

Developer-tool aesthetic, not admin template: dense typography, monospace for evidence and values,
tabular data over decorative cards, muted surface palette with one accent, keyboard-first (`/` focus
URL input, `g` + section key to jump, `⌘K` command palette in a later phase). Dark and light themes
both first-class via CSS custom properties defined in `index.css` (Tailwind v4 `@theme`).

Accessibility of WebLens itself is part of the definition of done: semantic landmarks, labelled
controls, visible focus rings, `aria-live` for scan status, no color-only status encoding (status
dots always paired with text).

## Error surfaces

| Case | UI |
|------|-----|
| Invalid URL | inline field error, submit blocked |
| Problem response (RFC 9457) | banner with `title`, `detail`, and `code`; retry affordance when retryable |
| Blocked target (private/loopback host) | explicit explanation that only public sites are scannable |
| Scan finished with analyzer errors | amber banner "Completed with N section issues", affected sections show reason |
| Result expired on server (410) before persistence | offer re-scan; explain the buffer window |
| IndexedDB unavailable/quota exceeded | banner: session-only mode, downloads still work |
