from django.db import migrations, models
import django.db.models.deletion


def mark_existing_computing_categories(apps, schema_editor):
    AssetCategory = apps.get_model("assets", "AssetCategory")
    AssetCategory.objects.filter(requires_component_tracking=True).update(is_computing_device=True)


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="assetcategory",
            name="is_computing_device",
            field=models.BooleanField(
                default=False,
                help_text="برای رایانه رومیزی و لپ‌تاپ فعال شود تا مشخصات اختصاصی رایانه نمایش داده شود.",
                verbose_name="تجهیز رایانه‌ای",
            ),
        ),
        migrations.RunPython(mark_existing_computing_categories, migrations.RunPython.noop),
        migrations.CreateModel(
            name="AssetRelationship",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="زمان ثبت")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="آخرین ویرایش")),
                ("relationship_type", models.CharField(
                    choices=[
                        ("connected_to", "متصل به"),
                        ("depends_on", "وابسته به"),
                        ("uses", "استفاده می‌کند از"),
                    ], default="connected_to", max_length=20, verbose_name="نوع ارتباط",
                )),
                ("connection_type", models.CharField(
                    blank=True,
                    choices=[
                        ("usb", "USB"), ("ethernet", "شبکه کابلی"), ("wifi", "Wi-Fi"),
                        ("shared", "اشتراک‌گذاری شبکه‌ای"), ("other", "سایر"),
                    ], max_length=20, verbose_name="روش اتصال",
                )),
                ("is_active", models.BooleanField(default=True, verbose_name="ارتباط فعال")),
                ("notes", models.CharField(blank=True, max_length=250, verbose_name="توضیحات")),
                ("asset", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="outgoing_relationships", to="assets.asset", verbose_name="دارایی مبدأ",
                )),
                ("related_asset", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="incoming_relationships", to="assets.asset", verbose_name="دارایی مرتبط",
                )),
            ],
            options={
                "verbose_name": "ارتباط دارایی",
                "verbose_name_plural": "ارتباطات دارایی‌ها",
                "ordering": ("asset__asset_tag", "related_asset__asset_tag"),
            },
        ),
        migrations.AddConstraint(
            model_name="assetrelationship",
            constraint=models.UniqueConstraint(
                fields=("asset", "related_asset", "relationship_type"), name="unique_asset_relationship",
            ),
        ),
        migrations.AddConstraint(
            model_name="assetrelationship",
            constraint=models.CheckConstraint(
                condition=~models.Q(asset=models.F("related_asset")), name="asset_relationship_not_self",
            ),
        ),
    ]
