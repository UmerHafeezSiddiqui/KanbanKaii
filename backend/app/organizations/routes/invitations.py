from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.redis.client import get_redis_client
from app.organizations.invite_store import (
    OrganizationInviteNotFoundError,
    OrganizationInviteStore,
    OrganizationInviteStoreError,
)
from app.organizations.repository import (
    OrganizationNotFoundError,
    OrganizationRepository,
    OrganizationRepositoryError,
)
from app.organizations.routes.common import (
    get_organization_repository,
    organization_http_error,
)
from app.organizations.schemas import (
    MyOrganizationInvitation,
    OrganizationInviteAccepted,
    OrganizationInviteCreate,
    OrganizationInviteCreated,
    OrganizationInviteResponse,
)
from app.organizations.service import RedisOrganizationInviteService


router = APIRouter()


def get_organization_invite_store() -> OrganizationInviteStore:
    return OrganizationInviteStore(get_redis_client())


def invite_store_http_error(error: OrganizationInviteStoreError) -> None:
    if isinstance(error, OrganizationInviteNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if "already exists" in str(error).lower():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error


@router.post("/invites/{token}/accept", response_model=OrganizationInviteAccepted)
async def accept_organization_invite(
    token: Annotated[str, Path(min_length=32, max_length=200)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[OrganizationRepository, Depends(get_organization_repository)],
    invite_store: Annotated[OrganizationInviteStore, Depends(get_organization_invite_store)],
) -> OrganizationInviteAccepted:
    try:
        token_hash = RedisOrganizationInviteService.hash_token(token)
        invite = await invite_store.get_by_token_hash(token_hash)
        if invite is None:
            raise OrganizationInviteNotFoundError(
                "Organization invitation is invalid or expired"
            )
        organization_id = await RedisOrganizationInviteService(
            repository,
            invite_store,
        ).accept_invite(invite, user)
        await invite_store.discard(invite, token_hash)
        return OrganizationInviteAccepted(organization_id=organization_id)
    except OrganizationInviteStoreError as error:
        invite_store_http_error(error)
    except OrganizationRepositoryError as error:
        organization_http_error(error)


@router.get("/invitations/pending", response_model=list[MyOrganizationInvitation])
async def list_my_organization_invitations(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    invite_store: Annotated[OrganizationInviteStore, Depends(get_organization_invite_store)],
) -> list[MyOrganizationInvitation]:
    try:
        return await invite_store.list_for_email(user.email)
    except OrganizationInviteStoreError as error:
        invite_store_http_error(error)


@router.post("/invitations/{invite_id}/accept", response_model=OrganizationInviteAccepted)
async def accept_in_app_organization_invitation(
    invite_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[OrganizationRepository, Depends(get_organization_repository)],
    invite_store: Annotated[OrganizationInviteStore, Depends(get_organization_invite_store)],
) -> OrganizationInviteAccepted:
    try:
        invite = await invite_store.get_by_id(invite_id)
        if invite is None:
            raise OrganizationInviteNotFoundError(
                "Organization invitation is invalid or expired"
            )
        if (invite.intended_email or "").lower() != user.email.lower():
            raise OrganizationInviteNotFoundError(
                "Organization invitation is invalid or expired"
            )
        organization_id = await RedisOrganizationInviteService(
            repository,
            invite_store,
        ).accept_invite(invite, user)
        await invite_store.discard(invite)
        return OrganizationInviteAccepted(organization_id=organization_id)
    except OrganizationInviteStoreError as error:
        invite_store_http_error(error)
    except OrganizationRepositoryError as error:
        organization_http_error(error)


@router.post("/invitations/{invite_id}/decline", status_code=204)
async def decline_in_app_organization_invitation(
    invite_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    invite_store: Annotated[OrganizationInviteStore, Depends(get_organization_invite_store)],
) -> Response:
    try:
        invite = await invite_store.get_by_id(invite_id)
        if invite is None or (invite.intended_email or "").lower() != user.email.lower():
            raise OrganizationInviteNotFoundError(
                "Organization invitation is invalid or expired"
            )
        await invite_store.delete(invite_id)
        return Response(status_code=204)
    except OrganizationInviteStoreError as error:
        invite_store_http_error(error)


@router.post("/{organization_id}/invites", response_model=OrganizationInviteCreated, status_code=201)
async def create_organization_invite(
    organization_id: UUID,
    request: OrganizationInviteCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[OrganizationRepository, Depends(get_organization_repository)],
    invite_store: Annotated[OrganizationInviteStore, Depends(get_organization_invite_store)],
) -> OrganizationInviteCreated:
    try:
        return await RedisOrganizationInviteService(
            repository,
            invite_store,
        ).create_invite(
            organization_id,
            request,
            user.id,
        )
    except OrganizationInviteStoreError as error:
        invite_store_http_error(error)
    except OrganizationRepositoryError as error:
        organization_http_error(error)


@router.get("/{organization_id}/invites", response_model=list[OrganizationInviteResponse])
async def list_organization_invites(
    organization_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[OrganizationRepository, Depends(get_organization_repository)],
    invite_store: Annotated[OrganizationInviteStore, Depends(get_organization_invite_store)],
) -> list[OrganizationInviteResponse]:
    try:
        await run_in_threadpool(repository.ensure_invite_manager, organization_id, user.id)
        return await invite_store.list_for_organization(organization_id)
    except OrganizationInviteStoreError as error:
        invite_store_http_error(error)
    except OrganizationRepositoryError as error:
        organization_http_error(error)


@router.delete("/{organization_id}/invites/{invite_id}", status_code=204)
async def revoke_organization_invite(
    organization_id: UUID,
    invite_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    repository: Annotated[OrganizationRepository, Depends(get_organization_repository)],
    invite_store: Annotated[OrganizationInviteStore, Depends(get_organization_invite_store)],
) -> Response:
    try:
        invite = await invite_store.get_by_id(invite_id)
        if invite is None or invite.organization_id != organization_id:
            raise OrganizationNotFoundError("Organization invitation was not found")
        members = await run_in_threadpool(repository.list_members, organization_id)
        current_member = next(
            (member for member in members if member.user_id == user.id),
            None,
        )
        if current_member is None or (
            current_member.role != "OWNER" and invite.created_by != user.id
        ):
            raise OrganizationNotFoundError("Organization invitation was not found")
        await invite_store.delete(invite_id)
        return Response(status_code=204)
    except OrganizationInviteStoreError as error:
        invite_store_http_error(error)
    except OrganizationRepositoryError as error:
        organization_http_error(error)
