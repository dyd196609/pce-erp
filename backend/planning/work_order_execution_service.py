"""Original formal work-order proof kernel; no new formal writes exposed."""
import json,re
from decimal import Decimal
from hashlib import sha256
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition
from pde.order_routing_execution_service import fail as _failfrom .services import PlanningBusinessErrordef _fail(code,message,status=409):    raise PlanningBusinessError(code,message,http_status=status)
from .work_order_models import ProductionWorkOrder,ProductionWorkOrderOperation
from .work_order_release_admission_contract import ACTION,GENERATE_ACTION,PROCESS,WORKFLOW_NODE
OBJECT='ProductionWorkOrder'

def _hash(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def _verify(row):
    from .test_work_order_service import require_formal_work_order
    require_formal_work_order(row)
    source = row.source_snapshot
    if (_hash(source) != row.snapshot_hash or source["companyId"] != row.company_id
            or source["productionPlanId"] != row.production_plan_id or source["materialId"] != row.material_id
            or Decimal(source["quantity"]) != row.quantity or source["uomId"] != row.uom_id
            or source["sourceSchedule"]["id"] != row.source_schedule_id):
        _fail("WORK_ORDER_SNAPSHOT_INCONSISTENT", "工单冻结来源与持久化身份、数量或单位不一致。")
    operations = list(row.operations.order_by("sequence", "pk"))
    expected = source["operations"]
    if len(operations) != len(expected):
        _fail("WORK_ORDER_OPERATIONS_INCOMPLETE", "工单工序明细与冻结来源数量不一致。")
    for operation, previous in zip(operations, expected):
        if (operation.source_snapshot != previous or operation.snapshot_hash != _hash(previous)
                or operation.sequence != previous["sequence"] or operation.root_step_id != previous["rootStepId"]
                or operation.effective_step_id != previous["effectiveStepId"]
                or operation.root_routing_version_id != previous["rootRoutingVersionId"]
                or operation.effective_routing_version_id != previous["effectiveRoutingVersionId"]
                or operation.operation_id != previous["operationId"] or operation.work_center_id != previous["workCenterId"]
                or operation.dependency_only != previous["dependencyOnly"] or operation.workload_quantity != previous["workloadQuantity"]
                or operation.workload_uom_id != previous["workloadUomId"]):
            _fail("WORK_ORDER_OPERATION_INCONSISTENT", "工单工序持久化字段与不可变来源不一致。")
    transitions = list(BusinessStateTransition.objects.filter(object_type=OBJECT, object_id=row.pk).order_by("version", "pk"))
    pairs = [("", "draft", GENERATE_ACTION)] + ([("draft", "released", ACTION)] if row.status == "released" else [])
    if row.status not in {"draft", "released"} or row.version != len(pairs)-1 or len(transitions) != len(pairs):
        _fail("WORK_ORDER_STATE_HISTORY_INCONSISTENT", "工单状态、版本与原生转换历史不完整。")
    if (row.status == "draft" and any((row.released_by_id, row.released_at, row.release_idempotency_key, row.release_request_hash))
            or row.status == "released" and not all((row.released_by_id, row.released_at, row.release_idempotency_key, row.release_request_hash))):
        _fail("WORK_ORDER_RELEASE_FACTS_INCONSISTENT", "工单下达字段与真实状态不一致。")
    for index, (event, expected_event) in enumerate(zip(transitions, pairs), 1):
        match = re.fullmatch(r"OrganizationOperatingAuditRecord:([1-9][0-9]*)", event.audit_reference or "")
        audit = OrganizationOperatingAuditRecord.objects.filter(pk=int(match[1])).first() if match else None
        if (event.version != index or (event.source_state, event.target_state, event.action_code) != expected_event
                or audit is None or audit.actor_id != event.operator_id or audit.organization_id != row.company_id
                or audit.target_type != OBJECT or audit.target_id != row.pk or audit.action_code != event.action_code
                or not isinstance(audit.before_snapshot, dict) or not isinstance(audit.after_snapshot, dict)
                or not isinstance(audit.before_snapshot.get("state"), dict) or not isinstance(audit.after_snapshot.get("state"), dict)
                or audit.before_snapshot.get("state", {}).get("status") != event.source_state
                or audit.after_snapshot.get("state", {}).get("status") != event.target_state
                or audit.reason.strip() != event.reason
                or audit.after_snapshot.get("state", {}).get("snapshotHash") != row.snapshot_hash):
            _fail("WORK_ORDER_AUDIT_INCONSISTENT", "工单状态审计与真实对象、动作或操作人不一致。")
        authorization = audit.after_snapshot.get("authorization")
        permission_codes = authorization.get("permissionCodes") if isinstance(authorization, dict) else None
        qualification = audit.after_snapshot["state"].get("releaseQualification")
        frozen_actor = qualification.get("currentActorEvidence") if isinstance(qualification, dict) else None
        if (not isinstance(authorization, dict) or authorization.get("allowed") is not True
                or not isinstance(permission_codes, (list, tuple))
                or any(not isinstance(code, str) for code in permission_codes)
                or not any(code in (ACTION, "*") for code in permission_codes)
                or not isinstance(qualification, dict) or qualification.get("qualificationProven") is not True
                or not isinstance(frozen_actor, dict)
                or type(frozen_actor.get("userId")) is not int or frozen_actor["userId"] != event.operator_id
                or type(frozen_actor.get("companyId")) is not int or frozen_actor["companyId"] != row.company_id):
            _fail("WORK_ORDER_AUTHORIZATION_HISTORY_INCONSISTENT", "工单状态审计的冻结授权或责任资格证明不完整或不一致。")
        for snapshot in (audit.before_snapshot, audit.after_snapshot):
            node = snapshot.get("workflowNode", {})
            if (node.get("processCode") != PROCESS or node.get("nodeCode") != WORKFLOW_NODE
                    or node.get("processId") != qualification.get("definitionId") or node.get("nodeId") != qualification.get("nodeId")):
                _fail("WORK_ORDER_WORKFLOW_AUDIT_INCONSISTENT", "工单审计必须引用真实MES下达节点，不得借用计划流程。")
    if (transitions[0].operator_id != row.created_by_id or row.status == "released"
            and (row.released_by_id != transitions[-1].operator_id or not row.released_at)):
        _fail("WORK_ORDER_ACTOR_HISTORY_INCONSISTENT", "工单生成、下达人员与原生转换历史不一致。")
    return operations, transitions


# Native formal continuation: individually restored symbols; existing proofs preserved.
from copy import deepcopy

from decimal import Decimal, InvalidOperation

from django.db import DatabaseError, IntegrityError, OperationalError, transaction

from django.utils import timezone

from masterdata.models import CodeRule, UnitOfMeasure

from pde.models import RoutingStep, WorkCenter

from workflow_runtime.models import BusinessStateTransition, WorkflowNodeDefinition

from workflow_runtime.action_permissions import ActionPermissionValidator

from workflow_runtime.state_transitions import (create_business_object_with_initial_state,
    record_projected_business_transition, transition_business_object)

from . import formal_scheduling_service as formal

from .services import PlanningBusinessError, record_audit

from .work_order_release_admission_contract import ACTION, GENERATE_ACTION, MODULE, PROCESS, WORKFLOW_NODE, register_actions

CONTRACT = "PCE-PRODUCTION-WORK-ORDER-EXECUTION-V1"

NUMBER_ENTITY = "production_work_order"

LABELS = {"": "未建立", "not_generated": "尚未生成生产工单", "draft": "已生成，待下达", "released": "已下达"}

ACTION_LABELS = {GENERATE_ACTION: "生成生产工单", ACTION: "下达生产工单"}

def _number_rule(company_id):
    rule = CodeRule.objects.filter(company_id=company_id, entity_type=NUMBER_ENTITY).first()
    if rule is None:
        _fail("WORK_ORDER_NUMBER_RULE_MISSING", "正式生产工单编号规则尚未登记，请先由授权人员完成受控技术配置。")
    if (not isinstance(rule.prefix, str) or not rule.prefix.strip()
            or not 1 <= rule.seq_length <= 20 or rule.current_seq < 0):
        _fail("WORK_ORDER_NUMBER_RULE_INVALID", "正式生产工单编号规则不完整；未自动覆盖或占用编号。")
    return rule

def _source(plan, facts):
    requirement = plan.planning_requirement
    demand = requirement.demand
    item = demand.sales_order_item
    schedule = facts["sourceSchedule"]
    if (schedule is None or item is None or plan.planned_qty <= 0
            or plan.planned_qty != requirement.net_required_qty
            or requirement.material_id != plan.material_id or demand.material_id != plan.material_id
            or item.material_id != plan.material_id or plan.planned_qty > item.quantity):
        _fail("WORK_ORDER_QUANTITY_SOURCE_INVALID", "工单数量必须来自本计划正式净需求及同一销售订单行，不得以步骤或占用数代替。")
    unit = UnitOfMeasure.objects.filter(pk=item.uom_id, company_id=facts["companyId"], is_active=True).first()
    if unit is None:
        _fail("WORK_ORDER_UOM_SOURCE_INVALID", "订单行缺少同公司有效正式单位，不能推测或隐式换算工单单位。")
    scale = Decimal(1).scaleb(-unit.decimal_places)
    if plan.planned_qty.quantize(scale) != plan.planned_qty:
        _fail("WORK_ORDER_UOM_PRECISION_INVALID", "计划数量不符合正式单位精度，未舍入或改写来源。")
    # Allocations are already validated by the native reception reader. Retain
    # their source/basis quantity separately from operation workload/UOM.
    allocation_rows = list(plan.operation_requirement_allocations.select_related("operation_requirement").all())
    for row in allocation_rows:
        if (row.company_id != facts["companyId"] or row.source_quantity != plan.planned_qty
                or row.source_uom_id != unit.pk or row.operation_requirement.basis_uom_id != unit.pk):
            _fail("WORK_ORDER_ALLOCATION_QUANTITY_CHANGED", "计划工序分配基准数量或单位与本计划、订单行不一致。")
    return {"companyId": facts["companyId"], "productionPlanId": plan.pk, "productionPlanNo": plan.plan_no,
        "quantity": str(plan.planned_qty), "materialId": plan.material_id,
        "materialCode": plan.material.code, "materialName": plan.material.name,
        "uomId": unit.pk, "uomCode": unit.code, "uomLabel": unit.name,
        "plannedStartDate": plan.planned_start_date.isoformat() if plan.planned_start_date else None,
        "requiredDate": plan.required_date.isoformat(), "requirementId": requirement.pk,
        "demandId": demand.pk, "salesOrderItemId": item.pk, "salesOrderId": item.sales_order_id,
        "planningEngine": plan.planning_engine, "sourceType": plan.source_type, "sourceId": plan.source_id,
        "sourceVersion": plan.source_version, "runBatch": plan.run_batch,
        "mpsSourceId": plan.mps_source_id, "mrpSourceId": plan.mrp_source_id,
        "sourceSchedule": deepcopy(schedule), "currentSourceChecks": deepcopy(facts["currentSourceChecks"])}

def _operation_sources(source):
    result = []
    schedule = source["sourceSchedule"]
    checks = {row["stepId"]: row for row in source["currentSourceChecks"]["steps"]}
    for frozen in schedule["steps"]:
        proof = frozen.get("engineeringVersion")
        if not isinstance(proof, dict):
            _fail("WORK_ORDER_OPERATION_SOURCE_MISSING", "正式排程步骤缺少完整工程版本身份，不能生成工单明细。")
        root_id, effective_id = frozen["rootStepId"], proof.get("effectiveRoutingStepId")
        root = RoutingStep.objects.select_related("routing_version", "operation", "work_center").filter(pk=root_id).first()
        effective = RoutingStep.objects.select_related("routing_version", "operation", "work_center").filter(pk=effective_id).first()
        if (root is None or effective is None or proof.get("rootRoutingStepId") != root_id
                or root.routing_version_id != proof.get("originalRoutingVersionId")
                or effective.routing_version_id != proof.get("effectiveRoutingVersionId")
                or effective.operation_id != frozen["operationId"]):
            _fail("WORK_ORDER_OPERATION_SOURCE_CHANGED", "根步骤、有效步骤及其路线版本与正式冻结来源不一致。")
        load = frozen.get("savedLoadReference")
        quantity = load.get("quantity") if isinstance(load, dict) else frozen.get("processDemandQuantity")
        unit_id = load.get("uomId") if isinstance(load, dict) else frozen.get("processDemandUomId")
        unit = UnitOfMeasure.objects.filter(pk=unit_id, company_id=source["companyId"], is_active=True).first() if unit_id else None
        if (quantity is None) != (unit_id is None) or unit_id is not None and unit is None:
            _fail("WORK_ORDER_OPERATION_UOM_INVALID", "工序作业量与正式单位必须成对存在；不得用工单数量补空。")
        if quantity is not None:
            try:
                numeric = Decimal(str(quantity))
            except (InvalidOperation, TypeError):
                _fail("WORK_ORDER_OPERATION_QUANTITY_INVALID", "来源工序作业量不是有效十进制数。")
            if not numeric.is_finite() or numeric <= 0:
                _fail("WORK_ORDER_OPERATION_QUANTITY_INVALID", "来源工序作业量必须大于0；非定量空值保持为空。")
        dependency = bool(frozen.get("dependencyOnly"))
        if dependency and frozen["processingMinutes"] is not None:
            _fail("WORK_ORDER_DEPENDENCY_NULL_INVALID", "依赖承接节点不得伪造加工时长。")
        center = WorkCenter.objects.filter(pk=frozen.get("workCenterId"), company_id=source["companyId"]).first()
        if frozen.get("workCenterId") is not None and center is None:
            _fail("WORK_ORDER_RESOURCE_SOURCE_INVALID", "冻结工作中心不在当前正式公司范围。")
        result.append({"sequence": frozen["sequence"], "rootStepId": root_id, "effectiveStepId": effective_id,
            "rootRoutingVersionId": root.routing_version_id, "effectiveRoutingVersionId": effective.routing_version_id,
            "originalManufacturingOutputId": proof.get("originalManufacturingOutputId"),
            "effectiveManufacturingOutputId": proof.get("effectiveManufacturingOutputId"),
            "operationId": effective.operation_id, "operationName": frozen["operationName"],
            "workCenterId": frozen.get("workCenterId"), "workCenterName": center.name if center else None,
            "workshopId": effective.workshop_id, "dependencyOnly": dependency,
            "workloadQuantity": str(quantity) if quantity is not None else None,
            "workloadUomId": unit_id, "workloadUomCode": unit.code if unit else None, "workloadUomLabel": unit.name if unit else None,
            "workloadLabel": (str(quantity) + " " + unit.name) if unit else "未定量（保留来源空值）",
            "processingMinutes": frozen["processingMinutes"], "start": frozen["start"], "end": frozen["end"],
            "startLabel": frozen["startLabel"], "endLabel": frozen["endLabel"],
            "predecessorSequences": deepcopy(frozen["predecessorSequences"]),
            "allocationIds": deepcopy(checks.get(root_id, {}).get("allocationIds", [])),
            "reservationIds": [r["id"] for r in schedule["reservations"] if r["stepId"] == root_id],
            "sourceVersionLabel": proof.get("versionLabel", "正式步骤版本"), "frozenStep": deepcopy(frozen)})
    if not result or len({r["rootStepId"] for r in result}) != len(result):
        _fail("WORK_ORDER_OPERATION_IDENTITIES_INVALID", "正式步骤为空或身份重复，未生成任何工单。")
    return result

def _present(row):
    if row is None:
        return {"generated": False, "released": False, "id": None, "no": None, "statusCode": "not_generated",
            "statusLabel": LABELS["not_generated"], "version": None, "quantity": None, "quantityLabel": "尚未生成",
            **{key: None for key in ("uomId", "uomCode", "uomLabel", "materialId", "materialCode", "materialName",
                "sourceScheduleId", "sourceScheduleRevision", "sourceScheduleVersion", "sourceScheduleSnapshotHash", "snapshotHash",
                "createdById", "createdAt", "releasedById", "releasedAt")},
            "createdAtLabel": "尚未生成", "releasedAtLabel": "尚未下达", "operations": [], "operationCount": 0,
            "routeProvenance": [], "stateTransitionHistory": [], "statusTransitionCount": 0, "stateMachineConsistent": True}
    operations, transitions = _verify(row)
    source, schedule = row.source_snapshot, row.source_snapshot["sourceSchedule"]
    zone = schedule["timezone"]
    lines = [{"id": item.pk, **{k: deepcopy(v) for k, v in item.source_snapshot.items() if k != "frozenStep"}} for item in operations]
    provenance = []
    for item in lines:
        proof = {k: item[k] for k in ("originalManufacturingOutputId", "effectiveManufacturingOutputId", "rootRoutingVersionId", "effectiveRoutingVersionId")}
        proof["statusLabel"] = item["sourceVersionLabel"]
        if proof not in provenance:
            provenance.append(proof)
    return {"generated": True, "released": row.status == "released", "id": row.pk, "no": row.no,
        "statusCode": row.status, "statusLabel": row.get_status_display(), "version": row.version,
        "quantity": str(row.quantity), "quantityLabel": str(row.quantity) + " " + source["uomLabel"],
        **{k: source[k] for k in ("uomId", "uomCode", "uomLabel", "materialId", "materialCode", "materialName")},
        "sourceScheduleId": row.source_schedule_id, "sourceScheduleRevision": schedule["revision"],
        "sourceScheduleVersion": schedule["version"], "sourceScheduleSnapshotHash": schedule["snapshotHash"], "snapshotHash": row.snapshot_hash,
        "createdById": row.created_by_id, "createdAt": row.created_at.isoformat(), "createdAtLabel": formal._label(row.created_at, zone),
        "releasedById": row.released_by_id, "releasedAt": row.released_at.isoformat() if row.released_at else None,
        "releasedAtLabel": formal._label(row.released_at, zone) if row.released_at else "尚未下达",
        "operations": lines, "operationCount": len(lines), "routeProvenance": provenance,
        "stateTransitionHistory": [{"id": event.pk, "sourceState": event.source_state, "targetState": event.target_state,
            "sourceStateLabel": LABELS[event.source_state], "targetStateLabel": LABELS[event.target_state],
            "actionCode": event.action_code, "actionLabel": ACTION_LABELS[event.action_code], "version": event.version,
            "operatorId": event.operator_id, "auditReference": event.audit_reference, "reason": event.reason,
            "timestamp": event.timestamp.isoformat(), "timestampLabel": formal._label(event.timestamp, zone)} for event in transitions],
        "statusTransitionCount": len(transitions), "stateMachineConsistent": True}

def _contracts(plan, actor):
    policy = register_actions().serialize()
    result = []
    for key, code, states, fields in (("generate", GENERATE_ACTION, ["not_generated"], ["executionToken", "idempotencyKey", "reason"]),
            ("release", ACTION, ["draft"], ["workOrderId", "expectedVersion", "executionToken", "idempotencyKey", "reason"])):
        result.append({**policy, "key": key, "actionCode": code, "displayName": ACTION_LABELS[code],
            "allowedStatuses": states, "sourceAllowedStatuses": ["confirmed"], "assessmentSourceObjectType": "ProductionPlan",
            "objectType": OBJECT, "serverValidator": "planning.work_order_execution_service." + ("generate_work_order" if key == "generate" else "release_work_order"),
            "httpMethod": "POST", "apiPath": f"/api/planning/production-plans/{plan.pk}/work-order/{key}/", "requestFields": fields})
    return result

def _token(action, actor, source, row=None):
    return _hash({"contract": CONTRACT, "action": action, "actorId": actor.pk, "companyId": actor.company_id,
        "sourceHash": _hash(source), "workOrderId": row.pk if row else None, "version": row.version if row else None})

def extend_execution_facts(*, actor, plan, facts):
    """The only execution projection, used unchanged by GET and both writers."""
    row = ProductionWorkOrder.objects.filter(company_id=actor.company_id, production_plan_id=plan.pk).first()
    facts["workOrder"] = _present(row)
    if row is not None and facts["releaseAdmission"]["ready"]:
        facts["releaseAdmission"]["statusLabel"] = "下达准入通过；" + facts["workOrder"]["statusLabel"]
    contracts = _contracts(plan, actor)
    source, source_error = None, None
    try:
        source = _source(plan, facts)
        source["operations"] = _operation_sources(source)
    except PlanningBusinessError as error:
        source_error = error
    available = []
    for contract in contracts:
        key, label, token = contract["key"], "", None
        if not facts["releaseAdmission"]["ready"]:
            label = facts["releaseAdmission"]["statusLabel"]
        elif source_error:
            label = source_error.message
        elif row is not None and row.source_snapshot != source:
            label = "当前计划或来源与已生成工单冻结依据不一致，不能下达或换绑。"
        elif key == "generate" and row is not None:
            label = "本计划已有正式工单，不能重复生成。"
        elif key == "release" and row is None:
            label = "请先明确生成生产工单。"
        elif key == "release" and row.status != "draft":
            label = "该工单已下达，不重复执行。"
        if not label and key == "generate":
            try:
                _number_rule(actor.company_id)
            except PlanningBusinessError as error:
                label = error.message
        if not label:
            token = _token(contract["actionCode"], actor, source, row if key == "release" else None)
        available.append({"key": key, "actionCode": contract["actionCode"], "displayName": contract["displayName"],
            "apiPath": contract["apiPath"], "enabled": not label, "disabledReason": label, "executionToken": token})
    facts["execution"] = {"contractVersion": CONTRACT, "factSource": "server", "actionContracts": contracts, "availableActions": available}
    return facts

def _payload(payload, release=False):
    keys = {"executionToken", "idempotencyKey", "reason"} | ({"workOrderId", "expectedVersion"} if release else set())
    if not isinstance(payload, dict) or set(payload) != keys:
        _fail("WORK_ORDER_FIELDS_INVALID", "提交字段不符合本次工单动作合同。", 400)
    for key, limit in (("idempotencyKey", 120), ("reason", 240)):
        if not isinstance(payload[key], str) or not payload[key].strip() or len(payload[key]) > limit:
            _fail("WORK_ORDER_INPUT_INVALID", "请填写有效幂等标识与明确业务原因。", 400)
    if not isinstance(payload["executionToken"], str) or not re.fullmatch("[0-9a-f]{64}", payload["executionToken"]):
        _fail("WORK_ORDER_TOKEN_INVALID", "请先刷新并引用本次服务端执行凭据。", 400)
    if release and (type(payload["workOrderId"]) is not int or payload["workOrderId"] <= 0
            or type(payload["expectedVersion"]) is not int or payload["expectedVersion"] < 0):
        _fail("WORK_ORDER_VERSION_INVALID", "必须提供正式工单身份与乐观版本。", 400)

def _fresh(user, plan_id, action=ACTION):
    from .work_order_reception_service import read_work_order_reception
    actor, plan = formal._plan(user, plan_id)
    facts = read_work_order_reception(user=actor, production_plan_id=plan.pk)
    if not facts["releaseAdmission"]["ready"] or not facts["responsibility"]["qualificationProven"]:
        _fail("WORK_ORDER_EXECUTION_QUALIFICATION_REQUIRED", facts["releaseAdmission"]["statusLabel"], 403)
    from .work_order_release_admission_service import _PlanFacts
    decision = ActionPermissionValidator(fact_provider=_PlanFacts(actor, plan)).evaluate(user=actor,
        module_code=MODULE, action_code=action, object_ids=[plan.pk], selection_count=1,
        requested_legal_entity_id=str(actor.company_id))
    if not decision["granted"]:
        _fail("WORK_ORDER_ACTION_PERMISSION_DENIED", decision.get("reason") or "当前工单动作未通过统一权限校验。", 403)
    source = _source(plan, facts)
    source["operations"] = _operation_sources(source)
    return actor, plan, facts, source

def _request_hash(actor, plan, action, payload, source):
    return _hash({"action": action, "actorId": actor.pk, "companyId": actor.company_id, "productionPlanId": plan.pk,
        "sourceHash": _hash(source), "sourceScheduleId": source["sourceSchedule"]["id"],
        "sourceScheduleSnapshotHash": source["sourceSchedule"]["snapshotHash"], "payload": payload})

def _audit(actor, plan, row, action, before, after, facts, reason):
    responsibility = facts["responsibility"]
    node = WorkflowNodeDefinition.objects.select_related("process_definition").filter(
        pk=responsibility["nodeId"], process_definition_id=responsibility["definitionId"],
        process_definition__definition_code=PROCESS, process_definition__active=True,
        node_code=WORKFLOW_NODE, business_action_code=ACTION, active=True).first()
    if node is None:
        _fail("WORK_ORDER_WORKFLOW_AUDIT_SOURCE_CHANGED", "正式MES下达节点已改变，未保存工单审计。")
    audit = record_audit(user=actor, action_code=action, target=row, target_type=OBJECT, target_no=row.no,
        before=before, after={**after, "snapshotHash": row.snapshot_hash,
            "productionPlanId": plan.pk, "sourceScheduleId": row.source_schedule_id,
            "releaseQualification": deepcopy(facts["responsibility"]), "executionContract": CONTRACT},
        authorization=next(c for c in facts["releaseAdmission"]["checks"] if c["checkCode"] == "actionAuthorization")["details"]["nativeDecision"],
        reason=reason)
    # The native audit helper owns actor/permission/object facts but its legacy
    # node selector is PLAN-specific. Adapt only this audit, in this transaction.
    formal_node = {"processId": node.process_definition_id, "processCode": node.process_definition.definition_code,
        "processName": node.process_definition.definition_name, "nodeId": node.pk, "nodeCode": node.node_code,
        "nodeName": node.node_name, "sequence": node.sequence}
    audit.before_snapshot["workflowNode"] = formal_node
    audit.after_snapshot["workflowNode"] = formal_node
    audit.save(update_fields=["before_snapshot", "after_snapshot"])
    return audit

def _writes(*, created=0, operations=0, released=0, idempotent=False):
    return {"idempotent": idempotent, "businessWriteCount": created + operations + released,
        "auditWriteCount": 0 if idempotent else 1, "stateTransitionWriteCount": 0 if idempotent else 1,
        "workOrderCreatedCount": created, "workOrderOperationCreatedCount": operations, "workOrderReleasedCount": released,
        "numberSequenceAdvanceCount": created, "technicalMutexWriteCount": 1,
        "productionScheduleCreatedCount": 0, "resourceOccupancyCreatedCount": 0,
        "resourceOccupancyReleasedCount": 0, "capacityGrantCreatedCount": 0}

def _read_after(actor, plan, writes):
    from .work_order_reception_service import read_work_order_reception
    facts = read_work_order_reception(user=actor, production_plan_id=plan.pk)
    facts["businessWriteCount"], facts["auditWriteCount"] = writes["businessWriteCount"], writes["auditWriteCount"]
    return facts, writes

def generate_work_order(*, user, production_plan_id, payload):
    _payload(payload)
    actor, plan = formal._plan(user, production_plan_id)
    try:
        with transaction.atomic():
            formal._writer_lock(actor)
            actor, plan, facts, source = _fresh(user, production_plan_id, GENERATE_ACTION)
            request_hash = _request_hash(actor, plan, GENERATE_ACTION, payload, source)
            previous = ProductionWorkOrder.objects.filter(company_id=actor.company_id, idempotency_key=payload["idempotencyKey"]).first()
            if previous is not None:
                if previous.production_plan_id != plan.pk or previous.request_hash != request_hash or previous.source_snapshot != source:
                    _fail("WORK_ORDER_IDEMPOTENCY_CONFLICT", "幂等标识已用于不同公司、计划、来源或生成意图。")
                _verify(previous)
                return _read_after(actor, plan, _writes(idempotent=True))
            if ProductionWorkOrder.objects.filter(production_plan_id=plan.pk).exists():
                _fail("WORK_ORDER_ALREADY_GENERATED", "本计划已有正式生产工单，请刷新后查看，未重复生成。")
            if payload["executionToken"] != _token(GENERATE_ACTION, actor, source):
                _fail("WORK_ORDER_SOURCE_CHANGED", "当前来源或请求账号已变化，请重新刷新后生成。")
            _number_rule(actor.company_id)
            number = CodeRule.next_code(company_id=actor.company_id, entity_type=NUMBER_ENTITY)
            row = create_business_object_with_initial_state(model=ProductionWorkOrder, initial_state="draft",
                company_id=actor.company_id, production_plan=plan, source_schedule_id=source["sourceSchedule"]["id"],
                no=number, material_id=source["materialId"], quantity=Decimal(source["quantity"]), uom_id=source["uomId"],
                source_snapshot=source, snapshot_hash=_hash(source), idempotency_key=payload["idempotencyKey"], request_hash=request_hash, created_by=actor)
            for item in source["operations"]:
                operation = ProductionWorkOrderOperation(work_order=row, sequence=item["sequence"], root_step_id=item["rootStepId"],
                    effective_step_id=item["effectiveStepId"], root_routing_version_id=item["rootRoutingVersionId"],
                    effective_routing_version_id=item["effectiveRoutingVersionId"], operation_id=item["operationId"],
                    work_center_id=item["workCenterId"], dependency_only=item["dependencyOnly"], workload_quantity=item["workloadQuantity"],
                    workload_uom_id=item["workloadUomId"], source_snapshot=item, snapshot_hash=_hash(item))
                operation.full_clean()
                operation.save(force_insert=True)
            audit = _audit(actor, plan, row, GENERATE_ACTION, {"status": ""}, {"status": "draft", "operationCount": len(source["operations"])}, facts, payload["reason"])
            record_projected_business_transition(object_type=OBJECT, object_id=row.pk, source_state="", target_state="draft",
                action_code=GENERATE_ACTION, operator=actor, reason=payload["reason"], audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}", allowed_transitions={("", "draft")})
            _verify(row)
            return _read_after(actor, plan, _writes(created=1, operations=len(source["operations"])))
    except (OperationalError, IntegrityError) as error:
        raise PlanningBusinessError("WORK_ORDER_CONCURRENT_CONFLICT", "工单状态或并发请求已变化，请只读刷新后核对原结果。", http_status=409) from error

def release_work_order(*, user, production_plan_id, payload):
    _payload(payload, release=True)
    actor, plan = formal._plan(user, production_plan_id)
    try:
        with transaction.atomic():
            formal._writer_lock(actor)
            actor, plan, facts, source = _fresh(user, production_plan_id)
            row = ProductionWorkOrder.objects.select_for_update().filter(company_id=actor.company_id, production_plan_id=plan.pk, pk=payload["workOrderId"]).first()
            if row is None:
                _fail("WORK_ORDER_NOT_FOUND", "本公司本计划尚无指定正式工单。", 404)
            _verify(row)
            if row.source_snapshot != source:
                _fail("WORK_ORDER_SOURCE_CHANGED", "当前计划、数量、单位或正式来源已改变，不能下达旧工单或静默换绑。")
            request_hash = _request_hash(actor, plan, ACTION, payload, source)
            if row.status == "released":
                if row.release_idempotency_key != payload["idempotencyKey"] or row.release_request_hash != request_hash:
                    _fail("WORK_ORDER_IDEMPOTENCY_CONFLICT", "工单已下达；幂等标识或原下达意图不一致。")
                return _read_after(actor, plan, _writes(idempotent=True))
            if row.version != payload["expectedVersion"]:
                _fail("WORK_ORDER_VERSION_CHANGED", "工单版本已变化，请重新读取。")
            if payload["executionToken"] != _token(ACTION, actor, source, row):
                _fail("WORK_ORDER_SOURCE_CHANGED", "当前来源或请求账号已变化，请重新刷新后下达。")
            audit = _audit(actor, plan, row, ACTION, {"status": "draft"}, {"status": "released"}, facts, payload["reason"])
            row.release_idempotency_key, row.release_request_hash = payload["idempotencyKey"], request_hash
            row.released_by, row.released_at = actor, timezone.now()
            row.save(update_fields=["release_idempotency_key", "release_request_hash", "released_by", "released_at", "updated_at"])
            transition_business_object(business_object=row, object_type=OBJECT, source_state="draft", target_state="released",
                action_code=ACTION, operator=actor, reason=payload["reason"], audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}", allowed_transitions={("draft", "released")})
            _verify(row)
            return _read_after(actor, plan, _writes(released=1))
    except (OperationalError, IntegrityError) as error:
        raise PlanningBusinessError("WORK_ORDER_CONCURRENT_CONFLICT", "工单状态或并发请求已变化，请只读刷新后核对原结果。", http_status=409) from error
