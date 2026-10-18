from unittest import TestCase
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.auth.dependencies import get_current_user_id
from app.integrations.slack.routes.webhooks import get_slack_ai_rate_limiter
from types import SimpleNamespace
from unittest.mock import AsyncMock
from app.database.ticket_repository import TicketRepositoryError
from app.routes.triage import get_configured_ollama_service, get_ticket_repository
from app.schemas.ticket import TicketCreate, TicketResponse
from app.schemas.triage import AIAnalysisResult, IncomingMessage
from app.services.ollama_service import OllamaUnavailableError


client = TestClient(app)


class FakeOllamaService:
    def __init__(self, result: AIAnalysisResult) -> None:
        self.result = result

    async def analyze(self, message: IncomingMessage) -> AIAnalysisResult:
        return self.result


class UnavailableOllamaService:
    async def analyze(self, message: IncomingMessage) -> AIAnalysisResult:
        raise OllamaUnavailableError("Ollama is not running at the configured host")


class FakeTicketRepository:
    def __init__(self) -> None:
        self.received_ticket = None

    def create(self, ticket: TicketCreate) -> TicketResponse:
        self.received_ticket = ticket
        return TicketResponse(
            **ticket.model_dump(),
            id=uuid4(),
            created_at=datetime.now(timezone.utc),
        )


class FailingTicketRepository:
    def create(self, ticket: TicketCreate) -> TicketResponse:
        raise TicketRepositoryError("Supabase could not create the ticket")


class TriageRouteTests(TestCase):
    def setUp(self):
        self.owner_id = uuid4()
        app.dependency_overrides[get_current_user_id] = lambda: self.owner_id
        app.dependency_overrides[get_slack_ai_rate_limiter] = lambda: SimpleNamespace(acquire=AsyncMock(return_value=True))

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_actionable_message_creates_and_returns_stored_ticket(self) -> None:
        owner_id = self.owner_id
        expected = AIAnalysisResult(
            isActionableTask=True,
            extractedTitle="Fix checkout",
            cleanDescription="Resolve the checkout failure.",
            estimatedPriority="HIGH",
        )
        app.dependency_overrides[get_configured_ollama_service] = (
            lambda: FakeOllamaService(expected)
        )
        repository = FakeTicketRepository()
        app.dependency_overrides[get_ticket_repository] = lambda: repository

        response = client.post(
            "/api/webhook/triage",
            json={
                "text": "Please fix checkout urgently",
                "user_name": "Aisha",
                "owner_id": str(owner_id),
                "source": "SLACK",
            },
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["status"], "created")
        self.assertEqual(body["analysis"], expected.model_dump())
        self.assertEqual(body["ticket"]["owner_id"], str(owner_id))
        self.assertEqual(body["ticket"]["status"], "PENDING")
        self.assertEqual(body["ticket"]["source"], "SLACK")
        self.assertEqual(repository.received_ticket.title, "Fix checkout")

    def test_non_actionable_message_returns_200(self) -> None:
        expected = AIAnalysisResult(
            isActionableTask=False,
            extractedTitle="",
            cleanDescription="",
            estimatedPriority="MEDIUM",
        )
        app.dependency_overrides[get_configured_ollama_service] = (
            lambda: FakeOllamaService(expected)
        )
        repository = FakeTicketRepository()
        app.dependency_overrides[get_ticket_repository] = lambda: repository

        response = client.post(
            "/api/webhook/triage",
            json={
                "text": "Thanks, have a great weekend!",
                "user_name": "Noah",
                "owner_id": str(self.owner_id),
                "source": "GITHUB",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ignored",
                "analysis": expected.model_dump(),
                "ticket": None,
            },
        )
        self.assertIsNone(repository.received_ticket)

    def test_reports_ollama_unavailable(self) -> None:
        app.dependency_overrides[get_configured_ollama_service] = (
            lambda: UnavailableOllamaService()
        )
        app.dependency_overrides[get_ticket_repository] = FakeTicketRepository

        response = client.post(
            "/api/webhook/triage",
            json={
                "text": "Please fix checkout",
                "user_name": "Aisha",
                "owner_id": str(self.owner_id),
                "source": "SLACK",
            },
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"detail": "Ollama is not running at the configured host"},
        )

    def test_reports_ticket_storage_failure(self) -> None:
        analysis = AIAnalysisResult(
            isActionableTask=True,
            extractedTitle="Fix checkout",
            cleanDescription="Resolve the checkout failure.",
            estimatedPriority="HIGH",
        )
        app.dependency_overrides[get_configured_ollama_service] = (
            lambda: FakeOllamaService(analysis)
        )
        app.dependency_overrides[get_ticket_repository] = FailingTicketRepository

        response = client.post(
            "/api/webhook/triage",
            json={
                "text": "Please fix checkout",
                "user_name": "Aisha",
                "owner_id": str(self.owner_id),
                "source": "SLACK",
            },
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json(),
            {"detail": "Supabase could not create the ticket"},
        )
