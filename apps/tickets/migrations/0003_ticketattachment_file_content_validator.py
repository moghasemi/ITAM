from django.db import migrations, models
import apps.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0002_ticket_center"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ticketattachment",
            name="file",
            field=models.FileField(
                upload_to="tickets/%Y/%m/",
                validators=[apps.core.validators.validate_document_file],
                verbose_name="فایل",
            ),
        ),
    ]
