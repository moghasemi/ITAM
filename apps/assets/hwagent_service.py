"""سرویس پردازش و یکپارچه‌سازی خروجی ایجنت سخت‌افزاری (HWAgent)."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone

from apps.core.constants import (
    DIFF_REMOVED,
    DIFF_REPLACED,
    EVENT_HARDWARE_BASELINE_LOCKED,
    EVENT_HARDWARE_DIFF_DETECTED,
    EVENT_HARDWARE_SNAPSHOT_CREATED,
    SNAPSHOT_DRAFT,
    SNAPSHOT_LOCKED,
    SNAPSHOT_PENDING,
)
from apps.integrations.models import OutboxEvent

from .models import Asset, AssetCategory, ComponentType, HardwareSnapshot, SnapshotItem
from .services import compute_diff, reference_snapshot


def get_or_create_component_type(name: str, code: str, is_key: bool = True, sort_order: int = 100) -> ComponentType:
    """دریافت یا ساخت خودکار گونه قطعه."""
    obj = ComponentType.objects.filter(code=code).first()
    if not obj:
        obj = ComponentType.objects.filter(name=name).first()
    if not obj:
        obj = ComponentType.objects.create(
            name=name,
            code=code,
            is_key_item=is_key,
            is_serialized=True,
            sort_order=sort_order,
        )
    return obj


def parse_hwagent_json(raw_json: Any) -> Dict[str, Any]:
    """اعتبارسنجی و تبدیل داده ورودی به ساختار دیکشنری استاندارد."""
    if isinstance(raw_json, str):
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as err:
            raise ValueError(f"قالب فایل JSON نامعتبر است: {err}")
    elif isinstance(raw_json, dict):
        data = raw_json
    else:
        raise ValueError("داده‌های ارسالی باید به فرمت JSON باشند.")

    # بررسی فیلدهای حداقلی یک اسنپ‌شات معتبر HWAgent
    has_hw_fields = any(k in data for k in ("cpu", "baseboard", "ram", "disks", "computerName"))
    if not has_hw_fields:
        raise ValueError("ساختار فایل ارسالی با قالب استاندارد HWAgent مطابقت ندارد.")

    return data


def generate_technical_spec_summary(data: Dict[str, Any]) -> str:
    """تولید خلاصه مشخصات فنی یکپارچه جهت شناسنامه دارایی."""
    parts = []
    cpu = data.get("cpu", {})
    if cpu and isinstance(cpu, dict):
        cpu_name = cpu.get("name", "").strip()
        cores = cpu.get("cores")
        threads = cpu.get("threads")
        clock = cpu.get("speed")
        core_info = f"{cores}C/{threads}T" if cores and threads else ""
        clock_info = f"{clock}MHz" if clock else ""
        details = " ".join(p for p in (core_info, clock_info) if p)
        if cpu_name:
            parts.append(f"CPU: {cpu_name} ({details})" if details else f"CPU: {cpu_name}")

    rams = data.get("ram", [])
    if isinstance(rams, list) and rams:
        total_gb = sum(r.get("capacityGB", 0) for r in rams if isinstance(r, dict))
        ram_speeds = {str(r.get("speedMHz")) for r in rams if isinstance(r, dict) and r.get("speedMHz")}
        speed_str = f" @ {'/'.join(sorted(ram_speeds))}MHz" if ram_speeds else ""
        parts.append(f"RAM: {total_gb}GB ({len(rams)} ماژول{speed_str})")

    disks = data.get("disks", [])
    if isinstance(disks, list) and disks:
        disk_labels = []
        for d in disks:
            if isinstance(d, dict):
                size = d.get("sizeGB", 0)
                media = d.get("mediaType", "")
                name = d.get("name", "").strip()
                label = f"{size}GB {media}".strip()
                if name:
                    label += f" ({name})"
                disk_labels.append(label)
        if disk_labels:
            parts.append(f"Storage: {' + '.join(disk_labels)}")

    bb = data.get("baseboard", {})
    if bb and isinstance(bb, dict):
        mb_name = f"{bb.get('manufacturer', '')} {bb.get('product', '')}".strip()
        if mb_name:
            parts.append(f"MB: {mb_name}")

    gpus = data.get("gpu", [])
    if isinstance(gpus, list) and gpus:
        gpu_names = [g.get("name", "").strip() for g in gpus if isinstance(g, dict) and g.get("name")]
        if gpu_names:
            parts.append(f"GPU: {', '.join(gpu_names)}")

    os_info = data.get("os", "").strip()
    if os_info:
        parts.append(f"OS: {os_info}")

    return " | ".join(parts)


def match_asset_for_hwagent(data: Dict[str, Any], center=None, asset_tag: Optional[str] = None) -> Optional[Asset]:
    """یافتن دارایی متناظر با اطلاعات HWAgent صرفاً در محدوده مرکز مشخص‌شده (Center-Bound Matching).

    قوانین امنیتی و انطباق:
    ۱. در صورت مشخص نبودن مرکز، هیچ دارایی جستجو یا بازگردانده نمی‌شود (Fail-Closed).
    ۲. جستجو منحصراً روی دارایی‌های فعال همان مرکز انجام می‌گیرد.
    ۳. در صورت بروز هرگونه ابهام (بیش از یک دارایی منطبق)، جهت جلوگیری از تغییر اشتباه هیچ دارایی انتخاب نمی‌شود.
    """
    if center is None:
        return None

    base_qs = Asset.objects.filter(center=center)

    # ۱) تطبیق بر اساس شماره اموال مشخص‌شده
    if asset_tag and asset_tag.strip():
        tag_matches = base_qs.filter(asset_tag__iexact=asset_tag.strip())
        cnt = tag_matches.count()
        if cnt == 1:
            return tag_matches.first()
        if cnt > 1:
            return None

    # ۲) تطبیق با سریال مادربرد یا شماره سریال دستگاه
    bb = data.get("baseboard", {})
    bb_serial = (bb.get("serial") or "").strip() if isinstance(bb, dict) else ""
    if bb_serial and bb_serial.lower() not in ("none", "default string", "to be filled by o.e.m.", ""):
        serial_matches = base_qs.filter(serial_number__iexact=bb_serial)
        cnt = serial_matches.count()
        if cnt == 1:
            return serial_matches.first()
        if cnt > 1:
            return None

    # ۳) تطبیق با آدرس فیزیکی MAC کارت شبکه
    networks = data.get("network", [])
    if isinstance(networks, list):
        for net in networks:
            if isinstance(net, dict) and net.get("mac"):
                mac = net["mac"].strip()
                if mac:
                    mac_matches = base_qs.filter(mac_address__iexact=mac)
                    cnt = mac_matches.count()
                    if cnt == 1:
                        return mac_matches.first()
                    if cnt > 1:
                        return None

    # ۴) تطبیق با نام کامپیوتر (Hostname)
    comp_name = (data.get("computerName") or "").strip()
    if comp_name:
        host_matches = base_qs.filter(hostname__iexact=comp_name)
        cnt = host_matches.count()
        if cnt == 1:
            return host_matches.first()
        if cnt > 1:
            return None

    return None

@transaction.atomic
def apply_hwagent_snapshot(
    asset: Asset,
    raw_data: Any,
    user=None,
    note: str = "",
    seal_number: str = "",
    auto_approve_baseline: bool = True,
) -> Tuple[HardwareSnapshot, Dict[str, Any]]:
    """پردازش و ذخیره اسنپ‌شات استخراج‌شده از HWAgent برای یک دارایی مشخص.

    خروجی: تاپل شامل نمونه اسنپ‌شات و دیکشنری مغایرت‌ها (Diff)
    """
    data = parse_hwagent_json(raw_data)

    # به‌روزرسانی اطلاعات سیستم در جدول دارایی
    comp_name = (data.get("computerName") or "").strip()
    if comp_name and not asset.hostname:
        asset.hostname = comp_name

    os_info = (data.get("os") or "").strip()
    if os_info:
        asset.os_name = os_info

    networks = data.get("network", [])
    if isinstance(networks, list) and networks:
        for net in networks:
            if isinstance(net, dict) and net.get("mac"):
                mac = net["mac"].strip()
                if mac and not asset.mac_address:
                    asset.mac_address = mac
                    break

    summary = generate_technical_spec_summary(data)
    if summary:
        asset.spec_summary = summary

    # اگر برند یا مدل خالی باشد از مادربورد تنظیم می‌کنیم
    bb = data.get("baseboard", {})
    if isinstance(bb, dict):
        if not asset.brand and bb.get("manufacturer"):
            asset.brand = bb.get("manufacturer", "")[:100]
        if not asset.model_name and bb.get("product"):
            asset.model_name = bb.get("product", "")[:120]
        if not asset.serial_number and bb.get("serial"):
            serial = bb.get("serial", "").strip()
            if serial.lower() not in ("none", "default string", "to be filled by o.e.m."):
                asset.serial_number = serial[:120]

    asset.save(update_fields=["hostname", "os_name", "mac_address", "spec_summary", "brand", "model_name", "serial_number", "updated_at"])

    # گونه‌های قطعات
    type_cpu = get_or_create_component_type("پردازنده (CPU)", "CPU", is_key=True, sort_order=10)
    type_ram = get_or_create_component_type("حافظه رم (RAM)", "RAM", is_key=True, sort_order=20)
    type_disk = get_or_create_component_type("هارد دیسک / حافظه داخلی", "SSD", is_key=True, sort_order=30)
    type_mb = get_or_create_component_type("مادربرد", "MB", is_key=True, sort_order=40)
    type_bios = get_or_create_component_type("بایوس", "BIOS", is_key=False, sort_order=50)
    type_gpu = get_or_create_component_type("کارت گرافیک", "GPU", is_key=True, sort_order=60)
    type_nic = get_or_create_component_type("کارت شبکه", "NIC", is_key=False, sort_order=70)

    # ایجاد اسنپ‌شات جدید
    reference = reference_snapshot(asset)
    is_baseline = reference is None

    snapshot_note = note.strip() or "دریافت خودکار از ایجنت سخت‌افزاری HWAgent"
    snapshot = HardwareSnapshot.objects.create(
        asset=asset,
        version=HardwareSnapshot.next_version(asset),
        status=SNAPSHOT_DRAFT,
        is_baseline=is_baseline,
        previous=reference,
        recorded_by=user,
        recorded_at=timezone.now(),
        note=snapshot_note,
        seal_number=seal_number,
        is_from_hwagent=True,
        agent_hashes=data.get("hashes", {}),
    )

    items_to_create = []

    # ۱) پردازنده
    cpu = data.get("cpu", {})
    if isinstance(cpu, dict) and cpu.get("name"):
        name = cpu.get("name", "").strip()
        brand = "Intel" if "intel" in name.lower() else ("AMD" if "amd" in name.lower() else "")
        cores = cpu.get("cores")
        threads = cpu.get("threads")
        clock = cpu.get("speed")
        cap = f"{cores} Cores / {threads} Threads / {clock} MHz" if cores else ""
        items_to_create.append(
            SnapshotItem(
                snapshot=snapshot,
                component_type=type_cpu,
                brand=brand,
                model_name=name[:120],
                capacity=cap[:120],
                quantity=1,
                slot="Socket 0",
            )
        )

    # ۲) مادربرد
    if isinstance(bb, dict) and (bb.get("manufacturer") or bb.get("product")):
        items_to_create.append(
            SnapshotItem(
                snapshot=snapshot,
                component_type=type_mb,
                brand=bb.get("manufacturer", "")[:100],
                model_name=bb.get("product", "")[:120],
                serial_number=bb.get("serial", "")[:120],
                quantity=1,
                slot="Baseboard",
            )
        )

    # ۳) بایوس
    bios = data.get("bios", {})
    if isinstance(bios, dict) and (bios.get("version") or bios.get("manufacturer")):
        items_to_create.append(
            SnapshotItem(
                snapshot=snapshot,
                component_type=type_bios,
                brand=bios.get("manufacturer", "")[:100],
                model_name=f"Ver: {bios.get('version', '')}"[:120],
                serial_number=bios.get("serial", "")[:120],
                quantity=1,
                slot="ROM",
            )
        )

    # ۴) رم‌ها
    rams = data.get("ram", [])
    if isinstance(rams, list):
        for r in rams:
            if isinstance(r, dict):
                cap_gb = r.get("capacityGB", 0)
                spd = r.get("speedMHz", "")
                cap_text = f"{cap_gb} GB ({spd} MHz)" if spd else f"{cap_gb} GB"
                items_to_create.append(
                    SnapshotItem(
                        snapshot=snapshot,
                        component_type=type_ram,
                        brand=r.get("manufacturer", "")[:100],
                        model_name=r.get("partNumber", "")[:120],
                        serial_number=r.get("serial", "")[:120],
                        capacity=cap_text[:120],
                        quantity=1,
                        slot=r.get("slot", "DIMM")[:80],
                    )
                )

    # ۵) دیسک‌ها
    disks = data.get("disks", [])
    if isinstance(disks, list):
        for i, d in enumerate(disks):
            if isinstance(d, dict):
                size_gb = d.get("sizeGB", 0)
                media = d.get("mediaType", "")
                cap_text = f"{size_gb} GB ({media})" if media else f"{size_gb} GB"
                items_to_create.append(
                    SnapshotItem(
                        snapshot=snapshot,
                        component_type=type_disk,
                        brand=d.get("name", "")[:100],
                        model_name=media[:120],
                        serial_number=d.get("serial", "")[:120],
                        capacity=cap_text[:120],
                        quantity=1,
                        slot=f"Port {i}",
                    )
                )

    # ۶) کارت‌های گرافیک
    gpus = data.get("gpu", [])
    if isinstance(gpus, list):
        for g in gpus:
            if isinstance(g, dict) and g.get("name"):
                items_to_create.append(
                    SnapshotItem(
                        snapshot=snapshot,
                        component_type=type_gpu,
                        model_name=g.get("name", "")[:120],
                        capacity=f"Driver: {g.get('driverVersion', '')}"[:120],
                        quantity=1,
                        slot="PCIe",
                    )
                )

    # ۷) کارت شبکه
    if isinstance(networks, list):
        for net in networks:
            if isinstance(net, dict) and net.get("mac"):
                items_to_create.append(
                    SnapshotItem(
                        snapshot=snapshot,
                        component_type=type_nic,
                        model_name=net.get("name", "")[:120],
                        serial_number=net.get("mac", "")[:120],
                        quantity=1,
                        slot="Onboard",
                    )
                )

    # درج اقلام در دیتابیس
    SnapshotItem.objects.bulk_create(items_to_create)

    # محاسبه تفاوت (Diff) با نسخه قبل
    current_items = list(snapshot.items.select_related("component_type"))
    previous_items = list(reference.items.select_related("component_type")) if reference else []
    diff = compute_diff(previous_items, current_items)

    snapshot.diff_data = diff
    snapshot.diff_count = diff.get("total_changes", 0)

    # تعیین وضعیت اسنپ‌شات
    if is_baseline and auto_approve_baseline and user and (user.is_superuser or getattr(user, 'is_admin_it', False)):
        snapshot.lock(user)
        asset.current_snapshot = snapshot
        asset.baseline_locked_at = snapshot.locked_at
        asset.save(update_fields=["current_snapshot", "baseline_locked_at", "updated_at"])
        OutboxEvent.emit(
            EVENT_HARDWARE_BASELINE_LOCKED,
            {"asset_id": asset.pk, "asset_tag": asset.asset_tag, "snapshot_id": snapshot.pk},
            aggregate_type="HardwareSnapshot",
            aggregate_id=snapshot.pk,
            actor=user,
        )
    else:
        snapshot.status = SNAPSHOT_PENDING
        snapshot.save(update_fields=["status", "diff_data", "diff_count", "updated_at"])

        if diff.get("has_alarm"):
            OutboxEvent.emit(
                EVENT_HARDWARE_DIFF_DETECTED,
                {
                    "asset_id": asset.pk,
                    "asset_tag": asset.asset_tag,
                    "snapshot_id": snapshot.pk,
                    "removed": diff.get("removed", 0),
                    "replaced": diff.get("replaced", 0),
                },
                aggregate_type="HardwareSnapshot",
                aggregate_id=snapshot.pk,
                actor=user,
            )

    OutboxEvent.emit(
        EVENT_HARDWARE_SNAPSHOT_CREATED,
        {
            "asset_id": asset.pk,
            "asset_tag": asset.asset_tag,
            "snapshot_id": snapshot.pk,
            "version": snapshot.version,
            "is_baseline": is_baseline,
            "is_from_hwagent": True,
        },
        aggregate_type="HardwareSnapshot",
        aggregate_id=snapshot.pk,
        actor=user,
    )

    return snapshot, diff


def process_batch_hwagent_files(
    files: List[Any],
    user,
    center=None,
    auto_create_asset: bool = False,
) -> Dict[str, Any]:
    """پردازش همزمان چندین فایل JSON دریافت شده از HWAgent."""
    results = {
        "total_files": len(files),
        "success": 0,
        "failed": 0,
        "alarms": 0,
        "items": [],
    }

    category_pc = AssetCategory.objects.filter(code="PC").first() or AssetCategory.objects.first()

    for f in files:
        name = getattr(f, "name", str(f))
        try:
            content = f.read() if hasattr(f, "read") else f
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="replace")
            data = parse_hwagent_json(content)

            asset = match_asset_for_hwagent(data, center=center)
            is_new = False

            if not asset:
                if auto_create_asset:
                    comp_name = data.get("computerName", "PC-AUTO").strip()
                    tag = f"TAG-{comp_name}-{timezone.now().strftime('%H%M%S')}"
                    asset = Asset.objects.create(
                        asset_tag=tag,
                        title=f"رایانه {comp_name}",
                        category=category_pc,
                        center=center,
                        hostname=comp_name,
                    )
                    is_new = True
                else:
                    results["failed"] += 1
                    results["items"].append({
                        "filename": name,
                        "status": "error",
                        "message": f"تجهیز متناظری برای سیستم «{data.get('computerName', 'نامشخص')}» یافت نشد. لطفاً ابتدا دارایی را ثبت کنید.",
                    })
                    continue

            snap, diff = apply_hwagent_snapshot(
                asset=asset,
                raw_data=data,
                user=user,
                note=f"بارگذاری دسته‌ای از فایل {name}",
            )

            has_alarm = diff.get("has_alarm", False)
            if has_alarm:
                results["alarms"] += 1

            results["success"] += 1
            results["items"].append({
                "filename": name,
                "status": "warning" if has_alarm else "success",
                "asset_tag": asset.asset_tag,
                "computer_name": asset.hostname,
                "version": snap.version,
                "is_new_asset": is_new,
                "diff_count": snap.diff_count,
                "has_alarm": has_alarm,
                "message": f"اسنپ‌شات نسخه {snap.version} با {snap.diff_count} تغییر ثبت شد." if not snap.is_baseline else "اسنپ‌شات پایه با موفقیت قفل شد.",
            })

        except Exception as e:
            results["failed"] += 1
            results["items"].append({
                "filename": name,
                "status": "error",
                "message": str(e),
            })

    return results
