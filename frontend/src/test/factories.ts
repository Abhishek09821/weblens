/**
 * Result factories for tests.
 *
 * Shaped like real backend payloads, including the awkward parts: an unimplemented section, a
 * negative finding with a reason, and evidence attached to every asserted finding.
 */
import type {
  AnalysisResult,
  Finding,
  Section,
  SectionKey,
  SectionStatus,
} from '@/types/analysis';

export function makeFinding(overrides: Partial<Finding> = {}): Finding {
  const base: Finding = {
    id: 'seo.metadata:title',
    category: 'document',
    name: 'Document title',
    status: 'verified',
    detected: true,
    value: 'Example Domain',
    values: [],
    unit: null,
    confidence: 'definitive',
    evidence: [
      {
        kind: 'html_element',
        source: 'dom.title',
        excerpt: 'Example Domain',
        location: 'https://example.test/',
        detail: {},
      },
    ],
    source: 'seo.metadata',
    details: { length: 14 },
    limitations: [],
    reason: null,
  };
  return { ...base, ...overrides };
}

export function makeSection(
  key: SectionKey,
  status: SectionStatus,
  findings: Finding[] = [],
  data: unknown = null,
): Section {
  return {
    meta: {
      key,
      status,
      analyzers:
        status === 'not_implemented'
          ? [
              {
                id: `${key}.placeholder`,
                version: '0.0.0',
                status: 'not_implemented',
                duration_ms: null,
                error_code: null,
                error_detail: 'Planned for phase 3.',
                missing_evidence: [],
              },
            ]
          : [
              {
                id: `${key}.metadata`,
                version: '1.0.0',
                status: 'completed',
                duration_ms: 3.2,
                error_code: null,
                error_detail: null,
                missing_evidence: [],
              },
            ],
      limitations:
        status === 'complete'
          ? ['Observed in the HTML as served. Metadata added by client-side JavaScript would not appear.']
          : [],
      unavailable_reason:
        status === 'not_implemented'
          ? 'No analyzer for this section ships in this build yet.'
          : status === 'unavailable'
            ? 'Every analyzer for this section failed.'
            : status === 'skipped'
              ? 'This section was excluded from the scan request.'
              : null,
    },
    findings,
    interpretations: [],
    data,
  };
}

export function makeResult(overrides: Partial<AnalysisResult> = {}): AnalysisResult {
  const seoFindings: Finding[] = [
    makeFinding(),
    makeFinding({
      id: 'seo.metadata:meta-description',
      name: 'Meta description',
      status: 'not_detected',
      detected: false,
      value: null,
      confidence: null,
      evidence: [],
      details: {},
      reason: 'No <meta name="description"> with content was present.',
    }),
  ];

  const base: AnalysisResult = {
    schema_version: '1.0',
    scan: {
      scan_id: '01M0CSX29SJT518RFY2VXF91XW',
      status: 'completed',
      created_at: '2026-08-19T10:43:35.353Z',
      started_at: '2026-08-19T10:43:35.400Z',
      finished_at: '2026-08-19T10:43:35.716Z',
      duration_ms: 316.47,
      engine_version: '0.1.0',
      schema_version: '1.0',
      options: {
        include_screenshot: true,
        include_full_page_screenshot: false,
        viewport: { width: 1440, height: 900 },
        responsive_widths: [390, 768, 1440],
        sections: null,
      },
      run_context: {
        browser_name: null,
        browser_version: null,
        user_agent: 'WebLens/0.1.0 (+https://github.com/weblens; passive website analyzer)',
        viewport: { width: 1440, height: 900 },
        device_scale_factor: 1,
        wait_strategy: 'http_response_only',
        settle_reached: null,
        network_throttling: 'none',
        cpu_throttling: 'none',
        locale: 'en-US',
        timezone: 'UTC',
        collection_mode: 'http_only',
      },
      stages: [
        {
          key: 'http_probe',
          label: 'Fetching document',
          status: 'completed',
          started_at: '2026-08-19T10:43:35.401Z',
          duration_ms: 184.6,
          error_code: null,
          error_detail: null,
          skip_reason: null,
        },
        {
          key: 'a11y_capture',
          label: 'Running accessibility rules',
          status: 'skipped',
          started_at: null,
          duration_ms: null,
          error_code: null,
          error_detail: null,
          skip_reason: 'Not implemented in this build.',
        },
      ],
    },
    target: {
      requested_url: 'example.test',
      normalized_url: 'https://example.test/',
      final_url: 'https://example.test/',
      host: 'example.test',
      port: 443,
      scheme: 'https',
      resolved_ips: ['93.184.216.34'],
      redirect_chain: [],
      http_status: 200,
      document_title: 'Example Domain',
      robots: {
        url: 'https://example.test/robots.txt',
        fetched: true,
        status: 404,
        allowed: true,
        matched_directive: null,
        user_agent_group: null,
        sitemaps: [],
        error: null,
      },
    },
    sections: {
      design: makeSection('design', 'not_implemented'),
      technology: makeSection('technology', 'not_implemented'),
      security: makeSection('security', 'not_implemented'),
      performance: makeSection('performance', 'not_implemented'),
      accessibility: makeSection('accessibility', 'not_implemented'),
      seo: makeSection('seo', 'complete', seoFindings, {
        metadata: {
          title: 'Example Domain',
          title_length: 14,
          description: null,
          description_length: null,
          canonical: null,
          robots_meta: null,
          viewport_meta: null,
          charset: 'utf-8',
          lang: 'en',
          h1_texts: ['Example Domain'],
          open_graph: [],
          twitter: [],
          hreflang: [],
          favicons: [],
        },
        indexability: null,
        structured_data: [],
      }),
      architecture: makeSection('architecture', 'not_implemented'),
      network: makeSection('network', 'not_implemented'),
    },
    errors: [],
    screenshots: [],
    limitations: [
      'One URL was analyzed. No crawling was performed, so findings describe this page only.',
      'This scan used HTTP collection only: no browser was used.',
    ],
  };

  return { ...base, ...overrides };
}
