from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("pde", "0003_pde_version_governance"),
    ]

    operations = [
        migrations.CreateModel(
            name="ManufacturingInputReference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_module", models.CharField(default="PDE", editable=False, max_length=16, verbose_name="来源模块")),
                ("target_module", models.CharField(choices=[("MRP", "物料需求计划"), ("SCM", "供应链管理中心")], max_length=16, verbose_name="目标模块")),
                ("source_object", models.CharField(max_length=80, verbose_name="来源对象")),
                ("target_object", models.CharField(max_length=80, verbose_name="目标对象")),
                ("reference_status", models.CharField(choices=[("draft", "草稿"), ("active", "有效引用"), ("inactive", "已停用")], default="draft", max_length=24, verbose_name="引用状态")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "pde_manufacturing_input_reference",
                "ordering": ("target_module", "source_object", "target_object"),
            },
        ),
        migrations.CreateModel(
            name="ProductManufacturingOutput",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("engineering_status", models.CharField(choices=[("incomplete", "工程资料不完整"), ("ready", "工程资料已齐套")], default="incomplete", max_length=24, verbose_name="工程状态")),
                ("effective_date", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("release_status", models.CharField(choices=[("draft", "草稿"), ("engineering_review", "工程评审中"), ("released_to_manufacturing", "已发布至制造")], default="draft", max_length=32, verbose_name="发布状态")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("bom_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_outputs", to="pde.bomversion")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_outputs", to="pde.productdefinition")),
                ("product_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_outputs", to="pde.productversion")),
                ("routing_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_outputs", to="pde.routingversion")),
            ],
            options={
                "db_table": "pde_product_manufacturing_output",
                "ordering": ("product__product_code", "product_version__version_no"),
            },
        ),
        migrations.AddConstraint(
            model_name="manufacturinginputreference",
            constraint=models.UniqueConstraint(fields=("source_module", "target_module", "source_object", "target_object"), name="pde_mfg_input_reference_unique"),
        ),
        migrations.AddConstraint(
            model_name="productmanufacturingoutput",
            constraint=models.UniqueConstraint(fields=("product", "product_version", "bom_version", "routing_version"), name="pde_mfg_output_version_set_unique"),
        ),
    ]
