"""مسیرهای اصلی سامانه."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.urls import include, path, re_path
from django.views.static import serve as media_serve

admin.site.site_header = "مدیریت سامانه ITAM"
admin.site.site_title = "ITAM"
admin.site.index_title = "پنل مدیریت پایگاه داده"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("org/", include("apps.org.urls")),
    path("assets/", include("apps.assets.urls")),
    path("tickets/", include("apps.tickets.urls")),
    path("maintenance/", include("apps.maintenance.urls")),
    path("integrations/", include("apps.integrations.urls")),
    path("reports/", include("apps.reports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
else:
    # در شبکه محلی، رسانه‌ها توسط خود جنگو سرو می‌شوند (بار سبک است)
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", media_serve, {"document_root": settings.MEDIA_ROOT}),
    ]
    if not getattr(settings, "USE_WHITENOISE", False):
        urlpatterns += [
            re_path(r"^static/(?P<path>.*)$", staticfiles_serve, {"insecure": True}),
        ]
