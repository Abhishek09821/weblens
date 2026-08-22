/**
 * Scan persistence.
 *
 * The browser is the system of record: results must survive refresh and browser restart, and the
 * backend releases its copy as soon as a write here succeeds. That makes two behaviours
 * non-negotiable, and both are enforced below rather than left to callers:
 *
 * 1. A write is one transaction across `scans`, `results`, and `screenshots`, so the library can
 *    never list a scan whose result is missing.
 * 2. A delete removes every trace of a scan in one transaction. There is no server copy to fall
 *    back on, so a partial delete would leave undeletable orphans.
 */
import { openDB, type IDBPDatabase } from 'idb';

import { analysisResultSchema, type AnalysisResult, type SectionKey } from '@/types/analysis';

import { applyMigrations } from './migrations';
import {
  DATA_STORES,
  DB_NAME,
  DB_VERSION,
  RECORD_SCHEMA_VERSION,
  type MetaRecord,
  type PersistOutcome,
  type QuarantinedScan,
  type ResultRecord,
  type ScanRecord,
  type ScreenshotItem,
  type ScreenshotRecord,
  type WebLensDb,
} from './types';

const QUOTA_HEADROOM = 0.9;

export interface ScanRepository {
  list(): Promise<ScanRecord[]>;
  get(scanId: string): Promise<ScanRecord | undefined>;
  getResult(scanId: string): Promise<AnalysisResult | undefined>;
  getScreenshots(scanId: string): Promise<ScreenshotItem[]>;
  persist(result: AnalysisResult, screenshots?: ScreenshotItem[]): Promise<PersistOutcome>;
  remove(scanId: string): Promise<void>;
  clear(): Promise<void>;
  quarantined(): Promise<QuarantinedScan[]>;
  /**
   * Release the database connection.
   *
   * An open connection blocks `deleteDatabase` and version upgrades from other tabs, so being able
   * to close deliberately is part of the contract, not just a test convenience.
   */
  close(): Promise<void>;
}

export class IdbScanRepository implements ScanRepository {
  private handle: Promise<IDBPDatabase<WebLensDb>> | null = null;

  private db(): Promise<IDBPDatabase<WebLensDb>> {
    this.handle ??= openDB<WebLensDb>(DB_NAME, DB_VERSION, {
      upgrade(database, oldVersion, newVersion, transaction) {
        applyMigrations(database, oldVersion, newVersion, transaction);
      },
      blocked() {
        console.warn('[weblens] another tab is holding an older database version open');
      },
    });
    return this.handle;
  }

  async list(): Promise<ScanRecord[]> {
    const db = await this.db();
    const records = await db.getAllFromIndex('scans', 'by_created_at');
    return records.reverse();
  }

  async get(scanId: string): Promise<ScanRecord | undefined> {
    return (await this.db()).get('scans', scanId);
  }

  async getResult(scanId: string): Promise<AnalysisResult | undefined> {
    const db = await this.db();
    const record = await db.get('results', scanId);
    if (!record) return undefined;

    if (record.schema_version !== RECORD_SCHEMA_VERSION) {
      await this.quarantine(scanId, record.schema_version);
      return undefined;
    }

    // Validate on read as well as on write: a record could have been written by a different
    // version of the app, or corrupted. Rendering it unchecked is how a dashboard crashes.
    const parsed = analysisResultSchema.safeParse(record.result);
    if (!parsed.success) {
      await this.quarantine(scanId, record.schema_version, 'stored record failed validation');
      return undefined;
    }
    return parsed.data;
  }

  async getScreenshots(scanId: string): Promise<ScreenshotItem[]> {
    const record = await (await this.db()).get('screenshots', scanId);
    return record?.items ?? [];
  }

  async persist(result: AnalysisResult, screenshots: ScreenshotItem[] = []): Promise<PersistOutcome> {
    const db = await this.db();
    const record = projectScanRecord(result, screenshots.length > 0);
    const resultRecord: ResultRecord = {
      scan_id: result.scan.scan_id,
      schema_version: RECORD_SCHEMA_VERSION,
      result,
    };

    const quotaWarning = await checkQuota(record.result_bytes);

    try {
      await writeAll(db, record, resultRecord, screenshots);
      return { saved: true, screenshotsDropped: false, ...(quotaWarning ? { warning: quotaWarning } : {}) };
    } catch (error) {
      if (!isQuotaError(error) || screenshots.length === 0) {
        throw error;
      }
      // Screenshots dominate size. Retry without them and report the degradation rather than
      // failing the write or silently claiming a screenshot exists.
      await writeAll(db, { ...record, has_screenshot: false }, resultRecord, []);
      return {
        saved: true,
        screenshotsDropped: true,
        warning:
          'Storage quota was reached, so screenshots were not saved. The analysis itself is stored.',
      };
    }
  }

  async remove(scanId: string): Promise<void> {
    const db = await this.db();
    const tx = db.transaction(DATA_STORES, 'readwrite');
    await Promise.all([
      tx.objectStore('scans').delete(scanId),
      tx.objectStore('results').delete(scanId),
      tx.objectStore('screenshots').delete(scanId),
      tx.done,
    ]);
    await this.removeFromQuarantine(scanId);
  }

  async clear(): Promise<void> {
    const db = await this.db();
    const tx = db.transaction(DATA_STORES, 'readwrite');
    await Promise.all([
      tx.objectStore('scans').clear(),
      tx.objectStore('results').clear(),
      tx.objectStore('screenshots').clear(),
      tx.done,
    ]);
    await this.setMeta('quarantine', []);
  }

  async quarantined(): Promise<QuarantinedScan[]> {
    const record = await (await this.db()).get('meta', 'quarantine');
    return Array.isArray(record?.value) ? (record.value as QuarantinedScan[]) : [];
  }

  async close(): Promise<void> {
    if (!this.handle) return;
    const pending = this.handle;
    this.handle = null;
    try {
      (await pending).close();
    } catch {
      // Already closed or failed to open; either way there is nothing to release.
    }
  }

  private async quarantine(scanId: string, schemaVersion: string, reason?: string): Promise<void> {
    const existing = await this.quarantined();
    if (existing.some((item) => item.id === scanId)) return;
    const entry: QuarantinedScan = {
      id: scanId,
      schema_version: schemaVersion,
      reason:
        reason ??
        (schemaVersion === '1.0'
          ? 'This V1 scan is preserved in history but its eight-section result is incompatible with the V2 four-report model. Run a new scan to view reports.'
          : `Saved by a WebLens build using schema ${schemaVersion}; this build reads ${RECORD_SCHEMA_VERSION}.`),
    };
    await this.setMeta('quarantine', [...existing, entry]);
  }

  private async removeFromQuarantine(scanId: string): Promise<void> {
    const existing = await this.quarantined();
    if (!existing.some((item) => item.id === scanId)) return;
    await this.setMeta(
      'quarantine',
      existing.filter((item) => item.id !== scanId),
    );
  }

  private async setMeta(key: string, value: unknown): Promise<void> {
    const db = await this.db();
    const record: MetaRecord = { key, value };
    await db.put('meta', record);
  }
}

/**
 * In-memory fallback used when IndexedDB is unavailable (private browsing, storage disabled).
 *
 * Same interface, so the app degrades to session-only persistence with a visible banner instead of
 * failing. Report downloads keep working because they are generated from the result in memory.
 */
export class MemoryScanRepository implements ScanRepository {
  private scans = new Map<string, ScanRecord>();
  private results = new Map<string, ResultRecord>();
  private screenshots = new Map<string, ScreenshotRecord>();

  async list(): Promise<ScanRecord[]> {
    return [...this.scans.values()].sort((a, b) => b.created_at.localeCompare(a.created_at));
  }

  async get(scanId: string): Promise<ScanRecord | undefined> {
    return this.scans.get(scanId);
  }

  async getResult(scanId: string): Promise<AnalysisResult | undefined> {
    return this.results.get(scanId)?.result;
  }

  async getScreenshots(scanId: string): Promise<ScreenshotItem[]> {
    return this.screenshots.get(scanId)?.items ?? [];
  }

  async persist(result: AnalysisResult, screenshots: ScreenshotItem[] = []): Promise<PersistOutcome> {
    const id = result.scan.scan_id;
    this.scans.set(id, projectScanRecord(result, screenshots.length > 0));
    this.results.set(id, { scan_id: id, schema_version: RECORD_SCHEMA_VERSION, result });
    if (screenshots.length > 0) this.screenshots.set(id, { scan_id: id, items: screenshots });
    return { saved: true, screenshotsDropped: false };
  }

  async remove(scanId: string): Promise<void> {
    this.scans.delete(scanId);
    this.results.delete(scanId);
    this.screenshots.delete(scanId);
  }

  async clear(): Promise<void> {
    this.scans.clear();
    this.results.clear();
    this.screenshots.clear();
  }

  async quarantined(): Promise<QuarantinedScan[]> {
    return [];
  }

  async close(): Promise<void> {
    // Nothing to release.
  }
}

async function writeAll(
  db: IDBPDatabase<WebLensDb>,
  record: ScanRecord,
  resultRecord: ResultRecord,
  screenshots: ScreenshotItem[],
): Promise<void> {
  const tx = db.transaction(DATA_STORES, 'readwrite');
  const writes: Promise<unknown>[] = [
    tx.objectStore('scans').put(record),
    tx.objectStore('results').put(resultRecord),
  ];
  if (screenshots.length > 0) {
    writes.push(
      tx.objectStore('screenshots').put({ scan_id: record.id, items: screenshots }),
    );
  }
  writes.push(tx.done);
  await Promise.all(writes);
}

export function projectScanRecord(result: AnalysisResult, hasScreenshot: boolean): ScanRecord {
  const sections = result.sections;
  const sectionStatuses = Object.fromEntries(
    Object.entries(sections).map(([key, section]) => [key, section.meta.status]),
  ) as Record<SectionKey, ScanRecord['section_statuses'][SectionKey]>;

  const findingCount = Object.values(sections).reduce(
    (total, section) => total + section.findings.length,
    0,
  );

  return {
    id: result.scan.scan_id,
    requested_url: result.target.requested_url,
    normalized_url: result.target.normalized_url,
    final_url: result.target.final_url ?? null,
    host: result.target.host,
    status: result.scan.status,
    created_at: result.scan.created_at,
    saved_at: new Date().toISOString(),
    duration_ms: result.scan.duration_ms ?? null,
    engine_version: result.scan.engine_version,
    schema_version: result.schema_version,
    section_statuses: sectionStatuses,
    security_percentage: readSecurityPercentage(result),
    error_count: result.errors.length,
    finding_count: findingCount,
    has_screenshot: hasScreenshot,
    result_bytes: approximateBytes(result),
  };
}

/** `null` unless the security section actually produced a score. */
function readSecurityPercentage(result: AnalysisResult): number | null {
  const section = result.sections.security;
  if (section.meta.status !== 'complete' && section.meta.status !== 'partial') return null;
  const data = section.data;
  if (!data || typeof data !== 'object') return null;
  const score = (data as { score?: { percentage?: unknown } }).score;
  return typeof score?.percentage === 'number' ? score.percentage : null;
}

function approximateBytes(result: AnalysisResult): number {
  try {
    return new TextEncoder().encode(JSON.stringify(result)).length;
  } catch {
    return 0;
  }
}

async function checkQuota(incomingBytes: number): Promise<string | undefined> {
  if (typeof navigator === 'undefined' || !navigator.storage?.estimate) return undefined;
  try {
    const { usage = 0, quota = 0 } = await navigator.storage.estimate();
    if (quota === 0) return undefined;
    if (usage + incomingBytes > quota * QUOTA_HEADROOM) {
      return 'Local storage for this site is nearly full. Delete old scans to make room.';
    }
  } catch {
    return undefined;
  }
  return undefined;
}

function isQuotaError(error: unknown): boolean {
  return (
    error instanceof DOMException &&
    (error.name === 'QuotaExceededError' || error.name === 'NS_ERROR_DOM_QUOTA_REACHED')
  );
}

let singleton: ScanRepository | null = null;

/** The app-wide repository, falling back to memory when IndexedDB is unavailable. */
export function getRepository(): ScanRepository {
  if (singleton) return singleton;
  singleton = indexedDbAvailable() ? new IdbScanRepository() : new MemoryScanRepository();
  return singleton;
}

export function isPersistent(): boolean {
  return getRepository() instanceof IdbScanRepository;
}

/** Test seam. */
export function setRepository(repository: ScanRepository | null): void {
  singleton = repository;
}

function indexedDbAvailable(): boolean {
  try {
    return typeof indexedDB !== 'undefined' && indexedDB !== null;
  } catch {
    return false;
  }
}
