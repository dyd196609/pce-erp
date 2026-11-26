from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("planning", "0002_planning_access_workflow_v1"),
        ("procurement", "0024_purchase_fulfillment_inventory_v1"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaserequest",
            name="source_purchase_plan",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="purchase_request",
                to="planning.purchaseplan",
                verbose_name="来源采购计划",
            ),
        ),
        migrations.AlterField(
            model_name="purchaserequest",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("PDEManufacturingInput", "PDE制造输入"),
                    ("MRPRequirement", "MRP需求"),
                    ("InventoryReplenishment", "库存补充"),
                    ("ManualRequest", "人工申请"),
                    ("PurchasePlan", "采购计划"),
                ],
                default="ManualRequest",
                max_length=40,
            ),
        ),
    ]
