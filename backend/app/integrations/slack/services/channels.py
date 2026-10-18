import logging
from uuid import UUID

import httpx
from starlette.concurrency import run_in_threadpool
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.integrations.slack.data.repository import SlackRepository, SlackRepositoryError
from app.integrations.slack.schemas import SlackChannelRefreshResponse
from app.integrations.slack.security.encryption import TokenCipher, TokenEncryptionError


SLACK_CONVERSATIONS_INFO_URL = "https://slack.com/api/conversations.info"
SLACK_CONVERSATIONS_JOIN_URL = "https://slack.com/api/conversations.join"
CHANNEL_NAME_CACHE_SECONDS = 60 * 60 * 6
logger = logging.getLogger(__name__)


class SlackChannelService:
    """Resolve Slack channel IDs to readable names without blocking ticket creation."""

    def __init__(
        self,
        repository: SlackRepository,
        token_cipher: TokenCipher,
        http_client: httpx.AsyncClient | None = None,
        redis: Redis | None = None,
    ) -> None:
        self.repository = repository
        self.token_cipher = token_cipher
        self.http_client = http_client
        self.redis = redis

    async def display_name(
        self,
        owner_id: UUID,
        team_id: str | None,
        slack_channel_id: str | None,
        channel_type: str | None = None,
    ) -> str | None:
        if not slack_channel_id:
            return None
        if channel_type == "im":
            return "Direct message"
        if channel_type == "mpim":
            return "Group direct message"

        try:
            cached = await self._cached_channel_name(team_id, slack_channel_id)
            if cached:
                return cached
            installation = await run_in_threadpool(self.repository.get_installation, owner_id)
            if installation is None:
                logger.info(
                    "Slack channel name skipped because installation was not found",
                    extra={"slack_channel_id": slack_channel_id},
                )
                return None
            token = self.token_cipher.decrypt(installation.token_ciphertext)
            payload = await self._get_channel(token, slack_channel_id)
            if payload.get("ok") is not True:
                logger.warning(
                    "Slack channel lookup returned non-ok response",
                    extra={
                        "slack_channel_id": slack_channel_id,
                        "slack_error": payload.get("error"),
                    },
                )
                return None

            channel = payload.get("channel")
            if not isinstance(channel, dict):
                logger.warning(
                    "Slack channel lookup returned invalid channel payload",
                    extra={"slack_channel_id": slack_channel_id},
                )
                return None
            resolved = self._extract_channel_name(payload)
            if resolved is not None:
                await self._cache_channel_name(team_id, slack_channel_id, resolved)
                logger.info(
                    "Slack channel name resolved",
                    extra={
                        "slack_channel_id": slack_channel_id,
                        "slack_channel_name": resolved,
                    },
                )
                return resolved
            logger.warning(
                "Slack channel lookup did not include a readable name",
                extra={"slack_channel_id": slack_channel_id},
            )
            return None
        except (SlackRepositoryError, TokenEncryptionError, httpx.HTTPError, ValueError, TypeError):
            logger.warning(
                "Could not resolve Slack channel display name",
                extra={"slack_channel_id": slack_channel_id},
            )
            return None

    async def refresh_organization_channels(
        self,
        organization_id: UUID,
    ) -> SlackChannelRefreshResponse:
        binding = await run_in_threadpool(self.repository.get_organization_workspace_binding, organization_id)
        if binding is None:
            return SlackChannelRefreshResponse(
                channels_checked=0,
                channels_updated=0,
                message="Slack workspace is not connected to this organization.",
            )

        installation = await run_in_threadpool(self.repository.get_installation, binding.verified_by_user_id)
        if installation is None:
            return SlackChannelRefreshResponse(
                channels_checked=0,
                channels_updated=0,
                reconnect_required=True,
                message="The Slack verifier no longer has a connected Slack installation. Reconnect Slack once.",
            )

        channels = await run_in_threadpool(self.repository.list_organization_mapped_channels, organization_id)
        if not channels:
            return SlackChannelRefreshResponse(
                channels_checked=0,
                channels_updated=0,
                message="No project board Slack channels are linked yet.",
            )

        token = self.token_cipher.decrypt(installation.token_ciphertext)
        checked = 0
        updated = 0
        joined = 0
        missing_scopes: set[str] = set()
        manual_invites: list[str] = []
        for channel in channels:
            checked += 1
            try:
                payload = await self._get_channel(token, channel.slack_channel_id)
            except httpx.HTTPError:
                logger.warning(
                    "Slack channel refresh request failed",
                    extra={
                        "organization_id": str(organization_id),
                        "slack_channel_id": channel.slack_channel_id,
                    },
                    exc_info=True,
                )
                continue
            if payload.get("ok") is not True:
                error = payload.get("error")
                self._collect_missing_scopes(payload, missing_scopes)
                logger.warning(
                    "Slack channel refresh skipped one channel",
                    extra={
                        "organization_id": str(organization_id),
                        "slack_channel_id": channel.slack_channel_id,
                        "slack_error": error,
                    },
                )
                continue

            if await self._ensure_public_channel_membership(
                token,
                channel.slack_team_id,
                channel.slack_channel_id,
                payload,
                missing_scopes,
                manual_invites,
            ):
                joined += 1

            name = self._extract_channel_name(payload)
            if not name:
                continue
            await self._cache_channel_name(channel.slack_team_id, channel.slack_channel_id, name)
            if name != channel.slack_channel_name:
                await run_in_threadpool(
                    self.repository.update_board_channel_display_name,
                    organization_id,
                    channel.board_id,
                    channel.slack_team_id,
                    channel.slack_channel_id,
                    name,
                )
                updated += 1

        reconnect_required = bool(missing_scopes)
        return SlackChannelRefreshResponse(
            channels_checked=checked,
            channels_updated=updated,
            channels_joined=joined,
            manual_invites_required=manual_invites,
            reconnect_required=reconnect_required,
            missing_scopes=sorted(missing_scopes),
            message=(
                "Slack needs updated permissions. Reconnect Slack once."
                if reconnect_required
                else "Some private channels still need the app to be invited once."
                if manual_invites
                else "Slack channel metadata refreshed."
            ),
        )

    async def _get_channel(self, token: str, slack_channel_id: str) -> dict:
        if self.http_client is not None:
            response = await self.http_client.get(
                SLACK_CONVERSATIONS_INFO_URL,
                params={"channel": slack_channel_id},
                headers={"Authorization": f"Bearer {token}"},
            )
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    SLACK_CONVERSATIONS_INFO_URL,
                    params={"channel": slack_channel_id},
                    headers={"Authorization": f"Bearer {token}"},
                )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Slack returned invalid channel data")
        return payload

    async def _join_channel(self, token: str, slack_channel_id: str) -> dict:
        if self.http_client is not None:
            response = await self.http_client.post(
                SLACK_CONVERSATIONS_JOIN_URL,
                json={"channel": slack_channel_id},
                headers={"Authorization": f"Bearer {token}"},
            )
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    SLACK_CONVERSATIONS_JOIN_URL,
                    json={"channel": slack_channel_id},
                    headers={"Authorization": f"Bearer {token}"},
                )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Slack returned invalid join data")
        return payload

    async def _ensure_public_channel_membership(
        self,
        token: str,
        slack_team_id: str,
        slack_channel_id: str,
        channel_payload: dict,
        missing_scopes: set[str],
        manual_invites: list[str],
    ) -> bool:
        channel = channel_payload.get("channel")
        if not isinstance(channel, dict):
            return False
        if channel.get("is_member") is True:
            return False
        if channel.get("is_channel") is not True:
            manual_invites.append(slack_channel_id)
            logger.info(
                "Slack channel requires manual app invite",
                extra={
                    "slack_team_id": slack_team_id,
                    "slack_channel_id": slack_channel_id,
                },
            )
            return False

        try:
            join_payload = await self._join_channel(token, slack_channel_id)
        except (httpx.HTTPError, ValueError, TypeError):
            logger.warning(
                "Slack channel auto-join failed",
                extra={
                    "slack_team_id": slack_team_id,
                    "slack_channel_id": slack_channel_id,
                },
                exc_info=True,
            )
            return False

        if join_payload.get("ok") is True:
            logger.info(
                "Slack bot joined mapped public channel",
                extra={
                    "slack_team_id": slack_team_id,
                    "slack_channel_id": slack_channel_id,
                },
            )
            return True

        self._collect_missing_scopes(join_payload, missing_scopes)
        error = join_payload.get("error")
        if error in {"method_not_supported_for_channel_type", "channel_not_found", "not_in_channel"}:
            manual_invites.append(slack_channel_id)
        logger.warning(
            "Slack channel auto-join returned non-ok response",
            extra={
                "slack_team_id": slack_team_id,
                "slack_channel_id": slack_channel_id,
                "slack_error": error,
            },
        )
        return False

    def _collect_missing_scopes(self, payload: dict, missing_scopes: set[str]) -> None:
        if payload.get("error") != "missing_scope":
            return
        needed = payload.get("needed")
        if isinstance(needed, str):
            missing_scopes.update(
                scope.strip()
                for scope in needed.split(",")
                if scope.strip()
            )

    def _extract_channel_name(self, payload: dict) -> str | None:
        channel = payload.get("channel")
        if not isinstance(channel, dict):
            return None
        for field in ("name_normalized", "name"):
            value = channel.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip().lstrip("#")
        return None

    async def _cached_channel_name(
        self,
        team_id: str | None,
        channel_id: str,
    ) -> str | None:
        if self.redis is None or not team_id:
            return None
        try:
            value = await self.redis.get(self._channel_cache_key(team_id, channel_id))
        except (RedisError, OSError):
            logger.warning("Slack channel cache read failed", exc_info=True)
            return None
        return value if isinstance(value, str) and value else None

    async def _cache_channel_name(
        self,
        team_id: str | None,
        channel_id: str,
        name: str,
    ) -> None:
        if self.redis is None or not team_id:
            return
        try:
            await self.redis.set(
                self._channel_cache_key(team_id, channel_id),
                name,
                ex=CHANNEL_NAME_CACHE_SECONDS,
            )
        except (RedisError, OSError):
            logger.warning("Slack channel cache write failed", exc_info=True)

    def _channel_cache_key(self, team_id: str, channel_id: str) -> str:
        return f"slack:channel-name:{team_id}:{channel_id}"
