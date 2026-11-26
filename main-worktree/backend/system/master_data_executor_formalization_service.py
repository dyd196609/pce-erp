"""Formalize the manually approved EMP047 master-data executor chain only."""

from hashlib import sha256
import json
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from pfm.models import Employee

from .authorization import AuthorizationService
from .models import (
    OrganizationOperatingAuditRecord,
    Permission,
    PositionResponsibility,
    Responsibility,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)


VERSION = "MASTER-DATA-EXECUTOR-FORMALIZATION-V1.0"
EMPLOYEE_NO = "EMP047"
USERNAME = "emd_emp047"
RESPONSIBILITY_CODE = "ENTERPRISE_MASTER_DATA_MAINTAINER"
ROLE_CODE = "enterprise_master_data_maintainer"

ALLOWED_PERMISSIONS = {
    "masterdata.validated_fact.formalize": ("正式化人工已验收基础资料", "MASTER_DATA"),
    "masterdata.customer.maintain": ("维护客户与经销商基础资料", "MASTER_DATA"),
    "masterdata.supplier.maintain": ("维护供应商基础资料", "MASTER_DATA"),
    "production.master_data.view": ("查看生产主数据", "PRODUCTION"),
    "production.master_data.unit.maintain": ("维护计量单位映射", "PRODUCTION"),
    "production.master_data.product.maintain": ("维护已授权产品分类", "PRODUCTION"),
    "production.master_data.material.maintain": ("定向维护已验收物料的计量单位与来源映射", "PRODUCTION"),
    "production.master_data.routing.maintain": ("正式化并维护已验收工艺路线", "PRODUCTION"),
}

DENIED_ACTIONS = (
    "masterdata.delete",
    "production.planning.release",
    "purchase.approval",
    "production.order.release",
    "finance.approval",
    "system.organization.admin",
    "system.user.admin",
    "system.role.admin",
)

PRE_GROUP3B_RESPONSIBILITY_DESCRIPTION = (
    "当前全屋定制/整木基础数据建立阶段的最小维护职责。"
    "允许 view/create/update/activate-deactivate/source mapping/readback；"
    "对象仅限客户/经销商、供应商、UOM Mapping、Product Category，以及人工验收后"
    "Material 的查看、定向UOM更新、来源映射与回读；不含物料删除、批量新增、重命名、"
    "MAKE/BUY或Material Type任意修改。Product、BOM、Routing、WorkCenter、Capacity、Working Time、Staffing"
    "及其它制造基础资料须另行人工确认授权。"
    "不含 delete、计划发布、采购审批、生产任务下达、财务审批、组织管理、用户管理或角色管理。"
)

RESPONSIBILITY_DESCRIPTION = (
    "当前全屋定制/整木基础数据建立阶段的最小维护职责。"
    "允许 view/create/update/activate-deactivate/source mapping/readback；"
    "对象仅限客户/经销商、供应商、UOM Mapping、Product Category，以及人工验收后"
    "Material 的查看、定向UOM更新、来源映射与回读；不含物料删除、批量新增、重命名、"
    "MAKE/BUY或Material Type任意修改；允许已人工验收Routing、RoutingVersion、RoutingStep及工艺类型的"
    "create、update、source mapping、readback。Product、BOM、WorkCenter、Capacity、Working Time、Staffing"
    "及其它未验收制造基础资料须另行人工确认授权。"
    "不含 delete、计划发布、采购审批、生产任务下达、财务审批、组织管理、用户管理或角色管理。"
)


class ExecutorFormalizationError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _db_hash():
    path = Path(settings.DATABASES["default"]["NAME"])
    return sha256(path.read_bytes()).hexdigest().upper()


def _business_hash(payload):
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def _audit(*, actor, action_code, target, target_type, target_label, reason, before, after):
    return OrganizationOperatingAuditRecord.objects.create(
        action_code=action_code,
        actor=actor,
        organization_id=actor.company_id,
        target_type=target_type,
        target_id=target.pk,
        target_label=target_label,
        reason=reason,
        before_snapshot={**before, "formalizationVersion": VERSION},
        after_snapshot={**after, "formalizationVersion": VERSION},
    )


def _identity_snapshot(employee):
    account = employee.user
    position = employee.position_ref
    responsibility = Responsibility.objects.filter(code=RESPONSIBILITY_CODE).first()
    mapping = None
    if responsibility and position:
        mapping = PositionResponsibility.objects.filter(
            position=position, responsibility=responsibility,
        ).first()
    assignment = None
    if account:
        assignment = UserRoleScopeAssignment.objects.filter(
            user=account, role__code=ROLE_CODE, organization_id=account.company_id,
        ).select_related("role").first()
    return {
        "employee": {
            "id": employee.pk,
            "employeeNo": employee.employee_no,
            "name": employee.full_name,
            "active": employee.status == "active",
            "departmentId": employee.department_ref_id,
            "department": employee.department_ref.name if employee.department_ref else "",
        },
        "position": {
            "id": position.pk if position else None,
            "code": position.code if position else "",
            "name": position.name if position else "",
            "active": bool(position and position.is_active),
            "defaultRoleCode": position.default_role.code if position and position.default_role else "",
        },
        "account": {
            "id": account.pk if account else None,
            "username": account.username if account else "",
            "active": bool(account and account.is_active),
            "employeeExact": bool(account and account.employee_profile.pk == employee.pk),
            "credentialState": "PENDING_SECURE_INITIALIZATION" if account and not account.has_usable_password() else "USABLE",
        },
        "responsibility": {
            "id": responsibility.pk if responsibility else None,
            "code": responsibility.code if responsibility else "",
            "name": responsibility.name if responsibility else "",
            "status": responsibility.status if responsibility else "",
            "effective": bool(
                responsibility
                and responsibility.is_active
                and responsibility.status == Responsibility.Status.ACTIVE
                and mapping
                and mapping.active
            ),
            "positionMappingId": mapping.pk if mapping else None,
        },
        "authority": {
            "roleCode": assignment.role.code if assignment else "",
            "scopeCode": assignment.scope_code if assignment else "",
            "active": bool(assignment and assignment.active),
        },
    }


class MasterDataExecutorFormalizationService:
    """Single guarded and audited write chain for the user's explicit decision."""

    @classmethod
    def execute(cls, *, actor):
        if not actor or not actor.is_superuser or actor.username != "admin":
            raise ExecutorFormalizationError(
                "TECHNICAL_ADMIN_REQUIRED",
                "首次实名执行人链必须由当前技术管理员通过正式服务建立。",
            )
        before_hash = _db_hash()
        before_counts = cls._counts(actor.company_id)
        write_counts = {
            "businessUserCreated": 0,
            "employeeUserLinked": 0,
            "responsibilityCreated": 0,
            "responsibilityActivated": 0,
            "positionResponsibilityBound": 0,
            "authorizationRoleCreated": 0,
            "permissionCatalogCreated": 0,
            "rolePermissionBound": 0,
            "positionDefaultRoleBound": 0,
            "userRoleScopeBound": 0,
        }

        with transaction.atomic():
            employee = Employee.objects.select_for_update().select_related(
                "department_ref", "department_ref__company", "position_ref", "user"
            ).filter(employee_no=EMPLOYEE_NO).first()
            if not employee or employee.full_name != "诸葛强":
                raise ExecutorFormalizationError("EMPLOYEE_IDENTITY_DRIFT", "EMP047 实名身份不唯一或已漂移。")
            if employee.status != "active" or not employee.department_ref or not employee.position_ref:
                raise ExecutorFormalizationError("EMPLOYEE_CHAIN_INACTIVE", "EMP047 不在职或缺少正式部门/岗位。")
            if employee.department_ref.name != "生产部" or employee.department_ref.company_id != actor.company_id:
                raise ExecutorFormalizationError("DEPARTMENT_IDENTITY_DRIFT", "EMP047 正式部门与人工裁决不一致。")
            position = employee.position_ref
            if position.name != "生产总监" or not position.is_active or position.company_id != actor.company_id:
                raise ExecutorFormalizationError("POSITION_IDENTITY_DRIFT", "EMP047 当前有效岗位与人工裁决不一致。")
            if Employee.objects.filter(user=actor).exists():
                raise ExecutorFormalizationError("ADMIN_EMPLOYEE_LINK_FORBIDDEN", "admin 已意外绑定员工，停止正式化。")

            account = employee.user
            username_owner = User.objects.select_for_update().filter(username=USERNAME).first()
            if account and account.username != USERNAME:
                raise ExecutorFormalizationError("EMPLOYEE_USER_CONFLICT", "EMP047 已绑定其它业务账号。")
            if username_owner and (not account or username_owner.pk != account.pk):
                raise ExecutorFormalizationError("USERNAME_COLLISION", f"账号 {USERNAME} 已被其它身份占用。")
            if not account:
                account = User(
                    username=USERNAME,
                    real_name=employee.full_name,
                    company_id=actor.company_id,
                    is_active=True,
                    is_staff=False,
                )
                account.set_unusable_password()
                account.full_clean()
                account.save()
                write_counts["businessUserCreated"] = 1
                _audit(
                    actor=actor, action_code="CREATE_EMPLOYEE_BUSINESS_USER", target=account,
                    target_type="User", target_label=f"{account.username} - {account.real_name}",
                    reason="用户人工指定 EMP047 为基础资料正式执行人",
                    before={}, after={
                        "username": account.username, "realName": account.real_name,
                        "companyId": account.company_id, "active": account.is_active,
                        "credentialState": "PENDING_SECURE_INITIALIZATION",
                        "namingBasis": "emd + normalized employee number",
                    },
                )
                employee.user = account
                employee.full_clean()
                employee.save(update_fields=["user", "updated_at"])
                write_counts["employeeUserLinked"] = 1
                _audit(
                    actor=actor, action_code="SAVE_EMPLOYEE_ACCOUNT", target=employee,
                    target_type="EmployeeAccount", target_label=f"{employee.employee_no} {employee.full_name}",
                    reason="实名业务账号与 EMP047 一对一绑定",
                    before={"userId": None}, after={"userId": account.pk, "username": account.username},
                )
            elif not account.is_active or account.company_id != actor.company_id or account.real_name != employee.full_name:
                raise ExecutorFormalizationError("EMPLOYEE_USER_CONFLICT", "EMP047 已有账号状态或实名信息不符合裁决。")

            responsibility = Responsibility.objects.select_for_update().filter(code=RESPONSIBILITY_CODE).first()
            if responsibility and responsibility.name != "企业基础资料维护员":
                raise ExecutorFormalizationError("RESPONSIBILITY_CONFLICT", "职责编码已被其它职责占用。")
            today = timezone.now().date()
            if not responsibility:
                responsibility = Responsibility.objects.create(
                    code=RESPONSIBILITY_CODE,
                    name="企业基础资料维护员",
                    description=RESPONSIBILITY_DESCRIPTION,
                    category="ENTERPRISE_MASTER_DATA",
                    is_active=True,
                    status=Responsibility.Status.ACTIVE,
                    effective_from=today,
                )
                responsibility.full_clean()
                write_counts["responsibilityCreated"] = 1
                write_counts["responsibilityActivated"] = 1
                _audit(
                    actor=actor, action_code="SAVE_RESPONSIBILITY", target=responsibility,
                    target_type="Responsibility", target_label=f"{responsibility.code} {responsibility.name}",
                    reason="用户人工接受企业基础资料维护员最小职责",
                    before={}, after={
                        "code": responsibility.code, "name": responsibility.name,
                        "category": responsibility.category, "status": responsibility.status,
                        "effectiveFrom": responsibility.effective_from.isoformat(),
                        "allowedSemantics": ["view", "create", "update", "activate/deactivate", "source mapping", "readback"],
                        "allowedObjects": ["客户/经销商", "供应商", "UOM Mapping", "Product Category"],
                        "deniedObjects": list(DENIED_ACTIONS),
                    },
                )
            elif (
                responsibility.description != RESPONSIBILITY_DESCRIPTION
                or responsibility.category != "ENTERPRISE_MASTER_DATA"
                or responsibility.status != Responsibility.Status.ACTIVE
                or not responsibility.is_active
            ):
                raise ExecutorFormalizationError("RESPONSIBILITY_CONFLICT", "现有职责定义或状态与人工裁决不一致。")

            mapping, mapping_created = PositionResponsibility.objects.select_for_update().get_or_create(
                position=position,
                responsibility=responsibility,
                defaults={"is_primary": False, "active": True},
            )
            if not mapping_created and not mapping.active:
                raise ExecutorFormalizationError("RESPONSIBILITY_MAPPING_CONFLICT", "岗位职责映射存在但未启用。")
            if mapping_created:
                mapping.full_clean()
                write_counts["positionResponsibilityBound"] = 1
                _audit(
                    actor=actor, action_code="SAVE_POSITION_RESPONSIBILITY", target=mapping,
                    target_type="PositionResponsibility", target_label=f"{position.name} / {responsibility.name}",
                    reason="生产总监岗位承接本阶段最小基础资料维护职责",
                    before={}, after={
                        "positionId": position.pk, "responsibilityId": responsibility.pk,
                        "active": True, "isPrimary": False,
                    },
                )

            role, role_created = Role.objects.select_for_update().get_or_create(
                code=ROLE_CODE,
                defaults={
                    "name": "企业基础资料维护员",
                    "description": "ENTERPRISE_MASTER_DATA_MAINTAINER 的最小技术授权投影",
                },
            )
            if not role_created and role.name != "企业基础资料维护员":
                raise ExecutorFormalizationError("AUTHORIZATION_ROLE_CONFLICT", "最小授权角色编码已被其它角色占用。")
            if role_created:
                write_counts["authorizationRoleCreated"] = 1
                _audit(
                    actor=actor, action_code="CREATE_RESPONSIBILITY_AUTHORIZATION_PROJECTION",
                    target=role, target_type="Role", target_label=f"{role.code} - {role.name}",
                    reason="复用现有 RBAC 为正式职责建立最小授权投影",
                    before={}, after={"roleCode": role.code, "responsibilityCode": responsibility.code},
                )

            existing_role_codes = set(
                RolePermission.objects.filter(role=role).values_list("permission__code", flat=True)
            )
            unexpected_codes = existing_role_codes - set(ALLOWED_PERMISSIONS)
            if unexpected_codes:
                raise ExecutorFormalizationError(
                    "AUTHORIZATION_BOUNDARY_CONFLICT",
                    f"最小授权角色已有超范围权限：{sorted(unexpected_codes)}",
                )
            for code, (name, module) in ALLOWED_PERMISSIONS.items():
                permission, permission_created = Permission.objects.get_or_create(
                    code=code, defaults={"name": name, "module": module},
                )
                if permission_created:
                    write_counts["permissionCatalogCreated"] += 1
                    _audit(
                        actor=actor, action_code="REGISTER_MASTER_DATA_ACTION", target=permission,
                        target_type="Permission", target_label=f"{permission.code} - {permission.name}",
                        reason="登记已人工授权基础资料正式化所需业务动作",
                        before={}, after={"code": permission.code, "module": permission.module},
                    )
                _, permission_bound = RolePermission.objects.get_or_create(role=role, permission=permission)
                if permission_bound:
                    write_counts["rolePermissionBound"] += 1

            if position.default_role_id and position.default_role_id != role.pk:
                raise ExecutorFormalizationError("POSITION_ROLE_CONFLICT", "生产总监岗位已有不兼容默认角色。")
            if not position.default_role_id:
                position.default_role = role
                position.full_clean()
                position.save(update_fields=["default_role"])
                write_counts["positionDefaultRoleBound"] = 1
                _audit(
                    actor=actor, action_code="SAVE_POSITION_DEFAULT_ROLE", target=position,
                    target_type="Position", target_label=f"{position.code} {position.name}",
                    reason="岗位职责通过现有 RBAC 投影获得最小业务动作权限",
                    before={"defaultRoleId": None}, after={"defaultRoleId": role.pk, "roleCode": role.code},
                )

            authority_payload = {
                "userId": account.pk,
                "roleCode": role.code,
                "legalEntityId": str(actor.company_id),
                "departmentId": None,
                "scopeCode": UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
                "version": 1,
            }
            assignment, assignment_created = UserRoleScopeAssignment.objects.select_for_update().get_or_create(
                user=account,
                role=role,
                organization_id=actor.company_id,
                defaults={
                    "department": None,
                    "scope_code": UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
                    "active": True,
                    "version": 1,
                    "business_hash": _business_hash(authority_payload),
                },
            )
            if not assignment_created and (
                not assignment.active
                or assignment.scope_code != UserRoleScopeAssignment.ScopeCode.ORGANIZATION
                or assignment.department_id is not None
            ):
                raise ExecutorFormalizationError("AUTHORIZATION_SCOPE_CONFLICT", "EMP047 已有不兼容的职责授权范围。")
            if assignment_created:
                # UserRoleScopeAssignment.clean() currently contains unrelated
                # workshop/company checks copied from another model. The exact
                # organization/scope invariants are guarded above and by DB
                # constraints, so do not invoke that defective model hook here.
                if assignment.organization_id != actor.company_id or assignment.department_id is not None:
                    raise ExecutorFormalizationError(
                        "AUTHORIZATION_SCOPE_CONFLICT", "实名账号授权组织或范围不正确。"
                    )
                write_counts["userRoleScopeBound"] = 1
                _audit(
                    actor=actor, action_code="SET_USER_AUTHORITIES", target=account,
                    target_type="User", target_label=f"{account.username} - {account.real_name}",
                    reason="实名账号承接岗位职责的本组织最小授权",
                    before={}, after={**authority_payload, "businessHash": assignment.business_hash},
                )

        employee = Employee.objects.select_related(
            "department_ref", "position_ref", "position_ref__default_role", "user"
        ).get(employee_no=EMPLOYEE_NO)
        identity = _identity_snapshot(employee)
        allowed_readback = {
            code: AuthorizationService.decide(
                user=employee.user,
                action_code=code,
                organization_id=employee.user.company_id,
                business_object={"organizationId": employee.user.company_id},
            )
            for code in ALLOWED_PERMISSIONS
        }
        denied_readback = {
            code: AuthorizationService.decide(
                user=employee.user,
                action_code=code,
                organization_id=employee.user.company_id,
                business_object={"organizationId": employee.user.company_id},
            )
            for code in DENIED_ACTIONS
        }
        if not all(item["allowed"] for item in allowed_readback.values()):
            raise ExecutorFormalizationError("AUTHORIZATION_READBACK_FAILED", "已授权动作回读未全部生效。")
        if any(item["allowed"] for item in denied_readback.values()):
            raise ExecutorFormalizationError("AUTHORIZATION_BOUNDARY_FAILED", "禁止动作回读发现越权。")
        if not (
            identity["employee"]["active"]
            and identity["position"]["active"]
            and identity["account"]["active"]
            and identity["account"]["employeeExact"]
            and identity["responsibility"]["effective"]
            and identity["authority"]["active"]
        ):
            raise ExecutorFormalizationError("EXECUTOR_CHAIN_READBACK_FAILED", "执行人链最终回读不完整。")

        return {
            "version": VERSION,
            "status": "MASTER DATA EXECUTOR CHAIN: READY",
            "before": {"databaseSha256": before_hash, "counts": before_counts},
            "after": {"databaseSha256": _db_hash(), "counts": cls._counts(actor.company_id)},
            "writeCounts": write_counts,
            "identityReadback": identity,
            "authorizationReadback": {
                "allowed": {code: item["decisionCode"] for code, item in allowed_readback.items()},
                "denied": {code: item["decisionCode"] for code, item in denied_readback.items()},
                "authoritySource": next(iter(allowed_readback.values()))["authoritySource"],
            },
            "adminEmployeeBindingCount": Employee.objects.filter(user=actor).count(),
        }

    @staticmethod
    def _counts(company_id):
        return {
            "users": User.objects.filter(company_id=company_id).count(),
            "employeeUserLinks": Employee.objects.filter(
                department_ref__company_id=company_id, user__isnull=False,
            ).count(),
            "responsibilities": Responsibility.objects.count(),
            "positionResponsibilityMappings": PositionResponsibility.objects.filter(
                position__company_id=company_id,
            ).count(),
            "roles": Role.objects.count(),
            "permissions": Permission.objects.count(),
            "rolePermissionMappings": RolePermission.objects.count(),
            "userRoleScopeAssignments": UserRoleScopeAssignment.objects.filter(
                organization_id=company_id,
            ).count(),
            "organizationAudits": OrganizationOperatingAuditRecord.objects.filter(
                organization_id=company_id,
            ).count(),
        }
