# Generated for OutboxDelivery lease-based dispatch locking.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0002_outboxdelivery"),
    ]

    operations = [
        migrations.AddField(
            model_name="outboxdelivery",
            name="lock_token",
            field=models.UUIDField(blank=True, editable=False, null=True, verbose_name="شناسه قفل"),
        ),
        migrations.AddField(
            model_name="outboxdelivery",
            name="locked_until",
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="انقضای قفل"),
        ),
    ]
