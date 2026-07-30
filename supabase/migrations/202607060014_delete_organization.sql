begin;

create or replace function public.delete_organization(
    p_organization_id uuid,
    p_confirmation_slug text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    v_organization public.organizations%rowtype;
begin
    if auth.uid() is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;

    select * into v_organization
    from public.organizations
    where id = p_organization_id
    for update;

    if not found then
        raise exception 'Organization was not found' using errcode = '22023';
    end if;
    if public.current_organization_role(p_organization_id) is distinct from 'OWNER' then
        raise exception 'Only the organization owner can delete it' using errcode = '42501';
    end if;
    if v_organization.slug is distinct from lower(btrim(p_confirmation_slug)) then
        raise exception 'Organization confirmation did not match' using errcode = '22023';
    end if;

    delete from public.organizations where id = p_organization_id;
end;
$$;

revoke all on function public.delete_organization(uuid, text)
from public, anon;
grant execute on function public.delete_organization(uuid, text)
to authenticated;

commit;
