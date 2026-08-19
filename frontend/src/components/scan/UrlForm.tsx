import { SearchIcon } from 'lucide-react';
import { useEffect, useId, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { validateUrlInput } from '@/lib/url-validation';
import { cn } from '@/lib/utils';

/**
 * URL entry.
 *
 * Validation runs locally for immediate feedback but is never treated as the authority: the backend
 * re-validates and is the only place that resolves DNS and enforces the address policy.
 */
export function UrlForm({
  onSubmit,
  disabled = false,
  externalError,
}: {
  onSubmit: (url: string) => void;
  disabled?: boolean;
  externalError?: string;
}) {
  const [value, setValue] = useState('');
  const [touched, setTouched] = useState(false);
  const inputId = useId();
  const errorId = `${inputId}-error`;
  const hintId = `${inputId}-hint`;
  const inputRef = useRef<HTMLInputElement>(null);

  // `/` focuses the URL field, the way a developer tool should behave.
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key !== '/' || event.metaKey || event.ctrlKey) return;
      const target = event.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      event.preventDefault();
      inputRef.current?.focus();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const validation = validateUrlInput(value);
  const localError = touched && !validation.valid ? validation.message : undefined;
  const error = externalError ?? localError;

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        setTouched(true);
        if (!validation.valid) {
          inputRef.current?.focus();
          return;
        }
        onSubmit(value.trim());
      }}
      className="space-y-2"
    >
      <label htmlFor={inputId} className="block text-sm font-medium">
        Website URL
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          id={inputId}
          ref={inputRef}
          type="text"
          inputMode="url"
          autoComplete="url"
          spellCheck={false}
          placeholder="example.com"
          value={value}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={cn(error ? errorId : undefined, hintId)}
          onChange={(event) => setValue(event.target.value)}
          onBlur={() => setTouched(true)}
          className="font-mono sm:flex-1"
        />
        <Button type="submit" disabled={disabled} className="sm:w-36">
          <SearchIcon className="size-4" />
          {disabled ? 'Analyzing…' : 'Analyze'}
        </Button>
      </div>
      <p id={hintId} className="text-xs text-muted-foreground">
        Publicly reachable http:// or https:// pages only. Press <kbd className="font-mono">/</kbd>{' '}
        to focus this field.
      </p>
      <p
        id={errorId}
        role="alert"
        aria-live="polite"
        className={cn('text-xs text-destructive', !error && 'sr-only')}
      >
        {error ?? ''}
      </p>
    </form>
  );
}
