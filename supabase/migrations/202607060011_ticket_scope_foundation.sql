begin;

alter table public.tickets
add column scope text not null default 'PRIVATE'
    check (scope in ('PRIVATE', 'PERSONAL_ASSIGNMENT', 'ORGANIZATION')),
add column organization_id uuid
    references public.organizations(id) on delete restrict,
add column created_by uuid references auth.users(id) on delete set null,
add column assigned_by_user_id uuid references auth.users(id) on delete set null,
add column assignee_user_id uuid references auth.users(id) on delete set null,
add column requested_by_name text
    check (
        requested_by_name is null
        or char_length(btrim(requested_by_name)) between 1 and 100
    ),
add column source_team_id text
    check (
        source_team_id is null
        or char_length(source_team_id) between 1 and 255
    ),
add column source_channel_id text
    check (
        source_channel_id is null
        or char_length(source_channel_id) between 1 and 255
    ),
add column source_message_ts text
    check (
        source_message_ts is null
        or char_length(source_message_ts) between 1 and 255
    ),
add column source_message_state text not null default 'ACTIVE'
    check (source_message_state in ('ACTIVE', 'DELETED')),
add column source_message_deleted_at timestamptz,
add column updated_at timestamptz not null default now();

-- Every existing ticket remains private and belongs to its current owner.
update public.tickets
set created_by = owner_id,
    assignee_user_id = owner_id,
    scope = 'PRIVATE',
    updated_at = created_at;

alter table public.tickets
add constraint tickets_scope_organization_check
check (
    (scope = 'PRIVATE' and organization_id is null)
    or
    (scope in ('PERSONAL_ASSIGNMENT', 'ORGANIZATION') and organization_id is not null)
),
add constraint tickets_source_deletion_check
check (
    (source_message_state = 'ACTIVE' and source_message_deleted_at is null)
    or
    (source_message_state = 'DELETED' and source_message_deleted_at is not null)
);

create index tickets_scope_idx
on public.tickets(scope);

create index tickets_assignee_scope_idx
on public.tickets(assignee_user_id, scope, status);

create index tickets_organization_scope_status_idx
on public.tickets(organization_id, scope, status)
where organization_id is not null;

create index tickets_assigned_by_idx
on public.tickets(assigned_by_user_id)
where assigned_by_user_id is not null;

create index tickets_slack_source_message_idx
on public.tickets(source_team_id, source_channel_id, source_message_ts)
where source_message_ts is not null;

create trigger tickets_set_updated_at
before update on public.tickets
for each row execute function public.set_updated_at();

commit;
