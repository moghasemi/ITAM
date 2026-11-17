from django.contrib import admin
from django.test import SimpleTestCase

from apps.assets.admin import AssetAdmin, AssetAttachmentAdmin
from apps.assets.models import Asset, AssetAttachment


class AssetAdminWorkflowProtectionTests(SimpleTestCase):
    def test_asset_admin_cannot_bypass_scoped_asset_views(self):
        model_admin = AssetAdmin(Asset, admin.site)

        self.assertFalse(model_admin.has_add_permission(None))
        self.assertFalse(model_admin.has_change_permission(None))
        self.assertFalse(model_admin.has_delete_permission(None))
        self.assertEqual(
            set(model_admin.readonly_fields),
            {field.name for field in Asset._meta.fields},
        )

    def test_asset_attachment_admin_preserves_evidence_workflow(self):
        model_admin = AssetAttachmentAdmin(AssetAttachment, admin.site)

        self.assertFalse(model_admin.has_add_permission(None))
        self.assertFalse(model_admin.has_change_permission(None))
        self.assertFalse(model_admin.has_delete_permission(None))
        self.assertEqual(
            set(model_admin.readonly_fields),
            {field.name for field in AssetAttachment._meta.fields},
        )
