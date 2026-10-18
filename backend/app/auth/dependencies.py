from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool
from supabase import Client
from supabase_auth.errors import AuthError

from app.database.supabase_client import (
    SupabaseConfigurationError,
    get_supabase_admin_client,
)


bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    email: str = Field(min_length=3, max_length=320)


def get_auth_client() -> Client:
    try:
        return get_supabase_admin_client()
    except SupabaseConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error


async def _verify_identity(
    credentials: HTTPAuthorizationCredentials | None,
    supabase: Client,
) -> tuple[UUID, dict[str, Any]]:
    """Verify shared token requirements without requiring an email claim."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = await run_in_threadpool(
            supabase.auth.get_claims,
            credentials.credentials,
        )
        if response is None:
            raise ValueError("Missing JWT claims")

        claims = response["claims"]
        if not isinstance(claims, dict):
            raise ValueError("Invalid JWT claims")
        if claims.get("role") != "authenticated":
            raise ValueError("JWT is not an authenticated user token")
        return UUID(str(claims["sub"])), claims
    except (AuthError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


async def get_current_user_id(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    supabase: Annotated[Client, Depends(get_auth_client)],
) -> UUID:
    """Verify a Supabase access token and return its user UUID claim."""
    user_id, _ = await _verify_identity(credentials, supabase)
    return user_id


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    supabase: Annotated[Client, Depends(get_auth_client)],
) -> AuthenticatedUser:
    """Verify a Supabase access token and return the user id plus email."""
    user_id, claims = await _verify_identity(credentials, supabase)
    try:
        return AuthenticatedUser(
            id=user_id,
            email=claims["email"],
        )
    except (AuthError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
