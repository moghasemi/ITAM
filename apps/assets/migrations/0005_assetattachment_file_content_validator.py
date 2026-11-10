from django.db import migrations, models
import apps.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0004_merge_20261107_1433"),
    ]

    operations = [
        migrations.AlterField(
            model_name="assetattachment",
            name="file",
            field=models.FileField(
                upload_to="assets/%Y/%m/",
                validators=[apps.core.validators.validate_document_file],
                verbose_name="فایل",
            ),
        ),
    ]
