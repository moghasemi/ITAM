"""نماهای دارایی‌ها، اسنپ‌شات سخت‌افزاری ضدسرقت و برچسب QR."""
from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
import json
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
    ComponentType,
    HardwareSnapshot,
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
        context["can_edit"] = user.has_role("admin_it")
        context["can_snapshot"] = can_record_snapshot(user, asset)
        context["tracking_required"] = asset.requires_component_tracking
        context["is_it"] = user.has_role("admin_it")
        return context


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
        log_asset_created(self.object, self.request.user)
        return response


class AssetUpdateView(AdminItRequiredMixin, BaseUpdateView):
    model = Asset
    form_class = AssetForm
    template_name = "assets/asset_form.html"
    page_title = "ویرایش دارایی"
    active_menu = "assets"
    success_url_name = "assets:detail"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
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


def snapshot_approve(request, pk: int):
    """تایید و قفل اسنپ‌شات توسط کارشناس IT."""
    snapshot = get_object_or_404(HardwareSnapshot.objects.select_related("asset"), pk=pk)
    if not request.user.has_role("admin_it"):
        raise PermissionDenied("تایید اسنپ‌شات فقط توسط کارشناس فناوری اطلاعات مرکز انجام می‌شود.")
    if request.method == "POST":
        from .services import approve_snapshot

        approve_snapshot(snapshot, request.user)
        if snapshot.is_baseline:
            messages.success(request, "اسنپ‌شات پایه تایید و قفل شد؛ از این پس تغییرات اقلام پایش می‌شود.")
        else:
            messages.success(request, "اسنپ‌شات تایید و قفل شد.")
    return redirect("assets:snapshot_detail", pk=pk)


def snapshot_reject(request, pk: int):
    """برگشت اسنپ‌شات به ثبت‌کننده."""
    snapshot = get_object_or_404(HardwareSnapshot.objects.select_related("asset"), pk=pk)
    if not request.user.has_role("admin_it"):
        raise PermissionDenied("این اقدام فقط برای کارشناس فناوری اطلاعات مرکز است.")
    if request.method == "POST":
        from .services import reject_snapshot

        reject_snapshot(snapshot, request.user, request.POST.get("note", ""))
        messages.warning(request, "اسنپ‌شات برای اصلاح برگشت داده شد.")
    return redirect("assets:snapshot_detail", pk=pk)


def snapshot_pending_list(request):
    """کارتابل اسنپ‌شات‌های در انتظار تایید."""
    if not request.user.has_role("admin_it"):
        raise PermissionDenied("دسترسی ندارید.")
    snapshots = HardwareSnapshot.objects.filter(status="pending").select_related("asset", "recorded_by")
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


def attachment_delete(request, pk: int):
    attachment = get_object_or_404(AssetAttachment.objects.select_related("asset"), pk=pk)
    if not request.user.has_role("admin_it"):
        raise PermissionDenied("حذف پیوست فقط توسط کارشناس IT امکان‌پذیر است.")
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
    """بارگذاری دسته‌ای فایل‌های JSON تولید شده توسط HWAgent."""
    if not (request.user.is_superuser or request.user.has_role("admin_it", "admin_province")):
        raise PermissionDenied("فقط کارشناسان فناوری اطلاعات به بارگذاری دسته‌ای دسترسی دارند.")

    from apps.org.models import Center
    centers = Center.objects.filter(is_active=True)

    if request.method == "POST":
        files = request.FILES.getlist("files")
        if not files:
            messages.error(request, "هیچ فایلی برای بارگذاری انتخاب نشده است.")
            return redirect("assets:hwagent_batch_import")

        center_id = request.POST.get("center")
        center = Center.objects.filter(pk=center_id).first() if center_id else getattr(request.user, "center", None)
        auto_create = request.POST.get("auto_create") == "on"

        results = process_batch_hwagent_files(
            files=files,
            user=request.user,
            center=center,
            auto_create_asset=auto_create,
        )

        messages.info(
            request,
            f"عملیات پردازش پایان یافت: {results['success']} موفق، {results['failed']} ناموفق، {results['alarms']} هشدار سرقت/مغایرت.",
        )
        return render(
            request,
            "assets/hwagent_batch_import.html",
            {
                "results": results,
                "centers": centers,
                "selected_center": center,
                "page_title": "نتایج بارگذاری دسته‌ای HWAgent",
                "active_menu": "assets",
            },
        )

    return render(
        request,
        "assets/hwagent_batch_import.html",
        {
            "centers": centers,
            "user_center": getattr(request.user, "center", None),
            "page_title": "بارگذاری دسته‌ای فایل‌های JSON ایجنت سخت‌افزاری",
            "active_menu": "assets",
        },
    )


@csrf_exempt
def api_hwagent_sync(request):
    """اندپوینت دریافت مستقیم و برخط اسنپ‌شات از کلاینت‌های HWAgent."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "error": "فقط متد POST مجاز است."}, status=405)

    try:
        if request.content_type == "application/json" or request.body:
            body = json.loads(request.body.decode("utf-8"))
        else:
            body = request.POST.dict()
    except Exception as exc:
        return JsonResponse({"status": "error", "error": f"قالب ارسالی نامعتبر است: {exc}"}, status=400)

    asset_tag = body.get("asset_tag") or request.GET.get("asset_tag")
    asset = match_asset_for_hwagent(body, asset_tag=asset_tag)

    if not asset:
        comp = body.get("computerName", "نامشخص")
        return JsonResponse(
            {
                "status": "error",
                "error": f"دارایی متناظری برای سیستم «{comp}» در سامانه ITAM یافت نشد. لطفاً ابتدا رایانه را ثبت کرده یا شماره اموال آن را ارسال کنید.",
            },
            status=404,
        )

    try:
        snapshot, diff = apply_hwagent_snapshot(
            asset=asset,
            raw_data=body,
            user=None,
            note="همگام‌سازی خودکار و مستقیم از HWAgent شبکه محلی",
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
        return JsonResponse({"status": "error", "error": str(exc)}, status=500)
