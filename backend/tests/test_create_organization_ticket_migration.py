from pathlib import Path
from unittest import TestCase


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607060019_create_organization_ticket.sql"
)


class CreateOrganizationTicketMigrationTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_only_owner_or_team_lead_can_assign(self) -> None:
        self.assertIn("not in ('OWNER', 'TEAM_LEAD')", self.sql)
        self.assertIn("Only an organization owner or team lead", self.sql)

    def test_assignee_must_be_an_organization_member(self) -> None:
        self.assertIn("member.organization_id = p_organization_id", self.sql)
        self.assertIn("member.user_id = p_assignee_user_id", self.sql)
        self.assertIn("The assignee is not an organization member", self.sql)

    def test_server_derives_formal_assignment_identity(self) -> None:
        self.assertIn("'ORGANIZATION'", self.sql)
        self.assertIn("p_assignee_user_id", self.sql)
        self.assertIn("v_user_id", self.sql)
        self.assertIn("v_assignee_name", self.sql)

    def test_only_authenticated_users_can_execute(self) -> None:
        self.assertIn("to authenticated", self.sql)
        self.assertIn("Authentication required", self.sql)
