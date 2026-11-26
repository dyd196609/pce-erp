from django.db import migrations


READ_PERMISSIONS = (
    ("warehouse.inventory.read", "读取库存余额", "WMS"),
    ("warehouse.inventory_transaction.read", "读取库存流水", "WMS"),
    ("procurement.receipt.read", "读取采购收货", "SCM"),
    ("quality.purchase_inspection.read", "读取采购来料检验", "QMS"),
    ("navigation.supplier_procurement.read", "读取供应商采购完成模块菜单", "SYSTEM"),
    ("finance.payable_check.read", "读取采购应付核对", "FIN"),
)


def register_read_permissions(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    for code, name, module in READ_PERMISSIONS:
        Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "module": module},
        )


def unregister_read_permissions(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    Permission.objects.filter(code__in=[row[0] for row in READ_PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [("procurement", "0027_inventory_dimensions_a15")]
    operations = [
        migrations.RunPython(register_read_permissions, unregister_read_permissions),
    ]
