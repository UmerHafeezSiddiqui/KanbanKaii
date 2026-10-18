from pathlib import Path
from unittest import TestCase


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607060011_ticket_scope_foundation.sql"
)


class TicketScopeMigrationTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_adds_all_ticket_scopes(self) -> None:
        for scope in ("PRIVATE", "PERSONAL_ASSIGNMENT", "ORGANIZATION"):
            self.assertIn(f"'{scope}'", self.sql)

    def test_backfills_existing_owner_relationships(self) -> None:
        self.assertIn("set created_by = owner_id", self.sql)
        self.assertIn("assignee_user_id = owner_id", self.sql)
        self.assertIn("scope = 'PRIVATE'", self.sql)

    def test_adds_slack_source_deletion_identity(self) -> None:
        self.assertIn("source_team_id", self.sql)
        self.assertIn("source_channel_id", self.sql)
        self.assertIn("source_message_ts", self.sql)
        self.assertIn("source_message_state", self.sql)
        self.assertIn("source_message_deleted_at", self.sql)

    def test_does_not_replace_existing_owner_rls_during_foundation_phase(self) -> None:
        self.assertNotIn("drop policy", self.sql.lower())
        self.assertNotIn("create policy", self.sql.lower())
