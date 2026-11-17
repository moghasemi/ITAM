""""ثبت مدل‌های دارایی در پنل مدیریت جنگو."""
from django import forms
from django.contrib import admin, messages

from apps.core.utils import log_action

from .models import Asset, AssetAttachment, AssetCategory, AssetRelationship, ComponentType, HardwareSnapshot, SnapshotItem, AgentCredential, AgentNonce, AgentSyncAuditLog


class SnapshotItemInline(admin.TabularInline):
    model = SnapshotItem
    extra = 0
    fields = ("component_type", "brand", "model_name", "serial_number", "capacity", "quantity", "slot", "condition")

    def has_add_permission(self, request, obj=None):
        return bool(obj and obj.is_editable and super().has_add_permission(request, obj))

    def has_change_permission(self, request, obj=None):
        return bool(obj and obj.is_editable and super().has_change_permission(request, obj))

    def has_delete_permission(self, request, obj=None):
        return bool(obj and obj.is_editable and super().has_delete_permission(request, obj))


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "requires_component_tracking", "is_computing_device", "is_active")
    list_filter = ("requires_component_tracking", "is_computing_device", "is_active")


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
    # Workflow state and snapshot identity are controlled only by domain services.
    readonly_fields = (
        "asset", "version", "status", "is_baseline", "previous", "is_from_hwagent",
        "agent_hashes", "recorded_by", "recorded_at", "technician_confirmed_by",
        "technician_confirmed_at", "it_confirmed_by", "it_confirmed_at",
        "locked_at", "diff_data", "diff_count",
    )

    def has_add_permission(self, request):
        # Snapshots must be created through the application workflow, not Django Admin.
        return False

    def has_change_permission(self, request, obj=None):
        if obj is not None and not obj.is_editable:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Preserve the audit trail and prevent deletion outside the workflow.
        return False


@admin.register(SnapshotItem)
class SnapshotItemAdmin(admin.ModelAdmin):
    list_display = ("snapshot", "component_type", "brand", "model_name", "serial_number", "condition")
    list_filter = ("component_type", "condition")
    search_fields = ("serial_number", "brand", "model_name")
    # Prevent moving an item from an editable snapshot into a locked snapshot.
    readonly_fields = ("snapshot",)

    def has_add_permission(self, request):
        # Snapshot items are created only as part of an editable snapshot inline.
        return False

    def has_change_permission(self, request, obj=None):
        if obj is None or not obj.snapshot.is_editable:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is None or not obj.snapshot.is_editable:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(AssetAttachment)
class AssetAttachmentAdmin(admin.ModelAdmin):
    list_display = ("asset", "kind", "title", "uploaded_by", "created_at")
    list_filter = ("kind",)

class AgentCredentialAdminForm(forms.ModelForm):
    asset = forms.ModelChoiceField(
        label="دارایی اختصاصی ایجنت",
        queryset=Asset.objects.filter(center__isnull=False, status="active").select_related("center"),
        required=True,
    )

    class Meta:
        model = AgentCredential
        fields = ("center", "asset", "name", "hostname", "expires_at")

    def clean(self):
        cleaned = super().clean()
        center = cleaned.get("center")
        asset = cleaned.get("asset")
        hostname = (cleaned.get("hostname") or "").strip()
        if asset and center and asset.center_id != center.pk:
            self.add_error("asset", "دارایی باید متعلق به مرکز انتخاب‌شده باشد.")
        if asset:
            expected = (asset.hostname or "").strip()
            if asset.status != "active":
                self.add_error("asset", "برای دارایی غیرفعال نمی‌توان اعتبارنامه صادر کرد.")
            elif not expected:
                self.add_error("asset", "ابتدا برای دارایی hostname ثبت کنید.")
            elif hostname and hostname.casefold() != expected.casefold():
                self.add_error("hostname", "hostname اعتبارنامه باید با hostname دارایی یکسان باشد.")
            else:
                cleaned["hostname"] = expected
        return cleaned


@admin.register(AgentCredential)
class AgentCredentialAdmin(admin.ModelAdmin):
    form = AgentCredentialAdminForm
    fields = ("center", "asset", "name", "hostname", "expires_at", "agent_uid", "token_prefix", "token_hash", "status", "last_sync_at", "last_ip", "revoked_at", "created_by")
    list_display = ("name", "center", "token_prefix", "status", "expires_at", "last_sync_at", "last_ip")
    list_filter = ("status", "center")
    search_fields = ("name", "hostname", "token_prefix")
    readonly_fields = (
        "agent_uid", "token_prefix", "token_hash", "status",
        "last_sync_at", "last_ip", "revoked_at", "created_by",
    )
    actions = ("revoke_credentials", "rotate_credentials", "suspend_credentials", "activate_credentials")

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            fields.extend(("center", "asset", "name", "hostname"))
        return tuple(fields)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            # The raw token is generated once and shown only in this response.
            credential, raw_token = AgentCredential.generate(
                center=obj.center,
                asset=obj.asset,
                name=obj.name,
                hostname=obj.hostname,
                expires_in_days=365,
                created_by=request.user,
            )
            if obj.expires_at:
                credential.expires_at = obj.expires_at
                credential.save(update_fields=["expires_at", "updated_at"])
            for field in (
                "pk", "agent_uid", "asset", "token_prefix", "token_hash", "status",
                "expires_at", "created_at", "updated_at", "created_by",
            ):
                setattr(obj, field, getattr(credential, field))
            obj._state.adding = False
            obj._state.db = credential._state.db
            log_action(
                "create", credential,
                note="صدور اعتبارنامه اختصاصی HWAgent",
                user=request.user,
            )
            self.message_user(
                request,
                f"توکن فقط همین یک‌بار نمایش داده می‌شود؛ آن را در محل امن به ایجنت بدهید: {raw_token}",
                level=messages.WARNING,
            )
            return
        super().save_model(request, obj, form, change)

    @admin.action(description="ابطال اعتبارنامه‌های انتخاب‌شده")
    def revoke_credentials(self, request, queryset):
        count = 0
        for credential in queryset.filter(status=AgentCredential.STATUS_ACTIVE):
            credential.revoke("ابطال توسط مدیر سامانه")
            log_action(
                "status_change", credential,
                note="ابطال اعتبارنامه HWAgent از پنل مدیریت",
                user=request.user,
            )
            count += 1
        self.message_user(request, f"{count} اعتبارنامه باطل شد.")

    @admin.action(description="چرخش توکن و صدور اعتبارنامه جدید")
    def rotate_credentials(self, request, queryset):
        for credential in queryset.filter(status=AgentCredential.STATUS_ACTIVE):
            new_credential, raw_token = credential.rotate(created_by=request.user)
            log_action(
                "status_change", credential,
                note="ابطال اعتبارنامه قبلی و چرخش توکن HWAgent",
                user=request.user,
            )
            log_action(
                "create", new_credential,
                note="صدور اعتبارنامه جدید در چرخش توکن HWAgent",
                user=request.user,
            )
            self.message_user(
                request,
                f"توکن جدید برای {new_credential.name} (فقط یک‌بار): {raw_token}",
                level=messages.WARNING,
            )

    @admin.action(description="تعلیق اعتبارنامه‌های انتخاب‌شده")
    def suspend_credentials(self, request, queryset):
        count = 0
        for credential in queryset.filter(status=AgentCredential.STATUS_ACTIVE):
            credential.status = AgentCredential.STATUS_SUSPENDED
            credential.save(update_fields=["status", "updated_at"])
            log_action(
                "status_change", credential,
                note="تعلیق اعتبارنامه HWAgent از پنل مدیریت",
                user=request.user,
            )
            count += 1
        self.message_user(request, f"{count} اعتبارنامه معلق شد.")

    @admin.action(description="فعال‌سازی اعتبارنامه‌های معلق")
    def activate_credentials(self, request, queryset):
        count = 0
        for credential in queryset.filter(status=AgentCredential.STATUS_SUSPENDED):
            credential.status = AgentCredential.STATUS_ACTIVE
            credential.save(update_fields=["status", "updated_at"])
            log_action(
                "status_change", credential,
                note="فعال‌سازی اعتبارنامه HWAgent از پنل مدیریت",
                user=request.user,
            )
            count += 1
        self.message_user(request, f"{count} اعتبارنامه فعال شد.")


@admin.register(AgentSyncAuditLog)
class AgentSyncAuditLogAdmin(admin.ModelAdmin):
    list_display = ("agent", "center", "remote_ip", "http_status", "success", "created_at")
    list_filter = ("success", "http_status", "center")
    search_fields = ("agent__name", "remote_ip", "rejection_reason")
    readonly_fields = ("created_at",)


@admin.register(AssetRelationship)
class AssetRelationshipAdmin(admin.ModelAdmin):
    list_display = ("asset", "relationship_type", "related_asset", "connection_type", "is_active")
    list_filter = ("relationship_type", "connection_type", "is_active")
    search_fields = ("asset__asset_tag", "related_asset__asset_tag")
