/**
 * Presentation helpers for finding and section status.
 *
 * The tone mapping is a product decision, not styling: `not_detected`, `not_determinable`, and
 * `unable_to_verify` map to neutral tones, never to red. Absence of a signal is not a failure,
 * and colouring it as one would be the UI making a claim the analyzer did not.
 */
import type { Finding, FindingStatus, SectionStatus } from '@/types/analysis';

export type StatusTone =
  | 'verified'
  | 'strongly-inferred'
  | 'inferred'
  | 'ai-inferred'
  | 'neutral'
  | 'attention'
  | 'muted';

const FINDING_STATUS_LABELS: Record<FindingStatus, string> = {
  verified: 'Verified',
  strongly_inferred: 'Strongly inferred',
  inferred: 'Inferred',
  ai_inferred: 'AI inferred',
  not_detected: 'Not detected',
  not_determinable: 'Not determinable',
  unable_to_verify: 'Unable to verify',
};

const FINDING_STATUS_TONES: Record<FindingStatus, StatusTone> = {
  verified: 'verified',
  strongly_inferred: 'strongly-inferred',
  inferred: 'inferred',
  ai_inferred: 'ai-inferred',
  not_detected: 'neutral',
  not_determinable: 'muted',
  unable_to_verify: 'attention',
};

const FINDING_STATUS_HELP: Record<FindingStatus, string> = {
  verified: 'Directly observed in evidence collected from this page.',
  strongly_inferred: 'Supported by multiple strong public or page-level signals, but not directly confirmed.',
  inferred: 'Derived from indirect signals. The supporting evidence is listed with the finding.',
  ai_inferred: 'An AI-generated hypothesis grounded in listed evidence; it is not a verified fact.',
  not_detected: 'Evidence was collected and this signal was absent. Not the same as "not used".',
  not_determinable: 'This property cannot be determined from public observations.',
  unable_to_verify: 'The evidence needed for this check was unavailable in this scan.',
};

const SECTION_STATUS_LABELS: Record<SectionStatus, string> = {
  complete: 'Complete',
  partial: 'Partial',
  insufficient_evidence: 'Insufficient evidence',
  unavailable: 'Unavailable',
  not_implemented: 'Not in this build',
  skipped: 'Skipped',
};

const SECTION_STATUS_TONES: Record<SectionStatus, StatusTone> = {
  complete: 'verified',
  partial: 'inferred',
  insufficient_evidence: 'attention',
  unavailable: 'attention',
  not_implemented: 'muted',
  skipped: 'muted',
};

export function findingStatusLabel(status: FindingStatus): string {
  return FINDING_STATUS_LABELS[status];
}

export function findingStatusTone(status: FindingStatus): StatusTone {
  return FINDING_STATUS_TONES[status];
}

export function findingStatusHelp(status: FindingStatus): string {
  return FINDING_STATUS_HELP[status];
}

export function sectionStatusLabel(status: SectionStatus): string {
  return SECTION_STATUS_LABELS[status];
}

export function sectionStatusTone(status: SectionStatus): StatusTone {
  return SECTION_STATUS_TONES[status];
}

export function isAsserted(finding: Finding): boolean {
  return (
    finding.status === 'verified' ||
    finding.status === 'strongly_inferred' ||
    finding.status === 'inferred' ||
    finding.status === 'ai_inferred'
  );
}

export function sectionIsRenderable(status: SectionStatus): boolean {
  return status === 'complete' || status === 'partial' || status === 'insufficient_evidence';
}

/**
 * Render a finding value with its unit, without inventing precision.
 *
 * A `null` value is rendered as an em dash rather than "0" or "none": those would be assertions
 * the finding does not make.
 */
export function formatFindingValue(finding: Finding): string {
  const { value, unit } = finding;
  if (value === null || value === undefined) {
    return finding.values.length > 0 ? finding.values.join(', ') : '—';
  }
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (typeof value === 'number') {
    if (unit === 'count') return String(value);
    return unit ? `${value} ${unit}` : String(value);
  }
  return unit ? `${value} (${unit})` : value;
}

export function statusToneClass(tone: StatusTone): string {
  switch (tone) {
    case 'verified':
      return 'bg-status-verified';
    case 'strongly-inferred':
      return 'bg-status-strongly-inferred';
    case 'inferred':
      return 'bg-status-inferred';
    case 'ai-inferred':
      return 'bg-status-ai-inferred';
    case 'attention':
      return 'bg-status-attention';
    case 'neutral':
      return 'bg-status-neutral';
    case 'muted':
      return 'bg-muted-foreground/40';
  }
}
