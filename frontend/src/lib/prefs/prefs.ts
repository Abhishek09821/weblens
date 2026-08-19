/**
 * UI preferences in localStorage.
 *
 * Strictly small, non-critical UI state. Scan data never comes here: localStorage is synchronous,
 * size-limited, and writing megabytes to it would block the main thread. Reads are defensive - a
 * corrupt value resets to defaults rather than throwing during startup.
 */
import type { SectionKey } from '@/types/analysis';

export const PREFS_KEY = 'weblens.prefs.v1';

export type ThemePreference = 'system' | 'light' | 'dark';
export type Density = 'comfortable' | 'compact';

export interface Prefs {
  theme: ThemePreference;
  density: Density;
  default_section: SectionKey;
  show_evidence_by_default: boolean;
  last_scan_options: {
    include_screenshot: boolean;
    include_full_page_screenshot: boolean;
  };
  history_retention: number | null;
}

export const DEFAULT_PREFS: Prefs = {
  theme: 'system',
  density: 'comfortable',
  default_section: 'seo',
  show_evidence_by_default: false,
  last_scan_options: { include_screenshot: true, include_full_page_screenshot: false },
  history_retention: null,
};

const THEMES: ThemePreference[] = ['system', 'light', 'dark'];
const DENSITIES: Density[] = ['comfortable', 'compact'];

/**
 * Always reach storage through `window`.
 *
 * Recent Node versions expose a global `localStorage` of their own, which shadows the DOM one under
 * a test runner. Going through `window` guarantees we get the browser (or jsdom) implementation.
 */
function storage(): Storage | null {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null;
  } catch {
    // Access itself can throw when storage is blocked by policy.
    return null;
  }
}

export function loadPrefs(): Prefs {
  const store = storage();
  if (!store) return { ...DEFAULT_PREFS };
  try {
    const raw = store.getItem(PREFS_KEY);
    if (!raw) return { ...DEFAULT_PREFS };
    return coerce(JSON.parse(raw));
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

export function savePrefs(prefs: Prefs): void {
  const store = storage();
  if (!store) return;
  try {
    store.setItem(PREFS_KEY, JSON.stringify(prefs));
  } catch {
    // Storage may be full or blocked. Preferences are not worth surfacing an error for.
  }
}

export function updatePrefs(patch: Partial<Prefs>): Prefs {
  const next = { ...loadPrefs(), ...patch };
  savePrefs(next);
  return next;
}

/** Accept anything, return something valid. Unknown fields are dropped. */
function coerce(input: unknown): Prefs {
  if (!input || typeof input !== 'object') return { ...DEFAULT_PREFS };
  const raw = input as Record<string, unknown>;
  const options = (raw.last_scan_options ?? {}) as Record<string, unknown>;

  return {
    theme: THEMES.includes(raw.theme as ThemePreference)
      ? (raw.theme as ThemePreference)
      : DEFAULT_PREFS.theme,
    density: DENSITIES.includes(raw.density as Density)
      ? (raw.density as Density)
      : DEFAULT_PREFS.density,
    default_section:
      typeof raw.default_section === 'string'
        ? (raw.default_section as SectionKey)
        : DEFAULT_PREFS.default_section,
    show_evidence_by_default:
      typeof raw.show_evidence_by_default === 'boolean'
        ? raw.show_evidence_by_default
        : DEFAULT_PREFS.show_evidence_by_default,
    last_scan_options: {
      include_screenshot:
        typeof options.include_screenshot === 'boolean'
          ? options.include_screenshot
          : DEFAULT_PREFS.last_scan_options.include_screenshot,
      include_full_page_screenshot:
        typeof options.include_full_page_screenshot === 'boolean'
          ? options.include_full_page_screenshot
          : DEFAULT_PREFS.last_scan_options.include_full_page_screenshot,
    },
    history_retention:
      typeof raw.history_retention === 'number' && raw.history_retention > 0
        ? Math.floor(raw.history_retention)
        : null,
  };
}

/** Apply the resolved theme to the document root. */
export function applyTheme(theme: ThemePreference): void {
  if (typeof document === 'undefined') return;
  const prefersDark =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-color-scheme: dark)').matches === true;
  const dark = theme === 'dark' || (theme === 'system' && prefersDark);
  document.documentElement.classList.toggle('dark', dark);
}
