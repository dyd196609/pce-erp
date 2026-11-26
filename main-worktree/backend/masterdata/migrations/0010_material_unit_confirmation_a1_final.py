from django.db import migrations, models


def classify_existing_material_units(apps, schema_editor):
    Material = apps.get_model("masterdata", "Material")
    Material.objects.filter(unit="", base_uom_id__isnull=True).order_by("pk").update(
        unit_status="not_confirmed"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("masterdata", "0009_unit_and_code_governance_a1"),
    ]

    operations = [
        migrations.AlterField(
            model_name="material",
            name="unit",
            field=models.CharField(
                blank=True,
                default="",
                help_text="兼容单位投影；正式基本单位未知时必须为空。",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="material",
            name="unit_status",
            field=models.CharField(
                choices=[("confirmed", "已确认"), ("not_confirmed", "待维护")],
                default="confirmed",
                help_text="来源未提供基本单位时使用not_confirmed，不得猜填工程派生单位。",
                max_length=20,
            ),
        ),
        migrations.RunPython(classify_existing_material_units, migrations.RunPython.noop),
    ]
