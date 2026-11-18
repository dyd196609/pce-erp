"""Delivered formal read/proof kernel with explicit purpose admission.
Only the original read/proof functions are loaded; this does not expose formal writes.
"""
from decimal import Decimal
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition
from .models import FormalProductionSchedule as Schedule,ProcessingReservation as Reservation
from .scheduling_primitives import _hash,_instant,_read_instantfrom .services import PlanningBusinessErrordef _fail(code,message,status=409,data=None):    raise PlanningBusinessError(code,message,http_status=status,data=data)

MODULE='formal-production-schedule'
OBJECT='FormalProductionSchedule'
PERMISSIONS={'commit':'planning.schedule.commit','cancel':'planning.schedule.cancel','authorize-capacity-scope':'planning.schedule.capacity_scope.authorize'}

def _active_reservations(actor):
    rows = list(Reservation.objects.filter(company_id=actor.company_id, released_at__isnull=True, schedule__usage_purpose="PRODUCTION_USE", schedule__production_plan_id__isnull=False)
        .select_related("schedule").order_by("pk"))
    checked = set()
    for row in rows:
        if row.schedule_id not in checked:
            _verify_schedule(row.schedule)
            checked.add(row.schedule_id)
    return rows

def _reservation_state(row):
    return {"id": row.pk, "scheduleId": row.schedule_id, "companyId": row.company_id,
        "workCenterId": row.work_center_id, "stepId": row.routing_step_id,
        "start": _read_instant(row.start_at).isoformat(), "end": _read_instant(row.end_at).isoformat(), "minutes": str(row.minutes),
        "scheduleStatus": row.schedule.status, "scheduleVersion": row.schedule.version}

def _verify_action_audit(audit, action):
    proof = audit.after_snapshot.get("state", {}).get("actionPermissionDecision") or {}
    native = audit.after_snapshot.get("authorization") or {}
    if (proof.get("granted") is not True or proof.get("action", {}).get("moduleCode") != MODULE
            or proof.get("action", {}).get("actionCode") != action or native.get("allowed") is not True
            or not ({"*", PERMISSIONS[action]} & set(native.get("permissionCodes", [])))):
        _fail("FORMAL_SCHEDULE_ACTION_PROOF_INVALID", "正式对象缺少统一动作权限及原生授权的已提交审计。")

def _verify_schedule(row):
    from .test_scheduling_service import require_formal_schedule
    require_formal_schedule(row)
    if row.snapshot_hash != _hash(row.snapshot):
        _fail("FORMAL_SCHEDULE_SNAPSHOT_INVALID", "正式排程冻结快照Hash不一致。")
    preview = row.snapshot["preview"]
    if (_read_instant(row.start_at) != _instant(preview["start"])
            or _read_instant(row.end_at) != _instant(preview["end"])
            or row.timezone != preview["timezone"]):
        _fail("FORMAL_SCHEDULE_SNAPSHOT_INVALID", "正式排程时间或时区与冻结快照不一致。")
    transitions = list(BusinessStateTransition.objects.filter(object_type=OBJECT, object_id=row.pk).order_by("version", "pk"))
    expected = [("", "draft"), ("draft", "saved")] + ([("saved", "cancelled")] if row.status == "cancelled" else [])
    if row.status not in {"saved", "cancelled"} or len(transitions) != len(expected) or row.version != len(expected) - 1:
        _fail("FORMAL_SCHEDULE_STATE_PROOF_INVALID", "排程状态与统一转换历史不一致。")
    for index, (transition, pair) in enumerate(zip(transitions, expected), 1):
        audit_id = transition.audit_reference.removeprefix("OrganizationOperatingAuditRecord:")
        audit = OrganizationOperatingAuditRecord.objects.filter(pk=audit_id, organization_id=row.company_id,
            target_type=OBJECT, target_id=row.pk, actor_id=transition.operator_id, action_code=transition.action_code).first()
        if (transition.version != index or (transition.source_state, transition.target_state) != pair or audit is None
                or audit.after_snapshot.get("state", {}).get("snapshotHash") != row.snapshot_hash
                or audit.after_snapshot.get("state", {}).get("status") != pair[1]):
            _fail("FORMAL_SCHEDULE_STATE_PROOF_INVALID", "排程统一转换未对应真实对象审计及冻结快照。")
        _verify_action_audit(audit, "cancel" if pair[1] == "cancelled" else "commit")
    actual = list(row.reservations.order_by("pk"))
    if len(actual) != len(row.snapshot["segments"]):
        _fail("FORMAL_SCHEDULE_OCCUPANCY_PROOF_INVALID", "正式排程加工分段数量与冻结快照不一致。")
    for saved, source in zip(actual, row.snapshot["segments"]):
        if (saved.company_id != row.company_id or saved.routing_step_id != source["stepId"]
                or saved.work_center_id != source["workCenterId"] or saved.sequence != source["sequence"]
                or _read_instant(saved.start_at) != _instant(source["start"]) or _read_instant(saved.end_at) != _instant(source["end"])
                or Decimal(saved.minutes) != Decimal(source["minutes"]) or saved.production_date.isoformat() != source["productionDate"]
                or (saved.released_at is None) != (row.status == "saved")):
            _fail("FORMAL_SCHEDULE_OCCUPANCY_PROOF_INVALID", "持久化加工分段或释放状态与冻结事实不一致。")
    return transitions, actual


# Native formal continuation: individually restored symbols; existing proofs preserved.
from copy import deepcopy

from datetime import date, datetime, timezone as datetime_timezone

import json

import os

from pathlib import Path

import re

from django.conf import settings

from django.db import connection, models, transaction

from workflow_runtime.action_permissions import ActionPermissionValidator, POLICIES

from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state, record_projected_business_transition,
    transition_business_object,
)

from .models import ScheduleCapacityGrant as Grant, SchedulingCompanyMutex as Mutex

from .services import (
    PlanningBusinessError, _plan_start_actor, _plan_start_rows, _plan_start_decision,
    _require_plan_start_permission, _parse_plan_start_date, record_audit,
)

CONTRACT = "PCE-PRODUCTION-PLAN-FORMAL-SCHEDULING-V1"

GRANT_CONTRACT = "PCE-EXACT-PLAN-STEP-PROCESSING-SCOPE-V1"

GRANT_OBJECT = "ScheduleCapacityGrant"

LABELS = {"commit": "保存正式排程", "cancel": "撤销排程并释放占用",
          "authorize-capacity-scope": "确认精确用途依据", "validate": "执行正式排程准入"}

ENVIRONMENT_LABELS = {"DAILY": "日常正式排程", "REHEARSAL": "日常启用隔离演练",
                      "ISOLATED": "隔离正式排程验证"}

RUNTIME_IDENTITIES = {
    "DAILY": ("PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE", "PDE-OPERABLE-ACCEPTANCE-20260912", "Daily"),
    "REHEARSAL": ("PCE_FORMAL_SCHEDULING_REHEARSAL", "PCE-FORMAL-SCHEDULING-REHEARSAL", "Rehearsal"),
}

def _json(value):
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, allow_nan=False))

def _legacy_execution_boundary():
    enabled = getattr(settings, "PCE_FORMAL_SCHEDULING_ISOLATED", None)
    enabled = enabled if enabled is not None else os.environ.get("PCE_FORMAL_SCHEDULING_ISOLATED") == "1"
    configured = getattr(settings, "PCE_FORMAL_SCHEDULING_DATABASE", "") or os.environ.get("PCE_FORMAL_SCHEDULING_DATABASE", "")
    current = str(connection.settings_dict.get("NAME", ""))
    if (not enabled or not configured or current.startswith("file:")
            or Path(current).resolve() != Path(configured).resolve()
            or not Path(configured).is_absolute()):
        _fail("FORMAL_SCHEDULING_ISOLATED_DATABASE_REQUIRED",
            "正式排程执行本轮仅开放已明确绑定的隔离数据库。", 403)
    if connection.vendor != "sqlite":
        _fail("FORMAL_SCHEDULING_DATABASE_UNSUPPORTED", "本轮仅验证受控SQLite隔离事务。", 403)
    with connection.cursor() as cursor:
        actual = next((row[2] for row in cursor.execute("PRAGMA database_list").fetchall() if row[1] == "main"), "")
    if not actual or Path(actual).resolve() != Path(configured).resolve():
        _fail("FORMAL_SCHEDULING_DATABASE_IDENTITY_MISMATCH", "实际数据库连接与正式排程绑定路径不一致。", 403)

def _runtime_setting(name):
    value = getattr(settings, name, None)
    return value if value is not None else os.environ.get(name)

def _runtime_environment():
    environment = _runtime_setting("PCE_FORMAL_SCHEDULING_ENVIRONMENT")
    if environment in (None, ""):
        return None  # Existing isolated launchers retain their original gate.
    if not isinstance(environment, str) or environment not in ENVIRONMENT_LABELS:
        _fail("FORMAL_SCHEDULING_ENVIRONMENT_INVALID", "正式排程必须声明有效的服务端运行环境。", 403)
    return environment

def _runtime_scope():
    raw = _runtime_setting("PCE_FORMAL_SCHEDULING_SCOPE")
    try:
        scope = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        scope = None
    if (type(scope) is not dict or set(scope) != {"companyId", "productionPlanId", "companyCode", "productionPlanNo"}
            or any(type(scope[key]) is not int or scope[key] <= 0 for key in ("companyId", "productionPlanId"))
            or any(not isinstance(scope[key], str) or not scope[key] or scope[key] != scope[key].strip()
                   for key in ("companyCode", "productionPlanNo"))):
        _fail("FORMAL_SCHEDULING_SCOPE_REQUIRED", "本运行环境必须配置准确的公司及生产计划服务端范围。", 403)
    return scope

def _execution_boundary():
    environment = _runtime_environment()
    if environment in (None, "ISOLATED"):
        _legacy_execution_boundary()
        return None
    # Modern environments are explicit identities, never aliases for the old
    # isolated switch. The sealed launcher owns these server declarations.
    if (os.environ.get("PCE_FORMAL_SCHEDULING_ISOLATED") == "1"
            or _runtime_setting("PCE_FORMAL_SCHEDULING_ISOLATED") not in (None, False, 0, "", "0")):
        _fail("FORMAL_SCHEDULING_ENVIRONMENT_CONFLICT", "日常及演练环境不能声明旧隔离排程资格。", 403)
    profile, identity, target = RUNTIME_IDENTITIES[environment]
    if (os.environ.get("PCE_RUNTIME_PROFILE") != profile
            or os.environ.get("PCE_DATABASE_IDENTITY") != identity
            or os.environ.get("PCE_RELEASE_RUNTIME_TARGET") != target
            or os.environ.get("PCE_RUNTIME_LAUNCHER_VERIFIED") != "1"
            or (environment == "DAILY" and (os.environ.get("PCE_NON_PRODUCTION_ACCEPTANCE") != "1"
                or os.environ.get("PCE_ISOLATED_RUNSERVER_TEST") == "1"))
            or (environment == "REHEARSAL" and (os.environ.get("PCE_ISOLATED_RUNSERVER_TEST") != "1"
                or os.environ.get("PCE_NON_PRODUCTION_ACCEPTANCE") == "1"))):
        _fail("FORMAL_SCHEDULING_RUNTIME_IDENTITY_MISMATCH", "正式排程环境与专属启动身份不一致。", 403)
    configured = _runtime_setting("PCE_FORMAL_SCHEDULING_DATABASE")
    current = str(connection.settings_dict.get("NAME", ""))
    declared = os.environ.get("PCE_DATABASE_PATH", "")
    if (not isinstance(configured, (str, Path)) or not str(configured) or current.startswith("file:")
            or not Path(configured).is_absolute() or not Path(current).is_absolute()
            or not declared or not Path(declared).is_absolute()
            or Path(current).resolve() != Path(configured).resolve()
            or Path(declared).resolve() != Path(configured).resolve()):
        _fail("FORMAL_SCHEDULING_DATABASE_BINDING_REQUIRED", "正式排程必须绑定当前环境的准确绝对数据库路径。", 403)
    if connection.vendor != "sqlite":
        _fail("FORMAL_SCHEDULING_DATABASE_UNSUPPORTED", "当前正式排程仅开放已验证的受控SQLite事务。", 403)
    if environment == "DAILY":
        # Reuse the existing approved Daily registry and its original guard;
        # declaring a Daily profile against a disposable copy is not enough.
        from pde.acceptance_isolation import verify_acceptance_connections
        try:
            verify_acceptance_connections(settings.DATABASES)
        except ValueError:
            _fail("FORMAL_SCHEDULING_RUNTIME_IDENTITY_MISMATCH", "日常排程数据库未通过既有受控日常环境核验。", 403)
    with connection.cursor() as cursor:
        actual = next((row[2] for row in cursor.execute("PRAGMA database_list").fetchall() if row[1] == "main"), "")
    if not actual or Path(actual).resolve() != Path(configured).resolve():
        _fail("FORMAL_SCHEDULING_DATABASE_IDENTITY_MISMATCH", "实际数据库连接与正式排程绑定路径不一致。", 403)
    return _runtime_scope()

def _plan(user, production_plan_id):
    scope = _execution_boundary()
    actor = _plan_start_actor(user)
    if type(production_plan_id) is not int or production_plan_id <= 0:
        _fail("PRODUCTION_PLAN_NOT_FOUND", "必须选择本公司正式生产计划。", 404)
    plan = _plan_start_rows(actor).filter(pk=production_plan_id).first()
    if plan is None:
        _fail("PRODUCTION_PLAN_NOT_FOUND", "生产计划不存在或不在当前公司范围。", 404)
    _require_plan_start_permission(_plan_start_decision(actor, plan, "planning.view"))
    if scope is not None:
        from system.models import Company
        company_code = Company.objects.filter(pk=actor.company_id).values_list("code", flat=True).first()
        if scope != {"companyId": actor.company_id, "productionPlanId": plan.pk,
                     "companyCode": company_code, "productionPlanNo": plan.plan_no}:
            _fail("FORMAL_SCHEDULING_SCOPE_NOT_ENABLED", "当前正式排程未开放本公司本计划范围。", 403)
    return actor, plan

class _PlanFacts:
    def __init__(self, plan, actor, schedule=None):
        self.plan, self.actor, self.schedule = plan, actor, schedule

    def read(self, module_code, object_ids):
        expected = self.schedule.pk if self.schedule is not None else self.plan.pk
        valid = module_code == MODULE and object_ids == [str(expected)]
        return {"found": valid, "objectIds": [str(expected)] if valid else [],
            "statuses": [self.schedule.status if self.schedule is not None else self.plan.status] if valid else [],
            "legalEntityIds": [str(self.actor.company_id)] if valid else [],
            "currentStateSource": "server", "reason": "" if valid else "object_scope_mismatch"}

class _PlanPermissions:
    def __init__(self, actor, plan, permission):
        self.actor, self.plan, self.permission = actor, plan, permission

    def read(self, user, legal_entity_id):
        decision = _plan_start_decision(self.actor, self.plan, self.permission)
        return {"provider": "system.AuthorizationService", "repository": decision["authoritySource"],
            "legalEntityId": str(legal_entity_id), "roleCodes": decision["roleCodes"] if decision["allowed"] else [],
            "permissionCodes": [self.permission] if decision["allowed"] else [], "serverDerived": True}

def _decision(actor, plan, action, schedule=None):
    native = _plan_start_decision(actor, plan, PERMISSIONS[action])
    target = schedule.pk if schedule is not None else plan.pk
    engine = ActionPermissionValidator(
        fact_provider=_PlanFacts(plan, actor, schedule),
        permission_provider=_PlanPermissions(actor, plan, PERMISSIONS[action]),
    ).evaluate(user=actor, module_code=MODULE, action_code=action,
        object_ids=[target], selection_count=1, requested_legal_entity_id=str(actor.company_id))
    return {"allowed": bool(native["allowed"] and engine["granted"]),
            "nativeDecision": native, "actionPermissionDecision": engine,
            "reason": native["reason"] if not native["allowed"] else engine.get("reason", ""),
            "actionCode": action, "requiredPermission": PERMISSIONS[action]}

def _require(decision):
    if not decision["allowed"]:
        _fail("FORMAL_SCHEDULING_PERMISSION_DENIED", decision["reason"] or "没有当前正式排程动作权限。", 403)

def _writer_lock(actor):
    # This is an actual UPDATE as the first transaction query: SQLite obtains
    # its cross-process writer lock before any source or reservation is read.
    if not Mutex.objects.filter(company_id=actor.company_id).update(revision=models.F("revision") + 1):
        Mutex.objects.create(company_id=actor.company_id, revision=1)

def _text(value, name, limit=300):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        _fail("FORMAL_SCHEDULING_INPUT_INVALID", f"{name}必须为1至{limit}个字符。", 400)
    return value.strip()

def _payload(payload, keys):
    if not isinstance(payload, dict) or set(payload) != set(keys):
        _fail("FORMAL_SCHEDULING_FIELDS_INVALID", "提交字段不符合本次明确业务动作合同。", 400)
    return _text(payload["reason"], "操作原因"), _text(payload["idempotencyKey"], "幂等标识", 120)

def _db_instant(value):
    """Only these new scheduling interval fields use UTC storage semantics.

    Legacy USE_TZ=False remains untouched. SQLite then stores UTC without a
    timezone marker; every read of these interval fields reattaches UTC.
    """
    value = value.astimezone(datetime_timezone.utc)
    return value if settings.USE_TZ else value.replace(tzinfo=None)

def _label(value, zone):
    from pde.formal_plan_date_preview_service import _display_datetime
    return _display_datetime(_read_instant(value).isoformat() if isinstance(value, datetime) else value, zone)

def _grant_state(row):
    return {"contractVersion": GRANT_CONTRACT, "companyId": row.company_id,
        "productionPlanId": row.production_plan_id, "standardCapacityId": row.standard_capacity_id,
        "exactScope": row.exact_scope, "referenceHash": row.reference_hash,
        "effectiveFrom": row.effective_from.isoformat(), "effectiveTo": row.effective_to.isoformat() if row.effective_to else None,
        "instructionReference": row.instruction_reference, "payload": row.payload,
        "createdById": row.created_by_id}

def _verify_grant(row, reference, consumed_days):
    state = _grant_state(row)
    if row.content_hash != _hash(state) or row.exact_scope != reference["exactScope"] or row.reference_hash != reference["referenceHash"]:
        _fail("SCHEDULE_CAPACITY_SCOPE_PROOF_INVALID", "精确用途依据的范围、原消费Hash或保存内容已变化。")
    if row.payload != {"consumer": "FORMAL_SCHEDULE_PROCESSING", "grantsScheduling": True,
            "grantsResourceOccupation": True, "phaseScope": "PROCESSING_ONLY", "priorReference": reference}:
        _fail("SCHEDULE_CAPACITY_SCOPE_PROOF_INVALID", "用途依据没有保留本次完整原消费证明或精确加工范围。")
    if any(day < row.effective_from or row.effective_to and day > row.effective_to for day in consumed_days):
        return False
    audits = list(OrganizationOperatingAuditRecord.objects.filter(organization_id=row.company_id,
        target_type=GRANT_OBJECT, target_id=row.pk, action_code="planning.schedule.capacity_scope.authorize"))
    if (len(audits) != 1 or audits[0].actor_id != row.created_by_id
            or {key: value for key, value in audits[0].after_snapshot.get("state", {}).items()
                if key != "actionPermissionDecision"} != {**state, "contentHash": row.content_hash}
            or audits[0].before_snapshot.get("state") != {}):
        _fail("SCHEDULE_CAPACITY_SCOPE_PROOF_INVALID", "精确用途依据缺少同对象、同操作人的原生提交审计。")
    _verify_action_audit(audits[0], "authorize-capacity-scope")
    return True

def authorize_capacity_scope(*, user, production_plan_id, payload):
    actor, plan = _plan(user, production_plan_id)
    decision = _decision(actor, plan, "authorize-capacity-scope")
    _require(decision)
    keys = ("exactScope", "referenceHash", "effectiveFrom", "effectiveTo", "instructionReference", "reason", "idempotencyKey")
    reason, idem = _payload(payload, keys)
    instruction = _text(payload["instructionReference"], "指令依据", 500)
    start = _parse_plan_start_date(payload["effectiveFrom"])
    end = _parse_plan_start_date(payload["effectiveTo"], allow_none=True)
    if plan.planned_start_date is None or start > plan.planned_start_date or end and end < plan.planned_start_date:
        _fail("SCHEDULE_CAPACITY_SCOPE_PERIOD_INVALID", "用途依据效期必须覆盖服务器已保存的计划开始日期。")
    request_hash = _hash(payload)
    with transaction.atomic():
        _writer_lock(actor)
        actor, plan = _plan(actor, production_plan_id)
        decision = _decision(actor, plan, "authorize-capacity-scope")
        _require(decision)
        if plan.planned_start_date is None or start > plan.planned_start_date or end and end < plan.planned_start_date:
            _fail("SCHEDULE_CAPACITY_SCOPE_PERIOD_INVALID", "用途依据效期不再覆盖当前服务器计划开始日期。")
        from pde.operation_input_preparation_service import resolve_capacity_consumption_reference
        reference = resolve_capacity_consumption_reference(user=actor, exact_scope=payload["exactScope"], on_date=plan.planned_start_date)
        if (reference is None or reference["exactScope"]["productionPlanId"] != plan.pk
                or reference["referenceHash"] != payload["referenceHash"]):
            _fail("SCHEDULE_CAPACITY_SCOPE_SOURCE_CHANGED", "用途依据必须引用当前计划有效步骤的原生精确消费证明。")
        if start < date.fromisoformat(reference["effectiveFrom"]) or reference["effectiveTo"] and (end is None or end > date.fromisoformat(reference["effectiveTo"])):
            _fail("SCHEDULE_CAPACITY_SCOPE_PERIOD_INVALID", "正式用途效期不得超出原消费证明有效期间。")
        previous = Grant.objects.filter(company_id=actor.company_id, idempotency_key=idem).first()
        if previous is not None:
            if previous.production_plan_id != plan.pk or previous.request_hash != request_hash:
                _fail("FORMAL_SCHEDULING_IDEMPOTENCY_CONFLICT", "幂等标识已用于不同用途授权内容。")
            _verify_grant(previous, reference, [plan.planned_start_date])
            return read_formal_scheduling(user=actor, production_plan_id=plan.pk), {"idempotent": True, "auditWriteCount": 0, "capacityGrantCreatedCount": 0}
        row = Grant(company_id=actor.company_id, production_plan=plan,
            standard_capacity_id=reference["capacityReference"]["standardCapacityId"], exact_scope=deepcopy(reference["exactScope"]),
            reference_hash=reference["referenceHash"], effective_from=start, effective_to=end,
            instruction_reference=instruction, payload={"consumer": "FORMAL_SCHEDULE_PROCESSING", "grantsScheduling": True,
                "grantsResourceOccupation": True, "phaseScope": "PROCESSING_ONLY", "priorReference": deepcopy(reference)},
            created_by=actor, idempotency_key=idem, request_hash=request_hash)
        row.content_hash = _hash(_grant_state(row))
        row.save(force_insert=True)
        record_audit(user=actor, action_code="planning.schedule.capacity_scope.authorize", target=row,
            target_type=GRANT_OBJECT, target_no=plan.plan_no, before={},
            after={**_grant_state(row), "contentHash": row.content_hash,
                "actionPermissionDecision": decision["actionPermissionDecision"]}, authorization=decision["nativeDecision"], reason=reason)
        _verify_grant(row, reference, [plan.planned_start_date])
        return read_formal_scheduling(user=actor, production_plan_id=plan.pk), {"idempotent": False, "auditWriteCount": 1, "capacityGrantCreatedCount": 1}

def _preview(plan, actor):
    from pde.formal_plan_date_preview_service import formal_plan_date_preview
    from pde.manufacturing_time_policy_service import resolve_scope
    from pde.daily_capacity_service import DailyCapacityReadinessService
    if plan.planned_start_date is None:
        _fail("SCHEDULE_SAVED_START_DATE_REQUIRED", "正式排程必须先保存计划开始日期。")
    # The confirmed formal shared arrangement is the timezone authority, rather
    # than a client date-preview parameter or a hard-coded business timezone.
    readiness, _ = DailyCapacityReadinessService.assess_plan_date_scope(
        plan, company_id=actor.company_id, on_date=plan.planned_start_date, user=actor)
    centers = sorted({fact["workCenterId"] for step in readiness["steps"]
        if step["applicability"]["result"] == "REQUIRED"
        and step.get("capacityDateMode") != "AUXILIARY_NO_INDEPENDENT_DATE"
        for fact in step.get("dailyCapacity", [])
        if fact.get("quantity") is not None and Decimal(fact["quantity"]) > 0})
    zones = set()
    from pde.manufacturing_time_policy_service import read_revision
    for center in centers:
        application = resolve_scope(user=actor, kind="WC_APPLICATION", on_date=plan.planned_start_date, work_center_id=center)["row"]
        shared = read_revision(user=actor, policy_id=application["sharedVersionId"])["row"]
        zones.add(shared["payload"]["timezone"])
    if len(zones) != 1:
        _fail("SCHEDULE_RESOURCE_TIMEZONE_AMBIGUOUS", "路线有效工作制度未给出唯一业务时区。")
    return formal_plan_date_preview(plan, user=actor, start_date=plan.planned_start_date, timezone=next(iter(zones)))

def _segments(preview, company_id):
    from pde.manufacturing_time_calculation import _minutes
    rows = []
    for step in preview["dates"]:
        for phase in step.get("phases", []):
            if phase["phase"] != "processing":
                if phase.get("occupancy") not in {"WORK_TIME_ONLY", "WAIT_ONLY"}:
                    _fail("SCHEDULE_PHASE_RESOURCE_RULE_UNSUPPORTED", "当前正式保存仅开放加工资源占用；其他资源阶段须另有正式实现。")
                continue
            if phase["occupancy"] != "WORK_CENTER" or not step.get("workCenterId"):
                _fail("SCHEDULE_PROCESSING_RESOURCE_REQUIRED", "加工阶段缺少正式工作中心资源规则。")
            for allocation in phase["allocations"]:
                begin, end = _instant(allocation["start"]), _instant(allocation["end"])
                if begin >= end:
                    _fail("SCHEDULE_PROCESSING_SEGMENT_INVALID", "正式加工占用分段必须具有正时间长度。")
                rows.append({"companyId": company_id, "stepId": step["rootStepId"], "sequence": step["sequence"],
                    "workCenterId": step["workCenterId"], "start": begin.isoformat(), "end": end.isoformat(),
                    "productionDate": allocation["productionDate"], "minutes": str(_minutes(begin, end)),
                    "stepLabel": step["operationName"]})
    return rows

def _assess(actor, plan):
    # Formal admission includes the caller's execution qualification. A reader
    # may inspect saved history without receiving a save-ready admission token.
    _require(_decision(actor, plan, "commit"))
    preview = _preview(plan, actor)
    blockers = deepcopy(preview.get("blockers", []))
    result = {"ready": False, "statusLabel": "正式排程准入受阻", "admissionToken": None,
        "blockers": blockers, "scopeGrantRequests": [], "conflicts": [], "stepCount": len(preview.get("dates", [])),
        "processingSegmentCount": 0, "preview": preview, "segments": [], "scopeProofs": [], "resourceSnapshot": []}
    result.update(previewStart=preview.get("start"), previewEnd=preview.get("end"),
        startLabel=preview["displayLabels"]["startLabel"], endLabel=preview["displayLabels"]["endLabel"])
    if not preview.get("previewReady"):
        return result
    from pde.models import WorkCenter
    from pde.manufacturing_time_policy_service import physical_hash
    segments = _segments(preview, actor.company_id)
    center_ids = sorted({row["workCenterId"] for row in segments})
    centers = list(WorkCenter.objects.filter(pk__in=center_ids, company_id=actor.company_id).order_by("pk"))
    if len(centers) != len(center_ids) or any(not row.is_active for row in centers):
        _fail("SCHEDULE_RESOURCE_CHANGED", "加工工作中心已停用、改变公司或不存在。")
    resources = [{"id": row.pk, "label": f"{row.code}／{row.name}", "physicalHash": physical_hash(row)} for row in centers]
    center_labels = {row["id"]: row["label"] for row in resources}
    for row in segments:
        row.update(workCenterLabel=center_labels[row["workCenterId"]], startLabel=_label(row["start"], preview["timezone"]),
            endLabel=_label(row["end"], preview["timezone"]), minutesLabel=f"{Decimal(row['minutes']).normalize():f}分钟",
            primaryLabel=f"{row['stepLabel']}加工分段", statusLabel="待保存加工占用")
    for step in preview["dates"]:
        reference = step.get("capacityConsumptionReference")
        if reference is None:
            continue
        days = sorted({date.fromisoformat(part["productionDate"]) for phase in step["phases"] for part in phase["allocations"]})
        matched = None
        for grant in Grant.objects.filter(company_id=actor.company_id, production_plan=plan,
                standard_capacity_id=step["standardCapacityId"], reference_hash=reference["referenceHash"]).order_by("pk"):
            if grant.exact_scope == reference["exactScope"] and _verify_grant(grant, reference, days):
                matched = grant
                break
        if matched is None:
            request = {"exactScope": deepcopy(reference["exactScope"]), "referenceHash": reference["referenceHash"],
                "effectiveFrom": plan.planned_start_date.isoformat(), "effectiveTo": reference["effectiveTo"],
                "standardCapacityId": step["standardCapacityId"], "stepLabel": step["operationName"],
                "statusLabel": "缺少本计划本步骤正式排程及加工占用用途依据",
                "scopeLabel": f"{plan.plan_no}／{step['operationName']}／产能{step['standardCapacityId']}",
                "effectiveFromLabel": plan.planned_start_date.strftime("%Y年%m月%d日"),
                "effectiveToLabel": reference["effectiveTo"] or "未设截止日期",
                "referenceLabel": "本次核验有效的原精确消费证明"}
            result["scopeGrantRequests"].append(request)
            blockers.append({"code": "SCHEDULE_CAPACITY_SCOPE_REQUIRED", "statusLabel": request["statusLabel"], "stepId": step["rootStepId"]})
            break  # The first real scope blocker is sufficient; do not survey onward.
        result["scopeProofs"].append({"id": matched.pk, "contentHash": matched.content_hash})
    active = _active_reservations(actor)
    for current in active:
        if current.schedule.status != "saved":
            _fail("SCHEDULE_RESERVATION_STATE_INVALID", "有效占用与正式排程状态不一致。")
    if not blockers:
        for candidate in segments:
            for existing in active:
                if (candidate["workCenterId"] == existing.work_center_id
                        and _instant(candidate["start"]) < _read_instant(existing.end_at) and _instant(candidate["end"]) > _read_instant(existing.start_at)):
                    existing_fact = _reservation_state(existing)
                    existing_fact.update(startLabel=_label(existing.start_at, preview["timezone"]),
                        endLabel=_label(existing.end_at, preview["timezone"]),
                        primaryLabel=f"已保存正式排程版本{existing.schedule.revision}加工占用")
                    result["conflicts"].append({"candidate": candidate, "existing": existing_fact,
                        "statusLabel": f"{candidate['workCenterLabel']}：本次{candidate['startLabel']}至{candidate['endLabel']}，"
                            f"与已保存版本{existing.schedule.revision}的{existing_fact['startLabel']}至{existing_fact['endLabel']}重叠"})
                    blockers.append({"code": "SCHEDULE_RESOURCE_CONFLICT", "statusLabel": "加工分段与已保存正式资源占用重叠",
                        "stepId": candidate["stepId"], "workCenterId": candidate["workCenterId"]})
                    break
            if blockers:
                break
    if Schedule.objects.filter(company_id=actor.company_id, production_plan=plan, status="saved").exists() and not blockers:
        blockers.append({"code": "SCHEDULE_ACTIVE_VERSION_EXISTS", "statusLabel": "本计划已有有效正式排程，须先撤销再建立新版本"})
    stable_preview = deepcopy(preview)
    for key in ("assessedAt", "resultHash"):
        stable_preview.pop(key, None)
    state = {"companyId": actor.company_id, "productionPlanId": plan.pk,
        "savedStartDate": plan.planned_start_date.isoformat(), "requiredDate": plan.required_date.isoformat(),
        "planCoreUpdatedAt": plan.updated_at.isoformat(), "planStatus": plan.status,
        "preview": stable_preview, "resources": resources, "scopeProofs": result["scopeProofs"],
        "activeReservations": [_reservation_state(row) for row in active]}
    result.update(ready=not blockers, statusLabel="正式排程准入通过，尚未保存" if not blockers else "正式排程准入受阻",
        admissionToken=_hash(state) if not blockers else None, segments=segments,
        processingSegmentCount=len(segments), resourceSnapshot=resources)
    return result

def _present_schedule(row):
    from pde.manufacturing_time_zone_catalog import display_timezone_label
    transitions, reservations = _verify_schedule(row)
    steps = deepcopy(row.snapshot["preview"]["dates"])
    for step in steps:
        step.update(stepLabel=step["operationName"], **step["displayLabels"])
    occupancy = []
    for saved, segment in zip(reservations, row.snapshot["segments"]):
        occupancy.append({**deepcopy(segment), "id": saved.pk, "scheduleId": row.pk,
            "statusLabel": "有效加工占用" if saved.released_at is None else "已释放加工占用",
            "releasedAt": _read_instant(saved.released_at).isoformat() if saved.released_at else None})
    audits = [{"id": audit.pk, "actorId": audit.actor_id, "actionCode": audit.action_code,
        "reason": audit.reason, "createdAt": audit.created_at.isoformat()} for audit in
        OrganizationOperatingAuditRecord.objects.filter(organization_id=row.company_id, target_type=OBJECT,
            target_id=row.pk).order_by("pk")]
    return {"id": row.pk, "productionPlanId": row.production_plan_id, "revision": row.revision,
        "version": row.version, "statusCode": row.status, "statusLabel": row.get_status_display(),
        "start": row.snapshot["preview"]["start"], "end": row.snapshot["preview"]["end"],
        "startLabel": _label(row.start_at, row.timezone), "endLabel": _label(row.end_at, row.timezone),
        "timezone": row.timezone, "timezoneLabel": display_timezone_label(row.timezone),
        "savedStartDate": row.saved_start_date.isoformat(), "snapshotHash": row.snapshot_hash,
        "stepCount": len(steps), "processingSegmentCount": len(occupancy), "steps": steps, "reservations": occupancy,
        "activeReservationCount": sum(item.released_at is None for item in reservations), "auditHistory": audits,
        "stateTransitionHistory": [{"id": item.pk, "sourceState": item.source_state, "targetState": item.target_state,
            "version": item.version, "operatorId": item.operator_id, "auditReference": item.audit_reference,
            "actionCode": item.action_code, "timestamp": item.timestamp.isoformat()} for item in transitions],
        "statusTransitionCount": len(transitions), "stateMachineConsistent": True}

def _with_action_availability(facts):
    """Explain existing server decisions; never decide or change availability.

    A base read has no admission. In particular, an empty scope-request list
    on that read is not evidence that scope assessment has completed.
    """
    admission = facts["admission"]
    active = facts["activeSchedule"]
    for action in facts["availableActions"]:
        name = action["actionCode"]
        decision = facts["actionAuthorization"]["decisions"].get(name)
        if decision is not None and not decision["allowed"]:
            native = decision["nativeDecision"]
            engine = decision["actionPermissionDecision"]
            if not native["allowed"]:
                code = "permission_denied" if native["decisionCode"] == "PERMISSION_DENIED" else "authorization_denied"
            elif engine["decisionCode"] == "business_state_denied":
                code = "business_state_denied"
            else:
                code = "permission_denied" if engine["decisionCode"] in {"role_denied", "permission_denied"} else "authorization_denied"
            label = decision["reason"]
            if name == "cancel" and active is None and code == "business_state_denied":
                label = f"当前没有可撤销的有效正式排程；{label}"
        elif name == "validate":
            code, label = "available", "可执行只读的正式准入与冲突检查；不会保存排程或资源占用。"
        elif action["enabled"]:
            code = "available"
            if name == "cancel":
                label = f"可撤销当前有效正式排程修订{active['revision']}，并释放该版本对应的加工占用。"
            elif name == "commit":
                label = "本次正式准入已通过，可保存正式排程及加工分段占用。"
            else:
                label = "本次存在待确认的精确用途范围，可按所列范围确认用途依据。"
        elif name == "commit":
            if admission is not None:
                code, label = "admission_blocked", "本次正式准入未通过，当前不能保存；请查看本次准入与冲突检查结果。"
            elif active is not None:
                code = "active_schedule_exists"
                label = f"已有有效正式排程修订{active['revision']}；本次尚未执行正式准入，不能重复保存。"
            else:
                code, label = "admission_not_assessed", "本次尚未执行正式准入与冲突检查，当前不能保存。"
        elif name == "authorize-capacity-scope":
            if admission is None:
                code, label = "scope_not_assessed", "本次尚未执行正式准入，待确认的精确用途范围尚未评估。"
            elif admission.get("preview", {}).get("previewReady") is True:
                code, label = "no_scope_confirmation_required", "本次已评估，没有待确认的精确用途范围，无需重复确认。"
            else:
                code, label = "scope_assessment_incomplete", "本次正式准入未完成，待确认的精确用途范围尚未确定。"
        else:
            code, label = "no_active_schedule", "当前没有可撤销的有效正式排程。"
        action.update(availabilityCode=code, availabilityLabel=label)
    return facts

def read_formal_scheduling(*, user, production_plan_id):
    actor, plan = _plan(user, production_plan_id)
    history = [_present_schedule(row) for row in Schedule.objects.filter(company_id=actor.company_id,
        production_plan=plan).order_by("revision", "pk")]
    active = next((row for row in history if row["statusCode"] == "saved"), None)
    native_active = Schedule.objects.filter(pk=active["id"]).first() if active else None
    decisions = {key: _decision(actor, plan, key, native_active if key == "cancel" else None)
        for key in PERMISSIONS}
    actions = []
    for name in ("authorize-capacity-scope", "commit", "cancel"):
        policy = POLICIES[(MODULE, name)].serialize()
        actions.append({**policy, "displayName": LABELS[name], "enabled": bool(name == "cancel" and active and decisions[name]["allowed"])})
    actions.insert(0, {"actionCode": "validate", "moduleCode": MODULE, "displayName": LABELS["validate"],
        "requiredPermission": "planning.view", "role": [], "organizationScope": "legal_entity",
        "serverValidator": "planning.formal_scheduling_service.assess_formal_scheduling", "enabled": True,
        "allowedStatuses": ["confirmed"], "scope": "single"})
    return _with_action_availability({"contractVersion": CONTRACT, "factSource": "server", "currentStateSource": "server",
        "companyId": actor.company_id, "productionPlanId": plan.pk, "productionPlanNo": plan.plan_no,
        "savedStartDate": plan.planned_start_date.isoformat() if plan.planned_start_date else None,
        "savedStartDateLabel": plan.planned_start_date.strftime("%Y年%m月%d日") if plan.planned_start_date else "未维护",
        "requiredDate": plan.required_date.isoformat(), "requiredDateLabel": plan.required_date.strftime("%Y年%m月%d日"),
        "timezoneLabel": active["timezoneLabel"] if active else "尚未取得正式时区",
        "statusLabel": active["statusLabel"] if active else "尚无有效正式排程",
        "modeLabel": ENVIRONMENT_LABELS[_runtime_environment() or "ISOLATED"], "actionAuthorization": {"canRead": True, "canValidate": True,
            "canCommit": decisions["commit"]["allowed"], "canCancel": bool(active and decisions["cancel"]["allowed"]),
            "canAuthorizeScope": decisions["authorize-capacity-scope"]["allowed"], "decisions": decisions,
            "reason": "" if decisions["commit"]["allowed"] else decisions["commit"]["reason"]},
        "availableActions": actions, "admission": None, "activeSchedule": active, "history": history, "scopeGrantRequests": [],
        "scheduleCount": len(history), "activeReservationCount": active["activeReservationCount"] if active else 0,
        "businessWriteCount": 0, "auditWriteCount": 0})

def assess_formal_scheduling(*, user, production_plan_id):
    actor, plan = _plan(user, production_plan_id)
    facts = read_formal_scheduling(user=actor, production_plan_id=plan.pk)
    try:
        facts["admission"] = _assess(actor, plan)
    except Exception as error:
        if isinstance(error, PlanningBusinessError) or hasattr(error, "code"):
            facts["admission"] = {"ready": False, "statusLabel": "正式排程准入受阻", "admissionToken": None,
                "blockers": [{"code": error.code, "statusLabel": getattr(error, "message", str(error))}],
                "scopeGrantRequests": [], "conflicts": [], "stepCount": None, "processingSegmentCount": None}
        else:
            raise
    facts["scopeGrantRequests"] = deepcopy(facts["admission"]["scopeGrantRequests"])
    admission = facts["admission"]
    admission.setdefault("startLabel", "尚未生成")
    admission.setdefault("endLabel", "尚未生成")
    if admission.get("preview"):
        facts["timezoneLabel"] = admission["preview"]["displayLabels"]["timezoneLabel"]
    for action in facts["availableActions"]:
        if action["actionCode"] == "commit":
            action["enabled"] = bool(admission["ready"] and facts["actionAuthorization"]["canCommit"])
        if action["actionCode"] == "authorize-capacity-scope":
            action["enabled"] = bool(facts["scopeGrantRequests"] and facts["actionAuthorization"]["canAuthorizeScope"])
    return _with_action_availability(facts)

def _audit(actor, plan, row, action, before, after, decision, reason):
    return record_audit(user=actor, action_code=action, target=row, target_type=OBJECT,
        target_no=f"{plan.plan_no}/排程版本{row.revision}", before=before,
        after={**after, "actionPermissionDecision": decision["actionPermissionDecision"]},
        authorization=decision["nativeDecision"], reason=reason)

def commit_formal_schedule(*, user, production_plan_id, payload):
    actor, plan = _plan(user, production_plan_id)
    _require(_decision(actor, plan, "commit"))
    reason, idem = _payload(payload, ("admissionToken", "idempotencyKey", "reason"))
    if not isinstance(payload["admissionToken"], str) or not re.fullmatch("[0-9a-f]{64}", payload["admissionToken"]):
        _fail("SCHEDULE_ADMISSION_TOKEN_REQUIRED", "保存必须引用本次正式准入凭据。", 400)
    request_hash = _hash(payload)
    with transaction.atomic():
        _writer_lock(actor)
        actor, plan = _plan(actor, production_plan_id)
        decision = _decision(actor, plan, "commit")
        _require(decision)
        previous = Schedule.objects.filter(company_id=actor.company_id, idempotency_key=idem).first()
        if previous is not None:
            if previous.production_plan_id != plan.pk or previous.request_hash != request_hash:
                _fail("FORMAL_SCHEDULING_IDEMPOTENCY_CONFLICT", "幂等标识已用于不同正式保存内容。")
            _verify_schedule(previous)
            return read_formal_scheduling(user=actor, production_plan_id=plan.pk), {"idempotent": True, "auditWriteCount": 0, "productionScheduleCreatedCount": 0, "resourceOccupancyCreatedCount": 0}
        admission = _assess(actor, plan)
        if not admission["ready"]:
            _fail("SCHEDULE_ADMISSION_BLOCKED", "当前正式排程准入未通过，未保存任何占用。", data=admission)
        if admission["admissionToken"] != payload["admissionToken"]:
            _fail("SCHEDULE_ADMISSION_CHANGED", "来源、日期、资源或占用已变化，请重新准入。")
        frozen = {key: deepcopy(admission[key]) for key in ("preview", "segments", "scopeProofs", "resourceSnapshot")}
        revision = (Schedule.objects.filter(production_plan=plan).aggregate(value=models.Max("revision"))["value"] or 0) + 1
        preview = admission["preview"]
        row = create_business_object_with_initial_state(model=Schedule, initial_state="draft",
            company_id=actor.company_id, production_plan=plan, usage_purpose='PRODUCTION_USE', revision=revision, version=0,            start_at=_db_instant(_instant(preview["start"])), end_at=_db_instant(_instant(preview["end"])), saved_start_date=plan.planned_start_date,
            timezone=preview["timezone"], snapshot=_json(frozen), snapshot_hash=_hash(frozen),
            admission_token=admission["admissionToken"], idempotency_key=idem, request_hash=request_hash, created_by=actor)
        initial = _audit(actor, plan, row, "planning.schedule.initialize", {},
            {"status": "draft", "snapshotHash": row.snapshot_hash}, decision, reason)
        record_projected_business_transition(object_type=OBJECT, object_id=row.pk, source_state="", target_state="draft",
            action_code=initial.action_code, operator=actor, reason=reason,
            audit_reference=f"OrganizationOperatingAuditRecord:{initial.pk}", allowed_transitions=(("", "draft"),))
        for segment in admission["segments"]:
            Reservation.objects.create(schedule=row, company_id=actor.company_id, work_center_id=segment["workCenterId"],
                routing_step_id=segment["stepId"], sequence=segment["sequence"], start_at=_db_instant(_instant(segment["start"])),
                end_at=_db_instant(_instant(segment["end"])), production_date=date.fromisoformat(segment["productionDate"]), minutes=segment["minutes"])
        audit = _audit(actor, plan, row, "planning.schedule.commit", {"status": "draft", "snapshotHash": row.snapshot_hash},
            {"status": "saved", "snapshotHash": row.snapshot_hash, "processingReservationCount": len(admission["segments"])}, decision, reason)
        transition_business_object(business_object=row, object_type=OBJECT, source_state="draft", target_state="saved",
            action_code=audit.action_code, operator=actor, reason=reason,
            audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}", allowed_transitions=(("draft", "saved"),))
        _verify_schedule(row)
        return read_formal_scheduling(user=actor, production_plan_id=plan.pk), {"idempotent": False,
            "auditWriteCount": 2, "productionScheduleCreatedCount": 1, "resourceOccupancyCreatedCount": len(admission["segments"])}

def cancel_formal_schedule(*, user, production_plan_id, schedule_id, payload):
    actor, plan = _plan(user, production_plan_id)
    reason, idem = _payload(payload, ("expectedVersion", "idempotencyKey", "reason"))
    if type(payload["expectedVersion"]) is not int:
        _fail("SCHEDULE_VERSION_REQUIRED", "撤销必须引用已回读的正式版本。", 400)
    request_hash = _hash(payload)
    with transaction.atomic():
        _writer_lock(actor)
        actor, plan = _plan(actor, production_plan_id)
        row = Schedule.objects.filter(pk=schedule_id, company_id=actor.company_id, production_plan=plan).first()
        if row is None:
            _fail("FORMAL_SCHEDULE_NOT_FOUND", "正式排程不存在或超出当前计划范围。", 404)
        decision = _decision(actor, plan, "cancel", row)
        _require(decision)
        _verify_schedule(row)
        if row.status == "cancelled":
            if row.cancel_idempotency_key != idem or row.cancel_request_hash != request_hash:
                _fail("SCHEDULE_ALREADY_CANCELLED", "该正式版本已撤销，不能重复执行不同撤销。")
            return read_formal_scheduling(user=actor, production_plan_id=plan.pk), {"idempotent": True, "auditWriteCount": 0, "resourceOccupancyReleasedCount": 0}
        if row.version != payload["expectedVersion"]:
            _fail("SCHEDULE_VERSION_CHANGED", "正式排程版本已变化，请重新读取。")
        released = row.reservations.filter(released_at__isnull=True).update(released_at=_db_instant(datetime.now(datetime_timezone.utc)))
        audit = _audit(actor, plan, row, "planning.schedule.cancel", {"status": "saved", "snapshotHash": row.snapshot_hash},
            {"status": "cancelled", "snapshotHash": row.snapshot_hash, "processingReservationReleasedCount": released}, decision, reason)
        transition_business_object(business_object=row, object_type=OBJECT, source_state="saved", target_state="cancelled",
            action_code=audit.action_code, operator=actor, reason=reason,
            audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}", allowed_transitions=(("saved", "cancelled"),))
        Schedule.objects.filter(pk=row.pk).update(cancel_idempotency_key=idem, cancel_request_hash=request_hash)
        row.cancel_idempotency_key, row.cancel_request_hash = idem, request_hash
        _verify_schedule(row)
        return read_formal_scheduling(user=actor, production_plan_id=plan.pk), {"idempotent": False, "auditWriteCount": 1, "resourceOccupancyReleasedCount": released}
