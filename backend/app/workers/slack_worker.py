from typing import Any
from datetime import datetime, timedelta, timezone

import httpx
from arq import Retry, cron
from postgrest.exceptions import APIError
from starlette.concurrency import run_in_threadpool

from app.database.supabase_client import get_supabase_admin_client
from app.database.ticket_repository import TicketRepository
from app.integrations.slack.config import get_slack_oauth_settings
from app.integrations.slack.security.encryption import TokenCipher
from app.integrations.slack.processing.processor import SlackEventProcessor
from app.integrations.slack.processing.queued_processor import SlackQueuedEventHandler
from app.integrations.slack.data.repository import SlackRepository
from app.integrations.slack.services.channels import SlackChannelService
from app.integrations.slack.services.users import SlackUserService
from app.redis.client import get_arq_redis_settings, get_redis_client
from app.services.model_service import get_ai_model_service
from app.maintenance.cleanup import IntegrationCleanupService
from app.services.ai_provider import AIModelUnavailableError
from app.integrations.slack.processing.queue import SlackJobQueue
from app.core.logging import get_application_logger


RETRY_DELAYS_SECONDS = (5, 15)
# Longer than three 180-second attempts plus backoff.
STALE_DELIVERY_SECONDS = 900
logger = get_application_logger("slack.worker")


def _is_transient_failure(error: Exception) -> bool:
    cause: BaseException | None = error
    while cause is not None:
        if isinstance(cause, (httpx.NetworkError, httpx.TimeoutException, httpx.RemoteProtocolError, ConnectionError, TimeoutError)):
            return True
        if isinstance(cause, httpx.HTTPStatusError):
            status = cause.response.status_code
            return status in {408, 429} or 500 <= status < 600
        if isinstance(cause, APIError):
            return isinstance(cause.code, str) and (cause.code.startswith(('08', '53')) or cause.code in {
                '40001', '40P01', '57P01', '57P02', '57P03',
                'PGRST000', 'PGRST001', 'PGRST002', 'PGRST003',
            })
        # Gemini exposes an integer code; Ollama exposes status_code.
        status = getattr(cause, 'status_code', None) or getattr(cause, 'code', None)
        if isinstance(status, int):
            return status in {408, 429} or 500 <= status < 600
        cause = cause.__cause__
    return isinstance(error, AIModelUnavailableError) and error.__cause__ is None


async def startup(ctx: dict[str, Any]) -> None:
    """Build long-lived worker services once, not once per job."""
    supabase_client = get_supabase_admin_client()
    repository = SlackRepository(supabase_client)
    settings = get_slack_oauth_settings()
    token_cipher = TokenCipher(settings.encryption_key)
    processor = SlackEventProcessor(
        slack_repository=repository,
        ticket_repository=TicketRepository(repository.client),
        ollama_service=get_ai_model_service(),
        slack_user_service=SlackUserService(
            repository,
            token_cipher,
        ),
        slack_channel_service=SlackChannelService(
            repository,
            token_cipher,
            redis=get_redis_client(),
        ),
    )
    ctx["slack_handler"] = SlackQueuedEventHandler(repository, processor)
    ctx["slack_repository"] = repository
    ctx["integration_cleanup"] = IntegrationCleanupService(supabase_client)


async def process_slack_event(ctx: dict[str, Any], event_id: str) -> None:
    handler: SlackQueuedEventHandler = ctx["slack_handler"]
    try:
        await handler.handle(event_id)
    except Exception as error:
        attempt = ctx.get('job_try', 1)
        retry = attempt <= len(RETRY_DELAYS_SECONDS) and _is_transient_failure(error)
        try:
            await run_in_threadpool(
                handler.repository.update_webhook_delivery, event_id,
                "RECEIVED" if retry else "FAILED", str(error), "PROCESSING_FAILED",
            )
        except Exception:
            logger.exception("Could not record Slack failure event_id=%s", event_id)
        if retry:
            raise Retry(defer=RETRY_DELAYS_SECONDS[attempt - 1]) from error
        raise


async def reconcile_slack_deliveries(ctx: dict[str, Any]) -> None:
    before = (datetime.now(timezone.utc) - timedelta(seconds=STALE_DELIVERY_SECONDS)).isoformat()
    event_ids = await run_in_threadpool(ctx["slack_repository"].list_stale_deliveries, before)
    queue = SlackJobQueue(ctx["redis"])
    for event_id in event_ids:
        await queue.enqueue(event_id)


async def cleanup_integration_data(ctx: dict[str, Any]) -> None:
    service: IntegrationCleanupService = ctx["integration_cleanup"]
    await run_in_threadpool(service.run)


class WorkerSettings:
    functions = [process_slack_event]
    cron_jobs = [
        cron(reconcile_slack_deliveries, minute=set(range(0, 60, 5)), run_at_startup=True, unique=True),
        cron(
            cleanup_integration_data,
            hour=3,
            minute=15,
            run_at_startup=True,
            unique=True,
        ),
    ]
    on_startup = startup
    redis_settings = get_arq_redis_settings()
    max_jobs = 3
    max_tries = len(RETRY_DELAYS_SECONDS) + 1
    job_timeout = 180
    keep_result = 3600
    retry_jobs = True
    health_check_interval = 5
    health_check_key = "kanbankaii:slack-worker:health"
