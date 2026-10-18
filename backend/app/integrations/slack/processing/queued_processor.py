from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.integrations.slack.processing.processor import SlackEventProcessor
from app.integrations.slack.data.repository import SlackRepository
from app.integrations.slack.schemas import SlackEventEnvelope
from app.core.logging import get_application_logger


logger = get_application_logger("slack.worker")


class SlackQueuedEventError(RuntimeError):
    """Raised when a queued Slack payload cannot be safely processed."""


class SlackQueuedEventHandler:
    def __init__(
        self,
        repository: SlackRepository,
        processor: SlackEventProcessor,
    ) -> None:
        self.repository = repository
        self.processor = processor

    async def handle(self, event_id: str) -> None:
        logger.info("ARQ loaded Slack job event_id=%s", event_id)
        delivery = await run_in_threadpool(
            self.repository.get_webhook_delivery,
            event_id,
        )
        if delivery.status == "COMPLETED":
            logger.info("ARQ skipped completed Slack job event_id=%s", event_id)
            return

        try:
            envelope = SlackEventEnvelope.model_validate(delivery.payload)
        except ValidationError as error:
            raise SlackQueuedEventError("Queued Slack payload is invalid") from error
        if not envelope.team_id or envelope.event is None or not envelope.event.text:
            raise SlackQueuedEventError("Queued Slack message is incomplete")

        targets = await run_in_threadpool(
            self.repository.find_mentioned_targets,
            envelope.team_id,
            envelope.event.text,
        )
        if not targets:
            await run_in_threadpool(
                self.repository.update_webhook_delivery,
                event_id,
                "COMPLETED",
                None,
                "IGNORED_NON_ACTIONABLE",
                [{"outcome": "CONNECTED_USER_NO_LONGER_AVAILABLE"}],
            )
            return
        await self.processor.process(event_id, envelope.team_id, envelope.event, targets)
