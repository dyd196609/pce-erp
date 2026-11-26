from django.db import migrations, models
from django.db.models import Q


FORMAL_MATERIAL_TYPES = [
    ("raw", "原材料"),
    ("semi", "半成品"),
    ("finished", "成品"),
    ("auxiliary", "辅料"),
    ("fixed_asset", "固定资产"),
]


def normalize_material_supply_facts(apps, schema_editor):
    """Preserve ambiguity instead of guessing purchase versus production."""
    Material = apps.get_model("masterdata", "Material")
    Material.objects.filter(material_type="fixed").update(material_type="fixed_asset")
    Material.objects.filter(is_purchased=True, is_produced=True).update(
        is_purchased=False,
        is_produced=False,
    )


class Migration(migrations.Migration):
    dependencies = [("masterdata", "0007_supplier_material_price_manual_source_r5")]

    operations = [
        migrations.AlterField(
            model_name="material",
            name="material_type",
            field=models.CharField(
                choices=FORMAL_MATERIAL_TYPES,
                default="raw",
                max_length=20,
            ),
        ),
        migrations.RunPython(normalize_material_supply_facts, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="material",
            constraint=models.CheckConstraint(
                condition=~(Q(is_purchased=True) & Q(is_produced=True)),
                name="material_supply_flags_not_conflicting",
            ),
        ),
        migrations.AddConstraint(
            model_name="material",
            constraint=models.CheckConstraint(
                condition=Q(material_type__in=[
                    "raw", "semi", "finished", "auxiliary", "fixed_asset",
                ]),
                name="material_type_formal_enum",
            ),
        ),
    ]
