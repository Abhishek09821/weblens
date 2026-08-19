import type { DBSchema } from 'idb';

import type { AnalysisResult, ScanStatus, SectionKey, SectionStatus } from '@/types/analysis';

export const DB_NAME = 'weblens';
export const DB_VERSION = 1;

/** Shape version of stored records, independent of the IndexedDB integer version. */
export const RECORD_SCHEMA_VERSION = '1.0';

/**
 * Small projection that powers the scan library.
 *
 * Deliberately not the whole result: opening the library must not deserialize megabytes. Kept in
 * its own store so listing scans touches only kilobytes.
 */
export interface ScanRecord {
  id: string;
  requested_url: string;
  normalized_url: string;
  final_url: string | null;
  host: string;
  status: ScanStatus;
  created_at: string;
  saved_at: string;
  duration_ms: number | null;
  engine_version: string;
  schema_version: string;
  section_statuses: Record<SectionKey, SectionStatus>;
  /** `null` when the security section is not complete. The list shows "—", never a zero. */
  security_percentage: number | null;
  error_count: number;
  finding_count: number;
  has_screenshot: boolean;
  result_bytes: number;
}

export interface ResultRecord {
  scan_id: string;
  schema_version: string;
  result: AnalysisResult;
}

export interface ScreenshotItem {
  label: string;
  width: number;
  height: number;
  blob: Blob;
}

export interface ScreenshotRecord {
  scan_id: string;
  items: ScreenshotItem[];
}

export interface MetaRecord {
  key: string;
  value: unknown;
}

export interface WebLensDb extends DBSchema {
  scans: {
    key: string;
    value: ScanRecord;
    indexes: {
      by_created_at: string;
      by_host: string;
      by_status: string;
      by_saved_at: string;
    };
  };
  results: { key: string; value: ResultRecord };
  screenshots: { key: string; value: ScreenshotRecord };
  meta: { key: string; value: MetaRecord };
}

export const STORES = ['scans', 'results', 'screenshots', 'meta'] as const;
export const DATA_STORES = ['scans', 'results', 'screenshots'] as const;

export interface PersistOutcome {
  saved: boolean;
  screenshotsDropped: boolean;
  /** Present when persistence degraded or failed, for honest reporting in the UI. */
  warning?: string;
}

export interface QuarantinedScan {
  id: string;
  schema_version: string;
  reason: string;
}
