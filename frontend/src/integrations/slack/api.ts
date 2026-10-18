import { apiRequest } from '@/api/client';

interface SlackConnectResponse {
  authorization_url: string;
}

export interface SlackConnectionStatus {
  connected: boolean;
  workspace_name: string | null;
}

export interface OrganizationSlackBindingStatus {
  connected: boolean;
  workspace_name: string | null;
  slack_team_id: string | null;
  verified_at: string | null;
  reconnect_required?: boolean;
  reconnect_reason?: string | null;
}

export interface SlackChannelRefreshResponse {
  channels_checked: number;
  channels_updated: number;
  channels_joined: number;
  manual_invites_required: string[];
  reconnect_required: boolean;
  missing_scopes: string[];
  message: string;
}

export async function startSlackConnection(organizationId?: string): Promise<string> {
  const result = await apiRequest<SlackConnectResponse>(
    '/api/integrations/slack/connect',
    {
      method: 'POST',
      params: { organization_id: organizationId },
    },
  );
  return result.authorization_url;
}

export async function getOrganizationSlackStatus(
  organizationId: string,
): Promise<OrganizationSlackBindingStatus> {
  return apiRequest<OrganizationSlackBindingStatus>(
    `/api/integrations/slack/organizations/${organizationId}/status`,
  );
}

export async function refreshOrganizationSlackChannels(
  organizationId: string,
): Promise<SlackChannelRefreshResponse> {
  return apiRequest<SlackChannelRefreshResponse>(
    `/api/integrations/slack/organizations/${organizationId}/channels/refresh`,
    { method: 'POST' },
  );
}

export async function getSlackConnectionStatus(): Promise<SlackConnectionStatus> {
  return apiRequest<SlackConnectionStatus>('/api/integrations/slack/status');
}

export async function disconnectSlack(): Promise<void> {
  await apiRequest<void>('/api/integrations/slack', { method: 'DELETE' });
}
