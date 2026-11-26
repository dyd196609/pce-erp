import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        # The released compatibility database has 0004 and no MPS/MRP schema.
        # This increment uses only columns already introduced through 0004.
        ("planning", "0004_engineering_and_plan_compatibility_a15"),
    ]

    operations = [
        migrations.AlterField(
            model_name="demand", name="sales_order_item",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="planning_demands", to="sales.salesorderitem",
            ),
        ),
        migrations.AddConstraint(
            model_name="demand",
            constraint=models.UniqueConstraint(
                fields=("sales_order_item", "manufacturing_output"),
                condition=models.Q(sales_order_item__isnull=False, manufacturing_output__isnull=False),
                name="planning_demand_item_output_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="demand",
            constraint=models.UniqueConstraint(
                fields=("sales_order_item",),
                condition=models.Q(sales_order_item__isnull=False, manufacturing_output__isnull=True),
                name="planning_demand_item_unversioned_unique",
            ),
        ),
    ]
