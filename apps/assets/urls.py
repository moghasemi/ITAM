"""مسیرهای دارایی‌ها و اسنپ‌شات سخت‌افزاری."""
from django.urls import path

from . import views

app_name = "assets"

urlpatterns = [
    path("", views.AssetListView.as_view(), name="list"),
    path("add/", views.AssetCreateView.as_view(), name="create"),
    path("labels/print/", views.label_print, name="label_print"),
    path("hardware/report/", views.hardware_change_report, name="hardware_report"),
    path("hardware/pending/", views.snapshot_pending_list, name="snapshot_pending"),
    path("categories/", views.CategoryListView.as_view(), name="category_list"),
    path("categories/add/", views.CategoryCreateView.as_view(), name="category_create"),
    path("categories/<int:pk>/edit/", views.CategoryUpdateView.as_view(), name="category_update"),
    path("component-types/", views.ComponentTypeListView.as_view(), name="component_type_list"),
    path("component-types/add/", views.ComponentTypeCreateView.as_view(), name="component_type_create"),
    path("component-types/<int:pk>/edit/", views.ComponentTypeUpdateView.as_view(), name="component_type_update"),
    # ورود از طریق QR
    path("scan/<uuid:token>/", views.asset_scan, name="scan"),
    path("<int:pk>/", views.AssetDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.AssetUpdateView.as_view(), name="update"),
    path("<int:pk>/qr.svg", views.asset_qr_image, name="qr_image"),
    path("<int:asset_pk>/attachments/add/", views.AttachmentCreateView.as_view(), name="attachment_create"),
    path("attachments/<int:pk>/delete/", views.attachment_delete, name="attachment_delete"),
    # اسنپ‌شات سخت‌افزاری
    path("<int:asset_pk>/snapshot/start/", views.snapshot_start, name="snapshot_start"),
    path("snapshots/<int:pk>/", views.SnapshotDetailView.as_view(), name="snapshot_detail"),
    path("snapshots/<int:pk>/edit/", views.SnapshotEditView.as_view(), name="snapshot_edit"),
    path("snapshots/<int:pk>/submit/", views.snapshot_submit, name="snapshot_submit"),
    path("snapshots/<int:pk>/approve/", views.snapshot_approve, name="snapshot_approve"),
    path("snapshots/<int:pk>/reject/", views.snapshot_reject, name="snapshot_reject"),
]
