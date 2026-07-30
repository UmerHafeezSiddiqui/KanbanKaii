create or replace function public.upsert_slack_integration(
    p_owner_id uuid,
    p_team_id text,
    p_team_name text,
    p_bot_user_id text,
    p_token_ciphertext text,
    p_scopes text[]
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    existing_integration public.integrations%rowtype;
    v_integration_id uuid;
begin
    select * into existing_integration
    from public.integrations
    where provider = 'SLACK'
      and external_account_id = p_team_id;

    if found and existing_integration.owner_id <> p_owner_id then
        raise exception 'Slack workspace is already connected to another account';
    end if;

    if found then
        update public.integrations
        set display_name = p_team_name,
            metadata = jsonb_build_object('bot_user_id', p_bot_user_id)
        where id = existing_integration.id
        returning id into v_integration_id;
    else
        insert into public.integrations(
            owner_id,
            provider,
            external_account_id,
            display_name,
            metadata
        ) values (
            p_owner_id,
            'SLACK',
            p_team_id,
            p_team_name,
            jsonb_build_object('bot_user_id', p_bot_user_id)
        ) returning id into v_integration_id;
    end if;

    insert into public.integration_credentials(
        integration_id,
        access_token_ciphertext,
        scopes,
        updated_at
    ) values (
        v_integration_id,
        p_token_ciphertext,
        p_scopes,
        now()
    )
    on conflict on constraint integration_credentials_pkey do update
    set access_token_ciphertext = excluded.access_token_ciphertext,
        scopes = excluded.scopes,
        updated_at = now();

    return v_integration_id;
end;
$$;

revoke all on function public.upsert_slack_integration(uuid, text, text, text, text, text[])
from public, anon, authenticated;
grant execute on function public.upsert_slack_integration(uuid, text, text, text, text, text[])
to service_role;
