begin;

drop function public.accept_redis_organization_invitation(uuid, text, uuid, text);

create function public.accept_redis_organization_invitation(
    p_organization_id uuid,
    p_default_role text,
    p_created_by uuid,
    p_intended_email text,
    p_user_id uuid
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
begin
    if auth.role() is distinct from 'service_role' then
        raise exception 'Server credentials required' using errcode = '42501';
    end if;
    if p_default_role is null or p_default_role not in ('TEAM_LEAD', 'MEMBER', 'VIEWER') then
        raise exception 'Invalid invitation role' using errcode = '22023';
    end if;
    if not exists (
        select 1 from auth.users
        where id = p_user_id
          and lower(email) = lower(btrim(p_intended_email))
          and btrim(p_intended_email) <> ''
    ) then
        raise exception 'This invitation is not for your account' using errcode = '42501';
    end if;
    if not exists (select 1 from public.organizations where id = p_organization_id) then
        raise exception 'Organization was not found' using errcode = '22023';
    end if;
    if exists (
        select 1 from public.organization_members
        where organization_id = p_organization_id and user_id = p_user_id
    ) then
        raise exception 'You are already a member of this organization' using errcode = '23505';
    end if;
    insert into public.organization_members(organization_id, user_id, role, invited_by)
    values (p_organization_id, p_user_id, p_default_role, p_created_by);
    return p_organization_id;
end;
$$;

revoke all on function public.accept_redis_organization_invitation(uuid, text, uuid, text, uuid)
from public, anon, authenticated;
grant execute on function public.accept_redis_organization_invitation(uuid, text, uuid, text, uuid)
to service_role;

commit;
