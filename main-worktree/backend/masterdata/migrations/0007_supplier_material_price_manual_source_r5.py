from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("masterdata", "0006_price_approval_result_supplier_material_price_v45_8")]

    operations = [
        migrations.AlterField(
            model_name="suppliermaterialprice",
            name="price_approval_result",
            field=models.OneToOneField(
                blank=True, null=True, on_delete=models.PROTECT,
                related_name="effective_price", to="masterdata.priceapprovalresult",
            ),
        ),
    ]
