from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("planning", "0003_demand_sales_order_source"),
        ("pde", "0008_engineering_fact_source_a15"),
        ("sales", "0002_sales_order_engineering_refs_a15"),
    ]

    operations = [
        migrations.AddField(model_name="demand", name="product_definition", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="planning_demands", to="pde.productdefinition", verbose_name="产品工程定义")),
        migrations.AddField(model_name="demand", name="product_version", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="planning_demands", to="pde.productversion", verbose_name="产品版本")),
        migrations.AddField(model_name="demand", name="manufacturing_output", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="planning_demands", to="pde.productmanufacturingoutput", verbose_name="工程发布组合")),
        migrations.AddField(model_name="purchaseplan", name="planning_engine", field=models.CharField(default="DIRECT_V1", max_length=40)),
        migrations.AddField(model_name="purchaseplan", name="run_batch", field=models.CharField(blank=True, default="", max_length=80)),
        migrations.AddField(model_name="purchaseplan", name="source_version", field=models.CharField(default="DIRECT-V1", max_length=40)),
        migrations.AddField(model_name="purchaseplan", name="mps_source_id", field=models.CharField(blank=True, default="", max_length=80)),
        migrations.AddField(model_name="purchaseplan", name="mrp_source_id", field=models.CharField(blank=True, default="", max_length=80)),
        migrations.AddField(model_name="productionplan", name="planning_engine", field=models.CharField(default="DIRECT_V1", max_length=40)),
        migrations.AddField(model_name="productionplan", name="run_batch", field=models.CharField(blank=True, default="", max_length=80)),
        migrations.AddField(model_name="productionplan", name="source_version", field=models.CharField(default="DIRECT-V1", max_length=40)),
        migrations.AddField(model_name="productionplan", name="mps_source_id", field=models.CharField(blank=True, default="", max_length=80)),
        migrations.AddField(model_name="productionplan", name="mrp_source_id", field=models.CharField(blank=True, default="", max_length=80)),
    ]
