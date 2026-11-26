from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("pde", "0008_engineering_fact_source_a15"),
        ("sales", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesorderitem", name="product_definition",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sales_order_items", to="pde.productdefinition", verbose_name="产品工程定义"),
        ),
        migrations.AddField(
            model_name="salesorderitem", name="product_version",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sales_order_items", to="pde.productversion", verbose_name="适用产品版本"),
        ),
        migrations.AddField(
            model_name="salesorderitem", name="manufacturing_output",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sales_order_items", to="pde.productmanufacturingoutput", verbose_name="工程发布组合"),
        ),
    ]
