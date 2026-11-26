from django.db import migrations


ACTIONS = [
    ("production.master_data.material.maintain", "维护生产物料与供应属性"),
    ("production.master_data.capacity.maintain", "维护标准产能"),
    ("production.engineering.source.maintain", "维护并确认工程来源"),
    ("production.engineering.rule.maintain", "维护并发布工程规则"),
    ("production.engineering.order.maintain", "维护订单工程实例"),
    ("production.engineering.calculation.record", "记录工程计算与派生事实"),
]

CODE_RULES = [
    ("production_standard_capacity", "CAP"),
    ("production_engineering_source", "ENGSRC"),
    ("production_order_engineering", "OEI"),
]


def configure_a17_authority(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    Role = apps.get_model("system", "Role")
    RolePermission = apps.get_model("system", "RolePermission")
    CodeRule = apps.get_model("masterdata", "CodeRule")
    Company = apps.get_model("system", "Company")

    permissions = {}
    for code, name in ACTIONS:
        permissions[code], _ = Permission.objects.update_or_create(
            code=code, defaults={"name": name, "module": "PRODUCTION"},
        )

    plan_role = Role.objects.filter(code="PLAN_OPERATOR_V1").first()
    if plan_role:
        for permission in permissions.values():
            RolePermission.objects.get_or_create(role=plan_role, permission=permission)

    for company_id in Company.objects.order_by("pk").values_list("pk", flat=True):
        for entity_type, prefix in CODE_RULES:
            CodeRule.objects.get_or_create(
                entity_type=entity_type,
                company_id=company_id,
                defaults={
                    "prefix": prefix,
                    "date_format": "%Y%m",
                    "seq_length": 6,
                    "current_seq": 0,
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        ("pde", "0012_engineeringbreakdownitem_and_more"),
        ("system", "0012_remove_process_system_process_standard_hours_nonnegative_and_more"),
    ]
    operations = [
        migrations.RunPython(configure_a17_authority, migrations.RunPython.noop),
    ]
