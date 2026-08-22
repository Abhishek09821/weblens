/** Four-report PDF generation from the stored V2 result. */
import { jsPDF } from 'jspdf';

import { findingStatusLabel } from '@/lib/format/status';
import { sectionLabel } from '@/lib/format/labels';
import { formatDuration, formatTimestamp } from '@/lib/format/values';
import { buildDesignPresentation } from '@/lib/presentation/design';
import { buildOverview } from '@/lib/presentation/overview';
import { buildTechPresentation } from '@/lib/presentation/technology';
import {
  SECTION_KEYS,
  securityPayloadSchema,
  trafficPayloadSchema,
  type AnalysisResult,
  type Finding,
  type FindingStatus,
  type SectionKey,
} from '@/types/analysis';

const PAGE_W = 210;
const PAGE_H = 297;
const MARGIN = 14;
const CONTENT_W = PAGE_W - MARGIN * 2;
const PRIMARY: [number, number, number] = [41, 128, 185];
const DARK: [number, number, number] = [30, 30, 30];
const GRAY: [number, number, number] = [100, 100, 100];
const LIGHT_GRAY: [number, number, number] = [210, 214, 220];

interface Writer {
  doc: jsPDF;
  y: number;
}

type SectionRenderer = (writer: Writer, result: AnalysisResult) => void;

const SECTION_RENDERERS: Record<SectionKey, SectionRenderer> = {
  design: renderDesign,
  technology: renderTechnology,
  security: renderSecurity,
  traffic: renderTraffic,
};

function writer(doc: jsPDF): Writer {
  return { doc, y: MARGIN };
}

function ensurePage(output: Writer, needed = 18): void {
  if (output.y + needed <= PAGE_H - MARGIN) return;
  output.doc.addPage();
  output.y = MARGIN;
}

function heading(output: Writer, text: string, level: 1 | 2 | 3 = 2): void {
  ensurePage(output, level === 1 ? 18 : 14);
  output.y += level === 1 ? 2 : 4;
  output.doc.setFont('helvetica', 'bold');
  output.doc.setFontSize(level === 1 ? 20 : level === 2 ? 14 : 11);
  output.doc.setTextColor(...(level === 2 ? PRIMARY : DARK));
  output.doc.text(text, MARGIN, output.y);
  output.y += level === 1 ? 10 : level === 2 ? 8 : 6;
  if (level === 2) {
    output.doc.setDrawColor(...PRIMARY);
    output.doc.setLineWidth(0.25);
    output.doc.line(MARGIN, output.y - 3, MARGIN + CONTENT_W, output.y - 3);
  }
}

function text(output: Writer, value: string, muted = false, indent = 0): void {
  output.doc.setFont('helvetica', 'normal');
  output.doc.setFontSize(muted ? 8.5 : 9.5);
  output.doc.setTextColor(...(muted ? GRAY : DARK));
  const lines = output.doc.splitTextToSize(value, CONTENT_W - indent);
  for (const line of lines) {
    ensurePage(output, 6);
    output.doc.text(line, MARGIN + indent, output.y);
    output.y += muted ? 4 : 4.5;
  }
}

function bullet(output: Writer, value: string, muted = false): void {
  ensurePage(output, 7);
  output.doc.setFontSize(9);
  output.doc.setTextColor(...(muted ? GRAY : DARK));
  output.doc.text('•', MARGIN + 1, output.y);
  text(output, value, muted, 5);
}

function keyValue(output: Writer, key: string, value: unknown): void {
  if (value === null || value === undefined || value === '') return;
  ensurePage(output, 7);
  output.doc.setFontSize(9);
  output.doc.setFont('helvetica', 'bold');
  output.doc.setTextColor(...GRAY);
  output.doc.text(key, MARGIN, output.y);
  output.doc.setFont('helvetica', 'normal');
  output.doc.setTextColor(...DARK);
  const lines = output.doc.splitTextToSize(String(value), CONTENT_W - 42);
  output.doc.text(lines, MARGIN + 42, output.y);
  output.y += Math.max(5, lines.length * 4);
}

function separator(output: Writer): void {
  output.y += 2;
  output.doc.setDrawColor(...LIGHT_GRAY);
  output.doc.line(MARGIN, output.y, MARGIN + CONTENT_W, output.y);
  output.y += 5;
}

function statusBadge(output: Writer, status: FindingStatus, x: number, y: number): void {
  const label = findingStatusLabel(status);
  const color = statusColor(status);
  output.doc.setFontSize(7);
  const width = output.doc.getTextWidth(label) + 5;
  output.doc.setFillColor(...color);
  output.doc.roundedRect(x, y - 3.5, width, 5.5, 1, 1, 'F');
  output.doc.setTextColor(255, 255, 255);
  output.doc.text(label, x + 2.5, y);
  output.doc.setTextColor(...DARK);
}

function statusColor(status: FindingStatus): [number, number, number] {
  switch (status) {
    case 'verified':
      return [39, 150, 96];
    case 'strongly_inferred':
      return [45, 120, 175];
    case 'inferred':
      return [190, 132, 28];
    case 'ai_inferred':
      return [132, 74, 170];
    case 'unable_to_verify':
      return [180, 92, 35];
    case 'not_detected':
    case 'not_determinable':
      return [112, 118, 126];
  }
}

function sectionHeader(output: Writer, result: AnalysisResult, key: SectionKey): void {
  const section = result.sections[key];
  heading(output, sectionLabel(key), 1);
  keyValue(output, 'Section status', section.meta.status.replace(/_/g, ' '));
  keyValue(output, 'Reason', section.meta.unavailable_reason);
  if (section.meta.status !== 'complete' && section.meta.status !== 'partial') {
    text(output, 'No report claims were substituted for unavailable evidence.', true);
  }
  separator(output);
}

function renderCover(output: Writer, result: AnalysisResult): void {
  const overview = buildOverview(result);
  output.y = 42;
  output.doc.setFont('helvetica', 'bold');
  output.doc.setFontSize(28);
  output.doc.setTextColor(...PRIMARY);
  output.doc.text('WebLens', MARGIN, output.y);
  output.y += 9;
  output.doc.setFont('helvetica', 'normal');
  output.doc.setFontSize(14);
  output.doc.setTextColor(...GRAY);
  output.doc.text('Website reverse-engineering report', MARGIN, output.y);
  output.y += 20;
  heading(output, result.target.host, 1);
  text(output, result.target.final_url ?? result.target.normalized_url, true);
  separator(output);
  keyValue(output, 'Scan status', result.scan.status.replace(/_/g, ' '));
  keyValue(output, 'Scanned', formatTimestamp(result.scan.finished_at ?? result.scan.created_at));
  keyValue(output, 'Duration', formatDuration(result.scan.duration_ms));
  keyValue(output, 'Engine', result.scan.engine_version);
  keyValue(output, 'Schema', result.schema_version);

  heading(output, 'Report summary', 2);
  if (overview.technology.items.length > 0) {
    bullet(output, `Technology: ${overview.technology.items.map((item) => item.name).join(', ')}`);
  } else {
    bullet(output, 'Technology: no product was positively identified from observable signals.', true);
  }
  bullet(
    output,
    overview.security.percentage === null
      ? 'Security: passive posture score unavailable.'
      : `Security: ${overview.security.percentage}% — ${overview.security.bandPhrase ?? 'band unavailable'}. This is not proof the site is secure.`,
  );
  bullet(
    output,
    overview.traffic.estimates.length > 0
      ? `Traffic: ${overview.traffic.estimates.map((estimate) => `${estimate.name} ${estimate.value}`).join(', ')}`
      : `Traffic: ${overview.traffic.unavailableReason ?? 'no estimate available'}`,
  );
  bullet(
    output,
    `Evidence: ${overview.evidence.verified} verified, ${overview.evidence.stronglyInferred} strongly inferred, ${overview.evidence.inferred} inferred, ${overview.evidence.aiInferred} AI hypotheses.`,
  );
}

function renderDesign(output: Writer, result: AnalysisResult): void {
  sectionHeader(output, result, 'design');
  const design = buildDesignPresentation(result);
  text(output, design.summary);

  heading(output, 'Page structure', 2);
  renderFindings(output, result.sections.design.findings.filter((finding) => ['document', 'structure'].includes(finding.category)));

  heading(output, 'Layout system and spacing', 2);
  if (design.layout.displayTypes.length > 0) keyValue(output, 'Layout methods', design.layout.displayTypes.join(', '));
  if (design.layout.gaps.length > 0) keyValue(output, 'Gap values', design.layout.gaps.join(', '));
  if (design.layout.borderRadii.length > 0) keyValue(output, 'Border radii', design.layout.borderRadii.join(', '));
  if (design.layout.shadows.length > 0) keyValue(output, 'Shadows', design.layout.shadows.join(', '));
  if (!design.layout.available) text(output, 'No layout values were available.', true);

  heading(output, 'Responsive behavior', 2);
  if (design.layout.breakpoints.length > 0) keyValue(output, 'Breakpoints', design.layout.breakpoints.join(', '));
  if (design.layout.hasOverflow) keyValue(output, 'Overflow widths', design.layout.overflowWidths.join(', '));
  if (design.layout.breakpoints.length === 0 && !design.layout.hasOverflow) text(output, 'No separate responsive observation was available.', true);

  heading(output, 'Typography', 2);
  keyValue(output, 'Loaded fonts', design.typography.loadedFonts.join(', '));
  keyValue(output, 'Font families', design.typography.fontFamilies.join(', '));
  keyValue(output, 'Weights', design.typography.weights.join(', '));
  keyValue(output, 'Type scale', design.typography.sizes.join(', '));
  keyValue(output, 'Line heights', design.typography.lineHeights.join(', '));

  heading(output, 'Color system', 2);
  keyValue(output, 'Background colors', design.colors.backgrounds.map((color) => color.hex ?? color.value).join(', '));
  keyValue(output, 'Text colors', design.colors.texts.map((color) => color.hex ?? color.value).join(', '));

  heading(output, 'Components and patterns', 2);
  renderFindings(output, result.sections.design.findings.filter((finding) => finding.category === 'forms'));

  heading(output, 'Media', 2);
  keyValue(output, 'Images', design.media.imageCount);
  keyValue(output, 'SVG elements', design.media.svgCount);
  keyValue(output, 'Videos', design.media.videoCount);
  keyValue(output, 'Formats', design.media.formats.join(', '));

  heading(output, 'Motion', 2);
  keyValue(output, 'Transitions', design.motion.transitions.join(', '));
  keyValue(output, 'Animations', design.motion.animations.join(', '));
  keyValue(output, 'Keyframe definitions', design.motion.keyframeCount);

  renderLimitations(output, result.sections.design.meta.limitations);
}

function renderTechnology(output: Writer, result: AnalysisResult): void {
  sectionHeader(output, result, 'technology');
  const presentation = buildTechPresentation(result);

  if (presentation.categories.length === 0) {
    text(output, 'No technology was positively identified from observable signals. Invisible backend or bundled technology was not guessed.', true);
  }
  for (const category of presentation.categories) {
    heading(output, category.title, 2);
    for (const item of category.items) {
      ensurePage(output, 16);
      output.doc.setFont('helvetica', 'bold');
      output.doc.setFontSize(10);
      output.doc.setTextColor(...DARK);
      output.doc.text(item.name, MARGIN, output.y);
      statusBadge(output, item.status, Math.min(MARGIN + output.doc.getTextWidth(item.name) + 4, 160), output.y);
      output.y += 5;
      text(output, item.description, true);
      if (item.signals.length > 0) text(output, `Evidence: ${item.signals.join(' ')}`, true);
      if (item.limitations.length > 0) text(output, `Limitations: ${item.limitations.join(' ')}`, true);
      output.y += 2;
    }
  }

  heading(output, 'Architecture hypothesis', 2);
  if (presentation.hypotheses.length === 0) {
    text(output, 'No AI architecture hypothesis was produced.', true);
  }
  for (const hypothesis of presentation.hypotheses) {
    heading(output, hypothesis.hypothesis, 3);
    statusBadge(output, 'ai_inferred', MARGIN, output.y);
    output.y += 6;
    text(output, 'AI hypothesis — not a verified detection.', true);
    if (hypothesis.reasoning) text(output, `Why inferred: ${hypothesis.reasoning}`);
    for (const basis of hypothesis.basis) bullet(output, `Basis: ${basis.label}`, true);
    for (const limitation of hypothesis.limitations) bullet(output, `Limitation: ${limitation}`, true);
  }

  heading(output, 'Unknown / not publicly determinable', 2);
  if (presentation.unknowns.length === 0) text(output, 'No explicit unknowns were reported.', true);
  for (const unknown of presentation.unknowns) {
    bullet(output, `${unknown.name} — ${findingStatusLabel(unknown.status)}: ${unknown.reason}`);
  }

  renderLimitations(output, result.sections.technology.meta.limitations);
}

function renderSecurity(output: Writer, result: AnalysisResult): void {
  sectionHeader(output, result, 'security');
  const section = result.sections.security;
  const parsed = securityPayloadSchema.safeParse(section.data);
  const score = parsed.success ? parsed.data.score : null;

  heading(output, 'Observable Security Posture', 2);
  if (score) {
    keyValue(output, 'Score', `${score.percentage}%`);
    keyValue(output, 'Band', score.band_phrase);
    keyValue(output, 'Applicable points', `${score.points_awarded} / ${score.points_applicable}`);
    keyValue(output, 'Methodology', score.methodology_version);
    text(output, score.disclaimer, true);
    text(output, 'This passive score is not proof that the website is secure.', true);

    heading(output, 'Security rules', 2);
    for (const rule of score.rules) {
      bullet(output, `${rule.id} ${rule.title} — ${rule.outcome}: ${rule.rationale}`);
      if (rule.recommendation) text(output, `Recommendation: ${rule.recommendation}`, true, 5);
    }
  } else {
    text(output, 'No posture score was produced; findings remain available below.', true);
  }

  heading(output, 'Passive observations', 2);
  renderFindings(output, section.findings);
  renderLimitations(output, section.meta.limitations);
}

function renderTraffic(output: Writer, result: AnalysisResult): void {
  sectionHeader(output, result, 'traffic');
  const section = result.sections.traffic;
  const parsed = trafficPayloadSchema.safeParse(section.data);
  const provider = parsed.success ? parsed.data : null;
  const popularity = section.findings.filter((finding) => finding.category === 'popularity');
  const signals = section.findings.filter((finding) => finding.category === 'analytics');
  const hasEstimate = popularity.some(
    (finding) =>
      (finding.status === 'verified' || finding.status === 'strongly_inferred' || finding.status === 'inferred') &&
      (finding.value !== null || finding.values.length > 0),
  );

  heading(output, 'Popularity and traffic estimates', 2);
  keyValue(output, 'Provider', provider?.provider_name ?? 'none configured');
  keyValue(output, 'Provider available', provider?.provider_available ? 'yes' : 'no');
  if (!hasEstimate) {
    text(output, 'Traffic estimates are unavailable. No visit count, rank, or popularity band was fabricated.', true);
  }
  renderFindings(output, popularity);

  heading(output, 'Public signals', 2);
  text(output, 'Analytics tooling observed on this visit does not measure or estimate traffic volume.', true);
  renderFindings(output, signals);
  renderLimitations(output, section.meta.limitations);
}

function renderFindings(output: Writer, findings: Finding[]): void {
  if (findings.length === 0) {
    text(output, 'No observations were available for this group.', true);
    return;
  }
  for (const finding of findings) {
    ensurePage(output, 13);
    output.doc.setFont('helvetica', 'bold');
    output.doc.setFontSize(9.5);
    output.doc.setTextColor(...DARK);
    output.doc.text(finding.name, MARGIN, output.y);
    statusBadge(output, finding.status, Math.min(MARGIN + output.doc.getTextWidth(finding.name) + 4, 160), output.y);
    output.y += 5;
    const renderedValue = findingValue(finding);
    if (renderedValue !== '—') text(output, `Value: ${renderedValue}`, true);
    if (finding.reason) text(output, finding.reason, true);
    if (finding.evidence.length > 0) text(output, `Evidence: ${finding.evidence.map((evidence) => evidence.source).join(', ')}`, true);
    for (const limitation of finding.limitations) text(output, `Limitation: ${limitation}`, true);
    output.y += 2;
  }
}

function findingValue(finding: Finding): string {
  if (finding.value !== null && finding.value !== undefined) {
    const rendered = typeof finding.value === 'boolean' ? (finding.value ? 'yes' : 'no') : String(finding.value);
    return finding.unit && finding.unit !== 'count' ? `${rendered} ${finding.unit}` : rendered;
  }
  return finding.values.length > 0 ? finding.values.join(', ') : '—';
}

function renderLimitations(output: Writer, limitations: string[]): void {
  if (limitations.length === 0) return;
  heading(output, 'Limitations', 2);
  for (const limitation of limitations) bullet(output, limitation, true);
}

function reportHeader(output: Writer, result: AnalysisResult, key: SectionKey): void {
  heading(output, `${sectionLabel(key)} — ${result.target.host}`, 1);
  keyValue(output, 'URL', result.target.final_url ?? result.target.normalized_url);
  keyValue(output, 'Scanned', formatTimestamp(result.scan.finished_at ?? result.scan.created_at));
  keyValue(output, 'Duration', formatDuration(result.scan.duration_ms));
  keyValue(output, 'Engine', result.scan.engine_version);
  separator(output);
}

function footer(output: Writer): void {
  separator(output);
  text(
    output,
    'WebLens passively observes one public page at one point in time. It does not submit forms, authenticate, or test access controls.',
    true,
  );
  text(output, `Generated ${new Date().toISOString()} by WebLens.`, true);
}

export function generateSectionPdf(result: AnalysisResult, sectionKey: SectionKey): Blob {
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  const output = writer(doc);
  reportHeader(output, result, sectionKey);
  SECTION_RENDERERS[sectionKey](output, result);
  footer(output);
  return doc.output('blob');
}

export function generateCompletePdf(result: AnalysisResult): Blob {
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  const output = writer(doc);
  renderCover(output, result);

  for (const sectionKey of SECTION_KEYS) {
    doc.addPage();
    output.y = MARGIN;
    SECTION_RENDERERS[sectionKey](output, result);
  }

  if (result.limitations.length > 0) {
    doc.addPage();
    output.y = MARGIN;
    heading(output, 'Scan limitations', 1);
    for (const limitation of result.limitations) bullet(output, limitation, true);
  }
  footer(output);
  return doc.output('blob');
}
