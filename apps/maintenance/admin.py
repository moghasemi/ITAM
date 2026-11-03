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
