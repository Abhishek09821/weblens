import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { makeResult } from '@/test/factories';

import { OverviewPanel } from './OverviewPanel';

describe('OverviewPanel V2 taxonomy', () => {
  it('prioritizes the four reports and evidence quality without old audit cards', () => {
    render(<OverviewPanel result={makeResult()} />);

    expect(screen.getByText('example.test')).toBeInTheDocument();
    expect(screen.getByText('Tech Stack')).toBeInTheDocument();
    expect(screen.getByText('Design')).toBeInTheDocument();
    expect(screen.getByText('Security Posture')).toBeInTheDocument();
    expect(screen.getByText('Traffic & Popularity')).toBeInTheDocument();
    expect(screen.getByText('Evidence Quality')).toBeInTheDocument();
    expect(screen.getByText(/No traffic data provider is configured/i)).toBeInTheDocument();

    expect(screen.queryByText('Performance')).not.toBeInTheDocument();
    expect(screen.queryByText('Accessibility')).not.toBeInTheDocument();
    expect(screen.queryByText('SEO')).not.toBeInTheDocument();
    expect(screen.queryByText('AI Summary')).not.toBeInTheDocument();
  });
});
