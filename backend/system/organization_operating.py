import re
import time

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import DatabaseError, IntegrityError, OperationalError, transaction
from django.utils.dateparse import parse_date

from pfm.models import (
    Employee,
    EmployeeReportingRelation,
    OrganizationLeadershipAssignment,
)
from workflow_runtime.models import WorkflowNodeDefinition

from .authorization import AuthorizationService
from .organization_code_allocator import (
    ENTITY_DEPARTMENT,
    ENTITY_EMPLOYEE,
    ENTITY_JOB_FAMILY,
    ENTITY_JOB_LEVEL,
    ENTITY_ORGANIZATION_UNIT,
    ENTITY_POSITION,
    allocate_code,
)
from .models import (
    Company,
    Department,
    JobFamily,
    JobLevel,
    OrganizationOperatingAuditRecord,
    OrganizationUnit,
    Position,
    PositionResponsibility,
    PositionWorkflowResponsibility,
    Responsibility,
    Role,
    User,
    Permission,
)
from .organization_operating_request_control import (
    OrganizationRequestControlError,
    OrganizationWriteRequestControl,
    is_idempotent_organization_action,
)


ORGANIZATION_OPERATING_CONTRACT = "PCE-ENTERPRISE-ORGANIZATION-OPERATING-MODEL-V1"

PERMISSION_STRUCTURE_MANAGE = "system.organization.structure.manage"
PERMISSION_DEPARTMENT_MANAGE = "system.organization.department.manage"
PERMISSION_POSITION_MANAGE = "system.organization.position.manage"
PERMISSION_RESPONSIBILITY_MANAGE = "system.organization.responsibility.manage"
PERMISSION_REPORTING_MANAGE = "system.organization.reporting.manage"
PERMISSION_WORKFLOW_RESPONSIBILITY_MANAGE = (
    "system.organization.workflow_responsibility.manage"
)

ACTION_PERMISSIONS = {
    "SAVE_COMPANY_NAME_CORRECTION": PERMISSION_STRUCTURE_MANAGE,
    "SAVE_ORGANIZATION_UNIT": PERMISSION_STRUCTURE_MANAGE,
    "SAVE_DEPARTMENT": PERMISSION_DEPARTMENT_MANAGE,
    "SAVE_DEPARTMENT_LEADER": PERMISSION_DEPARTMENT_MANAGE,
    "SAVE_JOB_FAMILY": PERMISSION_POSITION_MANAGE,
    "SAVE_JOB_LEVEL": PERMISSION_POSITION_MANAGE,
    "SAVE_POSITION": PERMISSION_POSITION_MANAGE,
    "SAVE_RESPONSIBILITY": PERMISSION_RESPONSIBILITY_MANAGE,
    "SAVE_POSITION_RESPONSIBILITY": PERMISSION_RESPONSIBILITY_MANAGE,
    "SAVE_REPORTING_RELATION": PERMISSION_REPORTING_MANAGE,
    "SAVE_EMPLOYEE": PERMISSION_REPORTING_MANAGE,
    "SAVE_EMPLOYEE_ACCOUNT": PERMISSION_REPORTING_MANAGE,
    "SAVE_WORKFLOW_RESPONSIBILITY": PERMISSION_WORKFLOW_RESPONSIBILITY_MANAGE,
}

GLOBAL_ACTIONS = {
    "SAVE_COMPANY_NAME_CORRECTION",
    "SAVE_ORGANIZATION_UNIT",
    "SAVE_JOB_FAMILY",
    "SAVE_JOB_LEVEL",
    "SAVE_RESPONSIBILITY",
}

RESPONSIBILITY_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+){2,}$")
RESPONSIBILITY_STATUS_TRANSITIONS = {
    Responsibility.Status.DRAFT: {
        Responsibility.Status.ACTIVE,
        Responsibility.Status.EXPIRED,
    },
    Responsibility.Status.ACTIVE: {
        Responsibility.Status.SUSPENDED,
        Responsibility.Status.EXPIRED,
    },
    Responsibility.Status.SUSPENDED: {
        Responsibility.Status.ACTIVE,
        Responsibility.Status.EXPIRED,
    },
    Responsibility.Status.EXPIRED: set(),
}


class OrganizationOperatingError(Exception):
    def __init__(self, code, message, *, http_status=400, decision=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.decision = decision


def employee_account_association_context(employee, *, company_id):
    """Project the existing employee-account association company boundary.

    This is deliberately separate from account provisioning and formal business
    candidate eligibility: the existing association action does not require a
    complete position chain or an active employee lifecycle status.
    """
    department = employee.department_ref if employee else None
    employee_company = department.company if department else None
    linked_user = employee.user if employee and employee.user_id else None
    context = {
        "eligible": False,
        "code": "OBJECT_NOT_FOUND",
        "message": "员工不存在。",
        "currentCompanyId": company_id,
        "employeeCompanyId": employee_company.pk if employee_company else None,
        "employeeCompanyName": employee_company.name if employee_company else "未关联正式公司",
        "hasLinkedAccount": linked_user is not None,
        "linkedUserId": employee.user_id if employee else None,
        "linkedUsername": linked_user.username if linked_user else "",
        "linkedUserActive": linked_user.is_active if linked_user else None,
    }
    if employee is None:
        return context
    if employee_company is None:
        return {
            **context,
            "code": "EMPLOYEE_COMPANY_REQUIRED",
            "message": "员工档案尚未通过正式部门确定所属公司，暂不能维护账户关联；请由用户核对真实任职关系。",
        }
    if employee_company.pk != company_id:
        return {
            **context,
            "code": "CROSS_COMPANY_WRITE_FORBIDDEN",
            "message": "员工不属于当前登录公司，不能维护账户关联。",
        }
    return {
        **context,
        "eligible": True,
        "code": "EMPLOYEE_ACCOUNT_ASSOCIATION_READY",
        "message": "员工属于当前登录公司；账户关联仍由正式保存服务校验账户所属公司及唯一关联关系。",
    }


def _required(payload, key, label):
    value = payload.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise OrganizationOperatingError("FIELD_REQUIRED", f"{label}不能为空。")
    return value.strip() if isinstance(value, str) else value


def _optional_id(payload, key):
    value = payload.get(key)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise OrganizationOperatingError("INVALID_REFERENCE", f"{key} 必须是有效对象ID。")


def _date(payload, key):
    value = payload.get(key)
    if value in (None, ""):
        return None
    parsed = parse_date(str(value))
    if not parsed:
        raise OrganizationOperatingError("INVALID_DATE", f"{key} 必须是有效日期。")
    return parsed


def _active(payload, key="active", default=True):
    value = payload.get(key, default)
    if isinstance(value, str):
        return value.strip().lower() not in {"false", "0", "no", "off"}
    return bool(value)


def _snapshot(instance, fields):
    result = {"id": instance.pk}
    for name in fields:
        value = getattr(instance, name)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        result[name] = value
    return result


def _ensure_period(effective_from, effective_to):
    if effective_from and effective_to and effective_to < effective_from:
        raise OrganizationOperatingError(
            "INVALID_EFFECTIVE_PERIOD", "失效日期不能早于生效日期。"
        )


def _ensure_not_descendant(model, instance, parent_id, parent_field="parent_id"):
    if parent_id is None:
        return
    if instance and instance.pk == parent_id:
        raise OrganizationOperatingError("HIERARCHY_CYCLE", "对象不能成为自己的上级。")
    seen = set()
    current_id = parent_id
    while current_id and current_id not in seen:
        if instance and current_id == instance.pk:
            raise OrganizationOperatingError("HIERARCHY_CYCLE", "上下级关系不能形成循环。")
        seen.add(current_id)
        current_id = model.objects.filter(pk=current_id).values_list(parent_field, flat=True).first()


def _reporting_snapshot(relation, *, employee_id=None, relation_type=None):
    return {
        "id": relation.pk if relation else None,
        "employeeId": relation.employee_id if relation else employee_id,
        "managerId": relation.manager_id if relation else None,
        "relationType": (
            relation.relation_type if relation else relation_type
        ) or EmployeeReportingRelation.RelationType.DIRECT,
        "isPrimary": relation.is_primary if relation else True,
        "active": relation.active if relation else False,
        "effectiveFrom": (
            relation.effective_from.isoformat()
            if relation and relation.effective_from else None
        ),
        "effectiveTo": (
            relation.effective_to.isoformat()
            if relation and relation.effective_to else None
        ),
    }


def _employee_manager_for_company(*, employee_id, company_id):
    manager = Employee.objects.select_related("department_ref").filter(pk=employee_id).first()
    if not manager:
        raise OrganizationOperatingError("INVALID_MANAGER", "直属主管员工档案不存在。")
    if not manager.department_ref_id or manager.department_ref.company_id != company_id:
        raise OrganizationOperatingError(
            "CROSS_COMPANY_MANAGER_FORBIDDEN", "V1 不允许设置跨公司的直属主管。"
        )
    return manager


def _ensure_reporting_cycle_free(*, employee, manager, relation_type):
    if employee.pk == manager.pk:
        raise OrganizationOperatingError(
            "SELF_MANAGER_FORBIDDEN", "员工不能成为自己的主管。"
        )
    visited = set()
    current_id = manager.pk
    while current_id:
        if current_id == employee.pk:
            raise OrganizationOperatingError(
                "REPORTING_CYCLE_FORBIDDEN", "员工汇报关系不能形成循环。"
            )
        if current_id in visited:
            raise OrganizationOperatingError(
                "REPORTING_CYCLE_FORBIDDEN", "所选主管所在的汇报链已经存在循环。"
            )
        visited.add(current_id)
        current_id = (
            EmployeeReportingRelation.objects.select_for_update()
            .filter(
                employee_id=current_id,
                relation_type=relation_type,
                active=True,
                is_primary=True,
            )
            .values_list("manager_id", flat=True)
            .first()
        )


class OrganizationOperatingService:
    """Explicit Action -> Guard -> Persistence -> Audit service for organization maintenance."""

    @classmethod
    def execute(cls, *, user, action, payload, request_identity=None):
        action = str(action or "").strip().upper()
        payload = payload or {}
        permission_code = ACTION_PERMISSIONS.get(action)
        if not permission_code:
            raise OrganizationOperatingError("ACTION_NOT_REGISTERED", "组织维护动作未注册。")
        reason = str(payload.get("reason") or "").strip()
        if len(reason) < 2:
            raise OrganizationOperatingError("REASON_REQUIRED", "请填写本次修改原因。")

        idempotent_action = is_idempotent_organization_action(action)
        for attempt in range(8 if idempotent_action else 1):
            try:
                return cls._execute_atomic(
                    user=user,
                    action=action,
                    payload=payload,
                    reason=reason,
                    permission_code=permission_code,
                    request_identity=request_identity,
                    idempotent_action=idempotent_action,
                )
            except OrganizationOperatingError:
                raise
            except OrganizationRequestControlError as error:
                raise OrganizationOperatingError(
                    error.code, error.message, http_status=error.http_status,
                ) from error
            except OperationalError as error:
                locked = "lock" in str(error).lower()
                if idempotent_action and locked and attempt < 7:
                    time.sleep(0.02 * (attempt + 1))
                    continue
                raise OrganizationOperatingError(
                    "IDEMPOTENCY_CONCURRENCY_CONFLICT" if idempotent_action
                    else "PERSISTENCE_DEPENDENCY_UNAVAILABLE",
                    "组织维护请求遇到并发锁冲突，未执行非幂等回退。"
                    if idempotent_action else "组织维护持久化依赖暂不可用。",
                    http_status=409 if idempotent_action else 503,
                ) from error
            except IntegrityError as error:
                if idempotent_action and attempt < 7:
                    time.sleep(0.01 * (attempt + 1))
                    continue
                raise OrganizationOperatingError(
                    "BUSINESS_UNIQUENESS_CONFLICT",
                    "相同正式业务身份已由另一请求提交，本请求未产生第二对象。",
                    http_status=409,
                ) from error
            except (ObjectDoesNotExist, ValidationError, ValueError) as error:
                raise OrganizationOperatingError(
                    "PERSISTENCE_VALIDATION_FAILED", str(error)
                ) from error
            except DatabaseError as error:
                raise OrganizationOperatingError(
                    "FORMAL_WRITE_DEPENDENCY_FAILED",
                    "正式账本、业务对象或审计写入失败；本次事务已回滚。",
                    http_status=503,
                ) from error

    @classmethod
    def _execute_atomic(
        cls, *, user, action, payload, reason, permission_code,
        request_identity, idempotent_action,
    ):
        with transaction.atomic():
            if not Company.objects.filter(pk=user.company_id, is_active=True).exists():
                raise OrganizationOperatingError(
                    "ORGANIZATION_INACTIVE",
                    "当前公司已退出有效经营范围，不允许继续组织维护。",
                    http_status=403,
                )

            department_id = cls._department_context(action, payload, user.company_id)
            decision = AuthorizationService.decide(
                user=user,
                action_code=permission_code,
                organization_id=str(user.company_id),
                business_object={"departmentId": department_id} if department_id else {},
            )
            if not decision["allowed"]:
                raise OrganizationOperatingError(
                    decision["decisionCode"], decision["reason"],
                    http_status=403, decision=decision,
                )
            if action in GLOBAL_ACTIONS and not user.is_superuser:
                scopes = set(decision.get("scope", {}).get("codes") or [])
                if not ({"ALL", "ORGANIZATION"} & scopes):
                    raise OrganizationOperatingError(
                        "SCOPE_DENIED", "该维护动作需要本组织或全部数据范围。",
                        http_status=403, decision=decision,
                    )

            request_control = None
            if idempotent_action:
                # The existing permission row is a per-action serialization lock
                # on databases that support SELECT FOR UPDATE.  Database unique
                # constraints remain the final protection on every backend.
                maintenance_permission = Permission.objects.select_for_update().filter(
                    code=permission_code
                ).first()
                if not maintenance_permission:
                    raise OrganizationOperatingError(
                        "FORMAL_PERMISSION_DEPENDENCY_UNAVAILABLE",
                        "组织正式维护权限主数据不存在。",
                        http_status=503,
                    )
                request_payload = payload
                if (
                    action == "SAVE_RESPONSIBILITY"
                    and _optional_id(payload, "id")
                    and not str(payload.get("status") or "").strip()
                ):
                    current_status = Responsibility.objects.filter(
                        pk=_optional_id(payload, "id")
                    ).values_list("status", flat=True).first()
                    request_payload = {**payload, "status": current_status or ""}
                request_control = OrganizationWriteRequestControl.prepare(
                    user=user,
                    action=action,
                    payload=request_payload,
                    request_identity=request_identity,
                )
                if request_control.is_replay:
                    cls._validate_replay(
                        user=user,
                        action=action,
                        replay_result=request_control.replay_result,
                    )
                    return request_control.replay_result

            handler = getattr(cls, f"_{action.lower()}")
            result = handler(user=user, payload=payload, reason=reason)
            response = {
                "contractVersion": ORGANIZATION_OPERATING_CONTRACT,
                "actionCode": action,
                "requiredPermission": permission_code,
                "authorization": decision,
                **result,
            }
            if not request_control:
                return response

            audit = OrganizationOperatingAuditRecord.objects.select_for_update().filter(
                pk=result.get("auditId"),
                action_code=action,
                actor=user,
                organization_id=user.company_id,
                target_id=result.get("target", {}).get("id"),
            ).first()
            if not audit:
                raise OrganizationRequestControlError(
                    "AUDIT_REFERENCE_INCOMPLETE",
                    "业务对象写入未形成同一事务内的权威审计。",
                )
            audit.after_snapshot = {
                **(audit.after_snapshot or {}),
                "requestControl": request_control.audit_context,
            }
            audit.save(update_fields=["after_snapshot"])

            response.update({
                "requestIdentity": request_control.request_identity,
                "payloadHash": request_control.request_hash,
                "writeRequestId": request_control.ledger.pk,
                "externalIdentityId": request_control.identity.pk,
                "idempotentReplay": False,
                "writeCount": int(result.get("writeCount") or 0) + 2,
            })
            request_control.commit(
                result=response,
                target_entity_id=result["target"]["id"],
                audit_id=audit.pk,
            )
            return response

    @staticmethod
    def _validate_replay(*, user, action, replay_result):
        target = replay_result.get("target") or {}
        target_id = target.get("id")
        audit = OrganizationOperatingAuditRecord.objects.select_for_update().filter(
            pk=replay_result.get("auditId"),
            action_code=action,
            actor=user,
            organization_id=user.company_id,
            target_id=target_id,
        ).first()
        if action == "SAVE_RESPONSIBILITY":
            target_exists = Responsibility.objects.filter(pk=target_id).exists()
        else:
            target_exists = PositionResponsibility.objects.filter(pk=target_id).exists()
        if not audit or not target_exists:
            raise OrganizationRequestControlError(
                "IDEMPOTENCY_HISTORY_INCOMPLETE",
                "首次提交结果引用的正式对象或Audit不存在；禁止将不完整历史重放为成功。",
            )

    @staticmethod
    def _department_context(action, payload, company_id):
        if action in {"SAVE_DEPARTMENT", "SAVE_DEPARTMENT_LEADER"}:
            return _optional_id(payload, "departmentId")
        if action in {"SAVE_POSITION", "SAVE_POSITION_RESPONSIBILITY", "SAVE_WORKFLOW_RESPONSIBILITY"}:
            position_id = _optional_id(payload, "positionId") or _optional_id(payload, "id")
            if position_id:
                return Position.objects.filter(pk=position_id, company_id=company_id).values_list(
                    "department_id", flat=True
                ).first()
            return _optional_id(payload, "departmentId")
        if action in {"SAVE_REPORTING_RELATION", "SAVE_EMPLOYEE", "SAVE_EMPLOYEE_ACCOUNT"}:
            employee_id = _optional_id(payload, "employeeId") or _optional_id(payload, "id")
            if employee_id:
                return Employee.objects.filter(
                    pk=employee_id, department_ref__company_id=company_id
                ).values_list("department_ref_id", flat=True).first()
            return _optional_id(payload, "departmentId")
        return None

    @classmethod
    def _save_company_name_correction(cls, *, user, payload, reason):
        company_id = _optional_id(payload, "companyId") or user.company_id
        if company_id != user.company_id:
            raise OrganizationOperatingError(
                "CROSS_COMPANY_WRITE_FORBIDDEN", "只能纠正当前登录组织的公司名称。", http_status=403,
            )
        company = Company.objects.select_for_update().filter(pk=company_id).first()
        if not company:
            raise OrganizationOperatingError("OBJECT_NOT_FOUND", "公司不存在。")
        expected_code = _required(payload, "companyCode", "公司编码")
        expected_name = _required(payload, "expectedCurrentName", "修改前公司名称")
        corrected_name = _required(payload, "correctedName", "纠正后公司名称")
        decision_basis = _required(payload, "decisionBasis", "用户纠错依据")
        if company.code != expected_code or company.name != expected_name:
            raise OrganizationOperatingError(
                "COMPANY_IDENTITY_CHANGED",
                "公司稳定身份或当前名称已变化，请重新读取后再执行纠错。",
            )
        if corrected_name == expected_name:
            raise OrganizationOperatingError("COMPANY_NAME_UNCHANGED", "纠正后名称与当前名称相同。")
        if Company.objects.exclude(pk=company.pk).filter(name=corrected_name).exists():
            raise OrganizationOperatingError("COMPANY_NAME_CONFLICT", "纠正后公司名称已被其他公司使用。")

        company_before = {
            "id": company.pk, "code": company.code, "name": company.name,
            "is_active": company.is_active,
        }
        mirrored_units = list(OrganizationUnit.objects.select_for_update().filter(
            company=company,
            unit_type=OrganizationUnit.UnitType.COMPANY,
            name=expected_name,
        ).order_by("pk"))
        unit_before = [_snapshot(row, ["code", "name", "unit_type", "company_id"]) for row in mirrored_units]

        company.name = corrected_name
        company.full_clean()
        company.save(update_fields=["name"])
        for unit in mirrored_units:
            unit.name = corrected_name
            unit.full_clean()
            unit.save(update_fields=["name"])

        company_after = {
            "id": company.pk, "code": company.code, "name": company.name,
            "is_active": company.is_active,
        }
        unit_after = [_snapshot(row, ["code", "name", "unit_type", "company_id"]) for row in mirrored_units]
        audit = cls._audit(
            user=user,
            action_code="SAVE_COMPANY_NAME_CORRECTION",
            target=company,
            target_type="Company",
            label=f"{company.code} {company.name}",
            reason=reason,
            before={"company": company_before, "mirroredOrganizationUnits": unit_before},
            after={
                "company": company_after,
                "mirroredOrganizationUnits": unit_after,
                "decisionBasis": decision_basis,
            },
        )
        return {
            "target": company_after,
            "mirroredOrganizationUnits": unit_after,
            "auditId": audit.pk,
            "writeCount": 2 + len(mirrored_units),
        }

    @staticmethod
    def _audit(*, user, action_code, target, target_type, label, reason, before, after):
        audit = OrganizationOperatingAuditRecord.objects.create(
            action_code=action_code,
            actor=user,
            organization_id=user.company_id,
            target_type=target_type,
            target_id=target.pk,
            target_label=label,
            reason=reason,
            before_snapshot=before,
            after_snapshot=after,
        )
        return audit

    @classmethod
    def _save_organization_unit(cls, *, user, payload, reason):
        row_id = _optional_id(payload, "id")
        row = OrganizationUnit.objects.select_for_update().filter(
            pk=row_id, company_id=user.company_id
        ).first() if row_id else None
        if row_id and not row:
            raise OrganizationOperatingError("OBJECT_NOT_FOUND", "组织单元不存在。")
        fields = ["code", "name", "unit_type", "parent_id", "company_id", "is_active", "effective_from", "effective_to"]
        before = _snapshot(row, fields) if row else {}
        parent_id = _optional_id(payload, "parentId")
        _ensure_not_descendant(OrganizationUnit, row, parent_id)
        if parent_id and not OrganizationUnit.objects.filter(pk=parent_id, company_id=user.company_id).exists():
            raise OrganizationOperatingError("INVALID_PARENT", "上级组织单元不属于当前公司。")
        effective_from, effective_to = _date(payload, "effectiveFrom"), _date(payload, "effectiveTo")
        _ensure_period(effective_from, effective_to)
        if not row:
            row = OrganizationUnit(company_id=user.company_id)
        row.code = row.code if row.pk else allocate_code(
            company_id=user.company_id, entity_type=ENTITY_ORGANIZATION_UNIT
        )
        row.name = _required(payload, "name", "组织单元名称")
        row.unit_type = _required(payload, "unitType", "组织单元类型")
        if row.unit_type not in OrganizationUnit.UnitType.values:
            raise OrganizationOperatingError("INVALID_UNIT_TYPE", "组织单元类型无效。")
        row.parent_id = parent_id
        row.is_active = _active(payload)
        row.effective_from, row.effective_to = effective_from, effective_to
        row.full_clean()
        row.save()
        after = _snapshot(row, fields)
        audit = cls._audit(user=user, action_code="SAVE_ORGANIZATION_UNIT", target=row, target_type="OrganizationUnit", label=f"{row.code} {row.name}", reason=reason, before=before, after=after)
        return {"target": after, "auditId": audit.pk, "writeCount": 2}

    @classmethod
    def _save_department(cls, *, user, payload, reason):
        row_id = _optional_id(payload, "departmentId") or _optional_id(payload, "id")
        row = Department.objects.select_for_update().filter(
            pk=row_id, company_id=user.company_id
        ).first() if row_id else None
        if row_id and not row:
            raise OrganizationOperatingError("OBJECT_NOT_FOUND", "部门不存在。")
        fields = ["code", "name", "parent_id", "department_type", "organization_unit_id", "responsible_position_id", "is_active", "effective_from", "effective_to"]
        before = _snapshot(row, fields) if row else {}
        parent_id = _optional_id(payload, "parentId")
        _ensure_not_descendant(Department, row, parent_id)
        if parent_id and not Department.objects.filter(pk=parent_id, company_id=user.company_id).exists():
            raise OrganizationOperatingError("INVALID_PARENT", "上级部门不属于当前公司。")
        unit_id = _optional_id(payload, "organizationUnitId")
        if unit_id and not OrganizationUnit.objects.filter(pk=unit_id, company_id=user.company_id).exists():
            raise OrganizationOperatingError("INVALID_ORGANIZATION_UNIT", "组织单元不属于当前公司。")
        responsible_position_id = _optional_id(payload, "responsiblePositionId")
        if responsible_position_id and not Position.objects.filter(pk=responsible_position_id, company_id=user.company_id).exists():
            raise OrganizationOperatingError("INVALID_POSITION", "责任岗位不属于当前公司。")
        effective_from, effective_to = _date(payload, "effectiveFrom"), _date(payload, "effectiveTo")
        _ensure_period(effective_from, effective_to)
        if not row:
            row = Department(company_id=user.company_id)
        row.code = row.code if row.pk else allocate_code(
            company_id=user.company_id, entity_type=ENTITY_DEPARTMENT
        )
        row.name = _required(payload, "name", "部门名称")
        row.parent_id = parent_id
        row.department_type = _required(payload, "departmentType", "部门类型")
        if row.department_type not in Department.DepartmentType.values:
            raise OrganizationOperatingError("INVALID_DEPARTMENT_TYPE", "部门类型无效。")
        row.organization_unit_id = unit_id
        row.responsible_position_id = responsible_position_id
        row.is_active = _active(payload)
        row.effective_from, row.effective_to = effective_from, effective_to
        row.full_clean()
        row.save()
        after = _snapshot(row, fields)
        audit = cls._audit(user=user, action_code="SAVE_DEPARTMENT", target=row, target_type="Department", label=f"{row.code} {row.name}", reason=reason, before=before, after=after)
        return {"target": after, "auditId": audit.pk, "writeCount": 2}

    @classmethod
    def _save_department_leader(cls, *, user, payload, reason):
        department = Department.objects.get(pk=_required(payload, "departmentId", "部门"), company_id=user.company_id)
        current_rows = list(
            OrganizationLeadershipAssignment.objects.select_for_update()
            .filter(department=department, active=True)
            .order_by("pk")
        )
        current = current_rows[0] if current_rows else None
        before = {"departmentId": department.pk, "leaderEmployeeId": current.employee_id if current else None}
        employee_id = _optional_id(payload, "leaderEmployeeId")
        effective_from, effective_to = _date(payload, "effectiveFrom"), _date(payload, "effectiveTo")
        _ensure_period(effective_from, effective_to)
        employee = None
        if employee_id:
            employee = Employee.objects.filter(pk=employee_id, department_ref__company_id=user.company_id).first()
            if not employee:
                raise OrganizationOperatingError("INVALID_EMPLOYEE", "实际负责人不属于当前公司。")
        closed_count = OrganizationLeadershipAssignment.objects.filter(
            pk__in=[row.pk for row in current_rows]
        ).update(active=False) if current_rows else 0
        target = department
        if employee:
            target = OrganizationLeadershipAssignment.objects.create(
                department=department,
                employee=employee,
                active=True,
                effective_from=effective_from,
                effective_to=effective_to,
            )
        after = {"departmentId": department.pk, "leaderEmployeeId": employee_id}
        audit = cls._audit(user=user, action_code="SAVE_DEPARTMENT_LEADER", target=department, target_type="DepartmentLeadership", label=f"{department.code} {department.name}", reason=reason, before=before, after=after)
        return {
            "target": after,
            "auditId": audit.pk,
            "writeCount": 1 + closed_count + (1 if employee_id else 0),
        }

    @classmethod
    def _save_job_family(cls, *, user, payload, reason):
        return cls._save_named_catalog(user=user, payload=payload, reason=reason, model=JobFamily, target_type="JobFamily", action="SAVE_JOB_FAMILY")

    @classmethod
    def _save_job_level(cls, *, user, payload, reason):
        row_id = _optional_id(payload, "id")
        row = JobLevel.objects.select_for_update().filter(pk=row_id, company_id=user.company_id).first() if row_id else None
        if row_id and not row:
            raise OrganizationOperatingError("OBJECT_NOT_FOUND", "岗位等级不存在。")
        fields = ["code", "name", "rank", "description", "is_active", "company_id"]
        before = _snapshot(row, fields) if row else {}
        if not row:
            row = JobLevel(company_id=user.company_id)
        row.code = row.code if row.pk else allocate_code(
            company_id=user.company_id, entity_type=ENTITY_JOB_LEVEL
        )
        row.name = _required(payload, "name", "岗位等级名称")
        row.rank = int(payload.get("rank") or 1)
        row.description = str(payload.get("description") or "").strip()
        row.is_active = _active(payload)
        row.full_clean(); row.save()
        after = _snapshot(row, fields)
        audit = cls._audit(user=user, action_code="SAVE_JOB_LEVEL", target=row, target_type="JobLevel", label=f"{row.code} {row.name}", reason=reason, before=before, after=after)
        return {"target": after, "auditId": audit.pk, "writeCount": 2}

    @classmethod
    def _save_named_catalog(cls, *, user, payload, reason, model, target_type, action):
        row_id = _optional_id(payload, "id")
        row = model.objects.select_for_update().filter(pk=row_id, company_id=user.company_id).first() if row_id else None
        if row_id and not row:
            raise OrganizationOperatingError("OBJECT_NOT_FOUND", f"{target_type} 不存在。")
        fields = ["code", "name", "description", "is_active", "company_id"]
        before = _snapshot(row, fields) if row else {}
        if not row:
            row = model(company_id=user.company_id)
        row.code = row.code if row.pk else allocate_code(
            company_id=user.company_id, entity_type=ENTITY_JOB_FAMILY
        )
        row.name = _required(payload, "name", "名称")
        row.description = str(payload.get("description") or "").strip()
        row.is_active = _active(payload)
        row.full_clean(); row.save()
        after = _snapshot(row, fields)
        audit = cls._audit(user=user, action_code=action, target=row, target_type=target_type, label=f"{row.code} {row.name}", reason=reason, before=before, after=after)
        return {"target": after, "auditId": audit.pk, "writeCount": 2}

    @classmethod
    def _save_position(cls, *, user, payload, reason):
        row_id = _optional_id(payload, "positionId") or _optional_id(payload, "id")
        row = Position.objects.select_for_update().filter(pk=row_id, company_id=user.company_id).first() if row_id else None
        if row_id and not row:
            raise OrganizationOperatingError("OBJECT_NOT_FOUND", "岗位不存在。")
        fields = ["code", "name", "workshop_id", "department_id", "job_family_id", "job_level_id", "parent_position_id", "default_role_id", "description", "responsibility_summary", "effective_from", "effective_to", "is_active"]
        before = _snapshot(row, fields) if row else {}
        parent_id = _optional_id(payload, "parentPositionId")
        _ensure_not_descendant(Position, row, parent_id, "parent_position_id")
        for key, model, message in [
            ("jobFamilyId", JobFamily, "岗位族"), ("jobLevelId", JobLevel, "岗位等级"),
            ("parentPositionId", Position, "上级岗位"), ("defaultRoleId", Role, "默认角色"),
        ]:
            ref_id = _optional_id(payload, key)
            if ref_id and not model.objects.filter(pk=ref_id).filter(**({"company_id": user.company_id} if hasattr(model, "company") else {})).exists():
                raise OrganizationOperatingError("INVALID_REFERENCE", f"{message}无效。")
        department_id = _optional_id(payload, "departmentId") or (row.department_id if row else None)
        if not department_id or not Department.objects.filter(pk=department_id, company_id=user.company_id).exists():
            raise OrganizationOperatingError("INVALID_DEPARTMENT", "岗位所属部门无效。")
        effective_from, effective_to = _date(payload, "effectiveFrom"), _date(payload, "effectiveTo")
        _ensure_period(effective_from, effective_to)
        if not row:
            row = Position(company_id=user.company_id)
        row.code = row.code if row.pk else allocate_code(
            company_id=user.company_id, entity_type=ENTITY_POSITION
        )
        row.name = _required(payload, "name", "岗位名称")
        row.department_id = department_id
        row.job_family_id = _optional_id(payload, "jobFamilyId")
        row.job_level_id = _optional_id(payload, "jobLevelId")
        row.parent_position_id = parent_id
        row.default_role_id = _optional_id(payload, "defaultRoleId")
        row.description = str(payload.get("description") or "").strip()
        row.responsibility_summary = str(payload.get("responsibilitySummary") or "").strip()
        row.effective_from, row.effective_to = effective_from, effective_to
        row.is_active = _active(payload)
        if "workshopId" in payload:
            from .models import Workshop
            workshop_id = _optional_id(payload, "workshopId")
            if workshop_id and not Workshop.objects.filter(pk=workshop_id, company_id=user.company_id, is_active=True).exists():
                raise OrganizationOperatingError("INVALID_WORKSHOP", "岗位所属车间必须为本公司启用车间。")
            row.workshop_id = workshop_id
        row.full_clean(); row.save()
        after = _snapshot(row, fields)
        audit = cls._audit(user=user, action_code="SAVE_POSITION", target=row, target_type="Position", label=f"{row.code} {row.name}", reason=reason, before=before, after=after)
        return {"target": after, "auditId": audit.pk, "writeCount": 2}

    @classmethod
    def _save_employee(cls, *, user, payload, reason):
        row_id = _optional_id(payload, "employeeId") or _optional_id(payload, "id")
        row = (
            Employee.objects.select_for_update()
            .select_related("department_ref", "position_ref")
            .filter(pk=row_id)
            .first()
            if row_id else None
        )
        if row_id and not row:
            raise OrganizationOperatingError("OBJECT_NOT_FOUND", "员工不存在。")
        if row:
            existing_company_ids = {
                company_id
                for company_id in (
                    row.department_ref.company_id if row.department_ref_id else None,
                    row.position_ref.company_id if row.position_ref_id else None,
                )
                if company_id is not None
            }
            if len(existing_company_ids) > 1:
                raise OrganizationOperatingError(
                    "EMPLOYEE_ORGANIZATION_CONFLICT",
                    "员工现有正式部门与岗位分属不同公司，必须先核对真实组织事实。",
                    http_status=409,
                )
            if existing_company_ids and existing_company_ids != {user.company_id}:
                raise OrganizationOperatingError(
                    "CROSS_COMPANY_WRITE_FORBIDDEN",
                    "员工属于其他公司，禁止跨公司维护。",
                    http_status=403,
                )
        department = Department.objects.filter(
            pk=_required(payload, "departmentId", "正式部门"), company_id=user.company_id
        ).first()
        if not department:
            raise OrganizationOperatingError("INVALID_DEPARTMENT", "正式部门不属于当前公司。")
        position = Position.objects.filter(
            pk=_required(payload, "positionId", "正式岗位"), company_id=user.company_id
        ).first()
        if not position or position.department_id != department.pk:
            raise OrganizationOperatingError("INVALID_POSITION", "正式岗位不属于所选部门。")
        status_code = str(payload.get("status") or Employee._meta.get_field("status").default)
        valid_statuses = {code for code, _ in Employee._meta.get_field("status").choices}
        if status_code not in valid_statuses:
            raise OrganizationOperatingError("INVALID_EMPLOYEE_STATUS", "员工状态无效。")
        fields = ["employee_no", "full_name", "phone", "status", "department_ref_id", "position_ref_id", "user_id"]
        direct_relation = (
            EmployeeReportingRelation.objects.select_for_update()
            .filter(
                employee=row,
                relation_type=EmployeeReportingRelation.RelationType.DIRECT,
                active=True,
                is_primary=True,
            )
            .first()
            if row else None
        )
        before = _snapshot(row, fields) if row else {}
        before["directManager"] = _reporting_snapshot(
            direct_relation,
            employee_id=row.pk if row else None,
            relation_type=EmployeeReportingRelation.RelationType.DIRECT,
        )
        if not row:
            row = Employee()
        row.employee_no = row.employee_no if row.pk else allocate_code(
            company_id=user.company_id, entity_type=ENTITY_EMPLOYEE
        )
        row.full_name = _required(payload, "fullName", "姓名")
        row.phone = str(payload.get("phone") or "").strip()
        row.status = status_code
        row.department_ref = department
        row.position_ref = position
        row.department_id = department.pk
        row.department_name = department.name
        row.position = position.name
        row.full_clean(); row.save()
        relation_write_count = 0
        if "directManagerId" in payload:
            manager_id = _optional_id(payload, "directManagerId")
            effective_from = _date(payload, "directManagerEffectiveFrom")
            effective_to = _date(payload, "directManagerEffectiveTo")
            _ensure_period(effective_from, effective_to)
            if manager_id:
                manager = _employee_manager_for_company(
                    employee_id=manager_id, company_id=user.company_id
                )
                _ensure_reporting_cycle_free(
                    employee=row,
                    manager=manager,
                    relation_type=EmployeeReportingRelation.RelationType.DIRECT,
                )
                if not direct_relation:
                    direct_relation = EmployeeReportingRelation(
                        employee=row,
                        relation_type=EmployeeReportingRelation.RelationType.DIRECT,
                        is_primary=True,
                    )
                direct_relation.manager = manager
                direct_relation.active = True
                direct_relation.effective_from = effective_from
                direct_relation.effective_to = effective_to
                direct_relation.full_clean()
                direct_relation.save()
                relation_write_count = 1
            elif direct_relation:
                direct_relation.active = False
                direct_relation.effective_from = effective_from or direct_relation.effective_from
                direct_relation.effective_to = effective_to or direct_relation.effective_to
                direct_relation.full_clean()
                direct_relation.save(update_fields=["active", "effective_from", "effective_to"])
                relation_write_count = 1
        after = _snapshot(row, fields)
        after["directManager"] = _reporting_snapshot(
            direct_relation if direct_relation and direct_relation.active else None,
            employee_id=row.pk,
            relation_type=EmployeeReportingRelation.RelationType.DIRECT,
        )
        audit = cls._audit(user=user, action_code="SAVE_EMPLOYEE", target=row, target_type="Employee", label=f"{row.employee_no} {row.full_name}", reason=reason, before=before, after=after)
        return {
            "target": after,
            "auditId": audit.pk,
            "writeCount": 2 + relation_write_count,
        }

    @classmethod
    def _save_employee_account(cls, *, user, payload, reason):
        employee = Employee.objects.select_for_update().select_related(
            "department_ref__company", "user",
        ).filter(
            pk=_required(payload, "employeeId", "员工")
        ).first()
        context = employee_account_association_context(employee, company_id=user.company_id)
        if not context["eligible"]:
            raise OrganizationOperatingError(
                context["code"], context["message"],
                http_status=403 if context["code"] == "CROSS_COMPANY_WRITE_FORBIDDEN" else 400,
            )
        user_id = _optional_id(payload, "userId")
        account = None
        if user_id:
            account = User.objects.filter(pk=user_id, company_id=user.company_id).first()
            if not account:
                raise OrganizationOperatingError("INVALID_USER", "登录账户不属于当前公司。")
            if Employee.objects.filter(user=account).exclude(pk=employee.pk).exists():
                raise OrganizationOperatingError("USER_ALREADY_LINKED", "该登录账户已关联其他员工。")
        before = {"id": employee.pk, "user_id": employee.user_id}
        employee.user = account
        employee.full_clean(); employee.save(update_fields=["user"])
        after = {"id": employee.pk, "user_id": employee.user_id}
        audit = cls._audit(user=user, action_code="SAVE_EMPLOYEE_ACCOUNT", target=employee, target_type="EmployeeAccount", label=f"{employee.employee_no} {employee.full_name}", reason=reason, before=before, after=after)
        return {"target": after, "auditId": audit.pk, "writeCount": 2}

    @classmethod
    def _save_responsibility(cls, *, user, payload, reason):
        row_id = _optional_id(payload, "id")
        row = Responsibility.objects.select_for_update().filter(pk=row_id).first() if row_id else None
        if row_id and not row:
            raise OrganizationOperatingError("OBJECT_NOT_FOUND", "岗位职责不存在。")
        fields = [
            "code", "name", "description", "category", "status",
            "effective_from", "effective_to", "is_active",
        ]
        before = _snapshot(row, fields) if row else {}
        creating = row is None
        if creating:
            row = Responsibility()

        code = _required(payload, "code", "职责编码")
        if not RESPONSIBILITY_CODE_PATTERN.fullmatch(code):
            raise OrganizationOperatingError(
                "INVALID_RESPONSIBILITY_CODE",
                "责任编码必须使用大写业务对象与责任目的，至少包含三个下划线分隔部分。",
            )
        if not creating and row.status != Responsibility.Status.DRAFT and code != row.code:
            raise OrganizationOperatingError(
                "RESPONSIBILITY_CODE_IMMUTABLE", "责任离开草稿状态后不得修改编码。"
            )
        code_conflict = Responsibility.objects.select_for_update().filter(code=code)
        if row and row.pk:
            code_conflict = code_conflict.exclude(pk=row.pk)
        if code_conflict.exists():
            raise OrganizationOperatingError(
                "RESPONSIBILITY_CODE_CONFLICT",
                "职责编码已被其他正式责任占用。",
                http_status=409,
            )

        requested_status = str(
            payload.get("status") or (row.status if not creating else Responsibility.Status.DRAFT)
        ).strip().upper()
        if requested_status not in Responsibility.Status.values:
            raise OrganizationOperatingError("INVALID_RESPONSIBILITY_STATUS", "责任状态无效。")
        if creating and requested_status != Responsibility.Status.DRAFT:
            raise OrganizationOperatingError(
                "RESPONSIBILITY_MUST_START_DRAFT", "新责任必须先以草稿状态创建。"
            )
        if not creating and requested_status != row.status:
            allowed = RESPONSIBILITY_STATUS_TRANSITIONS.get(row.status, set())
            if requested_status not in allowed:
                raise OrganizationOperatingError(
                    "INVALID_RESPONSIBILITY_STATUS_TRANSITION",
                    f"不允许责任状态从 {row.status} 转换为 {requested_status}。",
                )

        effective_from = parse_date(str(payload.get("effectiveFrom") or ""))
        effective_to = parse_date(str(payload.get("effectiveTo") or ""))
        if payload.get("effectiveFrom") and effective_from is None:
            raise OrganizationOperatingError("INVALID_EFFECTIVE_DATE", "生效日期格式无效。")
        if payload.get("effectiveTo") and effective_to is None:
            raise OrganizationOperatingError("INVALID_EFFECTIVE_DATE", "失效日期格式无效。")
        if effective_from and effective_to and effective_to < effective_from:
            raise OrganizationOperatingError(
                "INVALID_EFFECTIVE_PERIOD", "失效日期不得早于生效日期。"
            )

        description = str(payload.get("description") or "").strip()
        category = str(payload.get("businessDomain") or payload.get("category") or "").strip()
        if requested_status == Responsibility.Status.ACTIVE:
            if not effective_from:
                raise OrganizationOperatingError(
                    "RESPONSIBILITY_EFFECTIVE_FROM_REQUIRED", "责任生效时必须填写生效日期。"
                )
            if not description:
                raise OrganizationOperatingError(
                    "RESPONSIBILITY_DESCRIPTION_REQUIRED", "责任生效时必须填写说明。"
                )
            if not category:
                raise OrganizationOperatingError(
                    "RESPONSIBILITY_BUSINESS_DOMAIN_REQUIRED", "责任生效时必须填写业务领域。"
                )

        row.code = code
        row.name = _required(payload, "name", "职责名称")
        row.description = description
        row.category = category
        row.status = requested_status
        row.effective_from = effective_from
        row.effective_to = effective_to
        row.is_active = requested_status == Responsibility.Status.ACTIVE
        row.full_clean()
        row.save()
        after = _snapshot(row, fields)
        audit = cls._audit(user=user, action_code="SAVE_RESPONSIBILITY", target=row, target_type="Responsibility", label=f"{row.code} {row.name}", reason=reason, before=before, after=after)
        return {"target": after, "auditId": audit.pk, "writeCount": 2}

    @classmethod
    def _save_position_responsibility(cls, *, user, payload, reason):
        position = Position.objects.select_for_update().get(
            pk=_required(payload, "positionId", "岗位"),
            company_id=user.company_id,
        )
        if not position.is_active:
            raise OrganizationOperatingError("POSITION_INACTIVE", "岗位不是启用状态。")
        responsibility = Responsibility.objects.select_for_update().get(
            pk=_required(payload, "responsibilityId", "职责")
        )
        if (
            not responsibility.is_active
            or responsibility.status != Responsibility.Status.ACTIVE
        ):
            raise OrganizationOperatingError(
                "RESPONSIBILITY_INACTIVE", "只有生效责任可以正式分配给岗位。"
            )
        row_id = _optional_id(payload, "id")
        if row_id:
            row = PositionResponsibility.objects.select_for_update().filter(
                pk=row_id,
                position=position,
                responsibility=responsibility,
            ).first()
            if not row:
                raise OrganizationOperatingError(
                    "OBJECT_NOT_FOUND", "岗位职责关系不存在或业务身份不匹配。"
                )
        else:
            row = PositionResponsibility.objects.select_for_update().filter(
                position=position,
                responsibility=responsibility,
            ).first()
            if row:
                raise OrganizationOperatingError(
                    "POSITION_RESPONSIBILITY_CONFLICT",
                    "该岗位与责任已经存在正式关系；请按关系ID执行后续维护。",
                    http_status=409,
                )
        before = _snapshot(row, ["position_id", "responsibility_id", "is_primary", "active"]) if row else {}
        if not row:
            row = PositionResponsibility(position=position, responsibility=responsibility)
        row.is_primary = _active(payload, "isPrimary", False)
        row.active = _active(payload)
        row.full_clean(); row.save()
        after = _snapshot(row, ["position_id", "responsibility_id", "is_primary", "active"])
        audit = cls._audit(user=user, action_code="SAVE_POSITION_RESPONSIBILITY", target=row, target_type="PositionResponsibility", label=f"{position.name} / {responsibility.name}", reason=reason, before=before, after=after)
        return {"target": after, "auditId": audit.pk, "writeCount": 2}

    @classmethod
    def _save_reporting_relation(cls, *, user, payload, reason):
        employee = Employee.objects.filter(
            pk=_required(payload, "employeeId", "员工"),
            department_ref__company_id=user.company_id,
        ).first()
        if not employee:
            raise OrganizationOperatingError("OBJECT_NOT_FOUND", "员工不存在或不属于当前公司。")
        manager = _employee_manager_for_company(
            employee_id=_required(payload, "managerId", "主管"),
            company_id=user.company_id,
        )
        relation_type = str(payload.get("relationType") or EmployeeReportingRelation.RelationType.DIRECT)
        if relation_type not in EmployeeReportingRelation.RelationType.values:
            raise OrganizationOperatingError("INVALID_RELATION_TYPE", "汇报关系类型无效。")
        _ensure_reporting_cycle_free(
            employee=employee, manager=manager, relation_type=relation_type
        )
        row = EmployeeReportingRelation.objects.select_for_update().filter(employee=employee, relation_type=relation_type, active=True, is_primary=True).first()
        before = _snapshot(row, ["employee_id", "manager_id", "relation_type", "is_primary", "active", "effective_from", "effective_to"]) if row else {}
        if not row:
            row = EmployeeReportingRelation(employee=employee, relation_type=relation_type, is_primary=True)
        row.manager = manager
        row.active = _active(payload)
        row.effective_from, row.effective_to = _date(payload, "effectiveFrom"), _date(payload, "effectiveTo")
        _ensure_period(row.effective_from, row.effective_to)
        row.full_clean(); row.save()
        after = _snapshot(row, ["employee_id", "manager_id", "relation_type", "is_primary", "active", "effective_from", "effective_to"])
        audit = cls._audit(user=user, action_code="SAVE_REPORTING_RELATION", target=row, target_type="EmployeeReportingRelation", label=f"{employee.full_name} → {manager.full_name}", reason=reason, before=before, after=after)
        return {"target": after, "auditId": audit.pk, "writeCount": 2}

    @classmethod
    def _save_workflow_responsibility(cls, *, user, payload, reason):
        row_id = _optional_id(payload, "id")
        row = PositionWorkflowResponsibility.objects.select_for_update().filter(pk=row_id, position__company_id=user.company_id).first() if row_id else None
        if row_id and not row:
            raise OrganizationOperatingError("OBJECT_NOT_FOUND", "流程责任不存在。")
        position = Position.objects.get(pk=_required(payload, "positionId", "责任岗位"), company_id=user.company_id)
        if not position.is_active:
            raise OrganizationOperatingError("POSITION_INACTIVE", "责任岗位已停用。")
        workflow_node_id = _optional_id(payload, "workflowNodeId")
        if not workflow_node_id:
            raise OrganizationOperatingError("WORKFLOW_NODE_REQUIRED", "必须选择正式流程节点。")
        workflow_node = WorkflowNodeDefinition.objects.select_related("process_definition").filter(
            pk=workflow_node_id,
        ).first()
        if not workflow_node:
            raise OrganizationOperatingError("WORKFLOW_NODE_NOT_FOUND", "正式流程节点不存在。")
        if not workflow_node.active:
            raise OrganizationOperatingError("WORKFLOW_NODE_INACTIVE", "正式流程节点已停用。")
        if not workflow_node.process_definition.active:
            raise OrganizationOperatingError("PROCESS_DEFINITION_INACTIVE", "节点所属正式流程已停用。")
        if not Permission.objects.filter(code=workflow_node.business_action_code).exists():
            raise OrganizationOperatingError("BUSINESS_ACTION_NOT_FOUND", "节点业务动作未登记正式权限。")
        ownership_type = _required(payload, "ownershipType", "责任类型")
        if ownership_type not in PositionWorkflowResponsibility.OwnershipType.values:
            raise OrganizationOperatingError("INVALID_OWNERSHIP_TYPE", "责任类型无效。")
        fields = ["position_id", "responsibility_id", "workflow_node_id", "workflow_code", "node_code", "ownership_type", "active", "effective_from", "effective_to"]
        before = _snapshot(row, fields) if row else {}
        if not row:
            row = PositionWorkflowResponsibility()
        responsibility_id = _optional_id(payload, "responsibilityId")
        if not responsibility_id:
            raise OrganizationOperatingError("RESPONSIBILITY_REQUIRED", "必须选择岗位已承担的生效职责。")
        responsibility = Responsibility.objects.filter(pk=responsibility_id).first()
        if not responsibility:
            raise OrganizationOperatingError("INVALID_RESPONSIBILITY", "关联职责不存在。")
        if not responsibility.is_active or responsibility.status != Responsibility.Status.ACTIVE:
            raise OrganizationOperatingError("RESPONSIBILITY_INACTIVE", "关联职责不是生效状态。")
        if not PositionResponsibility.objects.filter(
            position=position, responsibility=responsibility, active=True,
        ).exists():
            raise OrganizationOperatingError(
                "POSITION_RESPONSIBILITY_NOT_ASSIGNED", "该生效职责尚未正式分配给所选岗位。"
            )
        row.position = position
        row.responsibility = responsibility
        row.workflow_node = workflow_node
        row.workflow_code = workflow_node.process_definition.definition_code
        row.node_code = workflow_node.node_code
        row.ownership_type = ownership_type
        row.active = _active(payload)
        row.effective_from, row.effective_to = _date(payload, "effectiveFrom"), _date(payload, "effectiveTo")
        _ensure_period(row.effective_from, row.effective_to)
        row.full_clean(); row.save()
        after = _snapshot(row, fields)
        audit = cls._audit(user=user, action_code="SAVE_WORKFLOW_RESPONSIBILITY", target=row, target_type="PositionWorkflowResponsibility", label=f"{position.name} / {row.workflow_code} / {row.node_code}", reason=reason, before=before, after=after)
        return {"target": after, "auditId": audit.pk, "writeCount": 2}
