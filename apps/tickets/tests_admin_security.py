"""Ticket admin is read-only; workflow mutations must use application services."""
from django.contrib import admin
from django.test import RequestFactory, TestCase

from apps.accounts.models import User
from apps.tickets.admin import TicketAdmin, TicketPartInline, TicketPauseInline
from apps.tickets.models import Ticket, TicketPart, TicketPause


class TicketAdminWorkflowProtectionTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/admin/")
        self.request.user = User(is_superuser=True, is_staff=True, is_active=True)
        self.ticket_admin = TicketAdmin(Ticket, admin.site)
        self.part_inline = TicketPartInline(Ticket, admin.site)
        self.pause_inline = TicketPauseInline(Ticket, admin.site)

    def test_ticket_cannot_be_created_changed_or_deleted_in_admin(self):
        self.assertFalse(self.ticket_admin.has_add_permission(self.request))
        self.assertFalse(self.ticket_admin.has_change_permission(self.request))
        self.assertFalse(self.ticket_admin.has_delete_permission(self.request))
        self.assertEqual(set(self.ticket_admin.get_readonly_fields(self.request)), {f.name for f in Ticket._meta.fields})

    def test_ticket_part_and_pause_inlines_are_read_only(self):
        for inline, model in ((self.part_inline, TicketPart), (self.pause_inline, TicketPause)):
            self.assertFalse(inline.has_add_permission(self.request))
            self.assertFalse(inline.has_change_permission(self.request))
            self.assertFalse(inline.has_delete_permission(self.request))
            self.assertEqual(set(inline.get_readonly_fields(self.request)), {f.name for f in model._meta.fields})
