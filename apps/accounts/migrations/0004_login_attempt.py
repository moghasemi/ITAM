# Generated for database-backed login throttling.
import django.db.models
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_org_unit_alter_user_role"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoginAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ip_address", models.GenericIPAddressField(blank=True, db_index=True, null=True, verbose_name="نشانی IP")),
                ("username_hash", models.CharField(db_index=True, max_length=64, verbose_name="شناسه یک‌طرفه نام کاربری")),
                ("attempted_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="زمان تلاش")),
            ],
            options={
                "verbose_name": "تلاش ناموفق ورود",
                "verbose_name_plural": "تلاش‌های ناموفق ورود",
                "indexes": [
                    models.Index(fields=["username_hash", "attempted_at"], name="accounts_login_user_time_idx"),
                    models.Index(fields=["ip_address", "attempted_at"], name="accounts_login_ip_time_idx"),
                ],
            },
        ),
    ]
