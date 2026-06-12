from system.models import Role, Permission, RolePermission, User

roles = [
    {"name": "超级管理员", "code": "superadmin", "description": "拥有系统全部权限"},
    {
        "name": "采购经理",
        "code": "purchase_manager",
        "description": "负责采购审批与管理",
    },
    {"name": "采购员", "code": "buyer", "description": "负责采购订单业务"},
    {"name": "仓库管理员", "code": "warehouse", "description": "负责库存与仓库业务"},
    {"name": "普通员工", "code": "employee", "description": "普通业务用户"},
]


permissions = [
    {"code": "dashboard_view", "name": "查看仪表盘", "module": "dashboard"},
    {"code": "material_view", "name": "查看物料", "module": "masterdata"},
    {"code": "material_create", "name": "新增物料", "module": "masterdata"},
    {"code": "material_edit", "name": "编辑物料", "module": "masterdata"},
    {"code": "material_delete", "name": "删除物料", "module": "masterdata"},
    {"code": "supplier_view", "name": "查看供应商", "module": "masterdata"},
    {"code": "supplier_create", "name": "新增供应商", "module": "masterdata"},
    {"code": "supplier_edit", "name": "编辑供应商", "module": "masterdata"},
    {"code": "supplier_delete", "name": "删除供应商", "module": "masterdata"},
    {"code": "employee_view", "name": "查看员工", "module": "hr"},
    {"code": "employee_create", "name": "新增员工", "module": "hr"},
    {"code": "employee_edit", "name": "编辑员工", "module": "hr"},
    {"code": "employee_delete", "name": "删除员工", "module": "hr"},
    {"code": "purchase_order_view", "name": "查看采购订单", "module": "purchase"},
    {"code": "purchase_order_create", "name": "新增采购订单", "module": "purchase"},
    {"code": "purchase_order_edit", "name": "编辑采购订单", "module": "purchase"},
    {"code": "purchase_order_delete", "name": "删除采购订单", "module": "purchase"},
    {"code": "purchase_order_approve", "name": "审批采购订单", "module": "purchase"},
    {"code": "purchase_order_export", "name": "导出采购订单", "module": "purchase"},
    {"code": "system_view", "name": "查看系统管理", "module": "system"},
    {"code": "system_user_view", "name": "查看用户", "module": "system"},
    {"code": "system_role_view", "name": "查看角色", "module": "system"},
    {"code": "system_permission_view", "name": "查看权限", "module": "system"},
    {"code": "system_menu_view", "name": "查看菜单", "module": "system"},
]


for item in roles:
    Role.objects.update_or_create(
        code=item["code"],
        defaults={
            "name": item["name"],
            "description": item["description"],
        },
    )


for item in permissions:
    Permission.objects.update_or_create(
        code=item["code"],
        defaults={
            "name": item["name"],
            "module": item["module"],
        },
    )


super_role = Role.objects.get(code="superadmin")

for permission in Permission.objects.all():
    RolePermission.objects.get_or_create(
        role=super_role,
        permission=permission,
    )


admin_user, created = User.objects.get_or_create(
    username="admin",
    defaults={
        "real_name": "超级管理员",
        "company_id": 1,
        "role": super_role,
        "is_staff": True,
        "is_superuser": True,
        "is_active": True,
    },
)

if created:
    admin_user.set_password("admin123")
    admin_user.save()
    print("超级管理员用户创建成功：用户名 admin，密码 admin123")
else:
    admin_user.role = super_role
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.is_active = True
    admin_user.save()
    print("超级管理员用户已存在，已绑定 superadmin 角色")

print("权限初始化完成")
print("角色数量：", Role.objects.count())
print("权限数量：", Permission.objects.count())
print("角色权限数量：", RolePermission.objects.count())
