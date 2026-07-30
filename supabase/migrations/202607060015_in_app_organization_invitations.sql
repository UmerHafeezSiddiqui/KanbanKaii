begin;

alter table public.organization_invites
add column declined_at timestamptz,
add column declined_by uuid references auth.users(id) on delete set null;

alter table public.organization_invites
add constraint organization_invites_declined_pair_check check (
    (declined_at is null and declined_by is null)
    or (declined_at is not null and declined_by is not null)
),
add constraint organization_invites_single_outcome_check check (
    not (accepted_at is not null and declined_at is not null)
    and not (revoked_at is not null and declined_at is not null)
);

create index organization_invites_intended_email_idx
on public.organization_invites(intended_email, created_at desc)
where intended_email is not null;

create or replace function public.create_organization_invite(
    p_organization_id uuid,
    p_token_hash text,
    p_intended_email text,
    p_default_role text,
    p_expires_at timestamptz
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_caller_role text;
    v_email text := lower(btrim(p_intended_email));
    v_invite_id uuid;
begin
    if v_user_id is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;
    v_caller_role := public.current_organization_role(p_organization_id);
    if coalesce(v_caller_role, '') not in ('OWNER', 'TEAM_LEAD') then
        raise exception 'Organization invitation is not permitted' using errcode = '42501';
    end if;
    if p_default_role not in ('TEAM_LEAD', 'MEMBER', 'VIEWER')
       or (v_caller_role = 'TEAM_LEAD' and p_default_role = 'TEAM_LEAD') then
        raise exception 'This role cannot be assigned by the current user' using errcode = '42501';
    end if;
    if char_length(v_email) not between 3 and 320 or position('@' in v_email) < 2
       or p_token_hash !~ '^[a-f0-9]{64}$' or p_expires_at <= now() then
        raise exception 'Invalid invitation data' using errcode = '22023';
    end if;

    perform pg_advisory_xact_lock(hashtextextended(p_organization_id::text || ':' || v_email, 0));

    if exists (
        select 1
        from public.organization_members member
        join auth.users account on account.id = member.user_id
        where member.organization_id = p_organization_id
          and lower(account.email) = v_email
    ) then
        raise exception 'This user is already an organization member' using errcode = '23505';
    end if;
    if exists (
        select 1 from public.organization_invites
        where organization_id = p_organization_id
          and intended_email = v_email
          and accepted_at is null and declined_at is null and revoked_at is null
          and expires_at > now()
    ) then
        raise exception 'A pending invitation already exists for this email' using errcode = '23505';
    end if;

    insert into public.organization_invites(
        organization_id, token_hash, intended_email, default_role, created_by, expires_at
    ) values (
        p_organization_id, p_token_hash, v_email, p_default_role, v_user_id, p_expires_at
    ) returning id into v_invite_id;

    return v_invite_id;
end;
$$;

create or replace function public.list_my_organization_invitations()
returns table (
    id uuid,
    organization_id uuid,
    organization_name text,
    organization_slug text,
    default_role text,
    created_by uuid,
    created_at timestamptz,
    expires_at timestamptz
)
language plpgsql
stable
security definer
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_email text;
begin
    if v_user_id is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;

    select lower(account.email) into v_email
    from auth.users account
    where account.id = v_user_id and account.email_confirmed_at is not null;

    if v_email is null then
        raise exception 'A verified email address is required' using errcode = '42501';
    end if;

    return query
    select
        invite.id,
        invite.organization_id,
        organization.name,
        organization.slug,
        invite.default_role,
        invite.created_by,
        invite.created_at,
        invite.expires_at
    from public.organization_invites invite
    join public.organizations organization on organization.id = invite.organization_id
    where invite.intended_email = v_email
      and invite.accepted_at is null
      and invite.declined_at is null
      and invite.revoked_at is null
      and invite.expires_at > now()
      and not exists (
          select 1 from public.organization_members member
          where member.organization_id = invite.organization_id
            and member.user_id = v_user_id
      )
    order by invite.created_at desc;
end;
$$;

create or replace function public.accept_organization_invitation_by_id(
    p_invite_id uuid
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_email text;
    v_invite public.organization_invites%rowtype;
begin
    if v_user_id is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;

    select lower(email) into v_email
    from auth.users
    where id = v_user_id and email_confirmed_at is not null;

    if v_email is null then
        raise exception 'A verified email address is required' using errcode = '42501';
    end if;

    select * into v_invite
    from public.organization_invites
    where id = p_invite_id
    for update;

    if not found or v_invite.accepted_at is not null
       or v_invite.declined_at is not null or v_invite.revoked_at is not null
       or v_invite.expires_at <= now() then
        raise exception 'Invitation is invalid or expired' using errcode = '22023';
    end if;
    if v_invite.intended_email is null or v_invite.intended_email is distinct from v_email then
        raise exception 'Invitation belongs to another email address' using errcode = '42501';
    end if;
    if exists (
        select 1 from public.organization_members
        where organization_id = v_invite.organization_id and user_id = v_user_id
    ) then
        raise exception 'You are already an organization member' using errcode = '23505';
    end if;

    insert into public.organization_members(organization_id, user_id, role, invited_by)
    values (v_invite.organization_id, v_user_id, v_invite.default_role, v_invite.created_by);

    update public.organization_invites
    set accepted_at = now(), accepted_by = v_user_id
    where id = v_invite.id;

    return v_invite.organization_id;
end;
$$;

create or replace function public.decline_organization_invitation(
    p_invite_id uuid
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_email text;
    v_invite public.organization_invites%rowtype;
begin
    if v_user_id is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;

    select lower(email) into v_email
    from auth.users
    where id = v_user_id and email_confirmed_at is not null;

    select * into v_invite
    from public.organization_invites
    where id = p_invite_id
    for update;

    if v_email is null or not found or v_invite.intended_email is distinct from v_email then
        raise exception 'Invitation was not found' using errcode = '42501';
    end if;
    if v_invite.accepted_at is not null or v_invite.declined_at is not null
       or v_invite.revoked_at is not null or v_invite.expires_at <= now() then
        raise exception 'Invitation is invalid or expired' using errcode = '22023';
    end if;

    update public.organization_invites
    set declined_at = now(), declined_by = v_user_id
    where id = v_invite.id;
end;
$$;

revoke all on function public.list_my_organization_invitations() from public, anon;
revoke all on function public.create_organization_invite(uuid, text, text, text, timestamptz) from public, anon;
revoke all on function public.accept_organization_invitation_by_id(uuid) from public, anon;
revoke all on function public.decline_organization_invitation(uuid) from public, anon;

grant execute on function public.list_my_organization_invitations() to authenticated;
grant execute on function public.create_organization_invite(uuid, text, text, text, timestamptz) to authenticated;
grant execute on function public.accept_organization_invitation_by_id(uuid) to authenticated;
grant execute on function public.decline_organization_invitation(uuid) to authenticated;

commit;
