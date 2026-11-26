"""User-approved single execution qualification; no schema/role writes."""
from django.db import migrations

CODE = "procurement.quote_comparison.register"
NAME = "正式报价比较登记及准备生成"


def register(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    row, created = Permission.objects.get_or_create(code=CODE, defaults={"name": NAME, "module": "SCM"})
    if not created and (row.name != NAME or row.module != "SCM"):
        raise RuntimeError("QUOTE_COMPARISON_PERMISSION_CONFLICT")


def unregister(apps, schema_editor):
    if apps.get_model("system", "RolePermission").objects.filter(permission__code=CODE).exists():
        raise RuntimeError("QUOTE_COMPARISON_PERMISSION_STILL_ASSIGNED")
    apps.get_model("system", "Permission").objects.filter(code=CODE).delete()


class Migration(migrations.Migration):
    dependencies = [("procurement", "0094_scm_read_permissions")]
    operations = [migrations.RunPython(register, unregister)]
