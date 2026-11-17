# Generated for serialized login admission.
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_login_attempt"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoginThrottleLock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=67, unique=True, verbose_name="اثر انگشت قفل")),
                ("lock_version", models.PositiveBigIntegerField(default=0)),
                ("updated_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="آخرین استفاده")),
            ],
            options={
                "verbose_name": "قفل محدودسازی ورود",
                "verbose_name_plural": "قفل‌های محدودسازی ورود",
            },
        ),
    ]
