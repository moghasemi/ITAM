"""مسیرهای اصلی سامانه."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.urls import include, path, re_path
from apps.core.views import private_media

admin.site.site_header = "مدیریت سامانه ITAM"
admin.site.site_title = "ITAM"
admin.site.index_title = "پنل مدیریت پایگاه داده"

from apps.assets.views import api_hwagent_sync

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/hardware/agent-sync/", api_hwagent_sync, name="api_hwagent_sync_root"),
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
    # Uploaded media is private: each request is checked against its owning record.
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", private_media, name="private_media"),
    ]
    if not getattr(settings, "USE_WHITENOISE", False):
        urlpatterns += [
            re_path(r"^static/(?P<path>.*)$", staticfiles_serve, {"insecure": True}),
        ]
