import json
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from postgrest.exceptions import APIError
from supabase import Client

from app.database.supabase_client import get_supabase_admin_client
from app.schemas.ticket import (
    OrganizationTicketCreate,
    TicketCreate,
    TicketResponse,
    TicketStatus,
    TicketUpdate,
)

OrganizationTicketView = str


class TicketRepositoryError(RuntimeError):
    """Raised when a ticket cannot be stored or read back safely."""


class TicketPermissionError(TicketRepositoryError):
    """Raised when RLS or a guarded database function denies an operation."""


class TicketRepository:
    """Store validated tickets in Supabase."""

    def __init__(self, client: Client | None = None) -> None:
        self.client = client or get_supabase_admin_client()

    def commit_slack_delivery(
        self, event_id: str, tickets: list[TicketResponse], results: list[dict[str, Any]],
    ) -> bool:
        try:
            response = self.client.rpc("commit_slack_ticket_batch", {
                "p_event_id": event_id,
                "p_tickets": [ticket.model_dump(mode="json") for ticket in tickets],
                "p_result": results,
            }).execute()
        except Exception as error:
            raise TicketRepositoryError("Supabase could not commit Slack tickets") from error
        if not isinstance(response.data, bool):
            raise TicketRepositoryError("Supabase returned an invalid Slack commit result")
        return response.data

    def create(self, ticket: TicketCreate) -> TicketResponse:
        """Insert one ticket and validate the row returned by Supabase."""
        payload = ticket.model_dump(mode="json")

        try:
            result = self.client.table("tickets").insert(payload).execute()
        except Exception as exc:
            raise TicketRepositoryError("Supabase could not create the ticket") from exc

        rows: Any = result.data
        if not isinstance(rows, list) or len(rows) != 1:
            raise TicketRepositoryError(
                "Supabase did not return exactly one created ticket"
            )

        return TicketRepository._parse_ticket(rows[0])

    def _list_rows(self, filters: list[tuple[str, str]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        while True:
            query = self.client.table("tickets").select("*", count="exact")
            for column, value in filters:
                query = query.eq(column, value)
            query = query.order("created_at", desc=True).order("id", desc=True)
            result = query.range(len(rows), len(rows) + 999).execute()
            if not isinstance(result.data, list) or not isinstance(result.count, int):
                raise TicketRepositoryError("Supabase returned an invalid ticket list")
            rows.extend(result.data)
            if len(rows) >= result.count:
                return rows
            if not result.data:
                raise TicketRepositoryError("Ticket list changed while loading; retry the request")

    def list_for_owner(
        self,
        owner_id: UUID,
        ticket_status: TicketStatus | None = None,
    ) -> list[TicketResponse]:
        """Return one owner's tickets, optionally filtered by status."""
        try:
            filters = [("owner_id", str(owner_id))]
            if ticket_status is not None:
                filters.append(("status", ticket_status))
            rows = self._list_rows(filters)
        except Exception as exc:
            raise TicketRepositoryError("Supabase could not load tickets") from exc
        return [self._parse_ticket(row) for row in rows]

    def list_for_organization(
        self,
        organization_id: UUID,
        ticket_status: TicketStatus | None = None,
        view: OrganizationTicketView = "overview",
        board_id: UUID | None = None,
    ) -> list[TicketResponse]:
        """Return organization-scoped tickets visible through the user's RLS policy."""
        try:
            filters = [("organization_id", str(organization_id)), ("scope", "ORGANIZATION")]
            if ticket_status is not None:
                filters.append(("status", ticket_status))
            if board_id is not None:
                filters.append(("board_id", str(board_id)))
            rows = self._list_rows(filters)
        except APIError as exc:
            if exc.code == "42501":
                raise TicketPermissionError(
                    "Organization ticket access is not permitted"
                ) from exc
            raise TicketRepositoryError(
                "Supabase could not load organization tickets"
            ) from exc
        except Exception as exc:
            raise TicketRepositoryError(
                "Supabase could not load organization tickets"
            ) from exc

        return [self._parse_ticket(row) for row in rows]

    def create_for_organization(
        self,
        organization_id: UUID,
        ticket: OrganizationTicketCreate,
    ) -> TicketResponse:
        """Create one guarded formal assignment through the database RPC."""
        try:
            result = self.client.rpc(
                "create_organization_ticket",
                {
                    "p_organization_id": str(organization_id),
                    "p_board_id": str(ticket.board_id) if ticket.board_id else None,
                    "p_assignee_user_id": str(ticket.assignee_user_id),
                    "p_title": ticket.title,
                    "p_description": ticket.description,
                    "p_priority": ticket.priority,
                    "p_status": ticket.status,
                },
            ).execute()
        except APIError as exc:
            if exc.code == "42501":
                raise TicketPermissionError(exc.message) from exc
            if exc.code in {"22023", "23514"}:
                raise TicketRepositoryError(exc.message) from exc
            raise TicketRepositoryError(
                "Supabase could not create the organization ticket"
            ) from exc
        except Exception as exc:
            raise TicketRepositoryError(
                "Supabase could not create the organization ticket"
            ) from exc
        return self._single_ticket(
            result.data,
            "Supabase did not return the created organization ticket",
        )

    def update_for_organization(
        self,
        organization_id: UUID,
        ticket_id: UUID,
        changes: TicketUpdate,
    ) -> TicketResponse:
        """Update an organization ticket when RLS grants lead-level management."""
        try:
            result = (
                self.client.table("tickets")
                .update(changes.model_dump(mode="json"))
                .eq("id", str(ticket_id))
                .eq("organization_id", str(organization_id))
                .eq("scope", "ORGANIZATION")
                .execute()
            )
        except APIError as exc:
            if exc.code == "42501":
                raise TicketPermissionError(
                    "Organization ticket management is not permitted"
                ) from exc
            raise TicketRepositoryError(
                "Supabase could not update the organization ticket"
            ) from exc
        except Exception as exc:
            raise TicketRepositoryError(
                "Supabase could not update the organization ticket"
            ) from exc
        return self._single_ticket(
            result.data,
            "Organization ticket was not found or management is not permitted",
        )

    def delete_for_organization(
        self,
        organization_id: UUID,
        ticket_id: UUID,
    ) -> None:
        """Delete an organization ticket when RLS grants lead-level management."""
        try:
            result = (
                self.client.table("tickets")
                .delete()
                .eq("id", str(ticket_id))
                .eq("organization_id", str(organization_id))
                .eq("scope", "ORGANIZATION")
                .execute()
            )
        except APIError as exc:
            if exc.code == "42501":
                raise TicketPermissionError(
                    "Organization ticket management is not permitted"
                ) from exc
            raise TicketRepositoryError(
                "Supabase could not delete the organization ticket"
            ) from exc
        except Exception as exc:
            raise TicketRepositoryError(
                "Supabase could not delete the organization ticket"
            ) from exc
        if not isinstance(result.data, list) or len(result.data) != 1:
            raise TicketPermissionError(
                "Organization ticket was not found or management is not permitted"
            )

    @staticmethod
    def _parse_ticket(row: Any) -> TicketResponse:
        try:
            return TicketResponse.model_validate_json(json.dumps(row))
        except ValidationError as exc:
            raise TicketRepositoryError(
                "Supabase returned an invalid ticket record"
            ) from exc

    @staticmethod
    def _single_ticket(rows: Any, empty_message: str) -> TicketResponse:
        if not isinstance(rows, list) or len(rows) != 1:
            raise TicketPermissionError(empty_message)
        return TicketRepository._parse_ticket(rows[0])

    def update_status(
        self,
        ticket_id: UUID,
        owner_id: UUID,
        new_status: TicketStatus,
    ) -> TicketResponse:
        """Use the RLS-aware status function for an authorized assignee."""
        try:
            result = (
                self.client.rpc(
                    "update_assigned_ticket_status",
                    {
                        "p_ticket_id": str(ticket_id),
                        "p_status": new_status,
                    },
                )
                .execute()
            )
        except APIError as exc:
            if exc.code == "42501":
                raise TicketPermissionError(
                    "Ticket status update is not permitted"
                ) from exc
            raise TicketRepositoryError(
                "Supabase could not update the ticket status"
            ) from exc
        except Exception as exc:
            raise TicketRepositoryError(
                "Supabase could not update the ticket status"
            ) from exc

        rows: Any = result.data
        if not isinstance(rows, list) or len(rows) != 1:
            raise TicketRepositoryError(
                "Ticket was not found or status update is not permitted"
            )

        return TicketRepository._parse_ticket(rows[0])

    def update(
        self,
        ticket_id: UUID,
        owner_id: UUID,
        changes: TicketUpdate,
    ) -> TicketResponse:
        """Update editable fields on one owner-scoped ticket."""
        try:
            result = (
                self.client.table("tickets")
                .update(changes.model_dump(mode="json"))
                .eq("id", str(ticket_id))
                .eq("owner_id", str(owner_id))
                .execute()
            )
        except Exception as exc:
            raise TicketRepositoryError("Supabase could not update the ticket") from exc

        rows: Any = result.data
        if not isinstance(rows, list) or len(rows) != 1:
            raise TicketRepositoryError("Ticket was not found for this owner")

        return TicketRepository._parse_ticket(rows[0])

    def delete(self, ticket_id: UUID, owner_id: UUID) -> None:
        """Delete a ticket only when it belongs to the given owner."""
        try:
            result = (
                self.client.table("tickets")
                .delete()
                .eq("id", str(ticket_id))
                .eq("owner_id", str(owner_id))
                .execute()
            )
        except Exception as exc:
            raise TicketRepositoryError("Supabase could not delete the ticket") from exc

        rows: Any = result.data
        if not isinstance(rows, list) or len(rows) != 1:
            raise TicketRepositoryError("Ticket was not found for this owner")
