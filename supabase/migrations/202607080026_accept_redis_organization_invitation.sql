create or replace function public.accept_redis_organization_invitation(
    p_organization_id uuid,
    p_default_role text,
    p_created_by uuid,
    p_intended_email text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_email text := lower(coalesce(auth.jwt() ->> 'email', ''));
    v_intended_email text := lower(btrim(coalesce(p_intended_email, '')));
begin
    if v_user_id is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;

    if p_default_role not in ('TEAM_LEAD', 'MEMBER', 'VIEWER') then
        raise exception 'Invalid invitation role' using errcode = '22023';
    end if;

    if v_intended_email = '' or v_email is distinct from v_intended_email then
        raise exception 'This invitation is not for your account' using errcode = '42501';
    end if;

    if not exists (
        select 1 from public.organizations
        where id = p_organization_id
    ) then
        raise exception 'Organization was not found' using errcode = '22023';
    end if;

    if exists (
        select 1
        from public.organization_members
        where organization_id = p_organization_id
          and user_id = v_user_id
    ) then
        raise exception 'You are already a member of this organization' using errcode = '23505';
    end if;

    insert into public.organization_members(
        organization_id,
        user_id,
        role,
        invited_by
    ) values (
        p_organization_id,
        v_user_id,
        p_default_role,
        p_created_by
    );

    return p_organization_id;
end;
$$;

revoke all on function public.accept_redis_organization_invitation(uuid, text, uuid, text) from public, anon;
grant execute on function public.accept_redis_organization_invitation(uuid, text, uuid, text) to authenticated;
