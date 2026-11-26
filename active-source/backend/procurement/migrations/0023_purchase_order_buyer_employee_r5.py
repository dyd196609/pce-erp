from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pfm", "0001_initial"),
        ("procurement", "0022_direct_price_source_trace_v46_batch22_r2"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorder",
            name="buyer_employee",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=models.PROTECT,
                related_name="purchase_orders_as_buyer", to="pfm.employee",
                verbose_name="采购员正式人员档案",
            ),
        ),
    ]
