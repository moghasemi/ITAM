"""نماهای دارایی‌ها، اسنپ‌شات سخت‌افزاری ضدسرقت و برچسب QR."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
import json
import mimetypes
import time
import hashlib
from datetime import datetime, timezone as dt_timezone
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db import IntegrityError, transaction
import uuid
import logging

logger = logging.getLogger(__name__)
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, UpdateView

from apps.accounts.permissions import (
    AdminItRequiredMixin,
    AnyRoleRequiredMixin,
    RepairStaffRequiredMixin,
)
from apps.core.mixins import (
    BaseCreateView,
    BaseDetailView,
    BaseListView,
    BaseUpdateView,
    PageContextMixin,
    apply_search,
)
from apps.core.models import SystemSetting
from apps.core.utils import log_action

from .forms import (
    AssetAttachmentForm,
    AssetFilterForm,
    AssetForm,
    CategoryForm,
    ComponentTypeForm,
    HardwareSnapshotForm,
    SnapshotItemFormSet,
)
from .models import (
    Asset,
    AssetAttachment,
    AssetCategory,
    AssetRelationship,
    ComponentType,
    HardwareSnapshot,
    AgentCredential,
    AgentNonce,
    AgentSyncAuditLog,
)
from .qrgen import svg as qr_svg
from .hwagent_service import apply_hwagent_snapshot, process_batch_hwagent_files, match_asset_for_hwagent
from .services import (
    asset_spec_rows,
    can_record_snapshot,
    create_snapshot,
    log_asset_created,
    log_asset_updated,
    recompute_diff,
    reference_snapshot,
    visible_assets,
)


# ---------------------------------------------------------------------------
# فهرست و شناسنامه دارایی
# ---------------------------------------------------------------------------
class AssetListView(AnyRoleRequiredMixin, BaseListView):
    model = Asset
    template_name = "assets/asset_list.html"
    page_title = "دارایی‌های فناوری اطلاعات"
    active_menu = "assets"
    paginate_by = 25
    filter_form_class = AssetFilterForm

    def get_filter_form(self):
        return self.filter_form_class(self.request.GET or None, user=self.request.user)

    def get_queryset(self):
        queryset = visible_assets(self.request.user).annotate(
            tickets_total=Count("tickets", distinct=True)
        )
        ordering = "asset_tag"
        form = self.get_filter_form()
        if form is not None and form.is_valid():
            data = form.cleaned_data
            queryset = apply_search(
                queryset,
                data.get("q"),
                ["asset_tag", "title", "serial_number", "brand", "model_name", "hostname", "ip_address"],
            )
            if data.get("center"):
                queryset = queryset.filter(center=data["center"])
            if data.get("category"):
                queryset = queryset.filter(category=data["category"])
            if data.get("department"):
                queryset = queryset.filter(department=data["department"])
            if data.get("location"):
                queryset = queryset.filter(location=data["location"])
            if data.get("contract"):
                queryset = queryset.filter(contract=data["contract"])
            if data.get("status"):
                queryset = queryset.filter(status=data["status"])
            tracking = data.get("tracking")
            if tracking == "with":
                queryset = queryset.filter(current_snapshot__isnull=False)
            elif tracking == "without":
                queryset = queryset.filter(current_snapshot__isnull=True)
            ordering = data.get("ordering") or "asset_tag"
        if ordering == "-open_tickets":
            return queryset.order_by("-tickets_total", "asset_tag")
        return queryset.order_by(ordering)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_create"] = self.request.user.has_role("admin_it")
        return context


class AssetDetailView(AnyRoleRequiredMixin, BaseDetailView):
    model = Asset
    template_name = "assets/asset_detail.html"
    page_title = "شناسنامه دارایی"
    active_menu = "assets"

    def get_queryset(self):
        return visible_assets(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        asset = self.object
        user = self.request.user
        context["spec_rows"] = asset_spec_rows(asset)
        context["components"] = (
            asset.current_snapshot.items.select_related("component_type")
            if asset.current_snapshot_id
            else []
        )
        context["snapshots"] = asset.snapshots.select_related(
            "recorded_by", "it_confirmed_by", "technician_confirmed_by"
        ).order_by("-version")
        context["tickets"] = asset.tickets.select_related("assigned_technician").order_by("-reported_at")[:15]
        context["visits"] = asset.visit_checks.select_related("visit", "checked_by").order_by("-checked_at")[:10]
        context["attachments"] = asset.attachments.select_related("uploaded_by")
        context["asset_relationships"] = AssetRelationship.objects.filter(
            Q(asset=asset) | Q(related_asset=asset), is_active=True
        ).select_related("asset__category", "related_asset__category")
        context["can_edit"] = user.has_role("admin_it")
        context["can_snapshot"] = can_record_snapshot(user, asset)
        context["tracking_required"] = asset.requires_component_tracking
        context["is_it"] = user.has_role("admin_it")
        return context


def _sync_connected_computers(asset, form):
    """همگام‌سازی ارتباط چاپگر/تجهیز جانبی با رایانه‌های همان مرکز."""
    relationships = asset.outgoing_relationships.filter(
        relationship_type=AssetRelationship.RELATION_CONNECTED_TO
    )
    if asset.category.is_computing_device:
        relationships.delete()
        return
    selected = form.cleaned_data.get("connected_computers")
    selected_ids = list(selected.values_list("pk", flat=True)) if selected is not None else []
    relationships.exclude(related_asset_id__in=selected_ids).delete()
    connection_type = form.cleaned_data.get("connection_type") or AssetRelationship.CONNECTION_TYPE_OTHER
    for computer in selected or []:
        AssetRelationship.objects.update_or_create(
            asset=asset, related_asset=computer,
            relationship_type=AssetRelationship.RELATION_CONNECTED_TO,
            defaults={"connection_type": connection_type, "is_active": True},
        )


class AssetCreateView(AdminItRequiredMixin, BaseCreateView):
    model = Asset
    form_class = AssetForm
    template_name = "assets/asset_form.html"
    page_title = "ثبت دارایی جدید"
    active_menu = "assets"
    success_url_name = "assets:detail"
    success_message = "دارایی ثبت شد."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        _sync_connected_computers(self.object, form)
        log_asset_created(self.object, self.request.user)
        return response


class AssetUpdateView(AdminItRequiredMixin, BaseUpdateView):
    model = Asset
    form_class = AssetForm
    template_name = "assets/asset_form.html"
    page_title = "ویرایش دارایی"
    active_menu = "assets"
    success_url_name = "assets:detail"

    def get_queryset(self):
        from apps.assets.services import visible_assets
        return visible_assets(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        _sync_connected_computers(self.object, form)
        log_asset_updated(self.object, {"asset_tag": self.object.asset_tag}, self.request.user)
        return response


def asset_scan(request, token):
    """ورود از طریق QR برچسب تجهیز."""
    asset = get_object_or_404(Asset, qr_token=token)
    if not request.user.is_authenticated:
        return redirect(f"{reverse('accounts:login')}?next={reverse('assets:scan', args=[token])}")
    if not visible_assets(request.user).filter(pk=asset.pk).exists():
        raise PermissionDenied("این تجهیز در محدوده دسترسی شما نیست.")
    if asset.requires_component_tracking and can_record_snapshot(request.user, asset):
        return redirect(reverse("assets:detail", args=[asset.pk]) + "?focus=hardware")
    return redirect("assets:detail", pk=asset.pk)


def asset_qr_image(request, pk: int):
    """تصویر QR دارایی به‌صورت SVG."""
    asset = get_object_or_404(visible_assets(request.user), pk=pk)
    content = qr_svg(asset.public_url(), module_size=8, title=str(asset.asset_tag))
    return HttpResponse(content, content_type="image/svg+xml; charset=utf-8")


def label_print(request):
    """چاپ برچسب QR برای تجهیزات انتخاب‌شده یا پالایش‌شده."""
    ids = request.GET.getlist("ids")
    queryset = visible_assets(request.user)
    if ids:
        queryset = queryset.filter(pk__in=ids)
    else:
        queryset = queryset.filter(baseline_locked_at__isnull=True) if request.GET.get("new") == "1" else queryset
    assets = queryset.order_by("asset_tag")[:200]
    rows = []
    for asset in assets:
        rows.append(
            {
                "asset": asset,
                "qr": qr_svg(asset.public_url(), module_size=4, title=str(asset.asset_tag)),
                "url": asset.public_url(),
            }
        )
    return render(
        request,
        "assets/label_print.html",
        {"rows": rows, "page_title": "چاپ برچسب QR"},
    )


# ---------------------------------------------------------------------------
# اسنپ‌شات سخت‌افزاری
# ---------------------------------------------------------------------------
def snapshot_start(request, asset_pk: int):
    """شروع ثبت اسنپ‌شات سخت‌افزاری برای یک تجهیز."""
    asset = get_object_or_404(visible_assets(request.user), pk=asset_pk)
    if request.method != "POST":
        return render(
            request,
            "assets/snapshot_start.html",
            {
                "asset": asset,
                "reference": reference_snapshot(asset),
                "page_title": "شروع ثبت اقلام سخت‌افزاری",
                "active_menu": "assets",
            },
        )
    try:
        snapshot = create_snapshot(asset, request.user)
    except PermissionDenied as exc:
        messages.error(request, str(exc))
        return redirect("assets:detail", pk=asset.pk)
    return redirect("assets:snapshot_edit", pk=snapshot.pk)


class SnapshotEditView(RepairStaffRequiredMixin, PageContextMixin, UpdateView):
    """ثبت و ویرایش اقلام داخل کیس با نمایش تفاوت نسبت به وضعیت قبلی."""

    model = HardwareSnapshot
    form_class = HardwareSnapshotForm
    template_name = "assets/snapshot_form.html"
    page_title = "ثبت اقلام سخت‌افزاری"
    active_menu = "assets"
    context_object_name = "snapshot"

    def get_object(self, queryset=None):
        snapshot = get_object_or_404(
            HardwareSnapshot.objects.select_related("asset", "previous"), pk=self.kwargs["pk"]
        )
        if not can_record_snapshot(self.request.user, snapshot.asset):
            raise PermissionDenied("اجازه ویرایش این اسنپ‌شات را ندارید.")
        if not snapshot.is_editable:
            messages.warning(self.request, "این اسنپ‌شات قفل شده است و فقط قابل مشاهده است.")
            raise PermissionDenied("اسنپ‌شات قفل‌شده قابل ویرایش نیست.")
        return snapshot

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        snapshot = self.object
        if self.request.method == "POST":
            formset = SnapshotItemFormSet(self.request.POST, self.request.FILES, instance=snapshot)
        else:
            formset = SnapshotItemFormSet(instance=snapshot)
        context["formset"] = formset
        context["asset"] = snapshot.asset
        context["reference"] = snapshot.previous or reference_snapshot(snapshot.asset, exclude=snapshot)
        context["preview"] = recompute_diff(snapshot, save=False)
        context["is_baseline"] = snapshot.is_baseline
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context["formset"]
        if not formset.is_valid():
            messages.error(self.request, "اقلام سخت‌افزاری را بررسی کنید.")
            return self.form_invalid(form)
        self.object = form.save()
        formset.instance = self.object
        formset.save()
        result = recompute_diff(self.object)
        log_action(
            "update",
            self.object,
            note="ثبت/ویرایش اقلام سخت‌افزاری",
            changes={"diff_count": result["total_changes"]},
            user=self.request.user,
        )
        messages.success(
            self.request,
            f"اقلام ذخیره شد. تعداد تغییرات نسبت به وضعیت قبلی: {result['total_changes']}",
        )
        if "submit_for_review" in self.request.POST:
            return redirect("assets:snapshot_submit", pk=self.object.pk)
        return redirect("assets:snapshot_detail", pk=self.object.pk)


class SnapshotDetailView(AnyRoleRequiredMixin, BaseDetailView):
    model = HardwareSnapshot
    template_name = "assets/snapshot_detail.html"
    page_title = "اسنپ‌شات سخت‌افزاری"
    active_menu = "assets"
    context_object_name = "snapshot"

    def get_queryset(self):
        return HardwareSnapshot.objects.select_related(
            "asset", "recorded_by", "previous", "it_confirmed_by", "technician_confirmed_by"
        ).filter(asset__in=visible_assets(self.request.user))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        snapshot = self.object
        context["items"] = snapshot.items.select_related("component_type")
        context["diff"] = snapshot.diff_data or recompute_diff(snapshot, save=False)
        context["reference"] = snapshot.previous
        context["asset"] = snapshot.asset
        context["can_edit"] = snapshot.is_editable and can_record_snapshot(self.request.user, snapshot.asset)
        context["can_approve"] = self.request.user.has_role("admin_it") and snapshot.status == "pending"
        return context


@login_required
def snapshot_submit(request, pk: int):
    """ارسال اسنپ‌شات برای تایید کارشناس IT."""
    snapshot = get_object_or_404(HardwareSnapshot.objects.select_related("asset"), pk=pk)
    if not can_record_snapshot(request.user, snapshot.asset):
        raise PermissionDenied("اجازه ارسال این اسنپ‌شات را ندارید.")
    if request.method == "POST":
        from .services import submit_snapshot

        try:
            result = submit_snapshot(snapshot, request.user)
            if result["has_alarm"]:
                messages.warning(
                    request,
                    f"اسنپ‌شات ثبت شد؛ {result['removed']} قلم مفقود و {result['replaced']} قلم تعویض‌شده گزارش شد.",
                )
            else:
                messages.success(request, "اسنپ‌شات برای تایید ارسال شد.")
        except ValidationError as exc:
            messages.error(request, "؛ ".join(exc.messages))
    return redirect("assets:snapshot_detail", pk=pk)


@login_required
def snapshot_approve(request, pk: int):
    """تایید و قفل اسنپ‌شات توسط کارشناس IT."""
    snapshot = get_object_or_404(HardwareSnapshot.objects.select_related("asset"), pk=pk)
    if not request.user.has_role("admin_it"):
        raise PermissionDenied("تایید اسنپ‌شات فقط توسط کارشناس فناوری اطلاعات مرکز انجام می‌شود.")
    if not visible_assets(request.user).filter(pk=snapshot.asset_id).exists():
        raise PermissionDenied("این اسنپ‌شات متعلق به مرکز مجاز شما نیست.")
    if request.method == "POST":
        from .services import approve_snapshot

        approve_snapshot(snapshot, request.user)
        if snapshot.is_baseline:
            messages.success(request, "اسنپ‌شات پایه تایید و قفل شد؛ از این پس تغییرات اقلام پایش می‌شود.")
        else:
            messages.success(request, "اسنپ‌شات تایید و قفل شد.")
    return redirect("assets:snapshot_detail", pk=pk)


@login_required
def snapshot_reject(request, pk: int):
    """برگشت اسنپ‌شات به ثبت‌کننده."""
    snapshot = get_object_or_404(HardwareSnapshot.objects.select_related("asset"), pk=pk)
    if not request.user.has_role("admin_it"):
        raise PermissionDenied("این اقدام فقط برای کارشناس فناوری اطلاعات مرکز است.")
    if not visible_assets(request.user).filter(pk=snapshot.asset_id).exists():
        raise PermissionDenied("این اسنپ‌شات متعلق به مرکز مجاز شما نیست.")
    if request.method == "POST":
        from .services import reject_snapshot

        reject_snapshot(snapshot, request.user, request.POST.get("note", ""))
        messages.warning(request, "اسنپ‌شات برای اصلاح برگشت داده شد.")
    return redirect("assets:snapshot_detail", pk=pk)


@login_required
def snapshot_pending_list(request):
    """کارتابل اسنپ‌شات‌های در انتظار تایید."""
    if not request.user.has_role("admin_it"):
        raise PermissionDenied("دسترسی ندارید.")
    snapshots = HardwareSnapshot.objects.filter(
        status="pending",
        asset__in=visible_assets(request.user),
    ).select_related("asset", "recorded_by")
    return render(
        request,
        "assets/snapshot_pending.html",
        {
            "snapshots": snapshots,
            "page_title": "اسنپ‌شات‌های در انتظار تایید",
            "active_menu": "hardware",
        },
    )


# ---------------------------------------------------------------------------
# پیوست‌ها
# ---------------------------------------------------------------------------
class AttachmentCreateView(RepairStaffRequiredMixin, PageContextMixin, CreateView):
    model = AssetAttachment
    form_class = AssetAttachmentForm
    template_name = "assets/attachment_form.html"
    page_title = "افزودن پیوست به دارایی"
    active_menu = "assets"

    def dispatch(self, request, *args, **kwargs):
        self.asset = get_object_or_404(visible_assets(request.user), pk=kwargs["asset_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["asset"] = self.asset
        return context

    def form_valid(self, form):
        form.instance.asset = self.asset
        form.instance.uploaded_by = self.request.user
        response = super().form_valid(form)
        log_action("create", self.object, user=self.request.user)
        messages.success(self.request, "پیوست ثبت شد.")
        return response

    def get_success_url(self):
        return reverse("assets:detail", args=[self.asset.pk])


@login_required
def attachment_download(request, pk: int):
    """Serve an attachment only after checking access to its owning asset."""
    attachment = get_object_or_404(
        AssetAttachment.objects.select_related("asset"),
        pk=pk,
    )
    if not visible_assets(request.user).filter(pk=attachment.asset_id).exists():
        raise PermissionDenied("این پیوست متعلق به دارایی خارج از دامنه مجاز شماست.")
    if not attachment.file:
        raise Http404("فایل پیوست موجود نیست.")
    filename = attachment.file.name.rsplit("/", 1)[-1]
    content_type, _ = mimetypes.guess_type(filename)
    response = FileResponse(
        attachment.file.open("rb"),
        as_attachment=True,
        filename=filename,
        content_type=content_type or "application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def snapshot_file(request, pk: int, kind: str):
    """Serve snapshot photos only to users who can view the owning asset."""
    snapshot = get_object_or_404(
        HardwareSnapshot.objects.select_related("asset"),
        pk=pk,
    )
    if not visible_assets(request.user).filter(pk=snapshot.asset_id).exists():
        raise PermissionDenied("این فایل متعلق به دارایی خارج از دامنه مجاز شماست.")
    allowed_fields = {"case_photo", "seal_photo"}
    if kind not in allowed_fields:
        raise Http404("نوع فایل معتبر نیست.")
    file_field = getattr(snapshot, kind)
    if not file_field:
        raise Http404("فایل تصویر موجود نیست.")
    filename = file_field.name.rsplit("/", 1)[-1]
    content_type, _ = mimetypes.guess_type(filename)
    response = FileResponse(
        file_field.open("rb"),
        as_attachment=False,
        filename=filename,
        content_type=content_type or "application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def snapshot_item_photo(request, pk: int):
    """Serve an individual component photo through the snapshot's asset scope."""
    item = get_object_or_404(
        SnapshotItem.objects.select_related("snapshot__asset"),
        pk=pk,
    )
    if not visible_assets(request.user).filter(pk=item.snapshot.asset_id).exists():
        raise PermissionDenied("این عکس متعلق به دارایی خارج از دامنه مجاز شماست.")
    if not item.photo:
        raise Http404("فایل تصویر موجود نیست.")
    filename = item.photo.name.rsplit("/", 1)[-1]
    content_type, _ = mimetypes.guess_type(filename)
    response = FileResponse(
        item.photo.open("rb"),
        as_attachment=False,
        filename=filename,
        content_type=content_type or "application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def attachment_delete(request, pk: int):
    attachment = get_object_or_404(AssetAttachment.objects.select_related("asset"), pk=pk)
    if not request.user.has_role("admin_it"):
        raise PermissionDenied("حذف پیوست فقط توسط کارشناس IT امکان‌پذیر است.")
    if not visible_assets(request.user).filter(pk=attachment.asset_id).exists():
        raise PermissionDenied("این پیوست متعلق به دارایی خارج از دامنه مجاز شماست.")
    asset_pk = attachment.asset_id
    if request.method == "POST":
        label = str(attachment)
        attachment.file.delete(save=False)
        attachment.delete()
        log_action("delete", None, model_name="AssetAttachment", object_id=pk,
                   object_label=label, user=request.user)
        messages.success(request, "پیوست حذف شد.")
    return redirect("assets:detail", pk=asset_pk)


# ---------------------------------------------------------------------------
# گونه‌های دارایی و قطعات
# ---------------------------------------------------------------------------
class CategoryListView(AdminItRequiredMixin, BaseListView):
    model = AssetCategory
    template_name = "assets/category_list.html"
    page_title = "گونه‌های دارایی"
    active_menu = "settings"
    paginate_by = 30

    def get_queryset(self):
        return AssetCategory.objects.annotate(assets_total=Count("assets", distinct=True)).order_by("name")


class CategoryCreateView(AdminItRequiredMixin, BaseCreateView):
    model = AssetCategory
    form_class = CategoryForm
    template_name = "assets/simple_form.html"
    page_title = "افزودن گونه دارایی"
    active_menu = "settings"
    success_url = reverse_lazy("assets:category_list")
    success_message = "گونه دارایی ثبت شد."


class CategoryUpdateView(AdminItRequiredMixin, BaseUpdateView):
    model = AssetCategory
    form_class = CategoryForm
    template_name = "assets/simple_form.html"
    page_title = "ویرایش گونه دارایی"
    active_menu = "settings"
    success_url = reverse_lazy("assets:category_list")


class ComponentTypeListView(AdminItRequiredMixin, BaseListView):
    model = ComponentType
    template_name = "assets/component_type_list.html"
    page_title = "گونه‌های قطعه سخت‌افزاری"
    active_menu = "settings"
    paginate_by = 40

    def get_queryset(self):
        return ComponentType.objects.annotate(items_total=Count("snapshot_items", distinct=True)).order_by(
            "sort_order", "name"
        )


class ComponentTypeCreateView(AdminItRequiredMixin, BaseCreateView):
    model = ComponentType
    form_class = ComponentTypeForm
    template_name = "assets/simple_form.html"
    page_title = "افزودن گونه قطعه"
    active_menu = "settings"
    success_url = reverse_lazy("assets:component_type_list")
    success_message = "گونه قطعه ثبت شد."


class ComponentTypeUpdateView(AdminItRequiredMixin, BaseUpdateView):
    model = ComponentType
    form_class = ComponentTypeForm
    template_name = "assets/simple_form.html"
    page_title = "ویرایش گونه قطعه"
    active_menu = "settings"
    success_url = reverse_lazy("assets:component_type_list")


def hardware_change_report(request):
    """گزارش تغییرات اقلام سخت‌افزاری (پایش سرقت)."""
    rows = []
    queryset = (
        HardwareSnapshot.objects.filter(asset__in=visible_assets(request.user))
        .exclude(diff_data={})
        .select_related("asset", "recorded_by", "it_confirmed_by")
        .order_by("-created_at")[:100]
    )
    for snapshot in queryset:
        changes = snapshot.changed_items
        if not changes:
            continue
        rows.append({"snapshot": snapshot, "changes": changes})
    return render(
        request,
        "assets/hardware_change_report.html",
        {
            "rows": rows,
            "page_title": "گزارش تغییر اقلام سخت‌افزاری",
            "active_menu": "hardware",
        },
    )


# ---------------------------------------------------------------------------
# ادغام ایجنت سخت‌افزاری HWAgent
# ---------------------------------------------------------------------------
def asset_hwagent_upload(request, asset_pk: int):
    """بارگذاری مستقیم فایل JSON خروجی HWAgent برای یک دارایی مشخص."""
    asset = get_object_or_404(visible_assets(request.user), pk=asset_pk)
    if not can_record_snapshot(request.user, asset):
        messages.error(request, "اجازه ثبت اسنپ‌شات برای این تجهیز را ندارید.")
        return redirect("assets:detail", pk=asset.pk)

    if request.method != "POST":
        return render(
            request,
            "assets/hwagent_upload.html",
            {
                "asset": asset,
                "page_title": f"بارگذاری اسنپ‌شات HWAgent برای {asset.asset_tag}",
                "active_menu": "assets",
            },
        )

    json_file = request.FILES.get("json_file")
    raw_content = request.POST.get("json_content", "").strip()

    if not json_file and not raw_content:
        messages.error(request, "لطفاً یک فایل JSON انتخاب کنید یا محتوای آن را الصاق نمایید.")
        return redirect("assets:hwagent_upload", asset_pk=asset.pk)

    try:
        content = json_file.read().decode("utf-8", errors="replace") if json_file else raw_content
        note = request.POST.get("note", "").strip() or f"بارگذاری فایل {getattr(json_file, 'name', 'دستی')}"
        seal = request.POST.get("seal_number", "").strip()

        snapshot, diff = apply_hwagent_snapshot(
            asset=asset,
            raw_data=content,
            user=request.user,
            note=note,
            seal_number=seal,
        )

        if diff.get("has_alarm"):
            messages.warning(
                request,
                f"⚠️ اسنپ‌شات با {snapshot.diff_count} تغییر ثبت شد. قطعات مفقود یا تعویض‌شده شناسایی شدند!",
            )
        else:
            messages.success(
                request,
                f"✅ اسنپ‌شات نسخه {snapshot.version} با موفقیت از داده‌های HWAgent ثبت شد.",
            )
        return redirect("assets:snapshot_detail", pk=snapshot.pk)

    except Exception as exc:
        messages.error(request, f"خطا در پردازش اطلاعات HWAgent: {exc}")
        return redirect("assets:hwagent_upload", asset_pk=asset.pk)


def hwagent_batch_import(request):
    """بارگذاری دسته‌ای فایل‌های JSON تولید شده توسط HWAgent با اعتبارسنجی قطعی دامنه مرکز."""
    if not (request.user.is_superuser or request.user.has_role("admin_it", "admin_province", "admin_country", "admin_county")):
        raise PermissionDenied("فقط کارشناسان فناوری اطلاعات به بارگذاری دسته‌ای دسترسی دارند.")

    from apps.org.models import Center

    scoped_centers = request.user.get_scoped_centers().filter(is_active=True)

    if request.method == "POST":
        files = request.FILES.getlist("files")
        if not files:
            messages.error(request, "هیچ فایلی برای بارگذاری انتخاب نشده است.")
            return redirect("assets:hwagent_batch_import")

        # استخراج مرکز منحصراً بر اساس دامنه احراز هویت شده کاربر
        if request.user.is_superuser or request.user.has_role("admin_country", "admin_province", "admin_county"):
            center_id = request.POST.get("center")
            if center_id:
                center = scoped_centers.filter(pk=center_id).first()
                if not center:
                    raise PermissionDenied("مرکز انتخاب‌شده خارج از دامنه مجاز شما است.")
            else:
                center = getattr(request.user, "center", None) or scoped_centers.first()
        else:
            # برای کارشناس مرکز، مقدار ارسالی فرم کلاینت نادیده گرفته شده و صرفاً مرکز خود کاربر اعمال می‌شود
            center = request.user.center
            if not center:
                raise PermissionDenied("کاربر به هیچ مرکزی منتسب نشده است.")

        auto_create = request.POST.get("auto_create") == "on"

        with transaction.atomic():
            results = process_batch_hwagent_files(
                files=files,
                user=request.user,
                center=center,
                auto_create_asset=auto_create,
            )

        if results["success"] > 0:
            messages.success(
                request,
                f"{results['success']} فایل با موفقیت پردازش شد. (تعداد هشدار مغایرت: {results['alarms']})",
            )
        if results["failed"] > 0:
            messages.warning(
                request,
                f"{results['failed']} فایل به دلیل عدم تطبیق یا خطا پردازش نشدند.",
            )

        return render(
            request,
            "assets/hwagent_batch_import.html",
            {
                "results": results,
                "centers": scoped_centers,
                "page_title": "نتیجه بارگذاری دسته‌ای HWAgent",
                "active_menu": "assets",
            },
        )

    return render(
        request,
        "assets/hwagent_batch_import.html",
        {
            "centers": scoped_centers,
            "page_title": "بارگذاری دسته‌ای فایل‌های HWAgent",
            "active_menu": "assets",
        },
    )


@csrf_exempt
def api_hwagent_sync(request):
    """اندپوینت ایمن دریافت مستقیم و برخط اسنپ‌شات از کلاینت‌های فیزیکی HWAgent.

    سیاست‌های امنیتی اجراشده:
    ۱. احراز هویت با Bearer Token اختصاصی هر کلاینت (One-way hashed).
    ۲. مقابله با حملات تکرار (Anti-Replay) با بررسی Timestamp و Nonce یکتا با تضمین اتمیک پایگاه داده (IntegrityError).
    ۳. انقیاد قطعی به مرکز (Center-Binding) بدون اعتماد به Payload کلاینت.
    ۴. تراکنش اتمیک و ثبت کامل لاگ ممیزی (Audit Logging).
    ۵. پاکسازی کامل پاسخ‌ها از هرگونه اطلاعات فنی داخلی (Error Sanitization) و استفاده از Tracking ID برای ارجاع به لاگ‌های سرور.
    """
    start_time = time.time()
    tracking_id = uuid.uuid4().hex[:12]
    remote_ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR")

    if request.method != "POST":
        return JsonResponse({"status": "error", "error": "فقط متد POST مجاز است."}, status=405)

    try:
        # ۱. استخراج و اعتبارسنجی هدر Authorization
        auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JsonResponse(
                {"status": "error", "error": "اعتبارنامه نامعتبر است (Bearer Token الزامی است)."},
                status=401,
            )

        raw_token = auth_header[7:].strip()
        agent = AgentCredential.verify_token(raw_token)
        if not agent:
            AgentSyncAuditLog.objects.create(
                agent=None,
                center=None,
                remote_ip=remote_ip,
                http_status=401,
                success=False,
                rejection_reason="توکن ایجنت نامعتبر، منقضی یا باطل شده است",
                execution_duration_ms=int((time.time() - start_time) * 1000),
            )
            return JsonResponse(
                {"status": "error", "error": "اعتبارنامه نامعتبر است یا منقضی/ابطال شده است."},
                status=401,
            )

        # ۲. بررسی هدر Timestamp و مقابله با انحراف ساعت (Anti-Clock Skew)
        timestamp_header = request.headers.get("X-ITAM-Timestamp") or request.META.get("HTTP_X_ITAM_TIMESTAMP", "")
        if not timestamp_header:
            AgentSyncAuditLog.objects.create(
                agent=agent,
                center=agent.center,
                remote_ip=remote_ip,
                http_status=401,
                success=False,
                rejection_reason="هدر X-ITAM-Timestamp ارسال نشده است",
                execution_duration_ms=int((time.time() - start_time) * 1000),
            )
            return JsonResponse(
                {"status": "error", "error": "هدر زمان‌سنجی (X-ITAM-Timestamp) الزامی است."},
                status=401,
            )

        req_dt = None
        try:
            req_dt = parse_datetime(timestamp_header)
            if not req_dt:
                req_dt = datetime.fromtimestamp(float(timestamp_header), tz=dt_timezone.utc)
        except Exception:
            pass

        if not req_dt:
            return JsonResponse(
                {"status": "error", "error": "قالب هدر X-ITAM-Timestamp نامعتبر است."},
                status=401,
            )

        now = timezone.now()
        if timezone.is_naive(req_dt):
            req_dt = timezone.make_aware(req_dt, dt_timezone.utc)

        skew_seconds = abs((now - req_dt).total_seconds())
        if skew_seconds > 300:
            AgentSyncAuditLog.objects.create(
                agent=agent,
                center=agent.center,
                remote_ip=remote_ip,
                http_status=401,
                success=False,
                rejection_reason=f"انحراف زمانی بیش از ۳۰۰ ثانیه ({int(skew_seconds)} ثانیه)",
                execution_duration_ms=int((time.time() - start_time) * 1000),
            )
            return JsonResponse(
                {"status": "error", "error": f"انحراف زمانی بیش از ۳۰۰ ثانیه است (Clock skew: {int(skew_seconds)}s)."},
                status=401,
            )

        # ۳. بررسی Nonce و مقابله با حمله تکرار (Anti-Replay) با درج اتمیک در دیتابیس
        nonce = (request.headers.get("X-ITAM-Nonce") or request.META.get("HTTP_X_ITAM_NONCE", "")).strip()
        if not nonce:
            return JsonResponse(
                {"status": "error", "error": "هدر شناسه یکتای درخواست (X-ITAM-Nonce) الزامی است."},
                status=401,
            )

        # درج اتمیک Nonce جهت پیشگیری قطعی از شرایط رقابتی همزمان (Race Condition)
        try:
            with transaction.atomic():
                AgentNonce.objects.create(agent=agent, nonce=nonce)
        except IntegrityError:
            AgentSyncAuditLog.objects.create(
                agent=agent,
                center=agent.center,
                remote_ip=remote_ip,
                http_status=401,
                success=False,
                rejection_reason=f"حمله تکرار همزمان یا استفاده مجدد از شناسه یکتا (Nonce Collision / Replay Attack): {nonce}",
                execution_duration_ms=int((time.time() - start_time) * 1000),
            )
            return JsonResponse(
                {"status": "error", "error": "شناسه درخواست تکراری است (Replay attack detected)."},
                status=401,
            )

        # ۴. دریافت بدنه درخواست و محاسبه هش
        raw_body = request.body
        payload_hash = hashlib.sha256(raw_body).hexdigest()
        try:
            if request.content_type == "application/json" or raw_body:
                body = json.loads(raw_body.decode("utf-8"))
            else:
                body = request.POST.dict()
        except Exception as exc:
            AgentSyncAuditLog.objects.create(
                agent=agent,
                center=agent.center,
                remote_ip=remote_ip,
                http_status=400,
                success=False,
                rejection_reason=f"قالب JSON نامعتبر: {exc}",
                payload_hash=payload_hash,
                execution_duration_ms=int((time.time() - start_time) * 1000),
            )
            return JsonResponse(
                {"status": "error", "error": "قالب ارسالی نامعتبر است (JSON غیراستاندارد)."},
                status=400,
            )

        # ۵. انقیاد قطعی مرکز و تطبیق دارایی
        target_center = agent.center
        asset_tag = body.get("asset_tag") or request.GET.get("asset_tag")

        with transaction.atomic():
            asset = match_asset_for_hwagent(body, center=target_center, asset_tag=asset_tag)
            if not asset:
                comp = body.get("computerName", "نامشخص")
                AgentSyncAuditLog.objects.create(
                    agent=agent,
                    center=target_center,
                    remote_ip=remote_ip,
                    http_status=404,
                    success=False,
                    rejection_reason=f"عدم تطبیق دارایی برای کلاینت {comp} در مرکز {target_center.name}",
                    payload_hash=payload_hash,
                    execution_duration_ms=int((time.time() - start_time) * 1000),
                )
                return JsonResponse(
                    {
                        "status": "error",
                        "error": f"دارایی متناظری برای سیستم «{comp}» در مرکز «{target_center.name}» یافت نشد.",
                    },
                    status=404,
                )

            try:
                snapshot, diff = apply_hwagent_snapshot(
                    asset=asset,
                    raw_data=body,
                    user=None,
                    note=f"همگام‌سازی از کلاینت {agent.name} با توکن اختصاصی",
                )
                agent.last_sync_at = timezone.now()
                agent.last_ip = remote_ip
                agent.save(update_fields=["last_sync_at", "last_ip", "updated_at"])

                duration = int((time.time() - start_time) * 1000)
                AgentSyncAuditLog.objects.create(
                    agent=agent,
                    center=target_center,
                    remote_ip=remote_ip,
                    http_status=200,
                    success=True,
                    payload_hash=payload_hash,
                    execution_duration_ms=duration,
                )
                return JsonResponse({
                    "status": "ok",
                    "asset_tag": asset.asset_tag,
                    "asset_title": str(asset),
                    "hostname": asset.hostname,
                    "version": snapshot.version,
                    "is_baseline": snapshot.is_baseline,
                    "diff_count": snapshot.diff_count,
                    "has_alarm": diff.get("has_alarm", False),
                    "message": f"اسنپ‌شات سخت‌افزاری نسخه {snapshot.version} با موفقیت در سامانه ITAM ثبت شد.",
                })
            except Exception as exc:
                logger.error(
                    "Error applying hwagent snapshot for agent %s on asset %s (tracking_id=%s): %s",
                    agent.name,
                    asset.asset_tag,
                    tracking_id,
                    exc,
                    exc_info=True,
                )
                duration = int((time.time() - start_time) * 1000)
                AgentSyncAuditLog.objects.create(
                    agent=agent,
                    center=target_center,
                    remote_ip=remote_ip,
                    http_status=500,
                    success=False,
                    rejection_reason=f"خطای سرور در ذخیره‌سازی اسنپ‌شات [tracking_id: {tracking_id}]: {exc}",
                    payload_hash=payload_hash,
                    execution_duration_ms=duration,
                )
                return JsonResponse(
                    {
                        "status": "error",
                        "error": "خطای داخلی سرور در پردازش اسنپ‌شات سخت‌افزاری رخ داد.",
                        "tracking_id": tracking_id,
                    },
                    status=500,
                )

    except Exception as exc:
        logger.error(
            "Unhandled exception in api_hwagent_sync (tracking_id=%s): %s",
            tracking_id,
            exc,
            exc_info=True,
        )
        return JsonResponse(
            {
                "status": "error",
                "error": "خطای غیرمنتظره سرور در پردازش درخواست رخ داد.",
                "tracking_id": tracking_id,
            },
            status=500,
        )
