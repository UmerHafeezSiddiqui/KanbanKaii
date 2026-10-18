from typing import Annotated
from urllib.parse import urlencode, urlsplit, urlunsplit
from uuid import UUID
from starlette.concurrency import run_in_threadpool

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse

from app.auth.dependencies import get_current_user_id
from app.database.supabase_client import SupabaseConfigurationError, get_supabase_admin_client
from app.integrations.slack.config import SlackConfigurationError, get_slack_oauth_settings
from app.integrations.slack.security.encryption import TokenCipher, TokenEncryptionError
from app.integrations.slack.services.connection import SlackConnectionError, SlackConnectionService
from app.integrations.slack.services.cache import SlackCacheInvalidator
from app.integrations.slack.services.channels import SlackChannelService
from app.integrations.slack.services.oauth import (
    SlackOAuthError,
    SlackOAuthService,
    SlackWorkspaceVerificationError,
)
from app.integrations.slack.services.oauth_state import (
    SlackOAuthStateError,
    SlackOAuthStateStore,
    SlackOAuthStateStoreError,
)
from app.integrations.slack.data.repository import (
    SlackRepository,
    SlackRepositoryError,
)
from app.integrations.slack.schemas import (
    OrganizationSlackBindingStatus,
    SlackChannelRefreshResponse,
    SlackConnectionStatus,
    SlackConnectResponse,
)
from app.redis.client import RedisConfigurationError, get_redis_client


router = APIRouter(prefix="/api/integrations/slack", tags=["slack"])


def get_slack_repository() -> SlackRepository:
    try:
        return SlackRepository(get_supabase_admin_client())
    except SupabaseConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def get_slack_oauth_state_store() -> SlackOAuthStateStore:
    try:
        return SlackOAuthStateStore(get_redis_client())
    except RedisConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def get_slack_oauth_service(
    repository: Annotated[SlackRepository, Depends(get_slack_repository)],
    state_store: Annotated[
        SlackOAuthStateStore,
        Depends(get_slack_oauth_state_store),
    ],
) -> SlackOAuthService:
    try:
        settings = get_slack_oauth_settings()
        return SlackOAuthService(
            settings,
            repository,
            TokenCipher(settings.encryption_key),
            state_store,
        )
    except SlackConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def get_slack_connection_service(
    repository: Annotated[SlackRepository, Depends(get_slack_repository)],
) -> SlackConnectionService:
    try:
        settings = get_slack_oauth_settings()
        return SlackConnectionService(
            repository,
            TokenCipher(settings.encryption_key),
        )
    except SlackConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def get_slack_channel_service(
    repository: Annotated[SlackRepository, Depends(get_slack_repository)],
) -> SlackChannelService:
    try:
        settings = get_slack_oauth_settings()
        return SlackChannelService(
            repository,
            TokenCipher(settings.encryption_key),
            redis=get_redis_client(),
        )
    except (SlackConfigurationError, RedisConfigurationError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def get_slack_cache_invalidator() -> SlackCacheInvalidator:
    try:
        return SlackCacheInvalidator(get_redis_client())
    except RedisConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def callback_redirect(
    result: str,
    detail: str | None = None,
    organization: bool = False,
) -> RedirectResponse:
    settings = get_slack_oauth_settings()
    query = {"slack": result}
    if detail:
        query["reason"] = detail
    return_url = settings.frontend_return_url
    if organization:
        parts = urlsplit(return_url)
        return_url = urlunsplit((parts.scheme, parts.netloc, "/organization", "", ""))
    separator = "&" if "?" in return_url else "?"
    return RedirectResponse(
        f"{return_url}{separator}{urlencode(query)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/connect", response_model=SlackConnectResponse)
async def connect_slack(
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
    oauth_service: Annotated[SlackOAuthService, Depends(get_slack_oauth_service)],
    organization_id: Annotated[UUID | None, Query()] = None,
) -> SlackConnectResponse:
    try:
        authorization_url = await oauth_service.create_authorization_url(
            owner_id, organization_id
        )
        return SlackConnectResponse(authorization_url=authorization_url)
    except SlackOAuthStateStoreError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except SlackWorkspaceVerificationError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except SlackRepositoryError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/callback")
async def slack_callback(
    oauth_service: Annotated[SlackOAuthService, Depends(get_slack_oauth_service)],
    cache_invalidator: Annotated[
        SlackCacheInvalidator,
        Depends(get_slack_cache_invalidator),
    ],
    code: Annotated[str | None, Query()] = None,
    state_value: Annotated[str | None, Query(alias="state")] = None,
    oauth_error: Annotated[str | None, Query(alias="error")] = None,
) -> RedirectResponse:
    if oauth_error:
        return callback_redirect("error", "access_denied")
    if not code or not state_value:
        return callback_redirect("error", "missing_callback_parameters")

    try:
        completion = await oauth_service.complete_installation(code, state_value)
        if completion.organization_id is not None:
            await cache_invalidator.invalidate_organization(
                str(completion.organization_id)
            )
        return callback_redirect(
            "organization_connected" if completion.organization_id else "connected",
            organization=completion.organization_id is not None,
        )
    except SlackOAuthStateError:
        return callback_redirect("error", "invalid_or_expired_state")
    except SlackOAuthStateStoreError:
        return callback_redirect("error", "state_store_unavailable")
    except SlackWorkspaceVerificationError as error:
        return callback_redirect(
            "error",
            "workspace_owner_required",
            organization=error.organization_id is not None,
        )
    except SlackOAuthError:
        return callback_redirect("error", "oauth_exchange_failed")
    except SlackRepositoryError:
        return callback_redirect("error", "installation_storage_failed")


@router.get(
    "/organizations/{organization_id}/status",
    response_model=OrganizationSlackBindingStatus,
)
async def organization_slack_status(
    organization_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repository: Annotated[SlackRepository, Depends(get_slack_repository)],
) -> OrganizationSlackBindingStatus:
    try:
        if not await run_in_threadpool(repository.is_organization_member, user_id, organization_id):
            raise HTTPException(status_code=403, detail="Organization membership required")
        return await run_in_threadpool(repository.get_organization_binding, organization_id)
    except SlackRepositoryError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.post(
    "/organizations/{organization_id}/channels/refresh",
    response_model=SlackChannelRefreshResponse,
)
async def refresh_organization_slack_channels(
    organization_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repository: Annotated[SlackRepository, Depends(get_slack_repository)],
    channel_service: Annotated[
        SlackChannelService,
        Depends(get_slack_channel_service),
    ],
    cache_invalidator: Annotated[
        SlackCacheInvalidator,
        Depends(get_slack_cache_invalidator),
    ],
) -> SlackChannelRefreshResponse:
    try:
        if not await run_in_threadpool(repository.is_organization_member, user_id, organization_id):
            raise HTTPException(status_code=403, detail="Organization membership required")
        await cache_invalidator.invalidate_organization(str(organization_id))
        return await channel_service.refresh_organization_channels(organization_id)
    except TokenEncryptionError as error:
        raise HTTPException(
            status_code=409,
            detail="Slack token cannot be read. Reconnect Slack once.",
        ) from error
    except SlackRepositoryError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/status", response_model=SlackConnectionStatus)
async def slack_connection_status(
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
    connection_service: Annotated[
        SlackConnectionService,
        Depends(get_slack_connection_service),
    ],
) -> SlackConnectionStatus:
    try:
        workspace_name = await connection_service.status(owner_id)
        return SlackConnectionStatus(
            connected=workspace_name is not None,
            workspace_name=workspace_name,
        )
    except (SlackConnectionError, SlackRepositoryError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_slack(
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
    connection_service: Annotated[
        SlackConnectionService,
        Depends(get_slack_connection_service),
    ],
) -> Response:
    try:
        await connection_service.disconnect(owner_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except (SlackConnectionError, SlackRepositoryError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
