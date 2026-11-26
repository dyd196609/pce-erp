from dataclasses import dataclass

from django.db import DatabaseError
from django.db.models import Q

from workflow_runtime.models import UserOrganizationRoleAuthority

from .models import Company, RolePermission, UserRoleScopeAssignment


AUTHORIZATION_CONTRACT_VERSION = "PCE-ORGANIZATION-ACCESS-CORE-V1"
FORMAL_AUTHORITY_SOURCE = "system.UserRoleScopeAssignment"
LEGACY_AUTHORITY_SOURCE = "workflow_runtime.UserOrganizationRoleAuthority"


def authority_scope_code(authority):
    formal_code = str(getattr(authority, "scope_code", "") or "").strip().upper()
    if formal_code in {"SELF", "DEPARTMENT", "ORGANIZATION", "ALL", "CUSTOM"}:
        return formal_code
    marker = str(getattr(authority, "department_id", "") or "").strip()
    if marker == "SELF":
        return "SELF"
    if marker == "ALL":
        return "ALL"
    if marker:
        return "DEPARTMENT"
    return "ORGANIZATION"


@dataclass(frozen=True)
class AuthorityEvidence:
    role_code: str
    organization_id: str
    scope_code: str
    department_id: int | None
    source: str


class AuthorizationService:
    """Single PCE V1 server-side authorization decision service."""

    @classmethod
    def decide(
        cls,
        *,
        user,
        action_code,
        organization_id=None,
        business_object=None,
        context=None,
    ):
        action_code = str(action_code or "").strip()
        organization_id = str(organization_id or getattr(user, "company_id", "") or "")
        base = {
            "contractVersion": AUTHORIZATION_CONTRACT_VERSION,
            "allowed": False,
            "actionCode": action_code,
            "organizationId": organization_id,
            "reason": "当前用户没有该业务动作权限。",
            "decisionCode": "PERMISSION_DENIED",
            "scope": {"codes": [], "departmentIds": []},
            "facts": {
                "visible": False,
                "executable": False,
                "disabledReason": "当前用户没有该业务动作权限。",
            },
            "roleCodes": [],
            "permissionCodes": [],
            "authoritySource": FORMAL_AUTHORITY_SOURCE,
        }
        if not action_code:
            return cls._deny(base, "ACTION_CODE_REQUIRED", "业务动作编码不能为空。")
        if not user or not user.is_authenticated or not user.is_active:
            return cls._deny(base, "IDENTITY_INVALID", "当前登录身份无效。")
        company = Company.objects.filter(pk=organization_id).only("id", "is_active").first()
        if not company:
            return cls._deny(base, "ORGANIZATION_NOT_FOUND", "目标公司不存在。")
        if not company.is_active:
            return cls._deny(
                base,
                "ORGANIZATION_INACTIVE",
                "目标公司已退出有效经营范围，不允许新增或修改业务数据。",
            )
        if user.is_superuser:
            return {
                **base,
                "allowed": True,
                "reason": "系统管理员通过统一授权服务校验。",
                "decisionCode": "ALLOWED_SUPERUSER",
                "scope": {"codes": ["ALL"], "departmentIds": []},
                "facts": {"visible": True, "executable": True, "disabledReason": ""},
                "roleCodes": ["superadmin"],
                "permissionCodes": ["*"],
                "authoritySource": "system.User",
            }

        evidence = cls.authority_evidence(user, organization_id)
        role_codes = {row.role_code for row in evidence}
        permission_codes = cls._permission_codes(role_codes)
        scoped_evidence = [
            row for row in evidence
            if cls._scope_matches(row, user, business_object or {}, context or {})
        ]
        scope_codes = sorted({row.scope_code for row in scoped_evidence})
        department_ids = sorted({
            row.department_id for row in scoped_evidence
            if row.department_id is not None
        })
        source = evidence[0].source if evidence else FORMAL_AUTHORITY_SOURCE
        decision = {
            **base,
            "roleCodes": sorted(role_codes),
            "permissionCodes": sorted(permission_codes),
            "scope": {"codes": scope_codes, "departmentIds": department_ids},
            "authoritySource": source,
        }
        if action_code not in permission_codes:
            return cls._deny(decision, "PERMISSION_DENIED", "当前角色未获得该业务动作权限。")
        if not scoped_evidence:
            return cls._deny(decision, "SCOPE_DENIED", "当前授权范围不覆盖该组织或业务对象。")
        return {
            **decision,
            "allowed": True,
            "reason": "角色、业务动作权限和数据范围均通过统一授权服务校验。",
            "decisionCode": "ALLOWED",
            "facts": {"visible": True, "executable": True, "disabledReason": ""},
        }

    @classmethod
    def authority_evidence(cls, user, organization_id=None):
        organization_id = str(organization_id or "").strip()
        if not user or not getattr(user, "pk", None):
            return []
        try:
            formal = list(
                UserRoleScopeAssignment.objects.select_related(
                    "role", "organization", "department"
                ).filter(user=user, active=True)
            )
        except (DatabaseError, TypeError):
            formal = []
        if formal:
            return [
                AuthorityEvidence(
                    role_code=row.role.code,
                    organization_id=str(row.organization_id),
                    scope_code=row.scope_code,
                    department_id=row.department_id,
                    source=FORMAL_AUTHORITY_SOURCE,
                )
                for row in formal
                if not organization_id or str(row.organization_id) == organization_id
            ]

        # Temporary compatibility adapter for protected R5.1/R10 consumers.
        try:
            legacy = UserOrganizationRoleAuthority.objects.filter(user=user, active=True)
            if organization_id:
                legacy = legacy.filter(legal_entity_id=organization_id)
            legacy = list(legacy)
        except (DatabaseError, TypeError):
            legacy = []
        return [
            AuthorityEvidence(
                role_code=row.role_code,
                organization_id=str(row.legal_entity_id),
                scope_code=authority_scope_code(row),
                department_id=(int(row.department_id) if str(row.department_id or "").isdigit() else None),
                source=LEGACY_AUTHORITY_SOURCE,
            )
            for row in legacy
        ]

    @classmethod
    def permission_profile(cls, user):
        if not user or not user.is_authenticated:
            return {
                "contractVersion": AUTHORIZATION_CONTRACT_VERSION,
                "authenticated": False,
                "roles": [],
                "permissionCodes": [],
                "actionFacts": {},
                "scopeCodes": [],
            }
        if user.is_superuser:
            role_codes, permission_codes, scope_codes = ["superadmin"], ["*"], ["ALL"]
            source = "system.User"
        else:
            evidence = cls.authority_evidence(user)
            role_codes = sorted({row.role_code for row in evidence})
            permission_codes = sorted(cls._permission_codes(role_codes))
            scope_codes = sorted({row.scope_code for row in evidence})
            source = evidence[0].source if evidence else FORMAL_AUTHORITY_SOURCE
        company = Company.objects.filter(pk=user.company_id).only("code", "name").first()
        return {
            "contractVersion": AUTHORIZATION_CONTRACT_VERSION,
            "authenticated": True,
            "userId": user.pk,
            "identity": {
                "userId": user.pk,
                "username": user.username,
                "realName": user.real_name,
                "employee": _employee_payload(user),
            },
            "organization": {
                "id": user.company_id,
                "code": company.code if company else "",
                "name": company.name if company else "",
            },
            "roles": role_codes,
            "permissionCodes": permission_codes,
            "actionFacts": {
                code: {
                    "actionCode": code,
                    "visible": True,
                    "executable": True,
                    "disabledReason": "",
                }
                for code in permission_codes
                if code != "*"
            },
            "scopeCodes": scope_codes,
            "authoritySource": source,
            "employee": _employee_payload(user),
            "aiBoundary": "ADVISORY_ONLY",
        }

    @staticmethod
    def _permission_codes(role_codes):
        if not role_codes:
            return set()
        try:
            return set(
                RolePermission.objects.filter(role__code__in=role_codes)
                .values_list("permission__code", flat=True)
                .distinct()
            )
        except DatabaseError:
            return set()

    @staticmethod
    def _scope_matches(evidence, user, business_object, context):
        object_organization_id = str(
            business_object.get("organizationId")
            or business_object.get("companyId")
            or context.get("organizationId")
            or evidence.organization_id
        )
        if object_organization_id != evidence.organization_id:
            return False
        if evidence.scope_code in {"ALL", "ORGANIZATION"}:
            return True
        if evidence.scope_code == "DEPARTMENT":
            object_department_id = business_object.get("departmentId") or context.get("departmentId")
            return object_department_id is None or str(object_department_id) == str(evidence.department_id)
        if evidence.scope_code == "SELF":
            owner_user_id = (
                business_object.get("ownerUserId")
                or business_object.get("userId")
                or context.get("ownerUserId")
            )
            return owner_user_id is None or str(owner_user_id) == str(user.pk)
        return False

    @staticmethod
    def _deny(base, decision_code, reason):
        return {
            **base,
            "allowed": False,
            "reason": reason,
            "decisionCode": decision_code,
            "facts": {"visible": False, "executable": False, "disabledReason": reason},
        }


class BusinessPermissionAuthorization:
    """Compatibility facade; all decisions now delegate to AuthorizationService."""

    @classmethod
    def decide(cls, user, permission_code, legal_entity_id=None):
        decision = AuthorizationService.decide(
            user=user,
            action_code=permission_code,
            organization_id=legal_entity_id,
        )
        return {
            **decision,
            "permissionCode": permission_code,
            "legalEntityId": str(legal_entity_id or ""),
            "scopeCodes": decision["scope"]["codes"],
            "authorityType": "PCE_ORGANIZATION_ACCESS_CORE_V1",
            "source": decision["authoritySource"],
        }


def user_access_profile(user):
    return AuthorizationService.permission_profile(user)


def scope_employee_queryset(queryset, user):
    """Apply the same formal Scope facts used by AuthorizationService."""
    if not user or not user.is_authenticated or not user.is_active:
        return queryset.none()
    if user.is_superuser:
        return queryset
    evidence = AuthorizationService.authority_evidence(user)
    if any(row.scope_code == "ALL" for row in evidence):
        return queryset
    scope_filter = Q(pk__in=[])
    for row in evidence:
        if row.scope_code == "SELF":
            scope_filter |= Q(user=user)
        elif row.scope_code == "DEPARTMENT" and row.department_id is not None:
            scope_filter |= Q(department_ref_id=row.department_id)
        elif row.scope_code == "ORGANIZATION":
            scope_filter |= Q(department_ref__company_id=row.organization_id)
    return queryset.filter(scope_filter).distinct()


def _employee_payload(user):
    try:
        employee = user.employee_profile
    except Exception:
        return None
    return {
        "id": employee.pk,
        "employeeNo": employee.employee_no,
        "fullName": employee.full_name,
        "departmentId": employee.department_ref_id,
        "departmentName": employee.department_ref.name if employee.department_ref else employee.department_name,
        "positionId": employee.position_ref_id,
        "positionName": employee.position_ref.name if employee.position_ref else employee.position,
        "status": employee.status,
    }
