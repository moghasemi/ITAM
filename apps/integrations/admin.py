"""ثبت مدل‌های یکپارچه‌سازی در پنل مدیریت جنگو."""
from django.contrib import admin

from .models import ApiCallLog, OutboxDelivery, OutboxEvent, WebhookEndpoint


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "auth_type", "is_active", "last_success_at", "failure_count")
    list_filter = ("is_active", "auth_type")


@admin.register(OutboxEvent)
class OutboxEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "aggregate_type", "aggregate_id", "status", "attempts")
    list_filter = ("status", "event_type", "aggregate_type")
    search_fields = ("aggregate_id", "actor_label")
    readonly_fields = [field.name for field in OutboxEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ApiCallLog)
class ApiCallLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "endpoint", "method", "url", "response_status", "ok", "duration_ms")
    list_filter = ("ok", "response_status")
    readonly_fields = [field.name for field in ApiCallLog._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(OutboxDelivery)
class OutboxDeliveryAdmin(admin.ModelAdmin):
    list_display = ("event", "endpoint", "status", "attempts", "last_attempt_at", "dispatched_at")
    list_filter = ("status", "endpoint")
    search_fields = ("event__aggregate_id", "endpoint__name", "last_error")
    readonly_fields = [field.name for field in OutboxDelivery._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
