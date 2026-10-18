import BarChart3 from 'lucide-react/dist/esm/icons/bar-chart-3';
import Building2 from 'lucide-react/dist/esm/icons/building-2';
import Columns3 from 'lucide-react/dist/esm/icons/columns-3';
import Home from 'lucide-react/dist/esm/icons/home';
import type { MouseEvent } from 'react';
import { cn } from '@/lib/utils';
import { navigateTo } from '@/lib/navigation';

const navigation = [
  { label: 'Home', mobileLabel: 'Home', href: '/dashboard', icon: Home },
  { label: 'Analytics', mobileLabel: 'Stats', href: '/analytics', icon: BarChart3 },
  { label: 'Organization board', mobileLabel: 'Org board', href: '/organization-board', icon: Columns3 },
  { label: 'Organization', mobileLabel: 'Org', href: '/organization', icon: Building2 },
];

export function AppSidebar() {
  const pathname = window.location.pathname;
  const openRoute = (event: MouseEvent<HTMLAnchorElement>, href: string) => {
    event.preventDefault();
    navigateTo(href);
  };

  return (
    <aside className="app-sidebar fixed inset-x-0 bottom-0 z-30 flex h-[calc(4rem+env(safe-area-inset-bottom))] shrink-0 flex-row border-t border-slate-200 bg-slate-50 pb-[env(safe-area-inset-bottom)] sm:static sm:pb-0 sm:h-auto sm:w-60 sm:flex-col sm:border-r sm:border-t-0">
      <a
        href="/"
        aria-label="KanbanKaii home"
        className="hidden h-16 shrink-0 items-center justify-center gap-3 border-b border-slate-100 px-2 sm:flex sm:justify-start sm:px-3"
      >
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-violet-700 text-base font-bold text-white">
          K
        </span>
        <span className="hidden truncate text-lg font-bold tracking-tight text-slate-950 sm:block">
          KanbanKaii
        </span>
      </a>
      <nav className="grid flex-1 grid-cols-4 items-center gap-1 px-2 py-2 sm:flex sm:flex-col sm:items-stretch sm:gap-2 sm:px-4 sm:py-6" aria-label="Primary navigation">
        {navigation.map(({ label, mobileLabel, href, icon: Icon }) => {
          const active = pathname === href;
          return (
            <a
              key={label}
              href={href}
              onClick={(event) => openRoute(event, href)}
              aria-label={label}
              title={label}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'relative flex h-12 min-w-0 flex-col items-center justify-center gap-1 rounded-xl text-slate-600 transition-colors hover:bg-slate-100 hover:text-violet-600 sm:h-10 sm:w-full sm:flex-row sm:justify-start sm:gap-3 sm:px-3',
                active && 'bg-violet-100 text-violet-800',
              )}
            >
              <Icon className="h-[18px] w-[18px] shrink-0" />
              <span className="max-w-full truncate px-1 text-[11px] font-semibold leading-none sm:hidden">{mobileLabel}</span>
              <span className="hidden text-sm font-medium sm:block">{label}</span>
            </a>
          );
        })}
      </nav>
    </aside>
  );
}
