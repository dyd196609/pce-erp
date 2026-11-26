import hashlib
import json
import datetime

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


ACTIONS = (
    ("procurement.purchase_order.submit", "提交采购订单", "purchase_manager"),
    ("procurement.purchase_order.approve", "审核采购订单", "purchase_manager"),
    ("procurement.purchase_order.review", "复核采购订单", "purchase_manager"),
    ("procurement.purchase_order.release", "下达采购订单", "purchase_manager"),
    ("procurement.receipt.receive", "采购到货收货", "warehouse"),
    ("quality.purchase.inspect", "采购来料检验", "quality_inspector"),
    ("warehouse.purchase.putaway", "采购检验合格入库", "warehouse"),
    ("procurement.purchase_order.complete", "采购订单正常结案", "purchase_manager"),
)

NODES = (
    (5, "SUBMIT_PURCHASE_ORDER", "提交采购订单", "procurement.purchase_order.submit", "CGB-MGR", "RESP_PUR_ORDER_003", "OWNER"),
    (6, "APPROVE_PURCHASE_ORDER", "审核采购订单", "procurement.purchase_order.approve", "CGB-MGR", "RESP_PUR_ORDER_003", "APPROVER"),
    (7, "REVIEW_PURCHASE_ORDER", "复核采购订单", "procurement.purchase_order.review", "CGB-MGR", "RESP_PUR_ORDER_003", "REVIEWER"),
    (8, "RELEASE_PURCHASE_ORDER", "下达采购订单", "procurement.purchase_order.release", "CGB-MGR", "RESP_PUR_ORDER_003", "APPROVER"),
    (9, "RECEIVE_PURCHASE_ORDER", "采购到货收货", "procurement.receipt.receive", "CCB-CLERK", "RESP_WH_IO_001", "EXECUTOR"),
    (10, "INSPECT_PURCHASE_RECEIPT", "采购来料检验", "quality.purchase.inspect", "PBB-QC", "RESP_QA_INSPECT_001", "EXECUTOR"),
    (11, "PUTAWAY_PURCHASE_INBOUND", "采购检验合格入库", "warehouse.purchase.putaway", "CCB-CLERK", "RESP_WH_IO_001", "EXECUTOR"),
    (12, "COMPLETE_PURCHASE_ORDER", "采购订单正常结案", "procurement.purchase_order.complete", "CGB-MGR", "RESP_PUR_ORDER_003", "OWNER"),
)


def seed_fulfillment_foundation(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    Role = apps.get_model("system", "Role")
    RolePermission = apps.get_model("system", "RolePermission")
    Position = apps.get_model("system", "Position")
    Responsibility = apps.get_model("system", "Responsibility")
    Mapping = apps.get_model("system", "PositionWorkflowResponsibility")
    Process = apps.get_model("workflow_runtime", "ProcessDefinition")
    Node = apps.get_model("workflow_runtime", "WorkflowNodeDefinition")
    Company = apps.get_model("system", "Company")
    Warehouse = apps.get_model("procurement", "Warehouse")

    roles = {role.code: role for role in Role.objects.all()}
    if "quality_inspector" not in roles:
        roles["quality_inspector"] = Role.objects.create(
            code="quality_inspector", name="质量检验员", description="采购来料质量检验执行角色"
        )
    permissions = {}
    for code, name, role_code in ACTIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code, defaults={"name": name, "module": "SCM"}
        )
        permissions[code] = permission
        for target_role in filter(None, (roles.get(role_code), roles.get("superadmin"))):
            RolePermission.objects.get_or_create(role=target_role, permission=permission)

    process = Process.objects.filter(definition_code="PROCUREMENT_PURCHASE_REQUEST_TO_ORDER").first()
    if process:
        for sequence, node_code, node_name, action_code, position_code, responsibility_code, ownership in NODES:
            position = Position.objects.filter(code=position_code).first()
            responsibility = Responsibility.objects.filter(code=responsibility_code).first()
            if not position or not responsibility:
                continue
            node, _ = Node.objects.update_or_create(
                process_definition=process,
                node_code=node_code,
                defaults={
                    "node_name": node_name,
                    "sequence": sequence,
                    "business_action_code": action_code,
                    "active": True,
                    "description": f"{node_name}正式业务节点。",
                },
            )
            Mapping.objects.update_or_create(
                position=position,
                workflow_code=process.definition_code,
                node_code=node_code,
                ownership_type=ownership,
                defaults={
                    "responsibility": responsibility,
                    "workflow_node": node,
                    "active": True,
                },
            )

    if process:
        fact = {
        "definitionCode": process.definition_code,
        "definitionName": process.definition_name,
        "businessDomain": process.business_domain,
        "description": process.description,
        "documentType": process.document_type,
        "version": process.version,
        "active": process.active,
        "nodes": list(Node.objects.filter(process_definition=process).order_by("sequence", "node_code").values(
            "node_code", "node_name", "sequence", "business_action_code", "active", "description"
        )),
    }
        fact["nodes"] = [{
            "nodeCode": row["node_code"], "nodeName": row["node_name"],
            "sequence": row["sequence"], "businessActionCode": row["business_action_code"],
            "active": row["active"], "description": row["description"],
        } for row in fact["nodes"]]
        process.definition_hash = hashlib.sha256(
            json.dumps(fact, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        process.save(update_fields=["definition_hash"])

    company = Company.objects.filter(is_active=True).order_by("id").first()
    if company:
        Warehouse.objects.update_or_create(
            code="WH-RM-001",
            defaults={
                "name": "原材料仓", "location_code": "RM-A-01",
                "company_id": company.pk, "is_active": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("masterdata", "0007_supplier_material_price_manual_source_r5"),
        ("pfm", "0003_enterprise_organization_model_v1"),
        ("system", "0010_positionworkflowresponsibility_workflow_node"),
        ("workflow_runtime", "0006_merge_formal_definitions_and_payment_backfill"),
        ("procurement", "0023_purchase_order_buyer_employee_r5"),
    ]

    operations = [
        migrations.CreateModel(
            name="Warehouse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("location_code", models.CharField(blank=True, default="", max_length=80)),
                ("company_id", models.BigIntegerField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "scm_warehouse", "ordering": ["code"]},
        ),
        migrations.AddField(model_name="purchasereceipt", name="receipt_date", field=models.DateField(default=datetime.date.today)),
        migrations.AddField(model_name="purchasereceipt", name="operator_account_id", field=models.BigIntegerField(verbose_name="收货执行账号ID")),
        migrations.AddField(model_name="purchasereceipt", name="operator_employee", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_receipts", to="pfm.employee", verbose_name="收货执行员工")),
        migrations.AddField(model_name="purchaseinspection", name="rejected_quantity", field=models.DecimalField(decimal_places=4, default=0, max_digits=18)),
        migrations.AddField(model_name="purchaseinspection", name="inspection_date", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="purchaseinspection", name="inspector_account_id", field=models.BigIntegerField(verbose_name="检验执行账号ID")),
        migrations.AddField(model_name="purchaseinspection", name="inspector_employee", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_inspections", to="pfm.employee", verbose_name="检验执行员工")),
        migrations.AddConstraint(model_name="purchaseinspection", constraint=models.CheckConstraint(condition=models.Q(("rejected_quantity__gte", 0)), name="scm_inspection_rejected_nonnegative")),
        migrations.AddField(model_name="warehouseinbound", name="warehouse", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_inbounds", to="procurement.warehouse")),
        migrations.AddField(model_name="warehouseinbound", name="inbound_date", field=models.DateField(default=datetime.date.today)),
        migrations.AddField(model_name="warehouseinbound", name="operator_account_id", field=models.BigIntegerField(verbose_name="入库执行账号ID")),
        migrations.AddField(model_name="warehouseinbound", name="operator_employee", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="warehouse_inbounds", to="pfm.employee", verbose_name="入库执行员工")),
        migrations.CreateModel(
            name="InventoryBalance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_balances", to="masterdata.material")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_balances", to="procurement.warehouse")),
            ],
            options={"db_table": "scm_inventory_balance"},
        ),
        migrations.AddConstraint(model_name="inventorybalance", constraint=models.UniqueConstraint(fields=("warehouse", "material"), name="scm_inventory_balance_unique")),
        migrations.AddConstraint(model_name="inventorybalance", constraint=models.CheckConstraint(condition=models.Q(("quantity__gte", 0)), name="scm_inventory_balance_nonnegative")),
        migrations.CreateModel(
            name="InventoryTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("transaction_no", models.CharField(max_length=80, unique=True)),
                ("direction", models.CharField(choices=[("IN", "入库"), ("OUT", "出库")], default="IN", max_length=8)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("before_quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("after_quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("operator_account_id", models.BigIntegerField()),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_transactions", to="masterdata.material")),
                ("operator_employee", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_transactions", to="pfm.employee")),
                ("source_inbound", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_transactions", to="procurement.warehouseinbound")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_transactions", to="procurement.warehouse")),
            ],
            options={"db_table": "scm_inventory_transaction", "ordering": ["-occurred_at", "-id"]},
        ),
        migrations.AddConstraint(model_name="inventorytransaction", constraint=models.UniqueConstraint(fields=("source_inbound", "material"), name="scm_inventory_transaction_inbound_material_unique")),
        migrations.AddConstraint(model_name="inventorytransaction", constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="scm_inventory_transaction_positive")),
        migrations.RunPython(seed_fulfillment_foundation, migrations.RunPython.noop),
    ]
