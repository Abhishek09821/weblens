import { SearchCodeIcon } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import type { EvidenceRef } from '@/types/analysis';

/**
 * The provenance of a claim, on demand.
 *
 * Every asserted finding can show the observations behind it. This is the user-facing half of the
 * rule that a verified finding cannot exist without evidence.
 */
export function EvidencePopover({ evidence, label }: { evidence: EvidenceRef[]; label: string }) {
  if (evidence.length === 0) return null;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 gap-1 px-1.5 text-xs text-muted-foreground hover:text-foreground"
          aria-label={`Show evidence for ${label}`}
        >
          <SearchCodeIcon className="size-3.5" />
          {evidence.length}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="max-h-96 overflow-y-auto scrollbar-thin">
        <p className="mb-2 text-xs font-medium">Observed evidence</p>
        <ul className="space-y-3">
          {evidence.map((ref, index) => (
            <li key={`${ref.source}-${index}`} className="space-y-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">{ref.source}</code>
                <span className="text-[11px] text-muted-foreground">{ref.kind}</span>
              </div>
              {ref.location && (
                <p className="truncate font-mono text-[11px] text-muted-foreground" title={ref.location}>
                  {ref.location}
                </p>
              )}
              {ref.excerpt && (
                <pre className="max-h-32 overflow-auto rounded-md bg-muted/60 p-2 font-mono text-[11px] whitespace-pre-wrap break-words scrollbar-thin">
                  {ref.excerpt}
                </pre>
              )}
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
