# Generated to align the model state with the shared TimeStampedModel and geographic semantics.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("org", "0006_treatment_management"),
    ]

    operations = [
        migrations.AlterField(
            model_name="center",
            name="parent_unit",
            field=models.ForeignKey(
                blank=False,
                help_text="این رابطه صرفاً موقعیت جغرافیایی مرکز را مشخص می‌کند.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="centers",
                to="org.organizationalunit",
                verbose_name="واحد سازمانی شهرستانی بالادست",
            ),
        ),
        migrations.AlterField(
            model_name="treatmentmanagement",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="زمان ثبت"),
        ),
        migrations.AlterField(
            model_name="treatmentmanagement",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, verbose_name="آخرین ویرایش"),
        ),
    ]
