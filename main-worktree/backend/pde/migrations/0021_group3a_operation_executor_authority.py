from django.db import migrations


def grant_operation_authority(apps, schema_editor):
    Role = apps.get_model("system", "Role")
    Permission = apps.get_model("system", "Permission")
    RolePermission = apps.get_model("system", "RolePermission")
    # Production originally reached this migration only after the governed
    # executor formalization service had created this role.  A blank database
    # has no such out-of-band prerequisite, so the historical migration chain
    # stopped here.  Recreate the same minimal RBAC projection deterministically
    # instead of assuming a post-migration initialization step already ran.
    role, _ = Role.objects.get_or_create(
        code="enterprise_master_data_maintainer",
        defaults={
            "name": "企业基础资料维护员",
            "description": "ENTERPRISE_MASTER_DATA_MAINTAINER 的最小技术授权投影",
        },
    )
    permission = Permission.objects.get(code="production.master_data.resource.maintain")
    RolePermission.objects.get_or_create(role=role, permission=permission)


def revoke_operation_authority(apps, schema_editor):
    RolePermission = apps.get_model("system", "RolePermission")
    RolePermission.objects.filter(
        role__code="enterprise_master_data_maintainer",
        permission__code="production.master_data.resource.maintain",
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pde", "0020_group3_transition_mode_override"),
    ]

    operations = [
        migrations.RunPython(grant_operation_authority, revoke_operation_authority),
    ]
