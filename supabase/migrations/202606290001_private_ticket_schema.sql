create table public.integrations (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null references auth.users(id) on delete cascade,
    provider text not null check (provider in ('SLACK', 'GITHUB')),
    external_account_id text not null check (char_length(external_account_id) between 1 and 255),
    display_name text not null check (char_length(display_name) between 1 and 200),
    created_at timestamptz not null default now(),
    unique (provider, external_account_id)
);

create table public.tickets (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null references auth.users(id) on delete cascade,
    title text not null check (char_length(title) between 1 and 200),
    description text not null check (char_length(description) between 1 and 5000),
    priority text not null check (priority in ('HIGH', 'MEDIUM', 'LOW')),
    status text not null default 'PENDING'
        check (status in ('PENDING', 'IN_PROGRESS', 'COMPLETED')),
    assignee text not null check (char_length(assignee) between 1 and 100),
    source text not null check (char_length(source) between 1 and 50),
    created_at timestamptz not null default now()
);

create index integrations_owner_id_idx on public.integrations(owner_id);
create index tickets_owner_id_idx on public.tickets(owner_id);
create index tickets_owner_status_idx on public.tickets(owner_id, status);

alter table public.integrations enable row level security;
alter table public.tickets enable row level security;

create policy "Users can view their own integrations"
on public.integrations for select
to authenticated
using ((select auth.uid()) = owner_id);

create policy "Users can create their own integrations"
on public.integrations for insert
to authenticated
with check ((select auth.uid()) = owner_id);

create policy "Users can update their own integrations"
on public.integrations for update
to authenticated
using ((select auth.uid()) = owner_id)
with check ((select auth.uid()) = owner_id);

create policy "Users can delete their own integrations"
on public.integrations for delete
to authenticated
using ((select auth.uid()) = owner_id);

create policy "Users can view their own tickets"
on public.tickets for select
to authenticated
using ((select auth.uid()) = owner_id);

create policy "Users can create their own tickets"
on public.tickets for insert
to authenticated
with check ((select auth.uid()) = owner_id);

create policy "Users can update their own tickets"
on public.tickets for update
to authenticated
using ((select auth.uid()) = owner_id)
with check ((select auth.uid()) = owner_id);

create policy "Users can delete their own tickets"
on public.tickets for delete
to authenticated
using ((select auth.uid()) = owner_id);

revoke all on public.integrations from anon;
revoke all on public.tickets from anon;
grant select, insert, update, delete on public.integrations to authenticated;
grant select, insert, update, delete on public.tickets to authenticated;
