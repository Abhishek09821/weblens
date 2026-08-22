import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { makeFinding, makeResult, makeSection } from '@/test/factories';

import { SectionPanel } from './SectionPanel';

describe('SectionPanel V2 reports', () => {
  it('renders deterministic technology claims with their exact evidence status', () => {
    render(<SectionPanel result={makeResult()} sectionKey="technology" />);

    expect(screen.getByRole('heading', { name: 'Tech Stack', level: 2 })).toBeInTheDocument();
    expect(screen.getAllByText('React').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Verified').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Strongly inferred').length).toBeGreaterThan(0);
    expect(screen.getByText(/Rendering strategy: Client Rendered/i)).toBeInTheDocument();
  });

  it('shows AI hypotheses separately and never presents them as verified', () => {
    render(<SectionPanel result={makeResult()} sectionKey="technology" />);

    const hypothesis = screen.getByRole('article');
    expect(hypothesis).toHaveTextContent('The site may use an API gateway');
    expect(hypothesis).toHaveTextContent('AI inferred');
    expect(hypothesis).toHaveTextContent('Hypothesis');
    expect(hypothesis).toHaveTextContent('Why it was inferred');
    expect(hypothesis).toHaveTextContent('Private infrastructure cannot be confirmed');
    expect(hypothesis).not.toHaveTextContent('Verified');
  });

  it('never renders internal confidence metadata', () => {
    const { container } = render(<SectionPanel result={makeResult()} sectionKey="technology" />);
    const text = container.textContent?.toLowerCase() ?? '';

    expect(text).not.toContain('definitive');
    expect(text).not.toContain('moderate confidence');
    expect(text).not.toMatch(/\d+%\s*(confident|certain)/);
  });

  it('reports unavailable traffic without inventing a number', () => {
    const { container } = render(<SectionPanel result={makeResult()} sectionKey="traffic" />);

    expect(screen.getByText('Traffic estimates unavailable')).toBeInTheDocument();
    expect(screen.getAllByText('Unable to verify').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/No traffic data provider is configured/i).length).toBeGreaterThan(0);
    expect(container).not.toHaveTextContent(/\b0\s+(visits|users|sessions)\b/i);
  });

  it('states plainly when a V2 section is unavailable', () => {
    const result = makeResult();
    result.sections.traffic = makeSection('traffic', 'unavailable');
    render(<SectionPanel result={result} sectionKey="traffic" />);

    expect(screen.getByText('No findings available')).toBeInTheDocument();
    expect(screen.getByText(/Every analyzer for this section failed/)).toBeInTheDocument();
    expect(screen.getByText(/Analyzers \(0\/1 completed\)/)).toBeInTheDocument();
  });

  it('separates interpretations from observations', () => {
    const result = makeResult();
    result.sections.design = {
      ...makeSection('design', 'complete', [
        makeFinding({
          id: 'design.color:background',
          category: 'color',
          name: 'Dominant background',
          value: '#0b0f17',
          source: 'design.color',
        }),
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
    expect(callout).not.toHaveTextContent('Dominant background');
  });

  it('offers the canonical per-section report download', () => {
    render(<SectionPanel result={makeResult()} sectionKey="technology" />);
    expect(screen.getByRole('button', { name: /techstack\.md/i })).toBeInTheDocument();
  });

  it('renders section limitations', () => {
    render(<SectionPanel result={makeResult()} sectionKey="design" />);
    expect(screen.getByText('Limitations')).toBeInTheDocument();
    expect(screen.getByText(/One public page was observed/)).toBeInTheDocument();
  });
});
