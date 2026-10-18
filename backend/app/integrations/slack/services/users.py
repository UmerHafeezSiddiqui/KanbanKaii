import logging
from uuid import UUID

import httpx
from starlette.concurrency import run_in_threadpool

from app.integrations.slack.security.encryption import TokenCipher, TokenEncryptionError
from app.integrations.slack.data.repository import SlackRepository, SlackRepositoryError


SLACK_USER_INFO_URL = "https://slack.com/api/users.info"
logger = logging.getLogger(__name__)


class SlackUserService:
    """Resolve Slack IDs to readable names without blocking ticket creation on failure."""

    def __init__(
        self,
        repository: SlackRepository,
        token_cipher: TokenCipher,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.repository = repository
        self.token_cipher = token_cipher
        self.http_client = http_client

    async def display_name(self, owner_id: UUID, slack_user_id: str) -> str:
        try:
            installation = await run_in_threadpool(self.repository.get_installation, owner_id)
            if installation is None:
                return slack_user_id
            token = self.token_cipher.decrypt(installation.token_ciphertext)
            payload = await self._get_user(token, slack_user_id)
            if payload.get("ok") is not True:
                return slack_user_id

            user = payload.get("user")
            if not isinstance(user, dict):
                return slack_user_id
            profile = user.get("profile")
            if isinstance(profile, dict):
                for field in ("display_name", "real_name"):
                    value = profile.get(field)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
            username = user.get("name")
            return username.strip() if isinstance(username, str) and username.strip() else slack_user_id
        except (SlackRepositoryError, TokenEncryptionError, httpx.HTTPError, ValueError, TypeError):
            logger.warning(
                "Could not resolve Slack user display name",
                extra={"slack_user_id": slack_user_id},
            )
            return slack_user_id

    async def _get_user(self, token: str, slack_user_id: str) -> dict:
        if self.http_client is not None:
            response = await self.http_client.get(
                SLACK_USER_INFO_URL,
                params={"user": slack_user_id},
                headers={"Authorization": f"Bearer {token}"},
            )
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    SLACK_USER_INFO_URL,
                    params={"user": slack_user_id},
                    headers={"Authorization": f"Bearer {token}"},
                )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Slack returned invalid user data")
        return payload
