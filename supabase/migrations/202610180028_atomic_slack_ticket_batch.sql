begin;

alter table public.webhook_deliveries add column tickets_committed_at timestamptz;
update public.webhook_deliveries
set tickets_committed_at = coalesce(processed_at, now())
where provider = 'SLACK' and status = 'COMPLETED';

create function public.commit_slack_ticket_batch(p_event_id text, p_tickets jsonb, p_result jsonb)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
    delivery public.webhook_deliveries;
begin
    if auth.role() is distinct from 'service_role' then
        raise exception 'Server credentials required' using errcode = '42501';
    end if;
    select * into delivery from public.webhook_deliveries
    where provider = 'SLACK' and external_event_id = p_event_id
    for update;
    if not found then
        raise exception 'Slack delivery was not found' using errcode = '22023';
    end if;
    if delivery.tickets_committed_at is not null or delivery.status = 'COMPLETED' then
        return false;
    end if;
    if p_tickets is null or jsonb_typeof(p_tickets) <> 'array' then
        raise exception 'Ticket batch must be an array' using errcode = '22023';
    end if;

    insert into public.tickets (
        id, owner_id, scope, organization_id, board_id, created_by,
        assigned_by_user_id, assignee_user_id, title, description, priority, status,
        assignee, source, requested_by_name, source_team_id, source_channel_id,
        source_channel_name, source_message_ts, source_message_state,
        source_message_deleted_at, created_at, updated_at
    )
    select id, owner_id, scope, organization_id, board_id, created_by,
        assigned_by_user_id, assignee_user_id, title, description, priority, status,
        assignee, source, requested_by_name, source_team_id, source_channel_id,
        source_channel_name, source_message_ts, source_message_state,
        source_message_deleted_at, created_at, updated_at
    from jsonb_populate_recordset(null::public.tickets, p_tickets);

    update public.webhook_deliveries
    set status = 'COMPLETED', error = null, result = p_result,
        outcome = case when jsonb_array_length(p_tickets) > 0
            then 'TICKET_CREATED' else 'IGNORED_NON_ACTIONABLE' end,
        processed_at = now(), tickets_committed_at = now()
    where id = delivery.id;
    return true;
end;
$$;

revoke all on function public.commit_slack_ticket_batch(text, jsonb, jsonb)
from public, anon, authenticated;
grant execute on function public.commit_slack_ticket_batch(text, jsonb, jsonb) to service_role;

commit;
