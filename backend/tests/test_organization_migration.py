from pathlib import Path
from unittest import TestCase


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607060010_organization_foundation.sql"
)


class OrganizationMigrationTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_defines_foundation_tables_and_roles(self) -> None:
        self.assertIn("create table public.organizations", self.sql)
        self.assertIn("create table public.organization_members", self.sql)
        self.assertIn("create table public.organization_invites", self.sql)
        for role in ("OWNER", "TEAM_LEAD", "MEMBER", "VIEWER"):
            self.assertIn(f"'{role}'", self.sql)

    def test_invitation_tokens_are_hashes_with_expiration(self) -> None:
        self.assertIn("token_hash text not null unique", self.sql)
        self.assertIn("token_hash ~ '^[a-f0-9]{64}$'", self.sql)
        self.assertIn("expires_at timestamptz not null", self.sql)
        self.assertNotIn("invite_token text", self.sql)

    def test_creation_is_atomic_and_assigns_owner(self) -> None:
        self.assertIn("function public.create_organization", self.sql)
        self.assertIn("'OWNER'", self.sql)
        self.assertIn("v_user_id uuid := auth.uid()", self.sql)

    def test_enables_rls_and_blocks_direct_membership_writes(self) -> None:
        self.assertIn(
            "alter table public.organization_members enable row level security",
            self.sql,
        )
        self.assertIn(
            "grant select on public.organization_members to authenticated",
            self.sql,
        )
        self.assertNotIn(
            "grant select, insert, update, delete on public.organization_members",
            self.sql,
        )
