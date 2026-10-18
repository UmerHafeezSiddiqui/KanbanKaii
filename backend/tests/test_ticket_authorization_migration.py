from pathlib import Path
from unittest import TestCase


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607060012_ticket_authorization.sql"
)


class TicketAuthorizationMigrationTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_private_personal_and_organization_visibility_are_distinct(self) -> None:
        self.assertIn("scope = 'PRIVATE'", self.sql)
        self.assertIn("scope = 'PERSONAL_ASSIGNMENT'", self.sql)
        self.assertIn("scope = 'ORGANIZATION'", self.sql)
        self.assertIn("public.is_organization_member", self.sql)

    def test_only_leadership_can_manage_organization_rows(self) -> None:
        self.assertIn("public.current_organization_role", self.sql)
        self.assertIn("in ('OWNER', 'TEAM_LEAD')", self.sql)

    def test_assignee_status_change_uses_narrow_rpc(self) -> None:
        self.assertIn("function public.update_assigned_ticket_status", self.sql)
        self.assertIn("v_ticket.assignee_user_id = v_user_id", self.sql)
        self.assertIn("if not coalesce((", self.sql)
        self.assertIn(
            "grant execute on function public.update_assigned_ticket_status",
            self.sql,
        )

    def test_relationship_columns_are_not_directly_updatable(self) -> None:
        self.assertIn("revoke update on public.tickets from authenticated", self.sql)
        self.assertIn(
            "grant update (title, description, priority, status, assignee)",
            self.sql,
        )
        self.assertNotIn("grant update (organization_id", self.sql)
