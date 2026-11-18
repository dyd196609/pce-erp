from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sales", "0004_order_operating_system_v1")]

    operations = [
        migrations.AddField(
            model_name="salesorderitem",
            name="tax_rate",
            field=models.DecimalField(decimal_places=6, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name="salesorderitem",
            name="price_tax_mode",
            field=models.CharField(
                choices=[("tax_inclusive", "含税单价"), ("tax_exclusive", "未税单价")],
                default="tax_exclusive",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="salesorderitem",
            constraint=models.CheckConstraint(
                condition=models.Q(tax_rate__gte=0, tax_rate__lte=1),
                name="sales_order_item_tax_rate_valid",
            ),
        ),
    ]
