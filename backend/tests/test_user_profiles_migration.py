from pathlib import Path
from unittest import TestCase


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607060016_user_profiles.sql"
)


class UserProfilesMigrationTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_creates_safe_public_profile_table(self) -> None:
        self.assertIn("create table public.user_profiles", self.sql)
        self.assertIn("display_name text not null", self.sql)
        self.assertIn("avatar_url text", self.sql)

    def test_syncs_signup_and_profile_metadata(self) -> None:
        self.assertIn("function public.sync_user_profile_from_auth", self.sql)
        self.assertIn("after insert or update of raw_user_meta_data", self.sql)
        self.assertIn("account.raw_user_meta_data", self.sql)

    def test_profile_visibility_requires_shared_organization(self) -> None:
        self.assertIn("function public.can_view_user_profile", self.sql)
        self.assertIn("target.organization_id = viewer.organization_id", self.sql)
        self.assertIn("public.can_view_user_profile(user_id)", self.sql)

    def test_member_rpc_returns_profile_fields(self) -> None:
        self.assertIn("function public.list_organization_members_with_profiles", self.sql)
        self.assertIn("profile.display_name", self.sql)
        self.assertIn("profile.job_title", self.sql)
        self.assertIn("profile.avatar_url", self.sql)
