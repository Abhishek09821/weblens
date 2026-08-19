/**
 * Minimal Web Storage implementation for the test environment.
 *
 * jsdom 30 no longer provides `window.localStorage`, and recent Node versions expose a global
 * `localStorage` that is unusable without `--localstorage-file`. Rather than mocking the
 * preferences module - which would stop testing the real read/write path - we give the environment
 * a genuine Storage so `lib/prefs` runs exactly as it does in a browser.
 */
export class MemoryStorage implements Storage {
  private map = new Map<string, string>();

  get length(): number {
    return this.map.size;
  }

  clear(): void {
    this.map.clear();
  }

  getItem(key: string): string | null {
    return this.map.get(String(key)) ?? null;
  }

  key(index: number): string | null {
    return [...this.map.keys()][index] ?? null;
  }

  removeItem(key: string): void {
    this.map.delete(String(key));
  }

  setItem(key: string, value: string): void {
    this.map.set(String(key), String(value));
  }
}

/** Install only when the environment's storage is missing or unusable. */
export function ensureLocalStorage(): Storage {
  const existing = (window as Window & { localStorage?: unknown }).localStorage;
  const usable =
    existing !== null &&
    typeof existing === 'object' &&
    typeof (existing as Storage).setItem === 'function' &&
    typeof (existing as Storage).clear === 'function';

  if (usable) return existing as Storage;

  const storage = new MemoryStorage();
  Object.defineProperty(window, 'localStorage', {
    value: storage,
    configurable: true,
    writable: false,
  });
  return storage;
}
