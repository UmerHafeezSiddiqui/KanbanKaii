begin;

create table public.organization_boards (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null
        references public.organizations(id) on delete cascade,
    name text not null check (char_length(btrim(name)) between 2 and 100),
    slug text not null
        check (
            char_length(slug) between 2 and 63
            and slug = lower(slug)
            and slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'
        ),
    created_by uuid not null references auth.users(id) on delete restrict,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (organization_id, slug),
    unique (id, organization_id)
);

create table public.organization_board_members (
    board_id uuid not null
        references public.organization_boards(id) on delete cascade,
    organization_id uuid not null
        references public.organizations(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    role text not null
        check (role in ('MANAGER', 'MEMBER', 'VIEWER')),
    added_by uuid references auth.users(id) on delete set null,
    joined_at timestamptz not null default now(),
    primary key (board_id, user_id),
    foreign key (board_id, organization_id)
        references public.organization_boards(id, organization_id)
        on delete cascade
);

alter table public.tickets
add column board_id uuid,
add constraint tickets_board_organization_fk
    foreign key (board_id, organization_id)
    references public.organization_boards(id, organization_id)
    on delete restrict,
add constraint tickets_board_scope_check
    check (
        board_id is null
        or (scope = 'ORGANIZATION' and organization_id is not null)
    );

create index organization_boards_organization_idx
on public.organization_boards(organization_id);

create index organization_board_members_user_idx
on public.organization_board_members(user_id);

create index organization_board_members_org_user_idx
on public.organization_board_members(organization_id, user_id);

create index tickets_board_scope_status_idx
on public.tickets(board_id, scope, status)
where board_id is not null;

create trigger organization_boards_set_updated_at
before update on public.organization_boards
for each row execute function public.set_updated_at();

create or replace function public.is_organization_board_member(
    p_board_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1
        from public.organization_board_members
        where board_id = p_board_id
          and user_id = (select auth.uid())
    );
$$;

create or replace function public.current_organization_board_role(
    p_board_id uuid
)
returns text
language sql
stable
security definer
set search_path = public
as $$
    select role
    from public.organization_board_members
    where board_id = p_board_id
      and user_id = (select auth.uid());
$$;

create or replace function public.can_manage_organization_board(
    p_organization_id uuid,
    p_board_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select coalesce(public.current_organization_role(p_organization_id), '') = 'OWNER'
        or coalesce(public.current_organization_board_role(p_board_id), '') = 'MANAGER';
$$;

create or replace function public.create_organization_board(
    p_organization_id uuid,
    p_name text,
    p_slug text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_role text;
    v_board_id uuid;
    v_name text := btrim(p_name);
    v_slug text := lower(btrim(p_slug));
begin
    if v_user_id is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;

    v_role := public.current_organization_role(p_organization_id);
    if coalesce(v_role, '') <> 'OWNER' then
        raise exception 'Only an organization manager can create boards'
            using errcode = '42501';
    end if;

    if char_length(v_name) not between 2 and 100
       or char_length(v_slug) not between 2 and 63
       or v_slug !~ '^[a-z0-9]+(?:-[a-z0-9]+)*$' then
        raise exception 'Board name or slug is invalid' using errcode = '22023';
    end if;

    insert into public.organization_boards(
        organization_id,
        name,
        slug,
        created_by
    ) values (
        p_organization_id,
        v_name,
        v_slug,
        v_user_id
    )
    returning id into v_board_id;

    insert into public.organization_board_members(
        board_id,
        organization_id,
        user_id,
        role,
        added_by
    ) values (
        v_board_id,
        p_organization_id,
        v_user_id,
        'MANAGER',
        v_user_id
    );

    return v_board_id;
end;
$$;

create or replace function public.upsert_organization_board_member(
    p_organization_id uuid,
    p_board_id uuid,
    p_user_id uuid,
    p_role text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
begin
    if v_user_id is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;

    if not public.can_manage_organization_board(p_organization_id, p_board_id) then
        raise exception 'Only an organization owner or board manager can manage board members'
            using errcode = '42501';
    end if;

    if p_role not in ('MANAGER', 'MEMBER', 'VIEWER') then
        raise exception 'Invalid board role' using errcode = '22023';
    end if;

    if not exists (
        select 1 from public.organization_members member
        where member.organization_id = p_organization_id
          and member.user_id = p_user_id
    ) then
        raise exception 'Board members must belong to the organization'
            using errcode = '22023';
    end if;

    insert into public.organization_board_members(
        board_id,
        organization_id,
        user_id,
        role,
        added_by
    ) values (
        p_board_id,
        p_organization_id,
        p_user_id,
        p_role,
        v_user_id
    )
    on conflict (board_id, user_id) do update set
        role = excluded.role;
end;
$$;

create or replace function public.remove_organization_board_member(
    p_organization_id uuid,
    p_board_id uuid,
    p_user_id uuid
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
        raise exception 'Only an organization owner or board manager can manage board members'
            using errcode = '42501';
    end if;

    delete from public.organization_board_members
    where organization_id = p_organization_id
      and board_id = p_board_id
      and user_id = p_user_id;
end;
$$;

create or replace function public.delete_organization_board(
    p_organization_id uuid,
    p_board_id uuid
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
        raise exception 'Only an organization owner or board manager can delete boards'
            using errcode = '42501';
    end if;

    if exists (
        select 1 from public.tickets
        where organization_id = p_organization_id
          and board_id = p_board_id
    ) then
        raise exception 'Board tickets must be resolved before deletion'
            using errcode = '23503';
    end if;

    delete from public.organization_boards
    where organization_id = p_organization_id
      and id = p_board_id;
end;
$$;

create or replace function public.list_organization_board_members_with_profiles(
    p_organization_id uuid,
    p_board_id uuid
)
returns table (
    board_id uuid,
    organization_id uuid,
    user_id uuid,
    role text,
    added_by uuid,
    joined_at timestamptz,
    display_name text,
    job_title text,
    avatar_url text
)
language sql
stable
security definer
set search_path = public
as $$
    select
        member.board_id,
        member.organization_id,
        member.user_id,
        member.role,
        member.added_by,
        member.joined_at,
        profile.display_name,
        profile.job_title,
        profile.avatar_url
    from public.organization_board_members member
    join public.user_profiles profile on profile.user_id = member.user_id
    where member.organization_id = p_organization_id
      and member.board_id = p_board_id
      and (
        public.current_organization_role(p_organization_id) = 'OWNER'
        or public.is_organization_board_member(p_board_id)
      )
    order by member.joined_at;
$$;

alter table public.organization_boards enable row level security;
alter table public.organization_board_members enable row level security;

create policy "Members can view permitted organization boards"
on public.organization_boards for select to authenticated
using (
    public.current_organization_role(organization_id) = 'OWNER'
    or public.is_organization_board_member(id)
);

create policy "Members can view permitted organization board membership"
on public.organization_board_members for select to authenticated
using (
    public.current_organization_role(organization_id) = 'OWNER'
    or public.is_organization_board_member(board_id)
);

drop policy if exists "Users can view permitted tickets" on public.tickets;
create policy "Users can view permitted tickets"
on public.tickets for select to authenticated
using (
    (scope = 'PRIVATE' and owner_id = (select auth.uid()))
    or (
        scope = 'PERSONAL_ASSIGNMENT'
        and (
            assignee_user_id = (select auth.uid())
            or assigned_by_user_id = (select auth.uid())
        )
    )
    or (
        scope = 'ORGANIZATION'
        and board_id is null
        and public.is_organization_member(organization_id)
    )
    or (
        scope = 'ORGANIZATION'
        and board_id is not null
        and (
            public.current_organization_role(organization_id) = 'OWNER'
            or public.is_organization_board_member(board_id)
        )
    )
);

drop policy if exists "Users can update manageable tickets" on public.tickets;
create policy "Users can update manageable tickets"
on public.tickets for update to authenticated
using (
    (scope = 'PRIVATE' and owner_id = (select auth.uid()))
    or (
        scope = 'PERSONAL_ASSIGNMENT'
        and assignee_user_id = (select auth.uid())
    )
    or (
        scope = 'ORGANIZATION'
        and board_id is null
        and public.current_organization_role(organization_id)
            in ('OWNER', 'TEAM_LEAD')
    )
    or (
        scope = 'ORGANIZATION'
        and board_id is not null
        and public.can_manage_organization_board(organization_id, board_id)
    )
)
with check (
    (scope = 'PRIVATE' and owner_id = (select auth.uid()))
    or (
        scope = 'PERSONAL_ASSIGNMENT'
        and assignee_user_id = (select auth.uid())
    )
    or (
        scope = 'ORGANIZATION'
        and board_id is null
        and public.current_organization_role(organization_id)
            in ('OWNER', 'TEAM_LEAD')
    )
    or (
        scope = 'ORGANIZATION'
        and board_id is not null
        and public.can_manage_organization_board(organization_id, board_id)
    )
);

drop policy if exists "Users can delete manageable tickets" on public.tickets;
create policy "Users can delete manageable tickets"
on public.tickets for delete to authenticated
using (
    (scope = 'PRIVATE' and owner_id = (select auth.uid()))
    or (
        scope = 'PERSONAL_ASSIGNMENT'
        and assignee_user_id = (select auth.uid())
    )
    or (
        scope = 'ORGANIZATION'
        and board_id is null
        and public.current_organization_role(organization_id)
            in ('OWNER', 'TEAM_LEAD')
    )
    or (
        scope = 'ORGANIZATION'
        and board_id is not null
        and public.can_manage_organization_board(organization_id, board_id)
    )
);

revoke all on public.organization_boards from anon, authenticated;
revoke all on public.organization_board_members from anon, authenticated;
grant select on public.organization_boards to authenticated;
grant select on public.organization_board_members to authenticated;

revoke all on function public.is_organization_board_member(uuid) from public, anon;
grant execute on function public.is_organization_board_member(uuid)
to authenticated, service_role;

revoke all on function public.current_organization_board_role(uuid) from public, anon;
grant execute on function public.current_organization_board_role(uuid)
to authenticated, service_role;

revoke all on function public.can_manage_organization_board(uuid, uuid) from public, anon;
grant execute on function public.can_manage_organization_board(uuid, uuid)
to authenticated, service_role;

revoke all on function public.create_organization_board(uuid, text, text)
from public, anon;
grant execute on function public.create_organization_board(uuid, text, text)
to authenticated;

revoke all on function public.upsert_organization_board_member(uuid, uuid, uuid, text)
from public, anon;
grant execute on function public.upsert_organization_board_member(uuid, uuid, uuid, text)
to authenticated;

revoke all on function public.remove_organization_board_member(uuid, uuid, uuid)
from public, anon;
grant execute on function public.remove_organization_board_member(uuid, uuid, uuid)
to authenticated;

revoke all on function public.delete_organization_board(uuid, uuid)
from public, anon;
grant execute on function public.delete_organization_board(uuid, uuid)
to authenticated;

revoke all on function public.list_organization_board_members_with_profiles(uuid, uuid)
from public, anon;
grant execute on function public.list_organization_board_members_with_profiles(uuid, uuid)
to authenticated;

commit;
