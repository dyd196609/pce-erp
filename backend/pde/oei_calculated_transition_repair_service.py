"""Evidence-only repair of an observed OEI event on an explicitly pinned copy."""
from hashlib import sha256
import json
from pathlib import Path

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import record_projected_business_transition
from system.models import OrganizationOperatingAuditRecord
from .engineering_calculation_service import EngineeringCalculationError, EngineeringCalculationService
from .models import EngineeringCalculationRecord, OrderEngineeringInstance
from .production_foundation_service import _actor_chain, _audit, _snapshot

ACTION = "pde.order_engineering.calculated_transition.repair"
OBJECT = "OrderEngineeringInstance"


def calculated_state_facts(*, instance, company_id):
    """One persisted state/history projection for API, page and diagnostics."""
    if instance.company_id != company_id:
        _fail("OEI_STATE_FACT_SCOPE_MISMATCH", "状态事实对象不属于当前公司。")
    from workflow_runtime.facts import status_transition_facts
    history = list(BusinessStateTransition.objects.filter(object_type=OBJECT, object_id=instance.pk)
                   .order_by("version", "pk").values("id", "source_state", "target_state", "operator_id",
                       "action_code", "audit_reference", "version", "timestamp"))
    consistent = bool(history) and history[-1]["target_state"] == instance.status
    consistent = consistent and all(a["target_state"] == b["source_state"] for a, b in zip(history, history[1:]))
    if consistent and instance.status == "calculated":
        last = history[-1]
        prefix = "OrganizationOperatingAuditRecord:"
        audit = (OrganizationOperatingAuditRecord.objects.filter(pk=last["audit_reference"][len(prefix):]).first()
                 if last["audit_reference"].startswith(prefix) and last["audit_reference"][len(prefix):].isdigit() else None)
        consistent = bool(audit and audit.organization_id == company_id and audit.target_type == OBJECT
            and audit.target_id == instance.pk and audit.actor_id == last["operator_id"]
            and audit.before_snapshot.get("state", {}).get("status") == last["source_state"]
            and audit.after_snapshot.get("state", {}).get("status") == "calculated")
    facts = status_transition_facts(history=history, state_machine_consistent=consistent)
    return {**facts, "statusLabel": "状态记录一致" if consistent else "状态记录不完整或存在冲突",
            "factSource": "server", "businessWriteSideEffectCount": 0}


def _fail(code, message):
    raise EngineeringCalculationError(code, message)


def _hash(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _isolation(source_audit_id, calculation_id):
    pin = getattr(settings, "PCE_OEI_CALCULATED_TRANSITION_REPAIR", {})
    if not isinstance(pin, dict) or pin.get("enabled") is not True:
        _fail("OEI_REPAIR_COPY_PIN_REQUIRED", "修复只能在显式启用并固定物理身份的新验证副本运行。")
    name = connection.settings_dict["NAME"]
    path = Path(str(name)).resolve()
    if (str(name).startswith("file:") or str(path) != str(Path(pin.get("databasePath", "")).resolve())
            or not path.name.endswith("-acceptance.sqlite3")
            or connection.settings_dict["ENGINE"] != "django.db.backends.sqlite3"):
        _fail("OEI_REPAIR_COPY_PIN_MISMATCH", "修复数据库配置与固定验证副本不一致。")
    stat = path.stat()
    if ((stat.st_dev, stat.st_ino) != (pin.get("device"), pin.get("fileId"))
            or source_audit_id != pin.get("sourceAuditId") or calculation_id != pin.get("calculationId")):
        _fail("OEI_REPAIR_COPY_PIN_MISMATCH", "修复物理文件或授权事件不匹配。")
    return pin


def inspect_calculated_transition(*, user, source_audit_id, calculation_id):
    pin = _isolation(source_audit_id, calculation_id)
    EngineeringCalculationService._authorize(user=user, action_code="production.engineering.order.maintain", company_id=user.company_id)
    EngineeringCalculationService._authorize(user=user, action_code="production.engineering.calculation.view", company_id=user.company_id)
    audit = OrganizationOperatingAuditRecord.objects.filter(pk=source_audit_id).first()
    calculation = EngineeringCalculationRecord.objects.filter(pk=calculation_id).first()
    if not audit or not calculation:
        _fail("OEI_REPAIR_EVIDENCE_REQUIRED", "缺少原业务审计或精确核算记录。")
    instance = OrderEngineeringInstance.objects.filter(pk=audit.target_id).first()
    if not isinstance(audit.before_snapshot, dict) or not isinstance(audit.after_snapshot, dict):
        _fail("OEI_REPAIR_EVIDENCE_REQUIRED", "原审计快照格式不完整。")
    before = audit.before_snapshot.get("state", {})
    after = audit.after_snapshot.get("state", {})
    if not isinstance(before, dict) or not isinstance(after, dict):
        _fail("OEI_REPAIR_EVIDENCE_REQUIRED", "原事件状态快照格式不完整。")
    if (not instance or audit.target_type != OBJECT or audit.action_code != "production.engineering.order.maintain"
            or instance.company_id != user.company_id or audit.organization_id != user.company_id
            or calculation.company_id != user.company_id or pin.get("companyId") != user.company_id
            or pin.get("engineeringInstanceId") != instance.pk):
        _fail("OEI_REPAIR_SCOPE_MISMATCH", "原审计、对象、核算和修复人不属于授权公司与对象范围。")
    for snapshot in (audit.before_snapshot, audit.after_snapshot):
        authorization = snapshot.get("authorization", {})
        if (authorization.get("allowed") is not True
                or authorization.get("actionCode") != audit.action_code
                or str(authorization.get("organizationId")) != str(audit.organization_id)):
            _fail("OEI_REPAIR_ORIGINAL_AUTHORIZATION_UNPROVEN", "原事件审计未证明相同动作与公司的真实授权。")
    fixed = ("id", "company_id", "sales_order_item_id", "source_record_id", "instance_no")
    current = _snapshot(instance)
    if (before.get("status") != "source_confirmed" or after.get("status") != "calculated"
            or instance.status != "calculated" or any(before.get(k) != after.get(k) or after.get(k) != current.get(k) for k in fixed)
            or after.get("updated_at") != current.get("updated_at")):
        _fail("OEI_REPAIR_EVENT_CONFLICT", "原事件状态、对象身份或当前事件时间存在冲突。")
    if (calculation.engineering_instance_id != instance.pk or calculation.sales_order_item_id != instance.sales_order_item_id
            or calculation.source_record_id != instance.source_record_id or calculation.status != "completed"
            or not calculation.details.exists() or not calculation.derived_facts.exists()):
        _fail("OEI_REPAIR_CALCULATION_EVIDENCE_MISMATCH", "精确核算与OEI、来源或持久结果不一致。")
    calc_audits = list(OrganizationOperatingAuditRecord.objects.filter(
        target_type="EngineeringCalculationRecord", target_id=calculation.pk,
        action_code="production.engineering.calculation.execute", actor_id=audit.actor_id,
        organization_id=audit.organization_id, created_at__lte=audit.created_at))
    if len(calc_audits) != 1 or calculation.finished_at is None or calculation.finished_at > audit.created_at:
        _fail("OEI_REPAIR_EVENT_TIME_UNPROVEN", "不能唯一证明同一操作者的核算完成发生在原OEI转换之前。")
    calculation_after = calc_audits[0].after_snapshot.get("state", {})
    if (calculation_after.get("status") != "completed" or calculation_after.get("inputHash") != calculation.input_hash
            or calculation_after.get("resultHash") != calculation.result_hash):
        _fail("OEI_REPAIR_CALCULATION_EVIDENCE_MISMATCH", "核算完成审计与已提交输入或结果Hash不一致。")
    event_time = after.get("updated_at")
    if not event_time or not before.get("updated_at") or before["updated_at"] >= event_time:
        _fail("OEI_REPAIR_EVENT_TIME_UNPROVEN", "缺少可比较的原事件发生时间。")
    from datetime import datetime
    try:
        occurred = datetime.fromisoformat(event_time)
    except (ValueError, TypeError):
        _fail("OEI_REPAIR_EVENT_TIME_UNPROVEN", "原事件时间格式无效。")
    if not (calculation.finished_at <= occurred <= audit.created_at):
        _fail("OEI_REPAIR_EVENT_TIME_UNPROVEN", "原事件时间不位于核算完成与原审计之间。")
    reference = f"OrganizationOperatingAuditRecord:{audit.pk}"
    existing = BusinessStateTransition.objects.filter(audit_reference=reference).first()
    if existing and (existing.object_type != OBJECT or existing.object_id != instance.pk
            or existing.source_state != "source_confirmed" or existing.target_state != "calculated"
            or existing.operator_id != audit.actor_id or existing.action_code != audit.action_code):
        _fail("OEI_REPAIR_TRANSITION_CONFLICT", "原审计已被不一致的转换事实引用。")
    history = BusinessStateTransition.objects.filter(object_type=OBJECT, object_id=instance.pk).order_by("version", "pk")
    predecessors = list(history.exclude(pk=existing.pk) if existing else history)
    if not predecessors or predecessors[-1].target_state != "source_confirmed":
        _fail("OEI_REPAIR_HISTORY_CONFLICT", "当前转换链末态不能证明原事件的来源状态。")
    proof = {"companyId": instance.company_id, "objectType": OBJECT, "objectId": instance.pk,
        "sourceState": "source_confirmed", "targetState": "calculated", "sourceAuditId": audit.pk,
        "sourceAuditHash": _hash({"before": audit.before_snapshot, "after": audit.after_snapshot, "actor": audit.actor_id, "createdAt": audit.created_at}),
        "originalOperatorId": audit.actor_id, "originalEventAt": event_time,
        "originalAuditRecordedAt": audit.created_at.isoformat(), "timeZone": settings.TIME_ZONE,
        "calculationId": calculation.pk, "calculationNo": calculation.calculation_no,
        "calculationInputHash": calculation.input_hash, "calculationResultHash": calculation.result_hash,
        "calculationAuditId": calc_audits[0].pk, "previousTransitionId": predecessors[-1].pk,
        "previousTransitionVersion": predecessors[-1].version}
    return {"evidence": proof, "evidenceHash": _hash(proof), "existingTransitionId": existing.pk if existing else None}


@transaction.atomic
def repair_calculated_transition(*, user, source_audit_id, calculation_id, expected_evidence_hash, reason):
    if not str(reason or "").strip():
        _fail("OEI_REPAIR_REASON_REQUIRED", "受控补记必须说明依据与责任。")
    _isolation(source_audit_id, calculation_id)
    source = OrganizationOperatingAuditRecord.objects.select_for_update().filter(pk=source_audit_id).first()
    if source and source.target_type == OBJECT:
        OrderEngineeringInstance.objects.select_for_update().filter(pk=source.target_id).first()
    result = inspect_calculated_transition(user=user, source_audit_id=source_audit_id, calculation_id=calculation_id)
    if result["evidenceHash"] != expected_evidence_hash:
        _fail("OEI_REPAIR_EVIDENCE_CHANGED", "补记证据与冻结预算不一致。")
    proof = result["evidence"]
    existing_audit = OrganizationOperatingAuditRecord.objects.filter(action_code=ACTION, target_type=OBJECT,
        target_id=proof["objectId"], after_snapshot__state__repair__evidenceHash=expected_evidence_hash).first()
    if result["existingTransitionId"]:
        if not existing_audit:
            _fail("OEI_REPAIR_RECEIPT_MISSING", "转换事实已存在，但没有本机制的真实修复审计，禁止重复补记。")
        receipt = existing_audit.after_snapshot["state"]["repair"]
        return {"idempotent": True, "transitionId": result["existingTransitionId"],
                "repairAuditId": existing_audit.pk, "evidenceHash": expected_evidence_hash,
                "originalEventAt": receipt["originalEventAt"], "repairRecordedAt": receipt["repairRecordedAt"]}
    if existing_audit:
        _fail("OEI_REPAIR_RECEIPT_CONFLICT", "存在修复审计但转换事实缺失，需单独核定。")
    # Project the immutable, already-committed audit event; do not replay the
    # mutable OEI transition. timestamp is the repair time, not the old event.
    fact = record_projected_business_transition(object_type=OBJECT, object_id=proof["objectId"],
        source_state="source_confirmed", target_state="calculated", action_code=source.action_code,
        operator=source.actor, reason=f"受控历史补记；原事件{proof['originalEventAt']}；{reason}"[:240],
        audit_reference=f"OrganizationOperatingAuditRecord:{source.pk}",
        allowed_transitions={("source_confirmed", "calculated")})
    instance = OrderEngineeringInstance.objects.get(pk=proof["objectId"])
    decision = EngineeringCalculationService._authorize(user=user, action_code="production.engineering.order.maintain", company_id=user.company_id)
    repair_audit = _audit(user=user, organization_id=user.company_id, action_code=ACTION, instance=instance,
        before={"observedState": _snapshot(instance), "transitionAbsent": True},
        after={"repair": {**proof, "evidenceHash": expected_evidence_hash, "transitionId": fact.pk,
                          "repairRecordedAt": fact.timestamp.isoformat(), "repairOperatorId": user.pk},
               "observedState": _snapshot(instance)}, reason=reason, authorization=decision, execution_chain=_actor_chain(user))
    return {"idempotent": False, "transitionId": fact.pk, "repairAuditId": repair_audit.pk,
            "evidenceHash": expected_evidence_hash, "originalEventAt": proof["originalEventAt"],
            "repairRecordedAt": fact.timestamp.isoformat()}
