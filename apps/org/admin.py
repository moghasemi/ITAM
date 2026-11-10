"""ثبت مدل‌های سازمانی در پنل مدیریت جنگو."""
from django.contrib import admin
from django.forms import inlineformset_factory

from .models import Center, Contract, Contractor, Department, Location, OrganizationalUnit, SlaPolicy


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
    list_display = ("number", "contractor", "province", "title", "start_date", "end_date", "visit_interval_days", "status")
    list_filter = ("status", "province", "contractor")
    search_fields = ("number", "title", "province__name", "contractor__name")
    fields = (
        "contractor", "province", "number", "title", "start_date", "end_date",
        "visit_interval_days", "status", "visit_scope", "repair_scope", "notes",
    )
    inlines = [SlaPolicyInline]
    date_hierarchy = "start_date"


@admin.register(SlaPolicy)
class SlaPolicyAdmin(admin.ModelAdmin):
    list_display = ("contract", "priority", "response_minutes", "resolve_minutes")
    list_filter = ("priority",)

@admin.register(OrganizationalUnit)
class OrganizationalUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "unit_type", "parent", "is_active")
    list_filter = ("unit_type", "is_active")
    search_fields = ("name", "code")


@admin.register(Center)
class CenterAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "parent_unit", "get_province_display", "city", "is_headquarters", "is_active")
    list_filter = ("is_headquarters", "is_active")
    search_fields = ("name", "code", "city")

    @admin.display(description="استان (سلسله‌مراتب سازمانی)")
    def get_province_display(self, obj):
        return obj.province_name

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "parent_unit":
            kwargs["queryset"] = OrganizationalUnit.objects.filter(
                unit_type=OrganizationalUnit.UNIT_COUNTY, is_active=True
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)
