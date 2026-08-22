/** Consolidated technology, architecture, infrastructure, and AI-hypothesis presentation. */
import { ChevronDownIcon, ExternalLinkIcon, SparklesIcon } from 'lucide-react';
import { useState } from 'react';

import { EvidencePopover } from '@/components/sections/EvidencePopover';
import { FindingStatusBadge } from '@/components/sections/StatusBadge';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  buildTechPresentation,
  type TechHypothesis,
  type TechItem,
} from '@/lib/presentation/technology';
import type { AnalysisResult } from '@/types/analysis';

export function TechnologyDetails({ result }: { result: AnalysisResult }) {
  const presentation = buildTechPresentation(result);
  const hasPositiveClaims = presentation.categories.some((category) => category.items.length > 0);

  return (
    <div className="space-y-5">
      {!hasPositiveClaims && (
        <Card>
          <CardContent className="py-6">
            <p className="text-sm text-muted-foreground">
              No technology was positively identified from observable signals. Server-rendered,
              self-hosted, bundled, and private backend technologies may not be externally visible.
            </p>
          </CardContent>
        </Card>
      )}

      {presentation.categories.map((category) => (
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

      {presentation.hypotheses.length > 0 && (
        <Card className="border-status-ai-inferred/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <SparklesIcon className="size-4 text-status-ai-inferred" aria-hidden="true" />
              Potential backend architecture
            </CardTitle>
            <CardDescription>
              AI-generated hypotheses grounded in public evidence. These are not verified detections.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {presentation.hypotheses.map((hypothesis) => (
              <HypothesisRow key={hypothesis.findingId} hypothesis={hypothesis} />
            ))}
          </CardContent>
        </Card>
      )}

      {presentation.unknowns.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Unknown / not publicly determinable</CardTitle>
            <CardDescription>
              These entries are explicit boundaries, not negative claims about the target.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="divide-y divide-border">
              {presentation.unknowns.map((unknown) => (
                <li key={unknown.findingId} className="py-3 first:pt-0 last:pb-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">{unknown.name}</span>
                    <FindingStatusBadge status={unknown.status} />
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{unknown.reason}</p>
                  {unknown.limitations.length > 0 && (
                    <ul className="mt-1 list-disc pl-4 text-xs text-muted-foreground">
                      {unknown.limitations.map((limitation) => (
                        <li key={limitation}>{limitation}</li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function TechItemRow({ item }: { item: TechItem }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{item.name}</span>
            <FindingStatusBadge status={item.status} />
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{item.description}</p>
          <p className="mt-1 font-mono text-[10px] text-muted-foreground">{item.source}</p>
        </div>
        <EvidencePopover evidence={item.evidence} label={item.name} />
      </div>

      {(item.signals.length > 0 || item.limitations.length > 0) && (
        <div className="mt-2">
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <ChevronDownIcon
              className={`size-3 transition-transform ${expanded ? 'rotate-180' : ''}`}
              aria-hidden="true"
            />
            Evidence basis and limitations
          </button>
          {expanded && (
            <div className="mt-2 space-y-2">
              {item.signals.length > 0 && (
                <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                  {item.signals.map((signal) => <li key={signal}>{signal}</li>)}
                </ul>
              )}
              {item.limitations.length > 0 && (
                <div>
                  <p className="text-xs font-medium">Limitations</p>
                  <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                    {item.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function HypothesisRow({ hypothesis }: { hypothesis: TechHypothesis }) {
  return (
    <article className="rounded-lg border border-status-ai-inferred/30 bg-status-ai-inferred/5 p-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="font-medium">{hypothesis.hypothesis}</h4>
            <FindingStatusBadge status="ai_inferred" />
            <Badge variant="outline">Hypothesis</Badge>
          </div>
          {hypothesis.reasoning && (
            <div className="mt-2">
              <p className="text-xs font-medium">Why it was inferred</p>
              <p className="mt-0.5 text-sm text-muted-foreground">{hypothesis.reasoning}</p>
            </div>
          )}
        </div>
        <EvidencePopover evidence={hypothesis.evidence} label={hypothesis.hypothesis} />
      </div>

      {hypothesis.basis.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium">Sources and evidence basis</p>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-muted-foreground">
            {hypothesis.basis.map((basis) => (
              <li key={`${basis.label}-${basis.url ?? ''}`}>
                {basis.url ? (
                  <a
                    href={basis.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex items-center gap-1 underline-offset-2 hover:underline"
                  >
                    {basis.label}
                    <ExternalLinkIcon className="size-3" aria-hidden="true" />
                  </a>
                ) : basis.label}
              </li>
            ))}
          </ul>
        </div>
      )}

      {hypothesis.limitations.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium">Limitations</p>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-muted-foreground">
            {hypothesis.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
          </ul>
        </div>
      )}
    </article>
  );
}
