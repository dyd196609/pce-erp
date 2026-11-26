from django.db import migrations, models


class Migration(migrations.Migration):
    # The deployed compatibility branch has no MPS/MRP schema. This field can
    # be applied on that branch without applying its separate planning chain.
    dependencies = [
        ("planning", "0007_demand_manufacturing_source_identity"),
    ]

    operations = [
        migrations.AddField(
            model_name="productionplan",
            name="planned_start_date",
            field=models.DateField("计划开始日期", blank=True, null=True),
        ),
    ]
