"""ثبت مدل‌های بازدید دوره‌ای در پنل مدیریت جنگو."""
from django.contrib import admin

from .models import MaintenanceVisit, VisitAssetCheck


class VisitAssetCheckInline(admin.TabularInline):
    model = VisitAssetCheck
    extra = 0
    fields = ("asset", "checked", "condition", "actions_taken", "parts_replaced", "next_due_date", "checked_by")


@admin.register(MaintenanceVisit)
class MaintenanceVisitAdmin(admin.ModelAdmin):
    list_display = ("number", "contract", "period_label", "scheduled_date", "scheduled_end_date", "status", "technician")
    list_filter = ("status", "contract__contractor")
    search_fields = ("number", "period_label", "contract__number")
    date_hierarchy = "scheduled_date"
    inlines = [VisitAssetCheckInline]


@admin.register(VisitAssetCheck)
class VisitAssetCheckAdmin(admin.ModelAdmin):
    list_display = ("visit", "asset", "checked", "condition", "checked_by", "checked_at")
    list_filter = ("checked", "condition")
    search_fields = ("asset__asset_tag", "visit__number")


from .repair_models import (
    GeneralITRequest, GeneralITRequestEvent, GeneralReferral, IndependentRepairer,
    RepairFeedback, RepairFeedbackReply, RepairRequest, RepairRequestEvent,
    RepairerProfileEvent, RepairerStatusEvent,
)


class ReadOnlyAuditAdmin(admin.ModelAdmin):
    """Audit records are append-only from the application and read-only in admin."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.has_role("admin_it")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IndependentRepairer)
class IndependentRepairerAdmin(ReadOnlyAuditAdmin):
    list_display = ("name", "kind", "province", "is_active", "updated_at")
    list_filter = ("province", "kind", "is_active")
    search_fields = ("name", "national_id", "phone")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")

    def has_add_permission(self, request):
        return False


@admin.register(RepairRequest)
class RepairRequestAdmin(ReadOnlyAuditAdmin):
    list_display = ("number", "center", "asset", "repairer_name_snapshot", "status", "estimate_amount", "final_cost")
    list_filter = ("status", "center__treatment_management__province")
    search_fields = ("number", "asset__asset_tag", "repairer_name_snapshot")


@admin.register(RepairRequestEvent)
class RepairRequestEventAdmin(ReadOnlyAuditAdmin):
    list_display = ("repair_request", "action", "actor", "created_at")
    list_filter = ("action",)


@admin.register(RepairerStatusEvent)
class RepairerStatusEventAdmin(ReadOnlyAuditAdmin):
    list_display = ("repairer", "previous_active", "new_active", "actor", "created_at")


@admin.register(RepairFeedback)
class RepairFeedbackAdmin(ReadOnlyAuditAdmin):
    list_display = ("repairer_name_snapshot", "center", "work_quality", "completion_speed", "cost_fairness", "author")
    list_filter = ("center__treatment_management__province",)


@admin.register(RepairFeedbackReply)
class RepairFeedbackReplyAdmin(ReadOnlyAuditAdmin):
    list_display = ("feedback", "author", "created_at")


@admin.register(GeneralReferral)
class GeneralReferralAdmin(ReadOnlyAuditAdmin):
    list_display = ("subject", "recipient_role", "recipient_name", "status", "created_by", "created_at")
    list_filter = ("status", "recipient_role")


@admin.register(GeneralITRequest)
class GeneralITRequestAdmin(ReadOnlyAuditAdmin):
    list_display = ("number", "center", "request_type", "status", "manager_approval", "requested_by")
    list_filter = ("status", "manager_approval", "request_type")


@admin.register(GeneralITRequestEvent)
class GeneralITRequestEventAdmin(ReadOnlyAuditAdmin):
    list_display = ("request", "action", "actor", "created_at")


@admin.register(RepairerProfileEvent)
class RepairerProfileEventAdmin(ReadOnlyAuditAdmin):
    list_display = ("repairer", "action", "actor", "created_at")
    list_filter = ("action",)
