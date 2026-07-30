begin;

create or replace function public.create_organization_ticket(
    p_organization_id uuid,
    p_assignee_user_id uuid,
    p_title text,
    p_description text,
    p_priority text,
    p_status text
)
returns setof public.tickets
language plpgsql
security definer
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_caller_role text;
    v_assignee_name text;
    v_assigner_name text;
    v_title text := btrim(p_title);
    v_description text := btrim(p_description);
begin
    if v_user_id is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;

    v_caller_role := public.current_organization_role(p_organization_id);
    if coalesce(v_caller_role, '') not in ('OWNER', 'TEAM_LEAD') then
        raise exception 'Only an organization owner or team lead can assign formal tickets'
            using errcode = '42501';
    end if;

    select profile.display_name into v_assignee_name
    from public.organization_members member
    join public.user_profiles profile on profile.user_id = member.user_id
    where member.organization_id = p_organization_id
      and member.user_id = p_assignee_user_id;

    if not found then
        raise exception 'The assignee is not an organization member' using errcode = '22023';
    end if;

    select profile.display_name into v_assigner_name
    from public.user_profiles profile
    where profile.user_id = v_user_id;

    if char_length(v_title) not between 1 and 200
       or char_length(v_description) not between 1 and 5000
       or p_priority not in ('HIGH', 'MEDIUM', 'LOW')
       or p_status not in ('PENDING', 'IN_PROGRESS', 'COMPLETED') then
        raise exception 'Invalid organization ticket data' using errcode = '22023';
    end if;

    return query
    insert into public.tickets(
        owner_id,
        scope,
        organization_id,
        created_by,
        assigned_by_user_id,
        assignee_user_id,
        title,
        description,
        priority,
        status,
        assignee,
        source,
        requested_by_name
    ) values (
        p_assignee_user_id,
        'ORGANIZATION',
        p_organization_id,
        v_user_id,
        v_user_id,
        p_assignee_user_id,
        v_title,
        v_description,
        p_priority,
        p_status,
        v_assignee_name,
        'MANUAL',
        coalesce(v_assigner_name, 'Organization lead')
    )
    returning *;
end;
$$;

revoke all on function public.create_organization_ticket(
    uuid, uuid, text, text, text, text
) from public, anon;
grant execute on function public.create_organization_ticket(
    uuid, uuid, text, text, text, text
) to authenticated;

commit;
