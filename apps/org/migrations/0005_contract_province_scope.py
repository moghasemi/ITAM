# A province is required for all newly managed contracts. Legacy contracts are
# backfilled only when their linked centers unambiguously identify one province.
from django.db import migrations, models
import django.db.models.deletion


def assign_unambiguous_provinces(apps, schema_editor):
    Contract = apps.get_model("org", "Contract")
    Center = apps.get_model("org", "Center")
    OrganizationalUnit = apps.get_model("org", "OrganizationalUnit")
    db = schema_editor.connection.alias
    for contract in Contract.objects.using(db).filter(province__isnull=True).iterator():
        center_ids = list(
            contract.centers.using(db).values_list("pk", flat=True)
        )
        if not center_ids:
            continue
        centers = list(
            Center.objects.using(db)
            .filter(pk__in=center_ids)
            .select_related("parent_unit__parent")
        )
        province_ids = set()
        unambiguous = len(centers) == len(center_ids)
        for center in centers:
            county = center.parent_unit
            province = county.parent if county else None
            if (
                not county
                or county.unit_type != "county"
                or not province
                or province.unit_type != "province"
            ):
                unambiguous = False
                break
            province_ids.add(province.pk)
        if unambiguous and len(province_ids) == 1:
            contract.province_id = province_ids.pop()
            contract.save(using=db, update_fields=["province"])


class Migration(migrations.Migration):
    dependencies = [
        ("org", "0004_alter_center_parent_unit_alter_center_province"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="province",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="contracts",
                to="org.organizationalunit",
                verbose_name="استان محل اجرای قرارداد",
            ),
        ),
        migrations.RunPython(assign_unambiguous_provinces, migrations.RunPython.noop),
    ]
