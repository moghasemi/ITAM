"""ثبت مدل‌های سازمانی در پنل مدیریت جنگو."""
from django.contrib import admin
from django.forms import inlineformset_factory

from .models import Contract, Contractor, Department, Location, SlaPolicy


class SlaPolicyInline(admin.TabularInline):
    model = SlaPolicy
    extra = 1


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "manager_name", "is_active")
    search_fields = ("name", "code")


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "building", "floor", "room", "is_active")
    list_filter = ("building", "is_active")
    search_fields = ("name", "building", "room")


@admin.register(Contractor)
class ContractorAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "contact_person", "contact_phone", "is_active")
    search_fields = ("name", "code", "contact_person")


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("number", "contractor", "title", "start_date", "end_date", "visit_interval_days", "status")
    list_filter = ("status", "contractor")
    search_fields = ("number", "title")
    inlines = [SlaPolicyInline]
    date_hierarchy = "start_date"


@admin.register(SlaPolicy)
class SlaPolicyAdmin(admin.ModelAdmin):
    list_display = ("contract", "priority", "response_minutes", "resolve_minutes")
    list_filter = ("priority",)
