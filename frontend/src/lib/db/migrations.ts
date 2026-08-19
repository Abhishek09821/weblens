/**
 * Structural database migrations.
 *
 * Two kinds of change, kept separate on purpose:
 *
 * - **Structural** (new store, new index) happens here, in the `versionchange` transaction, keyed
 *   on the IndexedDB integer version.
 * - **Record shape** is handled on read in the repository, keyed on the record's
 *   `schema_version` string. A record the current build cannot read is quarantined and surfaced
 *   to the user with a delete action - never force-rendered, never silently dropped.
 */
import type { IDBPDatabase, IDBPTransaction } from 'idb';

import type { WebLensDb } from './types';

type Migration = (
  db: IDBPDatabase<WebLensDb>,
  tx: IDBPTransaction<WebLensDb, ArrayLike<never>, 'versionchange'>,
) => void;

const migrations: Record<number, Migration> = {
  1: (db) => {
    const scans = db.createObjectStore('scans', { keyPath: 'id' });
    scans.createIndex('by_created_at', 'created_at');
    scans.createIndex('by_host', 'host');
    scans.createIndex('by_status', 'status');
    scans.createIndex('by_saved_at', 'saved_at');

    db.createObjectStore('results', { keyPath: 'scan_id' });
    db.createObjectStore('screenshots', { keyPath: 'scan_id' });
    db.createObjectStore('meta', { keyPath: 'key' });
  },
};

export function applyMigrations(
  db: IDBPDatabase<WebLensDb>,
  oldVersion: number,
  newVersion: number | null,
  tx: IDBPTransaction<WebLensDb, ArrayLike<never>, 'versionchange'>,
): void {
  const target = newVersion ?? oldVersion;
  for (let version = oldVersion + 1; version <= target; version += 1) {
    const migration = migrations[version];
    if (!migration) {
      throw new Error(`No IndexedDB migration registered for version ${version}`);
    }
    migration(db, tx);
  }
}

export const REGISTERED_MIGRATIONS = Object.keys(migrations).map(Number);
