from pathlib import Path
from unittest import TestCase


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607070022_manager_only_board_creation.sql"
)


class ManagerOnlyBoardCreationMigrationTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_replaces_board_creation_function(self) -> None:
        self.assertIn("create or replace function public.create_organization_board", self.sql)
        self.assertIn("coalesce(v_role, '') <> 'OWNER'", self.sql)
        self.assertIn("Only an organization manager can create boards", self.sql)

    def test_keeps_creator_as_board_manager(self) -> None:
        self.assertIn("'MANAGER'", self.sql)
        self.assertIn("public.organization_board_members", self.sql)
