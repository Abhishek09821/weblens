import { Link } from 'react-router-dom';

import { Button } from '@/components/ui/button';

export function NotFoundRoute() {
  return (
    <div className="mx-auto max-w-md space-y-4 py-16 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">Page not found</h1>
      <p className="text-sm text-muted-foreground">
        That route does not exist in WebLens.
      </p>
      <Button asChild variant="outline">
        <Link to="/">Back to analyze</Link>
      </Button>
    </div>
  );
}
