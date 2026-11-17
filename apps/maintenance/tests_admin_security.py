"""Maintenance visit admin is read-only; workflow mutations use application services."""
from django.contrib import admin
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.maintenance.admin import MaintenanceVisitAdmin, VisitAssetCheckAdmin, VisitAssetCheckInline
from apps.maintenance.models import MaintenanceVisit, VisitAssetCheck


class MaintenanceVisitAdminWorkflowProtectionTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/admin/")
        self.request.user = User(is_superuser=True, is_staff=True, is_active=True)
        self.visit_admin = MaintenanceVisitAdmin(MaintenanceVisit, admin.site)
        self.check_admin = VisitAssetCheckAdmin(VisitAssetCheck, admin.site)
        self.check_inline = VisitAssetCheckInline(MaintenanceVisit, admin.site)

    def test_visit_admin_is_read_only(self):
        self.assertFalse(self.visit_admin.has_add_permission(self.request))
        self.assertFalse(self.visit_admin.has_change_permission(self.request))
        self.assertFalse(self.visit_admin.has_delete_permission(self.request))
        self.assertEqual(set(self.visit_admin.get_readonly_fields(self.request)), {f.name for f in MaintenanceVisit._meta.fields})

    def test_visit_asset_check_admin_and_inline_are_read_only(self):
        self.assertFalse(self.check_admin.has_add_permission(self.request))
        self.assertFalse(self.check_admin.has_change_permission(self.request))
        self.assertFalse(self.check_admin.has_delete_permission(self.request))
        self.assertFalse(self.check_inline.has_add_permission(self.request))
        self.assertFalse(self.check_inline.has_change_permission(self.request))
        self.assertFalse(self.check_inline.has_delete_permission(self.request))
        self.assertEqual(set(self.check_inline.get_readonly_fields(self.request)), {f.name for f in VisitAssetCheck._meta.fields})
