"""مسیرهای گزارش‌ها."""
from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.ReportsHomeView.as_view(), name="home"),
    path("sla/", views.SlaReportView.as_view(), name="sla"),
    path("contractors/", views.ContractorScorecardView.as_view(), name="contractors"),
    path("repairs/", views.RepairPerformanceReportView.as_view(), name="repairs"),
    path("inventory/", views.InventoryReportView.as_view(), name="inventory"),
    path("visits/", views.VisitComplianceView.as_view(), name="visits"),
    path("failures/", views.FailureAnalysisView.as_view(), name="failures"),
]
