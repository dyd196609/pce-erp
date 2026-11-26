"""Register exactly three read permissions through the original data-migration pattern."""
from django.db import migrations

# Historical migration values are immutable, independent of future catalog edits.
READ_PERMISSIONS = (
    ("procurement.purchase_inquiry.read", "采购询价读取", "SCM"),
    ("procurement.supplier_quotation.read", "供应商报价读取", "SCM"),
    ("procurement.price_approval_preparation.read", "核价准备读取", "SCM"),
)


def register_permissions(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    for code, name, module in READ_PERMISSIONS:
        row, created = Permission.objects.get_or_create(
            code=code, defaults={"name": name, "module": module})
        if not created and (row.name != name or row.module != module):
            raise RuntimeError("SCM_READ_PERMISSION_REGISTRATION_CONFLICT: " + code)


def unregister_permissions(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    RolePermission = apps.get_model("system", "RolePermission")
    codes = [row[0] for row in READ_PERMISSIONS]
    if RolePermission.objects.filter(permission__code__in=codes).exists():
        raise RuntimeError("SCM_READ_PERMISSION_STILL_ASSIGNED_USE_FORMAL_MAINTENANCE")
    Permission.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):
    dependencies = [("procurement", "0093_m09_native_scope_proofs")]
    operations = [migrations.RunPython(register_permissions, unregister_permissions)]

