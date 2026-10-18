import httpx
from starlette.concurrency import run_in_threadpool
from uuid import UUID

from app.integrations.slack.security.encryption import TokenCipher, TokenEncryptionError
from app.integrations.slack.data.repository import SlackRepository


SLACK_AUTH_TEST_URL = "https://slack.com/api/auth.test"
SLACK_AUTH_REVOKE_URL = "https://slack.com/api/auth.revoke"
REVOKED_TOKEN_ERRORS = {"invalid_auth", "token_revoked", "account_inactive"}


class SlackConnectionError(RuntimeError):
    """Raised when Slack connection state cannot be verified or changed."""


class SlackConnectionService:
    def __init__(
        self,
        repository: SlackRepository,
        token_cipher: TokenCipher,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.repository = repository
        self.token_cipher = token_cipher
        self.http_client = http_client

    async def status(self, owner_id: UUID) -> str | None:
        installation = await run_in_threadpool(self.repository.get_installation, owner_id)
        if installation is None:
            return None
        try:
            token = self.token_cipher.decrypt(installation.token_ciphertext)
        except TokenEncryptionError as error:
            raise SlackConnectionError("Stored Slack credentials are invalid") from error
        result = await self._post(SLACK_AUTH_TEST_URL, token)
        if result.get("ok") is True:
            return installation.workspace_name
        if result.get("error") in REVOKED_TOKEN_ERRORS:
            await run_in_threadpool(self.repository.delete_owner_installation, owner_id)
            return None
        raise SlackConnectionError("Slack could not verify the installation")

    async def disconnect(self, owner_id: UUID) -> None:
        installation = await run_in_threadpool(self.repository.get_installation, owner_id)
        if installation is None:
            return
        try:
            token = self.token_cipher.decrypt(installation.token_ciphertext)
        except TokenEncryptionError as error:
            raise SlackConnectionError("Stored Slack credentials are invalid") from error
        result = await self._post(SLACK_AUTH_REVOKE_URL, token)
        if result.get("ok") is not True and result.get("error") not in REVOKED_TOKEN_ERRORS:
            raise SlackConnectionError("Slack could not revoke the installation")
        await run_in_threadpool(self.repository.delete_owner_installation, owner_id)

    async def _post(self, url: str, token: str) -> dict:
        try:
            if self.http_client is not None:
                response = await self.http_client.post(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                )
            else:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        url,
                        headers={"Authorization": f"Bearer {token}"},
                    )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise SlackConnectionError("Slack API request failed") from error
        if not isinstance(payload, dict):
            raise SlackConnectionError("Slack returned an invalid response")
        return payload
