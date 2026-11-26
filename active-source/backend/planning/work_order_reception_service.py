

# Native formal continuation: individually restored symbols; existing proofs preserved.
from copy import deepcopy

from datetime import date

from decimal import Decimal

from django.core.exceptions import ValidationError

from django.db import transaction

from . import formal_scheduling_service as formal

from .models import FormalProductionSchedule, ScheduleCapacityGrant

from .services import PlanningBusinessError

CONTRACT = "PCE-PRODUCTION-WORK-ORDER-RECEPTION-V2"

NODE = "production-work-order"

def _issue(code, label, **details):
    return {"code": code, "statusLabel": label, **details}

def _known_issue(error, **details):
    if not isinstance(error, ValidationError) and not hasattr(error, "code"):
        raise error
    return _issue(getattr(error, "code", None) or "WORK_ORDER_SOURCE_UNPROVEN",
        getattr(error, "message", None) or "正式来源校验未通过。", **details)

def _frozen_structure_issues(schedule):
    steps = schedule["steps"]
    sequences = {row["sequence"]: row for row in steps}
    if not steps or len(sequences) != len(steps) or len({r["rootStepId"] for r in steps}) != len(steps):
        return [_issue("WORK_ORDER_FROZEN_STEPS_INVALID", "正式版本步骤身份不完整或重复。")]
    for step in steps:
        for prior in step["predecessorSequences"]:
            if (prior not in sequences or prior == step["sequence"]
                    or formal._instant(step["start"]) < formal._instant(sequences[prior]["end"])):
                return [_issue("WORK_ORDER_DEPENDENCY_INVALID", "冻结前序依赖不存在、倒置或计划承接时点不一致。", stepId=step["rootStepId"])]
        if step.get("dependencyOnly"):
            if step["processingMinutes"] is not None or any(p["phase"] == "processing" for p in step["phases"]):
                return [_issue("WORK_ORDER_NULL_SEMANTICS_INVALID", "依赖承接节点不得填成定量加工或生成加工占用。", stepId=step["rootStepId"])]
            if any(r["stepId"] == step["rootStepId"] for r in schedule["reservations"]):
                return [_issue("WORK_ORDER_NULL_SEMANTICS_INVALID", "非定量节点存在不应生成的加工占用。", stepId=step["rootStepId"])]
    return []

def _current_source_checks(actor, plan, schedule):
    from pde.plan_step_context_service import resolve_step_context, version_fact
    from pde.operation_requirement_service import _source_read_cache, process_demand_for_plan
    from pde.manufacturing_output_generation_service import validate_selected_output
    from pde.manufacturing_time_policy_service import resolve_scope, physical_hash
    from pde.operation_input_preparation_service import resolve_capacity_consumption_reference
    from pde.daily_capacity_service import _current_plan_capacity
    from pde.models import WorkCenter

    issues, rows = [], []
    cache = _source_read_cache(actor, None)
    source_row = FormalProductionSchedule.objects.get(pk=schedule["id"], company_id=actor.company_id,
        production_plan_id=plan.pk)
    output_checked = set()
    capacity_steps = {}
    for saved_step in source_row.snapshot['preview'].get('originalReadiness', {}).get('steps', []):
        roots=[f['rootStepId'] for f in schedule['steps'] if f['stepId']==saved_step['stepId']]
        if len(roots)!=1 or saved_step.get('rootStepId',roots[0])!=roots[0]:
            raise PlanningBusinessError('WORK_ORDER_CAPACITY_STEP_IDENTITY_INVALID','冻结产能步骤无法唯一对应本排程的根步骤。')
        capacity_steps[roots[0]]=saved_step
    keys = ("originalManufacturingOutputId", "effectiveManufacturingOutputId", "originalRoutingVersionId",
        "effectiveRoutingVersionId", "rootRoutingStepId", "effectiveRoutingStepId", "bindingId",
        "sourceBaselineId", "mainCalculationId", "sourceSelection")
    for frozen in schedule["steps"]:
        step_id = frozen["rootStepId"]
        try:
            context = resolve_step_context(plan, step_id, user=actor, read_cache=cache)
            current = version_fact(context)
            previous = frozen.get("engineeringVersion")
            if not isinstance(previous, dict) or any(current.get(k) != previous.get(k) for k in keys):
                raise PlanningBusinessError("WORK_ORDER_ENGINEERING_VERSION_CHANGED",
                    "当前有效步骤来源与排程冻结版本不一致，禁止静默切换。")
            if context["output"].pk not in output_checked:
                validate_selected_output(context["output"], user=actor, read_cache=cache, _content_plan_id=plan.pk)
                output_checked.add(context["output"].pk)
            actual_step = context["step"]
            if (not actual_step.is_active or actual_step.operation_id != frozen["operationId"]
                    or actual_step.predecessor_sequences != frozen["predecessorSequences"]):
                raise PlanningBusinessError("WORK_ORDER_ROUTE_CHANGED", "当前步骤、工序或依赖已改变。")
            bridge = process_demand_for_plan(plan, context["output"], plan.planning_requirement.demand.sales_order_item,
                {"stepId": actual_step.pk, "operationId": actual_step.operation_id},
                company_id=actor.company_id, user=actor, read_cache=cache)
            allocation_ids = ([r["allocationId"] for r in bridge.get("contributions", [])] if bridge else [])
            # Dependency-only nodes retain a saved load reference without an
            # independently quantified processing duration. Compare that
            # reference, never require their NULL processing basis to be >0.
            frozen_load = frozen.get("savedLoadReference")
            frozen_quantity = (frozen_load.get("quantity") if isinstance(frozen_load, dict)
                else frozen.get("processDemandQuantity"))
            frozen_uom_id = (frozen_load.get("uomId") if isinstance(frozen_load, dict)
                else frozen.get("processDemandUomId"))
            if (bridge is not None and (frozen_quantity is None
                    or Decimal(bridge["quantity"]) != Decimal(frozen_quantity)
                    or bridge["uomId"] != frozen_uom_id)
                    or bridge is None and frozen_quantity is not None):
                raise PlanningBusinessError("WORK_ORDER_ALLOCATED_LOAD_CHANGED",
                    "当前有效投产量或单位与排程冻结依据不一致，不能用旧工期接收。")
            if frozen.get("standardCapacityId") is not None:
                matches = [fact for fact in capacity_steps.get(step_id, {}).get("dailyCapacity", [])
                    if fact["id"] == frozen["standardCapacityId"]]
                if len(matches) != 1:
                    raise PlanningBusinessError("WORK_ORDER_CAPACITY_FACT_UNPROVEN", "冻结版本缺少选中产能的完整原生事实。")
                capacity_days = sorted({part["productionDate"] for phase in frozen["phases"]
                    for part in phase["allocations"]}) or [schedule["savedStartDate"]]
                for day in capacity_days:
                    _current_plan_capacity(matches[0], date.fromisoformat(day),
                        no_date_reference=frozen.get("capacityConsumptionReference"), source_rules_cache=cache, read_user=actor)
            rows.append({"stepId": step_id,
                "statusLabel": f"{frozen['operationName']}：{current['versionLabel']}；当前有效来源及分配已复核",
                "currentEngineeringVersion": current, "allocationIds": allocation_ids,
                "allocationCount": len(allocation_ids)})
        except Exception as error:
            issues.append(_known_issue(error, stepId=step_id))
            break

    if not issues:
        for proof in source_row.snapshot["resourceSnapshot"]:
            center = WorkCenter.objects.filter(pk=proof["id"], company_id=actor.company_id).first()
            if center is None or not center.is_active or physical_hash(center) != proof["physicalHash"]:
                issues.append(_issue("WORK_ORDER_RESOURCE_CHANGED", "当前加工工作中心已停用、改变范围或与冻结资源不一致。"))
                break
    if not issues:
        try:
            # Reuse the formal selection rules on the saved working dates. No
            # dates or durations are recomputed and no policy is confirmed.
            for proof in source_row.snapshot["preview"].get("timePolicyProofs", []):
                matching = [row for row in schedule["steps"]
                    if (proof["kind"] == "SHARED_ARRANGEMENT"
                        or proof["kind"] == "WC_APPLICATION" and row.get("workCenterId") == proof["workCenterId"]
                        or proof["kind"] == "CAPACITY_TIME_BASIS" and row.get("standardCapacityId") == proof["standardCapacityId"]
                        or proof["kind"] == "OPERATION_RESTRICTION" and row.get("operationId") == proof["operationId"])]
                days = sorted({part["productionDate"] for row in matching for phase in row["phases"]
                    for part in phase["allocations"]}) or [schedule["savedStartDate"]]
                for day in days:
                    selected = resolve_scope(user=actor, kind=proof["kind"], on_date=date.fromisoformat(day),
                        work_center_id=proof.get("workCenterId"), operation_id=proof.get("operationId"),
                        standard_capacity_id=proof.get("standardCapacityId"), code=proof["code"])["row"]
                    if selected["id"] != proof["id"] or selected["contentHash"] != proof["contentHash"]:
                        raise PlanningBusinessError("WORK_ORDER_TIME_POLICY_CHANGED", "当前有效时间依据与排程冻结依据不一致。")
            frozen_proofs = {p["id"]: p["contentHash"] for p in source_row.snapshot["scopeProofs"]}
            used = set()
            for step in schedule["steps"]:
                prior = step.get("capacityConsumptionReference")
                if prior is None:
                    continue
                reference = resolve_capacity_consumption_reference(user=actor, exact_scope=prior["exactScope"],
                    on_date=plan.planned_start_date)
                if reference is None or reference["referenceHash"] != prior["referenceHash"]:
                    raise PlanningBusinessError("WORK_ORDER_CAPACITY_SOURCE_CHANGED", "原精确消费证明已失效或改变。")
                days = sorted({date.fromisoformat(p["productionDate"]) for phase in step["phases"] for p in phase["allocations"]})
                matched = False
                for grant in ScheduleCapacityGrant.objects.filter(pk__in=frozen_proofs, company_id=actor.company_id,
                        production_plan_id=plan.pk, standard_capacity_id=step["standardCapacityId"]):
                    if grant.exact_scope == reference["exactScope"]:
                        if (grant.content_hash != frozen_proofs[grant.pk] or not formal._verify_grant(grant, reference, days)):
                            raise PlanningBusinessError("WORK_ORDER_CAPACITY_GRANT_CHANGED", "正式加工用途证明已改变或不覆盖保存时段。")
                        used.add(grant.pk)
                        matched = True
                        break
                if not matched:
                    raise PlanningBusinessError("WORK_ORDER_CAPACITY_GRANT_MISSING", "冻结版本引用的精确正式用途证明不存在。")
            if used != set(frozen_proofs):
                raise PlanningBusinessError("WORK_ORDER_CAPACITY_GRANT_CHANGED", "冻结正式用途证明与当前步骤消费不一致。")
        except Exception as error:
            issues.append(_known_issue(error))
    return {"ready": not issues, "statusLabel": "当前步骤来源已复核" if not issues else "当前步骤来源复核受阻",
        "issues": issues, "steps": rows}

def _release_checks(actor, plan, source_checks, schedule, reception):
    from .work_order_release_admission_service import assess_release_admission
    return assess_release_admission(actor=actor, plan=plan, schedule=schedule,
        reception=reception, source_checks=source_checks)

@transaction.atomic
def read_work_order_reception(*, user, production_plan_id, expected_schedule_id=None,
        expected_revision=None, expected_snapshot_hash=None):
    actor, plan = formal._plan(user, production_plan_id)
    parent = formal.read_formal_scheduling(user=actor, production_plan_id=plan.pk)
    active = parent["activeSchedule"]
    if any(value is not None for value in (expected_schedule_id, expected_revision, expected_snapshot_hash)):
        if (active is None or expected_schedule_id is not None and active["id"] != expected_schedule_id
                or expected_revision is not None and active["revision"] != expected_revision
                or expected_snapshot_hash is not None and active["snapshotHash"] != expected_snapshot_hash):
            raise PlanningBusinessError("WORK_ORDER_SOURCE_VERSION_CHANGED",
                "指定排程已撤销、失效或与当前有效版本不一致，请重新读取。", http_status=409)
    issues = []
    if active is None:
        issues.append(_issue("WORK_ORDER_ACTIVE_SCHEDULE_REQUIRED", "当前计划没有可接收的有效正式排程。"))
    else:
        issues.extend(_frozen_structure_issues(active))
        if plan.planned_start_date is None or plan.planned_start_date.isoformat() != active["savedStartDate"]:
            issues.append(_issue("WORK_ORDER_PLAN_DATE_CHANGED", "当前计划开始日期与有效排程保存依据不一致。"))
        if plan.status != "confirmed":
            issues.append(_issue("WORK_ORDER_PLAN_STATE_CHANGED", "当前计划已不符合保存排程时的已确认计划合同。"))
    source = (_current_source_checks(actor, plan, active) if active and not issues else
        {"ready": False, "statusLabel": "尚未完成当前步骤来源复核", "issues": [], "steps": []})
    issues.extend(source["issues"])
    ready = active is not None and not issues
    reception = {"ready": ready, "statusLabel": "正式排程可供只读接收" if ready else "正式排程接收受阻", "issues": issues}
    release, responsibility = _release_checks(actor, plan, source, active, reception)
    facts = {"contractVersion": CONTRACT, "moduleCode": NODE, "factSource": "server", "currentStateSource": "server",
        "companyId": actor.company_id, "productionPlanId": plan.pk, "productionPlanNo": plan.plan_no,
        "modeLabel": parent["modeLabel"], "timezoneLabel": parent["timezoneLabel"], "statusLabel": reception["statusLabel"],
        "sourceSchedule": deepcopy(active), "reception": reception, "releaseAdmission": release,
        "currentSourceChecks": source, "responsibility": responsibility,
        "workOrder": {"generated": False, "released": False, "statusLabel": "本次仅只读接收，尚未生成或下达生产工单"},
        "businessWriteCount": 0, "auditWriteCount": 0}
    from .work_order_execution_service import extend_execution_facts
    return extend_execution_facts(actor=actor, plan=plan, facts=facts)
