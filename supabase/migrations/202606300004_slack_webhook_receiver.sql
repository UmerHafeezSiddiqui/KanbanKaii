alter table public.webhook_deliveries
add column if not exists payload jsonb;

create or replace function public.claim_slack_webhook_delivery(
    p_event_id text,
    p_payload jsonb
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
    inserted_id uuid;
begin
    insert into public.webhook_deliveries(
        provider,
        external_event_id,
        status,
        payload
    ) values (
        'SLACK',
        p_event_id,
        'RECEIVED',
        p_payload
    )
    on conflict (provider, external_event_id) do nothing
    returning id into inserted_id;

    return inserted_id is not null;
end;
$$;

revoke all on function public.claim_slack_webhook_delivery(text, jsonb)
from public, anon, authenticated;
grant execute on function public.claim_slack_webhook_delivery(text, jsonb)
to service_role;
