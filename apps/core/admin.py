"""ثبت مدل‌های هسته در پنل مدیریت جنگو."""
from django.contrib import admin

from .models import AuditLog, Holiday, Notification, SystemSetting


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ("org_name", "site_name", "counting_mode", "updated_at")

    def has_add_permission(self, request):
        return not SystemSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "is_recurring_annual", "is_active")
    list_filter = ("is_recurring_annual", "is_active")
    search_fields = ("title", "note")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user_label", "action", "model_name", "object_label", "ip_address")
    list_filter = ("action", "model_name")
    search_fields = ("object_label", "user_label", "note")
    readonly_fields = [field.name for field in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "level", "is_read", "created_at")
    list_filter = ("level", "is_read")
    search_fields = ("title", "message")
