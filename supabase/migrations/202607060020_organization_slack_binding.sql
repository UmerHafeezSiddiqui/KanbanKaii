begin;

create table public.organization_slack_workspaces (
    organization_id uuid primary key references public.organizations(id) on delete cascade,
    slack_team_id text not null unique check (char_length(slack_team_id) between 1 and 255),
    workspace_name text not null check (char_length(btrim(workspace_name)) between 1 and 200),
    verified_by_user_id uuid not null references auth.users(id) on delete restrict,
    verified_slack_user_id text not null check (char_length(verified_slack_user_id) between 1 and 255),
    is_primary_owner boolean not null default false,
    verified_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create index organization_slack_workspaces_team_idx
on public.organization_slack_workspaces(slack_team_id);

create or replace function public.bind_organization_slack_workspace(
    p_organization_id uuid,
    p_owner_id uuid,
    p_slack_team_id text,
    p_workspace_name text,
    p_slack_user_id text,
    p_is_primary_owner boolean
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    if not exists (
        select 1 from public.organization_members member
        where member.organization_id = p_organization_id
          and member.user_id = p_owner_id
          and member.role = 'OWNER'
    ) then
        raise exception 'Only the KanbanKaii organization owner can bind Slack'
            using errcode = '42501';
    end if;

    insert into public.organization_slack_workspaces(
        organization_id, slack_team_id, workspace_name,
        verified_by_user_id, verified_slack_user_id, is_primary_owner
    ) values (
        p_organization_id, p_slack_team_id, btrim(p_workspace_name),
        p_owner_id, p_slack_user_id, p_is_primary_owner
    )
    on conflict (organization_id) do update set
        slack_team_id = excluded.slack_team_id,
        workspace_name = excluded.workspace_name,
        verified_by_user_id = excluded.verified_by_user_id,
        verified_slack_user_id = excluded.verified_slack_user_id,
        is_primary_owner = excluded.is_primary_owner,
        verified_at = now();
end;
$$;

alter table public.organization_slack_workspaces enable row level security;
create policy "Members can view organization Slack binding"
on public.organization_slack_workspaces for select to authenticated
using (public.is_organization_member(organization_id));

revoke all on public.organization_slack_workspaces from anon, authenticated;
grant select on public.organization_slack_workspaces to authenticated;
revoke all on function public.bind_organization_slack_workspace(
    uuid, uuid, text, text, text, boolean
) from public, anon, authenticated;
grant execute on function public.bind_organization_slack_workspace(
    uuid, uuid, text, text, text, boolean
) to service_role;

commit;
