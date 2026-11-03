"""مسیرهای درخواست‌های خرابی."""
from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.TicketListView.as_view(), name="list"),
    path("mine/", views.MyTicketsView.as_view(), name="my_tickets"),
    path("new/", views.TicketCreateView.as_view(), name="create"),
    path("<int:pk>/", views.TicketDetailView.as_view(), name="detail"),
    path("<int:pk>/print/", views.ticket_print, name="print"),
    path("<int:pk>/acknowledge/", views.ticket_acknowledge, name="acknowledge"),
    path("<int:pk>/arrive/", views.ticket_arrive, name="arrive"),
    path("<int:pk>/start/", views.ticket_start, name="start"),
    path("<int:pk>/pause/", views.ticket_pause, name="pause"),
    path("<int:pk>/resume/", views.ticket_resume, name="resume"),
    path("<int:pk>/resolve/", views.ticket_resolve, name="resolve"),
    path("<int:pk>/user-confirm/", views.ticket_user_confirm, name="user_confirm"),
    path("<int:pk>/user-reject/", views.ticket_user_reject, name="user_reject"),
    path("<int:pk>/it-confirm/", views.ticket_it_confirm, name="it_confirm"),
    path("<int:pk>/cancel/", views.ticket_cancel, name="cancel"),
    path("<int:pk>/note/", views.ticket_add_note, name="add_note"),
    path("<int:pk>/part/", views.ticket_add_part, name="add_part"),
    path("<int:pk>/attachment/", views.ticket_add_attachment, name="add_attachment"),
]
