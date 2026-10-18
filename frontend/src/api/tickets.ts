import type {
  Ticket,
  TicketPriority,
  TicketSource,
  TicketStatus,
  TicketFormValues,
} from '@/types/ticket';
import { apiRequest } from './client';

type ApiPriority = 'HIGH' | 'MEDIUM' | 'LOW';
type ApiStatus = 'PENDING' | 'IN_PROGRESS' | 'COMPLETED';
export type OrganizationTicketView = 'overview' | 'organization_wide';

export interface ApiTicket {
  id: string;
  owner_id: string;
  scope: 'PRIVATE' | 'PERSONAL_ASSIGNMENT' | 'ORGANIZATION';
  organization_id: string | null;
  board_id: string | null;
  created_by: string | null;
  assigned_by_user_id: string | null;
  assignee_user_id: string | null;
  title: string;
  description: string;
  priority: ApiPriority;
  status: ApiStatus;
  assignee: string;
  source: string;
  requested_by_name: string | null;
  source_team_id: string | null;
  source_channel_id: string | null;
  source_channel_name: string | null;
  source_message_ts: string | null;
  source_message_state: 'ACTIVE' | 'DELETED';
  source_message_deleted_at: string | null;
  created_at: string;
  updated_at: string;
}

const priorityMap: Record<ApiPriority, TicketPriority> = {
  HIGH: 'High',
  MEDIUM: 'Medium',
  LOW: 'Low',
};

const statusMap: Record<ApiStatus, TicketStatus> = {
  PENDING: 'Pending',
  IN_PROGRESS: 'In Progress',
  COMPLETED: 'Completed',
};

const apiStatusMap: Record<TicketStatus, ApiStatus> = {
  Pending: 'PENDING',
  'In Progress': 'IN_PROGRESS',
  Completed: 'COMPLETED',
};

const apiPriorityMap: Record<TicketPriority, ApiPriority> = {
  High: 'HIGH',
  Medium: 'MEDIUM',
  Low: 'LOW',
};

function mapSource(source: string): TicketSource {
  if (source === 'SLACK') return 'Slack';
  if (source === 'GITHUB') return 'GitHub';
  return 'Manual';
}

export function mapApiTicket(ticket: ApiTicket): Ticket {
  return {
    id: ticket.id,
    title: ticket.title,
    description: ticket.description,
    priority: priorityMap[ticket.priority],
    status: statusMap[ticket.status],
    assignee: ticket.assignee,
    source: mapSource(ticket.source),
    ownerId: ticket.owner_id,
    scope: ticket.scope,
    organizationId: ticket.organization_id ?? undefined,
    boardId: ticket.board_id ?? undefined,
    createdBy: ticket.created_by ?? undefined,
    assignedByUserId: ticket.assigned_by_user_id ?? undefined,
    assigneeUserId: ticket.assignee_user_id ?? undefined,
    requestedByName: ticket.requested_by_name ?? undefined,
    sourceTeamId: ticket.source_team_id ?? undefined,
    sourceChannelId: ticket.source_channel_id ?? undefined,
    sourceChannelName: ticket.source_channel_name ?? undefined,
    sourceMessageTs: ticket.source_message_ts ?? undefined,
    sourceMessageState: ticket.source_message_state,
    sourceMessageDeletedAt: ticket.source_message_deleted_at ?? undefined,
    createdAt: ticket.created_at,
    updatedAt: ticket.updated_at,
  };
}

interface FetchTicketsOptions {
  status?: ApiStatus;
  signal?: AbortSignal;
  view?: OrganizationTicketView;
  boardId?: string;
}

export async function fetchTickets(
  options: FetchTicketsOptions = {},
): Promise<Ticket[]> {
  const tickets = await apiRequest<ApiTicket[]>('/api/tickets', {
    signal: options.signal,
    params: { status: options.status },
  });
  return tickets.map(mapApiTicket);
}

export async function fetchOrganizationTickets(
  organizationId: string,
  options: FetchTicketsOptions = {},
): Promise<Ticket[]> {
  const tickets = await apiRequest<ApiTicket[]>(
    `/api/tickets/organizations/${organizationId}`,
    {
      signal: options.signal,
      params: {
        status: options.status,
        view: options.view,
        board_id: options.boardId,
      },
    },
  );
  return tickets.map(mapApiTicket);
}

export async function updateTicketStatus(
  ticketId: string,
  status: TicketStatus,
): Promise<Ticket> {
  const ticket = await apiRequest<ApiTicket>(`/api/tickets/${ticketId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status: apiStatusMap[status] }),
  });
  return mapApiTicket(ticket);
}

export async function updateTicket(
  ticketId: string,
  values: TicketFormValues,
): Promise<Ticket> {
  const ticket = await apiRequest<ApiTicket>(`/api/tickets/${ticketId}`, {
    method: 'PATCH',
    body: JSON.stringify({
      title: values.title,
      description: values.description,
      priority: apiPriorityMap[values.priority],
      status: apiStatusMap[values.status],
      assignee: values.assignee,
    }),
  });
  return mapApiTicket(ticket);
}

export async function updateOrganizationTicket(
  organizationId: string,
  ticketId: string,
  values: TicketFormValues,
): Promise<Ticket> {
  const ticket = await apiRequest<ApiTicket>(
    `/api/tickets/organizations/${organizationId}/${ticketId}`,
    {
      method: 'PATCH',
      body: JSON.stringify({
        title: values.title,
        description: values.description,
        priority: apiPriorityMap[values.priority],
        status: apiStatusMap[values.status],
        assignee: values.assignee,
      }),
    },
  );
  return mapApiTicket(ticket);
}

export async function createTicket(values: TicketFormValues): Promise<Ticket> {
  const ticket = await apiRequest<ApiTicket>('/api/tickets', {
    method: 'POST',
    body: JSON.stringify({
      title: values.title,
      description: values.description,
      priority: apiPriorityMap[values.priority],
      status: apiStatusMap[values.status],
      assignee: values.assignee,
    }),
  });
  return mapApiTicket(ticket);
}

export async function createOrganizationTicket(
  organizationId: string,
  values: TicketFormValues,
  boardId?: string,
): Promise<Ticket> {
  if (!values.assigneeUserId) throw new Error('Select an organization member');
  const ticket = await apiRequest<ApiTicket>(
    `/api/tickets/organizations/${organizationId}`,
    {
      method: 'POST',
      body: JSON.stringify({
        board_id: boardId ?? null,
        title: values.title,
        description: values.description,
        priority: apiPriorityMap[values.priority],
        status: apiStatusMap[values.status],
        assignee_user_id: values.assigneeUserId,
      }),
    },
  );
  return mapApiTicket(ticket);
}

export async function deleteTicket(ticketId: string): Promise<void> {
  await apiRequest<void>(`/api/tickets/${ticketId}`, { method: 'DELETE' });
}

export async function deleteOrganizationTicket(
  organizationId: string,
  ticketId: string,
): Promise<void> {
  await apiRequest<void>(
    `/api/tickets/organizations/${organizationId}/${ticketId}`,
    { method: 'DELETE' },
  );
}
