from django.db import migrations


ACTIONS = [
    ("production.master_data.view", "查看生产主数据"),
    ("production.master_data.unit.maintain", "维护计量单位"),
    ("production.master_data.product.maintain", "维护产品与产品分类"),
    ("production.master_data.resource.maintain", "维护工作中心、工序与设备"),
    ("production.master_data.bom.maintain", "维护BOM及版本明细"),
    ("production.master_data.routing.maintain", "维护工艺路线及版本步骤"),
    ("production.master_data.location.maintain", "维护库位与批号身份"),
]

CODE_RULES = [
    ("production_product", "PROD"),
    ("production_product_category", "CAT"),
    ("production_work_center", "WC"),
    ("production_operation", "PROC"),
    ("production_equipment", "EQP"),
    ("production_bom", "BOM"),
    ("production_routing", "ROUTE"),
    ("warehouse_location", "LOC"),
    ("inventory_lot", "LOT"),
]


def configure_a1_governance(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    Role = apps.get_model("system", "Role")
    RolePermission = apps.get_model("system", "RolePermission")
    CodeRule = apps.get_model("masterdata", "CodeRule")
    permissions = {}
    for code, name in ACTIONS:
        permissions[code], _ = Permission.objects.update_or_create(
            code=code, defaults={"name": name, "module": "PRODUCTION"}
        )
    plan_role = Role.objects.filter(code="PLAN_OPERATOR_V1").first()
    if plan_role:
        RolePermission.objects.get_or_create(
            role=plan_role, permission=permissions["production.master_data.view"]
        )
    for entity_type, prefix in CODE_RULES:
        CodeRule.objects.get_or_create(
            entity_type=entity_type,
            company_id=1,
            defaults={
                "prefix": prefix,
                "date_format": "%Y%m",
                "seq_length": 6,
                "current_seq": 0,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("pde", "0006_production_master_data_a1"),
        ("system", "0011_process_operation_governance_a1"),
    ]
    operations = [
        migrations.RunPython(configure_a1_governance, migrations.RunPython.noop),
    ]
