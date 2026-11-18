from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("pde", "0002_pde_emd_relationships")]

    operations = [
        migrations.CreateModel(
            name="ProductVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version_no", models.CharField(max_length=40, verbose_name="版本号")),
                ("version_status", models.CharField(choices=[("draft", "草稿"), ("reviewed", "已评审"), ("released", "已发布"), ("obsolete", "已失效")], default="draft", max_length=24, verbose_name="版本状态")),
                ("effective_date", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("expire_date", models.DateField(blank=True, null=True, verbose_name="失效日期")),
                ("change_reason", models.CharField(blank=True, max_length=500, verbose_name="变更原因")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="product_versions", to="pde.productdefinition")),
            ],
            options={"db_table": "pde_product_version", "ordering": ("product__product_code", "version_no")},
        ),
        migrations.CreateModel(
            name="BOMVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bom_version", models.CharField(max_length=40, verbose_name="BOM版本")),
                ("material_list", models.JSONField(default=list, verbose_name="物料清单")),
                ("effective_date", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("expire_date", models.DateField(blank=True, null=True, verbose_name="失效日期")),
                ("status", models.CharField(choices=[("draft", "草稿"), ("reviewed", "已评审"), ("released", "已发布"), ("obsolete", "已失效")], default="draft", max_length=24, verbose_name="状态")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bom_versions", to="pde.productdefinition")),
                ("product_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bom_versions", to="pde.productversion")),
            ],
            options={"db_table": "pde_bom_version", "ordering": ("product__product_code", "bom_version")},
        ),
        migrations.CreateModel(
            name="RoutingVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("routing_version", models.CharField(max_length=40, verbose_name="工艺版本")),
                ("operation_list", models.JSONField(default=list, verbose_name="工序清单")),
                ("effective_date", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("expire_date", models.DateField(blank=True, null=True, verbose_name="失效日期")),
                ("status", models.CharField(choices=[("draft", "草稿"), ("reviewed", "已评审"), ("released", "已发布"), ("obsolete", "已失效")], default="draft", max_length=24, verbose_name="状态")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="routing_versions", to="pde.productdefinition")),
                ("product_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="routing_versions", to="pde.productversion")),
            ],
            options={"db_table": "pde_routing_version", "ordering": ("product__product_code", "routing_version")},
        ),
        migrations.CreateModel(
            name="EngineeringDocumentVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("document_name", models.CharField(max_length=200, verbose_name="资料名称")),
                ("document_version", models.CharField(max_length=40, verbose_name="资料版本")),
                ("effective_date", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("expire_date", models.DateField(blank=True, null=True, verbose_name="失效日期")),
                ("status", models.CharField(choices=[("draft", "草稿"), ("reviewed", "已评审"), ("released", "已发布"), ("obsolete", "已失效")], default="draft", max_length=24, verbose_name="状态")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="document_versions", to="pde.engineeringdocument")),
                ("product_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="engineering_document_versions", to="pde.productversion")),
                ("related_bom", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="document_versions", to="pde.bomversion")),
                ("related_product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="engineering_document_versions", to="pde.productdefinition")),
                ("related_routing", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="document_versions", to="pde.routingversion")),
            ],
            options={"db_table": "pde_engineering_document_version", "ordering": ("document__document_no", "document_version")},
        ),
        migrations.CreateModel(
            name="EffectiveDateControl",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order_date", models.DateField(verbose_name="订单日期")),
                ("is_effective", models.BooleanField(default=False, verbose_name="是否有效")),
                ("rejection_reason", models.CharField(blank=True, max_length=500, verbose_name="拒绝原因")),
                ("evaluated_at", models.DateTimeField(auto_now_add=True)),
                ("bom_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="effective_controls", to="pde.bomversion")),
                ("product_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="effective_controls", to="pde.productversion")),
                ("routing_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="effective_controls", to="pde.routingversion")),
            ],
            options={"db_table": "pde_effective_date_control", "ordering": ("-evaluated_at",)},
        ),
        migrations.CreateModel(
            name="EngineeringChangeNotice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("change_no", models.CharField(max_length=64, unique=True, verbose_name="变更编号")),
                ("change_type", models.CharField(choices=[("design", "设计变更"), ("material", "材料变更"), ("routing", "工艺变更"), ("document", "资料变更")], max_length=24, verbose_name="变更类型")),
                ("reason", models.CharField(max_length=500, verbose_name="变更原因")),
                ("effective_date", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("status", models.CharField(choices=[("draft", "草稿"), ("reviewing", "评审中"), ("approved", "已批准"), ("effective", "已生效")], default="draft", max_length=24, verbose_name="状态")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("after_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ecn_after", to="pde.productversion")),
                ("before_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ecn_before", to="pde.productversion")),
            ],
            options={"db_table": "pde_engineering_change_notice", "ordering": ("change_no",)},
        ),
        migrations.AddConstraint(model_name="productversion", constraint=models.UniqueConstraint(fields=("product", "version_no"), name="pde_product_version_unique")),
        migrations.AddConstraint(model_name="bomversion", constraint=models.UniqueConstraint(fields=("product", "bom_version"), name="pde_bom_version_unique")),
        migrations.AddConstraint(model_name="routingversion", constraint=models.UniqueConstraint(fields=("product", "routing_version"), name="pde_routing_version_unique")),
        migrations.AddConstraint(model_name="engineeringdocumentversion", constraint=models.UniqueConstraint(fields=("document", "document_version"), name="pde_engineering_document_version_unique")),
    ]
