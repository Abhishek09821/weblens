import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { FindingStatus } from '@/types/analysis';

import { FindingStatusBadge } from './StatusBadge';

const STATUSES: Array<[FindingStatus, string]> = [
  ['verified', 'Verified'],
  ['strongly_inferred', 'Strongly inferred'],
  ['inferred', 'Inferred'],
  ['ai_inferred', 'AI inferred'],
  ['not_detected', 'Not detected'],
  ['not_determinable', 'Not determinable'],
  ['unable_to_verify', 'Unable to verify'],
];

describe('FindingStatusBadge', () => {
  it('renders every V2 evidence state as distinct words', () => {
    render(
      <div>
        {STATUSES.map(([status]) => <FindingStatusBadge key={status} status={status} />)}
      </div>,
    );

    for (const [, label] of STATUSES) expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.getByText('AI inferred')).not.toHaveTextContent('Verified');
  });
});
