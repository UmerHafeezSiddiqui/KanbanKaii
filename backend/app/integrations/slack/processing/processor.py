from starlette.concurrency import run_in_threadpool

from app.core.logging import get_application_logger
from app.database.ticket_repository import TicketRepository
from app.integrations.slack.processing.message import prepare_slack_message
from app.integrations.slack.data.repository import (
    SlackConnectedUser,
    SlackMentionTarget,
    SlackRepository,
)
from app.integrations.slack.schemas import SlackEvent
from app.integrations.slack.services.channels import SlackChannelService
from app.integrations.slack.services.users import SlackUserService
from app.schemas.triage import AIAnalysisResult, IncomingMessage
from app.schemas.ticket import TicketResponse
from app.services.ai_provider import AIModelService
from app.services.ticket_factory import create_ticket_from_analysis


logger = get_application_logger("slack.processor")


DIRECT_MESSAGE_CHANNEL_TYPES = {"im", "mpim"}


def is_direct_message_channel(channel_type: str | None) -> bool:
    """Slack DMs should create personal tasks even when a lead sends them."""
    return channel_type in DIRECT_MESSAGE_CHANNEL_TYPES


class SlackEventProcessor:
    """Turn one Slack message into private tickets for its connected recipients."""

    def __init__(
        self,
        slack_repository: SlackRepository,
        ticket_repository: TicketRepository,
        ollama_service: AIModelService,
        slack_user_service: SlackUserService | None = None,
        slack_channel_service: SlackChannelService | None = None,
    ) -> None:
        self.slack_repository = slack_repository
        self.ticket_repository = ticket_repository
        self.ollama_service = ollama_service
        self.slack_user_service = slack_user_service
        self.slack_channel_service = slack_channel_service

    async def process(
        self,
        event_id: str,
        team_id: str,
        event: SlackEvent,
        targets: list[SlackMentionTarget],
    ) -> None:
        try:
            logger.info("Slack triage started event_id=%s", event_id)
            await run_in_threadpool(
                self.slack_repository.update_webhook_delivery,
                event_id,
                "PROCESSING",
            )

            prepared_text = prepare_slack_message(
                event.text or "",
                [target.slack_user_id for target in targets],
            )
            if not prepared_text:
                await run_in_threadpool(
                    self.slack_repository.update_webhook_delivery,
                    event_id,
                    "COMPLETED",
                    None,
                    "IGNORED_NON_ACTIONABLE",
                    [{"outcome": "IGNORED_EMPTY_MESSAGE"}],
                )
                logger.info("Slack mention-only message ignored event_id=%s", event_id)
                return

            sender_name = event.user or "Slack user"
            sender: SlackConnectedUser | None = None
            if event.user:
                sender = await run_in_threadpool(
                    self.slack_repository.find_connected_user,
                    team_id,
                    event.user,
                )
            if event.user and self.slack_user_service is not None:
                sender_name = await self.slack_user_service.display_name(
                    targets[0].owner_id,
                    event.user,
                )
            source_channel_name = None
            if self.slack_channel_service is not None:
                source_channel_name = await self.slack_channel_service.display_name(
                    targets[0].owner_id,
                    team_id,
                    event.channel,
                    event.channel_type,
                )

            message = IncomingMessage(text=prepared_text, user_name=sender_name)
            batch = await self.ollama_service.analyze_tasks(message)
            logger.info(
                "Slack triage analyzed event_id=%s actionable=%s tasks=%s",
                event_id,
                batch.isActionableTask,
                len(batch.tasks),
            )

            results: list[dict[str, object]] = []
            pending_tickets: list[TicketResponse] = []
            created_count = 0
            if not batch.isActionableTask:
                results = [
                    {
                        "slack_user_id": target.slack_user_id,
                        "outcome": "IGNORED_NON_ACTIONABLE",
                        "analysis": batch.model_dump(mode="json"),
                    }
                    for target in targets
                ]
                logger.info(
                    "Slack message ignored as non-actionable event_id=%s",
                    event_id,
                )
            else:
                for target in targets:
                    ticket_ids: list[str] = []
                    assignee_name = target.slack_user_id
                    if self.slack_user_service is not None:
                        assignee_name = await self.slack_user_service.display_name(
                            target.owner_id,
                            target.slack_user_id,
                        )

                    organization_context = None
                    if sender is not None and sender.owner_id != target.owner_id:
                        organization_context = await run_in_threadpool(
                            self.slack_repository.find_organization_assignment_context,
                            team_id,
                            sender.owner_id,
                            target.owner_id,
                        )

                    force_private_scope = is_direct_message_channel(event.channel_type)
                    is_formal_organization_assignment = (
                        not force_private_scope
                        and
                        organization_context is not None
                        and organization_context.assigner_role in {"OWNER", "TEAM_LEAD"}
                    )
                    board_binding = None
                    if is_formal_organization_assignment and organization_context is not None:
                        board_binding = await run_in_threadpool(
                            self.slack_repository.find_board_channel_binding,
                            organization_context.organization_id,
                            team_id,
                            event.channel,
                        )
                        if board_binding is None and event.channel:
                            logger.warning(
                                "Slack organization ticket has no project board channel mapping event_id=%s organization_id=%s team_id=%s channel_id=%s; ticket will stay organization-wide",
                                event_id,
                                organization_context.organization_id,
                                team_id,
                                event.channel,
                            )

                    for extracted in batch.tasks:
                        analysis = AIAnalysisResult(
                            isActionableTask=True,
                            extractedTitle=extracted.title,
                            cleanDescription=extracted.description,
                            estimatedPriority=extracted.priority,
                        )
                        ticket_data = create_ticket_from_analysis(
                            owner_id=target.owner_id,
                            message=message,
                            analysis=analysis,
                            source="SLACK",
                            assignee=assignee_name,
                            scope="ORGANIZATION"
                            if is_formal_organization_assignment
                            else "PRIVATE",
                            organization_id=organization_context.organization_id
                            if is_formal_organization_assignment
                            else None,
                            board_id=board_binding.board_id
                            if board_binding is not None
                            else None,
                            created_by=sender.owner_id if sender else target.owner_id,
                            assigned_by_user_id=sender.owner_id
                            if is_formal_organization_assignment and sender
                            else None,
                            assignee_user_id=target.owner_id,
                            requested_by_name=sender_name,
                            source_team_id=team_id,
                            source_channel_id=event.channel,
                            source_channel_name=source_channel_name,
                            source_message_ts=event.ts,
                        )
                        ticket = TicketResponse(**ticket_data.model_dump())
                        pending_tickets.append(ticket)
                        ticket_ids.append(str(ticket.id))
                        created_count += 1
                    results.append(
                        {
                            "slack_user_id": target.slack_user_id,
                            "outcome": "TICKET_CREATED",
                            "scope": "ORGANIZATION"
                            if is_formal_organization_assignment
                            else "PRIVATE",
                            "organization_id": str(organization_context.organization_id)
                            if is_formal_organization_assignment
                            else None,
                            "board_id": str(board_binding.board_id)
                            if board_binding is not None
                            else None,
                            "assigned_by_user_id": str(sender.owner_id)
                            if is_formal_organization_assignment and sender
                            else None,
                            "ticket_ids": ticket_ids,
                            "analysis": batch.model_dump(mode="json"),
                        }
                    )

            outcome = "TICKET_CREATED" if created_count else "IGNORED_NON_ACTIONABLE"
            await run_in_threadpool(
                self.ticket_repository.commit_slack_delivery,
                event_id,
                pending_tickets,
                results,
            )
            logger.info(
                "Slack triage completed event_id=%s outcome=%s tickets=%s",
                event_id,
                outcome,
                created_count,
            )
        except Exception as error:
            logger.exception("Slack event processing failed", extra={"event_id": event_id})
            try:
                await run_in_threadpool(
                    self.slack_repository.update_webhook_delivery,
                    event_id,
                    "FAILED",
                    str(error)[:1000],
                    "PROCESSING_FAILED",
                )
            except Exception:
                logger.exception(
                    "Could not mark Slack event as failed",
                    extra={"event_id": event_id},
                )
            raise
