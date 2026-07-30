begin;

drop policy if exists "Users can view their own tickets" on public.tickets;
drop policy if exists "Users can create their own tickets" on public.tickets;
drop policy if exists "Users can update their own tickets" on public.tickets;
drop policy if exists "Users can delete their own tickets" on public.tickets;

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
        and public.is_organization_member(organization_id)
    )
);

create policy "Users can create permitted tickets"
on public.tickets for insert to authenticated
with check (
    (
        scope = 'PRIVATE'
        and organization_id is null
        and owner_id = (select auth.uid())
        and created_by = (select auth.uid())
        and assignee_user_id = (select auth.uid())
        and assigned_by_user_id is null
    )
    or (
        scope = 'PERSONAL_ASSIGNMENT'
        and organization_id is not null
        and public.is_organization_member(organization_id)
        and owner_id = assignee_user_id
        and created_by = (select auth.uid())
        and assigned_by_user_id = (select auth.uid())
        and assignee_user_id <> (select auth.uid())
        and exists (
            select 1 from public.organization_members member
            where member.organization_id = tickets.organization_id
              and member.user_id = tickets.assignee_user_id
        )
    )
    or (
        scope = 'ORGANIZATION'
        and organization_id is not null
        and public.current_organization_role(organization_id)
            in ('OWNER', 'TEAM_LEAD')
        and owner_id = assignee_user_id
        and created_by = (select auth.uid())
        and assigned_by_user_id = (select auth.uid())
        and exists (
            select 1 from public.organization_members member
            where member.organization_id = tickets.organization_id
              and member.user_id = tickets.assignee_user_id
        )
    )
);

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
        and public.current_organization_role(organization_id)
            in ('OWNER', 'TEAM_LEAD')
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
        and public.current_organization_role(organization_id)
            in ('OWNER', 'TEAM_LEAD')
    )
);

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
        and public.current_organization_role(organization_id)
            in ('OWNER', 'TEAM_LEAD')
    )
);

create or replace function public.update_assigned_ticket_status(
    p_ticket_id uuid,
    p_status text
)
returns setof public.tickets
language plpgsql
security definer
set search_path = public
as $$
declare
    v_user_id uuid := auth.uid();
    v_ticket public.tickets%rowtype;
begin
    if v_user_id is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;

    if p_status not in ('PENDING', 'IN_PROGRESS', 'COMPLETED') then
        raise exception 'Invalid ticket status' using errcode = '22023';
    end if;

    select * into v_ticket
    from public.tickets
    where id = p_ticket_id
    for update;

    if not found then
        return;
    end if;

    if not coalesce((
        (v_ticket.scope = 'PRIVATE' and v_ticket.owner_id = v_user_id)
        or (
            v_ticket.scope = 'PERSONAL_ASSIGNMENT'
            and v_ticket.assignee_user_id = v_user_id
        )
        or (
            v_ticket.scope = 'ORGANIZATION'
            and (
                v_ticket.assignee_user_id = v_user_id
                or public.current_organization_role(v_ticket.organization_id)
                    in ('OWNER', 'TEAM_LEAD')
            )
        )
    ), false) then
        raise exception 'Ticket status update is not permitted'
            using errcode = '42501';
    end if;

    return query
    update public.tickets
    set status = p_status
    where id = p_ticket_id
    returning *;
end;
$$;

revoke update on public.tickets from authenticated;
grant update (title, description, priority, status, assignee)
on public.tickets to authenticated;

revoke all on function public.update_assigned_ticket_status(uuid, text)
from public, anon;
grant execute on function public.update_assigned_ticket_status(uuid, text)
to authenticated;

commit;
