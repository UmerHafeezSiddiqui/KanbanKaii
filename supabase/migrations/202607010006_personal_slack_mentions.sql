-- Allow several KanbanKaii users to connect independently to the same Slack workspace.
alter table public.integrations
drop constraint if exists integrations_provider_external_account_id_key;

create unique index if not exists integrations_owner_provider_idx
on public.integrations(owner_id, provider);

drop function if exists public.upsert_slack_integration(
    uuid, text, text, text, text, text[]
);

create or replace function public.upsert_slack_integration(
    p_owner_id uuid,
    p_team_id text,
    p_team_name text,
    p_bot_user_id text,
    p_slack_user_id text,
    p_token_ciphertext text,
    p_scopes text[]
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_integration_id uuid;
begin
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
        jsonb_build_object(
            'bot_user_id', p_bot_user_id,
            'slack_user_id', p_slack_user_id
        )
    )
    on conflict (owner_id, provider) do update
    set external_account_id = excluded.external_account_id,
        display_name = excluded.display_name,
        metadata = excluded.metadata
    returning id into v_integration_id;

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

revoke all on function public.upsert_slack_integration(
    uuid, text, text, text, text, text, text[]
) from public, anon, authenticated;
grant execute on function public.upsert_slack_integration(
    uuid, text, text, text, text, text, text[]
) to service_role;
