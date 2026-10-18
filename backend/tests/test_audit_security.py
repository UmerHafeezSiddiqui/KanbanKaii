import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.auth.dependencies import AuthenticatedUser, get_auth_client, get_current_user_id
from app.main import app
from app.integrations.slack.routes.webhooks import get_slack_ai_rate_limiter
from app.organizations.schemas import OrganizationInviteResponse
from app.organizations.service import RedisOrganizationInviteService
from app.routes.triage import get_configured_ollama_service, get_ticket_repository


class TriageSecurityTests(TestCase):
    def setUp(self):
        from app.schemas.triage import AIAnalysisResult
        self.model = SimpleNamespace(analyze=AsyncMock(return_value=AIAnalysisResult(
            isActionableTask=False, extractedTitle='', cleanDescription='', estimatedPriority='LOW',
        )))
        self.repository = Mock()
        self.limiter = SimpleNamespace(acquire=AsyncMock(return_value=True))
        app.dependency_overrides[get_slack_ai_rate_limiter] = lambda: self.limiter
        app.dependency_overrides[get_auth_client] = lambda: Mock()
        app.dependency_overrides[get_configured_ollama_service] = lambda: self.model
        app.dependency_overrides[get_ticket_repository] = lambda: self.repository
        self.body = dict(text="Fix checkout", user_name="Aisha", source="SLACK", owner_id=str(uuid4()))

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_unsigned_request_cannot_spend_model_or_write(self):
        response = TestClient(app).post('/api/webhook/triage', json=self.body)
        self.assertEqual(response.status_code, 401)
        self.model.analyze.assert_not_awaited()
        self.repository.create.assert_not_called()
        self.limiter.acquire.assert_not_awaited()

    def test_authenticated_user_cannot_write_for_another_owner(self):
        app.dependency_overrides[get_current_user_id] = uuid4
        response = TestClient(app).post('/api/webhook/triage', json=self.body)
        self.assertEqual(response.status_code, 403)
        self.model.analyze.assert_not_awaited()
        self.repository.create.assert_not_called()
        self.limiter.acquire.assert_not_awaited()

    def test_exhausted_allowance_cannot_spend_model_or_write(self):
        app.dependency_overrides[get_current_user_id] = lambda: UUID(self.body['owner_id'])
        self.limiter.acquire.return_value = False
        response = TestClient(app).post('/api/webhook/triage', json=self.body)
        self.assertEqual(response.status_code, 429)
        self.model.analyze.assert_not_awaited()
        self.repository.create.assert_not_called()

    def test_rate_limit_failure_fails_closed(self):
        from app.redis.rate_limiter import AIRateLimiterError
        app.dependency_overrides[get_current_user_id] = lambda: UUID(self.body['owner_id'])
        self.limiter.acquire.side_effect = AIRateLimiterError('Redis unavailable')
        response = TestClient(app).post('/api/webhook/triage', json=self.body)
        self.assertEqual(response.status_code, 503)
        self.model.analyze.assert_not_awaited()
        self.repository.create.assert_not_called()


class InvitationAcceptanceSecurityTests(TestCase):
    def setUp(self):
        self.user = AuthenticatedUser(id=uuid4(), email='recipient@example.com')
        now = datetime.now(timezone.utc)
        self.invite = OrganizationInviteResponse(
            id=uuid4(), organization_id=uuid4(), intended_email=self.user.email,
            default_role='MEMBER', created_by=uuid4(), created_at=now,
            expires_at=now + timedelta(hours=1),
        )
        self.repository = Mock()
        self.repository.accept_redis_invite.return_value = self.invite.organization_id
        self.service = RedisOrganizationInviteService(self.repository, Mock())

    def test_validated_recipient_is_forwarded_to_privileged_operation(self):
        result = asyncio.run(self.service.accept_invite(self.invite, self.user))
        self.assertEqual(result, self.invite.organization_id)
        self.repository.accept_redis_invite.assert_called_once_with(
            self.invite.organization_id, self.invite.default_role, self.invite.created_by,
            self.invite.intended_email, self.user.id,
        )

    def test_wrong_email_is_rejected_before_privileged_operation(self):
        from app.organizations.repository import OrganizationPermissionError
        self.invite.intended_email = 'someone-else@example.com'
        with self.assertRaises(OrganizationPermissionError):
            asyncio.run(self.service.accept_invite(self.invite, self.user))
        self.repository.accept_redis_invite.assert_not_called()

    def test_repository_uses_server_credentials_and_explicit_recipient(self):
        from app.organizations.repository import OrganizationRepository
        user_client = Mock()
        admin = Mock()
        admin.rpc.return_value.execute.return_value.data = str(self.invite.organization_id)
        with patch('app.organizations.repository.get_supabase_admin_client', return_value=admin):
            OrganizationRepository(user_client).accept_redis_invite(
                self.invite.organization_id, 'MEMBER', self.invite.created_by,
                self.user.email, self.user.id,
            )
        user_client.rpc.assert_not_called()
        self.assertEqual(admin.rpc.call_args.args[1]['p_user_id'], str(self.user.id))

    def test_missing_or_expired_invitation_never_reaches_membership_write(self):
        from app.auth.dependencies import get_current_user
        from app.organizations.routes.common import get_organization_repository
        from app.organizations.routes.invitations import get_organization_invite_store
        store = SimpleNamespace(get_by_id=AsyncMock(return_value=None), get_by_token_hash=AsyncMock(return_value=None))
        app.dependency_overrides[get_current_user] = lambda: self.user
        app.dependency_overrides[get_organization_repository] = lambda: self.repository
        app.dependency_overrides[get_organization_invite_store] = lambda: store
        try:
            for path in [f'/api/organizations/invitations/{uuid4()}/accept', '/api/organizations/invites/' + 'x' * 32 + '/accept']:
                self.assertEqual(TestClient(app).post(path).status_code, 404)
            self.repository.accept_redis_invite.assert_not_called()
        finally:
            app.dependency_overrides.clear()
