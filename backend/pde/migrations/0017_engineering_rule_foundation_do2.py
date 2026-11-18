from django.db import migrations


RULE_ACTIONS = [
    ("production.engineering.rule.view", "查看工程规则定义"),
    ("production.engineering.rule.create", "创建工程规则草稿"),
    ("production.engineering.rule.update_draft", "修改工程规则草稿"),
    ("production.engineering.rule.release", "评审、发布或失效工程规则"),
]


def configure_do2_rule_authority(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    Role = apps.get_model("system", "Role")
    RolePermission = apps.get_model("system", "RolePermission")

    permissions = {}
    for code, name in RULE_ACTIONS:
        permissions[code], _ = Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "module": "PRODUCTION"},
        )

    # Reuse the existing formal planning/engineering role.  No duplicate role,
    # responsibility, position, employee, or account is created here.
    plan_role = Role.objects.filter(code="PLAN_OPERATOR_V1").first()
    if plan_role:
        for permission in permissions.values():
            RolePermission.objects.get_or_create(role=plan_role, permission=permission)


class Migration(migrations.Migration):
    dependencies = [("pde", "0016_a1_final_industry_semantics")]
    operations = [
        migrations.RunPython(configure_do2_rule_authority, migrations.RunPython.noop),
    ]
