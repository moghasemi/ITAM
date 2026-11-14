"""مسیرهای بازدیدهای دوره‌ای."""
from django.urls import path

from . import repair_views

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

    path("repairers/", repair_views.repairer_list, name="repairer_list"),
    path("repairers/add/", repair_views.repairer_create, name="repairer_create"),
    path("repairers/<int:pk>/edit/", repair_views.repairer_update, name="repairer_update"),
    path("repairers/<int:pk>/status/", repair_views.repairer_status, name="repairer_status"),
    path("repairs/", repair_views.repair_list, name="repair_list"),
    path("repairs/add/", repair_views.repair_create, name="repair_create"),
    path("repairs/<int:pk>/", repair_views.repair_detail, name="repair_detail"),
    path("repairs/<int:pk>/decide/", repair_views.repair_decide, name="repair_decide"),
    path("repairs/<int:pk>/resubmit/", repair_views.repair_resubmit, name="repair_resubmit"),
    path("repairs/<int:pk>/complete/", repair_views.repair_complete, name="repair_complete"),
    path("repairs/<int:pk>/resolve-cost/", repair_views.repair_cost_resolve, name="repair_cost_resolve"),
    path("feedback/", repair_views.feedback_list, name="feedback_list"),
    path("feedback/<int:pk>/reply/", repair_views.feedback_reply, name="feedback_reply"),
    path("referrals/", repair_views.referral_list, name="referral_list"),
    path("referrals/add/", repair_views.referral_create, name="referral_create"),
    path("referrals/<int:pk>/resolve/", repair_views.referral_resolve, name="referral_resolve"),
    path("requests/", repair_views.it_request_list, name="it_request_list"),
    path("requests/add/", repair_views.it_request_create, name="it_request_create"),
    path("requests/<int:pk>/", repair_views.it_request_detail, name="it_request_detail"),
    path("requests/<int:pk>/assign/", repair_views.it_request_assign, name="it_request_assign"),
    path("requests/<int:pk>/manager-decision/", repair_views.it_request_manager_decide, name="it_request_manager_decide"),
    path("requests/<int:pk>/escalate/", repair_views.it_request_escalate, name="it_request_escalate"),
    path("requests/<int:pk>/resolve/", repair_views.it_request_resolve, name="it_request_resolve"),
]
