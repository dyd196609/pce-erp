import hashlib

from django.db import migrations


PROCESS_CODE = "PLAN_DEMAND_TO_SUPPLY_PLAN"
PERMISSIONS = (
    ("planning.view", "查看需求与计划主链"),
    ("planning.demand.create", "创建人工计划需求"),
    ("planning.requirement.calculate", "计算计划净需求"),
    ("planning.purchase_plan.confirm", "确认采购计划"),
    ("planning.production_plan.confirm", "确认生产计划"),
)
NODES = (
    ("CREATE_DEMAND", "创建正式需求", 10, "planning.demand.create"),
    ("CALCULATE_REQUIREMENT", "计算计划净需求", 20, "planning.requirement.calculate"),
    ("CONFIRM_PURCHASE_PLAN", "确认采购计划", 30, "planning.purchase_plan.confirm"),
    ("CONFIRM_PRODUCTION_PLAN", "确认生产计划", 40, "planning.production_plan.confirm"),
)


def seed_planning_access(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    ProcessDefinition = apps.get_model("workflow_runtime", "ProcessDefinition")
    WorkflowNodeDefinition = apps.get_model("workflow_runtime", "WorkflowNodeDefinition")
    for code, name in PERMISSIONS:
        Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "module": "PLAN"},
        )
    definition_hash = hashlib.sha256(
        "|".join(f"{code}:{sequence}:{action}" for code, _, sequence, action in NODES).encode("utf-8")
    ).hexdigest()
    process, _ = ProcessDefinition.objects.update_or_create(
        definition_code=PROCESS_CODE,
        defaults={
            "definition_name": "需求至采购/生产计划主链",
            "business_domain": "PLAN",
            "description": "最小正式计划链：需求、库存判断、净需求和供应计划分流。",
            "document_type": "PlanningRequirement",
            "version": 1,
            "active": True,
            "definition_hash": definition_hash,
        },
    )
    for node_code, node_name, sequence, action_code in NODES:
        WorkflowNodeDefinition.objects.update_or_create(
            process_definition=process,
            node_code=node_code,
            defaults={
                "node_name": node_name,
                "sequence": sequence,
                "business_action_code": action_code,
                "active": True,
                "description": "PCE计划运行 V1.0 最小正式节点",
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("planning", "0001_initial"),
        ("system", "0010_positionworkflowresponsibility_workflow_node"),
        ("workflow_runtime", "0006_merge_formal_definitions_and_payment_backfill"),
    ]

    operations = [migrations.RunPython(seed_planning_access, migrations.RunPython.noop)]

