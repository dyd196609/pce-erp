from django.db import migrations


A1_MAINTENANCE_ACTIONS = [
    "production.master_data.view",
    "production.master_data.unit.maintain",
    "production.master_data.product.maintain",
    "production.master_data.resource.maintain",
    "production.master_data.bom.maintain",
    "production.master_data.routing.maintain",
    "production.master_data.location.maintain",
    "production.engineering.version.maintain",
    "production.engineering.version.release",
    "production.engineering.document.maintain",
    "production.engineering.document.release",
    "production.engineering.release",
    "production.engineering.readiness.maintain",
]


def grant_existing_plan_operator_authority(apps, schema_editor):
    """Reuse the existing planning role; never seed a duplicate identity chain."""

    Role = apps.get_model("system", "Role")
    Permission = apps.get_model("system", "Permission")
    RolePermission = apps.get_model("system", "RolePermission")

    plan_role = Role.objects.filter(code="PLAN_OPERATOR_V1").first()
    if not plan_role:
        return

    permissions = Permission.objects.filter(code__in=A1_MAINTENANCE_ACTIONS)
    for permission in permissions:
        RolePermission.objects.get_or_create(role=plan_role, permission=permission)


class Migration(migrations.Migration):
    dependencies = [("pde", "0010_engineering_permissions_a15")]
    operations = [
        migrations.RunPython(
            grant_existing_plan_operator_authority,
            migrations.RunPython.noop,
        )
    ]
