import { StatusDot } from '@/components/sections/StatusBadge';
import { sectionLabel } from '@/lib/format/labels';
import { sectionStatusLabel } from '@/lib/format/status';
import { cn } from '@/lib/utils';
import { SECTION_KEYS, type SectionKey, type SectionSet } from '@/types/analysis';

export type NavKey = 'overview' | SectionKey;

/**
 * Section navigation with per-section status.
 *
 * Status is shown as a dot *and* text: colour alone would exclude anyone who cannot distinguish
 * the hues, in a tool that reports on other sites' accessibility.
 */
export function SectionNav({
  sections,
  active,
  onSelect,
}: {
  sections: SectionSet;
  active: NavKey;
  onSelect: (key: NavKey) => void;
}) {
  return (
    <nav aria-label="Report sections" className="lg:sticky lg:top-20">
      <ul className="flex gap-1 overflow-x-auto scrollbar-thin lg:flex-col lg:overflow-visible">
        {/* Overview tab */}
        <li className="shrink-0 lg:shrink">
          <button
            type="button"
            onClick={() => onSelect('overview')}
            aria-current={active === 'overview' ? 'page' : undefined}
            className={cn(
              'flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors',
              active === 'overview'
                ? 'bg-secondary text-secondary-foreground'
                : 'text-muted-foreground hover:bg-secondary/60 hover:text-foreground',
            )}
          >
            <span className="inline-block size-1.5 shrink-0 rounded-full bg-primary" aria-hidden="true" />
            <span className="flex-1 whitespace-nowrap font-medium">Overview</span>
          </button>
        </li>

        {SECTION_KEYS.map((key) => {
          const status = sections[key].meta.status;
          const findingCount = sections[key].findings.length;
          const isActive = key === active;
          return (
            <li key={key} className="shrink-0 lg:shrink">
              <button
                type="button"
                onClick={() => onSelect(key)}
                aria-current={isActive ? 'page' : undefined}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors',
                  isActive
                    ? 'bg-secondary text-secondary-foreground'
                    : 'text-muted-foreground hover:bg-secondary/60 hover:text-foreground',
                )}
              >
                <StatusDot status={status} />
                <span className="flex-1 whitespace-nowrap">{sectionLabel(key)}</span>
                <span className="font-mono text-[11px] text-muted-foreground/80">
                  {findingCount > 0 ? findingCount : sectionStatusShort(status)}
                </span>
                <span className="sr-only">{sectionStatusLabel(status)}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function sectionStatusShort(status: SectionSet[SectionKey]['meta']['status']): string {
  switch (status) {
    case 'not_implemented':
      return 'n/a';
    case 'unavailable':
      return '!';
    case 'insufficient_evidence':
      return '⚠';
    case 'skipped':
      return '–';
    default:
      return '0';
  }
}
