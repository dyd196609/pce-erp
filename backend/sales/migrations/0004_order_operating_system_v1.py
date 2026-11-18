import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


PROCESS_CODE = "SALES_ORDER_TO_SUPPLY_PLAN"

ACTION_DEFINITIONS = (
    ("sales.order.update", "编辑销售订单草稿", "ORDER_UPDATE", 40, "sales_order_editor", "销售订单编辑员", "OWNER"),
    ("sales.order.submit", "提交销售订单审核", "ORDER_SUBMIT", 50, "sales_order_editor", "销售订单编辑员", "OWNER"),
    ("sales.order.approve", "批准销售订单", "ORDER_APPROVE", 60, "sales_order_approver", "销售订单审批员", "APPROVER"),
    ("sales.order.engineering.start", "进入工程准备", "ENGINEERING_START", 70, "sales_order_engineering", "订单工程协调员", "EXECUTOR"),
    ("sales.order.engineering.complete", "完成工程准备", "ENGINEERING_COMPLETE", 80, "sales_order_engineering", "订单工程协调员", "EXECUTOR"),
    ("sales.order.execution.start", "开始订单执行", "EXECUTION_START", 90, "sales_order_execution", "订单执行员", "EXECUTOR"),
    ("sales.order.delivery.start", "开始订单交付", "DELIVERY_START", 100, "sales_order_execution", "订单执行员", "EXECUTOR"),
    ("sales.order.complete", "完成销售订单", "ORDER_COMPLETE", 110, "sales_order_execution", "订单执行员", "EXECUTOR"),
    ("sales.order.close", "关闭销售订单", "ORDER_CLOSE", 120, "sales_order_execution", "订单执行员", "OWNER"),
    ("sales.order.cancel", "取消销售订单", "ORDER_CANCEL", 130, "sales_order_editor", "销售订单编辑员", "OWNER"),
)


def seed_order_operating_authority(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    Role = apps.get_model("system", "Role")
    RolePermission = apps.get_model("system", "RolePermission")
    Position = apps.get_model("system", "Position")
    Responsibility = apps.get_model("system", "Responsibility")
    Mapping = apps.get_model("system", "PositionWorkflowResponsibility")
    Process = apps.get_model("workflow_runtime", "ProcessDefinition")
    Node = apps.get_model("workflow_runtime", "WorkflowNodeDefinition")

    process = Process.objects.filter(definition_code=PROCESS_CODE, active=True).first()
    position = Position.objects.filter(code="YXB-SALES", is_active=True).first()
    responsibility = Responsibility.objects.filter(code="RESP_SALES_ORDER_002", is_active=True).first()
    for action_code, action_name, node_code, sequence, role_code, role_name, ownership_type in ACTION_DEFINITIONS:
        permission, _ = Permission.objects.update_or_create(
            code=action_code, defaults={"name": action_name, "module": "SALES"},
        )
        role, _ = Role.objects.update_or_create(
            code=role_code,
            defaults={"name": role_name, "description": f"订单运作系统：{action_name}"},
        )
        RolePermission.objects.get_or_create(role=role, permission=permission)
        if process:
            node, _ = Node.objects.update_or_create(
                process_definition=process, node_code=node_code,
                defaults={
                    "node_name": action_name, "sequence": sequence,
                    "business_action_code": action_code, "active": True,
                    "description": "订单运作系统 V1 正式生命周期节点",
                },
            )
            if position and responsibility:
                Mapping.objects.update_or_create(
                    position=position, workflow_code=PROCESS_CODE, node_code=node_code,
                    ownership_type=ownership_type,
                    defaults={"responsibility": responsibility, "workflow_node": node, "active": True},
                )


class Migration(migrations.Migration):
    dependencies = [
        ("pde", "0019_manufacturing_structure_wave2"),
        ("sales", "0003_industrial_order_engineering_input_do1"),
        ("system", "0014_workshop_encoder_and_operation_measurement"),
        ("workflow_runtime", "0006_merge_formal_definitions_and_payment_backfill"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="salesorder", name="status",
            field=models.CharField(choices=[
                ("draft", "草稿"), ("submitted", "已提交"), ("approved", "已批准"),
                ("confirmed", "已确认（兼容）"), ("engineering", "工程准备中"),
                ("manufacturing_ready", "制造准备完成"), ("in_progress", "执行中"),
                ("delivering", "交付中"), ("completed", "已完成"),
                ("closed", "已关闭"), ("cancelled", "已取消"),
            ], max_length=20),
        ),
        migrations.AddField(
            model_name="salesorder", name="order_type",
            field=models.CharField(choices=[("standard", "标准订单"), ("project", "项目订单"), ("sample", "样品订单"), ("service", "服务订单")], default="standard", max_length=24),
        ),
        migrations.AddField(
            model_name="salesorder", name="order_source",
            field=models.CharField(choices=[("manual", "手工录入"), ("crm", "CRM"), ("edi", "EDI"), ("import", "导入")], default="manual", max_length=24),
        ),
        migrations.AddField(
            model_name="salesorder", name="approved_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="approved_sales_orders", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(model_name="salesorderitem", name="engineering_mode", field=models.CharField(choices=[("STANDARD", "标准产品"), ("TEMPLATE_ASSISTED", "模板辅助配置"), ("ORDER_ENGINEERED", "按单工程")], default="STANDARD", max_length=24)),
        migrations.AddField(model_name="salesorderitem", name="space_code", field=models.CharField(blank=True, default="", max_length=80)),
        migrations.AddField(model_name="salesorderitem", name="space_name", field=models.CharField(blank=True, default="", max_length=160)),
        migrations.AddField(model_name="salesorderitem", name="installation_area", field=models.CharField(blank=True, default="", max_length=200)),
        migrations.AddField(model_name="salesorderitem", name="component_category", field=models.CharField(blank=True, default="", max_length=120)),
        migrations.AddField(
            model_name="salesorderitem", name="product_configuration",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sales_order_items", to="pde.productconfiguration", verbose_name="产品配置"),
        ),
        migrations.CreateModel(
            name="SalesOrderActionRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action_code", models.CharField(max_length=120)),
                ("idempotency_key", models.CharField(max_length=160)),
                ("request_id", models.CharField(max_length=160)),
                ("source", models.CharField(default="api", max_length=80)),
                ("source_state", models.CharField(max_length=40)),
                ("target_state", models.CharField(max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sales_order_action_requests", to=settings.AUTH_USER_MODEL)),
                ("audit_record", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sales_order_action_requests", to="system.organizationoperatingauditrecord")),
                ("sales_order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="action_requests", to="sales.salesorder")),
            ],
            options={"db_table": "sales_order_action_request", "ordering": ("-created_at", "-id")},
        ),
        migrations.AddConstraint(model_name="salesorderactionrequest", constraint=models.UniqueConstraint(fields=("sales_order", "action_code", "idempotency_key"), name="uniq_sales_order_action_idempotency")),
        migrations.AddConstraint(model_name="salesorderactionrequest", constraint=models.UniqueConstraint(fields=("sales_order", "request_id"), name="uniq_sales_order_request_id")),
        migrations.RunPython(seed_order_operating_authority, migrations.RunPython.noop),
    ]
