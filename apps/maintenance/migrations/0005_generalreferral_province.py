from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("org", "0010_contract_center_assignment"),
        ("maintenance", "0004_decision_attachments"),
    ]

    operations = [
        migrations.AddField(
            model_name="generalreferral",
            name="province",
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={"unit_type": "province"},
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="general_referrals",
                to="org.organizationalunit",
                verbose_name="استان مسئول",
            ),
        ),
    ]
