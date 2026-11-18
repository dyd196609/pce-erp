"""Governed, data-only permissions for the BOMVersion formal control chain.

Importing this module never mutates the database.  The explicit registration
function follows the existing PDE permission-catalog pattern and deliberately
creates no roles, role-permission bindings, user assignments, or scopes.
"""

from django.db import transaction

from system.models import Permission


BOM_VERSION_PERMISSION_CATALOG = {
    "review": {
        "code": "pde.bom_version.review",
        "name": "BOM版本正式评审",
        "module": "PDE",
    },
    "release": {
        "code": "pde.bom_version.release",
        "name": "BOM版本正式发布",
        "module": "PDE",
    },
}


@transaction.atomic
def ensure_bom_version_permission_catalog():
    """Register the two exact BOMVersion actions without granting authority."""

    created_permissions = []
    existing_permissions = []
    for config in BOM_VERSION_PERMISSION_CATALOG.values():
        permission, created = Permission.objects.get_or_create(
            code=config["code"],
            defaults={"name": config["name"], "module": config["module"]},
        )
        if not created and (
            permission.name != config["name"]
            or permission.module != config["module"]
        ):
            raise ValueError(
                f"权限编码{config['code']}已存在但名称或模块不一致，停止登记。"
            )
        (created_permissions if created else existing_permissions).append(config["code"])
    return {
        "createdPermissions": sorted(created_permissions),
        "existingPermissions": sorted(existing_permissions),
        "rolePermissionWrites": 0,
        "userAuthorityWrites": 0,
        "scopeWrites": 0,
    }


__all__ = [
    "BOM_VERSION_PERMISSION_CATALOG",
    "ensure_bom_version_permission_catalog",
]
