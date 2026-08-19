/**
 * Section rendering tests.
 *
 * The confidence assertion is the important one: it encodes a product principle as an executable
 * check, so a future refactor that starts surfacing "85% confident" fails the build instead of
 * quietly changing what WebLens claims.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { makeFinding, makeResult, makeSection } from '@/test/factories';

import { SectionPanel } from './SectionPanel';

describe('SectionPanel', () => {
  it('renders verified findings with a word status and evidence access', () => {
    render(<SectionPanel result={makeResult()} sectionKey="seo" />);

    expect(screen.getByRole('heading', { name: 'SEO', level: 2 })).toBeInTheDocument();
    expect(screen.getByText('Document title')).toBeInTheDocument();
    expect(screen.getByText('Verified')).toBeInTheDocument();
    // The title appears in both the findings table and the metadata summary card.
    expect(screen.getAllByText('Example Domain').length).toBeGreaterThan(0);
    expect(
      screen.getByRole('button', { name: /show evidence for document title/i }),
    ).toBeInTheDocument();
  });

  it('shows the reason for a finding that was not detected', () => {
    render(<SectionPanel result={makeResult()} sectionKey="seo" />);

    expect(screen.getByText('Not detected')).toBeInTheDocument();
    expect(
      screen.getByText('No <meta name="description"> with content was present.'),
    ).toBeInTheDocument();
  });

  it('never renders confidence in the DOM', () => {
    const { container } = render(<SectionPanel result={makeResult()} sectionKey="seo" />);
    const text = container.textContent?.toLowerCase() ?? '';

    expect(text).not.toContain('confidence');
    expect(text).not.toContain('definitive');
    expect(text).not.toMatch(/\d+%\s*(confident|certain)/);
  });

  it('states plainly when a section is not implemented', () => {
    render(<SectionPanel result={makeResult()} sectionKey="design" />);

    expect(screen.getByText('Not implemented in this build')).toBeInTheDocument();
    expect(
      screen.getByText(/Nothing about the target was inferred in its place/i),
    ).toBeInTheDocument();
    // The planned analyzer is still listed, so "not built yet" is distinguishable from "found nothing".
    expect(screen.getByText(/Analyzers \(0\/1 completed\)/)).toBeInTheDocument();
  });

  it('explains an unavailable section rather than showing an empty panel', () => {
    const result = makeResult();
    result.sections.accessibility = makeSection('accessibility', 'unavailable');
    render(<SectionPanel result={result} sectionKey="accessibility" />);

    expect(screen.getByText('No findings available')).toBeInTheDocument();
    expect(screen.getByText(/Every analyzer for this section failed/)).toBeInTheDocument();
  });

  it('separates interpretations from observations', () => {
    const result = makeResult();
    result.sections.design = {
      ...makeSection('design', 'complete', [
        makeFinding({ id: 'design.color:background', name: 'Dominant background', value: '#0b0f17' }),
      ]),
      interpretations: [
        {
          id: 'design.interpretation:language',
          statement: 'Dark, high-radius visual language',
          basis: ['design.color:background'],
          source: 'design.interpretation',
          caveat: 'Interpretation derived from observed values, not a directly observed fact.',
        },
      ],
    };

    render(<SectionPanel result={result} sectionKey="design" />);

    const callout = screen.getByRole('region', { name: /interpretation/i });
    expect(callout).toHaveTextContent('Dark, high-radius visual language');
    expect(callout).toHaveTextContent('design.color:background');
    // The observation itself lives outside the interpretation container.
    expect(callout).not.toHaveTextContent('Dominant background');
  });

  it('offers a per-section report download', () => {
    render(<SectionPanel result={makeResult()} sectionKey="seo" />);
    expect(screen.getByRole('button', { name: /seo\.md/i })).toBeInTheDocument();
  });

  it('renders section limitations', () => {
    render(<SectionPanel result={makeResult()} sectionKey="seo" />);
    expect(screen.getByText('Limitations')).toBeInTheDocument();
    expect(screen.getByText(/Observed in the HTML as served/)).toBeInTheDocument();
  });
});
