from pathlib import Path
from unittest import TestCase


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607070023_slack_channel_board_mapping.sql"
)


class SlackChannelBoardMappingMigrationTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_creates_slack_channel_mapping_table(self) -> None:
        self.assertIn("create table if not exists public.organization_board_slack_channels", self.sql)
        self.assertIn("slack_team_id text not null", self.sql)
        self.assertIn("slack_channel_id text not null", self.sql)
        self.assertIn("foreign key (board_id, organization_id)", self.sql)

    def test_channel_mapping_is_guarded_by_board_manager_permissions(self) -> None:
        self.assertIn("public.can_manage_organization_board", self.sql)
        self.assertIn("upsert_organization_board_slack_channel", self.sql)
        self.assertIn("remove_organization_board_slack_channel", self.sql)

    def test_channel_mapping_requires_connected_organization_workspace(self) -> None:
        self.assertIn("organization_slack_workspaces", self.sql)
        self.assertIn("Slack workspace is not connected to this organization", self.sql)
