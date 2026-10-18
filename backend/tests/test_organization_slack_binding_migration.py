from pathlib import Path
from unittest import TestCase


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607060020_organization_slack_binding.sql"
)


class OrganizationSlackBindingMigrationTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_workspace_and_organization_are_uniquely_bound(self) -> None:
        self.assertIn("organization_id uuid primary key", self.sql)
        self.assertIn("slack_team_id text not null unique", self.sql)

    def test_only_kanbankaii_owner_can_be_recorded_as_verifier(self) -> None:
        self.assertIn("member.role = 'OWNER'", self.sql)
        self.assertIn("Only the KanbanKaii organization owner", self.sql)

    def test_members_can_view_binding_but_not_write_table(self) -> None:
        self.assertIn("Members can view organization Slack binding", self.sql)
        self.assertIn("grant select", self.sql)
        self.assertNotIn("grant insert", self.sql)
