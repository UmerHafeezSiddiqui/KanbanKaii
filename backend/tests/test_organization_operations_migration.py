from pathlib import Path
from unittest import TestCase


MIGRATION = Path(__file__).parents[2] / "supabase" / "migrations" / "202607060013_organization_membership_operations.sql"


class OrganizationOperationsMigrationTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_defines_guarded_membership_operations(self) -> None:
        for name in (
            "create_organization_invite",
            "accept_organization_invite",
            "revoke_organization_invite",
            "change_organization_member_role",
            "remove_organization_member",
        ):
            self.assertIn(f"function public.{name}", self.sql)

    def test_invite_acceptance_uses_verified_jwt_email(self) -> None:
        self.assertIn("auth.jwt() ->> 'email'", self.sql)
        self.assertIn("is distinct from v_user_email", self.sql)
        self.assertIn("Invitation belongs to another email address", self.sql)

    def test_missing_membership_cannot_pass_null_role_checks(self) -> None:
        self.assertIn("coalesce(v_caller_role, '')", self.sql)
        self.assertIn("is distinct from 'OWNER'", self.sql)

    def test_team_lead_cannot_create_team_lead(self) -> None:
        self.assertIn("v_caller_role = 'TEAM_LEAD' and p_default_role = 'TEAM_LEAD'", self.sql)

    def test_owner_cannot_be_changed_or_removed(self) -> None:
        self.assertIn("Organization ownership cannot be changed here", self.sql)
        self.assertIn("The organization owner cannot be removed", self.sql)
