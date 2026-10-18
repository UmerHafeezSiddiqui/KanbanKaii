import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import TestCase
from uuid import uuid4

from app.organizations.schemas import OrganizationInviteCreate, OrganizationInviteResponse
from app.organizations.service import RedisOrganizationInviteService


class FakeOrganizationRepository:
    def __init__(self) -> None:
        self.received = None

    def ensure_invite_manager(self, organization_id, created_by):
        self.manager = (organization_id, created_by)

    def get(self, organization_id):
        return SimpleNamespace(name='Test organization', slug='test-organization')


class FakeInviteStore:
    async def create(self, draft):
        self.received = draft
        now = datetime.now(timezone.utc)
        return OrganizationInviteResponse(
            id=uuid4(), organization_id=draft.organization_id, intended_email=draft.intended_email.lower(),
            default_role=draft.default_role, created_by=draft.created_by, created_at=now,
            expires_at=draft.expires_at,
        )


class OrganizationServiceTests(TestCase):
    def test_creates_random_invite_and_stores_only_hash(self) -> None:
        repository = FakeOrganizationRepository()
        store = FakeInviteStore()
        organization_id = uuid4()
        creator = uuid4()
        created = asyncio.run(RedisOrganizationInviteService(repository, store).create_invite(
            organization_id,
            OrganizationInviteCreate(intended_email="MEMBER@example.com"),
            creator,
        ))

        self.assertNotEqual(created.token, store.received.token_hash)
        self.assertEqual(len(store.received.token_hash), 64)
        self.assertEqual(created.intended_email, "member@example.com")
        self.assertEqual(repository.manager, (organization_id, creator))
        self.assertEqual(RedisOrganizationInviteService.hash_token(created.token), store.received.token_hash)

    def test_acceptance_hashes_raw_token(self) -> None:
        token_hash = RedisOrganizationInviteService.hash_token("raw-invitation-token")
        self.assertEqual(len(token_hash), 64)
        self.assertNotEqual(token_hash, "raw-invitation-token")
