"""ثبت مدل‌های درخواست خرابی در پنل مدیریت جنگو."""
from django.contrib import admin

from .models import Ticket, TicketAttachment, TicketEvent, TicketPart, TicketPause


class TicketEventInline(admin.TabularInline):
    model = TicketEvent
    extra = 0
    readonly_fields = ("event_type", "from_status", "to_status", "actor", "actor_label", "note", "at")
    can_delete = False


class TicketPartInline(admin.TabularInline):
    model = TicketPart
    extra = 0
    can_delete = False
    readonly_fields = [field.name for field in TicketPart._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class TicketPauseInline(admin.TabularInline):
    model = TicketPause
    extra = 0
    can_delete = False
    readonly_fields = [field.name for field in TicketPause._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "number", "asset", "title", "priority", "status",
        "assigned_contractor", "reported_at", "arrived_at", "resolved_declared_at",
    )
    list_filter = ("status", "priority", "failure_type", "assigned_contractor")
    search_fields = ("number", "title", "description", "asset__asset_tag")
    date_hierarchy = "reported_at"
    readonly_fields = [field.name for field in Ticket._meta.fields]
    inlines = [TicketEventInline, TicketPartInline, TicketPauseInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TicketEvent)
class TicketEventAdmin(admin.ModelAdmin):
    list_display = ("ticket", "event_type", "actor_label", "at")
    list_filter = ("event_type",)
    readonly_fields = [field.name for field in TicketEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TicketPause)
class TicketPauseAdmin(admin.ModelAdmin):
    list_display = ("ticket", "reason", "started_at", "ended_at", "created_by")
    list_filter = ("reason",)
    readonly_fields = [field.name for field in TicketPause._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "kind", "title", "uploaded_by", "created_at")
    list_filter = ("kind",)
    readonly_fields = [field.name for field in TicketAttachment._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
