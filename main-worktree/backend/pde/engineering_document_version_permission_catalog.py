"""System catalog for the dedicated EngineeringDocumentVersion review action."""

from django.db import transaction

from system.models import Permission

from .engineering_document_version_workflow_catalog import (
    ensure_engineering_document_version_workflow_catalog,
)


ENGINEERING_DOCUMENT_VERSION_REVIEW_PERMISSION = {
    "code": "pde.engineering_document_version.review",
    "name": "工程资料版本正式评审",
    "module": "PDE",
}


@transaction.atomic
def ensure_engineering_document_version_permission_catalog():
    config = ENGINEERING_DOCUMENT_VERSION_REVIEW_PERMISSION
    permission, created = Permission.objects.get_or_create(
        code=config["code"],
        defaults={"name": config["name"], "module": config["module"]},
    )
    if not created and (permission.name != config["name"] or permission.module != config["module"]):
        raise ValueError(f"权限编码{config['code']}已存在但名称或模块不一致，停止登记。")
    workflow_template = ensure_engineering_document_version_workflow_catalog()
    return {
        "createdPermissions": [config["code"]] if created else [],
        "existingPermissions": [] if created else [config["code"]],
        "workflowTemplate": workflow_template,
        "rolePermissionWrites": 0,
        "workflowResponsibilityWrites": 0,
        "userAuthorityWrites": 0,
        "scopeWrites": 0,
    }


__all__ = [
    "ENGINEERING_DOCUMENT_VERSION_REVIEW_PERMISSION",
    "ensure_engineering_document_version_permission_catalog",
]
