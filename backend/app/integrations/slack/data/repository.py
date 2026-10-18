from datetime import datetime
from typing import Any
from uuid import UUID
from dataclasses import dataclass

from supabase import Client
from app.integrations.slack.schemas import (
    OrganizationSlackBindingStatus,
    SlackQueuedDelivery,
    SlackStoredInstallation,
)


class SlackRepositoryError(RuntimeError):
    """Raised when Slack integration state cannot be persisted."""


@dataclass(frozen=True)
class SlackMentionTarget:
    owner_id: UUID
    slack_user_id: str


@dataclass(frozen=True)
class SlackConnectedUser:
    owner_id: UUID
    slack_user_id: str


@dataclass(frozen=True)
class SlackOrganizationAssignmentContext:
    organization_id: UUID
    assigner_role: str
    assignee_role: str


@dataclass(frozen=True)
class SlackBoardChannelBinding:
    organization_id: UUID
    board_id: UUID
    slack_team_id: str
    slack_channel_id: str


@dataclass(frozen=True)
class SlackOrganizationWorkspaceBinding:
    organization_id: UUID
    verified_by_user_id: UUID
    slack_team_id: str
    workspace_name: str


@dataclass(frozen=True)
class SlackMappedChannel:
    organization_id: UUID
    board_id: UUID
    slack_team_id: str
    slack_channel_id: str
    slack_channel_name: str | None


class SlackRepository:
    def __init__(self, client: Client) -> None:
        self.client = client

    def save_installation(
        self,
        owner_id: UUID,
        team_id: str,
        team_name: str,
        bot_user_id: str,
        slack_user_id: str,
        token_ciphertext: str,
        scopes: list[str],
    ) -> None:
        try:
            result = self.client.rpc(
                "upsert_slack_integration",
                {
                    "p_owner_id": str(owner_id),
                    "p_team_id": team_id,
                    "p_team_name": team_name,
                    "p_bot_user_id": bot_user_id,
                    "p_slack_user_id": slack_user_id,
                    "p_token_ciphertext": token_ciphertext,
                    "p_scopes": scopes,
                },
            ).execute()
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not save the Slack installation"
            ) from exc

        if result.data is None:
            raise SlackRepositoryError(
                "Supabase did not confirm the Slack installation"
            )

    def is_organization_owner(self, owner_id: UUID, organization_id: UUID) -> bool:
        try:
            result = (
                self.client.table("organization_members")
                .select("user_id")
                .eq("organization_id", str(organization_id))
                .eq("user_id", str(owner_id))
                .eq("role", "OWNER")
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not verify the organization owner"
            ) from exc
        return isinstance(result.data, list) and len(result.data) == 1

    def is_organization_member(self, user_id: UUID, organization_id: UUID) -> bool:
        try:
            result = (
                self.client.table("organization_members")
                .select("user_id")
                .eq("organization_id", str(organization_id))
                .eq("user_id", str(user_id))
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not verify organization membership"
            ) from exc
        return isinstance(result.data, list) and len(result.data) == 1

    def bind_organization_workspace(
        self,
        organization_id: UUID,
        owner_id: UUID,
        team_id: str,
        workspace_name: str,
        slack_user_id: str,
        is_primary_owner: bool,
    ) -> None:
        try:
            self.client.rpc(
                "bind_organization_slack_workspace",
                {
                    "p_organization_id": str(organization_id),
                    "p_owner_id": str(owner_id),
                    "p_slack_team_id": team_id,
                    "p_workspace_name": workspace_name,
                    "p_slack_user_id": slack_user_id,
                    "p_is_primary_owner": is_primary_owner,
                },
            ).execute()
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not bind the Slack workspace"
            ) from exc

    def get_organization_binding(
        self,
        organization_id: UUID,
    ) -> OrganizationSlackBindingStatus:
        try:
            result = (
                self.client.table("organization_slack_workspaces")
                .select("slack_team_id,workspace_name,verified_at")
                .eq("organization_id", str(organization_id))
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not load the organization Slack binding"
            ) from exc
        rows = result.data
        if not isinstance(rows, list) or not rows:
            return OrganizationSlackBindingStatus(connected=False)
        return OrganizationSlackBindingStatus(
            connected=True,
            workspace_name=rows[0].get("workspace_name"),
            slack_team_id=rows[0].get("slack_team_id"),
            verified_at=rows[0].get("verified_at"),
        )

    def get_organization_workspace_binding(
        self,
        organization_id: UUID,
    ) -> SlackOrganizationWorkspaceBinding | None:
        try:
            result = (
                self.client.table("organization_slack_workspaces")
                .select("organization_id,verified_by_user_id,slack_team_id,workspace_name")
                .eq("organization_id", str(organization_id))
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not load the organization Slack workspace"
            ) from exc

        rows: Any = result.data
        if not isinstance(rows, list):
            raise SlackRepositoryError(
                "Supabase returned an invalid Slack workspace binding"
            )
        if not rows:
            return None
        try:
            row = rows[0]
            return SlackOrganizationWorkspaceBinding(
                organization_id=UUID(str(row["organization_id"])),
                verified_by_user_id=UUID(str(row["verified_by_user_id"])),
                slack_team_id=str(row["slack_team_id"]),
                workspace_name=str(row["workspace_name"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SlackRepositoryError(
                "Supabase returned an invalid Slack workspace binding"
            ) from exc


    def get_installation(self, owner_id: UUID) -> SlackStoredInstallation | None:
        try:
            integration_result = (
                self.client.table("integrations")
                .select("id,display_name")
                .eq("owner_id", str(owner_id))
                .eq("provider", "SLACK")
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not load the Slack installation"
            ) from exc

        rows: Any = integration_result.data
        if not isinstance(rows, list):
            raise SlackRepositoryError("Supabase returned an invalid Slack installation")
        if not rows:
            return None

        integration_id = rows[0].get("id")
        workspace_name = rows[0].get("display_name")
        if not isinstance(integration_id, str) or not isinstance(workspace_name, str):
            raise SlackRepositoryError("Supabase returned an invalid Slack installation")

        try:
            credential_result = (
                self.client.table("integration_credentials")
                .select("access_token_ciphertext")
                .eq("integration_id", integration_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not load Slack credentials"
            ) from exc

        credentials: Any = credential_result.data
        if not isinstance(credentials, list) or len(credentials) != 1:
            raise SlackRepositoryError("Slack credentials were not found")
        ciphertext = credentials[0].get("access_token_ciphertext")
        if not isinstance(ciphertext, str) or not ciphertext:
            raise SlackRepositoryError("Supabase returned invalid Slack credentials")
        return SlackStoredInstallation(
            integration_id=integration_id,
            workspace_name=workspace_name,
            token_ciphertext=ciphertext,
        )

    def delete_owner_installation(self, owner_id: UUID) -> None:
        try:
            result = (
                self.client.table("integrations")
                .delete()
                .eq("owner_id", str(owner_id))
                .eq("provider", "SLACK")
                .execute()
            )
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not remove the Slack installation"
            ) from exc
        if not isinstance(result.data, list):
            raise SlackRepositoryError("Supabase returned an invalid delete result")

    def delete_team_installations(self, team_id: str) -> None:
        try:
            result = (
                self.client.table("integrations")
                .delete()
                .eq("provider", "SLACK")
                .eq("external_account_id", team_id)
                .execute()
            )
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not remove uninstalled Slack connections"
            ) from exc
        if not isinstance(result.data, list):
            raise SlackRepositoryError("Supabase returned an invalid delete result")

    def delete_revoked_installations(
        self,
        team_id: str,
        revoked_user_ids: list[str],
        bot_token_revoked: bool,
    ) -> None:
        if bot_token_revoked:
            self.delete_team_installations(team_id)
            return
        if not revoked_user_ids:
            return
        try:
            result = (
                self.client.table("integrations")
                .select("id,metadata")
                .eq("provider", "SLACK")
                .eq("external_account_id", team_id)
                .execute()
            )
            rows: Any = result.data
            if not isinstance(rows, list):
                raise SlackRepositoryError("Supabase returned invalid Slack integrations")
            for row in rows:
                metadata = row.get("metadata")
                if (
                    isinstance(metadata, dict)
                    and metadata.get("slack_user_id") in revoked_user_ids
                    and isinstance(row.get("id"), str)
                ):
                    self.client.table("integrations").delete().eq(
                        "id", row["id"]
                    ).execute()
        except SlackRepositoryError:
            raise
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not remove revoked Slack connections"
            ) from exc

    def claim_webhook_delivery(
        self,
        event_id: str,
        payload: dict[str, Any],
    ) -> bool:
        """Atomically store an event once; return False for a duplicate."""
        try:
            result = self.client.rpc(
                "claim_slack_webhook_delivery",
                {
                    "p_event_id": event_id,
                    "p_payload": payload,
                },
            ).execute()
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not record the Slack event"
            ) from exc

        if not isinstance(result.data, bool):
            raise SlackRepositoryError(
                "Supabase returned an invalid Slack event claim"
            )
        return result.data

    def list_stale_deliveries(self, before: str) -> list[str]:
        try:
            result = (self.client.table("webhook_deliveries")
                      .select("external_event_id").eq("provider", "SLACK")
                      .in_("status", ["RECEIVED", "PROCESSING"])
                      .is_("tickets_committed_at", "null").lt("received_at", before)
                      .order("received_at").limit(100).execute())
            return [row["external_event_id"] for row in result.data]
        except Exception as error:
            raise SlackRepositoryError("Supabase could not load stale Slack deliveries") from error

    def get_webhook_delivery(self, event_id: str) -> SlackQueuedDelivery:
        try:
            result = (
                self.client.table("webhook_deliveries")
                .select("status,payload")
                .eq("provider", "SLACK")
                .eq("external_event_id", event_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not load the queued Slack event"
            ) from exc

        rows: Any = result.data
        if not isinstance(rows, list) or len(rows) != 1:
            raise SlackRepositoryError("Queued Slack event was not found")
        try:
            return SlackQueuedDelivery.model_validate(rows[0])
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase returned an invalid queued Slack event"
            ) from exc

    def find_mentioned_targets(
        self,
        team_id: str,
        text: str,
    ) -> list[SlackMentionTarget]:
        """Return connected users from this workspace who are mentioned in text."""
        try:
            result = (
                self.client.table("integrations")
                .select("owner_id,metadata")
                .eq("provider", "SLACK")
                .eq("external_account_id", team_id)
                .execute()
            )
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not resolve Slack mention owners"
            ) from exc

        rows: Any = result.data
        if not isinstance(rows, list):
            raise SlackRepositoryError("Supabase returned invalid Slack integrations")

        targets: list[SlackMentionTarget] = []
        for row in rows:
            metadata = row.get("metadata")
            slack_user_id = metadata.get("slack_user_id") if isinstance(metadata, dict) else None
            if not isinstance(slack_user_id, str) or f"<@{slack_user_id}>" not in text:
                continue
            try:
                targets.append(
                    SlackMentionTarget(
                        owner_id=UUID(str(row["owner_id"])),
                        slack_user_id=slack_user_id,
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise SlackRepositoryError(
                    "Supabase returned an invalid Slack mention owner"
                ) from exc
        return targets

    def find_connected_user(
        self,
        team_id: str,
        slack_user_id: str,
    ) -> SlackConnectedUser | None:
        """Return the Kanban user connected to this Slack identity, if any."""
        try:
            result = (
                self.client.table("integrations")
                .select("owner_id,metadata")
                .eq("provider", "SLACK")
                .eq("external_account_id", team_id)
                .execute()
            )
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not resolve the Slack sender"
            ) from exc

        rows: Any = result.data
        if not isinstance(rows, list):
            raise SlackRepositoryError("Supabase returned invalid Slack integrations")

        for row in rows:
            metadata = row.get("metadata")
            connected_slack_user_id = (
                metadata.get("slack_user_id") if isinstance(metadata, dict) else None
            )
            if connected_slack_user_id != slack_user_id:
                continue
            try:
                return SlackConnectedUser(
                    owner_id=UUID(str(row["owner_id"])),
                    slack_user_id=connected_slack_user_id,
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise SlackRepositoryError(
                    "Supabase returned an invalid Slack connected user"
                ) from exc
        return None

    def find_organization_assignment_context(
        self,
        team_id: str,
        assigner_user_id: UUID,
        assignee_user_id: UUID,
    ) -> SlackOrganizationAssignmentContext | None:
        """Return shared org membership for a Slack assignment in this workspace."""
        try:
            binding_result = (
                self.client.table("organization_slack_workspaces")
                .select("organization_id")
                .eq("slack_team_id", team_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not resolve the Slack organization binding"
            ) from exc

        bindings: Any = binding_result.data
        if not isinstance(bindings, list):
            raise SlackRepositoryError(
                "Supabase returned an invalid Slack organization binding"
            )
        if not bindings:
            return None

        try:
            organization_id = UUID(str(bindings[0]["organization_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise SlackRepositoryError(
                "Supabase returned an invalid Slack organization binding"
            ) from exc

        try:
            members_result = (
                self.client.table("organization_members")
                .select("user_id,role")
                .eq("organization_id", str(organization_id))
                .execute()
            )
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not resolve organization Slack members"
            ) from exc

        members: Any = members_result.data
        if not isinstance(members, list):
            raise SlackRepositoryError(
                "Supabase returned invalid organization Slack members"
            )

        roles: dict[UUID, str] = {}
        for member in members:
            try:
                roles[UUID(str(member["user_id"]))] = str(member["role"])
            except (KeyError, TypeError, ValueError) as exc:
                raise SlackRepositoryError(
                    "Supabase returned an invalid organization member"
                ) from exc

        assigner_role = roles.get(assigner_user_id)
        assignee_role = roles.get(assignee_user_id)
        if assigner_role is None or assignee_role is None:
            return None
        return SlackOrganizationAssignmentContext(
            organization_id=organization_id,
            assigner_role=assigner_role,
            assignee_role=assignee_role,
        )

    def find_board_channel_binding(
        self,
        organization_id: UUID,
        team_id: str,
        channel_id: str | None,
    ) -> SlackBoardChannelBinding | None:
        """Return a project board mapped to this Slack channel, if configured."""
        if not channel_id:
            return None
        try:
            result = (
                self.client.table("organization_board_slack_channels")
                .select("organization_id,board_id,slack_team_id,slack_channel_id")
                .eq("organization_id", str(organization_id))
                .eq("slack_team_id", team_id)
                .eq("slack_channel_id", channel_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not resolve the Slack board channel mapping"
            ) from exc

        rows: Any = result.data
        if not isinstance(rows, list):
            raise SlackRepositoryError(
                "Supabase returned an invalid Slack board channel mapping"
            )
        if not rows:
            return None
        try:
            row = rows[0]
            return SlackBoardChannelBinding(
                organization_id=UUID(str(row["organization_id"])),
                board_id=UUID(str(row["board_id"])),
                slack_team_id=str(row["slack_team_id"]),
                slack_channel_id=str(row["slack_channel_id"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SlackRepositoryError(
                "Supabase returned an invalid Slack board channel mapping"
            ) from exc

    def list_organization_mapped_channels(
        self,
        organization_id: UUID,
    ) -> list[SlackMappedChannel]:
        try:
            result = (
                self.client.table("organization_board_slack_channels")
                .select(
                    "organization_id,board_id,slack_team_id,slack_channel_id,slack_channel_name"
                )
                .eq("organization_id", str(organization_id))
                .execute()
            )
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not load organization Slack channel mappings"
            ) from exc

        rows: Any = result.data
        if not isinstance(rows, list):
            raise SlackRepositoryError(
                "Supabase returned invalid organization Slack channel mappings"
            )
        channels: list[SlackMappedChannel] = []
        for row in rows:
            try:
                channel_name = row.get("slack_channel_name")
                channels.append(
                    SlackMappedChannel(
                        organization_id=UUID(str(row["organization_id"])),
                        board_id=UUID(str(row["board_id"])),
                        slack_team_id=str(row["slack_team_id"]),
                        slack_channel_id=str(row["slack_channel_id"]),
                        slack_channel_name=channel_name
                        if isinstance(channel_name, str) and channel_name
                        else None,
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise SlackRepositoryError(
                    "Supabase returned an invalid organization Slack channel mapping"
                ) from exc
        return channels

    def update_board_channel_display_name(
        self,
        organization_id: UUID,
        board_id: UUID,
        slack_team_id: str,
        slack_channel_id: str,
        slack_channel_name: str,
    ) -> None:
        try:
            self.client.table("organization_board_slack_channels").update(
                {"slack_channel_name": slack_channel_name}
            ).eq("organization_id", str(organization_id)).eq(
                "board_id", str(board_id)
            ).eq(
                "slack_team_id", slack_team_id
            ).eq(
                "slack_channel_id", slack_channel_id
            ).execute()
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not update the Slack channel display name"
            ) from exc

    def update_webhook_delivery(
        self,
        event_id: str,
        delivery_status: str,
        error: str | None = None,
        outcome: str | None = None,
        result: list[dict[str, Any]] | None = None,
    ) -> None:
        payload = {
            "status": delivery_status,
            "error": error,
            "outcome": outcome,
            "result": result,
            "processed_at": datetime.now().astimezone().isoformat()
            if delivery_status in {"COMPLETED", "FAILED"}
            else None,
        }
        try:
            result = (
                self.client.table("webhook_deliveries")
                .update(payload)
                .eq("provider", "SLACK")
                .eq("external_event_id", event_id)
                .is_("tickets_committed_at", "null")
                .execute()
            )
        except Exception as exc:
            raise SlackRepositoryError(
                "Supabase could not update the Slack event"
            ) from exc

        if not isinstance(result.data, list) or len(result.data) > 1:
            raise SlackRepositoryError("Slack event delivery was not found")
        if not result.data:
            self.get_webhook_delivery(event_id)
