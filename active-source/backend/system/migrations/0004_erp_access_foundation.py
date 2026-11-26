import django.db.models.deletion
from django.db import migrations, models


PERMISSIONS = (
    ("procurement.purchase_request.view", "采购申请查看", "SCM"),
    ("procurement.purchase_request.create", "采购申请新建", "SCM"),
    ("purchase_request.submit", "采购申请提交", "SCM"),
    ("purchase_request.approve", "采购申请审批", "SCM"),
    ("procurement.direct_purchase_order.view", "直接采购查看", "SCM"),
    ("procurement.direct_purchase_order.create", "直接采购创建", "SCM"),
    ("masterdata.supplier_material_price.view", "供应商物料价格查看", "MASTERDATA"),
    ("masterdata.supplier_material_price.manual_maintain", "人工维护供应商物料价格", "MASTERDATA"),
    ("procurement.agreed_price.confirm", "既定价格确认", "SCM"),
    ("procurement.purchase_order.view", "采购订单查看", "SCM"),
    ("procurement.purchase_order.create", "采购订单创建", "SCM"),
    ("procurement.receipt.receive", "采购收货", "SCM"),
    ("quality.purchase.inspect", "采购检验", "QMS"),
    ("warehouse.purchase.putaway", "采购入库", "WMS"),
)

BUYER_CODES = {
    "procurement.purchase_request.view",
    "procurement.purchase_request.create",
    "purchase_request.submit",
    "masterdata.supplier_material_price.view",
    "procurement.agreed_price.confirm",
    "procurement.purchase_order.view",
}

DIRECT_CODES = BUYER_CODES | {
    "procurement.direct_purchase_order.view",
    "procurement.direct_purchase_order.create",
    "masterdata.supplier_material_price.manual_maintain",
    "procurement.purchase_order.create",
}


def seed_access_foundation(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    Role = apps.get_model("system", "Role")
    RolePermission = apps.get_model("system", "RolePermission")

    permissions = {}
    for code, name, module in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code, defaults={"name": name, "module": module},
        )
        permissions[code] = permission

    superadmin, _ = Role.objects.update_or_create(
        code="superadmin",
        defaults={"name": "系统管理员", "description": "系统最高管理角色"},
    )
    buyer, _ = Role.objects.update_or_create(
        code="buyer",
        defaults={"name": "普通采购员", "description": "采购申请和普通采购操作，不含直接采购及人工价格维护"},
    )
    direct, _ = Role.objects.update_or_create(
        code="direct_purchase_authorized",
        defaults={"name": "直接采购授权人员", "description": "直接采购及人工维护供应商物料价格"},
    )

    for role, codes in (
        (superadmin, set(permissions)),
        (buyer, BUYER_CODES),
        (direct, DIRECT_CODES),
    ):
        for code in sorted(codes):
            RolePermission.objects.get_or_create(role=role, permission=permissions[code])

    duplicates = RolePermission.objects.values("role_id", "permission_id").annotate(
        row_count=models.Count("id")
    ).filter(row_count__gt=1)
    for duplicate in duplicates:
        rows = RolePermission.objects.filter(
            role_id=duplicate["role_id"], permission_id=duplicate["permission_id"]
        ).order_by("pk")
        rows.exclude(pk=rows.first().pk).delete()


class Migration(migrations.Migration):
    dependencies = [("system", "0003_menu_rolemenu")]

    operations = [
        migrations.RunPython(seed_access_foundation, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="rolepermission",
            constraint=models.UniqueConstraint(
                fields=("role", "permission"),
                name="uniq_system_role_permission",
            ),
        ),
    ]
