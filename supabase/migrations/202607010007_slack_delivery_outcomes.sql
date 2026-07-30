alter table public.webhook_deliveries
add column if not exists outcome text,
add column if not exists result jsonb;

alter table public.webhook_deliveries
drop constraint if exists webhook_deliveries_outcome_check;

alter table public.webhook_deliveries
add constraint webhook_deliveries_outcome_check check (
    outcome is null or outcome in (
        'TICKET_CREATED',
        'IGNORED_NON_ACTIONABLE',
        'PROCESSING_FAILED'
    )
);
