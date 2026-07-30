create table public.integration_credentials (
    integration_id uuid primary key
        references public.integrations(id) on delete cascade,
    access_token_ciphertext text not null,
    scopes text[] not null default '{}',
    updated_at timestamptz not null default now()
);

create table public.webhook_deliveries (
    id uuid primary key default gen_random_uuid(),
    provider text not null check (provider in ('SLACK', 'GITHUB')),
    external_event_id text not null,
    status text not null default 'RECEIVED'
        check (status in ('RECEIVED', 'PROCESSING', 'COMPLETED', 'FAILED')),
    error text,
    received_at timestamptz not null default now(),
    processed_at timestamptz,
    unique(provider, external_event_id)
);

alter table public.integration_credentials enable row level security;
alter table public.webhook_deliveries enable row level security;

revoke all on public.integration_credentials from anon, authenticated;
revoke all on public.webhook_deliveries from anon, authenticated;

grant select, insert, update, delete on public.integration_credentials to service_role;
grant select, insert, update, delete on public.webhook_deliveries to service_role;

drop policy if exists "Users can create their own integrations"
on public.integrations;
drop policy if exists "Users can update their own integrations"
on public.integrations;
revoke insert, update on public.integrations from authenticated;
