"""مسیرهای برنامه کاربران."""
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.ItamLoginView.as_view(), name="login"),
    path("logout/", views.ItamLogoutView.as_view(), name="logout"),
    path("profile/signature/", views.signature_file, name="signature_file"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("profile/edit/", views.ProfileUpdateView.as_view(), name="profile_edit"),
    path("password/", views.ItamPasswordChangeView.as_view(), name="password_change"),
    path("users/", views.UserListView.as_view(), name="user_list"),
    path("users/add/", views.UserCreateView.as_view(), name="user_create"),
    path("users/<int:pk>/", views.UserDetailView.as_view(), name="user_detail"),
    path("users/<int:pk>/edit/", views.UserUpdateView.as_view(), name="user_update"),
    path("users/<int:pk>/toggle/", views.user_toggle_active, name="user_toggle"),
    path("users/<int:pk>/password/", views.user_set_password, name="user_password"),
]
