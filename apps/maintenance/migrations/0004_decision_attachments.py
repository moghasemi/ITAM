from django.db import migrations, models
import apps.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("maintenance", "0003_merge_maintenance_migrations"),
    ]

    operations = [
        migrations.AddField(
            model_name="repairrequest",
            name="cost_dispute_attachment",
            field=models.FileField(
                blank=True,
                upload_to="repairs/cost-disputes/%Y/%m/",
                validators=[apps.core.validators.validate_document_file],
                verbose_name="مستند تصمیم اختلاف هزینه",
            ),
        ),
        migrations.AddField(
            model_name="generalreferral",
            name="resolution_attachment",
            field=models.FileField(
                blank=True,
                upload_to="referrals/resolutions/%Y/%m/",
                validators=[apps.core.validators.validate_document_file],
                verbose_name="مستند نتیجه / دستور",
            ),
        ),
    ]
