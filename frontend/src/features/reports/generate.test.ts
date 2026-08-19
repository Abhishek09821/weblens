/**
 * Report generation tests.
 *
 * Two of these encode product principles as executable checks rather than testing formatting:
 * confidence must never appear beside a claim, and cookie values must never appear in output. Those
 * are the promises most likely to be eroded by a well-intentioned refactor.
 */
import { describe, expect, it } from 'vitest';

import { makeFinding, makeResult, makeSection } from '@/test/factories';
import type { AnalysisResult } from '@/types/analysis';

import { bundleToZip } from './bundle';
import { renderAnalysisJson, stableStringify } from './json';
import { buildReportBundle, renderSectionReport } from './generate';
import { REPORT_DEFINITIONS } from './markdown/renderers';

function bundleFiles(result: AnalysisResult): Record<string, string> {
  return Object.fromEntries(
    buildReportBundle(result).files.map((file) => [file.path, file.contents]),
  );
}

describe('buildReportBundle', () => {
  it('produces the documented file set', () => {
    const files = bundleFiles(makeResult());
    expect(Object.keys(files).sort()).toEqual([
      'README.md',
      'accessibility.md',
      'analysis.json',
      'architecture.md',
      'design.md',
      'performance.md',
      'security.md',
      'seo.md',
      'techstack.md',
    ]);
  });

  it('names the archive after the host and scan time', () => {
    expect(buildReportBundle(makeResult()).suggestedName).toMatch(
      /^weblens-example\.test-\d{8}-\d{6}$/,
    );
  });

  it('includes scan metadata and target in every markdown file', () => {
    const files = bundleFiles(makeResult());
    for (const definition of REPORT_DEFINITIONS) {
      const contents = files[definition.file];
      expect(contents, definition.file).toBeDefined();
      expect(contents).toContain('01M0CSX29SJT518RFY2VXF91XW');
      expect(contents).toContain('https://example.test/');
      expect(contents).toContain('Engine version');
      expect(contents).toContain('Schema version');
    }
  });

  it('still writes a file for a section that produced nothing', () => {
    const files = bundleFiles(makeResult());
    // An empty-but-explained file makes a partial scan self-documenting.
    expect(files['design.md']).toContain('No findings available');
    expect(files['design.md']).toContain('No analyzer for this section ships in this build yet');
    expect(files['design.md']).toContain('Nothing about the target was inferred in its place');
  });

  it('renders findings with word statuses and reasons', () => {
    const seo = bundleFiles(makeResult())['seo.md'] ?? '';
    expect(seo).toContain('| Document title | Verified |');
    expect(seo).toContain('Meta description');
    expect(seo).toContain('Not detected');
    expect(seo).toContain('No <meta name="description"> with content was present.');
  });

  it('never prints confidence beside a claim', () => {
    const files = bundleFiles(makeResult());
    for (const [path, contents] of Object.entries(files)) {
      if (path === 'analysis.json') continue; // retained there as auditable metadata
      expect(contents.toLowerCase(), path).not.toContain('definitive');
      expect(contents.toLowerCase(), path).not.toContain('confidence');
    }
  });

  it('includes evidence for asserted findings', () => {
    const seo = bundleFiles(makeResult())['seo.md'] ?? '';
    expect(seo).toContain('Observed evidence');
    expect(seo).toContain('dom.title');
  });

  it('omits evidence when asked', () => {
    const file = renderSectionReport(makeResult(), 'seo', {
      includeEvidence: false,
      maxEvidencePerFinding: 0,
    });
    expect(file?.contents).not.toContain('Observed evidence');
  });

  it('folds the network section into the architecture report', () => {
    const architecture = bundleFiles(makeResult())['architecture.md'] ?? '';
    expect(architecture).toContain('Network and external resources');
    expect(architecture).toContain('robots.txt verdict');
  });

  it('states run context where measurements are involved', () => {
    const files = bundleFiles(makeResult());
    expect(files['performance.md']).toContain('Run context');
    expect(files['performance.md']).toContain('http_only');
    expect(files['design.md']).toContain('Wait strategy');
  });

  it('explains that no security score was produced', () => {
    expect(bundleFiles(makeResult())['security.md']).toContain('No posture score was produced');
  });

  it('lists the bundle contents and status legend in the README', () => {
    const readme = bundleFiles(makeResult())['README.md'] ?? '';
    expect(readme).toContain('analysis.json');
    expect(readme).toContain('**Not detected**');
    expect(readme).toContain('not the same');
  });
});

describe('markdown safety', () => {
  it('escapes hostile content so it cannot break out of a table cell', () => {
    const result = makeResult();
    result.sections.seo = makeSection('seo', 'complete', [
      makeFinding({
        id: 'seo.metadata:title',
        value: 'Evil | ## Fake heading\n- injected bullet',
        evidence: [
          {
            kind: 'html_element',
            source: 'dom.title',
            excerpt: 'contains ``` fence and | pipe',
            location: null,
            detail: {},
          },
        ],
      }),
    ]);

    const seo = renderSectionReport(result, 'seo')?.contents ?? '';
    const tableLine = seo.split('\n').find((line) => line.includes('Evil')) ?? '';

    expect(tableLine).toContain('\\|');
    expect(tableLine).not.toContain('\n');
    expect(seo).not.toContain('\n## Fake heading');
    // A fence in an excerpt must not terminate the code block early.
    expect(seo).toContain('````');
  });

  it('never emits a cookie value', () => {
    const result = makeResult();
    result.sections.security = makeSection('security', 'complete', [
      makeFinding({
        id: 'security.cookies:session',
        category: 'cookies',
        name: 'Cookie: session_id',
        value: 'Secure; HttpOnly; SameSite=Lax',
        evidence: [
          {
            kind: 'cookie',
            source: 'http.cookies[0]',
            excerpt: 'session_id (Secure, HttpOnly, SameSite=Lax)',
            location: null,
            detail: {},
          },
        ],
      }),
    ]);

    const files = buildReportBundle(result).files;
    for (const file of files) {
      expect(file.contents).not.toMatch(/set-cookie:\s*\S+=\S+/i);
    }
  });
});

describe('determinism', () => {
  it('renders byte-identical markdown for the same result', () => {
    const result = makeResult();
    expect(renderSectionReport(result, 'seo')?.contents).toBe(
      renderSectionReport(result, 'seo')?.contents,
    );
  });

  it('sorts json keys so exports are diffable', () => {
    expect(stableStringify({ b: 1, a: { d: 2, c: 3 } })).toBe(
      '{\n  "a": {\n    "c": 3,\n    "d": 2\n  },\n  "b": 1\n}\n',
    );
  });

  it('round-trips analysis.json', () => {
    const result = makeResult();
    expect(JSON.parse(renderAnalysisJson(result))).toEqual(JSON.parse(JSON.stringify(result)));
  });
});

describe('bundleToZip', () => {
  it('packages the report files', async () => {
    const bundle = buildReportBundle(makeResult());
    const blob = await bundleToZip(bundle);

    expect(blob.type).toBe('application/zip');
    expect(blob.size).toBeGreaterThan(0);

    const text = new TextDecoder('latin1').decode(await blob.arrayBuffer());
    for (const file of bundle.files) {
      expect(text).toContain(file.path);
    }
  });

  it('includes screenshots under a fixed path', async () => {
    const bundle = buildReportBundle(makeResult());
    const blob = await bundleToZip(bundle, [
      { label: 'Viewport Shot', width: 1440, height: 900, blob: new Blob([new Uint8Array([1, 2])]) },
    ]);
    const text = new TextDecoder('latin1').decode(await blob.arrayBuffer());
    expect(text).toContain('screenshots/viewport-shot.png');
  });
});
