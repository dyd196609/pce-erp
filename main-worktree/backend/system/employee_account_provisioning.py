"""Governed employee account-number generation and management-position provisioning."""

from hashlib import sha256
import json
import re

from django.db import transaction
from django.db.models import Q

from pfm.models import Employee

from .models import OrganizationOperatingAuditRecord, User


MANAGEMENT_POSITION_MARKERS = ("主管", "经理", "总监", "总经理")


class EmployeeAccountProvisioningError(ValueError):
    pass


def employee_account_number(employee):
    """Return the stable account number derived from the formal employee number."""
    stem = re.sub(r"[^a-z0-9]+", "_", str(employee.employee_no or "").lower()).strip("_")
    if not stem:
        raise EmployeeAccountProvisioningError("员工编号为空，不能生成登录账号。")
    return f"pce_{stem}"


def employee_company_id(employee):
    """Resolve the formal company without trusting client-provided account data."""
    department_company_id = getattr(employee.department_ref, "company_id", None)
    position_company_id = getattr(employee.position_ref, "company_id", None)
    company_ids = {value for value in (department_company_id, position_company_id) if value}
    if len(company_ids) != 1:
        raise EmployeeAccountProvisioningError("员工正式部门和岗位未确定唯一所属公司，不能开户。")
    return company_ids.pop()


def employee_account_provisioning_eligibility(employee, *, actor_company_id=None):
    """Project the existing SAVE_USER prerequisites without performing writes."""

    try:
        company_id = employee_company_id(employee)
    except EmployeeAccountProvisioningError as exc:
        return {
            "eligible": False,
            "code": "ACCOUNT_COMPANY_UNRESOLVED",
            "message": str(exc),
            "companyId": None,
        }
    if actor_company_id is not None and company_id != actor_company_id:
        return {
            "eligible": False,
            "code": "ACCOUNT_CROSS_COMPANY_FORBIDDEN",
            "message": "员工不属于当前管理员的经营公司，禁止跨公司开户。",
            "companyId": company_id,
        }
    if employee.status != "active":
        return {
            "eligible": False,
            "code": "ACCOUNT_EMPLOYEE_NOT_ACTIVE",
            "message": "仅可为当前在职员工建立登录账户。",
            "companyId": company_id,
        }
    if employee.user_id:
        return {
            "eligible": False,
            "code": "ACCOUNT_ALREADY_LINKED",
            "message": "该员工已关联正式登录账户，不能重复开户。",
            "companyId": company_id,
        }
    return {
        "eligible": True,
        "code": "ACCOUNT_PROVISIONING_READY",
        "message": "符合现有账户合同，可建立待设置初始密码的账户。",
        "companyId": company_id,
    }


@transaction.atomic
def provision_employee_account(*, employee, actor, reason, audit_action_code="CREATE_EMPLOYEE_ACCOUNT"):
    """Create or idempotently return the one governed account for an employee.

    The account starts with an unusable password.  Credential initialization is
    intentionally left to the existing explicit administrator password flow.
    """
    if not actor or not actor.is_superuser or not actor.company_id:
        raise EmployeeAccountProvisioningError("必须由当前公司的技术管理员执行员工开户。")
    reason = str(reason or "").strip()
    if not reason:
        raise EmployeeAccountProvisioningError("必须填写开户依据。")
    locked = Employee.objects.select_for_update().select_related(
        "user", "department_ref", "position_ref"
    ).get(pk=employee.pk)
    company_id = employee_company_id(locked)
    if company_id != actor.company_id:
        raise EmployeeAccountProvisioningError("员工不属于当前管理员的经营公司，禁止跨公司开户。")
    if locked.status != "active":
        raise EmployeeAccountProvisioningError("仅可为当前在职员工建立登录账户。")
    if locked.user_id:
        return {
            "account": locked.user,
            "employee": locked,
            "created": False,
            "idempotentReplay": True,
            "auditId": None,
        }
    username = employee_account_number(locked)
    owner = User.objects.select_for_update().filter(username=username).first()
    if owner:
        raise EmployeeAccountProvisioningError(f"系统生成账号 {username} 已被其他身份占用，开户已停止。")
    account = User(
        username=username,
        real_name=locked.full_name,
        company_id=company_id,
        is_active=True,
        is_staff=False,
    )
    account.set_unusable_password()
    account.full_clean()
    account.save()
    locked.user = account
    locked.full_clean()
    locked.save(update_fields=["user", "updated_at"])
    business_hash = sha256(json.dumps({
        "employeeId": locked.pk,
        "employeeNo": locked.employee_no,
        "username": username,
        "companyId": company_id,
    }, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=audit_action_code,
        actor=actor,
        organization_id=company_id,
        target_type="EmployeeAccount",
        target_id=locked.pk,
        target_label=f"{locked.employee_no} {locked.full_name} / {username}",
        reason=reason,
        before_snapshot={"userId": None},
        after_snapshot={
            "userId": account.pk,
            "username": username,
            "active": True,
            "credentialState": "PENDING_SECURE_INITIALIZATION",
            "rolesAssigned": 0,
            "businessHash": business_hash,
        },
    )
    return {
        "account": account,
        "employee": locked,
        "created": True,
        "idempotentReplay": False,
        "auditId": audit.pk,
    }


def management_position_candidates(*, company_id):
    query = Q()
    for marker in MANAGEMENT_POSITION_MARKERS:
        query |= Q(position_ref__name__contains=marker)
    return Employee.objects.select_related("user", "position_ref", "department_ref").filter(
        department_ref__company_id=company_id,
        status="active",
        position_ref__is_active=True,
    ).filter(query).order_by("position_ref__name", "employee_no")


@transaction.atomic
def provision_missing_management_accounts(*, actor, reason, apply=False):
    if not actor or not actor.is_superuser or not actor.company_id:
        raise EmployeeAccountProvisioningError("必须由当前公司的技术管理员执行管理岗位开户。")
    reason = str(reason or "").strip()
    if not reason:
        raise EmployeeAccountProvisioningError("必须填写开户依据。")
    candidates = list(management_position_candidates(company_id=actor.company_id).select_for_update())
    occupied = set(User.objects.select_for_update().values_list("username", flat=True))
    preview = []
    created = []
    for employee in candidates:
        if employee.user_id:
            preview.append({
                "employeeId": employee.pk, "employeeNo": employee.employee_no,
                "name": employee.full_name, "position": employee.position_ref.name,
                "mode": "EXISTING_ACCOUNT_REUSED", "username": employee.user.username,
            })
            continue
        username = employee_account_number(employee)
        owner = User.objects.filter(username=username).first()
        if owner:
            raise EmployeeAccountProvisioningError(
                f"生成账号 {username} 已被其他身份占用，停止批量开户。"
            )
        row = {
            "employeeId": employee.pk, "employeeNo": employee.employee_no,
            "name": employee.full_name, "position": employee.position_ref.name,
            "mode": "WOULD_CREATE" if not apply else "CREATED_PENDING_SECURE_INITIALIZATION",
            "username": username,
        }
        preview.append(row)
        if not apply:
            continue
        result = provision_employee_account(
            employee=employee, actor=actor, reason=reason,
            audit_action_code="CREATE_MANAGEMENT_EMPLOYEE_ACCOUNT",
        )
        account = result["account"]
        created.append({"employeeId": employee.pk, "userId": account.pk, "username": username})
        occupied.add(username)
    return {
        "mode": "APPLY" if apply else "DRY_RUN",
        "positionMarkers": list(MANAGEMENT_POSITION_MARKERS),
        "candidateCount": len(candidates),
        "missingAccountCount": sum(row["mode"] in {"WOULD_CREATE", "CREATED_PENDING_SECURE_INITIALIZATION"} for row in preview),
        "created": created,
        "rows": preview,
        "passwordWrites": 0,
        "roleAssignmentWrites": 0,
        "permissionWrites": 0,
    }
