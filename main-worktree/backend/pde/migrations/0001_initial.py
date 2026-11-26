from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="ProductDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("product_code", models.CharField(max_length=64, unique=True, verbose_name="产品编码")),
                ("product_name", models.CharField(max_length=160, verbose_name="产品名称")),
                ("specification", models.CharField(blank=True, max_length=160, verbose_name="规格")),
                ("model", models.CharField(blank=True, max_length=120, verbose_name="型号")),
                ("version", models.CharField(max_length=40, verbose_name="版本")),
                ("status", models.CharField(choices=[("draft", "草稿"), ("designed", "已设计"), ("released", "已发布")], default="draft", max_length=24, verbose_name="状态")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "pde_product_definition", "ordering": ("product_code",)},
        ),
        migrations.CreateModel(
            name="ProductRequirement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("requirement_no", models.CharField(max_length=64, unique=True, verbose_name="需求编号")),
                ("customer", models.CharField(max_length=160, verbose_name="客户")),
                ("product_name", models.CharField(max_length=160, verbose_name="产品名称")),
                ("requirement_source", models.CharField(max_length=80, verbose_name="需求来源")),
                ("requirement_date", models.DateField(verbose_name="需求日期")),
                ("owner", models.CharField(max_length=80, verbose_name="负责人")),
                ("status", models.CharField(choices=[("draft", "草稿"), ("reviewing", "评审中"), ("confirmed", "已确认")], default="draft", max_length=24, verbose_name="状态")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "pde_product_requirement", "ordering": ("requirement_no",)},
        ),
        migrations.CreateModel(
            name="ProductBOM",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bom_version", models.CharField(max_length=40, verbose_name="BOM版本")),
                ("emd_material_code", models.CharField(help_text="只保存企业主数据中心物料引用，不生成第二套物料编码。", max_length=64, verbose_name="EMD物料编码")),
                ("material_name", models.CharField(max_length=160, verbose_name="物料名称")),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18, verbose_name="数量")),
                ("unit", models.CharField(max_length=24, verbose_name="单位")),
                ("status", models.CharField(default="draft", max_length=24, verbose_name="状态")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bom_lines", to="pde.productdefinition")),
            ],
            options={"db_table": "pde_product_bom", "ordering": ("product__product_code", "bom_version", "id")},
        ),
        migrations.CreateModel(
            name="Routing",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("routing_version", models.CharField(max_length=40, verbose_name="工艺版本")),
                ("operation_sequence", models.PositiveIntegerField(verbose_name="工序顺序")),
                ("operation_name", models.CharField(max_length=160, verbose_name="工序名称")),
                ("emd_work_center_code", models.CharField(max_length=64, verbose_name="EMD工作中心")),
                ("standard_hours", models.DecimalField(decimal_places=4, max_digits=12, verbose_name="标准工时")),
                ("status", models.CharField(default="draft", max_length=24, verbose_name="状态")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="routings", to="pde.productdefinition")),
            ],
            options={"db_table": "pde_routing", "ordering": ("product__product_code", "routing_version", "operation_sequence")},
        ),
        migrations.AddConstraint(model_name="productbom", constraint=models.UniqueConstraint(fields=("product", "bom_version", "emd_material_code"), name="pde_bom_product_version_material_unique")),
        migrations.AddConstraint(model_name="routing", constraint=models.UniqueConstraint(fields=("product", "routing_version", "operation_sequence"), name="pde_routing_product_version_sequence_unique")),
    ]
