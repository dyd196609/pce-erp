"""Governed permission catalog for the two order-related review modules.

The catalog is deliberately data-only.  Importing this module never writes the
database; callers must explicitly invoke ``ensure_review_permission_catalog``
inside an authorized transaction.
"""

from hashlib import sha256
import json

from django.db import transaction

from system.models import (
    OrganizationOperatingAuditRecord, Permission, Role, RolePermission,
    UserRoleScopeAssignment,
)


REVIEW_PERMISSION_CATALOG = {
    "CRM_ORDER_REVIEW": {
        "moduleCode": "CRM_ORDER_REVIEW",
        "moduleName": "订单评审",
        "legacyViewAction": "sales.order.view",
        "legacyManageAction": "sales.order.update",
        "role": {
            "code": "crm_order_review_participant",
            "name": "订单评审参与人",
            "description": "仅在同时存在有效评审对象授权和本人责任项目时办理订单评审。",
        },
        "approvalRole": {
            "code": "crm_order_review_final_approver",
            "name": "订单评审最终审批人",
            "description": "仅用于对已提交订单评审版本作出最终通过或不通过决定；不包含评审参与、代签或提交资格。",
        },
        "actions": {
            "view": ("sales.order_review.view", "订单评审 - 查看"),
            "manageDraft": ("sales.order_review.manage_draft", "订单评审 - 维护完整草稿"),
            "maintainOwnOpinion": ("sales.order_review.maintain_own_opinion", "订单评审 - 维护本人意见"),
            "signOwnItems": ("sales.order_review.sign_own_items", "订单评审 - 签认本人项目"),
            "submit": ("sales.order_review.submit", "订单评审 - 正式提交"),
            "finalApprove": ("sales.order_review.final_approve", "订单评审 - 最终审批"),
        },
    },
    "PDE_PRODUCTION_FEASIBILITY": {
        "moduleCode": "PDE_PRODUCTION_FEASIBILITY_REVIEW",
        "moduleName": "生产可行性评审",
        "legacyViewAction": "production.master_data.view",
        "legacyManageAction": "production.engineering.readiness.maintain",
        "role": {
            "code": "pde_production_feasibility_review_participant",
            "name": "生产可行性评审参与人",
            "description": "仅在同时存在有效评审对象授权和本人责任项目时办理生产可行性评审。",
        },
        "actions": {
            "view": ("pde.production_feasibility_review.view", "生产可行性评审 - 查看"),
            "manageDraft": ("pde.production_feasibility_review.manage_draft", "生产可行性评审 - 维护完整草稿"),
            "maintainOwnOpinion": ("pde.production_feasibility_review.maintain_own_opinion", "生产可行性评审 - 维护本人意见"),
            "signOwnItems": ("pde.production_feasibility_review.sign_own_items", "生产可行性评审 - 签认本人项目"),
            "submit": ("pde.production_feasibility_review.submit", "生产可行性评审 - 正式提交"),
            "finalApprove": ("pde.production_feasibility_review.final_approve", "生产可行性评审—最终审批"),
        },
        "itemPermissions": {
            "01": ("pde.production_feasibility_review.item.01", "生产可行性评审—技术需求评审"),
            "02": ("pde.production_feasibility_review.item.02", "生产可行性评审—产品结构评审"),
            "03": ("pde.production_feasibility_review.item.03", "生产可行性评审—工艺方案评审"),
            "04": ("pde.production_feasibility_review.item.04", "生产可行性评审—用料要求评审"),
            "05": ("pde.production_feasibility_review.item.05", "生产可行性评审—物料准备评审"),
            "06": ("pde.production_feasibility_review.item.06", "生产可行性评审—人员条件评审"),
            "07": ("pde.production_feasibility_review.item.07", "生产可行性评审—设备条件评审"),
            "08": ("pde.production_feasibility_review.item.08", "生产可行性评审—实现周期评审"),
            "09": ("pde.production_feasibility_review.item.09", "生产可行性评审—质量验证评审"),
        },
    },
}


def review_permission_config(review_type):
    return REVIEW_PERMISSION_CATALOG.get(str(review_type or ""))


def review_item_permission(review_type, item_code):
    """Resolve a fixed template item by its stable formal item code."""
    config = review_permission_config(review_type) or {}
    return (config.get("itemPermissions") or {}).get(str(item_code or ""))


@transaction.atomic
def ensure_review_permission_catalog(*, create_participant_roles=True):
    """Idempotently register permissions and empty participant roles.

    Participant roles receive only view/own-opinion/own-sign permissions.  The
    runtime still requires a matching ``OrderReviewParticipantGrant``; this
    function never assigns a role to a user and never grants submit authority.
    """

    created_permissions = []
    updated_permissions = []
    roles = []
    approval_roles = []
    for config in REVIEW_PERMISSION_CATALOG.values():
        item_permissions = config.get("itemPermissions") or {}
        if item_permissions:
            from .models import OrderReviewTemplate
            template = OrderReviewTemplate.objects.prefetch_related("items").filter(
                review_type="PDE_PRODUCTION_FEASIBILITY", is_active=True,
            ).order_by("-effective_from", "-id").first()
            if not template:
                raise ValueError("生产可行性评审正式模板不存在，停止登记事项权限。")
            template_codes = set(template.items.filter(is_applicable=True).values_list("item_code", flat=True))
            if template_codes != set(item_permissions):
                raise ValueError("PDE事项权限稳定编码与当前正式模板不一致，停止登记。")
        permission_rows = {}
        for action_key, (code, name) in config["actions"].items():
            permission, created = Permission.objects.update_or_create(
                code=code,
                defaults={"name": name, "module": config["moduleCode"]},
            )
            permission_rows[action_key] = permission
            (created_permissions if created else updated_permissions).append(code)
        for item_code, (code, name) in (config.get("itemPermissions") or {}).items():
            permission, created = Permission.objects.update_or_create(
                code=code,
                defaults={"name": name, "module": config["moduleCode"]},
            )
            (created_permissions if created else updated_permissions).append(code)
        if not create_participant_roles:
            continue
        role_config = config["role"]
        role, role_created = Role.objects.update_or_create(
            code=role_config["code"],
            defaults={"name": role_config["name"], "description": role_config["description"]},
        )
        bound = []
        for action_key in ("view", "maintainOwnOpinion", "signOwnItems"):
            _, created = RolePermission.objects.get_or_create(
                role=role, permission=permission_rows[action_key],
            )
            if created:
                bound.append(permission_rows[action_key].code)
        roles.append({"code": role.code, "created": role_created, "boundPermissions": bound})
        approval_role_config = config.get("approvalRole")
        if approval_role_config:
            approval_role, approval_role_created = Role.objects.update_or_create(
                code=approval_role_config["code"],
                defaults={
                    "name": approval_role_config["name"],
                    "description": approval_role_config["description"],
                },
            )
            approval_bound = []
            _, created = RolePermission.objects.get_or_create(
                role=approval_role,
                permission=permission_rows["finalApprove"],
            )
            if created:
                approval_bound.append(permission_rows["finalApprove"].code)
            approval_roles.append({
                "code": approval_role.code,
                "created": approval_role_created,
                "boundPermissions": approval_bound,
                "userAssignments": 0,
            })
    return {
        "createdPermissions": sorted(created_permissions),
        "updatedPermissions": sorted(updated_permissions),
        "roles": roles,
        "approvalRoles": approval_roles,
        "userAuthorityWrites": 0,
        "submitPermissionAssignments": 0,
    }


def _business_hash(payload):
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


@transaction.atomic
def converge_active_review_participant_roles(*, actor, reason):
    """Add/reactivate the governed participant role for existing active grants.

    Existing user roles are preserved.  The function does not change passwords,
    participant grants, review records, review items, signatures, or submit
    permissions.
    """
    from .models import OrderReviewParticipantGrant

    catalog_result = ensure_review_permission_catalog()
    created = []
    reactivated = []
    unchanged = []
    grants = OrderReviewParticipantGrant.objects.select_related(
        "review", "user", "company", "employee",
    ).filter(active=True).order_by("review__review_type", "review_id", "user_id")
    for grant in grants:
        config = review_permission_config(grant.review.review_type)
        if not config:
            continue
        role = Role.objects.get(code=config["role"]["code"])
        assignment, was_created = UserRoleScopeAssignment.objects.get_or_create(
            user=grant.user, role=role, organization=grant.company,
            defaults={
                "scope_code": UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
                "active": True,
                "version": 1,
                "business_hash": _business_hash({
                    "userId": grant.user_id, "roleCode": role.code,
                    "organizationId": grant.company_id, "scopeCode": "ORGANIZATION",
                    "sourceGrantId": grant.pk, "version": 1,
                }),
            },
        )
        before = {
            "active": assignment.active,
            "scopeCode": assignment.scope_code,
            "version": assignment.version,
        }
        change = "unchanged"
        if was_created:
            change = "created"
            created.append(assignment.pk)
        elif not assignment.active:
            assignment.active = True
            assignment.scope_code = UserRoleScopeAssignment.ScopeCode.ORGANIZATION
            assignment.department = None
            assignment.version += 1
            assignment.business_hash = _business_hash({
                "assignmentId": assignment.pk, "sourceGrantId": grant.pk,
                "active": True, "scopeCode": "ORGANIZATION", "version": assignment.version,
            })
            assignment.save(update_fields=[
                "active", "scope_code", "department", "version", "business_hash", "updated_at",
            ])
            change = "reactivated"
            reactivated.append(assignment.pk)
        else:
            unchanged.append(assignment.pk)
        if change != "unchanged":
            OrganizationOperatingAuditRecord.objects.create(
                action_code="CONVERGE_REVIEW_PARTICIPANT_ROLE",
                actor=actor,
                organization=grant.company,
                target_type="UserRoleScopeAssignment",
                target_id=assignment.pk,
                target_label=f"{grant.user.username} / {role.code}",
                reason=reason,
                before_snapshot={} if was_created else before,
                after_snapshot={
                    "active": assignment.active,
                    "scopeCode": assignment.scope_code,
                    "version": assignment.version,
                    "sourceGrantId": grant.pk,
                    "reviewType": grant.review.review_type,
                },
            )
    return {
        "catalog": catalog_result,
        "activeGrantCount": grants.count(),
        "createdAssignmentIds": created,
        "reactivatedAssignmentIds": reactivated,
        "unchangedAssignmentIds": unchanged,
        "passwordWrites": 0,
        "reviewBusinessWrites": 0,
        "submitPermissionAssignments": 0,
    }
