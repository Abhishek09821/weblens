/**
 * Technology stack — human-readable grouped view.
 *
 * Technologies are grouped into meaningful categories (Frontend, Styling, Backend, etc.)
 * with descriptions and evidence. Raw analyzer output is available via expandable sections.
 */
import { ChevronDownIcon } from 'lucide-react';
import { useState } from 'react';

import { EvidencePopover } from '@/components/sections/EvidencePopover';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { buildTechPresentation, type TechItem } from '@/lib/presentation/technology';
import type { AnalysisResult } from '@/types/analysis';

export function TechnologyDetails({ result }: { result: AnalysisResult }) {
  const categories = buildTechPresentation(result);

  if (categories.length === 0) {
    return (
      <Card>
        <CardContent className="py-6">
          <p className="text-sm text-muted-foreground">
            No technologies could be positively identified from the observable signals on this page.
            This does not mean no technology is in use — server-rendered, self-hosted, or heavily
            bundled technologies are frequently invisible from the outside.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      {categories.map((category) => (
        <Card key={category.title}>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">{category.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {category.items.map((item) => (
              <TechItemRow key={item.findingId} item={item} />
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function TechItemRow({ item }: { item: TechItem }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium">{item.name}</span>
            <Badge variant={item.status === 'verified' ? 'verified' : 'inferred'}>
              {item.status === 'verified' ? 'Verified' : 'Inferred'}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{item.description}</p>
        </div>
        <EvidencePopover evidence={item.evidence} label={item.name} />
      </div>

      {item.signals.length > 0 && (
        <div className="mt-2">
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <ChevronDownIcon className={`size-3 transition-transform ${expanded ? 'rotate-180' : ''}`} />
            Why WebLens detected this
          </button>
          {expanded && (
            <ul className="mt-1.5 space-y-1 pl-4">
              {item.signals.map((signal, i) => (
                <li key={i} className="text-xs text-muted-foreground">• {signal}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
