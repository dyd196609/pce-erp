"""System catalog for RoutingVersion formal review and release actions.

Importing this module is read-only.  The explicit registration function creates
the permission and fixed Workflow template; it never grants a role, account or
scope and never creates review instances or decisions.
"""

from django.db import transaction

from system.models import Permission

from .routing_version_workflow_catalog import ensure_routing_version_workflow_catalog


ROUTING_VERSION_PERMISSION_CATALOG = {
    "review": {
        "code": "pde.routing_version.review",
        "name": "工艺路线版本正式评审",
        "module": "PDE",
    },
    "release": {
        "code": "pde.routing_version.release",
        "name": "工艺路线版本正式发布",
        "module": "PDE",
    },
}


@transaction.atomic
def ensure_routing_version_permission_catalog():
    created_permissions = []
    existing_permissions = []
    for config in ROUTING_VERSION_PERMISSION_CATALOG.values():
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
    workflow_template = ensure_routing_version_workflow_catalog()
    return {
        "createdPermissions": sorted(created_permissions),
        "existingPermissions": sorted(existing_permissions),
        "workflowTemplate": workflow_template,
        "rolePermissionWrites": 0,
        "userAuthorityWrites": 0,
        "scopeWrites": 0,
    }


__all__ = [
    "ROUTING_VERSION_PERMISSION_CATALOG",
    "ensure_routing_version_permission_catalog",
]
