"""Regression tests for HardwareSnapshot and SnapshotItem Django Admin guards."""

from django.contrib import admin
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.assets.admin import (
    AgentSyncAuditLogAdmin, HardwareSnapshotAdmin, SnapshotItemAdmin, SnapshotItemInline,
)
from apps.assets.models import (
    AgentSyncAuditLog, Asset, AssetCategory, ComponentType, HardwareSnapshot, SnapshotItem,
)
from apps.core.constants import SNAPSHOT_DRAFT, SNAPSHOT_LOCKED
from apps.org.models import Center, OrganizationalUnit


class HardwareSnapshotAdminProtectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        national = OrganizationalUnit.objects.create(
            name="Admin Snapshot National", code="ADM-SNAP-NAT",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
        )
        province = OrganizationalUnit.objects.create(
            name="Admin Snapshot Province", code="ADM-SNAP-PROV",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        county = OrganizationalUnit.objects.create(
            name="Admin Snapshot County", code="ADM-SNAP-COUNTY",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=province,
        )
        center = Center.objects.create(
            name="Admin Snapshot Center", code="ADM-SNAP-CENTER", parent_unit=county,
        )
        category = AssetCategory.objects.create(name="Admin Snapshot Asset")
        asset = Asset.objects.create(
            asset_tag="ADM-SNAP-ASSET-001", category=category, center=center,
        )
        cls.draft = HardwareSnapshot.objects.create(
            asset=asset, version=1, status=SNAPSHOT_DRAFT,
        )
        cls.locked = HardwareSnapshot.objects.create(
            asset=asset, version=2, status=SNAPSHOT_LOCKED,
        )
        component_type = ComponentType.objects.create(
            name="Admin Snapshot Component", code="ADM-SNAP-COMP",
        )
        cls.locked_item = SnapshotItem.objects.create(
            snapshot=cls.locked, component_type=component_type,
        )
        cls.draft_item = SnapshotItem.objects.create(
            snapshot=cls.draft, component_type=component_type,
        )
        cls.user = User.objects.create_superuser(
            username="snapshot-admin-guard",
            email="snapshot-admin-guard@example.invalid",
            password="Strong-Admin-Password-2026!",
        )

    def setUp(self):
        self.request = RequestFactory().get("/admin/")
        self.request.user = self.user
        self.snapshot_admin = HardwareSnapshotAdmin(HardwareSnapshot, admin.site)
        self.item_admin = SnapshotItemAdmin(SnapshotItem, admin.site)
        self.item_inline = SnapshotItemInline(HardwareSnapshot, admin.site)

    def test_snapshots_cannot_be_created_or_deleted_directly_in_admin(self):
        self.assertFalse(self.snapshot_admin.has_add_permission(self.request))
        self.assertFalse(self.snapshot_admin.has_delete_permission(self.request, self.draft))
        self.assertFalse(self.snapshot_admin.has_delete_permission(self.request, self.locked))

    def test_only_editable_snapshots_can_be_changed_in_admin(self):
        self.assertTrue(self.snapshot_admin.has_change_permission(self.request, self.draft))
        self.assertFalse(self.snapshot_admin.has_change_permission(self.request, self.locked))
        readonly = set(self.snapshot_admin.get_readonly_fields(self.request, self.draft))
        self.assertTrue({"asset", "version", "status", "locked_at"}.issubset(readonly))

    def test_snapshot_item_admin_only_allows_changes_for_editable_parent(self):
        self.assertFalse(self.item_admin.has_add_permission(self.request))
        self.assertTrue(self.item_admin.has_change_permission(self.request, self.draft_item))
        self.assertFalse(self.item_admin.has_change_permission(self.request, self.locked_item))
        self.assertIn("snapshot", self.item_admin.get_readonly_fields(self.request, self.draft_item))
        self.assertTrue(self.item_admin.has_delete_permission(self.request, self.draft_item))
        self.assertFalse(self.item_admin.has_delete_permission(self.request, self.locked_item))

    def test_snapshot_item_inline_is_disabled_for_locked_snapshot(self):
        self.assertTrue(self.item_inline.has_add_permission(self.request, self.draft))
        self.assertTrue(self.item_inline.has_change_permission(self.request, self.draft))
        self.assertTrue(self.item_inline.has_delete_permission(self.request, self.draft))
        self.assertFalse(self.item_inline.has_add_permission(self.request, self.locked))
        self.assertFalse(self.item_inline.has_change_permission(self.request, self.locked))
        self.assertFalse(self.item_inline.has_delete_permission(self.request, self.locked))



class AgentSyncAuditLogAdminProtectionTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/admin/")
        self.request.user = User.objects.create_superuser(
            username="agent-audit-admin-guard",
            email="agent-audit-admin-guard@example.invalid",
            password="Strong-Admin-Password-2026!",
        )
        self.audit_admin = AgentSyncAuditLogAdmin(AgentSyncAuditLog, admin.site)

    def test_agent_sync_audit_logs_are_append_only_in_admin(self):
        self.assertFalse(self.audit_admin.has_add_permission(self.request))
        self.assertFalse(self.audit_admin.has_change_permission(self.request))
        self.assertFalse(self.audit_admin.has_delete_permission(self.request))
        self.assertEqual(
            set(self.audit_admin.get_readonly_fields(self.request)),
            {field.name for field in AgentSyncAuditLog._meta.fields},
        )
