from django.db import migrations


ACTIONS = [
    ("production.engineering.version.maintain", "维护生产工程版本"),
    ("production.engineering.version.release", "发布或失效生产工程版本"),
    ("production.engineering.document.maintain", "维护工程资料版本"),
    ("production.engineering.document.release", "发布或失效工程资料版本"),
    ("production.engineering.release", "评审、发布或失效制造输出"),
    ("production.engineering.readiness.maintain", "维护产品工程准备状态"),
]


def configure_engineering_permissions(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    RolePermission = apps.get_model("system", "RolePermission")
    permissions = {}
    for code, name in ACTIONS:
        permissions[code], _ = Permission.objects.update_or_create(
            code=code, defaults={"name": name, "module": "PRODUCTION"},
        )
    eligible_role_ids = set(RolePermission.objects.filter(
        permission__code__in=[
            "production.master_data.product.maintain",
            "production.master_data.bom.maintain",
            "production.master_data.routing.maintain",
        ],
    ).values_list("role_id", flat=True))
    for role_id in eligible_role_ids:
        for permission in permissions.values():
            RolePermission.objects.get_or_create(role_id=role_id, permission=permission)


class Migration(migrations.Migration):
    dependencies = [("pde", "0009_stable_business_references_a15")]
    operations = [migrations.RunPython(configure_engineering_permissions, migrations.RunPython.noop)]
