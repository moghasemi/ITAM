"""مسیرهای بازدیدهای دوره‌ای."""
from django.urls import path

from . import views

app_name = "maintenance"

urlpatterns = [
    path("", views.VisitListView.as_view(), name="visit_list"),
    path("mine/", views.MyVisitsView.as_view(), name="my_visits"),
    path("new/", views.VisitCreateView.as_view(), name="visit_create"),
    path("<int:pk>/", views.VisitDetailView.as_view(), name="visit_detail"),
    path("<int:pk>/edit/", views.VisitUpdateView.as_view(), name="visit_update"),
    path("<int:pk>/start/", views.visit_start, name="visit_start"),
    path("<int:pk>/complete/", views.visit_complete, name="visit_complete"),
    path("<int:pk>/confirm/", views.visit_confirm, name="visit_confirm"),
    path("<int:pk>/bulk-healthy/", views.visit_bulk_healthy, name="visit_bulk_healthy"),
    path("<int:pk>/print/", views.visit_print, name="visit_print"),
    path("checks/<int:pk>/", views.check_edit, name="check_edit"),
]
