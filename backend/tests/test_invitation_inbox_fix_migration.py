from pathlib import Path
from unittest import TestCase


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607060017_fix_invitation_inbox_ambiguity.sql"
)


class InvitationInboxFixMigrationTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_auth_user_columns_are_qualified(self) -> None:
        self.assertIn("lower(account.email)", self.sql)
        self.assertIn("account.id = v_user_id", self.sql)
        self.assertIn("account.email_confirmed_at", self.sql)
        self.assertNotIn("where id = v_user_id", self.sql)

    def test_reloads_postgrest_schema(self) -> None:
        self.assertIn("notify pgrst, 'reload schema'", self.sql)
