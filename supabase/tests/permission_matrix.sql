-- Exercise real RLS as authenticated roles, without changing persistent data.
begin;
do $$
declare
    users uuid[] := array[gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), gen_random_uuid()];
    org uuid := gen_random_uuid();
    board uuid := gen_random_uuid();
    task uuid := gen_random_uuid();
    private_task uuid := gen_random_uuid();
    actor uuid;
    i integer;
    affected integer;
begin
    foreach actor in array users loop
        insert into auth.users(id, email) values (actor, actor::text || '@example.invalid');
    end loop;
    insert into public.organizations(id, name, slug, created_by)
    values (org, 'Permission gate', 'gate-' || org::text, users[1]);
    insert into public.organization_members(organization_id, user_id, role)
    values (org, users[1], 'OWNER'), (org, users[2], 'TEAM_LEAD'), (org, users[3], 'MEMBER');
    insert into public.organization_boards(id, organization_id, name, slug, created_by)
    values (board, org, 'Gate board', 'gate-board', users[1]);
    insert into public.organization_board_members(board_id, organization_id, user_id, role)
    values (board, org, users[2], 'MANAGER'), (board, org, users[3], 'MEMBER');
    insert into public.tickets(id, owner_id, scope, organization_id, board_id, created_by,
                              assignee_user_id, title, description, priority, assignee, source)
    values (task, users[1], 'ORGANIZATION', org, board, users[1], users[1],
            'Gate ticket', 'Permission fixture', 'LOW', 'Owner', 'MANUAL'),
           (private_task, users[4], 'PRIVATE', null, null, users[4], users[4],
            'Private ticket', 'Must stay private', 'LOW', 'Outsider', 'MANUAL');
    for i in 1..4 loop
        perform set_config('request.jwt.claims', jsonb_build_object('sub', users[i], 'role', 'authenticated')::text, true);
        execute 'set local role authenticated';
        assert auth.uid() = users[i], 'Fixture must execute with the selected identity';
        assert (select count(*) from public.tickets where id = task) = case when i = 4 then 0 else 1 end,
            'Board ticket visibility differs from owner/lead/member/outsider matrix';
        assert (select count(*) from public.tickets where id = private_task) = case when i = 4 then 1 else 0 end,
            'Private ticket leaked across users';
        update public.tickets set priority = 'HIGH' where id = task;
        get diagnostics affected = row_count;
        assert affected = case when i in (1, 2) then 1 else 0 end,
            'Only owner or board manager may update this board ticket';
        begin
            perform public.commit_slack_ticket_batch('forbidden', '[]', '[]');
            raise exception 'Authenticated user executed a service-only RPC';
        exception when insufficient_privilege then null;
        end;
        execute 'reset role';
    end loop;
    -- An organization lead without board membership cannot read the board.
    delete from public.organization_board_members where board_id = board and user_id = users[2];
    perform set_config('request.jwt.claims', jsonb_build_object('sub', users[2], 'role', 'authenticated')::text, true);
    execute 'set local role authenticated';
    assert not exists(select 1 from public.tickets where id = task), 'Unmapped lead read a board ticket';
    execute 'reset role';
end $$;
rollback;
