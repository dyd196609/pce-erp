from django.db import migrations, models
import django.db.models.deletion


def preserve_legacy_headers(apps, schema_editor):
    ProductBOM = apps.get_model("pde", "ProductBOM")
    Routing = apps.get_model("pde", "Routing")
    # The historical model still carries the legacy default ordering until the
    # AlterModelOptions operations below.  Always replace it with a field that
    # exists in this migration state so this data migration cannot resolve the
    # removed bom_version field.
    for row in ProductBOM.objects.filter(bom_code__isnull=True).order_by("pk"):
        row.bom_code = f"BOM-LEGACY-{row.pk:06d}"
        row.name = row.name or f"{row.product.product_name} BOM"
        row.company_id = row.product.company_id
        row.save(update_fields=["bom_code", "name", "company_id"])
    # Same compatibility guard for the removed routing_version and
    # operation_sequence fields in Routing's legacy default ordering.
    for row in Routing.objects.filter(routing_code__isnull=True).order_by("pk"):
        row.routing_code = f"ROUTE-LEGACY-{row.pk:06d}"
        row.name = row.name or f"{row.product.product_name} 工艺路线"
        row.company_id = row.product.company_id
        row.save(update_fields=["routing_code", "name", "company_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("masterdata", "0009_unit_and_code_governance_a1"),
        ("pde", "0005_product_engineering_readiness"),
        ("system", "0010_positionworkflowresponsibility_workflow_node"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, verbose_name="分类编码")),
                ("name", models.CharField(max_length=120, verbose_name="分类名称")),
                ("industry_type", models.CharField(choices=[("printing", "印刷"), ("wholeHouseWood", "全屋定制/整木"), ("general", "通用制造")], default="general", max_length=32, verbose_name="行业类型")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("effective_from", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("effective_to", models.DateField(blank=True, null=True, verbose_name="失效日期")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="product_categories", to="system.company", verbose_name="所属公司")),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="children", to="pde.productcategory", verbose_name="上级分类")),
            ],
            options={"db_table": "pde_product_category", "ordering": ("company_id", "code")},
        ),
        migrations.AddConstraint(model_name="productcategory", constraint=models.UniqueConstraint(fields=("company", "code"), name="pde_product_category_company_code_unique")),
        migrations.CreateModel(
            name="WorkCenter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, verbose_name="工作中心编码")),
                ("name", models.CharField(max_length=120, verbose_name="工作中心名称")),
                ("standard_labor_capacity", models.DecimalField(decimal_places=4, default=0, max_digits=18, verbose_name="标准人工产能")),
                ("machine_hours", models.DecimalField(decimal_places=4, default=0, max_digits=18, verbose_name="机器工时")),
                ("unit_labor_cost", models.DecimalField(decimal_places=4, default=0, max_digits=18, verbose_name="单位人工成本")),
                ("manufacturing_overhead", models.DecimalField(decimal_places=4, default=0, max_digits=18, verbose_name="制造费用")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("effective_from", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("effective_to", models.DateField(blank=True, null=True, verbose_name="失效日期")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="production_work_centers", to="system.company", verbose_name="所属公司")),
                ("department", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="production_work_centers", to="system.department", verbose_name="所属部门")),
                ("workshop", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="production_work_centers", to="system.workshop", verbose_name="所属车间")),
            ],
            options={"db_table": "pde_work_center", "ordering": ("company_id", "code")},
        ),
        migrations.AddConstraint(model_name="workcenter", constraint=models.UniqueConstraint(fields=("company", "code"), name="pde_work_center_company_code_unique")),
        migrations.AddConstraint(model_name="workcenter", constraint=models.CheckConstraint(condition=models.Q(standard_labor_capacity__gte=0), name="pde_wc_labor_capacity_nonnegative")),
        migrations.AddConstraint(model_name="workcenter", constraint=models.CheckConstraint(condition=models.Q(machine_hours__gte=0), name="pde_wc_machine_hours_nonnegative")),
        migrations.AddConstraint(model_name="workcenter", constraint=models.CheckConstraint(condition=models.Q(unit_labor_cost__gte=0), name="pde_wc_labor_cost_nonnegative")),
        migrations.AddConstraint(model_name="workcenter", constraint=models.CheckConstraint(condition=models.Q(manufacturing_overhead__gte=0), name="pde_wc_overhead_nonnegative")),
        migrations.CreateModel(
            name="Equipment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, verbose_name="设备编码")),
                ("name", models.CharField(max_length=120, verbose_name="设备名称")),
                ("equipment_type", models.CharField(blank=True, max_length=80, verbose_name="设备类型")),
                ("capacity_per_hour", models.DecimalField(decimal_places=4, default=0, max_digits=18, verbose_name="小时产能")),
                ("interface_identity", models.CharField(blank=True, help_text="只登记标准接口边界；协议、PLC和数据点需真实设备资料另行确认。", max_length=120, verbose_name="标准接口标识")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("effective_from", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("effective_to", models.DateField(blank=True, null=True, verbose_name="失效日期")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("work_center", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="equipment", to="pde.workcenter", verbose_name="所属工作中心")),
            ],
            options={"db_table": "pde_equipment", "ordering": ("work_center__company_id", "code")},
        ),
        migrations.AddConstraint(model_name="equipment", constraint=models.UniqueConstraint(fields=("work_center", "code"), name="pde_equipment_work_center_code_unique")),
        migrations.AddConstraint(model_name="equipment", constraint=models.CheckConstraint(condition=models.Q(capacity_per_hour__gte=0), name="pde_equipment_capacity_nonnegative")),
        migrations.AddField(model_name="productdefinition", name="company", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="product_definitions", to="system.company", verbose_name="所属公司")),
        migrations.AddField(model_name="productdefinition", name="category", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="products", to="pde.productcategory", verbose_name="产品分类")),
        migrations.AddField(model_name="productdefinition", name="material", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="product_definitions", to="masterdata.material", verbose_name="成品/半成品物料")),
        migrations.AddField(model_name="productdefinition", name="is_active", field=models.BooleanField(default=True, verbose_name="是否启用")),
        migrations.AddField(model_name="productdefinition", name="effective_from", field=models.DateField(blank=True, null=True, verbose_name="生效日期")),
        migrations.AddField(model_name="productdefinition", name="effective_to", field=models.DateField(blank=True, null=True, verbose_name="失效日期")),
        migrations.RemoveConstraint(model_name="productbom", name="pde_bom_product_version_material_unique"),
        migrations.AddField(model_name="productbom", name="company", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="product_boms", to="system.company", verbose_name="所属公司")),
        migrations.AddField(model_name="productbom", name="bom_code", field=models.CharField(blank=True, max_length=64, null=True, unique=True, verbose_name="BOM编码")),
        migrations.AddField(model_name="productbom", name="name", field=models.CharField(blank=True, max_length=160, verbose_name="BOM名称")),
        migrations.AddField(model_name="productbom", name="is_active", field=models.BooleanField(default=True, verbose_name="是否启用")),
        migrations.AddField(model_name="productbom", name="effective_from", field=models.DateField(blank=True, null=True, verbose_name="生效日期")),
        migrations.AddField(model_name="productbom", name="effective_to", field=models.DateField(blank=True, null=True, verbose_name="失效日期")),
        migrations.RemoveField(model_name="productbom", name="bom_version"),
        migrations.RemoveField(model_name="productbom", name="emd_material_code"),
        migrations.RemoveField(model_name="productbom", name="material_name"),
        migrations.RemoveField(model_name="productbom", name="quantity"),
        migrations.RemoveField(model_name="productbom", name="unit"),
        migrations.RemoveConstraint(model_name="routing", name="pde_routing_product_version_sequence_unique"),
        migrations.AddField(model_name="routing", name="company", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="product_routings", to="system.company", verbose_name="所属公司")),
        migrations.AddField(model_name="routing", name="routing_code", field=models.CharField(blank=True, max_length=64, null=True, unique=True, verbose_name="工艺路线编码")),
        migrations.AddField(model_name="routing", name="name", field=models.CharField(blank=True, max_length=160, verbose_name="工艺路线名称")),
        migrations.AddField(model_name="routing", name="is_active", field=models.BooleanField(default=True, verbose_name="是否启用")),
        migrations.AddField(model_name="routing", name="effective_from", field=models.DateField(blank=True, null=True, verbose_name="生效日期")),
        migrations.AddField(model_name="routing", name="effective_to", field=models.DateField(blank=True, null=True, verbose_name="失效日期")),
        migrations.RemoveField(model_name="routing", name="routing_version"),
        migrations.RemoveField(model_name="routing", name="operation_sequence"),
        migrations.RemoveField(model_name="routing", name="operation_name"),
        migrations.RemoveField(model_name="routing", name="emd_work_center_code"),
        migrations.RemoveField(model_name="routing", name="standard_hours"),
        migrations.AlterModelOptions(
            name="productbom",
            options={"ordering": ("product__product_code", "bom_code")},
        ),
        migrations.AlterModelOptions(
            name="routing",
            options={"ordering": ("product__product_code", "routing_code")},
        ),
        migrations.RunPython(preserve_legacy_headers, migrations.RunPython.noop),
        migrations.AddField(model_name="bomversion", name="bom", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="pde.productbom", verbose_name="BOM主表")),
        migrations.RemoveField(model_name="bomversion", name="material_list"),
        migrations.AddField(model_name="routingversion", name="routing", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="pde.routing", verbose_name="工艺路线主表")),
        migrations.RemoveField(model_name="routingversion", name="operation_list"),
        migrations.CreateModel(
            name="BOMItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("line_no", models.PositiveIntegerField(verbose_name="行号")),
                ("quantity", models.DecimalField(decimal_places=6, max_digits=18, verbose_name="数量")),
                ("scrap_rate", models.DecimalField(decimal_places=6, default=0, max_digits=8, verbose_name="损耗率")),
                ("effective_from", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("effective_to", models.DateField(blank=True, null=True, verbose_name="失效日期")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("bom_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="items", to="pde.bomversion", verbose_name="BOM版本")),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bom_items", to="masterdata.material", verbose_name="物料")),
                ("uom", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bom_items", to="masterdata.unitofmeasure", verbose_name="单位")),
            ],
            options={"db_table": "pde_bom_item", "ordering": ("bom_version_id", "line_no")},
        ),
        migrations.AddConstraint(model_name="bomitem", constraint=models.UniqueConstraint(fields=("bom_version", "line_no"), name="pde_bom_item_version_line_unique")),
        migrations.AddConstraint(model_name="bomitem", constraint=models.UniqueConstraint(fields=("bom_version", "material"), name="pde_bom_item_version_material_unique")),
        migrations.AddConstraint(model_name="bomitem", constraint=models.CheckConstraint(condition=models.Q(quantity__gt=0), name="pde_bom_item_quantity_positive")),
        migrations.AddConstraint(model_name="bomitem", constraint=models.CheckConstraint(condition=models.Q(scrap_rate__gte=0, scrap_rate__lt=1), name="pde_bom_item_scrap_rate_range")),
        migrations.CreateModel(
            name="BOMItemSubstitute",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("priority", models.PositiveIntegerField(default=1, verbose_name="优先级")),
                ("conversion_rate", models.DecimalField(decimal_places=6, default=1, max_digits=18, verbose_name="替代换算率")),
                ("effective_from", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("effective_to", models.DateField(blank=True, null=True, verbose_name="失效日期")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("bom_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="substitutes", to="pde.bomitem", verbose_name="BOM明细")),
                ("substitute_material", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bom_substitute_usages", to="masterdata.material", verbose_name="替代物料")),
            ],
            options={"db_table": "pde_bom_item_substitute", "ordering": ("bom_item_id", "priority", "id")},
        ),
        migrations.AddConstraint(model_name="bomitemsubstitute", constraint=models.UniqueConstraint(fields=("bom_item", "substitute_material"), name="pde_bom_substitute_material_unique")),
        migrations.AddConstraint(model_name="bomitemsubstitute", constraint=models.CheckConstraint(condition=models.Q(conversion_rate__gt=0), name="pde_bom_substitute_rate_positive")),
        migrations.CreateModel(
            name="RoutingStep",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveIntegerField(verbose_name="步骤顺序")),
                ("standard_hours", models.DecimalField(decimal_places=4, max_digits=12, verbose_name="标准工时")),
                ("setup_hours", models.DecimalField(decimal_places=4, default=0, max_digits=12, verbose_name="准备工时")),
                ("transfer_hours", models.DecimalField(decimal_places=4, default=0, max_digits=12, verbose_name="转移工时")),
                ("quality_checkpoint", models.BooleanField(default=False, verbose_name="质量检查点")),
                ("instruction", models.TextField(blank=True, verbose_name="操作说明")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("operation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="routing_steps", to="system.process", verbose_name="正式工序")),
                ("routing_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="steps", to="pde.routingversion", verbose_name="路线版本")),
                ("work_center", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="routing_steps", to="pde.workcenter", verbose_name="正式工作中心")),
            ],
            options={"db_table": "pde_routing_step", "ordering": ("routing_version_id", "sequence")},
        ),
        migrations.AddConstraint(model_name="routingstep", constraint=models.UniqueConstraint(fields=("routing_version", "sequence"), name="pde_routing_step_version_sequence_unique")),
        migrations.AddConstraint(model_name="routingstep", constraint=models.CheckConstraint(condition=models.Q(standard_hours__gt=0), name="pde_routing_step_standard_hours_positive")),
        migrations.AddConstraint(model_name="routingstep", constraint=models.CheckConstraint(condition=models.Q(setup_hours__gte=0), name="pde_routing_step_setup_hours_nonnegative")),
        migrations.AddConstraint(model_name="routingstep", constraint=models.CheckConstraint(condition=models.Q(transfer_hours__gte=0), name="pde_routing_step_transfer_hours_nonnegative")),
    ]
