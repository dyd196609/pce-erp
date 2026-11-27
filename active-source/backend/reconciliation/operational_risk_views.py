from decimal import Decimal

from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from planning.operation_predecessor_authority import predecessor_facts
from planning.workshop_task_models import ProductionWorkshopTask
from procurement.inventory_facts_api import PURCHASE_INSPECTION_READ_PERMISSION
from procurement.material_stock_authority import quality_projection
from procurement.models import PurchaseInspection
from sales.enterprise_authority import FOLLOWUP_ASSIGN, FOLLOWUP_VIEW, RISK_CLOSE, RISK_HANDLERS, RISK_RECEIVE
from sales.enterprise_authority import allowed, audit, scoped_grants
from sales.followup_views import EnterpriseView, conflict, follower_can_read, manager_can_assign, read_failure, response, validated
from system.models import User
from workflow_runtime.state_transitions import create_business_object_with_initial_state

from .risk_models import OperationalEvidenceRisk
from .risk_views import ACTIONS, UpdateInput, apply_risk_action, can_read_source, row_facts


PAGE_SIZE = 20
SALE = "work_order__production_plan__planning_requirement__demand__sales_order_item__sales_order"


class OperationalReceiveInput(serializers.Serializer):
    sourceId = serializers.IntegerField(min_value=1)
    handlerId = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=300)


def source_key(kind):
    if kind not in ("mes", "qms"):
        raise NotFound("没有此类运营风险。")
    return "task" if kind == "mes" else "inspection"


def sale_for_task(task):
    plan = task.work_order.production_plan
    requirement = getattr(plan, "planning_requirement", None)
    demand = getattr(requirement, "demand", None)
    line = getattr(demand, "sales_order_item", None)
    order = getattr(line, "sales_order", None)
    if order and (order.company_id == task.company_id
                  and task.work_order.source_snapshot.get("salesOrderId") == order.pk
                  and task.work_order.source_snapshot.get("salesOrderItemId") == line.pk):
        return order
    return None


def source_rows(actor, kind):
    if kind == "qms":
        if not can_read_source(actor, PURCHASE_INSPECTION_READ_PERMISSION):
            raise PermissionDenied("当前岗位没有正式来料检验读取权限。")
        return PurchaseInspection.objects.filter(
            source_receipt__source_purchase_order__company_id=actor.company_id,
            status__in=("qualified", "rejected"), rejected_quantity__gt=0,
        ).select_related("source_receipt__source_purchase_order")
    managers = scoped_grants(actor, FOLLOWUP_ASSIGN)
    followers = scoped_grants(actor, FOLLOWUP_VIEW)
    if not managers.exists() and not followers.exists():
        raise PermissionDenied("当前岗位没有正式生产跟单读取范围。")
    manager_scope = Q(work_center__department_id__in=managers.filter(
        scope_code="DEPARTMENT").values("department_id"))
    follower_scope = Q(**{SALE + "__productionfollowupassignment__owner_id": actor.pk})
    rows = ProductionWorkshopTask.objects.filter(
        company_id=actor.company_id, status="dispatched", work_order__company_id=actor.company_id,
        work_order__status="released", work_order__usage_purpose="PRODUCTION_USE",
    ).select_related(SALE, "source_operation", "work_center")
    return rows if allowed(actor, FOLLOWUP_ASSIGN) else rows.filter(manager_scope | follower_scope)


def can_read(actor, kind, original):
    if kind == "qms":
        return (original.source_receipt.source_purchase_order.company_id == actor.company_id
                and can_read_source(actor, PURCHASE_INSPECTION_READ_PERMISSION))
    order = sale_for_task(original)
    return bool(order and order.company_id == actor.company_id
                and (manager_can_assign(actor, order) or follower_can_read(actor, order)))


def verified_late_start(task):
    from pde.order_routing_execution_service import ArrangementError
    from planning.mes_task_date_facts import compare_task_start, task_date_facts
    from planning.mes_test_source_bridge import _verify_record
    from planning.operation_start_models import ProductionOperationStart
    from planning.services import PlanningBusinessError

    start = ProductionOperationStart.objects.filter(company_id=task.company_id, task=task).first()
    if start is None:
        return None
    dates = task_date_facts(task, start)
    timing = compare_task_start(dates)
    if not timing['isLate']:
        return None
    try:
        _verify_record(start, task)
    except (ArrangementError, PlanningBusinessError):
        return None
    return {**timing, 'startRecordId': start.pk}


def current_evidence(kind, row):
    if kind == "qms":
        quality = quality_projection(row)["lineReleaseFacts"]
        if not quality or quality["qualityReleaseStatus"] not in ("RELEASED", "REJECTED"):
            return None
        if Decimal(quality["rejectedQuantity"]) <= 0:
            return None
        return {
            "kind": kind, "no": quality["inspectionNo"], "orderNo": quality["purchaseOrderNo"],
            "lineId": quality["purchaseOrderItemId"], "receiptNo": quality["receiptNo"],
            "material": quality["materialCode"], "unit": quality["unit"],
            "quantity": quality["inspectionScopeQuantity"], "qualified": quality["qualifiedQuantity"],
            "rejected": quality["rejectedQuantity"], "statusLabel": quality["statusLabel"],
            "findingLabel": "逐行品质差异", "cause": "原检验行已有正式不合格量。",
            "department": "质检",
            "link": {"path": f"/qms/incoming-inspection/{row.pk}"},
        }
    order = sale_for_task(row)
    verified = predecessor_facts(row)
    if not verified["routeRelationshipConsistent"]:
        return None
    blockers = [{"operationId": item["operationId"], "name": item["operationName"],
                 "reason": item["statusLabel"], "reasonCode": item["reasonCode"]}
                for item in verified["items"]
                if item["operationId"] and item.get("reasonCode") and not item.get("prerequisiteSatisfied", item["completed"])]
    late_start = verified_late_start(row)
    return {
        "kind": kind, "no": row.no, "orderNo": order.order_no, "workOrderNo": row.work_order.no,
        "operation": row.source_operation.source_snapshot.get("operationName"),
        "statusLabel": row.get_status_display(),
        "findingLabel": ("正式前序阻断、开工延期" if blockers and late_start else
                         "开工延期" if late_start else "正式前序阻断" if blockers else "前序依据已核实"),
        "cause": verified["statusLabel"], "predecessors": blockers, "scheduleDelay": late_start, "department": "生产跟单",
        "link": {"path": "/business-trace", "query": {"followupOrder": order.order_no, "followupProgress": "1",
            "officeOrderLine": str(row.work_order.source_snapshot["salesOrderItemId"]), "officeProgressTask": str(row.pk)}},
    }


def rights_for(actor, kind, original):
    return {
        "receive": allowed(actor, RISK_RECEIVE),
        "close": allowed(actor, RISK_CLOSE),
        "handler": (can_read(actor, kind, original) if kind == "mes"
                    else allowed(actor, RISK_HANDLERS["quality"][0])),
    }


def qualified_handler(actor, kind, original):
    return can_read(actor, kind, original) and rights_for(actor, kind, original)["handler"]


def has_finding(source):
    return bool(source and (source["kind"] == "qms" or source["predecessors"] or source.get("scheduleDelay")))


class OperationalRiskDirectoryView(EnterpriseView):
    def get(self, request, kind):
        field = source_key(kind)
        actor = request.user
        try:
            page = int(request.query_params.get("page", 1))
        except (TypeError, ValueError):
            raise ValidationError("页码须为正整数。")
        if not 1 <= page <= 100000:
            raise ValidationError("页码须为正整数。")
        try:
            rows = source_rows(actor, kind).order_by("-pk")
            count = rows.count()
            originals = list(rows[(page - 1) * PAGE_SIZE:page * PAGE_SIZE])
            cases = {getattr(risk, field + "_id"): risk for risk in OperationalEvidenceRisk.objects.filter(
                **{field + "_id__in": [item.pk for item in originals]}).select_related("handler")}
            entries = []
            possible_handlers = None
            for original in originals:
                if not can_read(actor, kind, original):
                    continue
                live = current_evidence(kind, original)
                case = cases.get(original.pk)
                if not case and not has_finding(live):
                    continue
                rights = rights_for(actor, kind, original)
                item = {"id": original.pk, "source": live or case.source_evidence,
                        "sourceCurrent": live is not None,
                        "statusLabel": case.get_status_display() if case else "待受理"}
                if case:
                    item["risk"] = row_facts(actor, case, rights)
                    item["evidenceAtReceipt"] = case.source_evidence
                elif rights["receive"]:
                    if possible_handlers is None:
                        possible_handlers = list(User.objects.filter(company_id=actor.company_id, is_active=True))
                    item["action"] = {"type": "receive", "code": ACTIONS["receive"][0], "label": ACTIONS["receive"][1]}
                    item["handlers"] = [{"id": user.pk, "name": user.real_name} for user in possible_handlers
                                        if qualified_handler(user, kind, original)]
                entries.append(item)
            return response(request, {"items": entries, "page": page,
                                      "hasNext": page * PAGE_SIZE < count}, len(entries))
        except DatabaseError:
            return read_failure(request)

    @transaction.atomic
    def post(self, request, kind):
        field = source_key(kind)
        actor = request.user
        if not allowed(actor, RISK_RECEIVE):
            raise PermissionDenied("当前岗位没有风险受理权限。")
        data = validated(OperationalReceiveInput, request)
        original = source_rows(actor, kind).select_for_update().filter(pk=data["sourceId"]).first()
        if not original or not can_read(actor, kind, original):
            raise NotFound("当前范围没有对应的原始记录。")
        source = current_evidence(kind, original)
        if not has_finding(source):
            raise ValidationError("原记录尚无对应的正式风险依据。")
        handler = User.objects.filter(company_id=actor.company_id, is_active=True, pk=data["handlerId"]).first()
        if not handler or not qualified_handler(handler, kind, original):
            raise ValidationError("所选人员没有该原单的处理资格。")
        identity = {field: original}
        if OperationalEvidenceRisk.objects.filter(**identity).exists():
            return conflict("该原始记录已有风险办理记录。")
        try:
            with transaction.atomic():
                risk = create_business_object_with_initial_state(model=OperationalEvidenceRisk,
                    initial_state="received", handler=handler, source_evidence=source, **identity)
        except IntegrityError:
            if OperationalEvidenceRisk.objects.filter(**identity).exists():
                return conflict("该原始记录已有风险办理记录。")
            raise
        audit(actor, ACTIONS["receive"][0], risk, source["no"], data["reason"], {},
              {"handler": handler.real_name, "handlerId": handler.pk, "source": source})
        return response(request, {"risk": row_facts(actor, risk, rights_for(actor, kind, original))})


class OperationalRiskActionView(EnterpriseView):
    @transaction.atomic
    def post(self, request, kind, risk_id, action):
        field = source_key(kind)
        actor = request.user
        data = validated(UpdateInput, request)
        risk = OperationalEvidenceRisk.objects.select_for_update().filter(
            pk=risk_id, **{field + "_id__in": source_rows(actor, kind).values("pk")}).first()
        if not risk:
            raise NotFound("当前范围没有对应的风险记录。")
        original = getattr(risk, field)
        if not can_read(actor, kind, original):
            raise NotFound("当前范围没有对应的原始记录。")
        facts = apply_risk_action(actor, risk, rights_for(actor, kind, original), action, data,
                                  risk.source_evidence["no"], risk.source_evidence)
        if facts is None:
            return conflict("风险记录已变化，请读取最新记录。")
        return response(request, {"risk": facts})
