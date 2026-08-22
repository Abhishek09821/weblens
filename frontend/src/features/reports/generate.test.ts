import { describe, expect, it } from 'vitest';

import { makeFinding, makeResult, makeSection } from '@/test/factories';
import type { AnalysisResult } from '@/types/analysis';

import { bundleToZip } from './bundle';
import { buildReportBundle, renderSectionReport } from './generate';
import { renderAnalysisJson, stableStringify } from './json';
import { REPORT_DEFINITIONS } from './markdown/renderers';
import { generateCompletePdf, generateSectionPdf } from './pdf';

function bundleFiles(result: AnalysisResult): Record<string, string> {
  return Object.fromEntries(buildReportBundle(result).files.map((file) => [file.path, file.contents]));
}

describe('V2 report generation', () => {
  it('produces exactly four Markdown reports plus analysis.json', () => {
    expect(Object.keys(bundleFiles(makeResult())).sort()).toEqual([
      'analysis.json',
      'design.md',
      'security.md',
      'techstack.md',
      'traffic.md',
    ]);
    expect(REPORT_DEFINITIONS.map((definition) => definition.section)).toEqual([
      'design',
      'technology',
      'security',
      'traffic',
    ]);
  });

  it('names the archive after the host and scan time', () => {
    expect(buildReportBundle(makeResult()).suggestedName).toMatch(
      /^weblens-example\.test-\d{8}-\d{6}$/,
    );
  });

  it('includes scan metadata and target in every Markdown file', () => {
    const files = bundleFiles(makeResult());
    for (const definition of REPORT_DEFINITIONS) {
      const contents = files[definition.file];
      expect(contents, definition.file).toContain('01M0CSX29SJT518RFY2VXF91XW');
      expect(contents, definition.file).toContain('https://example.test/');
      expect(contents, definition.file).toContain('Engine version');
      expect(contents, definition.file).toContain('Schema version');
    }
  });

  it('structures design.md for reconstruction work', () => {
    const design = bundleFiles(makeResult())['design.md'];
    for (const heading of [
      'Page Structure',
      'Navigation',
      'Layout System',
      'Responsive Behavior',
      'Typography',
      'Colors',
      'Spacing',
      'Components and Patterns',
      'Media',
      'Motion',
      'AI / Research Verdicts',
      'Limitations',
    ]) {
      expect(design).toContain(`## ${heading}`);
    }
  });

  it('structures techstack.md with status fidelity and explicit AI hypotheses', () => {
    const tech = bundleFiles(makeResult())['techstack.md'];
    expect(tech).toContain('# Website Technical Stack');
    expect(tech).toContain('## Frontend');
    expect(tech).toContain('## Rendering');
    expect(tech).toContain('Strongly Supported');
    expect(tech).toContain('## Architecture Hypothesis');
    expect(tech).toContain('AI Inferred — this is a hypothesis, not a verified detection');
    expect(tech).toContain('Reasoning');
    expect(tech).toContain('https://research.example.test/source');
    expect(tech).toContain('## Unknown / Not Publicly Determinable');
  });

  it('reports unavailable traffic without fabricating an estimate', () => {
    const traffic = bundleFiles(makeResult())['traffic.md'];
    expect(traffic).toContain('Traffic estimates are unavailable');
    expect(traffic).toContain('No traffic data provider is configured');
    expect(traffic).toContain('Unable to verify');
    expect(traffic).not.toMatch(/\b0\s+(visits|users|sessions)\b/i);
  });

  it('never prints internal confidence values beside claims', () => {
    const files = bundleFiles(makeResult());
    for (const [path, contents] of Object.entries(files)) {
      if (path === 'analysis.json') continue;
      expect(contents.toLowerCase(), path).not.toContain('definitive');
      expect(contents.toLowerCase(), path).not.toContain('moderate confidence');
      expect(contents, path).not.toMatch(/\d+%\s*(confident|certain)/i);
    }
  });

  it('includes evidence for deterministic and AI-inferred claims', () => {
    const tech = bundleFiles(makeResult())['techstack.md'];
    expect(tech).toContain('Observed evidence');
    expect(tech).toContain('runtime.globals.React');
    expect(tech).toContain('ai.inference');
  });

  it('omits evidence when asked', () => {
    const file = renderSectionReport(makeResult(), 'technology', {
      includeEvidence: false,
      maxEvidencePerFinding: 0,
    });
    expect(file.contents).not.toContain('Observed evidence');
  });

  it('still writes an explained file for an unavailable section', () => {
    const result = makeResult();
    result.sections.design = makeSection('design', 'unavailable');
    const design = bundleFiles(result)['design.md'];
    expect(design).toContain('No findings available');
    expect(design).toContain('Every analyzer for this section failed');
  });
});

describe('Markdown safety', () => {
  it('escapes hostile content so it cannot break out of a table cell', () => {
    const result = makeResult();
    result.sections.design = makeSection('design', 'complete', [
      makeFinding({
        id: 'design.color:hostile',
        category: 'color',
        name: 'Hostile color label',
        value: 'Evil | ## Fake heading\n- injected bullet',
        source: 'design.color',
        evidence: [
          {
            kind: 'computed_style',
            source: 'styles.sample',
            excerpt: 'contains ``` fence and | pipe',
            location: null,
            detail: {},
          },
        ],
      }),
    ]);

    const markdown = renderSectionReport(result, 'design').contents;
    const tableLine = markdown.split('\n').find((line) => line.includes('Evil')) ?? '';
    expect(tableLine).toContain('\\|');
    expect(tableLine).not.toContain('\n');
    expect(markdown).not.toContain('\n## Fake heading');
    expect(markdown).toContain('````');
  });

  it('never emits a raw cookie value', () => {
    const result = makeResult();
    result.sections.security = makeSection('security', 'complete', [
      makeFinding({
        id: 'security.cookies:session',
        category: 'cookies',
        name: 'Session cookie attributes',
        value: 'Secure; HttpOnly; SameSite=Lax',
        source: 'security.cookies',
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
    ], { score: null, headers: [] });

    for (const file of buildReportBundle(result).files) {
      expect(file.contents).not.toMatch(/set-cookie:\s*\S+=\S+/i);
    }
  });
});

describe('determinism and machine-readable export', () => {
  it('renders byte-identical Markdown for the same result', () => {
    const result = makeResult();
    expect(renderSectionReport(result, 'technology').contents).toBe(
      renderSectionReport(result, 'technology').contents,
    );
  });

  it('sorts JSON keys so exports are diffable', () => {
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
  it('packages all five report files', async () => {
    const bundle = buildReportBundle(makeResult());
    const blob = await bundleToZip(bundle);
    expect(blob.type).toBe('application/zip');
    expect(blob.size).toBeGreaterThan(0);

    const text = new TextDecoder('latin1').decode(await blob.arrayBuffer());
    for (const file of bundle.files) expect(text).toContain(file.path);
  });

  it('preserves stored screenshots under a fixed supporting-evidence path', async () => {
    const bundle = buildReportBundle(makeResult());
    const blob = await bundleToZip(bundle, [
      { label: 'Viewport Shot', width: 1440, height: 900, blob: new Blob([new Uint8Array([1, 2])]) },
    ]);
    const text = new TextDecoder('latin1').decode(await blob.arrayBuffer());
    expect(text).toContain('screenshots/viewport-shot.png');
  });
});

describe('PDF exports', () => {
  it('renders each V2 section and the complete four-report document', () => {
    const result = makeResult();
    for (const definition of REPORT_DEFINITIONS) {
      const pdf = generateSectionPdf(result, definition.section);
      expect(pdf.type).toBe('application/pdf');
      expect(pdf.size).toBeGreaterThan(0);
    }

    const complete = generateCompletePdf(result);
    expect(complete.type).toBe('application/pdf');
    expect(complete.size).toBeGreaterThan(0);
  });
});