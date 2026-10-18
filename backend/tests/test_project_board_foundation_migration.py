from pathlib import Path
from unittest import TestCase


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607070021_project_board_foundation.sql"
)


class ProjectBoardFoundationMigrationTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_creates_board_tables_and_roles(self) -> None:
        self.assertIn("create table public.organization_boards", self.sql)
        self.assertIn("create table public.organization_board_members", self.sql)
        for role in ("MANAGER", "MEMBER", "VIEWER"):
            self.assertIn(f"'{role}'", self.sql)

    def test_tickets_can_be_scoped_to_a_board(self) -> None:
        self.assertIn("add column board_id uuid", self.sql)
        self.assertIn("tickets_board_organization_fk", self.sql)
        self.assertIn("tickets_board_scope_check", self.sql)

    def test_board_membership_limits_board_ticket_visibility(self) -> None:
        self.assertIn("public.is_organization_board_member(board_id)", self.sql)
        self.assertIn("scope = 'ORGANIZATION'", self.sql)
        self.assertIn("board_id is not null", self.sql)

    def test_board_mutations_are_guarded_by_rpc(self) -> None:
        self.assertIn("function public.create_organization_board", self.sql)
        self.assertIn("function public.upsert_organization_board_member", self.sql)
        self.assertIn("function public.delete_organization_board", self.sql)
        self.assertIn("Only an organization owner or board manager", self.sql)

    def test_only_organization_manager_can_create_boards(self) -> None:
        self.assertIn("coalesce(v_role, '') <> 'OWNER'", self.sql)
        self.assertIn("Only an organization manager can create boards", self.sql)
        self.assertNotIn("not in ('OWNER', 'TEAM_LEAD')", self.sql)
