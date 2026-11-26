"""Read-only baseline for the account/PDE item-permission closeout task."""

import json
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")

import django

django.setup()

from django.conf import settings
from pfm.models import Employee
from pde.models import OrderCrossFunctionalReview, OrderReviewTemplate
from system.models import (
    Company,
    Permission,
    PositionWorkflowResponsibility,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)
from workflow_runtime.models import (
    ApprovalDecision,
    ApprovalTask,
    UserOrganizationRoleAuthority,
    WorkflowInstance,
)


employee = Employee.objects.select_related(
    "user", "department_ref", "position_ref"
).filter(employee_no="EMP-COMP001-0001").first()
role = Role.objects.filter(code="ROLE-COMP001-0001").first()

payload = {
    "database": str(settings.DATABASES["default"]["NAME"]),
    "company": list(Company.objects.filter(pk=1).values("id", "code", "name", "is_active")),
    "employee": (
        {
            "id": employee.pk,
            "employeeNo": employee.employee_no,
            "name": employee.full_name,
            "status": employee.status,
            "department": getattr(employee.department_ref, "name", None),
            "departmentCode": getattr(employee.department_ref, "code", None),
            "position": getattr(employee.position_ref, "name", None),
            "positionCode": getattr(employee.position_ref, "code", None),
            "userId": employee.user_id,
            "username": employee.user.username if employee.user_id else None,
            "credentialUsable": employee.user.has_usable_password() if employee.user_id else None,
        }
        if employee
        else None
    ),
    "role": (
        {
            "id": role.pk,
            "code": role.code,
            "name": role.name,
            "description": role.description,
            "permissions": list(
                RolePermission.objects.filter(role=role)
                .values_list("permission__code", flat=True)
                .order_by("permission__code")
            ),
        }
        if role
        else None
    ),
    "pdePermissions": list(
        Permission.objects.filter(code__startswith="pde.production_feasibility_review.")
        .values("id", "code", "name", "module")
        .order_by("code")
    ),
    "pdeTemplates": [
        {
            "id": template.pk,
            "version": template.version,
            "title": template.title,
            "active": template.is_active,
            "items": list(
                template.items.values(
                    "id", "item_code", "item_text", "display_order", "is_applicable"
                ).order_by("display_order", "id")
            ),
        }
        for template in OrderReviewTemplate.objects.filter(
            review_type="PDE_PRODUCTION_FEASIBILITY"
        ).order_by("id")
    ],
    "approvalRole": list(
        Role.objects.filter(code="crm_order_review_final_approver").values("id", "code", "name")
    ),
    "approvalAssignments": list(
        UserRoleScopeAssignment.objects.filter(role__code="crm_order_review_final_approver")
        .values(
            "id", "user_id", "user__username", "organization_id", "scope_code", "active", "version"
        )
        .order_by("id")
    ),
    "legacyApprovalAuthorities": list(
        UserOrganizationRoleAuthority.objects.filter(role_code="crm_order_review_final_approver")
        .values(
            "id", "user_id", "user__username", "legal_entity_id", "department_id", "active", "version"
        )
        .order_by("id")
    ),
    "positionResponsibilities": list(
        PositionWorkflowResponsibility.objects.filter(position__name__contains="计划物控")
        .values(
            "id", "position_id", "position__code", "position__name", "workflow_code",
            "node_code", "ownership_type", "active"
        )
        .order_by("id")
    ),
    "crmReviews": list(
        OrderCrossFunctionalReview.objects.filter(review_type="CRM_ORDER_REVIEW")
        .values(
            "id", "review_version", "record_status", "source_order_no", "source_version",
            "reviewer_id", "submitted_at", "conclusion"
        )
        .order_by("id")
    ),
    "approvalInstances": list(
        WorkflowInstance.objects.filter(document_type="CRMOrderReview")
        .values("id", "document_id", "instance_no", "status", "current_step", "total_steps")
        .order_by("id")
    ),
    "approvalTasks": list(
        ApprovalTask.objects.filter(workflow_instance__document_type="CRMOrderReview")
        .values("id", "workflow_instance_id", "task_no", "required_role_code", "status")
        .order_by("id")
    ),
    "approvalDecisionCount": ApprovalDecision.objects.filter(
        task__workflow_instance__document_type="CRMOrderReview"
    ).count(),
    "counts": {
        "users": User.objects.count(),
        "roles": Role.objects.count(),
        "permissions": Permission.objects.count(),
        "assignments": UserRoleScopeAssignment.objects.count(),
        "pdeReviews": OrderCrossFunctionalReview.objects.filter(
            review_type="PDE_PRODUCTION_FEASIBILITY"
        ).count(),
    },
}

print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
