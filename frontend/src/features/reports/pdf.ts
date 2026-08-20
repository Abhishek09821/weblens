/**
 * Professional PDF report generation.
 *
 * Produces human-readable reports with:
 * - Color swatches rendered directly in the PDF
 * - Typography presented as a design system
 * - Technology grouped by category with explanations
 * - Security score with visual progress bar
 * - Performance metrics in clear cards
 * - Accessibility issues explained in plain language
 *
 * Every piece of data comes from the structured analysis result.
 * Nothing is invented. The PDF should be understandable enough
 * that someone could use it to understand or recreate the website.
 */
import { jsPDF } from 'jspdf';
import 'jspdf-autotable';

import { sectionLabel } from '@/lib/format/labels';
import { formatBytes, formatDuration, formatTimestamp } from '@/lib/format/values';
import { buildDesignPresentation } from '@/lib/presentation/design';
import { buildOverview } from '@/lib/presentation/overview';
import { buildTechPresentation } from '@/lib/presentation/technology';
import { securityScoreSchema } from '@/types/analysis';
import type { AnalysisResult, SectionKey } from '@/types/analysis';

// --- Constants ---
const PAGE_W = 210;
const PAGE_H = 297;
const M = 14; // margin
const CW = PAGE_W - 2 * M; // content width
const PRIMARY_COLOR: [number, number, number] = [41, 128, 185];
const DARK: [number, number, number] = [30, 30, 30];
const GRAY: [number, number, number] = [100, 100, 100];
const LIGHT_GRAY: [number, number, number] = [180, 180, 180];
const BG_LIGHT: [number, number, number] = [245, 247, 250];

interface W {
  doc: jsPDF;
  y: number;
}

function w(doc: jsPDF): W {
  return { doc, y: M };
}

function np(p: W, needed = 20): void {
  if (p.y + needed > PAGE_H - M - 10) {
    p.doc.addPage();
    p.y = M;
  }
}

// --- Text helpers ---
function title(p: W, text: string): void {
  np(p, 16);
  p.doc.setFontSize(20);
  p.doc.setFont('helvetica', 'bold');
  p.doc.setTextColor(...DARK);
  p.doc.text(text, M, p.y);
  p.y += 10;
}

function h2(p: W, text: string): void {
  np(p, 14);
  p.y += 5;
  p.doc.setFontSize(14);
  p.doc.setFont('helvetica', 'bold');
  p.doc.setTextColor(...PRIMARY_COLOR);
  p.doc.text(text, M, p.y);
  p.y += 7;
  // underline
  p.doc.setDrawColor(...PRIMARY_COLOR);
  p.doc.setLineWidth(0.3);
  p.doc.line(M, p.y - 2, M + CW, p.y - 2);
  p.y += 2;
}

function h3(p: W, text: string): void {
  np(p, 12);
  p.y += 3;
  p.doc.setFontSize(11);
  p.doc.setFont('helvetica', 'bold');
  p.doc.setTextColor(...DARK);
  p.doc.text(text, M, p.y);
  p.y += 6;
}

function body(p: W, text: string, indent = 0): void {
  p.doc.setFontSize(9.5);
  p.doc.setFont('helvetica', 'normal');
  p.doc.setTextColor(...DARK);
  const lines = p.doc.splitTextToSize(text, CW - indent);
  for (const line of lines) {
    np(p);
    p.doc.text(line, M + indent, p.y);
    p.y += 4.5;
  }
}

function gray(p: W, text: string, indent = 0): void {
  p.doc.setFontSize(8.5);
  p.doc.setFont('helvetica', 'normal');
  p.doc.setTextColor(...GRAY);
  const lines = p.doc.splitTextToSize(text, CW - indent);
  for (const line of lines) {
    np(p);
    p.doc.text(line, M + indent, p.y);
    p.y += 4;
  }
  p.doc.setTextColor(...DARK);
}

function bullet(p: W, text: string, indent = 4): void {
  np(p);
  p.doc.setFontSize(9);
  p.doc.setFont('helvetica', 'normal');
  p.doc.setTextColor(...DARK);
  p.doc.text('•', M + indent - 3, p.y);
  const lines = p.doc.splitTextToSize(text, CW - indent - 2);
  for (let i = 0; i < lines.length; i++) {
    if (i > 0) np(p);
    p.doc.text(lines[i], M + indent, p.y);
    p.y += 4.5;
  }
}

function kv(p: W, key: string, value: string | number | null | undefined): void {
  if (value == null || value === '') return;
  np(p);
  p.doc.setFontSize(9);
  p.doc.setFont('helvetica', 'bold');
  p.doc.setTextColor(...GRAY);
  p.doc.text(key, M, p.y);
  p.doc.setFont('helvetica', 'normal');
  p.doc.setTextColor(...DARK);
  p.doc.text(String(value), M + 38, p.y);
  p.y += 5;
}

function spacer(p: W, h = 3): void { p.y += h; }

function separator(p: W): void {
  p.y += 3;
  p.doc.setDrawColor(...LIGHT_GRAY);
  p.doc.setLineWidth(0.2);
  p.doc.line(M, p.y, M + CW, p.y);
  p.y += 5;
}

// --- Color swatch ---
function colorSwatch(p: W, colorStr: string, hex: string | null, x: number, y: number): number {
  const rgb = parseRgb(colorStr);
  if (rgb) {
    p.doc.setFillColor(rgb[0], rgb[1], rgb[2]);
  } else {
    p.doc.setFillColor(200, 200, 200);
  }
  p.doc.roundedRect(x, y - 3, 8, 8, 1, 1, 'F');
  p.doc.setFontSize(7);
  p.doc.setFont('helvetica', 'normal');
  p.doc.setTextColor(...DARK);
  p.doc.text(hex ?? colorStr.slice(0, 20), x + 10, y + 1.5);
  return 30; // width consumed
}

function parseRgb(color: string): [number, number, number] | null {
  const m = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (m) return [parseInt(m[1]), parseInt(m[2]), parseInt(m[3])];
  if (color.startsWith('#') && color.length >= 7) {
    return [parseInt(color.slice(1, 3), 16), parseInt(color.slice(3, 5), 16), parseInt(color.slice(5, 7), 16)];
  }
  return null;
}

// --- Badge ---
function badge(p: W, text: string, color: [number, number, number], x: number, y: number): number {
  p.doc.setFontSize(7);
  const tw = p.doc.getTextWidth(text) + 4;
  p.doc.setFillColor(color[0], color[1], color[2]);
  p.doc.roundedRect(x, y - 3, tw + 2, 5, 1, 1, 'F');
  p.doc.setTextColor(255, 255, 255);
  p.doc.text(text, x + 2, y);
  p.doc.setTextColor(...DARK);
  return tw + 4;
}

// --- Metric box ---
function metricBox(p: W, label: string, value: string, x: number, boxW: number): void {
  np(p, 20);
  p.doc.setFillColor(...BG_LIGHT);
  p.doc.roundedRect(x, p.y - 2, boxW - 2, 16, 2, 2, 'F');
  p.doc.setFontSize(12);
  p.doc.setFont('helvetica', 'bold');
  p.doc.setTextColor(...DARK);
  p.doc.text(value, x + 4, p.y + 5);
  p.doc.setFontSize(7.5);
  p.doc.setFont('helvetica', 'normal');
  p.doc.setTextColor(...GRAY);
  p.doc.text(label, x + 4, p.y + 11);
}

// =====================================================
// SECTION RENDERERS
// =====================================================

function renderCoverPage(p: W, result: AnalysisResult): void {
  const overview = buildOverview(result);

  p.y = 40;
  p.doc.setFontSize(28);
  p.doc.setFont('helvetica', 'bold');
  p.doc.setTextColor(...PRIMARY_COLOR);
  p.doc.text('WebLens', M, p.y);
  p.y += 8;
  p.doc.setFontSize(14);
  p.doc.setFont('helvetica', 'normal');
  p.doc.setTextColor(...GRAY);
  p.doc.text('Website Technical Intelligence Report', M, p.y);
  p.y += 20;

  p.doc.setFontSize(22);
  p.doc.setFont('helvetica', 'bold');
  p.doc.setTextColor(...DARK);
  p.doc.text(result.target.host, M, p.y);
  p.y += 10;

  p.doc.setFontSize(10);
  p.doc.setFont('helvetica', 'normal');
  p.doc.setTextColor(...GRAY);
  p.doc.text(result.target.final_url ?? result.target.normalized_url, M, p.y);
  p.y += 15;

  separator(p);

  kv(p, 'Scanned', formatTimestamp(result.scan.finished_at ?? result.scan.created_at));
  kv(p, 'Duration', formatDuration(result.scan.duration_ms));
  kv(p, 'Engine', `WebLens ${result.scan.engine_version}`);
  kv(p, 'Collection', result.scan.run_context?.collection_mode ?? 'browser');
  kv(p, 'HTTP Status', result.target.http_status);
  spacer(p, 10);

  // Quick stats
  if (overview.security.percentage !== null) {
    h3(p, 'Security Posture');
    body(p, `${overview.security.percentage}% — ${overview.security.bandPhrase ?? ''}`);
    spacer(p, 3);
  }

  if (overview.technology.detected.length > 0) {
    h3(p, 'Detected Technologies');
    body(p, overview.technology.detected.join(', '));
    spacer(p, 3);
  }

  if (overview.performance.ttfb !== null) {
    h3(p, 'Performance');
    const parts: string[] = [];
    if (overview.performance.ttfb) parts.push(`TTFB: ${formatDuration(overview.performance.ttfb)}`);
    if (overview.performance.fcp) parts.push(`FCP: ${formatDuration(overview.performance.fcp)}`);
    if (overview.performance.transferBytes) parts.push(`Transfer: ${formatBytes(overview.performance.transferBytes)}`);
    if (overview.performance.requestCount) parts.push(`${overview.performance.requestCount} requests`);
    body(p, parts.join('  •  '));
  }
}

function renderDesignSection(p: W, result: AnalysisResult): void {
  h2(p, 'Design Analysis');
  const design = buildDesignPresentation(result);

  // Summary
  body(p, design.summary);
  spacer(p, 5);

  // Colors with actual swatches
  if (design.colors.available) {
    h3(p, 'Color System');

    if (design.colors.backgrounds.length > 0) {
      gray(p, 'Background Colors');
      let x = M;
      let row = 0;
      for (const color of design.colors.backgrounds.slice(0, 8)) {
        if (x + 32 > M + CW) { x = M; p.y += 12; np(p, 12); }
        colorSwatch(p, color.value, color.hex, x, p.y);
        x += 32;
        row++;
      }
      p.y += row > 0 ? 12 : 0;
    }

    if (design.colors.texts.length > 0) {
      gray(p, 'Text Colors');
      let x = M;
      for (const color of design.colors.texts.slice(0, 8)) {
        if (x + 32 > M + CW) { x = M; p.y += 12; np(p, 12); }
        colorSwatch(p, color.value, color.hex, x, p.y);
        x += 32;
      }
      p.y += 12;
    }
    spacer(p, 3);
  }

  // Typography
  if (design.typography.available) {
    h3(p, 'Typography');
    if (design.typography.loadedFonts.length > 0) {
      body(p, `Primary fonts: ${design.typography.loadedFonts.join(', ')}`);
    }
    if (design.typography.weights.length > 0) {
      body(p, `Font weights: ${design.typography.weights.join(', ')}`);
    }
    if (design.typography.sizes.length > 0) {
      body(p, `Type scale: ${design.typography.sizes.slice(0, 8).join(', ')}`);
    }
    if (design.typography.lineHeights.length > 0) {
      body(p, `Line heights: ${design.typography.lineHeights.join(', ')}`);
    }
    spacer(p, 3);
  }

  // Layout
  if (design.layout.available) {
    h3(p, 'Layout & Spacing');
    if (design.layout.displayTypes.length > 0) {
      body(p, `Layout methods: ${design.layout.displayTypes.join(', ')}`);
    }
    if (design.layout.borderRadii.length > 0) {
      body(p, `Border radius values: ${design.layout.borderRadii.join(', ')}`);
    }
    if (design.layout.shadows.length > 0) {
      body(p, `Box shadows: ${design.layout.shadows.length} distinct shadow styles`);
    }
    if (design.layout.gaps.length > 0) {
      body(p, `Spacing/gap values: ${design.layout.gaps.join(', ')}`);
    }
    if (design.layout.breakpoints.length > 0) {
      body(p, `Responsive breakpoints: ${design.layout.breakpoints.length} media queries detected`);
    }
    spacer(p, 3);
  }

  // Motion
  if (design.motion.available) {
    h3(p, 'Motion & Animation');
    if (design.motion.transitions.length > 0) {
      body(p, `${design.motion.transitions.length} CSS transition patterns`);
    }
    if (design.motion.keyframeCount && design.motion.keyframeCount > 0) {
      body(p, `${design.motion.keyframeCount} @keyframes animation definitions`);
    }
  }

  // Media
  if (design.media.available) {
    h3(p, 'Media & Images');
    const parts: string[] = [];
    if (design.media.imageCount) parts.push(`${design.media.imageCount} images`);
    if (design.media.svgCount) parts.push(`${design.media.svgCount} SVG elements`);
    if (design.media.videoCount) parts.push(`${design.media.videoCount} videos`);
    if (design.media.lazyLoaded) parts.push(`${design.media.lazyLoaded} lazy-loaded`);
    if (parts.length > 0) body(p, parts.join('  •  '));
    if (design.media.formats.length > 0) {
      body(p, `Image formats: ${design.media.formats.join(', ')}`);
    }
  }
}

function renderTechnologySection(p: W, result: AnalysisResult): void {
  h2(p, 'Technology Stack');

  const categories = buildTechPresentation(result);
  if (categories.length === 0) {
    body(p, 'No technologies could be positively identified from observable signals. This does not mean no technology is in use — server-rendered or heavily bundled technologies are frequently invisible from the outside.');
    return;
  }

  for (const cat of categories) {
    h3(p, cat.title);
    for (const item of cat.items) {
      np(p, 14);
      // Name + badge
      p.doc.setFontSize(10);
      p.doc.setFont('helvetica', 'bold');
      p.doc.setTextColor(...DARK);
      p.doc.text(item.name, M + 2, p.y);
      const nw = p.doc.getTextWidth(item.name);
      badge(p, item.status === 'verified' ? 'Verified' : 'Inferred',
        item.status === 'verified' ? [39, 174, 96] : [243, 156, 18],
        M + 2 + nw + 3, p.y);
      p.y += 5;

      // Description
      gray(p, item.description, 2);

      // Signals
      if (item.signals.length > 0) {
        gray(p, `Evidence: ${item.signals[0]}`, 2);
      }
      p.y += 2;
    }
    spacer(p, 2);
  }

  // Rendering strategy
  const rendering = buildOverview(result).rendering;
  if (rendering.strategy) {
    h3(p, 'Rendering Strategy');
    body(p, `${rendering.certainty === 'Inferred' ? 'Likely: ' : ''}${rendering.strategy}`);
    if (rendering.certainty === 'Inferred') {
      gray(p, 'This is inferred from indirect signals and may not be definitive.');
    }
  }
}

function renderSecuritySection(p: W, result: AnalysisResult): void {
  h2(p, 'Security Analysis');

  const section = result.sections.security;
  const raw = section.data && typeof section.data === 'object'
    ? (section.data as { score?: unknown }).score : undefined;
  const parsed = securityScoreSchema.safeParse(raw);

  if (parsed.success) {
    const score = parsed.data;

    // Score display
    np(p, 25);
    p.doc.setFillColor(...BG_LIGHT);
    p.doc.roundedRect(M, p.y - 3, CW, 22, 2, 2, 'F');
    p.doc.setFontSize(24);
    p.doc.setFont('helvetica', 'bold');
    p.doc.setTextColor(...PRIMARY_COLOR);
    p.doc.text(`${score.percentage}%`, M + 5, p.y + 8);
    p.doc.setFontSize(11);
    p.doc.setFont('helvetica', 'normal');
    p.doc.setTextColor(...DARK);
    p.doc.text(score.band_phrase, M + 35, p.y + 5);
    p.doc.setFontSize(8);
    p.doc.setTextColor(...GRAY);
    p.doc.text(`${score.points_awarded} / ${score.points_applicable} points  •  methodology ${score.methodology_version}`, M + 35, p.y + 12);
    p.y += 25;

    // Progress bar
    np(p, 8);
    p.doc.setFillColor(230, 230, 230);
    p.doc.roundedRect(M, p.y, CW, 3, 1, 1, 'F');
    p.doc.setFillColor(...PRIMARY_COLOR);
    p.doc.roundedRect(M, p.y, CW * (score.percentage / 100), 3, 1, 1, 'F');
    p.y += 8;

    // Disclaimer
    gray(p, score.disclaimer);
    spacer(p, 5);

    // Strong controls
    const passing = score.rules.filter(r => r.outcome === 'pass');
    const failing = score.rules.filter(r => r.outcome === 'fail');

    if (passing.length > 0) {
      h3(p, 'Strong Controls');
      for (const rule of passing) {
        bullet(p, `${rule.title} — ${rule.rationale}`);
      }
      spacer(p, 3);
    }

    if (failing.length > 0) {
      h3(p, 'Missing / Weaker Controls');
      for (const rule of failing) {
        bullet(p, `${rule.title} — ${rule.rationale}`);
      }
      spacer(p, 3);
    }

    // Excluded
    if (score.excluded_rules.length > 0) {
      h3(p, 'Not Evaluated');
      for (const rule of score.excluded_rules) {
        gray(p, `${rule.id}: ${rule.reason}`, 4);
      }
    }
  } else {
    body(p, 'Security posture score was not available for this scan.');
  }
}

function renderPerformanceSection(p: W, result: AnalysisResult): void {
  h2(p, 'Performance');

  const findings = result.sections.performance.findings;
  const fv = (id: string) => {
    const f = findings.find(x => x.id === id);
    return typeof f?.value === 'number' ? f.value : null;
  };

  const ttfb = fv('performance.timings:ttfb');
  const fcp = fv('performance.timings:fcp');
  const lcp = fv('performance.timings:lcp');
  const dcl = fv('performance.timings:dcl');
  const load = fv('performance.timings:load');
  const transfer = fv('performance.resources:transfer-size');
  const requests = fv('performance.resources:request-count');

  // Metric boxes
  const boxW = CW / 3;
  let col = 0;
  const metrics: [string, string][] = [];
  if (ttfb !== null) metrics.push(['TTFB', formatDuration(ttfb)]);
  if (fcp !== null) metrics.push(['First Contentful Paint', formatDuration(fcp)]);
  if (lcp !== null) metrics.push(['Largest Contentful Paint', formatDuration(lcp)]);
  if (dcl !== null) metrics.push(['DOM Content Loaded', formatDuration(dcl)]);
  if (load !== null) metrics.push(['Load Event', formatDuration(load)]);
  if (transfer !== null) metrics.push(['Transfer Size', formatBytes(transfer)]);
  if (requests !== null) metrics.push(['Network Requests', String(requests)]);

  for (const [label, value] of metrics) {
    if (col >= 3) { col = 0; p.y += 20; }
    metricBox(p, label, value, M + col * boxW, boxW);
    col++;
  }
  if (metrics.length > 0) p.y += 22;

  // Resource breakdown
  const resourceTypes = findings.find(f => f.id === 'performance.resources:resource-types');
  if (resourceTypes?.values?.length) {
    h3(p, 'Resource Breakdown');
    for (const entry of resourceTypes.values.slice(0, 10)) {
      body(p, `  ${entry}`);
    }
  }

  spacer(p, 5);
  gray(p, 'Note: These are measurements from a single cold lab run. They are not representative of real-user experience and will vary across runs, locations, and network conditions.');
}

function renderAccessibilitySection(p: W, result: AnalysisResult): void {
  h2(p, 'Accessibility');

  const findings = result.sections.accessibility.findings;
  const fv = (id: string) => findings.find(f => f.id === id);

  const violations = fv('accessibility.axe:violation-count');
  const lang = fv('accessibility.structure:document-lang');
  const docTitle = fv('accessibility.structure:document-title');
  const headings = fv('accessibility.structure:heading-hierarchy');
  const imagesAlt = fv('accessibility.structure:images-missing-alt');
  const formLabels = fv('accessibility.structure:form-labels');
  const landmarks = fv('accessibility.structure:landmarks');

  if (violations && typeof violations.value === 'number') {
    body(p, `${violations.value} automated rule violation${violations.value !== 1 ? 's' : ''} detected by axe-core.`);
    spacer(p, 3);
  }

  h3(p, 'Document Structure');
  if (lang?.detected) bullet(p, `✓ Document declares language: ${lang.value}`);
  else if (lang) bullet(p, '✗ Document is missing a language declaration');

  if (docTitle?.detected) bullet(p, `✓ Document has a title`);
  else if (docTitle) bullet(p, '✗ Document is missing a title');

  if (headings?.value === 'correct') bullet(p, '✓ Heading hierarchy is correct');
  else if (headings?.values?.length) bullet(p, `✗ Heading hierarchy issue: ${headings.values[0]}`);

  if (landmarks?.detected) bullet(p, `✓ ${landmarks.value} ARIA landmarks present`);
  else if (landmarks) bullet(p, '✗ No ARIA landmarks detected');

  spacer(p, 3);

  if (imagesAlt && typeof imagesAlt.value === 'number' && imagesAlt.value > 0) {
    h3(p, 'Images');
    body(p, `${imagesAlt.value} image${imagesAlt.value > 1 ? 's do' : ' does'} not have an alt attribute.`);
    gray(p, 'Images without alternative text are invisible to screen reader users.');
  }

  if (formLabels && typeof formLabels.value === 'number' && formLabels.value > 0) {
    h3(p, 'Forms');
    body(p, `${formLabels.value} form input${formLabels.value > 1 ? 's' : ''} without associated labels.`);
    gray(p, 'Inputs without labels are difficult to identify for assistive technology users.');
  }

  spacer(p, 5);
  gray(p, 'Note: Automated rules detect a subset of WCAG issues. A clean result does not mean the site is accessible — conformance requires manual testing with assistive technologies and expert review.');
}

function renderSeoSection(p: W, result: AnalysisResult): void {
  h2(p, 'SEO');

  const findings = result.sections.seo.findings;
  const fv = (id: string) => findings.find(f => f.id === id);

  h3(p, 'Search Metadata');
  const titleF = fv('seo.metadata:title');
  const desc = fv('seo.metadata:meta-description');
  const canonical = fv('seo.metadata:canonical');
  const robots = fv('seo.metadata:robots-meta');
  const viewport = fv('seo.metadata:viewport-meta');
  const lang = fv('seo.metadata:html-lang');

  if (titleF?.detected) { kv(p, 'Title', String(titleF.value)); }
  else { kv(p, 'Title', '(not present)'); }
  if (desc?.detected) { kv(p, 'Description', String(desc.value).slice(0, 100)); }
  else { kv(p, 'Description', '(not present)'); }
  if (canonical?.detected) { kv(p, 'Canonical', String(canonical.value)); }
  if (robots?.detected) { kv(p, 'Robots', String(robots.value)); }
  if (viewport?.detected) { kv(p, 'Viewport', String(viewport.value)); }
  if (lang?.detected) { kv(p, 'Language', String(lang.value)); }

  spacer(p, 3);

  // Social
  const og = fv('seo.metadata:open-graph');
  const twitter = fv('seo.metadata:twitter-card');
  h3(p, 'Social Sharing');
  if (og?.detected) bullet(p, `Open Graph: ${og.value} tags present`);
  else bullet(p, 'Open Graph: not present');
  if (twitter?.detected) bullet(p, `Twitter Card: ${twitter.value} tags present`);
  else bullet(p, 'Twitter Card: not present');

  // Structured data
  const sd = fv('seo.structured_data:structured-data');
  if (sd?.detected) {
    h3(p, 'Structured Data');
    body(p, `${sd.value} structured data block${(sd.value as number) > 1 ? 's' : ''} found.`);
    if (sd.values.length > 0) gray(p, sd.values.join(', '));
  }

  // Indexability
  const robotsAllowed = fv('seo.indexability:robots-allowed');
  const sitemaps = fv('seo.indexability:sitemaps');
  if (robotsAllowed || sitemaps) {
    h3(p, 'Indexability');
    if (robotsAllowed?.detected) bullet(p, 'robots.txt allows access to this page');
    if (sitemaps?.detected) bullet(p, `${sitemaps.value} sitemap${(sitemaps.value as number) > 1 ? 's' : ''} declared in robots.txt`);
  }
}

function renderArchitectureSection(p: W, result: AnalysisResult): void {
  h2(p, 'Architecture & Infrastructure');

  const overview = buildOverview(result);
  const archFindings = result.sections.architecture.findings;

  // Rendering
  if (overview.rendering.strategy) {
    h3(p, 'Rendering Strategy');
    body(p, `${overview.rendering.certainty === 'Inferred' ? 'Likely: ' : ''}${overview.rendering.strategy}`);
    spacer(p, 3);
  }

  // Platform/infrastructure
  if (overview.infrastructure.platforms.length > 0 || overview.infrastructure.cdn.length > 0 || overview.infrastructure.server.length > 0) {
    h3(p, 'Infrastructure');
    if (overview.infrastructure.platforms.length > 0) body(p, `Platform: ${overview.infrastructure.platforms.join(', ')}`);
    if (overview.infrastructure.cdn.length > 0) body(p, `CDN: ${overview.infrastructure.cdn.join(', ')}`);
    if (overview.infrastructure.server.length > 0) body(p, `Server: ${overview.infrastructure.server.join(', ')}`);
    spacer(p, 3);
  }

  // Runtime findings
  const sw = archFindings.find(f => f.id === 'architecture.runtime:service-worker');
  const scripts = archFindings.find(f => f.id === 'architecture.runtime:script-types');
  const storage = archFindings.find(f => f.id === 'architecture.runtime:local-storage');
  const api = archFindings.find(f => f.id === 'architecture.runtime:api-requests');
  const consoleErrs = archFindings.find(f => f.id === 'architecture.runtime:console-errors');

  if (sw || scripts || storage || api) {
    h3(p, 'Runtime');
    if (sw?.detected) bullet(p, 'Service Worker registered');
    if (scripts?.value) bullet(p, `Script types: ${scripts.value}`);
    if (storage && typeof storage.value === 'number') bullet(p, `${storage.value} localStorage keys`);
    if (api && typeof api.value === 'number') bullet(p, `${api.value} API/XHR requests observed`);
    if (consoleErrs && typeof consoleErrs.value === 'number' && consoleErrs.value > 0) {
      bullet(p, `${consoleErrs.value} console errors/warnings`);
    }
  }
}

function renderNetworkSection(p: W, result: AnalysisResult): void {
  h2(p, 'Network & Resources');

  const findings = result.sections.network.findings;
  const domains = findings.find(f => f.id === 'network.resources:domain-count');
  const ratio = findings.find(f => f.id === 'network.third_parties:third-party-ratio');
  const tpDomains = findings.find(f => f.id === 'network.third_parties:third-party-domains');

  if (domains && typeof domains.value === 'number') {
    body(p, `${domains.value} unique domains contacted during page load.`);
  }
  if (ratio && typeof ratio.value === 'number') {
    body(p, `${ratio.value}% of requests went to third-party domains.`);
  }

  if (tpDomains?.values?.length) {
    spacer(p, 3);
    h3(p, 'Third-Party Domains');
    for (const domain of tpDomains.values.slice(0, 15)) {
      bullet(p, domain);
    }
  }

  if (domains?.values?.length) {
    spacer(p, 3);
    h3(p, 'Domain Breakdown');
    for (const entry of domains.values.slice(0, 10)) {
      body(p, `  ${entry}`);
    }
  }
}

// =====================================================
// PUBLIC API
// =====================================================

export function generateSectionPdf(result: AnalysisResult, sectionKey: SectionKey): Blob {
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  doc.setFont('helvetica');
  const p = w(doc);

  title(p, `${sectionLabel(sectionKey)} — ${result.target.host}`);
  kv(p, 'URL', result.target.final_url ?? result.target.normalized_url);
  kv(p, 'Scanned', formatTimestamp(result.scan.finished_at ?? result.scan.created_at));
  kv(p, 'Duration', formatDuration(result.scan.duration_ms));
  kv(p, 'Engine', result.scan.engine_version);
  kv(p, 'Collection', result.scan.run_context?.collection_mode ?? 'browser');
  separator(p);

  switch (sectionKey) {
    case 'design': renderDesignSection(p, result); break;
    case 'technology': renderTechnologySection(p, result); break;
    case 'security': renderSecuritySection(p, result); break;
    case 'performance': renderPerformanceSection(p, result); break;
    case 'accessibility': renderAccessibilitySection(p, result); break;
    case 'seo': renderSeoSection(p, result); break;
    case 'architecture': renderArchitectureSection(p, result); break;
    case 'network': renderNetworkSection(p, result); break;
  }

  // Footer
  spacer(p, 10);
  separator(p);
  gray(p, 'WebLens observes what a normal visit to a public URL reveals. It is passive: no forms submitted, no authentication attempted. Findings describe one page at one point in time.');
  gray(p, `Generated ${new Date().toISOString()} by WebLens.`);

  return doc.output('blob');
}

export function generateCompletePdf(result: AnalysisResult): Blob {
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  doc.setFont('helvetica');
  const p = w(doc);

  // Cover page
  renderCoverPage(p, result);

  // Design
  doc.addPage(); p.y = M;
  renderDesignSection(p, result);

  // Technology
  doc.addPage(); p.y = M;
  renderTechnologySection(p, result);

  // Security
  doc.addPage(); p.y = M;
  renderSecuritySection(p, result);

  // Performance
  doc.addPage(); p.y = M;
  renderPerformanceSection(p, result);

  // Accessibility
  doc.addPage(); p.y = M;
  renderAccessibilitySection(p, result);

  // SEO
  doc.addPage(); p.y = M;
  renderSeoSection(p, result);

  // Architecture
  doc.addPage(); p.y = M;
  renderArchitectureSection(p, result);

  // Network
  doc.addPage(); p.y = M;
  renderNetworkSection(p, result);

  // Limitations
  doc.addPage(); p.y = M;
  h2(p, 'Limitations');
  for (const l of result.limitations) {
    bullet(p, l);
  }
  spacer(p, 5);
  gray(p, 'WebLens observes what a normal visit to a public URL reveals. It is passive: no forms submitted, no authentication attempted. Findings describe one page at one point in time.');
  gray(p, `Generated ${new Date().toISOString()} by WebLens.`);

  return doc.output('blob');
}
