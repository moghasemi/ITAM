from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("org", "0008_center_is_demo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="center",
            name="parent_unit",
            field=models.ForeignKey(
                blank=False,
                help_text="این رابطه صرفاً موقعیت جغرافیایی مرکز را مشخص می‌کند.",
                null=True,
                on_delete=models.PROTECT,
                related_name="centers",
                to="org.organizationalunit",
                verbose_name="شهرستان جغرافیایی",
            ),
        ),
        migrations.AlterField(
            model_name="center",
            name="province",
            field=models.CharField(
                blank=True,
                default="مرکزی",
                help_text="این فیلد منسوخ شده است؛ استان از شهرستان جغرافیایی بالادست استخراج می‌شود.",
                max_length=80,
                verbose_name="استان (منسوخ‌شده)",
            ),
        ),
    ]
