"""ثابت‌ها و انتخاب‌های مشترک میان برنامه‌ها."""

# ---------------------------------------------------------------------------
# اولویت درخواست‌ها
# ---------------------------------------------------------------------------
PRIORITY_CRITICAL = "critical"
PRIORITY_HIGH = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW = "low"

PRIORITY_CHOICES = (
    (PRIORITY_LOW, "کم"),
    (PRIORITY_MEDIUM, "متوسط"),
    (PRIORITY_HIGH, "زیاد"),
    (PRIORITY_CRITICAL, "بحرانی"),
)

PRIORITY_LABELS = dict(PRIORITY_CHOICES)
PRIORITY_ORDER = {
    PRIORITY_CRITICAL: 0,
    PRIORITY_HIGH: 1,
    PRIORITY_MEDIUM: 2,
    PRIORITY_LOW: 3,
}
PRIORITY_CSS = {
    PRIORITY_CRITICAL: "danger",
    PRIORITY_HIGH: "warning",
    PRIORITY_MEDIUM: "info",
    PRIORITY_LOW: "neutral",
}

# ---------------------------------------------------------------------------
# وضعیت درخواست خرابی (گردش کار)
# ---------------------------------------------------------------------------
STATUS_REPORTED = "reported"
STATUS_ACKNOWLEDGED = "acknowledged"
STATUS_IN_PROGRESS = "in_progress"
STATUS_WAITING_PARTS = "waiting_parts"
STATUS_RESOLVED = "resolved"
STATUS_USER_CONFIRMED = "user_confirmed"
STATUS_CLOSED = "closed"
STATUS_REJECTED = "rejected"
STATUS_CANCELED = "canceled"

TICKET_STATUS_CHOICES = (
    (STATUS_REPORTED, "اعلام خرابی توسط اداره"),
    (STATUS_ACKNOWLEDGED, "پذیرش توسط پیمانکار"),
    (STATUS_IN_PROGRESS, "در حال رسیدگی / حضور در محل"),
    (STATUS_WAITING_PARTS, "انتظار قطعه"),
    (STATUS_RESOLVED, "اعلام رفع خرابی توسط پیمانکار"),
    (STATUS_USER_CONFIRMED, "تایید کاربر"),
    (STATUS_CLOSED, "تایید کارشناس IT و بسته‌شده"),
    (STATUS_REJECTED, "رد شده"),
    (STATUS_CANCELED, "لغو شده"),
)

TICKET_STATUS_LABELS = dict(TICKET_STATUS_CHOICES)
TICKET_STATUS_CSS = {
    STATUS_REPORTED: "danger",
    STATUS_ACKNOWLEDGED: "info",
    STATUS_IN_PROGRESS: "warning",
    STATUS_WAITING_PARTS: "warning",
    STATUS_RESOLVED: "info",
    STATUS_USER_CONFIRMED: "info",
    STATUS_CLOSED: "success",
    STATUS_REJECTED: "neutral",
    STATUS_CANCELED: "neutral",
}

#: ترتیب پیشرفت گردش کار
TICKET_STATUS_SEQUENCE = [
    STATUS_REPORTED,
    STATUS_ACKNOWLEDGED,
    STATUS_IN_PROGRESS,
    STATUS_WAITING_PARTS,
    STATUS_RESOLVED,
    STATUS_USER_CONFIRMED,
    STATUS_CLOSED,
]

#: وضعیت‌هایی که کار در آن‌ها تمام‌شده تلقی می‌شود
TICKET_OPEN_STATUSES = [
    STATUS_REPORTED,
    STATUS_ACKNOWLEDGED,
    STATUS_IN_PROGRESS,
    STATUS_WAITING_PARTS,
    STATUS_RESOLVED,
    STATUS_USER_CONFIRMED,
]
TICKET_CLOSED_STATUSES = [STATUS_CLOSED, STATUS_REJECTED, STATUS_CANCELED]

# ---------------------------------------------------------------------------
# نوع خرابی
# ---------------------------------------------------------------------------
FAILURE_HARDWARE = "hardware"
FAILURE_SOFTWARE = "software"
FAILURE_NETWORK = "network"
FAILURE_PRINTER = "printer"
FAILURE_POWER = "power"
FAILURE_OTHER = "other"

FAILURE_TYPE_CHOICES = (
    (FAILURE_HARDWARE, "سخت‌افزاری"),
    (FAILURE_SOFTWARE, "نرم‌افزاری"),
    (FAILURE_NETWORK, "شبکه و ارتباطات"),
    (FAILURE_PRINTER, "پرینتر و مصرفی"),
    (FAILURE_POWER, "برق و تغذیه"),
    (FAILURE_OTHER, "سایر"),
)

# ---------------------------------------------------------------------------
# وضعیت دارایی
# ---------------------------------------------------------------------------
ASSET_ACTIVE = "active"
ASSET_IN_REPAIR = "in_repair"
ASSET_OUT_OF_SERVICE = "out_of_service"
ASSET_STORAGE = "storage"
ASSET_RETIRED = "retired"

ASSET_STATUS_CHOICES = (
    (ASSET_ACTIVE, "در بهره‌برداری"),
    (ASSET_IN_REPAIR, "در تعمیر"),
    (ASSET_OUT_OF_SERVICE, "از کار افتاده"),
    (ASSET_STORAGE, "انبار"),
    (ASSET_RETIRED, "از رده خارج"),
)
ASSET_STATUS_CSS = {
    ASSET_ACTIVE: "success",
    ASSET_IN_REPAIR: "warning",
    ASSET_OUT_OF_SERVICE: "danger",
    ASSET_STORAGE: "info",
    ASSET_RETIRED: "neutral",
}

# ---------------------------------------------------------------------------
# وضعیت اسنپ‌شات سخت‌افزاری
# ---------------------------------------------------------------------------
SNAPSHOT_DRAFT = "draft"
SNAPSHOT_PENDING = "pending"
SNAPSHOT_LOCKED = "locked"
SNAPSHOT_REJECTED = "rejected"

SNAPSHOT_STATUS_CHOICES = (
    (SNAPSHOT_DRAFT, "پیش‌نویس (در حال ثبت)"),
    (SNAPSHOT_PENDING, "در انتظار تایید کارشناس IT"),
    (SNAPSHOT_LOCKED, "تایید و قفل‌شده"),
    (SNAPSHOT_REJECTED, "برگشت داده‌شده"),
)
SNAPSHOT_STATUS_CSS = {
    SNAPSHOT_DRAFT: "neutral",
    SNAPSHOT_PENDING: "warning",
    SNAPSHOT_LOCKED: "success",
    SNAPSHOT_REJECTED: "danger",
}

#: وضعیت قطعه در اسنپ‌شات
ITEM_OK = "ok"
ITEM_FAULTY = "faulty"
ITEM_REPLACED = "replaced"
ITEM_MISSING = "missing"
ITEM_ADDED = "added"

ITEM_CONDITION_CHOICES = (
    (ITEM_OK, "سالم"),
    (ITEM_FAULTY, "معیوب"),
    (ITEM_REPLACED, "تعویض‌شده"),
    (ITEM_MISSING, "مفقود"),
    (ITEM_ADDED, "اضافه‌شده"),
)
ITEM_CONDITION_CSS = {
    ITEM_OK: "success",
    ITEM_FAULTY: "danger",
    ITEM_REPLACED: "warning",
    ITEM_MISSING: "danger",
    ITEM_ADDED: "info",
}

# ---------------------------------------------------------------------------
# نتیجه مقایسه اقلام (Diff)
# ---------------------------------------------------------------------------
DIFF_UNCHANGED = "unchanged"
DIFF_ADDED = "added"
DIFF_REMOVED = "removed"
DIFF_REPLACED = "replaced"
DIFF_CHANGED = "changed"

DIFF_CHOICES = (
    (DIFF_UNCHANGED, "بدون تغییر"),
    (DIFF_ADDED, "اضافه شده"),
    (DIFF_REMOVED, "حذف/مفقود شده"),
    (DIFF_REPLACED, "تعویض شده"),
    (DIFF_CHANGED, "مشخصات تغییر کرده"),
)
DIFF_CSS = {
    DIFF_UNCHANGED: "neutral",
    DIFF_ADDED: "info",
    DIFF_REMOVED: "danger",
    DIFF_REPLACED: "warning",
    DIFF_CHANGED: "warning",
}

# ---------------------------------------------------------------------------
# بازدید دوره‌ای
# ---------------------------------------------------------------------------
VISIT_PLANNED = "planned"
VISIT_IN_PROGRESS = "in_progress"
VISIT_DONE = "done"
VISIT_MISSED = "missed"
VISIT_CANCELED = "canceled"

VISIT_STATUS_CHOICES = (
    (VISIT_PLANNED, "برنامه‌ریزی‌شده"),
    (VISIT_IN_PROGRESS, "در حال انجام"),
    (VISIT_DONE, "انجام‌شده"),
    (VISIT_MISSED, "انجام‌نشده"),
    (VISIT_CANCELED, "لغو شده"),
)
VISIT_STATUS_CSS = {
    VISIT_PLANNED: "info",
    VISIT_IN_PROGRESS: "warning",
    VISIT_DONE: "success",
    VISIT_MISSED: "danger",
    VISIT_CANCELED: "neutral",
}

#: وضعیت سلامت تجهیز در بازدید
CHECK_HEALTHY = "healthy"
CHECK_NEEDS_PARTS = "needs_parts"
CHECK_FAULTY = "faulty"
CHECK_OUT_OF_SERVICE = "out_of_service"
CHECK_NOT_SEEN = "not_seen"

CHECK_CONDITION_CHOICES = (
    (CHECK_HEALTHY, "سالم"),
    (CHECK_NEEDS_PARTS, "نیازمند قطعه"),
    (CHECK_FAULTY, "معیوب"),
    (CHECK_OUT_OF_SERVICE, "از کار افتاده"),
    (CHECK_NOT_SEEN, "تجهیز مشاهده نشد"),
)
CHECK_CONDITION_CSS = {
    CHECK_HEALTHY: "success",
    CHECK_NEEDS_PARTS: "warning",
    CHECK_FAULTY: "danger",
    CHECK_OUT_OF_SERVICE: "danger",
    CHECK_NOT_SEEN: "neutral",
}

# ---------------------------------------------------------------------------
# توقف ساعت SLA
# ---------------------------------------------------------------------------
PAUSE_PARTS = "awaiting_parts"
PAUSE_APPROVAL = "awaiting_approval"
PAUSE_USER = "awaiting_user"
PAUSE_SITE_ACCESS = "site_not_accessible"
PAUSE_OTHER = "other"

PAUSE_REASON_CHOICES = (
    (PAUSE_PARTS, "انتظار تامین قطعه"),
    (PAUSE_APPROVAL, "انتظار تایید"),
    (PAUSE_USER, "انتظار همکاری کاربر"),
    (PAUSE_SITE_ACCESS, "عدم دسترسی به محل"),
    (PAUSE_OTHER, "سایر"),
)

# ---------------------------------------------------------------------------
# رخدادهای Outbox
# ---------------------------------------------------------------------------
EVENT_TICKET_REPORTED = "ticket.reported"
EVENT_TICKET_ACKNOWLEDGED = "ticket.acknowledged"
EVENT_TICKET_ARRIVED = "ticket.arrived"
EVENT_TICKET_STATUS_CHANGED = "ticket.status_changed"
EVENT_TICKET_RESOLVED = "ticket.resolved"
EVENT_TICKET_CLOSED = "ticket.closed"
EVENT_TICKET_SLA_BREACHED = "ticket.sla_breached"
EVENT_ASSET_CREATED = "asset.created"
EVENT_ASSET_UPDATED = "asset.updated"
EVENT_HARDWARE_SNAPSHOT_CREATED = "hardware.snapshot_created"
EVENT_HARDWARE_BASELINE_LOCKED = "hardware.baseline_locked"
EVENT_HARDWARE_DIFF_DETECTED = "hardware.diff_detected"
EVENT_VISIT_PLANNED = "maintenance.visit_planned"
EVENT_VISIT_COMPLETED = "maintenance.visit_completed"
EVENT_VISIT_MISSED = "maintenance.visit_missed"

EVENT_TYPE_CHOICES = (
    (EVENT_TICKET_REPORTED, "اعلام خرابی"),
    (EVENT_TICKET_ACKNOWLEDGED, "پذیرش پیمانکار"),
    (EVENT_TICKET_ARRIVED, "حضور در محل"),
    (EVENT_TICKET_STATUS_CHANGED, "تغییر وضعیت درخواست"),
    (EVENT_TICKET_RESOLVED, "اعلام رفع خرابی"),
    (EVENT_TICKET_CLOSED, "بسته شدن درخواست"),
    (EVENT_TICKET_SLA_BREACHED, "نقض SLA"),
    (EVENT_ASSET_CREATED, "ثبت دارایی"),
    (EVENT_ASSET_UPDATED, "ویرایش دارایی"),
    (EVENT_HARDWARE_SNAPSHOT_CREATED, "ثبت اسنپ‌شات سخت‌افزار"),
    (EVENT_HARDWARE_BASELINE_LOCKED, "قفل اسنپ‌شات پایه"),
    (EVENT_HARDWARE_DIFF_DETECTED, "کشف تغییر اقلام سخت‌افزاری"),
    (EVENT_VISIT_PLANNED, "برنامه‌ریزی بازدید دوره‌ای"),
    (EVENT_VISIT_COMPLETED, "پایان بازدید دوره‌ای"),
    (EVENT_VISIT_MISSED, "بازدید انجام‌نشده"),
)
