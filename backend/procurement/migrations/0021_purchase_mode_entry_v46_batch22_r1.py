from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("procurement", "0020_standard_purchase_price_link_v46_batch2")]

    operations = [
        migrations.AddField(
            model_name="purchaserequest",
            name="purchase_mode",
            field=models.CharField(
                choices=[
                    ("STANDARD", "标准采购"),
                    ("AGREED_PRICE", "既定价格采购"),
                    ("DIRECT", "直接采购"),
                ],
                default="STANDARD",
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="purchaseorder",
            name="purchase_mode",
            field=models.CharField(
                choices=[
                    ("STANDARD", "标准采购"),
                    ("AGREED_PRICE", "既定价格采购"),
                    ("DIRECT", "直接采购"),
                    ("LEGACY", "历史兼容"),
                ],
                default="LEGACY",
                max_length=24,
            ),
        ),
    ]
