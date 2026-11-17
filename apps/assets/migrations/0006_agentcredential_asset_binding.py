# Generated for P1.4: bind each HWAgent credential to one asset.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0005_assetattachment_file_content_validator"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentcredential",
            name="asset",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="agent_credentials",
                to="assets.asset",
                verbose_name="دارایی اختصاصی ایجنت",
            ),
        ),
    ]
