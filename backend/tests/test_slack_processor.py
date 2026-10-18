import asyncio
from unittest import TestCase
from uuid import uuid4
from types import SimpleNamespace

from app.integrations.slack.processing.processor import SlackEventProcessor
from app.integrations.slack.data.repository import (
    SlackConnectedUser,
    SlackMentionTarget,
    SlackOrganizationAssignmentContext,
)
from app.integrations.slack.schemas import SlackEvent
from app.schemas.triage import AITaskBatchResult, ExtractedTask


class FakeSlackRepository:
    def __init__(self) -> None:
        self.states = []
        self.sender_owner_id = None
        self.assignment_context = None
        self.board_binding = None

    def update_webhook_delivery(
        self,
        event_id,
        status,
        error=None,
        outcome=None,
        result=None,
    ) -> None:
        self.states.append((event_id, status, error, outcome, result))

    def find_connected_user(self, team_id, slack_user_id):
        self.sender_lookup = (team_id, slack_user_id)
        if self.sender_owner_id is None:
            return None
        return SlackConnectedUser(self.sender_owner_id, slack_user_id)

    def find_organization_assignment_context(
        self,
        team_id,
        assigner_user_id,
        assignee_user_id,
    ):
        self.assignment_lookup = (team_id, assigner_user_id, assignee_user_id)
        return self.assignment_context

    def find_board_channel_binding(self, organization_id, team_id, channel_id):
        self.board_binding_lookup = (organization_id, team_id, channel_id)
        return self.board_binding


class FakeTicketRepository:
    def __init__(self) -> None:
        self.created = []

    def create(self, ticket):
        self.created.append(ticket)
        return SimpleNamespace(id=uuid4())

    def commit_slack_delivery(self, event_id, tickets, results):
        self.created.extend(tickets)
        self.results = results
        self.outcome = 'TICKET_CREATED' if tickets else 'IGNORED_NON_ACTIONABLE'
        return True


class FakeOllamaService:
    def __init__(self, actionable=True, task_count=1) -> None:
        self.actionable = actionable
        self.task_count = task_count
        self.messages = []

    async def analyze_tasks(self, message):
        self.messages.append(message)
        return AITaskBatchResult(
            isActionableTask=self.actionable,
            tasks=[
                ExtractedTask(
                    title=f"Task {index + 1}",
                    description=f"Complete task {index + 1}.",
                    priority="HIGH",
                )
                for index in range(self.task_count if self.actionable else 0)
            ],
        )


class FakeSlackUserService:
    def __init__(self) -> None:
        self.lookups = []

    async def display_name(self, owner_id, slack_user_id):
        self.lookup = (owner_id, slack_user_id)
        self.lookups.append((owner_id, slack_user_id))
        if slack_user_id == "U-CONNECTED":
            return "Noah"
        return "Aisha"


class FakeSlackChannelService:
    def __init__(self) -> None:
        self.lookups = []

    async def display_name(self, owner_id, team_id, slack_channel_id, channel_type=None):
        self.lookups.append((owner_id, team_id, slack_channel_id, channel_type))
        return "product-team"


class SlackEventProcessorTests(TestCase):
    def test_later_recipient_failure_leaves_no_partial_tickets_before_replay(self):
        first, second = uuid4(), uuid4()
        tickets = FakeTicketRepository()
        users = FakeSlackUserService()
        original = users.display_name

        async def fail_second(owner_id, slack_user_id):
            if slack_user_id == 'U-SECOND':
                raise RuntimeError('Slack temporarily unavailable')
            return await original(owner_id, slack_user_id)

        users.display_name = fail_second
        processor = SlackEventProcessor(FakeSlackRepository(), tickets, FakeOllamaService(), users)
        event = SlackEvent(type='message', user='U-SENDER', text='<@U-FIRST> <@U-SECOND> fix checkout')
        targets = [SlackMentionTarget(first, 'U-FIRST'), SlackMentionTarget(second, 'U-SECOND')]
        with self.assertRaises(RuntimeError):
            asyncio.run(processor.process('Ev-replay', 'T123', event, targets))
        self.assertEqual(tickets.created, [])
        users.display_name = original
        asyncio.run(processor.process('Ev-replay', 'T123', event, targets))
        self.assertEqual(len(tickets.created), 2)

    def test_actionable_mention_creates_private_owner_ticket(self) -> None:
        owner_id = uuid4()
        slack_repository = FakeSlackRepository()
        ticket_repository = FakeTicketRepository()
        ollama = FakeOllamaService()
        slack_users = FakeSlackUserService()
        processor = SlackEventProcessor(
            slack_repository,
            ticket_repository,
            ollama,
            slack_users,
        )

        asyncio.run(
            processor.process(
                "Ev123",
                "T123",
                SlackEvent(
                    type="message",
                    user="U-SENDER",
                    text="<@U-CONNECTED> please fix checkout before tomorrow",
                ),
                [SlackMentionTarget(owner_id, "U-CONNECTED")],
            )
        )

        self.assertEqual(
            ollama.messages[0].text,
            "please fix checkout before tomorrow",
        )
        self.assertEqual(len(ticket_repository.created), 1)
        ticket = ticket_repository.created[0]
        self.assertEqual(ticket.owner_id, owner_id)
        self.assertEqual(ticket.assignee, "Noah")
        self.assertEqual(ticket.requested_by_name, "Aisha")
        self.assertEqual(ollama.messages[0].user_name, "Aisha")
        self.assertIn((owner_id, "U-SENDER"), slack_users.lookups)
        self.assertIn((owner_id, "U-CONNECTED"), slack_users.lookups)
        self.assertEqual(ticket.source, "SLACK")
        self.assertEqual(ticket.scope, "PRIVATE")
        self.assertEqual(
            [state[1] for state in slack_repository.states],
            ["PROCESSING"],
        )
        self.assertEqual(ticket_repository.outcome, "TICKET_CREATED")
        self.assertEqual(
            ticket_repository.results[0]["analysis"]["isActionableTask"],
            True,
        )

    def test_multiple_requested_outcomes_create_multiple_tickets(self) -> None:
        repository = FakeSlackRepository()
        tickets = FakeTicketRepository()
        processor = SlackEventProcessor(
            repository,
            tickets,
            FakeOllamaService(task_count=3),
        )

        asyncio.run(
            processor.process(
                "Ev-multi",
                "T123",
                SlackEvent(
                    type="message",
                    user="U-SENDER",
                    text="<@U-CONNECTED> fix checkout, update SQL, and review tests",
                ),
                [SlackMentionTarget(uuid4(), "U-CONNECTED")],
            )
        )

        self.assertEqual(len(tickets.created), 3)
        self.assertEqual(len(tickets.results[0]["ticket_ids"]), 3)

    def test_non_actionable_mention_completes_without_ticket(self) -> None:
        slack_repository = FakeSlackRepository()
        ticket_repository = FakeTicketRepository()
        processor = SlackEventProcessor(
            slack_repository,
            ticket_repository,
            FakeOllamaService(actionable=False),
        )

        asyncio.run(
            processor.process(
                "Ev124",
                "T123",
                SlackEvent(
                    type="message",
                    user="U-SENDER",
                    text="hello <@U-CONNECTED>",
                ),
                [SlackMentionTarget(uuid4(), "U-CONNECTED")],
            )
        )

        self.assertEqual(ticket_repository.created, [])
        self.assertEqual(ticket_repository.outcome, "IGNORED_NON_ACTIONABLE")
        self.assertEqual(
            ticket_repository.outcome,
            "IGNORED_NON_ACTIONABLE",
        )

    def test_lead_assignment_creates_organization_ticket(self) -> None:
        assigner_id = uuid4()
        assignee_id = uuid4()
        organization_id = uuid4()
        slack_repository = FakeSlackRepository()
        slack_repository.sender_owner_id = assigner_id
        slack_repository.assignment_context = SlackOrganizationAssignmentContext(
            organization_id=organization_id,
            assigner_role="TEAM_LEAD",
            assignee_role="MEMBER",
        )
        tickets = FakeTicketRepository()
        slack_channels = FakeSlackChannelService()
        processor = SlackEventProcessor(
            slack_repository,
            tickets,
            FakeOllamaService(),
            FakeSlackUserService(),
            slack_channels,
        )

        asyncio.run(
            processor.process(
                "Ev-org",
                "T123",
                SlackEvent(
                    type="message",
                    user="U-SENDER",
                    text="<@U-CONNECTED> fix the deployment issue",
                    channel="C123",
                    channel_type="channel",
                    ts="123.456",
                ),
                [SlackMentionTarget(assignee_id, "U-CONNECTED")],
            )
        )

        self.assertEqual(len(tickets.created), 1)
        ticket = tickets.created[0]
        self.assertEqual(ticket.scope, "ORGANIZATION")
        self.assertEqual(ticket.organization_id, organization_id)
        self.assertEqual(ticket.owner_id, assignee_id)
        self.assertEqual(ticket.assignee_user_id, assignee_id)
        self.assertEqual(ticket.assigned_by_user_id, assigner_id)
        self.assertEqual(ticket.created_by, assigner_id)
        self.assertEqual(ticket.assignee, "Noah")
        self.assertEqual(ticket.requested_by_name, "Aisha")
        self.assertEqual(ticket.source_team_id, "T123")
        self.assertEqual(ticket.source_channel_id, "C123")
        self.assertEqual(ticket.source_channel_name, "product-team")
        self.assertEqual(ticket.source_message_ts, "123.456")
        self.assertEqual(slack_channels.lookups, [(assignee_id, "T123", "C123", "channel")])
        self.assertEqual(tickets.results[0]["scope"], "ORGANIZATION")

    def test_mapped_slack_channel_scopes_organization_ticket_to_project_board(self) -> None:
        assigner_id = uuid4()
        assignee_id = uuid4()
        organization_id = uuid4()
        board_id = uuid4()
        slack_repository = FakeSlackRepository()
        slack_repository.sender_owner_id = assigner_id
        slack_repository.assignment_context = SlackOrganizationAssignmentContext(
            organization_id=organization_id,
            assigner_role="OWNER",
            assignee_role="MEMBER",
        )
        slack_repository.board_binding = SimpleNamespace(
            organization_id=organization_id,
            board_id=board_id,
            slack_team_id="T123",
            slack_channel_id="C123",
        )
        tickets = FakeTicketRepository()
        processor = SlackEventProcessor(
            slack_repository,
            tickets,
            FakeOllamaService(),
            FakeSlackUserService(),
        )

        asyncio.run(
            processor.process(
                "Ev-board",
                "T123",
                SlackEvent(
                    type="message",
                    user="U-SENDER",
                    text="<@U-CONNECTED> fix the backend queue",
                    channel="C123",
                    channel_type="channel",
                    ts="111.222",
                ),
                [SlackMentionTarget(assignee_id, "U-CONNECTED")],
            )
        )

        ticket = tickets.created[0]
        self.assertEqual(ticket.scope, "ORGANIZATION")
        self.assertEqual(ticket.organization_id, organization_id)
        self.assertEqual(ticket.board_id, board_id)
        self.assertEqual(
            slack_repository.board_binding_lookup,
            (organization_id, "T123", "C123"),
        )
        self.assertEqual(tickets.results[0]["board_id"], str(board_id))

    def test_lead_assignment_in_private_channel_creates_organization_ticket(self) -> None:
        assigner_id = uuid4()
        assignee_id = uuid4()
        organization_id = uuid4()
        slack_repository = FakeSlackRepository()
        slack_repository.sender_owner_id = assigner_id
        slack_repository.assignment_context = SlackOrganizationAssignmentContext(
            organization_id=organization_id,
            assigner_role="OWNER",
            assignee_role="MEMBER",
        )
        tickets = FakeTicketRepository()
        processor = SlackEventProcessor(
            slack_repository,
            tickets,
            FakeOllamaService(),
            FakeSlackUserService(),
        )

        asyncio.run(
            processor.process(
                "Ev-private-channel",
                "T123",
                SlackEvent(
                    type="message",
                    user="U-SENDER",
                    text="<@U-CONNECTED> prepare the launch checklist",
                    channel="G123",
                    channel_type="group",
                    ts="456.789",
                ),
                [SlackMentionTarget(assignee_id, "U-CONNECTED")],
            )
        )

        ticket = tickets.created[0]
        self.assertEqual(ticket.scope, "ORGANIZATION")
        self.assertEqual(ticket.organization_id, organization_id)
        self.assertEqual(ticket.assigned_by_user_id, assigner_id)
        self.assertEqual(ticket.assignee_user_id, assignee_id)

    def test_lead_assignment_in_direct_message_stays_private_ticket(self) -> None:
        assigner_id = uuid4()
        assignee_id = uuid4()
        slack_repository = FakeSlackRepository()
        slack_repository.sender_owner_id = assigner_id
        slack_repository.assignment_context = SlackOrganizationAssignmentContext(
            organization_id=uuid4(),
            assigner_role="TEAM_LEAD",
            assignee_role="MEMBER",
        )
        tickets = FakeTicketRepository()
        processor = SlackEventProcessor(
            slack_repository,
            tickets,
            FakeOllamaService(),
            FakeSlackUserService(),
        )

        asyncio.run(
            processor.process(
                "Ev-dm",
                "T123",
                SlackEvent(
                    type="message",
                    user="U-SENDER",
                    text="<@U-CONNECTED> can you check this quietly?",
                    channel="D123",
                    channel_type="im",
                    ts="789.123",
                ),
                [SlackMentionTarget(assignee_id, "U-CONNECTED")],
            )
        )

        ticket = tickets.created[0]
        self.assertEqual(ticket.scope, "PRIVATE")
        self.assertIsNone(ticket.organization_id)
        self.assertIsNone(ticket.assigned_by_user_id)
        self.assertEqual(ticket.assignee_user_id, assignee_id)

    def test_member_assignment_stays_private_ticket(self) -> None:
        assigner_id = uuid4()
        assignee_id = uuid4()
        slack_repository = FakeSlackRepository()
        slack_repository.sender_owner_id = assigner_id
        slack_repository.assignment_context = SlackOrganizationAssignmentContext(
            organization_id=uuid4(),
            assigner_role="MEMBER",
            assignee_role="MEMBER",
        )
        tickets = FakeTicketRepository()
        processor = SlackEventProcessor(
            slack_repository,
            tickets,
            FakeOllamaService(),
            FakeSlackUserService(),
        )

        asyncio.run(
            processor.process(
                "Ev-private",
                "T123",
                SlackEvent(
                    type="message",
                    user="U-SENDER",
                    text="<@U-CONNECTED> please review my PR",
                ),
                [SlackMentionTarget(assignee_id, "U-CONNECTED")],
            )
        )

        ticket = tickets.created[0]
        self.assertEqual(ticket.scope, "PRIVATE")
        self.assertIsNone(ticket.organization_id)
        self.assertEqual(ticket.owner_id, assignee_id)
        self.assertEqual(ticket.assignee_user_id, assignee_id)
        self.assertIsNone(ticket.assigned_by_user_id)
        self.assertEqual(ticket.requested_by_name, "Aisha")
