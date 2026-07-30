begin;

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
    if p_token_hash !~ '^[a-f0-9]{64}$' or p_expires_at <= now() then
        raise exception 'Invalid invitation data' using errcode = '22023';
    end if;

    insert into public.organization_invites(
        organization_id, token_hash, intended_email, default_role,
        created_by, expires_at
    ) values (
        p_organization_id,
        p_token_hash,
        nullif(lower(btrim(p_intended_email)), ''),
        p_default_role,
        v_user_id,
        p_expires_at
    ) returning id into v_invite_id;
    return v_invite_id;
end;
$$;

create or replace function public.accept_organization_invite(
    p_token_hash text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_user_email text := lower(auth.jwt() ->> 'email');
    v_invite public.organization_invites%rowtype;
begin
    if v_user_id is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;

    select * into v_invite
    from public.organization_invites
    where token_hash = p_token_hash
    for update;

    if not found or v_invite.accepted_at is not null
       or v_invite.revoked_at is not null or v_invite.expires_at <= now() then
        raise exception 'Invitation is invalid or expired' using errcode = '22023';
    end if;
    if v_invite.intended_email is not null
       and v_invite.intended_email is distinct from v_user_email then
        raise exception 'Invitation belongs to another email address' using errcode = '42501';
    end if;

    insert into public.organization_members(
        organization_id, user_id, role, invited_by
    ) values (
        v_invite.organization_id,
        v_user_id,
        v_invite.default_role,
        v_invite.created_by
    ) on conflict (organization_id, user_id) do nothing;

    update public.organization_invites
    set accepted_at = now(), accepted_by = v_user_id
    where id = v_invite.id;

    return v_invite.organization_id;
end;
$$;

create or replace function public.revoke_organization_invite(
    p_invite_id uuid
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_invite public.organization_invites%rowtype;
begin
    select * into v_invite from public.organization_invites where id = p_invite_id for update;
    if not found then
        raise exception 'Invitation was not found' using errcode = '22023';
    end if;
    if public.current_organization_role(v_invite.organization_id) is distinct from 'OWNER'
       and v_invite.created_by <> v_user_id then
        raise exception 'Invitation revocation is not permitted' using errcode = '42501';
    end if;
    if v_invite.accepted_at is not null then
        raise exception 'Accepted invitations cannot be revoked' using errcode = '22023';
    end if;
    update public.organization_invites set revoked_at = now() where id = p_invite_id;
end;
$$;

create or replace function public.change_organization_member_role(
    p_organization_id uuid,
    p_user_id uuid,
    p_role text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    v_caller_role text := public.current_organization_role(p_organization_id);
    v_target_role text;
begin
    select role into v_target_role from public.organization_members
    where organization_id = p_organization_id and user_id = p_user_id;
    if not found then
        raise exception 'Organization member was not found' using errcode = '22023';
    end if;
    if v_target_role = 'OWNER' or p_role = 'OWNER' then
        raise exception 'Organization ownership cannot be changed here' using errcode = '42501';
    end if;
    if v_caller_role = 'OWNER' and p_role in ('TEAM_LEAD', 'MEMBER', 'VIEWER') then
        null;
    elsif v_caller_role = 'TEAM_LEAD'
          and v_target_role in ('MEMBER', 'VIEWER')
          and p_role in ('MEMBER', 'VIEWER') then
        null;
    else
        raise exception 'Role change is not permitted' using errcode = '42501';
    end if;
    update public.organization_members set role = p_role
    where organization_id = p_organization_id and user_id = p_user_id;
end;
$$;

create or replace function public.remove_organization_member(
    p_organization_id uuid,
    p_user_id uuid
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    v_caller_role text := public.current_organization_role(p_organization_id);
    v_target_role text;
begin
    select role into v_target_role from public.organization_members
    where organization_id = p_organization_id and user_id = p_user_id;
    if not found then
        raise exception 'Organization member was not found' using errcode = '22023';
    end if;
    if v_target_role = 'OWNER' then
        raise exception 'The organization owner cannot be removed' using errcode = '42501';
    end if;
    if coalesce(v_caller_role, '') <> 'OWNER'
       and not (v_caller_role = 'TEAM_LEAD' and v_target_role in ('MEMBER', 'VIEWER')) then
        raise exception 'Member removal is not permitted' using errcode = '42501';
    end if;
    delete from public.organization_members
    where organization_id = p_organization_id and user_id = p_user_id;
end;
$$;

revoke all on function public.create_organization_invite(uuid, text, text, text, timestamptz) from public, anon;
revoke all on function public.accept_organization_invite(text) from public, anon;
revoke all on function public.revoke_organization_invite(uuid) from public, anon;
revoke all on function public.change_organization_member_role(uuid, uuid, text) from public, anon;
revoke all on function public.remove_organization_member(uuid, uuid) from public, anon;

grant execute on function public.create_organization_invite(uuid, text, text, text, timestamptz) to authenticated;
grant execute on function public.accept_organization_invite(text) to authenticated;
grant execute on function public.revoke_organization_invite(uuid) to authenticated;
grant execute on function public.change_organization_member_role(uuid, uuid, text) to authenticated;
grant execute on function public.remove_organization_member(uuid, uuid) to authenticated;

commit;
