/**
 * Technology stack presentation model.
 *
 * Groups raw technology findings into meaningful categories for the UI.
 * Every item traces back to one or more findings — nothing is invented.
 */
import type { Finding, AnalysisResult } from '@/types/analysis';

export interface TechCategory {
  title: string;
  items: TechItem[];
}

export interface TechItem {
  name: string;
  status: 'verified' | 'inferred';
  description: string;
  signals: string[];
  findingId: string;
  evidence: Finding['evidence'];
}

const CATEGORY_MAP: Record<string, string> = {
  // Framework
  'React': 'Frontend',
  'Next.js': 'Frontend',
  'Vue.js': 'Frontend',
  'Nuxt': 'Frontend',
  'Angular': 'Frontend',
  'Svelte': 'Frontend',
  'Gatsby': 'Frontend',
  'Remix': 'Frontend',
  'Ember.js': 'Frontend',
  'Backbone.js': 'Frontend',
  'Turbo/Hotwire': 'Frontend',
  'Stimulus': 'Frontend',
  'Alpine.js': 'Frontend',
  'HTMX': 'Frontend',
  // Libraries
  'jQuery': 'Frontend',
  'Lodash': 'Frontend',
  'GSAP': 'Frontend',
  'Three.js': 'Frontend',
  // Styling
  'Tailwind CSS': 'Styling',
  'Bootstrap': 'Styling',
  'Bulma': 'Styling',
  'Material UI': 'Styling',
  'Chakra UI': 'Styling',
  'Styled Components': 'Styling',
  'CSS Modules': 'Styling',
  'Emotion': 'Styling',
  'Foundation': 'Styling',
  'Ant Design': 'Styling',
  // CMS / E-commerce
  'WordPress': 'Platform',
  'Drupal': 'Platform',
  'Shopify': 'Platform',
  'WooCommerce': 'Platform',
  // Build tools
  'Webpack': 'Build & Tooling',
  'Vite': 'Build & Tooling',
  // Server
  'PHP': 'Backend / Server',
  'ASP.NET': 'Backend / Server',
  'Express': 'Backend / Server',
  'Apache': 'Backend / Server',
  'nginx': 'Backend / Server',
  'LiteSpeed': 'Backend / Server',
  'Microsoft-IIS': 'Backend / Server',
  'Caddy': 'Backend / Server',
  'Phusion Passenger': 'Backend / Server',
  // Infrastructure
  'Cloudflare': 'Infrastructure',
  'Vercel': 'Infrastructure',
  'Netlify': 'Infrastructure',
  'AWS CloudFront': 'Infrastructure',
  'Fastly': 'Infrastructure',
  'GitHub Pages': 'Infrastructure',
  // Analytics & Third-party
  'Google Analytics': 'Third-Party Services',
  'Google Tag Manager': 'Third-Party Services',
  'Facebook Pixel': 'Third-Party Services',
  'Google Fonts': 'Third-Party Services',
  'Adobe Fonts': 'Third-Party Services',
};

const TECH_DESCRIPTIONS: Record<string, string> = {
  'React': 'A JavaScript UI library for building component-based interfaces.',
  'Next.js': 'A React meta-framework with server-side rendering and routing.',
  'Vue.js': 'A progressive JavaScript framework for building user interfaces.',
  'Nuxt': 'A Vue.js meta-framework with SSR and static site generation.',
  'Angular': 'A TypeScript-based web application framework.',
  'Svelte': 'A compiler-based UI framework with no virtual DOM.',
  'jQuery': 'A legacy JavaScript library for DOM manipulation and AJAX.',
  'Tailwind CSS': 'A utility-first CSS framework.',
  'Bootstrap': 'A component-based CSS framework with pre-built UI elements.',
  'Cloudflare': 'A global CDN and security platform.',
  'Vercel': 'A frontend cloud platform optimized for Next.js deployments.',
  'Netlify': 'A platform for deploying and hosting modern web applications.',
  'Google Analytics': 'Web analytics service for tracking visitor behavior.',
  'Google Tag Manager': 'A tag management system for marketing and analytics scripts.',
  'WordPress': 'A content management system powering the website.',
  'Webpack': 'A JavaScript module bundler used to build the application.',
  'Vite': 'A fast build tool and development server for modern web projects.',
  'nginx': 'A high-performance web server and reverse proxy.',
  'Apache': 'A widely-used open-source web server.',
  'PHP': 'A server-side scripting language.',
  'Express': 'A minimal Node.js web application framework.',
  'Turbo/Hotwire': 'A set of libraries for fast page transitions without heavy JavaScript.',
  'Stimulus': 'A modest JavaScript framework for enhancing server-rendered HTML.',
  'Alpine.js': 'A lightweight reactive JavaScript framework for adding behavior to markup.',
  'HTMX': 'A library that allows accessing modern browser features directly from HTML.',
  'GSAP': 'A professional-grade animation library.',
  'Shopify': 'An e-commerce platform powering the online store.',
  'GitHub Pages': 'Static site hosting provided by GitHub.',
  'Google Fonts': 'A web font service delivering typefaces to the page.',
};

export function buildTechPresentation(result: AnalysisResult): TechCategory[] {
  const techFindings = result.sections.technology.findings;
  const archFindings = result.sections.architecture.findings;

  const allFindings = [...techFindings, ...archFindings].filter(
    (f) => (f.status === 'verified' || f.status === 'inferred') && f.detected,
  );

  const categories = new Map<string, TechItem[]>();

  for (const finding of allFindings) {
    // Skip generic "not detected" or summary findings
    if (finding.name === 'Server-side technology' || finding.name === 'Hosting platform') continue;
    if (finding.source === 'architecture.rendering') continue; // Handled separately
    if (finding.source === 'architecture.runtime') continue; // Handled separately

    const name = finding.name.replace('Platform: ', '');
    const category = CATEGORY_MAP[name] ?? inferCategory(finding);
    const item: TechItem = {
      name,
      status: finding.status === 'verified' ? 'verified' : 'inferred',
      description: TECH_DESCRIPTIONS[name] ?? `Detected from observable signals on this page.`,
      signals: buildSignalSummary(finding),
      findingId: finding.id,
      evidence: finding.evidence,
    };

    const group = categories.get(category) ?? [];
    group.push(item);
    categories.set(category, group);
  }

  // Sort categories in presentation order
  const ORDER = ['Frontend', 'Styling', 'Backend / Server', 'Infrastructure', 'Platform', 'Build & Tooling', 'Third-Party Services', 'Other'];
  return ORDER
    .filter((title) => categories.has(title))
    .map((title) => ({ title, items: categories.get(title)! }));
}

function inferCategory(finding: Finding): string {
  if (finding.source.includes('platform')) return 'Infrastructure';
  if (finding.source.includes('language')) return 'Backend / Server';
  if (finding.source.includes('styling')) return 'Styling';
  if (finding.source.includes('framework')) return 'Frontend';
  if (finding.source.includes('stack')) return 'Other';
  return 'Other';
}

function buildSignalSummary(finding: Finding): string[] {
  const signals: string[] = [];
  for (const ev of finding.evidence.slice(0, 3)) {
    if (ev.excerpt) {
      // Make evidence human-readable
      const readable = humanizeEvidence(ev.kind, ev.excerpt);
      signals.push(readable);
    }
  }
  return signals;
}

function humanizeEvidence(kind: string, excerpt: string): string {
  switch (kind) {
    case 'http_header':
      return `Response header contains "${excerpt.slice(0, 60)}"`;
    case 'script_url':
      return `Script loaded from ${excerpt.slice(0, 80)}`;
    case 'runtime_global':
      return `Runtime global \`${excerpt}\` is present`;
    case 'network_request':
      return `Network request to ${excerpt.slice(0, 80)}`;
    case 'html_attribute':
      return `HTML attribute \`${excerpt}\` found in markup`;
    case 'html_element':
      return `HTML element matches pattern`;
    case 'meta_tag':
      return `Meta tag declares "${excerpt.slice(0, 60)}"`;
    case 'stylesheet_url':
      return `Stylesheet loaded from ${excerpt.slice(0, 80)}`;
    case 'computed_style':
      return `CSS custom property \`${excerpt}\` detected`;
    default:
      return excerpt.slice(0, 80);
  }
}
