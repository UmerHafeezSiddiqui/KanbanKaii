-- Run after all migrations: psql <local-database-url> -v ON_ERROR_STOP=1 -f supabase/tests/audit_regressions.sql
begin;

do $$
declare
    signature text := 'public.accept_redis_organization_invitation(uuid,text,uuid,text,uuid)';
begin
    assert to_regprocedure('public.accept_redis_organization_invitation(uuid,text,uuid,text)') is null,
        'The vulnerable four-argument invitation RPC must be removed';
    assert not has_function_privilege('authenticated', signature, 'EXECUTE');
    assert not has_function_privilege('anon', signature, 'EXECUTE');
    assert has_function_privilege('service_role', signature, 'EXECUTE');
    assert not has_function_privilege('authenticated', 'public.commit_slack_ticket_batch(text,jsonb,jsonb)', 'EXECUTE');
end $$;

do $$
declare
    recipient uuid := gen_random_uuid();
    org uuid := gen_random_uuid();
    first_id uuid := gen_random_uuid();
    second_id uuid := gen_random_uuid();
    event_id text := 'audit-' || gen_random_uuid()::text;
    valid_ticket jsonb;
    invalid_ticket jsonb;
begin
    insert into auth.users(id, email) values (recipient, 'audit-recipient@example.invalid');
    insert into public.organizations(id, name, slug, created_by)
    values (org, 'Audit test', 'audit-' || org::text, recipient);
    perform set_config('request.jwt.claims', '{"role":"service_role"}', true);
    begin
        perform public.accept_redis_organization_invitation(org, 'TEAM_LEAD', recipient, 'wrong@example.invalid', recipient);
        raise exception 'Wrong recipient email was accepted';
    exception when insufficient_privilege then null;
    end;
    perform public.accept_redis_organization_invitation(org, 'MEMBER', recipient, 'audit-recipient@example.invalid', recipient);
    assert exists (select 1 from public.organization_members where organization_id = org and user_id = recipient and role = 'MEMBER');

    insert into public.webhook_deliveries(provider, external_event_id) values ('SLACK', event_id);
    valid_ticket := jsonb_build_object(
        'id', first_id, 'owner_id', recipient, 'scope', 'PRIVATE',
        'created_by', recipient, 'assignee_user_id', recipient,
        'title', 'Audit ticket', 'description', 'Valid task', 'priority', 'HIGH',
        'status', 'PENDING', 'source', 'SLACK', 'assignee', 'Recipient',
        'source_message_state', 'ACTIVE', 'created_at', now(), 'updated_at', now()
    );
    invalid_ticket := valid_ticket || jsonb_build_object('id', second_id, 'title', '');
    begin
        perform public.commit_slack_ticket_batch(event_id, jsonb_build_array(valid_ticket, invalid_ticket), '[]');
        raise exception 'Invalid second ticket was accepted';
    exception when check_violation then null;
    end;
    assert not exists (select 1 from public.tickets where id = first_id), 'Partial insert survived rollback';
    assert (select tickets_committed_at is null from public.webhook_deliveries where external_event_id = event_id);
    assert public.commit_slack_ticket_batch(event_id, jsonb_build_array(valid_ticket), '[]');
    -- Simulate a stale failure update and a replay with a different model result.
    update public.webhook_deliveries set status = 'FAILED' where external_event_id = event_id;
    assert not public.commit_slack_ticket_batch(event_id, jsonb_build_array(valid_ticket || jsonb_build_object('id', second_id)), '[]');
    assert (select count(*) = 1 from public.tickets where id in (first_id, second_id)), 'Replay duplicated tickets';
end $$;

-- Pending events remain recoverable after an outage longer than one day.
do $$
declare
    pending text := 'pending-' || gen_random_uuid()::text;
    terminal text := 'failed-' || gen_random_uuid()::text;
begin
    insert into public.webhook_deliveries(provider, external_event_id, received_at)
    values ('SLACK', pending, now() - interval '2 days');
    insert into public.webhook_deliveries(provider, external_event_id, status, processed_at)
    values ('SLACK', terminal, 'FAILED', now() - interval '91 days');
    perform public.cleanup_integration_transient_data();
    assert exists(select 1 from public.webhook_deliveries where external_event_id = pending and status = 'RECEIVED'),
        'Cleanup made a pending event unrecoverable';
    assert not exists(select 1 from public.webhook_deliveries where external_event_id = terminal),
        'Terminal failure retention stopped working';
end $$;

rollback;
