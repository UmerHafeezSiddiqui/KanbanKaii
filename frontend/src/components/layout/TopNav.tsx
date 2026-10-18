import Bell from 'lucide-react/dist/esm/icons/bell';
import UserRound from 'lucide-react/dist/esm/icons/user-round';
import { useEffect, useRef, useState, type MouseEvent, type SyntheticEvent } from 'react';
import { useAuth } from '@/auth/AuthContext';
import { fetchTickets, mapApiTicket, type ApiTicket } from '@/api/tickets';
import type { Ticket } from '@/types/ticket';
import { BackendStatus } from './BackendStatus';
import { navigateTo } from '@/lib/navigation';
import { getSupabaseClient } from '@/lib/supabase';

interface TopNavProps {
  pageTitle: string;
}

const notificationReadKey = (userId: string) => `kanbankaii:notifications-read:${userId}`;

function mergeNotification(items: Ticket[], incoming: Ticket): Ticket[] {
  const nextItems = items.filter((ticket) => ticket.id !== incoming.id);
  return [incoming, ...nextItems].slice(0, 5);
}

export function TopNav({ pageTitle }: TopNavProps) {
  const { user, signOut } = useAuth();
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [notifications, setNotifications] = useState<Ticket[]>([]);
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const [notificationsError, setNotificationsError] = useState<string | null>(null);
  const [notificationsReadAt, setNotificationsReadAt] = useState(0);
  const notificationsMenuRef = useRef<HTMLDetailsElement>(null);
  const profileMenuRef = useRef<HTMLDetailsElement>(null);
  const displayName =
    (user?.user_metadata.display_name as string | undefined) ||
    user?.email?.split('@')[0] ||
    'Account';

  const unreadNotifications = notifications.filter((ticket) => {
    if (!ticket.createdAt) return notificationsReadAt === 0;
    return new Date(ticket.createdAt).getTime() > notificationsReadAt;
  });

  useEffect(() => {
    if (!user) {
      setNotificationsReadAt(0);
      setNotifications([]);
      return;
    }

    const savedReadAt = Number(window.localStorage.getItem(notificationReadKey(user.id)) ?? 0);
    setNotificationsReadAt(Number.isFinite(savedReadAt) ? savedReadAt : 0);
  }, [user]);

  useEffect(() => {
    if (!user) return undefined;

    const supabase = getSupabaseClient();
    const channel = supabase
      .channel(`top-nav-ticket-notifications:${user.id}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'tickets',
          filter: `owner_id=eq.${user.id}`,
        },
        (payload) => {
          const incoming = mapApiTicket(payload.new as ApiTicket);
          setNotifications((items) => mergeNotification(items, incoming));
        },
      )
      .subscribe();

    return () => {
      void supabase.removeChannel(channel);
    };
  }, [user]);

  const handleSignOut = async () => {
    setIsSigningOut(true);
    try {
      await signOut();
      window.location.replace('/auth');
    } finally {
      setIsSigningOut(false);
    }
  };

  const openRoute = (event: MouseEvent<HTMLAnchorElement>, path: string) => {
    event.preventDefault();
    navigateTo(path);
    if (notificationsMenuRef.current) notificationsMenuRef.current.open = false;
    if (profileMenuRef.current) profileMenuRef.current.open = false;
  };

  const loadNotifications = async () => {
    if (notificationsLoading) return;
    setNotificationsLoading(true);
    setNotificationsError(null);
    try {
      const tickets = await fetchTickets();
      setNotifications(tickets.slice(0, 5));
    } catch (error) {
      setNotificationsError(
        error instanceof Error ? error.message : 'Could not load notifications',
      );
    } finally {
      setNotificationsLoading(false);
    }
  };

  const handleNotificationToggle = (event: SyntheticEvent<HTMLDetailsElement>) => {
    if (!event.currentTarget.open) return;
    if (profileMenuRef.current) profileMenuRef.current.open = false;
    void loadNotifications();
  };

  const handleProfileToggle = (event: SyntheticEvent<HTMLDetailsElement>) => {
    if (event.currentTarget.open && notificationsMenuRef.current) {
      notificationsMenuRef.current.open = false;
    }
  };

  const markNotificationsAsRead = () => {
    if (!user || unreadNotifications.length === 0) return;
    const readAt = Date.now();
    window.localStorage.setItem(notificationReadKey(user.id), String(readAt));
    setNotificationsReadAt(readAt);
  };

  useEffect(() => {
    const closeMenus = () => {
      if (notificationsMenuRef.current) notificationsMenuRef.current.open = false;
      if (profileMenuRef.current) profileMenuRef.current.open = false;
    };

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (
        !notificationsMenuRef.current?.contains(target) &&
        !profileMenuRef.current?.contains(target)
      ) {
        closeMenus();
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeMenus();
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const notificationTime = (createdAt?: string) => {
    if (!createdAt) return 'Recently';
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(createdAt));
  };

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 sm:h-16 sm:px-6">
      <div className="min-w-0 flex-1">
        <p className="truncate text-base font-semibold tracking-tight text-slate-950 sm:text-lg">{pageTitle}</p>

      </div>

      <div className="flex shrink-0 items-center gap-1.5 sm:gap-3">
        <BackendStatus />
        <details ref={notificationsMenuRef} className="group relative" onToggle={handleNotificationToggle}>
          <summary className="relative flex h-11 w-11 cursor-pointer list-none items-center justify-center rounded-xl text-slate-600 hover:bg-white/80 hover:text-violet-600 [&::-webkit-details-marker]:hidden">
            <Bell className="h-[17px] w-[17px]" />
            {unreadNotifications.length > 0 && (
              <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-rose-500 ring-2 ring-white" />
            )}
            <span className="sr-only">Notifications</span>
          </summary>
          <div className="absolute right-[-3rem] z-40 mt-2 w-[min(20rem,calc(100vw-1.5rem))] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-xl sm:right-0 sm:w-72">
            <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-4 py-3">
              <div>
                <p className="text-sm font-semibold text-slate-800">Notifications</p>
                <p className="text-xs text-slate-500">
                  {unreadNotifications.length > 0
                    ? `${unreadNotifications.length} unread ticket${unreadNotifications.length === 1 ? '' : 's'}`
                    : 'You are all caught up'}
                </p>
              </div>
              <button
                type="button"
                disabled={notificationsLoading || unreadNotifications.length === 0}
                onClick={markNotificationsAsRead}
                className="shrink-0 text-xs font-semibold text-violet-600 hover:text-violet-800 disabled:cursor-default disabled:text-slate-300"
              >
                Mark all as read
              </button>
            </div>
            <div className="max-h-80 divide-y divide-slate-100 overflow-y-auto">
              {notificationsLoading && (
                <p className="px-4 py-5 text-center text-xs text-slate-500">Loading tickets…</p>
              )}
              {!notificationsLoading && notificationsError && (
                <div className="px-4 py-4">
                  <p className="text-xs text-rose-600">{notificationsError}</p>
                  <button type="button" onClick={() => void loadNotifications()} className="mt-2 text-xs font-semibold text-violet-600 hover:text-violet-800">Try again</button>
                </div>
              )}
              {!notificationsLoading && !notificationsError && notifications.length === 0 && (
                <p className="px-4 py-5 text-center text-xs text-slate-500">No tickets have been created yet.</p>
              )}
              {!notificationsLoading && !notificationsError && notifications.map((ticket) => {
                const isUnread = !ticket.createdAt || new Date(ticket.createdAt).getTime() > notificationsReadAt;
                return (
                <a key={ticket.id} href="/dashboard" onClick={(event) => openRoute(event, '/dashboard')} className={`block px-4 py-3 hover:bg-slate-50 ${isUnread ? 'bg-violet-50/40' : ''}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-start gap-2">
                      {isUnread && <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-500" />}
                      <p className="line-clamp-2 text-xs font-medium leading-4 text-slate-700">{ticket.title}</p>
                    </div>
                    <span className="shrink-0 rounded bg-violet-50 px-1.5 py-0.5 text-xs font-semibold text-violet-600">{ticket.source}</span>
                  </div>
                  <p className="mt-1.5 text-xs text-slate-500">Created {notificationTime(ticket.createdAt)}</p>
                </a>
                );
              })}
            </div>
          </div>
        </details>

        <details ref={profileMenuRef} className="group relative" onToggle={handleProfileToggle}>
          <summary aria-label="Account menu" className="flex cursor-pointer list-none items-center gap-2 min-h-11 rounded-xl p-1 hover:bg-slate-100 sm:pr-2 [&::-webkit-details-marker]:hidden">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-800 text-white">
              <UserRound className="h-4 w-4" />
            </span>
            <span className="hidden max-w-28 truncate text-xs font-medium text-slate-600 sm:inline">{displayName}</span>
          </summary>
          <div className="absolute right-0 z-40 mt-2 w-[min(12rem,calc(100vw-1.5rem))] rounded-lg border border-slate-200 bg-white p-1.5 shadow-xl">
            <div className="border-b border-slate-100 px-3 py-2.5">
              <p className="truncate text-xs font-semibold text-slate-800">{displayName}</p>
              <p className="mt-0.5 truncate text-xs text-slate-500">{user?.email}</p>
            </div>
            <a href="/profile" onClick={(event) => openRoute(event, '/profile')} className="mt-1 block rounded-md px-3 py-2 text-xs font-medium text-slate-600 hover:bg-violet-50 hover:text-violet-700">
              Profile
            </a>
            <a href="/settings" onClick={(event) => openRoute(event, '/settings')} className="block rounded-md px-3 py-2 text-xs font-medium text-slate-600 hover:bg-violet-50 hover:text-violet-700">
              Settings
            </a>
            <button
              type="button"
              disabled={isSigningOut}
              onClick={() => void handleSignOut()}
              className="block w-full rounded-md px-3 py-2 text-left text-xs font-medium text-rose-600 hover:bg-rose-50 disabled:opacity-50"
            >
              {isSigningOut ? 'Signing out…' : 'Sign out'}
            </button>
          </div>
        </details>
      </div>
    </header>
  );
}
