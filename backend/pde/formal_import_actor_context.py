"""Formal human-like actor context for Wave 1 import commits.

This module does not introduce a second authorization system.  It composes the
existing User/Employee/Position/Responsibility models with AuthorizationService
and provides an isolated rehearsal bootstrap for manual acceptance.
"""

from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
import uuid

from django.db import transaction
from pce_backend.identity_context import database_identity

from pfm.models import Employee
from system.authorization import AuthorizationService
from system.models import (
    Department,
    OrganizationOperatingAuditRecord,
    Permission,
    Position,
    PositionResponsibility,
    Responsibility,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)


ACTOR_CONTEXT_VERSION = "WAVE1-FORMAL-IMPORT-ACTOR-CONTEXT-V1.0"
WAVE1_IMPORT_PERMISSIONS = (
    "production.master_data.view",
    "masterdata.customer.maintain",
    "masterdata.supplier.maintain",
    "production.master_data.material.maintain",
    "production.master_data.product.maintain",
    "production.master_data.resource.maintain",
    "production.master_data.capacity.maintain",
)


class FormalImportActorContextError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def preview_actor_binding(*, user, organization_id):
    """Return the stable, non-authorizing identity bound into a preview."""
    database = database_identity()
    user_id = getattr(user, "pk", getattr(user, "id", None))
    username = getattr(user, "username", None) or f"test-or-diagnostic-user:{user_id or 'unresolved'}"
    return {
        "userId": user_id,
        "username": username,
        "stableIdentity": f"system.User:{username}",
        "organizationId": int(organization_id or 0),
        "databaseAlias": database["databaseAlias"],
        "databaseContext": database["databaseContext"],
        "authContextVersion": database["version"],
    }


def _effective_on(row, today):
    return not (
        (row.effective_from and row.effective_from > today)
        or (row.effective_to and row.effective_to < today)
    )


def resolve_formal_import_actor(*, user, organization_id, action_code):
    """Resolve every formal identity layer or fail closed with a precise code."""
    if not user or not getattr(user, "is_authenticated", False) or not user.is_active:
        raise FormalImportActorContextError(
            "FORMAL_IMPORT_ACTOR_USER_INVALID", "正式导入账户不存在或未启用。"
        )
    organization_id = int(organization_id or 0)
    if not organization_id or int(user.company_id) != organization_id:
        raise FormalImportActorContextError(
            "FORMAL_IMPORT_ACTOR_ORGANIZATION_MISMATCH",
            "正式导入账户与目标企业范围不一致。",
        )
    from system.models import Company
    if not Company.objects.filter(pk=organization_id, is_active=True).exists():
        raise FormalImportActorContextError(
            "FORMAL_IMPORT_ACTOR_ORGANIZATION_INACTIVE",
            "目标公司已退出有效经营范围，正式导入已拒绝。",
        )

    decision = AuthorizationService.decide(
        user=user,
        action_code=action_code,
        organization_id=organization_id,
        business_object={"organizationId": organization_id},
        context={"actionType": "FORMAL_IMPORT_COMMIT", "businessWrite": True},
    )
    if not decision.get("allowed"):
        suffix = "SCOPE_DENIED" if decision.get("decisionCode") == "SCOPE_DENIED" else "PERMISSION_DENIED"
        raise FormalImportActorContextError(
            f"FORMAL_IMPORT_ACTOR_{suffix}", decision.get("reason", "正式导入权限校验失败。"),
            {"authorization": decision},
        )

    employee = Employee.objects.select_related(
        "department_ref", "department_ref__company", "position_ref",
        "position_ref__department", "position_ref__default_role",
    ).filter(user=user).first()
    if not employee:
        raise FormalImportActorContextError(
            "FORMAL_IMPORT_ACTOR_EMPLOYEE_REQUIRED", "正式导入账户必须关联员工。"
        )
    if employee.status != "active":
        raise FormalImportActorContextError(
            "FORMAL_IMPORT_ACTOR_EMPLOYEE_INACTIVE", "正式导入员工必须处于在职状态。"
        )
    if not employee.position_ref_id:
        raise FormalImportActorContextError(
            "FORMAL_IMPORT_ACTOR_POSITION_REQUIRED", "正式导入员工必须关联岗位。"
        )
    position = employee.position_ref
    if not position.is_active:
        raise FormalImportActorContextError(
            "FORMAL_IMPORT_ACTOR_POSITION_DISABLED", "正式导入岗位必须启用。"
        )
    today = date.today()
    if not _effective_on(position, today):
        raise FormalImportActorContextError(
            "FORMAL_IMPORT_ACTOR_POSITION_OUT_OF_TERM", "正式导入岗位不在有效期内。"
        )
    if (
        position.company_id != organization_id
        or not employee.department_ref_id
        or employee.department_ref.company_id != organization_id
        or (position.department_id and position.department_id != employee.department_ref_id)
    ):
        raise FormalImportActorContextError(
            "FORMAL_IMPORT_ACTOR_ORGANIZATION_MISMATCH",
            "员工、岗位、部门与目标企业范围不一致。",
        )

    mappings = list(
        PositionResponsibility.objects.select_related("responsibility")
        .filter(position=position, active=True)
        .order_by("pk")
    )
    active_mappings = [
        mapping for mapping in mappings
        if mapping.responsibility.is_active
        and mapping.responsibility.status == Responsibility.Status.ACTIVE
        and _effective_on(mapping.responsibility, today)
    ]
    if not active_mappings:
        code = (
            "FORMAL_IMPORT_ACTOR_RESPONSIBILITY_EXPIRED"
            if mappings else "FORMAL_IMPORT_ACTOR_RESPONSIBILITY_REQUIRED"
        )
        raise FormalImportActorContextError(
            code, "正式导入岗位必须关联当前有效的职责。"
        )
    mapping = sorted(
        active_mappings,
        key=lambda item: (
            item.responsibility.code != "ENTERPRISE_MASTER_DATA_MAINTAINER",
            item.pk,
        ),
    )[0]

    assignments = list(
        UserRoleScopeAssignment.objects.select_related("role")
        .filter(user=user, organization_id=organization_id, active=True)
    )
    assignment = next(
        (row for row in assignments if action_code in set(
            RolePermission.objects.filter(role=row.role).values_list("permission__code", flat=True)
        )),
        None,
    )
    if not assignment:
        raise FormalImportActorContextError(
            "FORMAL_IMPORT_ACTOR_PERMISSION_DENIED", "正式导入账户缺少有效角色权限范围。"
        )
    if not position.default_role_id or position.default_role_id != assignment.role_id:
        raise FormalImportActorContextError(
            "FORMAL_IMPORT_ACTOR_ROLE_POSITION_MISMATCH",
            "正式导入岗位角色与账户授权角色不一致。",
        )

    return {
        "contractVersion": ACTOR_CONTEXT_VERSION,
        "userId": user.pk,
        "username": user.username,
        "employeeId": employee.pk,
        "employeeNo": employee.employee_no,
        "employmentStatus": employee.status,
        "positionId": position.pk,
        "positionCode": position.code,
        "positionEnabled": position.is_active,
        "responsibilityId": mapping.responsibility_id,
        "responsibilityCode": mapping.responsibility.code,
        "responsibilityEffectiveFrom": (
            mapping.responsibility.effective_from.isoformat()
            if mapping.responsibility.effective_from else None
        ),
        "responsibilityEffectiveTo": (
            mapping.responsibility.effective_to.isoformat()
            if mapping.responsibility.effective_to else None
        ),
        "roleId": assignment.role_id,
        "roleCode": assignment.role.code,
        "permissionCode": action_code,
        "organizationId": organization_id,
        "scopeCode": assignment.scope_code,
        "authorizationDecision": decision["decisionCode"],
    }


def _business_hash(payload):
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(content.encode("utf-8")).hexdigest()


@transaction.atomic
def bootstrap_rehearsal_actors(
    *, company, run_id, maintenance_username, maintenance_password,
    readonly_username, readonly_password, acceptance_label="A4", database_binding_id=None,
):
    """Create two isolated identities through the existing formal models."""
    marker = str(run_id).strip()
    database_binding_id = database_binding_id or str(uuid.uuid4())
    if not marker or not maintenance_password or not readonly_password:
        raise ValueError("run id and both temporary passwords are required")
    label = str(acceptance_label).strip().upper()
    code = f"W1AC-{label}-20260911"
    today = date.today()
    department, _ = Department.objects.get_or_create(
        company=company,
        name=f"Wave1 {label}隔离验收部门 [{marker}]",
        defaults={"code": code, "department_type": Department.DepartmentType.SUPPORT, "is_active": True},
    )
    role, _ = Role.objects.get_or_create(
        code=f"{code}-ROLE",
        defaults={"name": f"Wave1 {label}导入维护角色 [{marker}]", "description": f"REHEARSAL:{marker}"},
    )
    for permission_code in WAVE1_IMPORT_PERMISSIONS:
        permission, _ = Permission.objects.get_or_create(
            code=permission_code,
            defaults={"name": permission_code, "module": "PRODUCTION"},
        )
        RolePermission.objects.get_or_create(role=role, permission=permission)
    responsibility, _ = Responsibility.objects.get_or_create(
        code=f"{code}-RESP",
        defaults={
            "name": f"Wave1 {label}正式导入职责 [{marker}]",
            "description": f"REHEARSAL:{marker}; Wave1基础资料导入维护",
            "category": "ENTERPRISE_MASTER_DATA",
            "status": Responsibility.Status.ACTIVE,
            "is_active": True,
            "effective_from": today,
        },
    )
    position, _ = Position.objects.get_or_create(
        code=code,
        defaults={
            "name": f"Wave1 {label}隔离导入岗位 [{marker}]",
            "company": company,
            "department": department,
            "default_role": role,
            "description": f"REHEARSAL:{marker}",
            "effective_from": today,
            "is_active": True,
        },
    )
    PositionResponsibility.objects.get_or_create(
        position=position, responsibility=responsibility,
        defaults={"is_primary": True, "active": True},
    )
    maintenance, _ = User.objects.get_or_create(
        username=maintenance_username,
        defaults={
            "real_name": f"Wave1 {label}隔离导入维护员 [{marker}]",
            "company_id": company.pk,
            "is_active": True,
            "is_staff": False,
        },
    )
    maintenance.set_password(maintenance_password)
    maintenance.is_active = True
    maintenance.is_staff = False
    maintenance.is_superuser = False
    maintenance.company_id = company.pk
    maintenance.save()
    employee, _ = Employee.objects.get_or_create(
        employee_no=f"W1AC-{label}-E1",
        defaults={
            "user": maintenance,
            "full_name": maintenance.real_name,
            "hire_date": today,
            "status": "active",
            "department_ref": department,
            "position_ref": position,
            "department_name": department.name,
            "position": position.name,
        },
    )
    if employee.user_id != maintenance.pk:
        raise ValueError("rehearsal employee identity collision")
    scope_payload = {
        "runId": marker, "userId": maintenance.pk, "roleCode": role.code,
        "organizationId": company.pk, "scopeCode": UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
    }
    UserRoleScopeAssignment.objects.get_or_create(
        user=maintenance, role=role, organization=company,
        defaults={
            "scope_code": UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            "active": True, "version": 1, "business_hash": _business_hash(scope_payload),
        },
    )

    read_role, _ = Role.objects.get_or_create(
        code=f"{code}-READ",
        defaults={"name": f"Wave1 {label}只读角色 [{marker}]", "description": f"REHEARSAL:{marker}"},
    )
    view_permission = Permission.objects.get(code="production.master_data.view")
    RolePermission.objects.get_or_create(role=read_role, permission=view_permission)
    readonly, _ = User.objects.get_or_create(
        username=readonly_username,
        defaults={
            "real_name": f"Wave1 {label}隔离只读员 [{marker}]", "company_id": company.pk,
            "is_active": True, "is_staff": False,
        },
    )
    readonly.set_password(readonly_password)
    readonly.is_active = True
    readonly.is_staff = False
    readonly.is_superuser = False
    readonly.company_id = company.pk
    readonly.save()
    read_payload = {
        "runId": marker, "userId": readonly.pk, "roleCode": read_role.code,
        "organizationId": company.pk, "scopeCode": UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
    }
    UserRoleScopeAssignment.objects.get_or_create(
        user=readonly, role=read_role, organization=company,
        defaults={
            "scope_code": UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            "active": True, "version": 1, "business_hash": _business_hash(read_payload),
        },
    )
    OrganizationOperatingAuditRecord.objects.create(
        action_code="BOOTSTRAP_FORMAL_IMPORT_REHEARSAL_ACTOR",
        actor=maintenance,
        organization=company,
        target_type="FormalImportRehearsalActor",
        target_id=maintenance.pk,
        target_label=maintenance.username,
        reason=f"隔离人工验收执行主体初始化 [{marker}]",
        before_snapshot={},
        after_snapshot={
            "runId": marker, "rehearsalMarker": True,
            "databaseBindingId": database_binding_id,
            "acceptanceLabel": label,
            "databaseIdentity": database_identity(),
            "maintenanceUserId": maintenance.pk, "readonlyUserId": readonly.pk,
            "employeeId": employee.pk, "positionId": position.pk,
            "responsibilityId": responsibility.pk, "roleId": role.pk,
            "organizationId": company.pk,
        },
    )
    context = resolve_formal_import_actor(
        user=maintenance, organization_id=company.pk,
        action_code="masterdata.customer.maintain",
    )
    return {"maintenance": maintenance, "readonly": readonly, "context": context}
