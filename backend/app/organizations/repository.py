from __future__ import annotations

import json
from typing import Any, NoReturn
from uuid import UUID

from postgrest.exceptions import APIError
from pydantic import ValidationError
from supabase import Client
from app.database.supabase_client import SupabaseConfigurationError, get_supabase_admin_client

from app.organizations.schemas import (
    AssignableRole,
    AssignableBoardRole,
    OrganizationBoardMemberResponse,
    OrganizationBoardSlackChannelResponse,
    OrganizationBoardResponse,
    OrganizationMemberResponse,
    OrganizationResponse,
)


class OrganizationRepositoryError(RuntimeError):
    pass


class OrganizationPermissionError(OrganizationRepositoryError):
    pass


class OrganizationConflictError(OrganizationRepositoryError):
    pass


class OrganizationNotFoundError(OrganizationRepositoryError):
    pass


class OrganizationInputError(OrganizationRepositoryError):
    pass


def _raise_database_error(error: APIError, fallback: str) -> NoReturn:
    if error.code == "42501":
        raise OrganizationPermissionError(error.message) from error
    if error.code == "23505":
        raise OrganizationConflictError("Organization data already exists") from error
    if error.code in {"22023", "23514"}:
        raise OrganizationInputError(error.message) from error
    raise OrganizationRepositoryError(fallback) from error


def _uuid_result(data: Any) -> UUID:
    value = data[0] if isinstance(data, list) and len(data) == 1 else data
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as error:
        raise OrganizationRepositoryError("Supabase returned an invalid identifier") from error


class OrganizationRepository:
    def __init__(self, client: Client) -> None:
        self.client = client

    def create(self, name: str, slug: str) -> OrganizationResponse:
        try:
            result = self.client.rpc(
                "create_organization", {"p_name": name, "p_slug": slug}
            ).execute()
        except APIError as error:
            _raise_database_error(error, "Supabase could not create the organization")
        return self.get(_uuid_result(result.data))

    def list(self) -> list[OrganizationResponse]:
        try:
            result = self.client.table("organizations").select("*").order("created_at").execute()
            return [
                OrganizationResponse.model_validate_json(json.dumps(row))
                for row in result.data
            ]
        except (APIError, ValidationError, TypeError) as error:
            raise OrganizationRepositoryError("Supabase could not load organizations") from error

    def get(self, organization_id: UUID) -> OrganizationResponse:
        try:
            result = self.client.table("organizations").select("*").eq("id", str(organization_id)).execute()
        except APIError as error:
            _raise_database_error(error, "Supabase could not load the organization")
        rows = result.data
        if not isinstance(rows, list) or len(rows) != 1:
            raise OrganizationNotFoundError("Organization was not found")
        try:
            return OrganizationResponse.model_validate_json(json.dumps(rows[0]))
        except ValidationError as error:
            raise OrganizationRepositoryError("Supabase returned an invalid organization") from error

    def delete(self, organization_id: UUID, confirmation_slug: str) -> None:
        try:
            self.client.rpc(
                "delete_organization",
                {
                    "p_organization_id": str(organization_id),
                    "p_confirmation_slug": confirmation_slug,
                },
            ).execute()
        except APIError as error:
            if error.code == "23503":
                raise OrganizationConflictError(
                    "Organization tickets must be resolved before deletion"
                ) from error
            _raise_database_error(error, "Supabase could not delete the organization")

    def list_members(self, organization_id: UUID) -> list[OrganizationMemberResponse]:
        try:
            result = self.client.rpc(
                "list_organization_members_with_profiles",
                {"p_organization_id": str(organization_id)},
            ).execute()
            return [
                OrganizationMemberResponse.model_validate_json(json.dumps(row))
                for row in result.data
            ]
        except (APIError, ValidationError, TypeError) as error:
            raise OrganizationRepositoryError("Supabase could not load organization members") from error

    def create_board(
        self,
        organization_id: UUID,
        name: str,
        slug: str,
    ) -> OrganizationBoardResponse:
        try:
            result = self.client.rpc(
                "create_organization_board",
                {
                    "p_organization_id": str(organization_id),
                    "p_name": name,
                    "p_slug": slug,
                },
            ).execute()
        except APIError as error:
            _raise_database_error(error, "Supabase could not create the board")
        board_id = _uuid_result(result.data)
        boards = [board for board in self.list_boards(organization_id) if board.id == board_id]
        if len(boards) != 1:
            raise OrganizationRepositoryError("Supabase did not return the board")
        return boards[0]

    def list_boards(self, organization_id: UUID) -> list[OrganizationBoardResponse]:
        try:
            result = (
                self.client.table("organization_boards")
                .select("*")
                .eq("organization_id", str(organization_id))
                .order("created_at", desc=True)
                .execute()
            )
            return [
                OrganizationBoardResponse.model_validate_json(json.dumps(row))
                for row in result.data
            ]
        except (APIError, ValidationError, TypeError) as error:
            raise OrganizationRepositoryError("Supabase could not load boards") from error

    def delete_board(self, organization_id: UUID, board_id: UUID) -> None:
        try:
            self.client.rpc(
                "delete_organization_board",
                {
                    "p_organization_id": str(organization_id),
                    "p_board_id": str(board_id),
                },
            ).execute()
        except APIError as error:
            _raise_database_error(error, "Supabase could not delete the board")

    def list_board_members(
        self,
        organization_id: UUID,
        board_id: UUID,
    ) -> list[OrganizationBoardMemberResponse]:
        try:
            result = self.client.rpc(
                "list_organization_board_members_with_profiles",
                {
                    "p_organization_id": str(organization_id),
                    "p_board_id": str(board_id),
                },
            ).execute()
            return [
                OrganizationBoardMemberResponse.model_validate_json(json.dumps(row))
                for row in result.data
            ]
        except (APIError, ValidationError, TypeError) as error:
            if isinstance(error, APIError):
                _raise_database_error(error, "Supabase could not load board members")
            raise OrganizationRepositoryError("Supabase could not load board members") from error

    def add_board_member(
        self,
        organization_id: UUID,
        board_id: UUID,
        user_id: UUID,
        role: AssignableBoardRole,
    ) -> OrganizationBoardMemberResponse:
        try:
            self.client.rpc(
                "upsert_organization_board_member",
                {
                    "p_organization_id": str(organization_id),
                    "p_board_id": str(board_id),
                    "p_user_id": str(user_id),
                    "p_role": role,
                },
            ).execute()
        except APIError as error:
            _raise_database_error(error, "Supabase could not save the board member")
        members = [
            member
            for member in self.list_board_members(organization_id, board_id)
            if member.user_id == user_id
        ]
        if len(members) != 1:
            raise OrganizationRepositoryError("Supabase did not return the board member")
        return members[0]

    def remove_board_member(
        self,
        organization_id: UUID,
        board_id: UUID,
        user_id: UUID,
    ) -> None:
        try:
            self.client.rpc(
                "remove_organization_board_member",
                {
                    "p_organization_id": str(organization_id),
                    "p_board_id": str(board_id),
                    "p_user_id": str(user_id),
                },
            ).execute()
        except APIError as error:
            _raise_database_error(error, "Supabase could not remove the board member")

    def list_board_slack_channels(
        self,
        organization_id: UUID,
        board_id: UUID,
    ) -> list[OrganizationBoardSlackChannelResponse]:
        try:
            result = (
                self.client.table("organization_board_slack_channels")
                .select("*")
                .eq("organization_id", str(organization_id))
                .eq("board_id", str(board_id))
                .order("created_at", desc=True)
                .execute()
            )
            return [
                OrganizationBoardSlackChannelResponse.model_validate_json(json.dumps(row))
                for row in result.data
            ]
        except (APIError, ValidationError, TypeError) as error:
            if isinstance(error, APIError):
                _raise_database_error(error, "Supabase could not load board Slack channels")
            raise OrganizationRepositoryError(
                "Supabase could not load board Slack channels"
            ) from error

    def add_board_slack_channel(
        self,
        organization_id: UUID,
        board_id: UUID,
        slack_team_id: str,
        slack_channel_id: str,
        slack_channel_name: str | None,
    ) -> OrganizationBoardSlackChannelResponse:
        try:
            self.client.rpc(
                "upsert_organization_board_slack_channel",
                {
                    "p_organization_id": str(organization_id),
                    "p_board_id": str(board_id),
                    "p_slack_team_id": slack_team_id,
                    "p_slack_channel_id": slack_channel_id,
                    "p_slack_channel_name": slack_channel_name or "",
                },
            ).execute()
        except APIError as error:
            _raise_database_error(error, "Supabase could not save the board Slack channel")
        channels = [
            channel
            for channel in self.list_board_slack_channels(organization_id, board_id)
            if channel.slack_team_id == slack_team_id
            and channel.slack_channel_id == slack_channel_id
        ]
        if len(channels) != 1:
            raise OrganizationRepositoryError(
                "Supabase did not return the board Slack channel"
            )
        return channels[0]

    def remove_board_slack_channel(
        self,
        organization_id: UUID,
        board_id: UUID,
        slack_team_id: str,
        slack_channel_id: str,
    ) -> None:
        try:
            self.client.rpc(
                "remove_organization_board_slack_channel",
                {
                    "p_organization_id": str(organization_id),
                    "p_board_id": str(board_id),
                    "p_slack_team_id": slack_team_id,
                    "p_slack_channel_id": slack_channel_id,
                },
            ).execute()
        except APIError as error:
            _raise_database_error(error, "Supabase could not remove the board Slack channel")

    def change_role(self, organization_id: UUID, user_id: UUID, role: AssignableRole) -> OrganizationMemberResponse:
        try:
            self.client.rpc("change_organization_member_role", {
                "p_organization_id": str(organization_id), "p_user_id": str(user_id), "p_role": role,
            }).execute()
        except APIError as error:
            _raise_database_error(error, "Supabase could not change the member role")
        members = [member for member in self.list_members(organization_id) if member.user_id == user_id]
        if len(members) != 1:
            raise OrganizationNotFoundError("Organization member was not found")
        return members[0]

    def remove_member(self, organization_id: UUID, user_id: UUID) -> None:
        try:
            self.client.rpc("remove_organization_member", {
                "p_organization_id": str(organization_id), "p_user_id": str(user_id),
            }).execute()
        except APIError as error:
            _raise_database_error(error, "Supabase could not remove the member")

    def leave(self, organization_id: UUID) -> None:
        try:
            self.client.rpc(
                "leave_organization",
                {"p_organization_id": str(organization_id)},
            ).execute()
        except APIError as error:
            _raise_database_error(error, "Supabase could not leave the organization")

    def ensure_invite_manager(self, organization_id: UUID, user_id: UUID) -> None:
        members = self.list_members(organization_id)
        current_member = next(
            (member for member in members if member.user_id == user_id),
            None,
        )
        if current_member is None:
            raise OrganizationPermissionError("Organization membership is required")
        if current_member.role not in {"OWNER", "TEAM_LEAD"}:
            raise OrganizationPermissionError(
                "Organization invitation is not permitted"
            )

    def accept_redis_invite(
        self,
        organization_id: UUID,
        default_role: AssignableRole,
        created_by: UUID,
        intended_email: str,
        user_id: UUID,
    ) -> UUID:
        try:
            result = get_supabase_admin_client().rpc(
                "accept_redis_organization_invitation",
                {
                    "p_organization_id": str(organization_id),
                    "p_default_role": default_role,
                    "p_created_by": str(created_by),
                    "p_intended_email": intended_email,
                    "p_user_id": str(user_id),
                },
            ).execute()
        except APIError as error:
            _raise_database_error(error, "Supabase could not accept the invitation")
        except SupabaseConfigurationError as error:
            raise OrganizationRepositoryError("Invitation acceptance is not configured") from error
        return _uuid_result(result.data)
