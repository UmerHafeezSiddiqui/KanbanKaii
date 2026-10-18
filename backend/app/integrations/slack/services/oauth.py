import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode
from uuid import UUID

import httpx
from starlette.concurrency import run_in_threadpool

from app.integrations.slack.config import SlackOAuthSettings
from app.integrations.slack.security.encryption import TokenCipher
from app.integrations.slack.data.repository import SlackRepository
from app.integrations.slack.schemas import SlackOAuthAccessResponse, SlackUserInfoResponse
from app.integrations.slack.services.oauth_state import SlackOAuthStateStore


SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
class SlackOAuthError(RuntimeError):
    """Raised when Slack rejects or returns an invalid OAuth exchange."""


class SlackWorkspaceVerificationError(SlackOAuthError):
    """Raised when the connector cannot prove workspace ownership."""

    def __init__(
        self,
        message: str,
        organization_id: UUID | None = None,
    ) -> None:
        super().__init__(message)
        self.organization_id = organization_id


@dataclass(frozen=True)
class SlackOAuthCompletion:
    workspace_name: str
    organization_id: UUID | None = None


class SlackOAuthService:
    def __init__(
        self,
        settings: SlackOAuthSettings,
        repository: SlackRepository,
        token_cipher: TokenCipher,
        state_store: SlackOAuthStateStore,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.token_cipher = token_cipher
        self.state_store = state_store
        self.http_client = http_client

    async def create_authorization_url(
        self,
        owner_id: UUID,
        organization_id: UUID | None = None,
    ) -> str:
        if organization_id and not await run_in_threadpool(self.repository.is_organization_owner, owner_id, organization_id):
            raise SlackWorkspaceVerificationError(
                "Only the KanbanKaii organization owner can bind Slack"
            )
        raw_state = secrets.token_urlsafe(32)
        state_hash = hashlib.sha256(raw_state.encode("utf-8")).hexdigest()
        await self.state_store.create(owner_id, state_hash, organization_id)

        query = urlencode(
            {
                "client_id": self.settings.client_id,
                "scope": ",".join(self.settings.scopes),
                "redirect_uri": self.settings.redirect_uri,
                "state": raw_state,
            }
        )
        return f"{SLACK_AUTHORIZE_URL}?{query}"

    async def complete_installation(
        self,
        code: str,
        raw_state: str,
    ) -> SlackOAuthCompletion:
        state_hash = hashlib.sha256(raw_state.encode("utf-8")).hexdigest()
        context = await self.state_store.consume(state_hash)
        request_data = {
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret,
            "code": code,
            "redirect_uri": self.settings.redirect_uri,
        }
        try:
            if self.http_client is not None:
                response = await self.http_client.post(SLACK_TOKEN_URL, data=request_data)
            else:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    response = await client.post(SLACK_TOKEN_URL, data=request_data)
            response.raise_for_status()
            oauth_result = SlackOAuthAccessResponse.model_validate(response.json())
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise SlackOAuthError("Slack OAuth token exchange failed") from error

        if (
            not oauth_result.ok
            or not oauth_result.access_token
            or not oauth_result.team
            or not oauth_result.bot_user_id
            or not oauth_result.authed_user
        ):
            raise SlackOAuthError(
                f"Slack rejected the OAuth request: {oauth_result.error or 'invalid response'}"
            )

        if context.organization_id:
            if not await run_in_threadpool(self.repository.is_organization_owner, context.owner_id, context.organization_id):
                raise SlackWorkspaceVerificationError(
                    "KanbanKaii organization ownership changed during Slack authorization",
                    context.organization_id,
                )
            try:
                slack_user = await self._get_installer(oauth_result)
            except SlackWorkspaceVerificationError as error:
                raise SlackWorkspaceVerificationError(
                    str(error), context.organization_id
                ) from error
            if not (slack_user.user and (
                slack_user.user.is_owner or slack_user.user.is_primary_owner
            )):
                raise SlackWorkspaceVerificationError(
                    "The Slack account is not a workspace owner",
                    context.organization_id,
                )

        ciphertext = self.token_cipher.encrypt(oauth_result.access_token)
        scopes = [scope for scope in oauth_result.scope.split(",") if scope]
        await run_in_threadpool(
            self.repository.save_installation,
            owner_id=context.owner_id,
            team_id=oauth_result.team.id,
            team_name=oauth_result.team.name,
            bot_user_id=oauth_result.bot_user_id,
            slack_user_id=oauth_result.authed_user.id,
            token_ciphertext=ciphertext,
            scopes=scopes,
        )
        if context.organization_id:
            assert slack_user.user is not None
            await run_in_threadpool(
                self.repository.bind_organization_workspace,
                organization_id=context.organization_id,
                owner_id=context.owner_id,
                team_id=oauth_result.team.id,
                workspace_name=oauth_result.team.name,
                slack_user_id=slack_user.user.id,
                is_primary_owner=slack_user.user.is_primary_owner,
            )
        return SlackOAuthCompletion(
            workspace_name=oauth_result.team.name,
            organization_id=context.organization_id,
        )

    async def _get_installer(
        self,
        oauth_result: SlackOAuthAccessResponse,
    ) -> SlackUserInfoResponse:
        assert oauth_result.access_token and oauth_result.authed_user
        headers = {"Authorization": f"Bearer {oauth_result.access_token}"}
        params = {"user": oauth_result.authed_user.id}
        try:
            if self.http_client is not None:
                response = await self.http_client.get(
                    "https://slack.com/api/users.info", headers=headers, params=params
                )
            else:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    response = await client.get(
                        "https://slack.com/api/users.info", headers=headers, params=params
                    )
            response.raise_for_status()
            result = SlackUserInfoResponse.model_validate(response.json())
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise SlackWorkspaceVerificationError(
                "Slack workspace ownership verification failed"
            ) from error
        if not result.ok or not result.user:
            raise SlackWorkspaceVerificationError(
                f"Slack could not verify the workspace owner: {result.error or 'invalid response'}"
            )
        return result
