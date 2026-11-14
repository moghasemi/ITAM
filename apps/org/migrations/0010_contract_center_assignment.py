import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("org", "0009_center_geographic_labels"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ContractCenterAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="زمان ثبت")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخرین ویرایش")),
                ("start_date", models.DateField(verbose_name="تاریخ شروع")),
                ("end_date", models.DateField(blank=True, null=True, verbose_name="تاریخ پایان")),
                ("status", models.CharField(choices=[("planned", "برنامه‌ریزی‌شده"), ("active", "فعال"), ("ended", "پایان‌یافته")], default="planned", max_length=12, verbose_name="وضعیت")),
                ("end_reason", models.TextField(blank=True, verbose_name="دلیل پایان انتساب")),
                ("assigned_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_contract_center_assignments", to=settings.AUTH_USER_MODEL, verbose_name="ثبت‌کننده")),
                ("center", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="contractor_assignments", to="org.center", verbose_name="مرکز")),
                ("contract", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="center_assignments", to="org.contract", verbose_name="قرارداد")),
                ("ended_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ended_contract_center_assignments", to=settings.AUTH_USER_MODEL, verbose_name="پایان‌دهنده")),
            ],
            options={
                "verbose_name": "انتساب پیمانکار به مرکز",
                "verbose_name_plural": "تاریخچه انتساب پیمانکار به مراکز",
                "ordering": ("-start_date",),
            },
        ),
        migrations.AddConstraint(
            model_name="contractcenterassignment",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "active")), fields=("center",), name="unique_active_contractor_per_center"),
        ),
        migrations.AddIndex(
            model_name="contractcenterassignment",
            index=models.Index(fields=["center", "status"], name="org_contract_center_status_idx"),
        ),
    ]
