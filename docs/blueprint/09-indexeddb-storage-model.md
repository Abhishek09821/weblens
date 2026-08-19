# 9. IndexedDB storage model

Requirement: scan results survive page refresh and browser restart, with no remote database. The
browser is therefore the system of record; the backend is a transport buffer.

Library: `idb` (thin promise wrapper over the native API, ~1 kB gzipped). Not Dexie — we need four
stores and explicit migrations, not a query DSL.

## Database

- Name: `weblens`
- Version: `1` (IndexedDB integer version, incremented per schema change)
- Data schema version: the `schema_version` string carried on each record, independent of the above

## Object stores

| Store | Key | Contents | Why separate |
|-------|-----|----------|--------------|
| `scans` | `id` (ULID) | `ScanRecord` projection (~1 kB) | history list loads instantly, never touches large blobs |
| `results` | `scan_id` | `ResultRecord` (full `AnalysisResult`, tens of kB to a few MB) | loaded only when a report is opened |
| `screenshots` | `scan_id` | `ScreenshotRecord` with `Blob`s | heaviest data; stored as `Blob` (not data URL) which is smaller and streams to `<img>` via `createObjectURL` |
| `meta` | `key` | singletons: `schema_version`, `last_cleanup_at`, `prefs_migrated`, `quarantine` | migration bookkeeping |

Indexes on `scans`:

| Index | Key path | Used by |
|-------|----------|---------|
| `by_created_at` | `created_at` | default history ordering (descending) |
| `by_host` | `host` | "other scans of this site" and grouping |
| `by_status` | `status` | filtering failed/partial scans |
| `by_saved_at` | `saved_at` | retention/cleanup sweeps |

## Write path (one transaction)

```
persistScan(result, screenshots):
  tx = db.transaction(['scans','results','screenshots'], 'readwrite')
  tx.scans.put(project(result))          // small projection
  tx.results.put({ scan_id, schema_version, result })
  if screenshots.length: tx.screenshots.put({ scan_id, items })
  await tx.done                          // atomic: no orphan result without a record
```

All three writes share one transaction, so a failure mid-way cannot leave the history list pointing
at a result that does not exist. Only after `tx.done` resolves does the client call
`DELETE /api/v1/scans/{id}`, and only then is the scan considered persisted.

## Delete path

```
deleteScan(id):
  tx = db.transaction(['scans','results','screenshots'], 'readwrite')
  delete from all three by key
  await tx.done
  revokeObjectURLs(id)                   // release any live blob URLs
  DELETE /api/v1/scans/{id}              // best-effort; ignores 404
```

"When a user explicitly deletes a scan, its IndexedDB data must be removed" is satisfied by deleting
from every store keyed on that scan in a single transaction. A `deleteAll()` clears the three data
stores but preserves `meta`. Deletion is confirmed through a dialog and is not undoable — stated
plainly in the UI, since there is no server copy to recover from.

## Migrations

```ts
type Migration = (db: IDBPDatabase, tx: IDBPTransaction) => void;
const migrations: Record<number, Migration> = {
  1: (db) => { /* create stores + indexes */ },
};
```

`upgrade(db, oldVersion, newVersion, tx)` applies every migration in `(oldVersion, newVersion]` in
order. Structural changes (new store/index) go here. Record-shape changes are handled separately on
read by `migrateResult(record)`, which dispatches on the record's `schema_version`:

- `schema_version` matches current → return as-is.
- Older, with a registered upgrade path → transform, re-validate, write back.
- Older with no path, or newer than the app (user downgraded) → move the id into
  `meta.quarantine` and surface the record in the UI as "saved by a different WebLens version, cannot
  be displayed", with a delete action. Nothing is force-rendered and nothing is silently dropped.

## Quota and pressure

- Before writing, `navigator.storage.estimate()` is consulted; if the projected write exceeds 90% of
  quota, the UI warns and offers to delete old scans instead of failing mid-transaction.
- `QuotaExceededError` is caught and retried once without screenshots (they dominate size), and the
  resulting `ScanRecord.has_screenshot` is `false` — an honest degradation, recorded rather than
  hidden.
- Optional retention preference (`keep last N scans`, default off) runs a sweep on app start using
  `by_saved_at`.
- If IndexedDB is entirely unavailable (private mode in some browsers, disabled storage), the
  repository falls back to an in-memory implementation behind the same interface and the UI shows a
  persistent "session-only" banner. Reports still download.

## localStorage — strictly UI preferences

Single key `weblens.prefs.v1` holding a small JSON object:

```ts
interface Prefs {
  theme: 'system' | 'light' | 'dark';
  density: 'comfortable' | 'compact';
  default_section: SectionKey;
  show_evidence_by_default: boolean;
  last_scan_options: { include_screenshot: boolean; include_full_page_screenshot: boolean };
  history_retention: number | null;
}
```

No scan data ever goes here — it is size-limited, synchronous, and would block the main thread on
large payloads. Reads are defensive: a parse failure or unknown value resets to defaults rather than
throwing at startup.

## Testing hooks

The repository is an interface (`ScanRepository`) with two implementations: `IdbScanRepository` and
`MemoryScanRepository`. Tests run the same suite against both, and `fake-indexeddb` gives the idb
implementation a real IndexedDB in Node. Round-trip, delete-cascade, quota-fallback, and
schema-quarantine cases are all covered (doc 12).
