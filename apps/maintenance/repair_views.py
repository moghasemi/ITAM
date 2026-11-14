"""HTTP views for repairers, independent repairs, referrals and general IT requests."""
from __future__ import annotations

from django.contrib import messages
from django.db.models import Avg, Count
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import User

from .repair_forms import (
    FeedbackReplyForm,
    GeneralITAssignForm,
    GeneralITEscalateForm,
    GeneralITManagerDecisionForm,
    GeneralITRequestForm,
    GeneralITResolveForm,
    IndependentRepairerForm,
    ReferralCreateForm,
    ReferralResolveForm,
    RepairCompletionForm,
    RepairDecisionForm,
    RepairRequestForm,
)
from .repair_models import (
    GeneralITRequest, GeneralReferral, IndependentRepairer, RepairFeedback,
    RepairerProfileEvent, RepairRequest,
)
from .repair_services import (
    add_feedback_reply,
    assign_general_it_request,
    complete_repair_request,
    create_general_it_request,
    create_referral,
    create_repair_request,
    decide_repair_request,
    escalate_general_it_request,
    manager_decide_general_it_request,
    resolve_general_it_request,
    resolve_referral,
    resolve_repair_cost_dispute,
    resubmit_repair_request,
    set_repairer_active,
    visible_repair_feedback,
    visible_repairers,
    visible_repair_requests,
)


def _require_it_staff(user):
    if not user.is_authenticated or (user.role != User.ROLE_ADMIN_IT and not user.is_admin_country and not user.is_admin_province):
        raise PermissionDenied("این بخش فقط برای مدیران و کارشناسان فناوری اطلاعات مجاز است.")


@login_required
def repairer_list(request):
    _require_it_staff(request.user)
    rows = visible_repairers(request.user).annotate(
        repair_count=Count("repair_requests", distinct=True),
        average_quality=Avg("feedback__work_quality"),
        average_speed=Avg("feedback__completion_speed"),
        average_cost_fairness=Avg("feedback__cost_fairness"),
    ).prefetch_related("status_events", "profile_events")
    return render(request, "maintenance/workflow_list.html", {
        "page_title": "تعمیرکاران مستقل",
        "kind": "repairers",
        "rows": rows,
        "active_menu": "repairs",
        "can_create": True,
    })


@login_required
def repairer_create(request):
    _require_it_staff(request.user)
    form = IndependentRepairerForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.updated_by = request.user
        allowed_provinces = set(
            request.user.get_scoped_centers().values_list(
                "treatment_management__province_id", flat=True
            )
        )
        if not request.user.is_admin_country and obj.province_id not in allowed_provinces:
            raise PermissionDenied("استان انتخاب‌شده خارج از حوزه مجاز شماست.")
        obj.save()
        RepairerProfileEvent.objects.create(
            repairer=obj, action="created", previous_values={},
            new_values={
                "name": obj.name, "kind": obj.kind, "national_id": obj.national_id,
                "phone": obj.phone, "email": obj.email, "address": obj.address,
                "specialties": obj.specialties, "notes": obj.notes,
            },
            actor=request.user,
        )
        messages.success(request, "تعمیرکار مستقل ثبت شد.")
        return redirect("maintenance:repairer_list")
    return render(request, "maintenance/workflow_form.html", {
        "page_title": "ثبت تعمیرکار مستقل", "form": form, "active_menu": "repairs",
    })


@login_required
def repairer_update(request, pk: int):
    _require_it_staff(request.user)
    obj = get_object_or_404(visible_repairers(request.user), pk=pk)
    fields = ("name", "kind", "national_id", "phone", "email", "address", "specialties", "notes")
    # ModelForm validation mutates its instance in _post_clean; capture the
    # persisted values before binding/validating the submitted form.
    previous = {field: getattr(obj, field) for field in fields}
    form = IndependentRepairerForm(request.POST or None, instance=obj, user=request.user)
    if request.method == "POST" and form.is_valid():
        changed_fields = set(form.changed_data).intersection(fields)
        changed = form.save(commit=False)
        changed.updated_by = request.user
        changed.save()
        current = {field: getattr(changed, field) for field in fields}
        if changed_fields:
            RepairerProfileEvent.objects.create(
                repairer=changed, action="updated",
                previous_values=previous, new_values=current, actor=request.user,
            )
        messages.success(request, "مشخصات تعمیرکار ذخیره شد؛ نسخه قبلی و جدید در تاریخچه ممیزی حفظ شد.")
        return redirect("maintenance:repairer_list")
    return render(request, "maintenance/workflow_form.html", {
        "page_title": "ویرایش تعمیرکار مستقل", "form": form, "active_menu": "repairs",
    })


@login_required
def repairer_status(request, pk: int):
    _require_it_staff(request.user)
    if request.method != "POST":
        return redirect("maintenance:repairer_list")
    obj = get_object_or_404(visible_repairers(request.user), pk=pk)
    active = request.POST.get("active") == "1"
    try:
        set_repairer_active(
            repairer=obj, active=active,
            reason=request.POST.get("reason", ""), actor=request.user,
        )
        messages.success(request, "وضعیت تعمیرکار تغییر کرد و در تاریخچه ثبت شد.")
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, "؛ ".join(getattr(exc, "messages", [str(exc)])))
    return redirect("maintenance:repairer_list")


@login_required
def repair_list(request):
    _require_it_staff(request.user)
    rows = visible_repair_requests(request.user).select_related(
        "center", "asset", "repairer", "requested_by", "approved_by"
    )
    return render(request, "maintenance/workflow_list.html", {
        "page_title": "درخواست‌های تعمیر مستقل",
        "kind": "repairs",
        "rows": rows,
        "active_menu": "repairs",
        "can_create": True,
    })


@login_required
def repair_create(request):
    _require_it_staff(request.user)
    form = RepairRequestForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            repair = create_repair_request(
                center=data["center"], asset=data["asset"], repairer=data["repairer"],
                fault_description=data["fault_description"],
                referral_reason=data["referral_reason"],
                estimate_amount=data["estimate_amount"],
                estimate_attachment=data.get("estimate_attachment"),
                actor=request.user,
            )
            messages.success(request, "درخواست تعمیر برای تایید مدیر استان ارسال شد.")
            return redirect(repair.get_absolute_url())
        except (PermissionDenied, ValidationError) as exc:
            form.add_error(None, exc)
    return render(request, "maintenance/workflow_form.html", {
        "page_title": "ثبت درخواست تعمیر مستقل", "form": form, "active_menu": "repairs",
    })


@login_required
def repair_detail(request, pk: int):
    repair = get_object_or_404(
        visible_repair_requests(request.user).select_related(
            "center", "asset", "repairer", "requested_by", "approved_by",
            "cost_increase_approved_by",
        ).prefetch_related("events", "feedback__replies"),
        pk=pk,
    )
    province_admin = request.user.is_admin_province
    center_expert = (
        request.user.has_role(User.ROLE_ADMIN_IT)
        and request.user.get_scoped_centers().filter(pk=repair.center_id).exists()
    )
    feedback = getattr(repair, "feedback", None)
    return render(request, "maintenance/repair_detail.html", {
        "page_title": f"درخواست تعمیر {repair.number}",
        "repair": repair,
        "events": repair.events.select_related("actor"),
        "feedback": feedback,
        "reply_form": FeedbackReplyForm(),
        "decision_form": RepairDecisionForm(),
        "completion_form": RepairCompletionForm(),
        "can_decide": province_admin,
        "can_complete": center_expert and (request.user.role == User.ROLE_ADMIN_IT or request.user.is_admin_country),
        "can_reply": (
            feedback is not None
            and (request.user.role == User.ROLE_ADMIN_IT or request.user.is_admin_province)
            and visible_repair_feedback(request.user).filter(pk=feedback.pk).exists()
        ),
        "active_menu": "repairs",
    })


@login_required
def repair_decide(request, pk: int):
    repair = get_object_or_404(visible_repair_requests(request.user), pk=pk)
    form = RepairDecisionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            decide_repair_request(
                repair=repair, decision=form.cleaned_data["decision"],
                note=form.cleaned_data.get("note", ""), actor=request.user,
            )
            messages.success(request, "تصمیم مدیر استان ثبت شد.")
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, "؛ ".join(getattr(exc, "messages", [str(exc)])))
    return redirect("maintenance:repair_detail", pk=pk)


@login_required
def repair_resubmit(request, pk: int):
    repair = get_object_or_404(visible_repair_requests(request.user), pk=pk)
    form = RepairRequestForm(request.POST or None, request.FILES or None, instance=repair, user=request.user)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            resubmit_repair_request(
                repair=repair, actor=request.user,
                fault_description=data["fault_description"],
                referral_reason=data["referral_reason"],
                estimate_amount=data["estimate_amount"],
                estimate_attachment=data.get("estimate_attachment"),
            )
            messages.success(request, "درخواست اصلاح و مجدداً ارسال شد.")
            return redirect(repair.get_absolute_url())
        except (PermissionDenied, ValidationError) as exc:
            form.add_error(None, exc)
    return render(request, "maintenance/workflow_form.html", {
        "page_title": "اصلاح درخواست تعمیر", "form": form, "active_menu": "repairs",
    })


@login_required
def repair_complete(request, pk: int):
    repair = get_object_or_404(visible_repair_requests(request.user), pk=pk)
    form = RepairCompletionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            complete_repair_request(
                repair=repair, actor=request.user,
                outcome=data["outcome"], final_cost=data["final_cost"],
                final_cost_reason=data.get("final_cost_reason", ""),
                completion_attachment=data.get("completion_attachment"),
                work_quality=data["work_quality"],
                completion_speed=data["completion_speed"],
                cost_fairness=data["cost_fairness"],
                comment=data.get("comment", ""),
            )
            messages.success(request, "نتیجه تعمیر و سه امتیاز ارزیابی ثبت شد.")
            return redirect("maintenance:repair_detail", pk=pk)
        except (PermissionDenied, ValidationError) as exc:
            form.add_error(None, exc)
    return render(request, "maintenance/workflow_form.html", {
        "page_title": "ثبت نتیجه تعمیر و ارزیابی", "form": form, "active_menu": "repairs",
    })


@login_required
def repair_cost_resolve(request, pk: int):
    repair = get_object_or_404(visible_repair_requests(request.user), pk=pk)
    if request.method == "POST":
        decision = request.POST.get("decision", "")
        note = request.POST.get("note", "")
        try:
            resolve_repair_cost_dispute(
                repair=repair, decision=decision, note=note, actor=request.user,
                attachment=request.FILES.get("attachment"),
            )
            messages.success(request, "تعیین تکلیف اختلاف هزینه ثبت شد.")
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, "؛ ".join(getattr(exc, "messages", [str(exc)])))
    return redirect("maintenance:repair_detail", pk=pk)


@login_required
def feedback_list(request):
    _require_it_staff(request.user)
    rows = visible_repair_feedback(request.user).select_related(
        "repair_request", "repairer", "center", "author"
    ).prefetch_related("replies__author")
    return render(request, "maintenance/workflow_list.html", {
        "page_title": "ارزیابی و بازخورد تعمیرکاران استان",
        "kind": "feedback",
        "rows": rows,
        "active_menu": "repairs",
        "can_create": False,
    })


@login_required
def feedback_reply(request, pk: int):
    _require_it_staff(request.user)
    feedback = get_object_or_404(visible_repair_feedback(request.user), pk=pk)
    form = FeedbackReplyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            add_feedback_reply(
                feedback=feedback, body=form.cleaned_data["body"], actor=request.user,
            )
            messages.success(request, "پاسخ ثبت شد.")
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, "؛ ".join(getattr(exc, "messages", [str(exc)])))
    return redirect("maintenance:repair_detail", pk=feedback.repair_request_id)


@login_required
def referral_list(request):
    if not request.user.is_authenticated:
        raise PermissionDenied("ورود به سامانه الزامی است.")
    rows = GeneralReferral.objects.select_related("center", "repair_request", "created_by")
    can_create = request.user.role == User.ROLE_ADMIN_IT or request.user.is_admin_province
    if not request.user.is_admin_country:
        from django.db.models import Q
        if can_create:
            rows = rows.filter(
                Q(center__in=request.user.get_scoped_centers()) | Q(recipient_user=request.user)
            )
        else:
            rows = rows.filter(recipient_user=request.user)
    return render(request, "maintenance/workflow_list.html", {
        "page_title": "ارجاع‌های عمومی",
        "kind": "referrals",
        "rows": rows,
        "active_menu": "referrals",
        "can_create": can_create,
    })


@login_required
def referral_create(request):
    _require_it_staff(request.user)
    form = ReferralCreateForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            referral = create_referral(
                subject=data["subject"], description=data["description"],
                recipient_role=data["recipient_role"], recipient_name=data["recipient_name"],
                recipient_user=data.get("recipient_user"), center=data.get("center"),
                repair_request=data.get("repair_request"), attachment=data.get("attachment"),
                actor=request.user,
            )
            messages.success(request, "ارجاع ثبت شد.")
            return redirect("maintenance:referral_list")
        except (PermissionDenied, ValidationError) as exc:
            form.add_error(None, exc)
    return render(request, "maintenance/workflow_form.html", {
        "page_title": "ثبت ارجاع عمومی", "form": form, "active_menu": "referrals",
    })


@login_required
def referral_resolve(request, pk: int):
    referral = get_object_or_404(GeneralReferral.objects.all(), pk=pk)
    if referral.center_id and not request.user.get_scoped_centers().filter(pk=referral.center_id).exists() and not request.user.is_admin_country and referral.recipient_user_id != request.user.pk:
        raise PermissionDenied("ارجاع خارج از حوزه مجاز شماست.")
    form = ReferralResolveForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            resolve_referral(
                referral=referral, outcome=form.cleaned_data["outcome"],
                instruction=form.cleaned_data.get("instruction", ""), actor=request.user,
                attachment=form.cleaned_data.get("attachment"),
            )
            messages.success(request, "نتیجه ارجاع ثبت شد.")
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, "؛ ".join(getattr(exc, "messages", [str(exc)])))
    return redirect("maintenance:referral_list")


def _visible_it_requests(user):
    if not user or not user.is_authenticated:
        return GeneralITRequest.objects.none()
    if user.is_admin_country:
        return GeneralITRequest.objects.all()
    if user.role == User.ROLE_REQUESTER:
        return GeneralITRequest.objects.filter(requested_by=user)
    if user.role == User.ROLE_MANAGER:
        return GeneralITRequest.objects.filter(center_id=user.center_id)
    return GeneralITRequest.objects.filter(center__in=user.get_scoped_centers()) | GeneralITRequest.objects.filter(requested_by=user)


@login_required
def it_request_list(request):
    rows = _visible_it_requests(request.user).select_related("center", "requested_by", "assigned_to")
    return render(request, "maintenance/workflow_list.html", {
        "page_title": "درخواست‌های عمومی فناوری اطلاعات",
        "kind": "it_requests",
        "rows": rows.distinct(),
        "active_menu": "it_requests",
        "can_create": True,
    })


@login_required
def it_request_create(request):
    form = GeneralITRequestForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            obj = create_general_it_request(
                center=data["center"], request_type=data["request_type"],
                title=data["title"], description=data["description"],
                asset=data.get("asset"), actor=request.user,
            )
            messages.success(request, "درخواست ثبت شد.")
            return redirect("maintenance:it_request_detail", pk=obj.pk)
        except (PermissionDenied, ValidationError) as exc:
            form.add_error(None, exc)
    return render(request, "maintenance/workflow_form.html", {
        "page_title": "ثبت درخواست عمومی IT", "form": form, "active_menu": "it_requests",
    })


@login_required
def it_request_detail(request, pk: int):
    obj = get_object_or_404(_visible_it_requests(request.user), pk=pk)
    can_manage = request.user.role == User.ROLE_ADMIN_IT and request.user.get_scoped_centers().filter(pk=obj.center_id).exists()
    can_manager_review = request.user.role == User.ROLE_MANAGER and request.user.center_id == obj.center_id
    can_province_resolve = request.user.is_admin_province
    return render(request, "maintenance/it_request_detail.html", {
        "page_title": f"درخواست {obj.number}",
        "item": obj,
        "events": obj.events.select_related("actor"),
        "assign_form": GeneralITAssignForm(center=obj.center),
        "manager_form": GeneralITManagerDecisionForm(),
        "escalate_form": GeneralITEscalateForm(),
        "resolve_form": GeneralITResolveForm(),
        "can_manage": can_manage,
        "can_manager_review": can_manager_review,
        "can_province_resolve": can_province_resolve,
        "active_menu": "it_requests",
    })


@login_required
def it_request_assign(request, pk: int):
    obj = get_object_or_404(_visible_it_requests(request.user), pk=pk)
    form = GeneralITAssignForm(request.POST or None, center=obj.center)
    if request.method == "POST" and form.is_valid():
        try:
            assign_general_it_request(
                request=obj, expert=form.cleaned_data["expert"], actor=request.user,
            )
            messages.success(request, "درخواست به کارشناس IT ارجاع شد.")
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, "؛ ".join(getattr(exc, "messages", [str(exc)])))
    return redirect("maintenance:it_request_detail", pk=pk)


@login_required
def it_request_manager_decide(request, pk: int):
    obj = get_object_or_404(_visible_it_requests(request.user), pk=pk)
    form = GeneralITManagerDecisionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            manager_decide_general_it_request(
                request=obj, decision=form.cleaned_data["decision"],
                note=form.cleaned_data.get("note", ""), actor=request.user,
            )
            messages.success(request, "تصمیم مدیر مرکز ثبت شد.")
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, "؛ ".join(getattr(exc, "messages", [str(exc)])))
    return redirect("maintenance:it_request_detail", pk=pk)


@login_required
def it_request_escalate(request, pk: int):
    obj = get_object_or_404(_visible_it_requests(request.user), pk=pk)
    form = GeneralITEscalateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            escalate_general_it_request(
                request=obj, actor=request.user,
                bypass_reason=form.cleaned_data.get("bypass_reason", ""),
            )
            messages.success(request, "درخواست به مدیریت استانی ارسال شد.")
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, "؛ ".join(getattr(exc, "messages", [str(exc)])))
    return redirect("maintenance:it_request_detail", pk=pk)


@login_required
def it_request_resolve(request, pk: int):
    obj = get_object_or_404(_visible_it_requests(request.user), pk=pk)
    form = GeneralITResolveForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            resolve_general_it_request(
                request=obj, decision=form.cleaned_data["decision"], actor=request.user,
            )
            messages.success(request, "دستور استانی ثبت و درخواست مختومه شد.")
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, "؛ ".join(getattr(exc, "messages", [str(exc)])))
    return redirect("maintenance:it_request_detail", pk=pk)
