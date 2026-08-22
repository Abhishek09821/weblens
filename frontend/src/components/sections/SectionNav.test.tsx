import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { makeResult } from '@/test/factories';

import { SectionNav } from './SectionNav';

describe('SectionNav', () => {
  it('exposes only overview and the four V2 reports in canonical order', () => {
    const onSelect = vi.fn();
    render(<SectionNav sections={makeResult().sections} active="overview" onSelect={onSelect} />);

    const buttons = screen.getAllByRole('button');
    expect(buttons.map((button) => button.querySelector('span.flex-1')?.textContent)).toEqual([
      'Overview',
      'Design',
      'Tech Stack',
      'Security',
      'Traffic',
    ]);
    expect(screen.queryByText('Performance')).not.toBeInTheDocument();
    expect(screen.queryByText('Accessibility')).not.toBeInTheDocument();
    expect(screen.queryByText('SEO')).not.toBeInTheDocument();
    expect(screen.queryByText('Architecture')).not.toBeInTheDocument();
    expect(screen.queryByText('Network')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /traffic/i }));
    expect(onSelect).toHaveBeenCalledWith('traffic');
  });
});
