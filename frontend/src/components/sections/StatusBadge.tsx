import { Badge } from '@/components/ui/badge';
import {
  findingStatusHelp,
  findingStatusLabel,
  findingStatusTone,
  sectionStatusLabel,
  sectionStatusTone,
  statusToneClass,
  type StatusTone,
} from '@/lib/format/status';
import { cn } from '@/lib/utils';
import type { FindingStatus, SectionStatus } from '@/types/analysis';

const TONE_VARIANT: Record<
  StatusTone,
  | 'verified'
  | 'stronglyInferred'
  | 'inferred'
  | 'aiInferred'
  | 'neutral'
  | 'attention'
  | 'muted'
> = {
  verified: 'verified',
  'strongly-inferred': 'stronglyInferred',
  inferred: 'inferred',
  'ai-inferred': 'aiInferred',
  neutral: 'neutral',
  attention: 'attention',
  muted: 'muted',
};

/**
 * Finding status, always as words.
 *
 * `confidence` is never rendered: a number beside an uncertain claim reads as authority and
 * launders a guess into a fact (docs/blueprint/decisions.md D5).
 */
export function FindingStatusBadge({ status }: { status: FindingStatus }) {
  return (
    <Badge variant={TONE_VARIANT[findingStatusTone(status)]} title={findingStatusHelp(status)}>
      {findingStatusLabel(status)}
    </Badge>
  );
}

export function SectionStatusBadge({ status }: { status: SectionStatus }) {
  return <Badge variant={TONE_VARIANT[sectionStatusTone(status)]}>{sectionStatusLabel(status)}</Badge>;
}

/** Status dot, always paired with text so status is never encoded by colour alone. */
export function StatusDot({ status, className }: { status: SectionStatus; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn('inline-block size-1.5 shrink-0 rounded-full', statusToneClass(sectionStatusTone(status)), className)}
    />
  );
}
