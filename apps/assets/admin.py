"""ثبت مدل‌های دارایی در پنل مدیریت جنگو."""
from django.contrib import admin

from .models import Asset, AssetAttachment, AssetCategory, ComponentType, HardwareSnapshot, SnapshotItem, AgentCredential, AgentNonce, AgentSyncAuditLog


class SnapshotItemInline(admin.TabularInline):
    model = SnapshotItem
    extra = 0
    fields = ("component_type", "brand", "model_name", "serial_number", "capacity", "quantity", "slot", "condition")


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "requires_component_tracking", "is_active")
    list_filter = ("requires_component_tracking", "is_active")


@admin.register(ComponentType)
class ComponentTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_serialized", "is_key_item", "sort_order", "is_active")
    list_filter = ("is_serialized", "is_key_item", "is_active")


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("asset_tag", "title", "category", "brand", "serial_number", "department", "status")
    list_filter = ("category", "status", "department", "contract")
    search_fields = ("asset_tag", "title", "serial_number", "hostname", "ip_address")
    readonly_fields = ("qr_token", "current_snapshot", "baseline_locked_at")


@admin.register(HardwareSnapshot)
class HardwareSnapshotAdmin(admin.ModelAdmin):
    list_display = ("asset", "version", "status", "is_baseline", "diff_count", "recorded_by", "recorded_at")
    list_filter = ("status", "is_baseline")
    search_fields = ("asset__asset_tag", "seal_number")
    inlines = [SnapshotItemInline]
    readonly_fields = ("diff_data", "diff_count", "locked_at")


@admin.register(SnapshotItem)
class SnapshotItemAdmin(admin.ModelAdmin):
    list_display = ("snapshot", "component_type", "brand", "model_name", "serial_number", "condition")
    list_filter = ("component_type", "condition")
    search_fields = ("serial_number", "brand", "model_name")


@admin.register(AssetAttachment)
class AssetAttachmentAdmin(admin.ModelAdmin):
    list_display = ("asset", "kind", "title", "uploaded_by", "created_at")
    list_filter = ("kind",)

@admin.register(AgentCredential)
class AgentCredentialAdmin(admin.ModelAdmin):
    list_display = ("name", "center", "token_prefix", "status", "last_sync_at", "last_ip")
    list_filter = ("status", "center")
    search_fields = ("name", "hostname", "token_prefix")
    readonly_fields = ("token_hash", "token_prefix", "agent_uid", "last_sync_at", "last_ip")


@admin.register(AgentSyncAuditLog)
class AgentSyncAuditLogAdmin(admin.ModelAdmin):
    list_display = ("agent", "center", "remote_ip", "http_status", "success", "created_at")
    list_filter = ("success", "http_status", "center")
    search_fields = ("agent__name", "remote_ip", "rejection_reason")
    readonly_fields = ("created_at",)
