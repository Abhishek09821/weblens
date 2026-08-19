import { LightbulbIcon } from 'lucide-react';

import type { Interpretation } from '@/types/analysis';

/**
 * Interpretations, visually separated from observations.
 *
 * The separation is the point: a statement like "modern dark SaaS-like visual language" is a
 * reading of measured values, not a measurement. It lives in its own container, is labelled, and
 * cites the findings it derives from.
 */
export function InterpretationCallout({ interpretations }: { interpretations: Interpretation[] }) {
  if (interpretations.length === 0) return null;

  return (
    <section
      aria-labelledby="interpretation-heading"
      className="rounded-lg border border-dashed border-status-inferred/50 bg-status-inferred/5 p-4"
    >
      <h3
        id="interpretation-heading"
        className="mb-1 flex items-center gap-2 text-sm font-semibold text-status-inferred"
      >
        <LightbulbIcon className="size-4" aria-hidden="true" />
        Interpretation
      </h3>
      <p className="mb-3 text-xs text-muted-foreground">
        Readings of the measured values above. These are judgements, not observations.
      </p>
      <ul className="space-y-3">
        {interpretations.map((item) => (
          <li key={item.id} className="space-y-1">
            <p className="text-sm">{item.statement}</p>
            <p className="text-xs text-muted-foreground">
              Derived from{' '}
              {item.basis.map((id, index) => (
                <span key={id}>
                  {index > 0 && ', '}
                  <code className="font-mono">{id}</code>
                </span>
              ))}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
