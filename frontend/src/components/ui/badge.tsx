import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import type * as React from 'react';

import { cn } from '@/lib/utils';

/**
 * Status tones deliberately avoid red for absent signals. "Not detected" and "not determinable"
 * are neutral outcomes, and colouring them as failures would be the UI making a claim the
 * analyzer did not (docs/blueprint/decisions.md D5).
 */
const badgeVariants = cva(
  'inline-flex items-center justify-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-none w-fit whitespace-nowrap shrink-0',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary/15 text-primary',
        outline: 'border-border text-foreground',
        muted: 'border-transparent bg-muted text-muted-foreground',
        verified: 'border-transparent bg-status-verified/15 text-status-verified',
        stronglyInferred:
          'border border-status-strongly-inferred/30 bg-status-strongly-inferred/10 text-status-strongly-inferred',
        inferred: 'border-transparent bg-status-inferred/15 text-status-inferred',
        aiInferred:
          'border border-status-ai-inferred/30 bg-status-ai-inferred/10 text-status-ai-inferred',
        neutral: 'border-border/70 bg-transparent text-status-neutral',
        attention: 'border-transparent bg-status-attention/15 text-status-attention',
      },
    },
    defaultVariants: { variant: 'default' },
  },
);

function Badge({
  className,
  variant,
  asChild = false,
  ...props
}: React.ComponentProps<'span'> & VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : 'span';
  return (
    <Comp data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
