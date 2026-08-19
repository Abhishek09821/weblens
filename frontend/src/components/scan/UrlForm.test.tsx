import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { UrlForm } from './UrlForm';

describe('UrlForm', () => {
  it('submits a valid URL', async () => {
    const onSubmit = vi.fn();
    render(<UrlForm onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText('Website URL'), 'example.com');
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }));

    expect(onSubmit).toHaveBeenCalledWith('example.com');
  });

  it('blocks submission of an invalid URL and explains why', async () => {
    const onSubmit = vi.fn();
    render(<UrlForm onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText('Website URL'), 'localhost');
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent(/publicly reachable/i);
    expect(screen.getByLabelText('Website URL')).toHaveAttribute('aria-invalid', 'true');
  });

  it('does not shout at the user before they have finished typing', async () => {
    render(<UrlForm onSubmit={vi.fn()} />);
    await userEvent.type(screen.getByLabelText('Website URL'), 'exa');

    // Untouched-and-incomplete input shows no error yet; the live region stays empty.
    expect(screen.getByRole('alert')).toHaveTextContent('');
  });

  it('surfaces a server-side rejection on the field', () => {
    render(<UrlForm onSubmit={vi.fn()} externalError="Host resolves to a blocked range." />);
    expect(screen.getByRole('alert')).toHaveTextContent('Host resolves to a blocked range.');
  });

  it('disables input while a scan is running', () => {
    render(<UrlForm onSubmit={vi.fn()} disabled />);
    expect(screen.getByLabelText('Website URL')).toBeDisabled();
    expect(screen.getByRole('button', { name: /analyzing/i })).toBeDisabled();
  });

  it('focuses the field when "/" is pressed', async () => {
    render(<UrlForm onSubmit={vi.fn()} />);
    const input = screen.getByLabelText('Website URL');

    expect(input).not.toHaveFocus();
    await userEvent.keyboard('/');
    expect(input).toHaveFocus();
  });
});
