begin;

create or replace function public.leave_organization(
    p_organization_id uuid
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_role text;
begin
    if v_user_id is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;

    select member.role into v_role
    from public.organization_members member
    where member.organization_id = p_organization_id
      and member.user_id = v_user_id
    for update;

    if not found then
        raise exception 'Organization membership was not found' using errcode = '22023';
    end if;
    if v_role = 'OWNER' then
        raise exception 'The organization owner cannot leave. Transfer ownership or delete the organization.'
            using errcode = '42501';
    end if;

    delete from public.organization_members member
    where member.organization_id = p_organization_id
      and member.user_id = v_user_id;
end;
$$;

revoke all on function public.leave_organization(uuid) from public, anon;
grant execute on function public.leave_organization(uuid) to authenticated;

commit;
