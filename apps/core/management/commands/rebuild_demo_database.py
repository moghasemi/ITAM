"""Back up, clear, and repopulate a local SQLite development database."""
from __future__ import annotations

import datetime as dt
import hashlib
import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "پشتیبان‌گیری، پاک‌سازی و بازسازی پایگاه داده نمونه محیط توسعه"

    def add_arguments(self, parser):
        parser.add_argument("--admin-password", required=True, help="گذرواژه کاربران نمونه")
        parser.add_argument("--assets", type=int, default=30, help="تعداد دارایی‌های نمونه")
        parser.add_argument("--confirm-reset", action="store_true", help="تایید حذف تمام داده‌های پایگاه محلی")
        parser.add_argument(
            "--backup-dir",
            default=str(Path(settings.BASE_DIR).parent / "itam-db-backups"),
            help="مسیر نگهداری نسخه پشتیبان SQLite",
        )
        parser.add_argument("--no-demo-tickets", action="store_true")

    def handle(self, *args, **options):
        if not options["confirm_reset"]:
            raise CommandError("برای ادامه باید آرگومان --confirm-reset را صریحاً وارد کنید.")
        if not settings.DEBUG:
            raise CommandError("این فرمان فقط در محیطی با DEBUG=True مجاز است.")
        if connection.vendor != "sqlite":
            raise CommandError("این فرمان فقط برای پایگاه داده SQLite محلی طراحی شده است.")
        if options["assets"] < 1:
            raise CommandError("--assets باید حداقل ۱ باشد.")

        db_path = Path(connection.settings_dict["NAME"]).resolve()
        project_root = Path(settings.BASE_DIR).resolve()
        if not db_path.is_file() or db_path.parent != project_root:
            raise CommandError(
                "فقط فایل SQLite موجود در ریشه پروژه قابل بازسازی است؛ "
                f"مسیر فعلی: {db_path}"
            )

        backup_dir = Path(options["backup_dir"]).resolve()
        if backup_dir == project_root or backup_dir.is_relative_to(project_root):
            raise CommandError("مسیر پشتیبان باید خارج از پوشه پروژه باشد.")
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = backup_dir / f"itam-before-demo-rebuild-{timestamp}.sqlite3"

        # SQLite's online backup API includes committed data consistently,
        # including pages that may otherwise still be in a WAL file.
        connection.close()
        source = sqlite3.connect(str(db_path))
        backup = sqlite3.connect(str(backup_path))
        try:
            source.backup(backup)
        finally:
            backup.close()
            source.close()

        if not backup_path.is_file() or backup_path.stat().st_size == 0:
            raise CommandError("ساخت نسخه پشتیبان ناموفق بود؛ پایگاه داده پاک نشد.")

        # Verify the backup before any destructive operation.
        with sqlite3.connect(str(backup_path)) as verification:
            integrity = verification.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_key_issues = verification.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or foreign_key_issues:
            raise CommandError(
                "اعتبارسنجی نسخه پشتیبان ناموفق بود؛ پایگاه داده پاک نشد. "
                f"integrity={integrity}, foreign_key_issues={len(foreign_key_issues)}"
            )
        backup_sha256 = hashlib.sha256(backup_path.read_bytes()).hexdigest()

        self.stdout.write(self.style.SUCCESS(f"نسخه پشتیبان ذخیره و اعتبارسنجی شد: {backup_path}"))
        self.stdout.write(f"SHA-256: {backup_sha256}")
        try:
            # Apply pending schema migrations before flush/seed. Any failure
            # enters the restore path below, keeping the original DB recoverable.
            call_command("migrate", interactive=False, verbosity=0)
            call_command("flush", interactive=False, verbosity=0)
            call_command(
                "seed_demo",
                admin_password=options["admin_password"],
                assets=options["assets"],
                no_demo_tickets=options["no_demo_tickets"],
            )
            with sqlite3.connect(str(db_path)) as verification:
                integrity = verification.execute("PRAGMA integrity_check").fetchone()[0]
                foreign_key_issues = verification.execute("PRAGMA foreign_key_check").fetchall()
            if integrity != "ok" or foreign_key_issues:
                raise CommandError(
                    "اعتبارسنجی پایگاه بازسازی‌شده ناموفق بود: "
                    f"integrity={integrity}, foreign_key_issues={len(foreign_key_issues)}"
                )
        except Exception as seed_error:
            self.stderr.write(self.style.ERROR("بازسازی نمونه ناموفق بود؛ تلاش برای بازیابی نسخه پشتیبان..."))
            try:
                connection.close()
                source_backup = sqlite3.connect(str(backup_path))
                target = sqlite3.connect(str(db_path))
                try:
                    source_backup.backup(target)
                finally:
                    target.close()
                    source_backup.close()
                connection.close()
            except Exception as restore_error:
                raise CommandError(
                    "بازسازی و بازیابی خودکار ناموفق بود. نسخه پشتیبان سالم در این مسیر باقی است: "
                    f"{backup_path}. خطای بازیابی: {restore_error}"
                ) from seed_error
            raise CommandError(
                "داده‌های قبلی از نسخه پشتیبان بازیابی شدند. "
                f"علت شکست seed_demo: {seed_error}"
            ) from seed_error

        self.stdout.write(self.style.SUCCESS("پایگاه داده نمونه با موفقیت بازسازی شد."))
        self.stdout.write(f"نسخه پشتیبان قبلی: {backup_path}")
