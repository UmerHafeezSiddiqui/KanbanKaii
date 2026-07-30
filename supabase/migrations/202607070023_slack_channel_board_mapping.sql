begin;

create table if not exists public.organization_board_slack_channels (
    organization_id uuid not null
        references public.organizations(id) on delete cascade,
    board_id uuid not null
        references public.organization_boards(id) on delete cascade,
    slack_team_id text not null check (char_length(btrim(slack_team_id)) between 1 and 255),
    slack_channel_id text not null check (char_length(btrim(slack_channel_id)) between 1 and 255),
    slack_channel_name text check (
        slack_channel_name is null
        or char_length(btrim(slack_channel_name)) between 1 and 255
    ),
    created_by uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default now(),
    primary key (organization_id, slack_team_id, slack_channel_id),
    foreign key (board_id, organization_id)
        references public.organization_boards(id, organization_id)
        on delete cascade
);

create index if not exists organization_board_slack_channels_board_idx
on public.organization_board_slack_channels(board_id);

create index if not exists organization_board_slack_channels_lookup_idx
on public.organization_board_slack_channels(slack_team_id, slack_channel_id);

create or replace function public.upsert_organization_board_slack_channel(
    p_organization_id uuid,
    p_board_id uuid,
    p_slack_team_id text,
    p_slack_channel_id text,
    p_slack_channel_name text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_slack_team_id text := btrim(p_slack_team_id);
    v_slack_channel_id text := btrim(p_slack_channel_id);
    v_slack_channel_name text := nullif(btrim(coalesce(p_slack_channel_name, '')), '');
begin
    if v_user_id is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;

    if not public.can_manage_organization_board(p_organization_id, p_board_id) then
        raise exception 'Only an organization manager or board manager can link Slack channels'
            using errcode = '42501';
    end if;

    if char_length(v_slack_team_id) not between 1 and 255
       or char_length(v_slack_channel_id) not between 1 and 255 then
        raise exception 'Slack channel mapping is invalid' using errcode = '22023';
    end if;

    if not exists (
        select 1
        from public.organization_slack_workspaces workspace
        where workspace.organization_id = p_organization_id
          and workspace.slack_team_id = v_slack_team_id
    ) then
        raise exception 'Slack workspace is not connected to this organization'
            using errcode = '22023';
    end if;

    insert into public.organization_board_slack_channels(
        organization_id,
        board_id,
        slack_team_id,
        slack_channel_id,
        slack_channel_name,
        created_by
    ) values (
        p_organization_id,
        p_board_id,
        v_slack_team_id,
        v_slack_channel_id,
        v_slack_channel_name,
        v_user_id
    )
    on conflict (organization_id, slack_team_id, slack_channel_id) do update set
        board_id = excluded.board_id,
        slack_channel_name = excluded.slack_channel_name,
        created_by = excluded.created_by,
        created_at = now();
end;
$$;

create or replace function public.remove_organization_board_slack_channel(
    p_organization_id uuid,
    p_board_id uuid,
    p_slack_team_id text,
    p_slack_channel_id text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    if auth.uid() is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;

    if not public.can_manage_organization_board(p_organization_id, p_board_id) then
        raise exception 'Only an organization manager or board manager can unlink Slack channels'
            using errcode = '42501';
    end if;

    delete from public.organization_board_slack_channels
    where organization_id = p_organization_id
      and board_id = p_board_id
      and slack_team_id = btrim(p_slack_team_id)
      and slack_channel_id = btrim(p_slack_channel_id);
end;
$$;

alter table public.organization_board_slack_channels enable row level security;

drop policy if exists "Members can view permitted board Slack channels"
on public.organization_board_slack_channels;
create policy "Members can view permitted board Slack channels"
on public.organization_board_slack_channels for select to authenticated
using (
    public.current_organization_role(organization_id) = 'OWNER'
    or public.is_organization_board_member(board_id)
);

revoke all on public.organization_board_slack_channels from anon, authenticated;
grant select on public.organization_board_slack_channels to authenticated;

revoke all on function public.upsert_organization_board_slack_channel(
    uuid, uuid, text, text, text
) from public, anon;
grant execute on function public.upsert_organization_board_slack_channel(
    uuid, uuid, text, text, text
) to authenticated;

revoke all on function public.remove_organization_board_slack_channel(
    uuid, uuid, text, text
) from public, anon;
grant execute on function public.remove_organization_board_slack_channel(
    uuid, uuid, text, text
) to authenticated;

commit;
