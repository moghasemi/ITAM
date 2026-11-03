"""مسیرهای یکپارچه‌سازی و صف رخدادها."""
from django.urls import path

from . import views

app_name = "integrations"

urlpatterns = [
    path("outbox/", views.OutboxListView.as_view(), name="outbox_list"),
    path("outbox/<int:pk>/", views.OutboxDetailView.as_view(), name="outbox_detail"),
    path("outbox/<int:pk>/requeue/", views.requeue_event, name="requeue_event"),
    path("outbox/requeue-all/", views.requeue_all, name="requeue_all"),
    path("dispatch/", views.dispatch_now, name="dispatch_now"),
    path("endpoints/", views.EndpointListView.as_view(), name="endpoint_list"),
    path("endpoints/add/", views.EndpointCreateView.as_view(), name="endpoint_create"),
    path("endpoints/<int:pk>/edit/", views.EndpointUpdateView.as_view(), name="endpoint_update"),
    path("api-calls/", views.ApiCallListView.as_view(), name="api_call_list"),
]
