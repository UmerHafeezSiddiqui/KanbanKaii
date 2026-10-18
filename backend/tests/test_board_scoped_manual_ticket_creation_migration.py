from pathlib import Path
from unittest import TestCase


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607070024_board_scoped_manual_ticket_creation.sql"
)


class BoardScopedManualTicketCreationMigrationTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_replaces_organization_ticket_function_with_board_id_parameter(self) -> None:
        self.assertIn("drop function if exists public.create_organization_ticket", self.sql)
        self.assertIn("p_board_id uuid", self.sql)
        self.assertIn("board_id,", self.sql)
        self.assertIn("p_board_id,", self.sql)

    def test_unboarded_ticket_still_allows_owner_or_team_lead(self) -> None:
        self.assertIn("p_board_id is null", self.sql)
        self.assertIn("not in ('OWNER', 'TEAM_LEAD')", self.sql)

    def test_board_ticket_requires_board_manager_permission(self) -> None:
        self.assertIn("public.can_manage_organization_board(p_organization_id, p_board_id)", self.sql)
        self.assertIn("Only an organization manager or board manager", self.sql)

    def test_board_ticket_assignee_must_be_board_member(self) -> None:
        self.assertIn("from public.organization_board_members board_member", self.sql)
        self.assertIn("Project-board tickets can only be assigned to board members", self.sql)
