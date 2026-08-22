/** V2 result factories shared by component, persistence, and export tests. */
import type {
  AnalysisResult,
  Finding,
  Section,
  SectionKey,
  SectionStatus,
} from '@/types/analysis';

export function makeFinding(overrides: Partial<Finding> = {}): Finding {
  const base: Finding = {
    id: 'technology.framework:react',
    category: 'framework',
    name: 'React',
    status: 'verified',
    detected: true,
    value: 'React',
    values: [],
    unit: null,
    confidence: 'definitive',
    evidence: [
      {
        kind: 'runtime_global',
        source: 'runtime.globals.React',
        excerpt: 'React',
        location: 'https://example.test/',
        detail: {},
      },
    ],
    source: 'technology.framework',
    details: {},
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
                error_detail: 'Not available in this build.',
                missing_evidence: [],
              },
            ]
          : [
              {
                id: `${key}.analyzer`,
                version: '2.0.0',
                status: status === 'unavailable' ? 'failed' : 'completed',
                duration_ms: 3.2,
                error_code: status === 'unavailable' ? 'MISSING_EVIDENCE' : null,
                error_detail: status === 'unavailable' ? 'Required evidence was unavailable.' : null,
                missing_evidence: [],
              },
            ],
      limitations:
        status === 'complete'
          ? ['One public page was observed; private and server-side behavior is outside scope.']
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
  const designFindings = [
    makeFinding({
      id: 'accessibility.structure:document-title',
      category: 'document',
      name: 'Document title',
      value: 'Example Domain',
      source: 'accessibility.structure',
      evidence: [
        {
          kind: 'html_element',
          source: 'dom.title',
          excerpt: 'Example Domain',
          location: 'https://example.test/',
          detail: {},
        },
      ],
    }),
    makeFinding({
      id: 'design.color:background-colors',
      category: 'color',
      name: 'Background colors',
      value: 2,
      values: ['rgb(255, 255, 255)', 'rgb(20, 24, 32)'],
      unit: 'count',
      source: 'design.color',
    }),
  ];

  const technologyFindings = [
    makeFinding(),
    makeFinding({
      id: 'architecture.rendering:rendering-strategy',
      category: 'architecture',
      name: 'Rendering strategy',
      value: 'client_rendered',
      status: 'strongly_inferred',
      confidence: 'strong',
      source: 'architecture.rendering',
    }),
    makeFinding({
      id: 'technology.language:server-technology',
      category: 'server-technology',
      name: 'Server-side technology',
      status: 'not_determinable',
      detected: null,
      value: null,
      confidence: null,
      evidence: [],
      source: 'technology.language',
      reason: 'The server implementation is not exposed by public response signals.',
    }),
    makeFinding({
      id: 'ai.inference:backend:api-gateway',
      category: 'ai_inference',
      name: 'The site may use an API gateway',
      status: 'ai_inferred',
      detected: null,
      value: null,
      confidence: 'moderate',
      source: 'ai.inference',
      evidence: [
        {
          kind: 'ai_reasoning',
          source: 'ai.inference',
          excerpt: 'Observed API request routing is consistent with a gateway, but is not conclusive.',
          location: null,
          detail: {
            basis: 'architecture.runtime:api-requests, https://research.example.test/source',
          },
        },
      ],
      limitations: ['Private infrastructure cannot be confirmed from a public page.'],
    }),
  ];

  const securityFindings = [
    makeFinding({
      id: 'security.headers:hsts',
      category: 'headers',
      name: 'Strict-Transport-Security',
      value: 'max-age=31536000',
      source: 'security.headers',
      evidence: [
        {
          kind: 'http_header',
          source: 'response.headers.strict-transport-security',
          excerpt: 'max-age=31536000',
          location: 'https://example.test/',
          detail: {},
        },
      ],
    }),
  ];

  const trafficFindings = [
    makeFinding({
      id: 'traffic.popularity:domain-rank',
      category: 'popularity',
      name: 'Domain popularity rank',
      status: 'unable_to_verify',
      detected: null,
      value: null,
      confidence: null,
      evidence: [],
      source: 'traffic.popularity',
      reason: 'No traffic data provider is configured in this build.',
      limitations: ['No exact visit counts can be determined from passive observation alone.'],
    }),
    makeFinding({
      id: 'traffic.signals:analytics-services',
      category: 'analytics',
      name: 'Analytics and tracking services',
      status: 'not_detected',
      detected: false,
      value: null,
      confidence: null,
      evidence: [],
      source: 'traffic.signals',
      reason: 'No known analytics domains were observed during this visit.',
      limitations: ['Server-side analytics cannot be detected externally.'],
    }),
  ];

  const base: AnalysisResult = {
    schema_version: '2.0',
    scan: {
      scan_id: '01M0CSX29SJT518RFY2VXF91XW',
      status: 'completed',
      created_at: '2026-08-19T10:43:35.353Z',
      started_at: '2026-08-19T10:43:35.400Z',
      finished_at: '2026-08-19T10:43:35.716Z',
      duration_ms: 316.47,
      engine_version: '0.2.0',
      schema_version: '2.0',
      options: {
        include_screenshot: true,
        include_full_page_screenshot: false,
        viewport: { width: 1440, height: 900 },
        responsive_widths: [390, 768, 1440],
        sections: null,
      },
      run_context: {
        browser_name: 'Chromium',
        browser_version: '140',
        user_agent: 'WebLens/0.2.0 passive website analyzer',
        viewport: { width: 1440, height: 900 },
        device_scale_factor: 1,
        wait_strategy: 'network_idle',
        settle_reached: true,
        network_throttling: 'none',
        cpu_throttling: 'none',
        locale: 'en-US',
        timezone: 'UTC',
        collection_mode: 'browser',
      },
      stages: [
        {
          key: 'analyze',
          label: 'Analyzing evidence',
          status: 'completed',
          started_at: '2026-08-19T10:43:35.401Z',
          duration_ms: 184.6,
          error_code: null,
          error_detail: null,
          skip_reason: null,
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
      design: makeSection('design', 'complete', designFindings, {
        coverage: { cap_hit: false, elements_sampled: 42, elements_total: 42 },
        axe: null,
      }),
      technology: makeSection('technology', 'complete', technologyFindings),
      security: makeSection('security', 'complete', securityFindings, { score: null, headers: [] }),
      traffic: makeSection('traffic', 'complete', trafficFindings, {
        provider_name: null,
        provider_available: false,
      }),
    },
    quality: {
      overall: 'medium',
      overall_score: 55,
      sections: {
        design: {
          section: 'design',
          quality: 'medium',
          score: 60,
          analyzers_completed: 5,
          analyzers_total: 7,
          findings_verified: 2,
          findings_inferred: 0,
          findings_negative: 0,
          ai_fallback_recommended: false,
          reason: 'Design: 5/7 analyzers completed, 2 verified/inferred findings. Some gaps exist.',
        },
        technology: {
          section: 'technology',
          quality: 'medium',
          score: 55,
          analyzers_completed: 10,
          analyzers_total: 14,
          findings_verified: 3,
          findings_inferred: 1,
          findings_negative: 1,
          ai_fallback_recommended: false,
          reason: 'Technology: 10/14 analyzers completed, 4 verified/inferred findings. Some gaps exist.',
        },
        security: {
          section: 'security',
          quality: 'high',
          score: 75,
          analyzers_completed: 7,
          analyzers_total: 7,
          findings_verified: 1,
          findings_inferred: 0,
          findings_negative: 0,
          ai_fallback_recommended: false,
          reason: 'Security: 7/7 analyzers completed, 1 verified/inferred findings. Evidence is sufficient.',
        },
        traffic: {
          section: 'traffic',
          quality: 'low',
          score: 20,
          analyzers_completed: 2,
          analyzers_total: 2,
          findings_verified: 0,
          findings_inferred: 0,
          findings_negative: 2,
          ai_fallback_recommended: true,
          reason: 'Traffic: 2/2 analyzers completed, only 0 verified/inferred findings. AI intelligence could supplement the analysis.',
        },
      },
      ai_fallback_available: true,
      ai_fallback_sections: ['traffic'],
    },
    errors: [],
    screenshots: [],
    limitations: ['One URL was analyzed. No crawling was performed.'],
  };

  return { ...base, ...overrides };
}
