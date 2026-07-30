create or replace function public.cleanup_integration_transient_data()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    stale_deliveries integer := 0;
    ignored_deliveries integer := 0;
    completed_deliveries integer := 0;
    failed_deliveries integer := 0;
begin
    -- A job still active after 24 hours cannot be a live ARQ/Ollama request.
    -- Mark it failed first so active statuses are never deleted directly.
    update public.webhook_deliveries
    set status = 'FAILED',
        outcome = 'PROCESSING_FAILED',
        error = coalesce(error, 'Delivery exceeded the 24-hour processing window'),
        processed_at = now()
    where status in ('RECEIVED', 'PROCESSING')
      and received_at < now() - interval '24 hours';
    get diagnostics stale_deliveries = row_count;

    delete from public.webhook_deliveries
    where status = 'COMPLETED'
      and outcome = 'IGNORED_NON_ACTIONABLE'
      and processed_at < now() - interval '7 days';
    get diagnostics ignored_deliveries = row_count;

    delete from public.webhook_deliveries
    where status = 'COMPLETED'
      and outcome is distinct from 'IGNORED_NON_ACTIONABLE'
      and processed_at < now() - interval '30 days';
    get diagnostics completed_deliveries = row_count;

    delete from public.webhook_deliveries
    where status = 'FAILED'
      and processed_at < now() - interval '90 days';
    get diagnostics failed_deliveries = row_count;

    return jsonb_build_object(
        'stale_marked_failed', stale_deliveries,
        'ignored_deleted', ignored_deliveries,
        'completed_deleted', completed_deliveries,
        'failed_deleted', failed_deliveries
    );
end;
$$;

revoke all on function public.cleanup_integration_transient_data()
from public, anon, authenticated;
grant execute on function public.cleanup_integration_transient_data()
to service_role;
