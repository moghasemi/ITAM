"""Business rules for contractor assignments, independent repairs and referrals."""
from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import Notification
from apps.core.utils import log_action
from apps.org.models import ContractCenterAssignment, OrganizationalUnit

from .repair_models import (
    GeneralITRequest,
    GeneralITRequestEvent,
    GeneralReferral,
    IndependentRepairer,
    RepairFeedback,
    RepairFeedbackReply,
    RepairRequest,
    RepairRequestEvent,
    RepairerStatusEvent,
)


def _province_id_for_center(center):
    if not center or not center.treatment_management_id:
        return None
    return center.treatment_management.province_id


def _is_country_admin(user):
    return bool(user and user.is_authenticated and user.is_admin_country)


def _is_province_admin(user):
    return bool(user and user.is_authenticated and user.is_admin_province)


def _province_id_for_user(user):
    if not user:
        return None
    if user.org_unit_id and user.org_unit.unit_type == OrganizationalUnit.UNIT_PROVINCE:
        return user.org_unit_id
    if user.center_id and user.center.treatment_management_id:
        return user.center.treatment_management.province_id
    return None


def _can_manage_center(user, center):
    return bool(
        user and user.is_authenticated
        and center
        and user.get_scoped_centers().filter(pk=center.pk).exists()
    )


def _require_province_admin_for_center(user, center):
    if not _is_province_admin(user):
        raise PermissionDenied("این اقدام فقط برای مدیر فناوری اطلاعات استان مجاز است.")
    if not _is_country_admin(user):
        province_id = _province_id_for_center(center)
        if not province_id or _province_id_for_user(user) != province_id:
            raise PermissionDenied("مرکز خارج از حوزه استان مجاز شماست.")


def visible_repair_requests(user):
    from apps.maintenance.models import RepairRequest as Model
    if not user or not user.is_authenticated:
        return Model.objects.none()
    if _is_country_admin(user):
        return Model.objects.all()
    return Model.objects.filter(center__in=user.get_scoped_centers())


def visible_repairers(user):
    if not user or not user.is_authenticated:
        return IndependentRepairer.objects.none()
    if _is_country_admin(user):
        return IndependentRepairer.objects.all()
    if (user.is_admin_province or user.role == User.ROLE_ADMIN_IT) and _province_id_for_user(user):
        return IndependentRepairer.objects.filter(province_id=_province_id_for_user(user))
    province_ids = user.get_scoped_centers().values("treatment_management__province_id")
    return IndependentRepairer.objects.filter(province_id__in=province_ids).distinct()


def visible_repair_feedback(user):
    if not user or not user.is_authenticated:
        return RepairFeedback.objects.none()
    if _is_country_admin(user):
        return RepairFeedback.objects.select_related(
            "repairer", "center", "author", "repair_request"
        )
    province_ids = user.get_scoped_centers().values("treatment_management__province_id")
    # Provincial IT experts and the provincial IT head can review all feedback
    # in their province; center experts are limited to their assigned centers.
    if (user.is_admin_province or user.role == User.ROLE_ADMIN_IT) and _province_id_for_user(user):
        return RepairFeedback.objects.filter(
            center__treatment_management__province_id=_province_id_for_user(user)
        ).select_related("repairer", "center", "author", "repair_request")
    return RepairFeedback.objects.filter(
        center__in=user.get_scoped_centers()
    ).select_related("repairer", "center", "author", "repair_request")


def set_repairer_active(*, repairer, active, reason, actor):
    if not reason or not reason.strip():
        raise ValidationError("برای فعال یا غیرفعال کردن تعمیرکار، ثبت دلیل الزامی است.")
    if not actor or not actor.is_authenticated:
        raise PermissionDenied("کاربر معتبر لازم است.")
    if not (actor.is_admin_province or actor.role == User.ROLE_ADMIN_IT):
        raise PermissionDenied("اجازه مدیریت تعمیرکاران مستقل را ندارید.")
    if not visible_repairers(actor).filter(pk=repairer.pk).exists():
        raise PermissionDenied("تعمیرکار خارج از حوزه مجاز شماست.")
    with transaction.atomic():
        locked = IndependentRepairer.objects.select_for_update().get(pk=repairer.pk)
        previous = locked.is_active
        if previous == bool(active):
            return locked
        locked.is_active = bool(active)
        locked.updated_by = actor
        locked.save(update_fields=["is_active", "updated_by", "updated_at"])
        RepairerStatusEvent.objects.create(
            repairer=locked,
            previous_active=previous,
            new_active=bool(active),
            reason=reason.strip(),
            actor=actor,
        )
        return locked


@transaction.atomic
def assign_contractor_to_center(*, contract, center, start_date, actor):
    if not _is_province_admin(actor):
        raise PermissionDenied("انتساب پیمانکار رسمی فقط توسط مدیر استان انجام می‌شود.")
    if not _is_country_admin(actor) and (
        not center.treatment_management_id
        or center.treatment_management.province_id != _province_id_for_user(actor)
    ):
        raise PermissionDenied("مرکز خارج از استان مجاز شماست.")
    if not contract.is_current or not contract.is_provincial:
        raise ValidationError("فقط قرارداد استانیِ جاری قابل انتساب است.")
    assignment = ContractCenterAssignment(
        contract=contract,
        center=center,
        start_date=start_date,
        status=ContractCenterAssignment.STATUS_ACTIVE,
        assigned_by=actor,
    )
    assignment.full_clean()
    try:
        assignment.save()
    except IntegrityError as exc:
        raise ValidationError(
            "این مرکز هم‌اکنون پیمانکار رسمی فعال دارد؛ ابتدا انتساب قبلی را با ثبت دلیل پایان دهید."
        ) from exc
    log_action(
        "assign", assignment,
        changes={
            "center": {"از": "", "به": str(center)},
            "contract": {"از": "", "به": contract.number},
        },
        note="انتساب پیمانکار رسمی به مرکز ثبت شد.",
        user=actor,
    )
    return assignment


@transaction.atomic
def end_contractor_assignment(*, assignment, reason, actor, end_date=None):
    if not reason or not reason.strip():
        raise ValidationError("ثبت دلیل پایان انتساب الزامی است.")
    if not _is_province_admin(actor):
        raise PermissionDenied("فقط مدیر استان می‌تواند انتساب رسمی را پایان دهد.")
    if not _is_country_admin(actor) and (
        assignment.center.treatment_management.province_id != _province_id_for_user(actor)
    ):
        raise PermissionDenied("انتساب خارج از حوزه استان مجاز شماست.")
    locked = ContractCenterAssignment.objects.select_for_update().get(pk=assignment.pk)
    if locked.status != ContractCenterAssignment.STATUS_ACTIVE:
        raise ValidationError("فقط انتساب فعال قابل پایان دادن است.")
    locked.status = ContractCenterAssignment.STATUS_ENDED
    locked.end_date = end_date or timezone.localdate()
    locked.ended_by = actor
    locked.end_reason = reason.strip()
    locked.full_clean()
    locked.save(update_fields=[
        "status", "end_date", "ended_by", "end_reason", "updated_at"
    ])
    log_action(
        "end", locked,
        changes={
            "status": {"از": ContractCenterAssignment.STATUS_ACTIVE, "به": ContractCenterAssignment.STATUS_ENDED},
            "end_date": {"از": "", "به": str(locked.end_date)},
        },
        note=reason.strip(),
        user=actor,
    )
    return locked


def _record_repair_event(repair, action, note, actor, previous="", metadata=None):
    return RepairRequestEvent.objects.create(
        repair_request=repair,
        action=action,
        previous_status=previous,
        new_status=repair.status,
        note=note,
        metadata=metadata or {},
        actor=actor,
    )


@transaction.atomic
def create_repair_request(*, center, asset, repairer, fault_description,
                          referral_reason, estimate_amount, actor, estimate_attachment=None):
    if not actor or not actor.is_authenticated or (actor.role != User.ROLE_ADMIN_IT and not actor.is_admin_country):
        raise PermissionDenied("ثبت درخواست تعمیر فقط برای کارشناس فناوری اطلاعات مرکز مجاز است.")
    if not _can_manage_center(actor, center):
        raise PermissionDenied("مرکز خارج از حوزه مجاز شماست.")
    if asset.center_id != center.pk:
        raise ValidationError("دارایی انتخاب‌شده متعلق به مرکز درخواست نیست.")
    if not repairer.is_active:
        raise ValidationError("تعمیرکار غیرفعال برای درخواست جدید قابل انتخاب نیست.")
    province_id = _province_id_for_center(center)
    if not province_id or repairer.province_id != province_id:
        raise ValidationError("تعمیرکار باید در فهرست مشترک همان استان ثبت شده باشد.")
    if Decimal(estimate_amount) < 0:
        raise ValidationError("برآورد هزینه نمی‌تواند منفی باشد.")
    repair = RepairRequest(
        center=center, asset=asset, repairer=repairer,
        repairer_name_snapshot=repairer.name,
        fault_description=fault_description.strip(),
        referral_reason=referral_reason.strip(),
        estimate_amount=estimate_amount,
        estimate_attachment=estimate_attachment or "",
        requested_by=actor,
        status=RepairRequest.STATUS_PENDING,
        submitted_at=timezone.now(),
    )
    repair.full_clean()
    repair.save()
    _record_repair_event(
        repair, "submitted", "درخواست برای تایید مدیر استان ارسال شد.", actor,
        previous=RepairRequest.STATUS_DRAFT,
    )
    return repair


@transaction.atomic
def decide_repair_request(*, repair, decision, note, actor):
    _require_province_admin_for_center(actor, repair.center)
    if repair.status not in (RepairRequest.STATUS_PENDING, RepairRequest.STATUS_RETURNED):
        raise ValidationError("این درخواست در وضعیت قابل تصمیم‌گیری نیست.")
    if decision not in {"approve", "return", "reject"}:
        raise ValidationError("تصمیم نامعتبر است.")
    if decision in {"return", "reject"} and not (note or "").strip():
        raise ValidationError("برای عودت یا رد درخواست، توضیح الزامی است.")
    locked = RepairRequest.objects.select_for_update().get(pk=repair.pk)
    previous = locked.status
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.decision_note = (note or "").strip()
    if decision == "approve":
        locked.status = RepairRequest.STATUS_APPROVED
        action = "approved"
    elif decision == "return":
        locked.status = RepairRequest.STATUS_RETURNED
        action = "returned"
    else:
        locked.status = RepairRequest.STATUS_REJECTED
        locked.rejected_at = timezone.now()
        action = "rejected_final"
    locked.save(update_fields=[
        "status", "approved_by", "approved_at", "decision_note",
        "rejected_at", "updated_at",
    ])
    _record_repair_event(locked, action, locked.decision_note or "تایید شد.", actor, previous)
    Notification.push(
        locked.requested_by, "تصمیم درخواست تعمیر ثبت شد",
        f"{locked.number}: {locked.get_status_display()}",
        url=locked.get_absolute_url(),
        level="warning" if decision == "reject" else "info",
    )
    return locked


@transaction.atomic
def resubmit_repair_request(*, repair, actor, fault_description=None,
                            referral_reason=None, estimate_amount=None,
                            estimate_attachment=None):
    if not _can_manage_center(actor, repair.center) or (actor.role != User.ROLE_ADMIN_IT and not actor.is_admin_country):
        raise PermissionDenied("فقط کارشناس IT همان مرکز می‌تواند درخواست را اصلاح کند.")
    if repair.status != RepairRequest.STATUS_RETURNED:
        raise ValidationError("فقط درخواست عودت‌شده قابل اصلاح و ارسال مجدد است.")
    previous = repair.status
    if fault_description is not None:
        repair.fault_description = fault_description.strip()
    if referral_reason is not None:
        repair.referral_reason = referral_reason.strip()
    if estimate_amount is not None:
        repair.estimate_amount = estimate_amount
    if estimate_attachment:
        repair.estimate_attachment = estimate_attachment
    repair.status = RepairRequest.STATUS_PENDING
    repair.submitted_at = timezone.now()
    repair.full_clean()
    repair.save()
    _record_repair_event(repair, "resubmitted", "درخواست اصلاح و مجدداً ارسال شد.", actor, previous)
    return repair


@transaction.atomic
def complete_repair_request(*, repair, outcome, final_cost, actor,
                            work_quality, completion_speed, cost_fairness,
                            comment="", completion_attachment=None, final_cost_reason=""):
    if not _can_manage_center(actor, repair.center) or not actor.has_role(User.ROLE_ADMIN_IT):
        raise PermissionDenied("ثبت نتیجه تعمیر فقط برای کارشناس IT همان مرکز مجاز است.")
    if repair.status != RepairRequest.STATUS_APPROVED:
        raise ValidationError("فقط درخواست تاییدشده قابل ثبت نتیجه تعمیر است.")
    if not outcome or not outcome.strip():
        raise ValidationError("شرح نتیجه تعمیر الزامی است.")
    if final_cost is None or Decimal(final_cost) < 0:
        raise ValidationError("هزینه نهایی معتبر الزامی است.")
    for value in (work_quality, completion_speed, cost_fairness):
        if int(value) < 1 or int(value) > 5:
            raise ValidationError("هر سه امتیاز باید بین ۱ تا ۵ باشند.")
    if Decimal(final_cost) > repair.estimate_amount and not (final_cost_reason or "").strip():
        raise ValidationError("برای هزینه بالاتر از برآورد، توضیح افزایش هزینه الزامی است.")

    previous = repair.status
    repair.outcome = outcome.strip()
    repair.final_cost = final_cost
    repair.final_cost_reason = (final_cost_reason or "").strip()
    repair.completion_attachment = completion_attachment or ""
    repair.completed_at = timezone.now()
    disputed = Decimal(final_cost) > repair.estimate_amount
    repair.status = RepairRequest.STATUS_DISPUTED if disputed else RepairRequest.STATUS_COMPLETED
    repair.save(update_fields=[
        "outcome", "final_cost", "final_cost_reason", "completion_attachment",
        "completed_at", "status", "updated_at",
    ])
    RepairFeedback.objects.create(
        repair_request=repair,
        repairer=repair.repairer,
        center=repair.center,
        repairer_name_snapshot=repair.repairer_name_snapshot,
        work_quality=work_quality,
        completion_speed=completion_speed,
        cost_fairness=cost_fairness,
        comment=(comment or "").strip(),
        author=actor,
    )
    _record_repair_event(
        repair,
        "completed_cost_disputed" if disputed else "completed",
        "نتیجه تعمیر و ارزیابی ثبت شد." + (" اختلاف هزینه برای تعیین تکلیف باز ماند." if disputed else ""),
        actor,
        previous,
        metadata={"estimate": str(repair.estimate_amount), "final_cost": str(final_cost)},
    )
    province_admins = User.objects.filter(
        role=User.ROLE_ADMIN_PROVINCE,
        org_unit_id=_province_id_for_center(repair.center),
        is_active=True,
    )
    Notification.push_many(
        province_admins,
        "نتیجه تعمیر ثبت شد",
        f"{repair.number}: " + ("اختلاف هزینه نیازمند تعیین تکلیف است." if disputed else "تعمیر تکمیل شد."),
        url=repair.get_absolute_url(),
        level="warning" if disputed else "success",
    )
    return repair


@transaction.atomic
def resolve_repair_cost_dispute(*, repair, decision, note, actor, attachment=None):
    _require_province_admin_for_center(actor, repair.center)
    if repair.status != RepairRequest.STATUS_DISPUTED:
        raise ValidationError("این درخواست اختلاف هزینه باز ندارد.")
    if not (note or "").strip():
        raise ValidationError("ثبت نتیجه و مستند تصمیم الزامی است.")
    previous = repair.status
    repair.cost_dispute_resolution = note.strip()
    if attachment:
        repair.cost_dispute_attachment = attachment
    if decision == "approve_increase":
        repair.cost_increase_approved_by = actor
        repair.cost_increase_approved_at = timezone.now()
        repair.status = RepairRequest.STATUS_RESOLVED
        action = "cost_increase_approved"
        notification_title = "افزایش هزینه تعمیر تایید شد"
        notification_level = "success"
    elif decision == "settled":
        repair.status = RepairRequest.STATUS_RESOLVED
        action = "cost_dispute_settled"
        notification_title = "اختلاف هزینه تعمیر تسویه شد"
        notification_level = "success"
    elif decision == "reject_increase":
        # The repair itself remains recorded, but the excess amount stays open
        # as a dispute until a later approval or documented settlement.
        action = "cost_increase_rejected"
        notification_title = "افزایش هزینه تعمیر تایید نشد؛ پرونده باز ماند"
        notification_level = "warning"
    else:
        raise ValidationError("تصمیم اختلاف هزینه نامعتبر است.")
    update_fields = ["cost_dispute_resolution", "updated_at"]
    if attachment:
        update_fields.append("cost_dispute_attachment")
    if decision != "reject_increase":
        update_fields.extend([
            "cost_increase_approved_by", "cost_increase_approved_at", "status",
        ])
    repair.save(update_fields=update_fields)
    _record_repair_event(
        repair, action, note.strip(), actor, previous,
        metadata={"decision_attachment": repair.cost_dispute_attachment.name if repair.cost_dispute_attachment else ""},
    )
    Notification.push(
        repair.requested_by, notification_title,
        f"{repair.number}: {note.strip()}",
        url=repair.get_absolute_url(), level=notification_level,
    )
    return repair


@transaction.atomic
def create_referral(*, subject, description, recipient_role, recipient_name,
                    actor, center=None, repair_request=None, recipient_user=None,
                    attachment=None):
    if not actor or not actor.is_authenticated:
        raise PermissionDenied("ورود به سامانه الزامی است.")
    if center and not _can_manage_center(actor, center):
        raise PermissionDenied("مرکز خارج از حوزه مجاز شماست.")
    if repair_request and not visible_repair_requests(actor).filter(pk=repair_request.pk).exists():
        raise PermissionDenied("درخواست تعمیر خارج از حوزه مجاز شماست.")
    referral = GeneralReferral(
        subject=subject.strip(), description=description.strip(),
        recipient_role=recipient_role.strip(), recipient_name=recipient_name.strip(),
        center=center, repair_request=repair_request, recipient_user=recipient_user,
        attachment=attachment or "", created_by=actor,
    )
    referral.full_clean()
    referral.save()
    log_action(
        "create", referral,
        changes={
            "subject": {"از": "", "به": referral.subject},
            "recipient_role": {"از": "", "به": referral.recipient_role},
            "recipient_name": {"از": "", "به": referral.recipient_name},
        },
        note="ارجاع عمومی ثبت شد.",
        user=actor,
    )
    if recipient_user:
        Notification.push(
            recipient_user, "ارجاع جدید در ITAM",
            referral.subject, url=reverse("maintenance:referral_list"),
        )
    return referral


@transaction.atomic
def resolve_referral(*, referral, outcome, instruction, actor, attachment=None):
    if not actor or not actor.is_authenticated:
        raise PermissionDenied("ورود به سامانه الزامی است.")
    if referral.center_id:
        if (
            not _is_country_admin(actor)
            and referral.recipient_user_id != actor.pk
            and not actor.get_scoped_centers().filter(pk=referral.center_id).exists()
        ):
            raise PermissionDenied("ارجاع خارج از حوزه مجاز شماست.")
    elif not (_is_country_admin(actor) or referral.recipient_user_id == actor.pk):
        raise PermissionDenied("ارجاع سراسری فقط توسط کاربر گیرنده یا مدیر کشوری قابل تعیین تکلیف است.")
    if not (outcome or "").strip():
        raise ValidationError("ثبت نتیجه پیگیری الزامی است.")
    referral.status = GeneralReferral.STATUS_RESOLVED
    referral.outcome = outcome.strip()
    referral.instruction = (instruction or "").strip()
    if attachment:
        referral.resolution_attachment = attachment
    referral.resolved_by = actor
    referral.resolved_at = timezone.now()
    referral.save(update_fields=[
        "status", "outcome", "instruction", "resolved_by", "resolved_at", "updated_at",
        *(["resolution_attachment"] if attachment else []),
    ])
    log_action(
        "resolve", referral,
        changes={
            "status": {"از": GeneralReferral.STATUS_OPEN, "به": GeneralReferral.STATUS_RESOLVED},
            "outcome": {"از": "", "به": referral.outcome},
            "instruction": {"از": "", "به": referral.instruction},
            "resolution_attachment": {"از": "", "به": referral.resolution_attachment.name if referral.resolution_attachment else ""},
        },
        note="ارجاع عمومی تعیین تکلیف شد.",
        user=actor,
    )
    recipients = [referral.created_by]
    if referral.repair_request_id:
        recipients.append(referral.repair_request.requested_by)
    Notification.push_many(
        {user.pk: user for user in recipients}.values(),
        "نتیجه ارجاع در ITAM ثبت شد",
        f"{referral.subject}: {referral.outcome}",
        url=reverse("maintenance:referral_list"),
        level="success",
    )
    return referral


def add_feedback_reply(*, feedback, body, actor, parent=None):
    if not body or not body.strip():
        raise ValidationError("متن پاسخ الزامی است.")
    if not actor or not actor.is_authenticated or not (
        actor.is_admin_province or actor.role == User.ROLE_ADMIN_IT
    ):
        raise PermissionDenied("فقط مدیر استان یا کارشناس فناوری اطلاعات مجاز می‌تواند پاسخ ثبت کند.")
    if not visible_repair_feedback(actor).filter(pk=feedback.pk).exists():
        raise PermissionDenied("این ارزیابی خارج از حوزه مجاز شماست.")
    if parent and parent.feedback_id != feedback.pk:
        raise ValidationError("پاسخ والد متعلق به همین ارزیابی نیست.")
    return RepairFeedbackReply.objects.create(
        feedback=feedback, parent=parent, body=body.strip(), author=actor,
    )


@transaction.atomic
def create_general_it_request(*, center, request_type, title, description, actor, asset=None):
    if not actor or not actor.is_authenticated:
        raise PermissionDenied("ورود به سامانه الزامی است.")
    if actor.center_id != center.pk and not _can_manage_center(actor, center):
        raise PermissionDenied("ثبت درخواست برای این مرکز مجاز نیست.")
    if asset and asset.center_id != center.pk:
        raise ValidationError("دارایی باید متعلق به همان مرکز باشد.")
    request = GeneralITRequest.objects.create(
        center=center, request_type=request_type, title=title.strip(),
        description=description.strip(), requested_by=actor, asset=asset,
    )
    GeneralITRequestEvent.objects.create(
        request=request, action="created", note="درخواست ثبت شد.", actor=actor,
    )
    return request


@transaction.atomic
def assign_general_it_request(*, request, expert, actor):
    if (actor.role != User.ROLE_ADMIN_IT and not actor.is_admin_country) or not _can_manage_center(actor, request.center):
        raise PermissionDenied("فقط کارشناس IT مجاز همان مرکز می‌تواند درخواست را ارجاع دهد.")
    if expert.role != User.ROLE_ADMIN_IT or not expert.is_active or expert.center_id != request.center_id:
        raise ValidationError("کارشناس انتخاب‌شده باید فعال و متعلق به همان مرکز باشد.")
    request.assigned_to = expert
    request.status = GeneralITRequest.STATUS_ASSIGNED
    request.save(update_fields=["assigned_to", "status", "updated_at"])
    GeneralITRequestEvent.objects.create(
        request=request, action="assigned", note=f"به {expert.display_name} ارجاع شد.", actor=actor,
    )
    Notification.push(
        request.requested_by, "درخواست IT به کارشناس ارجاع شد",
        request.number, url=reverse("maintenance:it_request_detail", args=[request.pk]),
    )
    return request


@transaction.atomic
def manager_decide_general_it_request(*, request, decision, note, actor):
    if actor.role != User.ROLE_MANAGER or actor.center_id != request.center_id:
        raise PermissionDenied("فقط مدیر همان مرکز می‌تواند درخواست را بررسی کند.")
    if request.manager_approval != GeneralITRequest.MANAGER_PENDING:
        raise ValidationError("درخواست قبلاً توسط مدیر بررسی شده است.")
    if decision not in {"approve", "reject"}:
        raise ValidationError("تصمیم مدیر نامعتبر است.")
    if decision == "reject" and not (note or "").strip():
        raise ValidationError("برای رد درخواست، دلیل الزامی است.")
    request.manager_approval = (
        GeneralITRequest.MANAGER_APPROVED if decision == "approve"
        else GeneralITRequest.MANAGER_REJECTED
    )
    request.manager_reviewed_by = actor
    request.manager_reviewed_at = timezone.now()
    request.status = (
        GeneralITRequest.STATUS_APPROVED if decision == "approve"
        else GeneralITRequest.STATUS_REJECTED
    )
    request.provincial_decision = (note or "").strip()
    request.save(update_fields=[
        "manager_approval", "manager_reviewed_by", "manager_reviewed_at",
        "status", "provincial_decision", "updated_at",
    ])
    GeneralITRequestEvent.objects.create(
        request=request, action=f"manager_{decision}", note=(note or "تایید مدیر مرکز"),
        actor=actor,
    )
    Notification.push_many(
        [u for u in (request.requested_by, request.assigned_to) if u],
        "تصمیم مدیر مرکز درباره درخواست IT",
        f"{request.number}: {request.get_manager_approval_display()}",
        url=reverse("maintenance:it_request_detail", args=[request.pk]),
        level="warning" if decision == "reject" else "info",
    )
    return request


@transaction.atomic
def escalate_general_it_request(*, request, actor, bypass_reason=""):
    if (actor.role != User.ROLE_ADMIN_IT and not actor.is_admin_country) or not _can_manage_center(actor, request.center):
        raise PermissionDenied("فقط کارشناس IT همان مرکز می‌تواند درخواست را به استان ارسال کند.")
    if request.status in (GeneralITRequest.STATUS_REJECTED, GeneralITRequest.STATUS_RESOLVED):
        raise ValidationError("درخواست ردشده یا مختومه قابل ارسال مجدد نیست.")
    if request.manager_approval == GeneralITRequest.MANAGER_REJECTED:
        raise ValidationError("درخواست توسط مدیر مرکز رد شده و قابل ارجاع نیست.")
    if request.manager_approval == GeneralITRequest.MANAGER_PENDING:
        if not (bypass_reason or "").strip():
            raise ValidationError("عبور از تایید مدیر مرکز نیازمند ثبت دلیل است.")
        request.manager_approval = GeneralITRequest.MANAGER_BYPASSED
        request.manager_bypass_reason = bypass_reason.strip()
    request.status = GeneralITRequest.STATUS_ESCALATED
    request.save(update_fields=[
        "status", "manager_approval", "manager_bypass_reason", "updated_at",
    ])
    GeneralITRequestEvent.objects.create(
        request=request, action="escalated",
        note=(bypass_reason.strip() if bypass_reason else "با تایید مدیر مرکز به استان ارسال شد."),
        actor=actor,
    )
    province_admins = User.objects.filter(
        role=User.ROLE_ADMIN_PROVINCE,
        org_unit_id=_province_id_for_center(request.center),
        is_active=True,
    )
    Notification.push_many(
        province_admins, "درخواست جدید برای مدیریت درمان استان",
        f"{request.number}: {request.title}",
        url=reverse("maintenance:it_request_detail", args=[request.pk]),
    )
    return request


@transaction.atomic
def resolve_general_it_request(*, request, decision, actor):
    _require_province_admin_for_center(actor, request.center)
    if request.status != GeneralITRequest.STATUS_ESCALATED:
        raise ValidationError("فقط درخواست ارسال‌شده به استان قابل تعیین تکلیف است.")
    if not (decision or "").strip():
        raise ValidationError("ثبت دستور یا نتیجه استانی الزامی است.")
    request.provincial_decision = decision.strip()
    request.status = GeneralITRequest.STATUS_RESOLVED
    request.resolved_by = actor
    request.resolved_at = timezone.now()
    request.save(update_fields=[
        "provincial_decision", "status", "resolved_by", "resolved_at", "updated_at",
    ])
    GeneralITRequestEvent.objects.create(
        request=request, action="provincial_resolved", note=decision.strip(), actor=actor,
    )
    Notification.push_many(
        [u for u in (request.requested_by, request.assigned_to) if u],
        "دستور استانی درخواست IT ثبت شد",
        f"{request.number}: {decision.strip()}",
        url=reverse("maintenance:it_request_detail", args=[request.pk]),
        level="success",
    )
    return request
