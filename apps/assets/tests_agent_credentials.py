from django.test import TestCase

from apps.assets.models import AgentCredential
from apps.org.models import Center, OrganizationalUnit


class AgentCredentialLifecycleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        national = OrganizationalUnit.objects.create(
            name="ستاد ایجنت", code="AGENT-NAT",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
        )
        province = OrganizationalUnit.objects.create(
            name="استان ایجنت", code="AGENT-PROV",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        county = OrganizationalUnit.objects.create(
            name="شهرستان ایجنت", code="AGENT-COUNTY",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=province,
        )
        cls.center = Center.objects.create(
            name="مرکز ایجنت", code="AGENT-CENTER", parent_unit=county
        )

    def test_raw_token_is_not_persisted_and_revocation_is_immediate(self):
        credential, raw_token = AgentCredential.generate(
            center=self.center, name="Test PC"
        )
        self.assertNotEqual(credential.token_hash, raw_token)
        self.assertEqual(AgentCredential.verify_token(raw_token).pk, credential.pk)

        credential.revoke("test revocation")
        self.assertIsNone(AgentCredential.verify_token(raw_token))
        credential.refresh_from_db()
        self.assertEqual(credential.status, AgentCredential.STATUS_REVOKED)
        self.assertEqual(credential.revocation_reason, "test revocation")

    def test_rotation_revokes_old_token_and_issues_new_token(self):
        credential, old_token = AgentCredential.generate(
            center=self.center, name="Test PC"
        )
        replacement, new_token = credential.rotate()

        credential.refresh_from_db()
        self.assertEqual(credential.status, AgentCredential.STATUS_REVOKED)
        self.assertIsNone(AgentCredential.verify_token(old_token))
        self.assertEqual(AgentCredential.verify_token(new_token).pk, replacement.pk)
        self.assertEqual(replacement.center_id, self.center.pk)
