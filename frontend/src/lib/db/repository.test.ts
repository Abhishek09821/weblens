/**
 * Persistence tests.
 *
 * The requirement is that results survive refresh and browser restart, so these run against a real
 * IndexedDB implementation (`fake-indexeddb`) rather than a mock, and the "restart" case is covered
 * by opening a fresh repository over the same database.
 *
 * Connections are closed in teardown: an open connection blocks `deleteDatabase`, which would make
 * the suite hang rather than fail — the least useful failure mode there is.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { makeResult } from '@/test/factories';

import { IdbScanRepository, MemoryScanRepository, projectScanRecord } from './repository';
import type { ScanRepository } from './repository';
import { DB_NAME, RECORD_SCHEMA_VERSION } from './types';

function wipe(): Promise<void> {
  return new Promise<void>((resolve) => {
    const request = indexedDB.deleteDatabase(DB_NAME);
    request.onsuccess = () => resolve();
    request.onerror = () => resolve();
    request.onblocked = () => resolve();
  });
}

function openRaw(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function putRawResult(scanId: string, record: unknown): Promise<void> {
  await putRawRecord('results', record);
  void scanId;
}

async function putRawScan(record: unknown): Promise<void> {
  await putRawRecord('scans', record);
}

async function putRawRecord(store: 'results' | 'scans', record: unknown): Promise<void> {
  const db = await openRaw();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(store, 'readwrite');
    tx.objectStore(store).put(record as never);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

function makeLegacyV1Result(): unknown {
  const current = makeResult();
  const legacySection = (key: string) => ({
    ...current.sections.design,
    meta: { ...current.sections.design.meta, key },
  });
  return {
    ...current,
    schema_version: '1.0',
    scan: { ...current.scan, schema_version: '1.0' },
    sections: {
      design: legacySection('design'),
      technology: legacySection('technology'),
      security: legacySection('security'),
      performance: legacySection('performance'),
      accessibility: legacySection('accessibility'),
      seo: legacySection('seo'),
      architecture: legacySection('architecture'),
      network: legacySection('network'),
    },
  };
}

// The same suite runs against both implementations: the in-memory fallback must behave like the
// real one, or the "session-only" degradation would be a different product.
const implementations: [string, () => ScanRepository][] = [
  ['IdbScanRepository', () => new IdbScanRepository()],
  ['MemoryScanRepository', () => new MemoryScanRepository()],
];

describe.each(implementations)('%s', (_name, create) => {
  let repo: ScanRepository;

  beforeEach(() => {
    repo = create();
  });

  afterEach(async () => {
    await repo.close();
    await wipe();
  });

  it('stores and reads back a result', async () => {
    const result = makeResult();
    const outcome = await repo.persist(result);

    expect(outcome.saved).toBe(true);
    expect(await repo.getResult(result.scan.scan_id)).toEqual(result);
  });

  it('lists a compact projection instead of full results', async () => {
    await repo.persist(makeResult());
    const [record] = await repo.list();

    expect(record).toBeDefined();
    expect(record?.host).toBe('example.test');
    expect(record?.finding_count).toBe(9);
    expect(record?.section_statuses.traffic).toBe('complete');
    expect(record?.section_statuses.design).toBe('complete');
    expect(record?.result_bytes).toBeGreaterThan(0);
    // A projection, not the whole payload.
    expect(record).not.toHaveProperty('sections');
  });

  it('orders the library newest first', async () => {
    const older = makeResult();
    const newerBase = makeResult();
    const newer = {
      ...newerBase,
      scan: {
        ...newerBase.scan,
        scan_id: '01M0CSX29SJT518RFY2VXF92AA',
        created_at: '2026-08-20T10:00:00.000Z',
      },
    };
    await repo.persist(older);
    await repo.persist(newer);

    const ids = (await repo.list()).map((record) => record.id);
    expect(ids[0]).toBe(newer.scan.scan_id);
    expect(ids).toHaveLength(2);
  });

  it('removes every trace of a deleted scan', async () => {
    const result = makeResult();
    await repo.persist(result, [
      { label: 'viewport', width: 1440, height: 900, blob: new Blob([new Uint8Array([1, 2, 3])]) },
    ]);

    await repo.remove(result.scan.scan_id);

    expect(await repo.get(result.scan.scan_id)).toBeUndefined();
    expect(await repo.getResult(result.scan.scan_id)).toBeUndefined();
    expect(await repo.getScreenshots(result.scan.scan_id)).toEqual([]);
    expect(await repo.list()).toEqual([]);
  });

  it('stores screenshots separately from the result', async () => {
    const result = makeResult();
    await repo.persist(result, [
      { label: 'viewport', width: 800, height: 600, blob: new Blob([new Uint8Array([9, 9])]) },
    ]);

    const shots = await repo.getScreenshots(result.scan.scan_id);
    expect(shots).toHaveLength(1);
    expect(shots[0]?.label).toBe('viewport');
    expect((await repo.get(result.scan.scan_id))?.has_screenshot).toBe(true);
  });

  it('clears everything on request', async () => {
    await repo.persist(makeResult());
    await repo.clear();
    expect(await repo.list()).toEqual([]);
  });
});

describe('IdbScanRepository durability', () => {
  let repo: IdbScanRepository;

  beforeEach(() => {
    repo = new IdbScanRepository();
  });

  afterEach(async () => {
    await repo.close();
    await wipe();
  });

  it('survives a simulated browser restart', async () => {
    const result = makeResult();
    await repo.persist(result);
    await repo.close();

    // A fresh instance reopens the database, which is what a reload or browser restart does.
    const afterRestart = new IdbScanRepository();
    try {
      expect((await afterRestart.getResult(result.scan.scan_id))?.scan.scan_id).toBe(
        result.scan.scan_id,
      );
      expect(await afterRestart.list()).toHaveLength(1);
    } finally {
      await afterRestart.close();
    }
  });

  it('quarantines a record written by an incompatible schema version', async () => {
    const result = makeResult();
    await repo.persist(result);
    await repo.close();

    await putRawResult(result.scan.scan_id, {
      scan_id: result.scan.scan_id,
      schema_version: '9.9',
      result,
    });

    const fresh = new IdbScanRepository();
    try {
      expect(await fresh.getResult(result.scan.scan_id)).toBeUndefined();
      const quarantined = await fresh.quarantined();
      expect(quarantined).toHaveLength(1);
      expect(quarantined[0]?.schema_version).toBe('9.9');
      expect(quarantined[0]?.reason).toContain('9.9');
    } finally {
      await fresh.close();
    }
  });

  it('preserves a real V1 compact history row while quarantining its eight-section result', async () => {
    const result = makeResult();
    await repo.persist(result);
    const compact = await repo.get(result.scan.scan_id);
    await repo.close();

    await putRawScan({
      ...compact,
      schema_version: '1.0',
      section_statuses: {
        design: 'complete',
        technology: 'complete',
        security: 'complete',
        performance: 'complete',
        accessibility: 'complete',
        seo: 'complete',
        architecture: 'complete',
        network: 'complete',
      },
    });
    await putRawResult(result.scan.scan_id, {
      scan_id: result.scan.scan_id,
      schema_version: '1.0',
      result: makeLegacyV1Result(),
    });

    const fresh = new IdbScanRepository();
    try {
      const [historyRow] = await fresh.list();
      expect(historyRow?.host).toBe('example.test');
      expect(historyRow?.section_statuses.traffic).toBeUndefined();
      expect(await fresh.getResult(result.scan.scan_id)).toBeUndefined();
      const [quarantined] = await fresh.quarantined();
      expect(quarantined?.schema_version).toBe('1.0');
      expect(quarantined?.reason).toContain('V1 scan is preserved in history');
      expect(quarantined?.reason).toContain('eight-section');
    } finally {
      await fresh.close();
    }
  });

  it('quarantines a stored record that fails validation', async () => {
    const result = makeResult();
    await repo.persist(result);
    await repo.close();

    await putRawResult(result.scan.scan_id, {
      scan_id: result.scan.scan_id,
      schema_version: RECORD_SCHEMA_VERSION,
      // `status` is a structural key, so an invalid value must be rejected rather than rendered.
      result: { ...result, scan: { ...result.scan, status: 'teleported' } },
    });

    const fresh = new IdbScanRepository();
    try {
      expect(await fresh.getResult(result.scan.scan_id)).toBeUndefined();
      expect(await fresh.quarantined()).toHaveLength(1);
    } finally {
      await fresh.close();
    }
  });

  it('forgets a quarantined record once it is deleted', async () => {
    const result = makeResult();
    await repo.persist(result);
    await repo.close();

    await putRawResult(result.scan.scan_id, {
      scan_id: result.scan.scan_id,
      schema_version: '9.9',
      result,
    });

    const fresh = new IdbScanRepository();
    try {
      await fresh.getResult(result.scan.scan_id);
      expect(await fresh.quarantined()).toHaveLength(1);
      await fresh.remove(result.scan.scan_id);
      expect(await fresh.quarantined()).toHaveLength(0);
    } finally {
      await fresh.close();
    }
  });
});

describe('projectScanRecord', () => {
  it('reports no security percentage when the section is not scored', () => {
    // "—" in the UI, never a misleading zero.
    expect(projectScanRecord(makeResult(), false).security_percentage).toBeNull();
  });

  it('reads the security percentage when a score exists', () => {
    const result = makeResult();
    result.sections.security = {
      ...result.sections.security,
      meta: { ...result.sections.security.meta, status: 'complete', unavailable_reason: null },
      data: { score: { percentage: 72.5 } },
    };
    expect(projectScanRecord(result, false).security_percentage).toBe(72.5);
  });

  it('records the schema version it was written with', () => {
    expect(projectScanRecord(makeResult(), false).schema_version).toBe(RECORD_SCHEMA_VERSION);
  });
});
