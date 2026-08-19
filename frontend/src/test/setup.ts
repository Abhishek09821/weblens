import '@testing-library/jest-dom/vitest';
import 'fake-indexeddb/auto';

import { afterEach, beforeEach } from 'vitest';

import { setRepository } from '@/lib/db/repository';
import { PREFS_KEY } from '@/lib/prefs/prefs';

import { ensureLocalStorage } from './localStorage';

/**
 * `fake-indexeddb/auto` gives the repository a real IndexedDB implementation in Node, so
 * persistence tests exercise actual transaction and index behaviour rather than a mock that agrees
 * with whatever the code does.
 */
const storage = ensureLocalStorage();

beforeEach(() => {
  storage.clear();
  storage.removeItem(PREFS_KEY);
  setRepository(null);
});

afterEach(() => {
  setRepository(null);
});
