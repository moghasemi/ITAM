"""ثبت مدل کاربر در پنل مدیریت جنگو."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "display_name", "role", "department", "contractor", "is_active")
    list_filter = ("role", "is_active", "department", "contractor")
    search_fields = ("username", "first_name", "last_name", "personnel_code", "phone")
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "اطلاعات سازمانی",
            {
                "fields": (
                    "role", "personnel_code", "national_code", "phone", "job_title",
                    "department", "contractor", "signature", "last_seen_at",
                )
            },
        ),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("اطلاعات سازمانی", {"fields": ("role", "department", "contractor")}),
    )
