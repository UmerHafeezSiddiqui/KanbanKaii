from pathlib import Path
from unittest import TestCase


MIGRATION = Path(__file__).parents[2] / "supabase" / "migrations" / "202607060014_delete_organization.sql"


class DeleteOrganizationMigrationTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_requires_owner_and_exact_slug_confirmation(self) -> None:
        self.assertIn("is distinct from 'OWNER'", self.sql)
        self.assertIn("p_confirmation_slug", self.sql)
        self.assertIn("Organization confirmation did not match", self.sql)

    def test_only_authenticated_users_can_execute(self) -> None:
        self.assertIn("auth.uid() is null", self.sql)
        self.assertIn("to authenticated", self.sql)
