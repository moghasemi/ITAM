# Separate the provincial treatment-management organization from geography.
from django.db import migrations, models
import django.db.models.deletion


def backfill_treatment_management(apps, schema_editor):
    OrganizationalUnit = apps.get_model("org", "OrganizationalUnit")
    TreatmentManagement = apps.get_model("org", "TreatmentManagement")
    Center = apps.get_model("org", "Center")
    db = schema_editor.connection.alias

    for province in OrganizationalUnit.objects.using(db).filter(unit_type="province").iterator():
        management, _ = TreatmentManagement.objects.using(db).get_or_create(
            province_id=province.pk,
            defaults={
                "name": f"مدیریت درمان استان {province.name}",
                "code": f"TM-{province.pk}",
                "is_active": province.is_active,
            },
        )
        Center.objects.using(db).filter(
            parent_unit__parent_id=province.pk,
            treatment_management__isnull=True,
        ).update(treatment_management_id=management.pk)


class Migration(migrations.Migration):
    dependencies = [
        ("org", "0005_contract_province_scope"),
    ]

    operations = [
        migrations.CreateModel(
            name="TreatmentManagement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخرین به‌روزرسانی")),
                ("name", models.CharField(max_length=150, verbose_name="نام مدیریت درمان")),
                ("code", models.CharField(max_length=40, unique=True, verbose_name="کد مدیریت درمان")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("notes", models.TextField(blank=True, verbose_name="یادداشت")),
                ("province", models.OneToOneField(
                    limit_choices_to={"unit_type": "province"},
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="treatment_management",
                    to="org.organizationalunit",
                    verbose_name="استان",
                )),
            ],
            options={
                "verbose_name": "مدیریت درمان استان",
                "verbose_name_plural": "مدیریت‌های درمان استان",
                "ordering": ("province__name",),
            },
        ),
        migrations.AddField(
            model_name="center",
            name="treatment_management",
            field=models.ForeignKey(
                blank=True,
                help_text="واحد سازمانی مالک مرکز؛ استان آن باید با استان محل جغرافیایی مرکز یکسان باشد.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="centers",
                to="org.treatmentmanagement",
                verbose_name="مدیریت درمان استان",
            ),
        ),
        migrations.RunPython(backfill_treatment_management, migrations.RunPython.noop),
    ]
