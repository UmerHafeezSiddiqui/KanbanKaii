from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.organizations.schemas import (
    AssignableRole,
    MyOrganizationInvitation,
    OrganizationInviteResponse,
)


INVITE_KEY_PREFIX = "organization:invite:"
INVITE_TOKEN_KEY_PREFIX = "organization:invite_token:"
INVITE_ORGANIZATION_INDEX_PREFIX = "organization:invites:by_org:"
INVITE_EMAIL_INDEX_PREFIX = "organization:invites:by_email:"
INVITE_DEDUPE_KEY_PREFIX = "organization:invite_dedupe:"


class OrganizationInviteStoreError(RuntimeError):
    """Raised when Redis cannot manage transient organization invitations."""


class OrganizationInviteNotFoundError(OrganizationInviteStoreError):
    """Raised when an invitation is missing, expired, revoked, or declined."""


@dataclass(frozen=True)
class RedisInviteDraft:
    organization_id: UUID
    organization_name: str
    organization_slug: str
    intended_email: str
    default_role: AssignableRole
    created_by: UUID
    expires_at: datetime
    token_hash: str


class OrganizationInviteStore:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def create(self, draft: RedisInviteDraft) -> OrganizationInviteResponse:
        invite_id = uuid4()
        now = datetime.now(timezone.utc)
        ttl_seconds = self._ttl_seconds(draft.expires_at)
        if ttl_seconds <= 0:
            raise OrganizationInviteStoreError("Invitation expiry must be in the future")

        email = self._normalize_email(draft.intended_email)
        payload = {
            "id": str(invite_id),
            "organization_id": str(draft.organization_id),
            "organization_name": draft.organization_name,
            "organization_slug": draft.organization_slug,
            "intended_email": email,
            "default_role": draft.default_role,
            "created_by": str(draft.created_by),
            "created_at": now.isoformat(),
            "expires_at": draft.expires_at.isoformat(),
            "token_hash": draft.token_hash,
        }
        invite_key = self._invite_key(invite_id)
        token_key = self._token_key(draft.token_hash)
        organization_index_key = self._organization_index_key(draft.organization_id)
        email_index_key = self._email_index_key(email)
        dedupe_key = self._dedupe_key(draft.organization_id, email)

        try:
            async with self.redis.pipeline(transaction=True) as pipeline:
                pipeline.set(dedupe_key, str(invite_id), ex=ttl_seconds, nx=True)
                results = await pipeline.execute()
            if results[0] is not True:
                raise OrganizationInviteStoreError(
                    "A pending invitation already exists for this email"
                )

            async with self.redis.pipeline(transaction=True) as pipeline:
                pipeline.set(invite_key, json.dumps(payload), ex=ttl_seconds)
                pipeline.set(token_key, str(invite_id), ex=ttl_seconds, nx=True)
                pipeline.sadd(organization_index_key, str(invite_id))
                pipeline.expire(organization_index_key, ttl_seconds, nx=True)
                pipeline.expire(organization_index_key, ttl_seconds, gt=True)
                pipeline.sadd(email_index_key, str(invite_id))
                pipeline.expire(email_index_key, ttl_seconds, nx=True)
                pipeline.expire(email_index_key, ttl_seconds, gt=True)
                results = await pipeline.execute()
            if results[1] is not True:
                async with self.redis.pipeline(transaction=True) as cleanup:
                    cleanup.delete(invite_key, dedupe_key)
                    cleanup.srem(organization_index_key, str(invite_id))
                    cleanup.srem(email_index_key, str(invite_id))
                    await cleanup.execute()
                raise OrganizationInviteStoreError("Organization invitation token collision")
        except OrganizationInviteStoreError:
            raise
        except (RedisError, OSError) as error:
            raise OrganizationInviteStoreError(
                "Redis could not create the organization invitation"
            ) from error

        return self._response_from_payload(payload)

    async def list_for_organization(
        self,
        organization_id: UUID,
    ) -> list[OrganizationInviteResponse]:
        invite_ids = await self._index_members(self._organization_index_key(organization_id))
        invites = [
            invite
            for invite_id in invite_ids
            if (invite := await self.get_by_id(UUID(invite_id))) is not None
        ]
        return sorted(invites, key=lambda invite: invite.created_at, reverse=True)

    async def list_for_email(self, email: str) -> list[MyOrganizationInvitation]:
        invite_ids = await self._index_members(self._email_index_key(self._normalize_email(email)))
        invitations: list[MyOrganizationInvitation] = []
        for invite_id in invite_ids:
            payload = await self._payload_by_id(UUID(invite_id))
            if payload is None:
                continue
            invitations.append(
                MyOrganizationInvitation.model_validate_json(json.dumps({
                    "id": payload["id"],
                    "organization_id": payload["organization_id"],
                    "organization_name": payload["organization_name"],
                    "organization_slug": payload["organization_slug"],
                    "default_role": payload["default_role"],
                    "created_by": payload["created_by"],
                    "created_at": payload["created_at"],
                    "expires_at": payload["expires_at"],
                }))
            )
        return sorted(invitations, key=lambda invite: invite.created_at, reverse=True)

    async def get_by_id(self, invite_id: UUID) -> OrganizationInviteResponse | None:
        payload = await self._payload_by_id(invite_id)
        return self._response_from_payload(payload) if payload else None

    async def get_by_token_hash(
        self,
        token_hash: str,
    ) -> OrganizationInviteResponse | None:
        try:
            invite_id = await self.redis.get(self._token_key(token_hash))
        except (RedisError, OSError) as error:
            raise OrganizationInviteStoreError(
                "Redis could not load the organization invitation token"
            ) from error
        if not invite_id:
            return None
        return await self.get_by_id(UUID(invite_id))

    async def delete(self, invite_id: UUID) -> None:
        payload = await self._payload_by_id(invite_id)
        if payload is None:
            raise OrganizationInviteNotFoundError("Organization invitation was not found")
        await self.discard(self._response_from_payload(payload), payload["token_hash"])

    async def discard(
        self,
        invite: OrganizationInviteResponse,
        token_hash: str | None = None,
    ) -> None:
        payload = None if token_hash else await self._payload_by_id(invite.id)
        resolved_token_hash = token_hash or (payload["token_hash"] if payload else None)
        if resolved_token_hash is None:
            return
        intended_email = self._normalize_email(invite.intended_email or "")
        organization_id = invite.organization_id
        try:
            async with self.redis.pipeline(transaction=True) as pipeline:
                pipeline.delete(self._invite_key(invite.id))
                pipeline.delete(self._token_key(resolved_token_hash))
                pipeline.delete(self._dedupe_key(organization_id, intended_email))
                pipeline.srem(self._organization_index_key(organization_id), str(invite.id))
                pipeline.srem(self._email_index_key(intended_email), str(invite.id))
                await pipeline.execute()
        except (RedisError, OSError) as error:
            raise OrganizationInviteStoreError(
                "Redis could not delete the organization invitation"
            ) from error

    async def _payload_by_id(self, invite_id: UUID) -> dict[str, str] | None:
        try:
            raw_payload = await self.redis.get(self._invite_key(invite_id))
        except (RedisError, OSError) as error:
            raise OrganizationInviteStoreError(
                "Redis could not load the organization invitation"
            ) from error
        if raw_payload is None:
            return None
        try:
            payload = json.loads(raw_payload)
            if not isinstance(payload, dict):
                raise TypeError("Invite payload must be an object")
            return payload
        except (json.JSONDecodeError, TypeError) as error:
            raise OrganizationInviteStoreError(
                "Redis returned an invalid organization invitation"
            ) from error

    async def _index_members(self, key: str) -> set[str]:
        try:
            members = await self.redis.smembers(key)
            return {str(member) for member in members}
        except (RedisError, OSError) as error:
            raise OrganizationInviteStoreError(
                "Redis could not load organization invitation indexes"
            ) from error

    def _response_from_payload(self, payload: dict[str, str]) -> OrganizationInviteResponse:
        return OrganizationInviteResponse.model_validate_json(json.dumps({
            "id": payload["id"],
            "organization_id": payload["organization_id"],
            "intended_email": payload["intended_email"],
            "default_role": payload["default_role"],
            "created_by": payload["created_by"],
            "created_at": payload["created_at"],
            "expires_at": payload["expires_at"],
            "accepted_at": None,
            "accepted_by": None,
            "revoked_at": None,
            "declined_at": None,
            "declined_by": None,
        }))

    @staticmethod
    def _ttl_seconds(expires_at: datetime) -> int:
        now = datetime.now(timezone.utc)
        expiry = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
        return max(0, int((expiry - now).total_seconds()))

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _invite_key(invite_id: UUID) -> str:
        return f"{INVITE_KEY_PREFIX}{invite_id}"

    @staticmethod
    def _token_key(token_hash: str) -> str:
        return f"{INVITE_TOKEN_KEY_PREFIX}{token_hash}"

    @staticmethod
    def _organization_index_key(organization_id: UUID) -> str:
        return f"{INVITE_ORGANIZATION_INDEX_PREFIX}{organization_id}"

    @staticmethod
    def _email_index_key(email: str) -> str:
        return f"{INVITE_EMAIL_INDEX_PREFIX}{email}"

    @staticmethod
    def _dedupe_key(organization_id: UUID, email: str) -> str:
        return f"{INVITE_DEDUPE_KEY_PREFIX}{organization_id}:{email}"
