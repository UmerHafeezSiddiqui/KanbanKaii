import { afterEach, test } from 'node:test';
import assert from 'node:assert/strict';
import { act, useState } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { KanbanBoard } from '../src/components/KanbanBoard';
import { TicketCard } from '../src/components/TicketCard';
import { TicketModal } from '../src/components/TicketModal';
import type { Ticket } from '../src/types/ticket';
import { setApiRequestHandler, setAuthState, setTicketLoadError } from './services.mjs';
import { useOrganizationBoards } from '../src/hooks/organization/useOrganizationBoards';
import type { OrganizationBoardMember, OrganizationBoardSlackChannel } from '../src/api/organizations';
import { LandingPage } from '../src/pages/LandingPage';
import { ProtectedRoute } from '../src/auth/RouteGuards';
import colors from 'tailwindcss/colors.js';

let root: Root | undefined;
async function render(element: React.ReactNode) {
  const container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
  await act(async () => { root?.render(element); });
  return container;
}
afterEach(async () => {
  await act(async () => root?.unmount());
  document.body.innerHTML = '';
  root = undefined;
  setAuthState({ user: { id: 'test-user' }, isLoading: false, configurationError: null });
});

test('board selection keeps the newest board details when requests finish out of order', async () => {
  const pending = new Map<string, (data: unknown) => void>();
  setApiRequestHandler((path: string) => new Promise((resolve) => pending.set(path, resolve)));
  let actions: ReturnType<typeof useOrganizationBoards> | undefined;
  const organization = { id: 'org', name: 'Organization', slug: 'org', created_by: 'owner', created_at: '', updated_at: '' };
  function BoardProbe() {
    const [id, setId] = useState<string | null>(null);
    const [members, setMembers] = useState<OrganizationBoardMember[]>([]);
    const [channels, setChannels] = useState<OrganizationBoardSlackChannel[]>([]);
    actions = useOrganizationBoards({
      canCreateBoards: false, organization, selectedBoard: id ? { ...organization, id, organization_id: 'org' } : null,
      setBoardMembers: setMembers, setBoardSlackChannels: setChannels, setSelectedBoardId: setId,
      setBoards: () => undefined, setConfirmBoardDelete: () => undefined,
      setConfirmBoardMemberRemove: () => undefined, setConfirmSlackChannelRemove: () => undefined,
      setIsSaving: () => undefined, setShowSlackChannelForm: () => undefined,
      slackBinding: { connected: false, workspace_name: null, slack_team_id: null, verified_at: null },
    });
    return <p>{JSON.stringify({ id, members: members.map((member) => member.user_id), channels: channels.map((channel) => channel.slack_channel_id) })}</p>;
  }
  const container = await render(<BoardProbe />);
  assert.ok(actions);
  let first: Promise<void> | undefined;
  let second: Promise<void> | undefined;
  await act(async () => { first = actions?.selectBoard('A'); });
  await act(async () => { second = actions?.selectBoard('B'); });
  const finish = (board: string) => {
    pending.get(`/api/organizations/org/boards/${board}/members`)?.([{ user_id: `member-${board}` }]);
    pending.get(`/api/organizations/org/boards/${board}/slack-channels`)?.([{ slack_channel_id: `channel-${board}` }]);
  };
  await act(async () => { finish('B'); await second; });
  assert.match(container.textContent ?? '', /member-B/);
  await act(async () => { finish('A'); await first; });
  assert.match(container.textContent ?? '', /member-B/);
  assert.match(container.textContent ?? '', /channel-B/);
  assert.doesNotMatch(container.textContent ?? '', /member-A|channel-A/);
});

test('ProtectedRoute displays configuration errors without exposing protected content', async () => {
  setAuthState({ user: null, isLoading: false, configurationError: 'Missing Supabase URL' });
  const container = await render(<ProtectedRoute><p>Private workspace</p></ProtectedRoute>);
  assert.match(container.textContent ?? '', /Authentication is not configured/);
  assert.match(container.textContent ?? '', /Missing Supabase URL/);
  assert.doesNotMatch(container.textContent ?? '', /Private workspace|Loading your workspace/);
});

const ticket: Ticket = {
  id: 'ticket-1', title: 'Fix checkout', description: 'Customers cannot pay',
  status: 'Pending', priority: 'High', source: 'Slack', assignee: 'Aisha',
  scope: 'ORGANIZATION', requestedByName: 'Noah',
  ownerId: 'test-user', sourceMessageState: 'ACTIVE',
};

test('AUD-003: a network failure shows Retry, and retry recovers', async () => {
  setTicketLoadError(new TypeError('Failed to fetch'));
  const container = await render(<KanbanBoard />);
  const retry = [...container.querySelectorAll('button')].find((button) => button.textContent === 'Retry');
  assert.ok(retry, 'A failed request must show a Retry action');
  assert.match(container.textContent ?? '', /connect|load|fetch/i);
  setTicketLoadError(null);
  await act(async () => retry.click());
  assert.equal([...container.querySelectorAll('button')].some((button) => button.textContent === 'Retry'), false);
});

test('AUD-004: organization details have a focusable native button', async () => {
  let opened = 0;
  const container = await render(<TicketCard ticket={ticket} draggable={false} onEdit={() => { opened++; }} />);
  const details = [...container.querySelectorAll('button')].find((button) => button.textContent?.includes(ticket.title));
  assert.ok(details, 'Details must use a native keyboard-activatable control');
  details.focus();
  assert.equal(document.activeElement, details);
  await act(async () => details.click());
  assert.equal(opened, 1);
});

test('AUD-004: draggable cards keep details separate from the drag activator', async () => {
  let opened = 0;
  const container = await render(<TicketCard ticket={ticket} onEdit={() => { opened++; }} />);
  const handle = container.querySelector('button[aria-roledescription="sortable"]');
  assert.ok(handle, 'A separate keyboard drag control must exist');
  assert.ok([...container.querySelectorAll('button')].some((button) => button !== handle && button.textContent?.includes(ticket.title)));
  await act(async () => handle.click());
  assert.equal(opened, 0);
});

function luminance(hex: string) {
  return [0.2126, 0.7152, 0.0722].reduce((sum, weight, index) => {
    const value = parseInt(hex.slice(1 + index * 2, 3 + index * 2), 16) / 255;
    return sum + weight * (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  }, 0);
}

test('AUD-005: ticket description and metadata text meet 4.5:1 on white', async () => {
  const container = await render(<TicketCard ticket={ticket} draggable={false} onEdit={() => undefined} />);
  for (const text of [ticket.description, 'Assigned to']) {
    const element = [...container.querySelectorAll('p, span')].find((item) => item.textContent === text);
    assert.ok(element);
    const styled = element.closest('[class*="text-slate-"]');
    assert.ok(styled);
    const shade = styled.className.match(/text-slate-(\d+)/)?.[1];
    assert.ok(shade);
    const color = Object.entries(colors.slate).find(([key]) => key === shade)?.[1];
    assert.ok(color);
    const contrast = 1.05 / (luminance(color) + 0.05);
    assert.ok(contrast >= 4.5, `${text}: ${contrast.toFixed(2)}:1`);
  }
});

test('AUD-007: each ticket select is associated with its visible label', async () => {
  await render(<TicketModal ticket={ticket} isOpen defaultStatus="Pending" onClose={() => undefined} onSave={async () => true} onDelete={async () => true} />);
  for (const name of ['Priority', 'Status', 'Source']) {
    const label = [...document.querySelectorAll('label')].find((item) => item.textContent === name);
    assert.ok(label);
    assert.ok(label.htmlFor, `${name} needs a label association`);
    const control = document.getElementById(label.htmlFor);
    assert.ok(control);
    assert.equal(control.getAttribute('role'), 'combobox');
  }
});

test('landing preserves the original hero, artwork and signup route without sparkle decoration', async () => {
  const container = await render(<LandingPage />);
  assert.ok(container.querySelector('h1')?.textContent?.includes('Your messages already know what needs to be done.'));
  assert.equal(container.querySelector('img')?.getAttribute('src'), '/landing-mobile-showcase.png');
  assert.ok(container.querySelector('a[href="/auth?mode=signup"]'));
  assert.ok(container.querySelector('#features'));
  assert.equal(container.querySelector('.lucide-sparkles'), null);
});
