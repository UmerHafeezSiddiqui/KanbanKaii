import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  DndContext,
  DragOverlay,
  MouseSensor,
  TouchSensor,
  KeyboardSensor,
  closestCorners,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { toast } from 'sonner';
import ArrowDownUp from 'lucide-react/dist/esm/icons/arrow-down-up';
import ListFilter from 'lucide-react/dist/esm/icons/list-filter';
import Plus from 'lucide-react/dist/esm/icons/plus';
import Search from 'lucide-react/dist/esm/icons/search';
import {
  createTicket,
  createOrganizationTicket,
  deleteOrganizationTicket,
  deleteTicket as deleteStoredTicket,
  fetchTickets,
  fetchOrganizationTickets,
  mapApiTicket,
  updateTicket,
  updateOrganizationTicket,
  updateTicketStatus,
  type ApiTicket,
  type OrganizationTicketView,
} from '@/api/tickets';
import {
  TICKET_STATUSES,
  TICKET_PRIORITIES,
  TICKET_SOURCES,
  type Ticket,
  type TicketFormValues,
  type TicketPriority,
  type TicketSource,
  type TicketStatus,
} from '@/types/ticket';
import { KanbanColumn } from './KanbanColumn';
import { TicketCard } from './TicketCard';
import { Skeleton } from '@/components/ui/skeleton';
import { getSupabaseClient } from '@/lib/supabase';
import { useAuth } from '@/auth/AuthContext';
import { notificationSettingsFromUser } from '@/api/settings';
import type { OrganizationRole } from '@/api/organizations';

const TicketModal = lazy(() => import('./TicketModal').then((module) => ({ default: module.TicketModal })));

function mergeTicket(items: Ticket[], incoming: Ticket): Ticket[] {
  const existingIndex = items.findIndex((ticket) => ticket.id === incoming.id);
  if (existingIndex === -1) return [incoming, ...items];
  return items.map((ticket) => ticket.id === incoming.id ? incoming : ticket);
}

type BoardMenu = 'filter' | 'sort' | null;
type SortMode = 'NEWEST' | 'OLDEST' | 'PRIORITY' | 'TITLE';

const sortOptions: { value: SortMode; label: string }[] = [
  { value: 'NEWEST', label: 'Newest first' },
  { value: 'OLDEST', label: 'Oldest first' },
  { value: 'PRIORITY', label: 'Priority: high to low' },
  { value: 'TITLE', label: 'Title: A to Z' },
];

const priorityOrder: Record<TicketPriority, number> = {
  High: 0,
  Medium: 1,
  Low: 2,
};

interface KanbanBoardProps {
  organizationId?: string;
  organizationBoardId?: string;
  organizationTicketView?: OrganizationTicketView;
  organizationBoardNames?: Record<string, string>;
  organizationRole?: OrganizationRole;
  organizationMembers?: Array<{ user_id: string; display_name: string }>;
  toolbarContext?: ReactNode;
  skipLoad?: boolean;
}

export function KanbanBoard({
  organizationId,
  organizationBoardId,
  organizationTicketView = 'overview',
  organizationBoardNames = {},
  organizationRole,
  organizationMembers = [],
  toolbarContext,
  skipLoad = false,
}: KanbanBoardProps) {
  const { user } = useAuth();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [isLoading, setIsLoading] = useState(!skipLoad);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [editingTicket, setEditingTicket] = useState<Ticket | null>(null);
  const [defaultStatus, setDefaultStatus] = useState<TicketStatus>('Pending');
  const [modalOpen, setModalOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [priorityFilter, setPriorityFilter] = useState<TicketPriority | 'ALL'>('ALL');
  const [sourceFilter, setSourceFilter] = useState<TicketSource | 'ALL'>('ALL');
  const [sortMode, setSortMode] = useState<SortMode>('NEWEST');
  const [openMenu, setOpenMenu] = useState<BoardMenu>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const controlsRef = useRef<HTMLDivElement>(null);
  const ticketsRef = useRef<Ticket[]>([]);
  const notificationSettings = useMemo(() => notificationSettingsFromUser(user), [user]);
  const isOrganizationBoard = Boolean(organizationId);
  const canManageOrganization = organizationRole === 'OWNER' || organizationRole === 'TEAM_LEAD';
  const canCreate = !skipLoad && (!isOrganizationBoard || canManageOrganization);
  const assigneeOptions = useMemo(
    () => organizationMembers
      .filter((member) => member.user_id !== user?.id)
      .map((member) => ({ value: member.user_id, label: member.display_name })),
    [organizationMembers, user?.id],
  );
  const canMoveTicket = useCallback(
    () => !skipLoad && !isOrganizationBoard,
    [isOrganizationBoard, skipLoad],
  );

  const activeFilterCount = Number(priorityFilter !== 'ALL') + Number(sourceFilter !== 'ALL');

  const visibleTickets = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const matches = tickets.filter((ticket) => {
      const searchable = `${ticket.title} ${ticket.description} ${ticket.assignee} ${ticket.source} ${ticket.priority}`.toLowerCase();
      return (
        (!organizationBoardId || ticket.boardId === organizationBoardId) &&
        (!normalizedQuery || searchable.includes(normalizedQuery)) &&
        (priorityFilter === 'ALL' || ticket.priority === priorityFilter) &&
        (sourceFilter === 'ALL' || ticket.source === sourceFilter)
      );
    });

    return [...matches].sort((left, right) => {
      if (sortMode === 'TITLE') return left.title.localeCompare(right.title);
      if (sortMode === 'PRIORITY') {
        const priorityDifference = priorityOrder[left.priority] - priorityOrder[right.priority];
        if (priorityDifference !== 0) return priorityDifference;
      }
      const leftTime = left.createdAt ? new Date(left.createdAt).getTime() : 0;
      const rightTime = right.createdAt ? new Date(right.createdAt).getTime() : 0;
      return sortMode === 'OLDEST' ? leftTime - rightTime : rightTime - leftTime;
    });
  }, [organizationBoardId, priorityFilter, query, sortMode, sourceFilter, tickets]);

  const ticketsByStatus = useMemo(() => {
    const grouped: Record<TicketStatus, Ticket[]> = {
      Pending: [],
      'In Progress': [],
      Completed: [],
    };
    for (const ticket of visibleTickets) {
      grouped[ticket.status]?.push(ticket);
    }
    return grouped;
  }, [visibleTickets]);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      if (!controlsRef.current?.contains(event.target as Node)) setOpenMenu(null);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpenMenu(null);
    };
    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const loadTickets = useCallback(async (signal?: AbortSignal) => {
    if (skipLoad) {
      setTickets([]);
      setLoadError(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setLoadError(null);
    try {
      setTickets(
        organizationId
          ? await fetchOrganizationTickets(organizationId, {
              signal,
              view: organizationTicketView,
              boardId: organizationBoardId,
            })
          : await fetchTickets({ signal }),
      );
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      if (error instanceof TypeError) {
        setLoadError('Could not connect to the ticket API. Check your connection and retry.');
        return;
      }
      setLoadError(error instanceof Error ? error.message : 'Could not load tickets');
    } finally {
      if (!signal?.aborted) setIsLoading(false);
    }
  }, [organizationBoardId, organizationId, organizationTicketView, skipLoad]);

  useEffect(() => {
    const controller = new AbortController();
    void loadTickets(controller.signal);
    return () => controller.abort();
  }, [loadTickets]);

  useEffect(() => {
    ticketsRef.current = tickets;
  }, [tickets]);

  useEffect(() => {
    if (!activeId) return undefined;

    const previousUserSelect = document.body.style.userSelect;
    const previousWebkitUserSelect = document.body.style.webkitUserSelect;
    const previousOverscrollBehavior = document.body.style.overscrollBehavior;

    document.body.style.userSelect = 'none';
    document.body.style.webkitUserSelect = 'none';
    document.body.style.overscrollBehavior = 'contain';

    return () => {
      document.body.style.userSelect = previousUserSelect;
      document.body.style.webkitUserSelect = previousWebkitUserSelect;
      document.body.style.overscrollBehavior = previousOverscrollBehavior;
    };
  }, [activeId]);

  useEffect(() => {
    if (!user || skipLoad) return undefined;

    const supabase = getSupabaseClient();
    const realtimeFilter = organizationId
      ? `organization_id=eq.${organizationId}`
      : `owner_id=eq.${user.id}`;
    const channel = supabase
      .channel(organizationId ? `organization-tickets:${organizationId}` : `tickets:${user.id}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'tickets',
          filter: realtimeFilter,
        },
        (payload) => {
          const incoming = mapApiTicket(payload.new as ApiTicket);
          if (isOrganizationBoard && incoming.scope !== 'ORGANIZATION') return;
          const nextTickets = mergeTicket(ticketsRef.current, incoming);
          ticketsRef.current = nextTickets;
          setTickets(nextTickets);
          if (incoming.source === 'Slack' && notificationSettings.newTickets) {
            toast.success(`New Slack ticket: ${incoming.title}`);
          }
        },
      )
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'tickets',
          filter: realtimeFilter,
        },
        (payload) => {
          const incoming = mapApiTicket(payload.new as ApiTicket);
          if (isOrganizationBoard && incoming.scope !== 'ORGANIZATION') return;
          const previous = ticketsRef.current.find((ticket) => ticket.id === incoming.id);
          const nextTickets = mergeTicket(ticketsRef.current, incoming);
          ticketsRef.current = nextTickets;
          setTickets(nextTickets);
          if (
            previous &&
            previous.status !== incoming.status &&
            notificationSettings.statusChanges
          ) {
            toast.info(`${incoming.title} moved to ${incoming.status}`);
          }
        },
      )
      .subscribe();

    return () => {
      void supabase.removeChannel(channel);
    };
  }, [isOrganizationBoard, notificationSettings.newTickets, notificationSettings.statusChanges, organizationId, skipLoad, user]);

  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 140, tolerance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const activeTicket = tickets.find((ticket) => ticket.id === activeId);

  const statusFromDropTarget = (id: string): TicketStatus | undefined => {
    const targetTicket = tickets.find((ticket) => ticket.id === id);
    if (targetTicket) return targetTicket.status;
    return TICKET_STATUSES.find((status) => status === id);
  };

  const handleDragEnd = ({ active, over }: DragEndEvent) => {
    setActiveId(null);
    if (!over) return;
    const nextStatus = statusFromDropTarget(String(over.id));
    const current = tickets.find((ticket) => ticket.id === active.id);
    if (!current || !nextStatus || current.status === nextStatus || !canMoveTicket()) return;

    setTickets((items) =>
      items.map((ticket) => ticket.id === active.id ? { ...ticket, status: nextStatus } : ticket),
    );
    void updateTicketStatus(current.id, nextStatus)
      .then((savedTicket) => {
        setTickets((items) =>
          items.map((ticket) => ticket.id === savedTicket.id ? savedTicket : ticket),
        );
        toast.success(`Moved to ${nextStatus}`);
      })
      .catch(() => {
        setTickets((items) =>
          items.map((ticket) => ticket.id === current.id ? current : ticket),
        );
        toast.error('Could not save the status change');
      });
  };

  const openEditor = (ticket: Ticket) => {
    setEditingTicket(ticket);
    setModalOpen(true);
  };

  const openCreator = (status: TicketStatus) => {
    if (!canCreate) return;
    setEditingTicket(null);
    setDefaultStatus(status);
    setModalOpen(true);
  };

  const saveTicket = async (values: TicketFormValues): Promise<boolean> => {
    if (editingTicket) {
      try {
        const ticketOrganizationId = organizationId ?? editingTicket.organizationId;
        const updatedTicket = ticketOrganizationId && editingTicket.scope === 'ORGANIZATION'
          ? await updateOrganizationTicket(ticketOrganizationId, editingTicket.id, values)
          : await updateTicket(editingTicket.id, values);
        setTickets((items) =>
          items.map((item) => item.id === updatedTicket.id ? updatedTicket : item),
        );
        setModalOpen(false);
        toast.success('Ticket updated');
        return true;
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'Could not update the ticket');
        return false;
      }
    }

    try {
      const createdTicket = organizationId
        ? await createOrganizationTicket(organizationId, values, organizationBoardId)
        : await createTicket(values);
      setTickets((items) => mergeTicket(items, createdTicket));
      setModalOpen(false);
      toast.success('Ticket created');
      return true;
    } catch {
      toast.error('Could not create the ticket');
      return false;
    }
  };

  const deleteTicket = async (id: string): Promise<boolean> => {
    try {
      const ticket = tickets.find((item) => item.id === id);
      const ticketOrganizationId = organizationId ?? ticket?.organizationId;
      if (ticketOrganizationId && ticket?.scope === 'ORGANIZATION') {
        await deleteOrganizationTicket(ticketOrganizationId, id);
      }
      else await deleteStoredTicket(id);
      setTickets((items) => items.filter((ticket) => ticket.id !== id));
      setModalOpen(false);
      toast.success('Ticket deleted');
      return true;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not delete the ticket');
      return false;
    }
  };

  return (
    <>
      <div className="flex min-h-14 items-center gap-2 border-b border-slate-200 bg-white px-3 py-2.5 sm:gap-3 sm:px-6">
        {toolbarContext && (
          <div className="min-w-0 shrink">
            {toolbarContext}
          </div>
        )}
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <button
            type="button"
            aria-label="Search tickets"
            aria-expanded={searchOpen || Boolean(query)}
            onClick={() => setSearchOpen((open) => !open)}
            className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg border text-slate-500 transition hover:border-violet-300 hover:text-violet-600 ${
              searchOpen || query ? 'border-violet-200 bg-violet-50 text-violet-700' : 'border-slate-200 bg-white'
            }`}
          >
            <Search className="h-4 w-4" />
          </button>
          {(searchOpen || query) && (
            <label className="flex min-w-0 flex-1 items-center rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-sm sm:w-72 sm:flex-none">
              <input
                autoFocus
                aria-label="Search tickets"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search tickets"
                className="w-full bg-transparent text-xs text-slate-700 outline-none placeholder:text-slate-400"
              />
            </label>
          )}
        </div>
        <div ref={controlsRef} className="relative ml-auto flex w-auto shrink-0 items-center justify-end gap-1 sm:gap-2">
          {canCreate && <button type="button" aria-label="New ticket" onClick={() => openCreator('Pending')} className="flex min-h-10 items-center gap-2 rounded-lg bg-violet-700 px-3 py-2 text-sm font-semibold text-white hover:bg-violet-800">
            <Plus className="h-3.5 w-3.5" /><span className="hidden sm:inline">New ticket</span>
          </button>}
          <button
            type="button"
            aria-label="Filter tickets"
            aria-expanded={openMenu === 'filter'}
            onClick={() => setOpenMenu((menu) => menu === 'filter' ? null : 'filter')}
            className={`flex items-center min-h-10 gap-2 rounded-lg px-3 py-2 text-sm font-medium hover:bg-slate-100 ${activeFilterCount ? 'text-violet-700' : 'text-slate-500 hover:text-slate-800'}`}
          >
            <ListFilter className="h-3.5 w-3.5" /><span className="hidden sm:inline">Filter</span>
            {activeFilterCount > 0 && <span className="grid h-4 min-w-4 place-items-center rounded-full bg-violet-100 px-1 text-[9px] font-bold text-violet-700">{activeFilterCount}</span>}
          </button>
          <button
            type="button"
            aria-label="Sort tickets"
            aria-expanded={openMenu === 'sort'}
            onClick={() => setOpenMenu((menu) => menu === 'sort' ? null : 'sort')}
            className={`flex items-center min-h-10 gap-2 rounded-lg px-3 py-2 text-sm font-medium hover:bg-slate-100 ${sortMode !== 'NEWEST' ? 'text-violet-700' : 'text-slate-500 hover:text-slate-800'}`}
          >
            <ArrowDownUp className="h-3.5 w-3.5" /><span className="hidden sm:inline">Sort</span>
          </button>

          {openMenu === 'filter' && (
            <div className="absolute right-0 top-10 z-40 w-64 rounded-xl border border-slate-200 bg-white p-3 shadow-xl">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-slate-800">Filter tickets</p>
                <button
                  type="button"
                  disabled={activeFilterCount === 0}
                  onClick={() => { setPriorityFilter('ALL'); setSourceFilter('ALL'); }}
                  className="text-[10px] font-semibold text-violet-600 hover:text-violet-800 disabled:text-slate-300"
                >
                  Clear
                </button>
              </div>
              <div className="mt-3">
                <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Priority</p>
                <div className="flex flex-wrap gap-1.5">
                  {(['ALL', ...TICKET_PRIORITIES] as const).map((priority) => (
                    <button
                      key={priority}
                      type="button"
                      onClick={() => setPriorityFilter(priority)}
                      className={`rounded-md border px-2 py-1 text-[10px] font-medium ${priorityFilter === priority ? 'border-violet-200 bg-violet-50 text-violet-700' : 'border-slate-200 text-slate-500 hover:border-slate-300'}`}
                    >
                      {priority === 'ALL' ? 'All' : priority}
                    </button>
                  ))}
                </div>
              </div>
              <div className="mt-3">
                <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Source</p>
                <div className="flex flex-wrap gap-1.5">
                  {(['ALL', ...TICKET_SOURCES] as const).map((source) => (
                    <button
                      key={source}
                      type="button"
                      onClick={() => setSourceFilter(source)}
                      className={`rounded-md border px-2 py-1 text-[10px] font-medium ${sourceFilter === source ? 'border-violet-200 bg-violet-50 text-violet-700' : 'border-slate-200 text-slate-500 hover:border-slate-300'}`}
                    >
                      {source === 'ALL' ? 'All' : source}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {openMenu === 'sort' && (
            <div className="absolute right-0 top-10 z-40 w-52 rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl">
              {sortOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => { setSortMode(option.value); setOpenMenu(null); }}
                  className={`block w-full rounded-lg px-3 py-2 text-left text-[11px] font-medium ${sortMode === option.value ? 'bg-violet-50 text-violet-700' : 'text-slate-600 hover:bg-slate-50'}`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={({ active }: DragStartEvent) => setActiveId(String(active.id))}
        onDragCancel={() => setActiveId(null)}
        onDragEnd={handleDragEnd}
      >
        {isLoading && tickets.length > 0 && (
          <div className="border-b border-slate-200 bg-white px-6 py-2">
            <div className="flex items-center gap-3 text-[11px] font-medium text-slate-500">
              <Skeleton className="h-1.5 flex-1 rounded-full bg-violet-100" />
              Refreshing tickets…
            </div>
          </div>
        )}
        {loadError && (
          <div className="flex items-center justify-between border-b border-red-200 bg-red-50 px-6 py-2 text-xs text-red-700">
            <span>{loadError}</span>
            <button
              type="button"
              className="font-semibold hover:text-red-900"
              onClick={() => void loadTickets()}
            >
              Retry
            </button>
          </div>
        )}
        <div className="overflow-x-auto overscroll-x-contain">
          <div className="flex min-h-[calc(100dvh-11rem)] snap-x snap-mandatory gap-4 bg-slate-50 p-4 sm:grid sm:min-h-[calc(100dvh-7.5rem)] sm:min-w-[780px] sm:grid-cols-3 sm:gap-4 sm:p-6">
            {TICKET_STATUSES.map((status) => (
              <KanbanColumn
                key={status}
                id={status}
                title={status}
                tickets={ticketsByStatus[status] ?? []}
                onEdit={openEditor}
                onAdd={openCreator}
                canAdd={canCreate}
                canDragTicket={canMoveTicket}
                boardNames={organizationBoardNames}
                isLoading={isLoading}
              />
            ))}
          </div>
        </div>
        <DragOverlay dropAnimation={{ duration: 180, easing: 'ease-out' }}>
          {activeTicket ? (
            <TicketCard
              ticket={activeTicket}
              onEdit={() => undefined}
              boardName={activeTicket.boardId ? organizationBoardNames[activeTicket.boardId] : undefined}
              overlay
              draggable={false}
            />
          ) : null}
        </DragOverlay>
      </DndContext>

      {modalOpen && (
        <Suspense fallback={null}>
          <TicketModal
            ticket={editingTicket}
            isOpen={modalOpen}
            onClose={() => setModalOpen(false)}
            onSave={saveTicket}
            onDelete={deleteTicket}
            defaultStatus={defaultStatus}
            readOnly={isOrganizationBoard && !canManageOrganization}
            assigneeOptions={isOrganizationBoard ? assigneeOptions : undefined}
          />
        </Suspense>
      )}
    </>
  );
}
