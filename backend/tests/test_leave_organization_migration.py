from pathlib import Path
from unittest import TestCase


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607060018_leave_organization.sql"
)


class LeaveOrganizationMigrationTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_deletes_only_authenticated_users_membership(self) -> None:
        self.assertIn("function public.leave_organization", self.sql)
        self.assertIn("member.user_id = v_user_id", self.sql)
        self.assertIn("delete from public.organization_members", self.sql)

    def test_owner_cannot_leave(self) -> None:
        self.assertIn("if v_role = 'OWNER'", self.sql)
        self.assertIn("The organization owner cannot leave", self.sql)

    def test_only_authenticated_role_can_execute(self) -> None:
        self.assertIn("to authenticated", self.sql)
        self.assertIn("Authentication required", self.sql)
