# Generated merge migration for parallel asset model changes.
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0002_assetcategory_computing_and_relationships"),
        ("assets", "0003_asset_is_quarantined_asset_quarantine_notes_and_more"),
    ]

    operations = []
