from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("org", "0007_align_treatment_management_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="center",
            name="is_demo",
            field=models.BooleanField(
                default=False,
                help_text="این مرکز داده آزمایشی است و نباید با مرکز واقعی اشتباه گرفته شود.",
                verbose_name="داده نمونه",
            ),
        ),
    ]
