/**
 * PDF report generation from structured analysis data.
 *
 * Uses jsPDF to generate professional PDF reports directly in the browser.
 * Each section gets its own PDF, plus a complete bundle PDF with all sections.
 * All data comes from the same verified structured result used for Markdown reports.
 */
import { jsPDF } from 'jspdf';

import { sectionLabel } from '@/lib/format/labels';
import { findingStatusLabel } from '@/lib/format/status';
import { formatDuration, formatTimestamp } from '@/lib/format/values';
import { securityScoreSchema } from '@/types/analysis';
import type { AnalysisResult, Finding, SectionKey } from '@/types/analysis';

import { STANDING_DISCLAIMER } from './markdown/shared';

const PAGE_WIDTH = 210; // A4 width in mm
const PAGE_HEIGHT = 297;
const MARGIN = 15;
const CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN;
const LINE_HEIGHT = 5;
const FONT_SIZE_TITLE = 18;
const FONT_SIZE_H2 = 13;
const FONT_SIZE_H3 = 11;
const FONT_SIZE_BODY = 9;
const FONT_SIZE_SMALL = 8;

interface PdfWriter {
  doc: jsPDF;
  y: number;
  pageNum: number;
}

function createWriter(): PdfWriter {
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  doc.setFont('helvetica');
  return { doc, y: MARGIN, pageNum: 1 };
}

function checkPage(w: PdfWriter, needed: number = LINE_HEIGHT * 3): void {
  if (w.y + needed > PAGE_HEIGHT - MARGIN) {
    w.doc.addPage();
    w.pageNum += 1;
    w.y = MARGIN;
  }
}

function addTitle(w: PdfWriter, text: string): void {
  checkPage(w, 20);
  w.doc.setFontSize(FONT_SIZE_TITLE);
  w.doc.setFont('helvetica', 'bold');
  w.doc.text(text, MARGIN, w.y);
  w.y += 10;
}

function addH2(w: PdfWriter, text: string): void {
  checkPage(w, 15);
  w.y += 4;
  w.doc.setFontSize(FONT_SIZE_H2);
  w.doc.setFont('helvetica', 'bold');
  w.doc.text(text, MARGIN, w.y);
  w.y += 7;
}

function addH3(w: PdfWriter, text: string): void {
  checkPage(w, 12);
  w.y += 3;
  w.doc.setFontSize(FONT_SIZE_H3);
  w.doc.setFont('helvetica', 'bold');
  w.doc.text(text, MARGIN, w.y);
  w.y += 6;
}

function addText(w: PdfWriter, text: string, indent: number = 0): void {
  w.doc.setFontSize(FONT_SIZE_BODY);
  w.doc.setFont('helvetica', 'normal');
  const lines = w.doc.splitTextToSize(text, CONTENT_WIDTH - indent);
  for (const line of lines) {
    checkPage(w);
    w.doc.text(line, MARGIN + indent, w.y);
    w.y += LINE_HEIGHT;
  }
}

function addSmallText(w: PdfWriter, text: string, indent: number = 0): void {
  w.doc.setFontSize(FONT_SIZE_SMALL);
  w.doc.setFont('helvetica', 'normal');
  w.doc.setTextColor(100, 100, 100);
  const lines = w.doc.splitTextToSize(text, CONTENT_WIDTH - indent);
  for (const line of lines) {
    checkPage(w);
    w.doc.text(line, MARGIN + indent, w.y);
    w.y += LINE_HEIGHT - 0.5;
  }
  w.doc.setTextColor(0, 0, 0);
}

function addBold(w: PdfWriter, text: string, indent: number = 0): void {
  w.doc.setFontSize(FONT_SIZE_BODY);
  w.doc.setFont('helvetica', 'bold');
  const lines = w.doc.splitTextToSize(text, CONTENT_WIDTH - indent);
  for (const line of lines) {
    checkPage(w);
    w.doc.text(line, MARGIN + indent, w.y);
    w.y += LINE_HEIGHT;
  }
  w.doc.setFont('helvetica', 'normal');
}

function addKeyValue(w: PdfWriter, key: string, value: string | number | null | undefined): void {
  if (value === null || value === undefined) return;
  checkPage(w);
  w.doc.setFontSize(FONT_SIZE_BODY);
  w.doc.setFont('helvetica', 'bold');
  w.doc.text(`${key}:`, MARGIN, w.y);
  w.doc.setFont('helvetica', 'normal');
  const valueStr = String(value);
  const lines = w.doc.splitTextToSize(valueStr, CONTENT_WIDTH - 45);
  w.doc.text(lines[0] ?? '', MARGIN + 45, w.y);
  w.y += LINE_HEIGHT;
  for (let i = 1; i < lines.length; i++) {
    checkPage(w);
    w.doc.text(lines[i], MARGIN + 45, w.y);
    w.y += LINE_HEIGHT;
  }
}

function addSeparator(w: PdfWriter): void {
  w.y += 2;
  checkPage(w, 5);
  w.doc.setDrawColor(200, 200, 200);
  w.doc.line(MARGIN, w.y, PAGE_WIDTH - MARGIN, w.y);
  w.y += 4;
}

function addFrontMatter(w: PdfWriter, result: AnalysisResult, title: string): void {
  addTitle(w, `${title} — ${result.target.host}`);
  w.y += 2;
  addKeyValue(w, 'URL', result.target.final_url ?? result.target.normalized_url);
  addKeyValue(w, 'Scanned', formatTimestamp(result.scan.finished_at ?? result.scan.created_at));
  addKeyValue(w, 'Duration', formatDuration(result.scan.duration_ms));
  addKeyValue(w, 'Engine', result.scan.engine_version);
  addKeyValue(w, 'Collection', result.scan.run_context?.collection_mode ?? 'unknown');
  addKeyValue(w, 'Scan ID', result.scan.scan_id);
  addSeparator(w);
}

function addFindings(w: PdfWriter, findings: Finding[]): void {
  if (findings.length === 0) return;

  addH2(w, 'Findings');

  // Group by category
  const groups = new Map<string, Finding[]>();
  for (const f of [...findings].sort((a, b) => a.category.localeCompare(b.category))) {
    const g = groups.get(f.category) ?? [];
    g.push(f);
    groups.set(f.category, g);
  }

  for (const [category, group] of groups) {
    addH3(w, category.replace(/[_-]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()));

    for (const finding of group) {
      checkPage(w, 15);
      // Finding name and status
      w.doc.setFontSize(FONT_SIZE_BODY);
      w.doc.setFont('helvetica', 'bold');
      w.doc.text(finding.name, MARGIN + 2, w.y);
      w.doc.setFont('helvetica', 'normal');

      const statusText = `[${findingStatusLabel(finding.status)}]`;
      const nameWidth = w.doc.getTextWidth(finding.name);
      w.doc.setFontSize(FONT_SIZE_SMALL);
      w.doc.setTextColor(100, 100, 100);
      w.doc.text(statusText, MARGIN + 2 + nameWidth + 3, w.y);
      w.doc.setTextColor(0, 0, 0);
      w.y += LINE_HEIGHT;

      // Value
      const value = formatFindingValueForPdf(finding);
      if (value) {
        addSmallText(w, `Value: ${value}`, 4);
      }

      // Reason (for negative findings)
      if (finding.reason) {
        addSmallText(w, finding.reason, 4);
      }

      // Evidence summary
      if (finding.evidence.length > 0) {
        const evidenceStr = finding.evidence
          .slice(0, 2)
          .map((e) => `${e.source}${e.excerpt ? ': ' + e.excerpt.slice(0, 60) : ''}`)
          .join('; ');
        addSmallText(w, `Evidence: ${evidenceStr}`, 4);
      }

      w.y += 1;
    }
  }
}

function addLimitations(w: PdfWriter, result: AnalysisResult, sectionKey?: SectionKey): void {
  const limitations = sectionKey
    ? [...(result.sections[sectionKey].meta.limitations), ...result.limitations]
    : result.limitations;

  if (limitations.length === 0) return;

  addH2(w, 'Limitations');
  for (const limitation of limitations) {
    addText(w, `• ${limitation}`, 2);
  }
}

function addDisclaimer(w: PdfWriter): void {
  w.y += 4;
  addSeparator(w);
  addSmallText(w, STANDING_DISCLAIMER);
  addSmallText(w, `Generated ${new Date().toISOString()} by WebLens report generator.`);
}

function formatFindingValueForPdf(finding: Finding): string {
  const { value, unit, values } = finding;
  if (value === null || value === undefined) {
    return values.length > 0 ? values.slice(0, 5).join(', ') + (values.length > 5 ? '...' : '') : '';
  }
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (typeof value === 'number') return unit ? `${value} ${unit}` : String(value);
  return unit ? `${value} (${unit})` : value;
}

// --- Public API ---

/** Generate a PDF for a single section. */
export function generateSectionPdf(result: AnalysisResult, sectionKey: SectionKey): Blob {
  const w = createWriter();
  const section = result.sections[sectionKey];
  const title = sectionLabel(sectionKey);

  addFrontMatter(w, result, title);

  // Section status
  addKeyValue(w, 'Section status', section.meta.status);
  if (section.meta.unavailable_reason) {
    addText(w, section.meta.unavailable_reason);
  }
  w.y += 2;

  // Security-specific: score block
  if (sectionKey === 'security') {
    addSecurityScore(w, section.data);
  }

  // Findings
  addFindings(w, section.findings);

  // Interpretations
  if (section.interpretations.length > 0) {
    addH2(w, 'Interpretation');
    addSmallText(w, 'Readings of measured values, not observations. Each cites the findings it derives from.');
    w.y += 2;
    for (const interp of section.interpretations) {
      addBold(w, interp.statement, 2);
      addSmallText(w, `Based on: ${interp.basis.join(', ')}`, 4);
      w.y += 2;
    }
  }

  // Analyzer runs
  addH2(w, 'Analyzers');
  for (const run of section.meta.analyzers) {
    checkPage(w);
    const duration = run.duration_ms != null ? formatDuration(run.duration_ms) : '—';
    addText(w, `${run.id} (${run.version}) — ${run.status} — ${duration}`);
    if (run.error_detail) {
      addSmallText(w, `Error: ${run.error_detail}`, 4);
    }
  }

  addLimitations(w, result, sectionKey);
  addDisclaimer(w);

  return w.doc.output('blob');
}

/** Generate a complete PDF with all sections. */
export function generateCompletePdf(result: AnalysisResult): Blob {
  const w = createWriter();

  // Cover page
  addTitle(w, `WebLens Analysis Report`);
  w.y += 5;
  addH2(w, result.target.host);
  w.y += 5;
  addKeyValue(w, 'Requested URL', result.target.requested_url);
  addKeyValue(w, 'Final URL', result.target.final_url ?? result.target.normalized_url);
  addKeyValue(w, 'HTTP Status', result.target.http_status);
  addKeyValue(w, 'Scanned', formatTimestamp(result.scan.finished_at ?? result.scan.created_at));
  addKeyValue(w, 'Duration', formatDuration(result.scan.duration_ms));
  addKeyValue(w, 'Engine', result.scan.engine_version);
  addKeyValue(w, 'Schema', result.schema_version);
  addKeyValue(w, 'Collection', result.scan.run_context?.collection_mode ?? 'unknown');
  addKeyValue(w, 'Status', result.scan.status.replace(/_/g, ' '));
  addKeyValue(w, 'Scan ID', result.scan.scan_id);

  if (result.errors.length > 0) {
    w.y += 3;
    addText(w, `${result.errors.length} issue(s) occurred during this scan.`);
  }

  // Run context
  if (result.scan.run_context) {
    w.y += 3;
    addH3(w, 'Run Context');
    const rc = result.scan.run_context;
    addKeyValue(w, 'Browser', rc.browser_name ? `${rc.browser_name} ${rc.browser_version ?? ''}`.trim() : 'not used');
    addKeyValue(w, 'Viewport', `${rc.viewport.width} x ${rc.viewport.height}`);
    addKeyValue(w, 'Wait strategy', rc.wait_strategy);
    addKeyValue(w, 'User agent', rc.user_agent);
  }

  addSeparator(w);

  // Table of contents
  addH2(w, 'Sections');
  const sectionKeys: SectionKey[] = ['seo', 'security', 'technology', 'design', 'performance', 'accessibility', 'architecture', 'network'];
  for (const key of sectionKeys) {
    const sec = result.sections[key];
    const count = sec.findings.length;
    addText(w, `• ${sectionLabel(key)} — ${sec.meta.status} — ${count} findings`);
  }

  addSeparator(w);

  // Each section
  for (const key of sectionKeys) {
    w.doc.addPage();
    w.y = MARGIN;

    const section = result.sections[key];
    addH2(w, sectionLabel(key));
    addKeyValue(w, 'Status', section.meta.status);
    if (section.meta.unavailable_reason) {
      addText(w, section.meta.unavailable_reason);
    }
    w.y += 2;

    // Security score
    if (key === 'security') {
      addSecurityScore(w, section.data);
    }

    // Findings
    addFindings(w, section.findings);

    // Interpretations
    if (section.interpretations.length > 0) {
      addH3(w, 'Interpretation');
      for (const interp of section.interpretations) {
        addBold(w, interp.statement, 2);
        addSmallText(w, `Based on: ${interp.basis.join(', ')}`, 4);
        w.y += 1;
      }
    }

    // Limitations
    if (section.meta.limitations.length > 0) {
      addH3(w, 'Limitations');
      for (const l of section.meta.limitations) {
        addText(w, `• ${l}`, 2);
      }
    }
  }

  // Final page: scan-wide limitations
  w.doc.addPage();
  w.y = MARGIN;
  addH2(w, 'Scan-wide Limitations');
  for (const l of result.limitations) {
    addText(w, `• ${l}`, 2);
  }

  addDisclaimer(w);

  return w.doc.output('blob');
}

function addSecurityScore(w: PdfWriter, data: unknown): void {
  const raw = data && typeof data === 'object' ? (data as { score?: unknown }).score : undefined;
  const parsed = securityScoreSchema.safeParse(raw);
  if (!parsed.success) return;

  const score = parsed.data;

  addH3(w, score.label);
  addSmallText(w, score.disclaimer);
  w.y += 2;

  // Score display
  w.doc.setFontSize(16);
  w.doc.setFont('helvetica', 'bold');
  w.doc.text(`${score.percentage}%`, MARGIN, w.y);
  w.doc.setFontSize(FONT_SIZE_BODY);
  w.doc.setFont('helvetica', 'normal');
  w.doc.text(`  ${score.band_phrase}  (${score.points_awarded}/${score.points_applicable} points)`, MARGIN + 18, w.y);
  w.y += 8;

  // Rules table
  addH3(w, 'Security Rules');
  for (const rule of score.rules) {
    checkPage(w, 12);
    const outcome = rule.outcome === 'pass' ? '[PASS]' : rule.outcome === 'fail' ? '[FAIL]' : `[${rule.outcome.toUpperCase()}]`;
    addText(w, `${outcome} ${rule.title} (${rule.id}) — ${rule.awarded}/${rule.weight} pts`);
    if (rule.rationale) {
      addSmallText(w, rule.rationale, 6);
    }
  }

  // Excluded rules
  if (score.excluded_rules.length > 0) {
    w.y += 2;
    addH3(w, 'Excluded from Score');
    for (const rule of score.excluded_rules) {
      addSmallText(w, `${rule.id}: ${rule.reason}`);
    }
  }

  w.y += 3;
}
