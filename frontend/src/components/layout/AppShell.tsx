import { CircleAlertIcon, MonitorIcon, MoonIcon, SunIcon } from 'lucide-react';
import { useContext, type ReactNode } from 'react';
import { Link, NavLink } from 'react-router-dom';

import { ThemeContext } from '@/components/layout/ThemeProvider';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useHealth } from '@/features/scan/useHealth';
import { isPersistent } from '@/lib/db/repository';
import { cn } from '@/lib/utils';
import type { ThemePreference } from '@/lib/prefs/prefs';

const THEME_ICONS: Record<ThemePreference, typeof SunIcon> = {
  system: MonitorIcon,
  light: SunIcon,
  dark: MoonIcon,
};

export function AppShell({ children }: { children: ReactNode }) {
  const health = useHealth();
  const persistent = isPersistent();

  return (
    <div className="min-h-dvh flex flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2 focus:text-sm"
      >
        Skip to content
      </a>

      <header className="border-b border-border bg-card/60 backdrop-blur sticky top-0 z-30">
        <div className="mx-auto flex h-14 w-full max-w-[1600px] items-center gap-4 px-4">
          <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <img src="/favicon.svg" alt="" aria-hidden="true" className="size-5" />
            <span>WebLens</span>
          </Link>
          <Badge variant="muted" className="font-mono">
            {health.data?.engine_version ? `v${health.data.engine_version}` : 'offline'}
          </Badge>

          <nav aria-label="Main" className="ml-2 hidden items-center gap-1 text-sm sm:flex">
            <ShellLink to="/">Analyze</ShellLink>
            <ShellLink to="/about">Methodology</ShellLink>
          </nav>

          <div className="ml-auto flex items-center gap-2">
            {!persistent && (
              <Badge variant="attention" className="hidden sm:inline-flex">
                <CircleAlertIcon className="size-3" aria-hidden="true" />
                Session-only storage
              </Badge>
            )}
            {health.data && !health.data.browser.available && (
              <Badge variant="neutral" className="hidden font-normal md:inline-flex">
                Browser collection unavailable
              </Badge>
            )}
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6">
        {children}
      </main>

      <footer className="border-t border-border px-4 py-4">
        <div className="mx-auto flex max-w-[1600px] flex-col gap-1 text-xs text-muted-foreground">
          <p>
            Passive analysis of publicly reachable pages. Detection is evidence-based and does not
            use an AI model.
          </p>
          <p>
            <Link to="/about" className="underline underline-offset-2 hover:text-foreground">
              Methodology and limitations
            </Link>
          </p>
        </div>
      </footer>
    </div>
  );
}

function ShellLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        cn(
          'rounded-md px-2.5 py-1.5 transition-colors',
          isActive ? 'bg-secondary text-secondary-foreground' : 'text-muted-foreground hover:text-foreground',
        )
      }
    >
      {children}
    </NavLink>
  );
}

function ThemeToggle() {
  const { theme, setTheme } = useContext(ThemeContext);
  const Icon = THEME_ICONS[theme];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={`Theme: ${theme}`}>
          <Icon className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuLabel>Theme</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {(['system', 'light', 'dark'] as const).map((option) => {
          const OptionIcon = THEME_ICONS[option];
          return (
            <DropdownMenuItem key={option} onSelect={() => setTheme(option)}>
              <OptionIcon className="size-4" />
              <span className="capitalize">{option}</span>
              {theme === option && <span className="ml-auto text-xs text-muted-foreground">active</span>}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
