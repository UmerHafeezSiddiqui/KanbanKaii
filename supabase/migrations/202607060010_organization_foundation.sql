begin;

create table public.organizations (
    id uuid primary key default gen_random_uuid(),
    name text not null check (char_length(btrim(name)) between 2 and 100),
    slug text not null unique
        check (
            char_length(slug) between 2 and 63
            and slug = lower(slug)
            and slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'
        ),
    created_by uuid not null references auth.users(id) on delete restrict,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.organization_members (
    organization_id uuid not null
        references public.organizations(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    role text not null
        check (role in ('OWNER', 'TEAM_LEAD', 'MEMBER', 'VIEWER')),
    invited_by uuid references auth.users(id) on delete set null,
    joined_at timestamptz not null default now(),
    primary key (organization_id, user_id)
);

create table public.organization_invites (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null
        references public.organizations(id) on delete cascade,
    token_hash text not null unique
        check (token_hash ~ '^[a-f0-9]{64}$'),
    intended_email text
        check (
            intended_email is null
            or (
                intended_email = lower(btrim(intended_email))
                and char_length(intended_email) between 3 and 320
            )
        ),
    default_role text not null default 'MEMBER'
        check (default_role in ('TEAM_LEAD', 'MEMBER', 'VIEWER')),
    created_by uuid not null references auth.users(id) on delete cascade,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null,
    accepted_at timestamptz,
    accepted_by uuid references auth.users(id) on delete set null,
    revoked_at timestamptz,
    check (expires_at > created_at),
    check (
        (accepted_at is null and accepted_by is null)
        or (accepted_at is not null and accepted_by is not null)
    ),
    check (accepted_at is null or revoked_at is null)
);

create index organizations_created_by_idx
on public.organizations(created_by);

create index organization_members_user_id_idx
on public.organization_members(user_id);

create index organization_members_organization_role_idx
on public.organization_members(organization_id, role);

create index organization_invites_organization_id_idx
on public.organization_invites(organization_id);

create index organization_invites_active_idx
on public.organization_invites(organization_id, expires_at)
where accepted_at is null and revoked_at is null;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger organizations_set_updated_at
before update on public.organizations
for each row execute function public.set_updated_at();

create or replace function public.is_organization_member(
    p_organization_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1
        from public.organization_members
        where organization_id = p_organization_id
          and user_id = (select auth.uid())
    );
$$;

create or replace function public.current_organization_role(
    p_organization_id uuid
)
returns text
language sql
stable
security definer
set search_path = public
as $$
    select role
    from public.organization_members
    where organization_id = p_organization_id
      and user_id = (select auth.uid());
$$;

create or replace function public.create_organization(
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
    v_organization_id uuid;
    v_name text := btrim(p_name);
    v_slug text := lower(btrim(p_slug));
begin
    if v_user_id is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;

    if char_length(v_name) not between 2 and 100 then
        raise exception 'Organization name must contain 2 to 100 characters'
            using errcode = '22023';
    end if;

    if char_length(v_slug) not between 2 and 63
       or v_slug !~ '^[a-z0-9]+(?:-[a-z0-9]+)*$' then
        raise exception 'Organization slug is invalid' using errcode = '22023';
    end if;

    insert into public.organizations(name, slug, created_by)
    values (v_name, v_slug, v_user_id)
    returning id into v_organization_id;

    insert into public.organization_members(
        organization_id,
        user_id,
        role,
        invited_by
    ) values (
        v_organization_id,
        v_user_id,
        'OWNER',
        v_user_id
    );

    return v_organization_id;
end;
$$;

alter table public.organizations enable row level security;
alter table public.organization_members enable row level security;
alter table public.organization_invites enable row level security;

create policy "Members can view their organizations"
on public.organizations for select
to authenticated
using (public.is_organization_member(id));

create policy "Owners can update their organizations"
on public.organizations for update
to authenticated
using (public.current_organization_role(id) = 'OWNER')
with check (public.current_organization_role(id) = 'OWNER');

create policy "Owners can delete their organizations"
on public.organizations for delete
to authenticated
using (public.current_organization_role(id) = 'OWNER');

create policy "Members can view organization membership"
on public.organization_members for select
to authenticated
using (public.is_organization_member(organization_id));

create policy "Leads can view organization invitations"
on public.organization_invites for select
to authenticated
using (
    public.current_organization_role(organization_id)
    in ('OWNER', 'TEAM_LEAD')
);

revoke all on public.organizations from anon, authenticated;
revoke all on public.organization_members from anon, authenticated;
revoke all on public.organization_invites from anon, authenticated;

grant select, delete on public.organizations to authenticated;
grant update (name, slug) on public.organizations to authenticated;
grant select on public.organization_members to authenticated;
grant select on public.organization_invites to authenticated;

revoke all on function public.is_organization_member(uuid)
from public, anon;
grant execute on function public.is_organization_member(uuid)
to authenticated, service_role;

revoke all on function public.current_organization_role(uuid)
from public, anon;
grant execute on function public.current_organization_role(uuid)
to authenticated, service_role;

revoke all on function public.create_organization(text, text)
from public, anon;
grant execute on function public.create_organization(text, text)
to authenticated;

revoke all on function public.set_updated_at()
from public, anon, authenticated;

commit;
