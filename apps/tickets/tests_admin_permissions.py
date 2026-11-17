from django.contrib import admin
from django.test import SimpleTestCase

from apps.tickets.admin import TicketAttachmentAdmin, TicketPauseAdmin
from apps.tickets.models import TicketAttachment, TicketPause


class TicketAdminWorkflowProtectionTests(SimpleTestCase):
    def test_ticket_pause_admin_cannot_edit_sla_history(self):
        model_admin = TicketPauseAdmin(TicketPause, admin.site)

        self.assertFalse(model_admin.has_add_permission(None))
        self.assertFalse(model_admin.has_change_permission(None))
        self.assertFalse(model_admin.has_delete_permission(None))
        self.assertEqual(
            set(model_admin.readonly_fields),
            {field.name for field in TicketPause._meta.fields},
        )

    def test_ticket_attachment_admin_cannot_change_evidence(self):
        model_admin = TicketAttachmentAdmin(TicketAttachment, admin.site)

        self.assertFalse(model_admin.has_add_permission(None))
        self.assertFalse(model_admin.has_change_permission(None))
        self.assertFalse(model_admin.has_delete_permission(None))
        self.assertEqual(
            set(model_admin.readonly_fields),
            {field.name for field in TicketAttachment._meta.fields},
        )
