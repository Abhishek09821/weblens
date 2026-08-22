import { beforeEach, describe, expect, it } from 'vitest';

import { DEFAULT_PREFS, loadPrefs, PREFS_KEY } from './prefs';

describe('V2 preference compatibility', () => {
  beforeEach(() => window.localStorage.clear());

  it('replaces a retired V1 default section with the V2 default', () => {
    window.localStorage.setItem(PREFS_KEY, JSON.stringify({ default_section: 'seo' }));
    expect(loadPrefs().default_section).toBe(DEFAULT_PREFS.default_section);
    expect(loadPrefs().default_section).toBe('design');
  });

  it('preserves a valid V2 default section', () => {
    window.localStorage.setItem(PREFS_KEY, JSON.stringify({ default_section: 'traffic' }));
    expect(loadPrefs().default_section).toBe('traffic');
  });
});
