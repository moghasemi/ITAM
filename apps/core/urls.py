"""مسیرهای هسته سامانه."""
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("search/", views.global_search, name="search"),
    path("notifications/", views.notification_list, name="notification_list"),
    path("notifications/read-all/", views.notifications_read_all, name="notifications_read_all"),
    path("notifications/<int:pk>/read/", views.notification_read, name="notification_read"),
    path("settings/", views.SettingUpdateView.as_view(), name="setting_update"),
    path("settings/holidays/", views.HolidayListView.as_view(), name="holiday_list"),
    path("settings/holidays/add/", views.holiday_create, name="holiday_create"),
    path("settings/holidays/<int:pk>/edit/", views.HolidayUpdateView.as_view(), name="holiday_update"),
    path("settings/holidays/<int:pk>/delete/", views.holiday_delete, name="holiday_delete"),
    path("audit/", views.AuditLogListView.as_view(), name="audit_list"),
]
