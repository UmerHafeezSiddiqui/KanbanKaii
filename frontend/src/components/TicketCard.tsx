import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { cn } from '@/lib/utils';
import type { Ticket } from '@/types/ticket';
import type { CSSProperties } from 'react';
import Github from 'lucide-react/dist/esm/icons/github';
import MessageSquare from 'lucide-react/dist/esm/icons/message-square';
import UserRound from 'lucide-react/dist/esm/icons/user-round';

interface TicketCardProps {
  ticket: Ticket;
  onEdit: (ticket: Ticket) => void;
  boardName?: string;
  overlay?: boolean;
  draggable?: boolean;
}

const priorityConfig = {
  High: {
    bg: 'bg-red-50 text-red-700 border-red-200',
    dark: 'dark:bg-red-950/30 dark:text-red-300 dark:border-red-900',
  },
  Medium: {
    bg: 'bg-amber-50 text-amber-700 border-amber-200',
    dark: 'dark:bg-amber-950/30 dark:text-amber-300 dark:border-amber-900',
  },
  Low: {
    bg: 'bg-slate-50 text-slate-700 border-slate-200',
    dark: 'dark:bg-slate-900/50 dark:text-slate-300 dark:border-slate-800',
  },
};

export function TicketCard({ ticket, onEdit, boardName, overlay = false, draggable = true }: TicketCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: ticket.id, disabled: overlay || !draggable });

  const style: CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    userSelect: 'none',
    WebkitUserSelect: 'none',
    WebkitTouchCallout: 'none',
  };

  const priority = priorityConfig[ticket.priority];

  const SourceIcon = ticket.source === 'GitHub' ? Github : MessageSquare;
  const isAssignedTicket = ticket.scope !== 'PRIVATE';
  const requesterName = ticket.requestedByName;

  return (
    <div
      ref={setNodeRef}
      style={style}
      onClick={() => {
        if (!isDragging) onEdit(ticket);
      }}
      onContextMenu={(event) => {
        if (draggable) event.preventDefault();
      }}
      className={cn(
        'ticket-card group relative cursor-pointer select-none rounded-xl bg-white p-4 shadow-[0_1px_3px_rgba(15,23,42,0.06)] transition-shadow duration-200 hover:shadow-[0_4px_14px_rgba(15,23,42,0.10)]',
        draggable && 'cursor-grab active:cursor-grabbing',
        isDragging && 'opacity-50 rotate-2 shadow-xl ring-2 ring-primary/20'
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="pr-5 text-sm font-semibold leading-snug text-slate-800">
          <button
            type="button"
            className="text-left rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-600 focus-visible:ring-offset-2"
            aria-label={`Open ticket: ${ticket.title}`}
            disabled={overlay}
          >
            {ticket.title}
          </button>
        </h4>
        {draggable && (
          <button
            type="button"
            ref={setActivatorNodeRef}
            {...attributes}
            {...listeners}
            aria-label={`Move ticket: ${ticket.title}`}
            disabled={overlay}
            onClick={(event) => event.stopPropagation()}
            className="absolute right-1 top-1 grid h-8 w-8 touch-none place-content-center grid-cols-[repeat(2,4px)] gap-0.5 rounded opacity-60 transition-opacity group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-600"
          >
            {Array.from({ length: 6 }).map((_, index) => (
              <span key={index} className="h-1 w-1 rounded-full bg-slate-400" />
            ))}
          </button>
        )}
      </div>

      {ticket.description && (
        <p className="mt-2 line-clamp-2 text-[13px] leading-relaxed text-slate-600">
          {ticket.description}
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <span
          className={cn(
            'inline-flex items-center rounded-md px-2 py-1 text-[11px] font-semibold',
            priority.bg,
            priority.dark
          )}
        >
          {ticket.priority}
        </span>

        <span className="inline-flex items-center gap-1 rounded-md bg-slate-50 px-2 py-1 text-[11px] font-medium text-slate-600">
          <SourceIcon className="h-3 w-3" /> {ticket.source}
        </span>

        {boardName && (
          <span className="inline-flex items-center rounded-md bg-violet-50 px-2 py-1 text-[11px] font-semibold text-violet-700">
            {boardName}
          </span>
        )}
      </div>
      <div className="mt-3 space-y-1.5 border-t border-slate-100 pt-2.5 text-xs text-slate-600">
        <div className="flex items-center gap-1.5">
          <UserRound className="h-3.5 w-3.5 shrink-0" />
          <span className="shrink-0">{isAssignedTicket ? 'Assigned to' : 'Assignee'}</span>
          <span className="truncate font-medium text-slate-600">{ticket.assignee}</span>
        </div>
        {requesterName && (
          <div className="flex items-center gap-1.5 pl-5">
            <span className="shrink-0">{isAssignedTicket ? 'Assigned by' : 'Requested by'}</span>
            <span className="truncate font-medium text-slate-600">{requesterName}</span>
          </div>
        )}
      </div>
    </div>
  );
}
