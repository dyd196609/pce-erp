import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


ACTION_CODE = "sales.order.engineering_input.maintain"
PROCESS_CODE = "SALES_ORDER_TO_SUPPLY_PLAN"


def seed_engineering_input_authority(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    Role = apps.get_model("system", "Role")
    RolePermission = apps.get_model("system", "RolePermission")
    Position = apps.get_model("system", "Position")
    Responsibility = apps.get_model("system", "Responsibility")
    Mapping = apps.get_model("system", "PositionWorkflowResponsibility")
    Process = apps.get_model("workflow_runtime", "ProcessDefinition")
    Node = apps.get_model("workflow_runtime", "WorkflowNodeDefinition")

    permission, _ = Permission.objects.update_or_create(
        code=ACTION_CODE,
        defaults={"name": "维护销售订单工程输入", "module": "SALES"},
    )
    role = Role.objects.filter(code="sales_order_operator").first()
    if role:
        RolePermission.objects.get_or_create(role=role, permission=permission)

    process = Process.objects.filter(definition_code=PROCESS_CODE, active=True).first()
    if not process:
        return
    node, _ = Node.objects.update_or_create(
        process_definition=process,
        node_code="MAINTAIN_ENGINEERING_INPUT",
        defaults={
            "node_name": "维护订单工程输入",
            "sequence": 15,
            "business_action_code": ACTION_CODE,
            "active": True,
            "description": "A1.8 DO-1订单行原始/规范工程输入正式维护节点",
        },
    )
    position = Position.objects.filter(code="YXB-SALES", is_active=True).first()
    responsibility = Responsibility.objects.filter(
        code="RESP_SALES_ORDER_002", is_active=True,
    ).first()
    if position and responsibility:
        Mapping.objects.update_or_create(
            position=position,
            workflow_code=PROCESS_CODE,
            node_code=node.node_code,
            ownership_type="OWNER",
            defaults={
                "responsibility": responsibility,
                "workflow_node": node,
                "active": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("masterdata", "0010_material_unit_confirmation_a1_final"),
        ("pde", "0016_a1_final_industry_semantics"),
        ("pfm", "0003_enterprise_organization_model_v1"),
        ("sales", "0002_sales_order_engineering_refs_a15"),
        ("system", "0013_process_workshop_a1_final"),
        ("workflow_runtime", "0006_merge_formal_definitions_and_payment_backfill"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="salesorder", name="contract_reference",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="salesorder", name="delivery_information",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="salesorder", name="engineering_document_version",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="sales_orders", to="pde.engineeringdocumentversion",
                verbose_name="订单正式文档引用",
            ),
        ),
        migrations.AddField(
            model_name="salesorder", name="external_source_no",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="salesorder", name="project_reference",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="salesorder", name="sales_owner",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="owned_sales_orders", to="pfm.employee", verbose_name="销售负责人",
            ),
        ),
        migrations.AddField(
            model_name="salesorderitem", name="configuration_reference",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="salesorderitem", name="customer_product_description",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="salesorderitem", name="customer_product_name",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="salesorderitem", name="engineering_document_version",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="sales_order_items", to="pde.engineeringdocumentversion",
                verbose_name="行图纸/工程资料引用",
            ),
        ),
        migrations.AddField(
            model_name="salesorderitem", name="engineering_requirements",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="salesorderitem", name="external_line_no",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="salesorderitem", name="quality_requirements",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="salesorderitem", name="remark",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="salesorderitem", name="specification",
            field=models.CharField(blank=True, default="", max_length=300),
        ),
        migrations.AddField(
            model_name="salesorderitem", name="uom",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="sales_order_items", to="masterdata.unitofmeasure",
                verbose_name="订单计量单位",
            ),
        ),
        migrations.CreateModel(
            name="SalesOrderItemEngineeringAttribute",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveIntegerField(default=1)),
                ("raw_source", models.CharField(max_length=200)),
                ("raw_sheet", models.CharField(blank=True, default="", max_length=120)),
                ("external_source", models.CharField(blank=True, default="", max_length=200)),
                ("raw_field", models.CharField(max_length=160)),
                ("raw_value", models.JSONField()),
                ("canonical_field", models.CharField(max_length=160)),
                ("normalized_value", models.JSONField(blank=True, null=True)),
                ("value_type", models.CharField(choices=[("string", "文本"), ("decimal", "小数"), ("integer", "整数"), ("boolean", "布尔"), ("date", "日期"), ("datetime", "日期时间"), ("code", "编码"), ("json", "结构化值")], max_length=20)),
                ("source_type", models.CharField(choices=[("CUSTOMER", "客户"), ("SITE_MEASUREMENT", "现场测量"), ("SALES", "销售"), ("DESIGN", "设计"), ("ENGINEERING_INPUT", "工程输入"), ("ENGINEERING_DERIVED", "工程派生"), ("MASTER_DATA", "主数据"), ("RULE_PARAMETER", "规则参数"), ("AGGREGATED", "汇总")], max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_sales_order_engineering_attributes", to=settings.AUTH_USER_MODEL)),
                ("engineering_document_version", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sales_order_engineering_attributes", to="pde.engineeringdocumentversion", verbose_name="来源工程资料版本")),
                ("sales_order_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="engineering_attributes", to="sales.salesorderitem", verbose_name="销售订单明细")),
                ("unit", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sales_order_engineering_attributes", to="masterdata.unitofmeasure", verbose_name="规范计量单位")),
            ],
            options={
                "db_table": "sales_order_item_engineering_attribute",
                "ordering": ("sales_order_item_id", "sequence", "id"),
            },
        ),
        migrations.AddConstraint(
            model_name="salesorderitemengineeringattribute",
            constraint=models.UniqueConstraint(
                fields=("sales_order_item", "canonical_field", "sequence"),
                name="uniq_sales_item_eng_attr_canonical_sequence",
            ),
        ),
        migrations.RunPython(seed_engineering_input_authority, migrations.RunPython.noop),
    ]
