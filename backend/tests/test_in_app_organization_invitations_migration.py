from pathlib import Path
from unittest import TestCase


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202607060015_in_app_organization_invitations.sql"
)


class InAppOrganizationInvitationsMigrationTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_recipient_inbox_requires_confirmed_email(self) -> None:
        self.assertIn("function public.list_my_organization_invitations", self.sql)
        self.assertIn("email_confirmed_at is not null", self.sql)
        self.assertIn("invite.intended_email = v_email", self.sql)

    def test_acceptance_and_decline_are_bound_to_recipient(self) -> None:
        self.assertIn("function public.accept_organization_invitation_by_id", self.sql)
        self.assertIn("function public.decline_organization_invitation", self.sql)
        self.assertIn("Invitation belongs to another email address", self.sql)

    def test_duplicate_active_invites_and_existing_members_are_rejected(self) -> None:
        self.assertIn("A pending invitation already exists for this email", self.sql)
        self.assertIn("This user is already an organization member", self.sql)
        self.assertIn("pg_advisory_xact_lock", self.sql)

    def test_invitation_outcomes_cannot_overlap(self) -> None:
        self.assertIn("organization_invites_single_outcome_check", self.sql)
        self.assertIn("declined_at", self.sql)
        self.assertIn("declined_by", self.sql)
