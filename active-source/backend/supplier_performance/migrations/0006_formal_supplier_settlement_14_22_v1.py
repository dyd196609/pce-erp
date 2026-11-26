import hashlib

from django.db import migrations, models


PROCESS_CODE = "PROCUREMENT_SUPPLIER_SETTLEMENT_V1"
PURCHASE_ACTIONS = (
    ("scm.supplier_reconciliation.create", "创建供应商对账"),
    ("scm.supplier_reconciliation.analyze", "执行供应商对账基础差异分析"),
    ("scm.supplier_reconciliation.confirm", "确认供应商对账"),
    ("scm.supplier_performance.calculate", "计算供应商采购绩效"),
    ("scm.buyer_performance.calculate", "计算采购员采购绩效"),
)
FINANCE_ACTIONS = (
    ("scm.supplier_payable.confirm", "确认供应商应付"),
    ("scm.supplier_payment_request.create", "创建供应商付款申请"),
    ("scm.supplier_payment_request.submit", "提交供应商付款申请"),
    ("scm.supplier_payment_request.approve", "批准供应商付款申请"),
    ("scm.supplier_payment_request.release", "付款申请转入待付款处理"),
    ("scm.supplier_payment_status.record", "记录供应商付款业务状态"),
    ("scm.supplier_settlement.complete", "确认供应商结算完成"),
)
NODES = (
    ("CREATE_RECONCILIATION", "创建供应商对账", 10, PURCHASE_ACTIONS[0][0], "PURCHASE"),
    ("ANALYZE_DIFFERENCES", "基础差异分析", 20, PURCHASE_ACTIONS[1][0], "PURCHASE"),
    ("CONFIRM_RECONCILIATION", "确认供应商对账", 30, PURCHASE_ACTIONS[2][0], "PURCHASE"),
    ("CONFIRM_PAYABLE", "确认供应商应付", 40, FINANCE_ACTIONS[0][0], "FINANCE"),
    ("CREATE_PAYMENT_REQUEST", "创建付款申请", 50, FINANCE_ACTIONS[1][0], "FINANCE"),
    ("SUBMIT_PAYMENT_REQUEST", "提交付款申请", 51, FINANCE_ACTIONS[2][0], "FINANCE"),
    ("APPROVE_PAYMENT_REQUEST", "批准付款申请", 52, FINANCE_ACTIONS[3][0], "FINANCE"),
    ("RELEASE_PAYMENT_REQUEST", "转入待付款处理", 53, FINANCE_ACTIONS[4][0], "FINANCE"),
    ("RECORD_PAYMENT_STATUS", "记录付款业务状态", 60, FINANCE_ACTIONS[5][0], "FINANCE"),
    ("COMPLETE_SETTLEMENT", "确认供应商结算完成", 70, FINANCE_ACTIONS[6][0], "FINANCE"),
    ("CALCULATE_SUPPLIER_PERFORMANCE", "计算供应商绩效", 80, PURCHASE_ACTIONS[3][0], "PURCHASE"),
    ("CALCULATE_BUYER_PERFORMANCE", "计算采购员绩效", 90, PURCHASE_ACTIONS[4][0], "PURCHASE"),
)


def seed_formal_foundation(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    Role = apps.get_model("system", "Role")
    RolePermission = apps.get_model("system", "RolePermission")
    Position = apps.get_model("system", "Position")
    PositionResponsibility = apps.get_model("system", "PositionResponsibility")
    Responsibility = apps.get_model("system", "Responsibility")
    Mapping = apps.get_model("system", "PositionWorkflowResponsibility")
    Process = apps.get_model("workflow_runtime", "ProcessDefinition")
    Node = apps.get_model("workflow_runtime", "WorkflowNodeDefinition")

    purchase_role, _ = Role.objects.update_or_create(
        code="purchase_manager",
        defaults={"name": "采购经理", "description": "采购业务管理与供应商结算采购侧动作"},
    )
    finance_role, _ = Role.objects.update_or_create(
        code="supplier_settlement_finance",
        defaults={"name": "供应商结算财务执行员", "description": "系统流程验收：14—22财务侧最小执行角色"},
    )
    for role, actions in ((purchase_role, PURCHASE_ACTIONS), (finance_role, FINANCE_ACTIONS)):
        for code, name in actions:
            permission, _ = Permission.objects.update_or_create(
                code=code, defaults={"name": name, "module": "SCM"}
            )
            RolePermission.objects.get_or_create(role=role, permission=permission)

    definition_hash = hashlib.sha256(
        "|".join(f"{code}:{sequence}:{action}" for code, _, sequence, action, _ in NODES).encode()
    ).hexdigest()
    process, _ = Process.objects.update_or_create(
        definition_code=PROCESS_CODE,
        defaults={
            "definition_name": "采购入库后供应商结算与绩效闭环",
            "business_domain": "SCM",
            "description": "正式采购13—22中14—22独立业务动作；不执行银行付款或总账写入。",
            "document_type": "SupplierReconciliation",
            "version": 1,
            "active": True,
            "definition_hash": definition_hash,
        },
    )
    purchase_position = Position.objects.filter(code="CGB-MGR", is_active=True).first()
    finance_position = Position.objects.filter(name="会计", is_active=True).order_by("pk").first()
    purchase_responsibility = Responsibility.objects.filter(
        code="RESP_PUR_ORDER_003", is_active=True, status="ACTIVE"
    ).first()
    finance_responsibility = Responsibility.objects.filter(
        code="RESP_FIN_ACCOUNT_001", is_active=True, status="ACTIVE"
    ).first()
    if finance_position and finance_responsibility:
        PositionResponsibility.objects.get_or_create(
            position=finance_position,
            responsibility=finance_responsibility,
            defaults={"is_primary": False, "active": True},
        )
    for node_code, node_name, sequence, action_code, owner in NODES:
        node, _ = Node.objects.update_or_create(
            process_definition=process,
            node_code=node_code,
            defaults={
                "node_name": node_name,
                "sequence": sequence,
                "business_action_code": action_code,
                "active": True,
                "description": "PCE采购结算与绩效闭环14—22 V1.0最小正式节点",
            },
        )
        position = purchase_position if owner == "PURCHASE" else finance_position
        responsibility = purchase_responsibility if owner == "PURCHASE" else finance_responsibility
        if position and responsibility:
            Mapping.objects.update_or_create(
                position=position,
                workflow_code=PROCESS_CODE,
                node_code=node_code,
                ownership_type="OWNER",
                defaults={"responsibility": responsibility, "workflow_node": node, "active": True},
            )


class Migration(migrations.Migration):
    dependencies = [
        ("supplier_performance", "0005_v84_payment_status_closed_loop"),
        ("system", "0010_positionworkflowresponsibility_workflow_node"),
        ("workflow_runtime", "0006_merge_formal_definitions_and_payment_backfill"),
        ("procurement", "0024_purchase_fulfillment_inventory_v1"),
    ]

    operations = [
        migrations.AddField(
            model_name="supplierreconciliation",
            name="inventory_transaction_ids",
            field=models.JSONField(default=list),
        ),
        migrations.AlterField(
            model_name="supplierreconciliationdifference",
            name="difference_type",
            field=models.CharField(
                choices=[
                    ("quantity_difference", "数量差异"),
                    ("quality_difference", "质量差异"),
                    ("price_difference", "价格差异"),
                    ("amount_difference", "金额差异"),
                    ("delivery_difference", "交付差异"),
                    ("other_difference", "其他差异"),
                ],
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name="suppliersettlementactionaudit",
            name="source_object_type",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="suppliersettlementactionaudit",
            name="source_object_no",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="suppliersettlementactionaudit",
            name="amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=18),
        ),
        migrations.AddField(
            model_name="suppliersettlementactionaudit",
            name="authorization_result",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="suppliersettlementactionaudit",
            name="evidence",
            field=models.JSONField(default=dict),
        ),
        migrations.RunPython(seed_formal_foundation, migrations.RunPython.noop),
    ]
