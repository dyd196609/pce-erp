from datetime import date
from decimal import Decimal

from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from masterdata.models import Material
from masterdata.models import SupplierMaterialPrice
from procurement.business_action_control import record_action_audit
from procurement.models import InventoryBalance, PurchaseRequest, PurchaseRequestItem
from system.models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    PositionWorkflowResponsibility,
)
from workflow_runtime.models import WorkflowNodeDefinition
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
    record_projected_business_transition,
    transition_business_object,
)

from .models import (
    Demand, MPSDemandAllocation, MasterProductionScheduleLine,
    MasterProductionScheduleRun, MaterialRequirementProposal,
    MaterialRequirementsPlanningRun, PlanningRequirement, ProductionPlan,
    PurchasePlan,
)
from .schema import order_planning_schema_ready


PROCESS_CODE = "PLAN_DEMAND_TO_SUPPLY_PLAN"


class PlanningBusinessError(Exception):
    def __init__(self, code, message, *, http_status=400, data=None):
        self.code = code
        self.message = message
        self.http_status = http_status
        self.data = data
        super().__init__(message)


def supply_type_for(material):
    if material.supply_type == "purchase":
        return "purchase"
    if material.supply_type == "production":
        return "production"
    return "ambiguous"


def requirement_supply_type_for(demand):
    """Read formal order supply authority; material flags cannot replace it."""
    auxiliary = {
        "materialId": demand.material_id,
        "isPurchased": demand.material.is_purchased,
        "isProduced": demand.material.is_produced,
    }
    if not demand.sales_order_item_id:
        if demand.source_type == "sales_order" or demand.source_document_type == "SalesOrderItem":
            raise PlanningBusinessError(
                "REQUIREMENT_SUPPLY_SOURCE_CONFLICT", "订单计划需求缺少正式订单行来源。", http_status=409,
            )
        resolved = supply_type_for(demand.material)
        return resolved, {
            "sourceAuthority": "MATERIAL_MASTER_AUXILIARY",
            "resolvedSupplyType": resolved,
            "materialFlagsAuxiliary": auxiliary,
        }

    from sales.supply_admission_service import supply_admission_facts

    item = demand.sales_order_item
    order = item.sales_order
    if (
        demand.source_type != "sales_order"
        or demand.source_document_type != "SalesOrderItem"
        or demand.source_document_id != str(item.pk)
        or demand.source_document_no != order.order_no
        or demand.material_id != item.material_id
        or demand.required_qty != item.quantity
        or demand.required_date != item.required_date
        or demand.material.company_id != order.company_id
        or demand.department.company_id != order.company_id
    ):
        raise PlanningBusinessError(
            "REQUIREMENT_SUPPLY_SOURCE_CONFLICT", "计划需求与订单行、物料、数量、日期或公司来源不一致。", http_status=409,
        )
    facts = supply_admission_facts(item)
    if facts["status"] != "CONFIRMED" and facts["factId"] is not None:
        raise PlanningBusinessError(
            "REQUIREMENT_SUPPLY_ADMISSION_INVALID", "订单供应确认来源或审计状态链无效，禁止用物料标志降级。",
            http_status=409, data={"salesOrderItemId": item.pk, "supplyAdmissionStatus": facts["status"]},
        )
    if facts["status"] == "CONFIRMED":
        resolved = {"MAKE": "production", "BUY": "purchase"}[facts["supplyBranch"]]
        return resolved, {
            "sourceAuthority": facts["factSource"],
            "salesOrderItemId": item.pk,
            "supplyAdmissionId": facts["factId"],
            "status": facts["status"],
            "supplyBranch": facts["supplyBranch"],
            "resolvedSupplyType": resolved,
            "confirmedBy": facts["confirmedBy"],
            "auditId": facts["auditId"],
            "stateMachineConsistent": facts["stateMachineConsistent"],
            "statusTransitionCount": facts["statusTransitionCount"],
            "materialFlagsAuxiliary": auxiliary,
        }
    # There is no independent root-order engineering supply-decision field.
    # BOM component supply and released manufacturing readiness are not MAKE/BUY.
    return "ambiguous", {
        "sourceAuthority": "UNRESOLVED_ORDER_SUPPLY",
        "salesOrderItemId": item.pk,
        "supplyAdmissionId": None,
        "status": facts["status"],
        "resolvedSupplyType": "ambiguous",
        "reason": facts["reason"],
        "materialFlagsAuxiliary": auxiliary,
    }


def available_inventory(material):
    value = InventoryBalance.objects.filter(material=material).aggregate(total=Sum("quantity"))["total"]
    return value or Decimal("0")


def _number(prefix, row):
    return f"{prefix}{date.today():%Y%m%d}{row.pk:04d}"


def _workflow_node(action_code):
    node = WorkflowNodeDefinition.objects.select_related("process_definition").filter(
        process_definition__definition_code=PROCESS_CODE,
        process_definition__active=True,
        business_action_code=action_code,
        active=True,
    ).order_by("sequence", "pk").first()
    if not node:
        return {"processCode": PROCESS_CODE, "nodeCode": "", "nodeName": ""}
    return {
        "processCode": PROCESS_CODE,
        "nodeCode": node.node_code,
        "nodeName": node.node_name,
        "sequence": node.sequence,
    }


def _procurement_workflow_actor(user, action_code):
    employee = getattr(user, "employee_profile", None)
    position = getattr(employee, "position_ref", None) if employee else None
    if not employee or employee.status != "active" or not position:
        raise PlanningBusinessError(
            "PROCUREMENT_ACTOR_EMPLOYEE_REQUIRED",
            "采购执行账户必须关联在职员工和正式采购岗位。",
            http_status=409,
        )
    node = WorkflowNodeDefinition.objects.select_related("process_definition").filter(
        process_definition__definition_code="PROCUREMENT_PURCHASE_REQUEST_TO_ORDER",
        process_definition__active=True,
        business_action_code=action_code,
        active=True,
    ).order_by("sequence", "pk").first()
    mapping = PositionWorkflowResponsibility.objects.select_related(
        "responsibility", "position", "workflow_node"
    ).filter(
        workflow_node=node,
        position=position,
        active=True,
    ).order_by("pk").first() if node else None
    if not node or not mapping:
        raise PlanningBusinessError(
            "PROCUREMENT_WORKFLOW_RESPONSIBILITY_DENIED",
            "当前员工岗位未承担采购申请创建流程责任。",
            http_status=403,
        )
    return employee, position, node, mapping


def _purchase_request_number():
    prefix = f"PR{date.today():%Y%m%d}"
    latest = PurchaseRequest.objects.filter(request_no__startswith=prefix).order_by("-request_no").first()
    suffix = str(latest.request_no)[len(prefix):] if latest else ""
    sequence = int(suffix) + 1 if suffix.isdigit() else 1
    return f"{prefix}{sequence:04d}"


def _current_price_candidates(material, on_date):
    return list(SupplierMaterialPrice.objects.select_related("supplier").filter(
        material=material,
        supplier__is_active=True,
        status="ACTIVE",
        effective_date__lte=on_date,
    ).filter(
        models.Q(expiry_date__isnull=True) | models.Q(expiry_date__gte=on_date)
    ).order_by("supplier_id", "currency", "confirmed_at", "created_at", "price_no", "id"))


@transaction.atomic
def convert_purchase_plan_to_request(*, user, purchase_plan_id, authorization):
    plan = PurchasePlan.objects.select_for_update().select_related(
        "planning_requirement__demand__department", "material"
    ).filter(pk=purchase_plan_id).first()
    if not plan:
        raise PlanningBusinessError("PURCHASE_PLAN_NOT_FOUND", "采购计划不存在。", http_status=404)
    existing = PurchaseRequest.objects.select_for_update().filter(source_purchase_plan=plan).first()
    if existing:
        raise PlanningBusinessError(
            "PURCHASE_PLAN_ALREADY_CONVERTED",
            f"采购计划已由采购申请 {existing.request_no} 全量承接，不得重复生成。",
            http_status=409,
            data={"purchaseRequestId": existing.pk, "purchaseRequestNo": existing.request_no},
        )
    requirement = plan.planning_requirement
    demand = requirement.demand
    if plan.status != "confirmed":
        raise PlanningBusinessError(
            "PURCHASE_PLAN_STATUS_INVALID", "只有已确认且尚未承接的采购计划允许生成采购申请。", http_status=409
        )
    if plan.net_required_qty <= 0:
        raise PlanningBusinessError("PURCHASE_PLAN_QTY_INVALID", "采购计划净需求必须大于 0。", http_status=409)
    if requirement.supply_type != "purchase":
        raise PlanningBusinessError("PURCHASE_PLAN_SUPPLY_TYPE_INVALID", "来源计划需求不是采购供应类型。", http_status=409)
    if not plan.material_id or not plan.material.is_active or not plan.material.is_purchased:
        raise PlanningBusinessError("PURCHASE_PLAN_MATERIAL_INVALID", "采购计划物料不存在、已停用或不是采购件。", http_status=409)
    if requirement.material_id != plan.material_id or demand.material_id != plan.material_id:
        raise PlanningBusinessError("PURCHASE_PLAN_SOURCE_MATERIAL_MISMATCH", "需求、计划需求与采购计划物料不一致。", http_status=409)
    if not demand.department_id or requirement.status != "confirmed" or demand.status != "confirmed":
        raise PlanningBusinessError("PURCHASE_PLAN_SOURCE_INVALID", "采购计划上游需求链状态或部门事实无效。", http_status=409)

    employee, position, node, mapping = _procurement_workflow_actor(
        user, "procurement.purchase_request.create"
    )
    purchase_department = position.department
    business_date = date.today()
    current_prices = _current_price_candidates(plan.material, business_date)
    purchase_mode = "AGREED_PRICE" if current_prices else "STANDARD"
    request_value = PurchaseRequest.objects.create(
        request_no=_purchase_request_number(),
        request_date=business_date,
        requester=employee.full_name,
        requester_employee_id=employee.pk,
        requester_employee_no=employee.employee_no,
        department=demand.department.name,
        department_master=demand.department,
        usage_department=demand.department.name,
        usage_department_master=demand.department,
        purchase_department=purchase_department.name,
        purchase_department_master=purchase_department,
        request_type="other",
        source_type="PurchasePlan",
        source_purchase_plan=plan,
        purchase_mode=purchase_mode,
        application_reason=f"采购计划 {plan.plan_no} 正式承接",
        purchase_purpose="计划驱动采购执行",
        note_description="系统流程验收数据 / PCE计划驱动采购V1.0",
        required_date=plan.required_date,
        quantity=plan.net_required_qty,
        amount=Decimal("0"),
        status="draft",
        approval_status="not_submitted",
        approval_current_node="申请人起草",
    )
    item = PurchaseRequestItem.objects.create(
        purchase_request=request_value,
        material=plan.material,
        material_code=plan.material.code,
        material_name=plan.material.name,
        specification=plan.material.specification or "",
        unit=plan.material.purchase_unit or plan.material.unit,
        material_category=plan.material.category.name if plan.material.category_id else "",
        purchase_attribute="可采购",
        demand_reason=demand.reason,
        purchase_remark=f"来源采购计划 {plan.plan_no}",
        quantity=plan.net_required_qty,
        required_date=plan.required_date,
        remark="计划净需求全量承接；采购申请阶段不重新计算库存或净需求。",
        line_no=1,
    )
    request_value.items = [{
        "lineNo": 1,
        "purchaseRequestItemId": item.pk,
        "materialId": plan.material_id,
        "materialCode": plan.material.code,
        "materialName": plan.material.name,
        "quantity": str(plan.net_required_qty),
        "requiredDate": plan.required_date.isoformat(),
        "sourcePurchasePlanId": plan.pk,
        "sourcePurchasePlanNo": plan.plan_no,
    }]
    request_value.save(update_fields=["items", "updated_at"])
    plan.status = "released"
    plan.save(update_fields=["status", "updated_at"])
    audit = record_action_audit(
        user=user,
        action_code="procurement.purchase_request.create",
        organization_id=demand.department.company_id,
        target_type="PurchaseRequest",
        target_id=request_value.pk,
        target_no=request_value.request_no,
        before={
            "purchasePlanNo": plan.plan_no,
            "purchasePlanStatus": "confirmed",
            "convertedQty": "0.0000",
        },
        after={
            "purchasePlanNo": plan.plan_no,
            "purchasePlanStatus": plan.status,
            "purchaseRequestNo": request_value.request_no,
            "purchaseRequestStatus": request_value.status,
            "convertedQty": str(request_value.quantity),
            "remainingQty": "0.0000",
            "purchaseMode": purchase_mode,
            "workflowResponsibility": {
                "nodeCode": node.node_code,
                "positionCode": position.code,
                "responsibilityCode": mapping.responsibility.code if mapping.responsibility else "",
                "ownershipType": mapping.ownership_type,
            },
            "priceCandidates": [row.price_no for row in current_prices],
            "inventoryWriteCount": 0,
        },
        authorization=authorization,
        reason="系统流程验收数据 / 采购计划转采购申请 V1.0",
    )
    return request_value, audit


def _actor(user):
    employee = getattr(user, "employee_profile", None)
    position = getattr(employee, "position_ref", None) if employee else None
    return {
        "account": user.username,
        "employeeNo": employee.employee_no if employee else "",
        "employeeName": employee.full_name if employee else "",
        "positionCode": position.code if position else "",
        "positionName": position.name if position else "",
    }


def record_audit(*, user, action_code, target, target_type, target_no, before, after, authorization):
    common = {
        "actor": _actor(user),
        "workflowNode": _workflow_node(action_code),
        "authorization": {
            "allowed": authorization.get("allowed", False),
            "decisionCode": authorization.get("decisionCode", ""),
            "roleCodes": authorization.get("roleCodes", []),
            "permissionCodes": authorization.get("permissionCodes", []),
            "authoritySource": authorization.get("authoritySource", ""),
        },
    }
    return OrganizationOperatingAuditRecord.objects.create(
        action_code=action_code,
        actor=user,
        organization=Company.objects.get(pk=user.company_id),
        target_type=target_type,
        target_id=target.pk,
        target_label=target_no,
        reason="系统流程验收数据 / 计划主链 V1.0",
        before_snapshot={**common, "state": before},
        after_snapshot={**common, "state": after},
    )


@transaction.atomic
def create_manual_demand(*, user, payload, authorization):
    material = Material.objects.filter(
        pk=payload.get("materialId"), is_active=True, company_id=user.company_id
    ).first()
    if not material:
        raise PlanningBusinessError("MATERIAL_INVALID", "物料不存在、已停用或不属于当前组织。")
    department = Department.objects.filter(
        pk=payload.get("departmentId"), is_active=True, company_id=user.company_id
    ).first()
    if not department:
        raise PlanningBusinessError("DEPARTMENT_INVALID", "需求部门不存在、已停用或不属于当前组织。")
    try:
        required_qty = Decimal(str(payload.get("requiredQty") or "0"))
    except Exception as exc:
        raise PlanningBusinessError("REQUIRED_QTY_INVALID", "需求数量必须是有效数字。") from exc
    if required_qty <= 0:
        raise PlanningBusinessError("REQUIRED_QTY_INVALID", "需求数量必须大于 0。")
    required_date = payload.get("requiredDate")
    if not required_date:
        raise PlanningBusinessError("REQUIRED_DATE_REQUIRED", "需求日期不能为空。")
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise PlanningBusinessError("DEMAND_REASON_REQUIRED", "需求原因不能为空。")
    row = Demand.objects.create(
        demand_no=f"TMP-DM-{timezone.now().timestamp()}",
        source_type="manual_demand",
        source_document_type="ManualDemand",
        source_document_id="pending",
        source_document_no="pending",
        material=material,
        required_qty=required_qty,
        required_date=required_date,
        department=department,
        reason=reason,
        acceptance_marker=str(payload.get("acceptanceMarker") or "").strip(),
        status="draft",
        created_by=user,
    )
    row.demand_no = _number("DM", row)
    row.source_document_id = str(row.pk)
    row.source_document_no = row.demand_no
    row.full_clean()
    row.save(update_fields=["demand_no", "source_document_id", "source_document_no", "updated_at"])
    audit = record_audit(
        user=user,
        action_code="planning.demand.create",
        target=row,
        target_type="Demand",
        target_no=row.demand_no,
        before={},
        after={"demandNo": row.demand_no, "status": row.status, "requiredQty": str(row.required_qty)},
        authorization=authorization,
    )
    return row, audit


def _idempotency_facts(payload):
    request_id = str(payload.get("requestId") or "").strip()
    idempotency_key = str(payload.get("idempotencyKey") or "").strip()
    if not request_id or not idempotency_key:
        raise PlanningBusinessError(
            "PLANNING_IDEMPOTENCY_REQUIRED",
            "计划运行必须提供 Request ID 和 Idempotency Key。",
        )
    return request_id, idempotency_key


@transaction.atomic
def generate_mps_proposal(*, user, payload, authorization):
    if not order_planning_schema_ready():
        raise PlanningBusinessError(
            "ORDER_PLANNING_NOT_ENABLED",
            "订单计划链 V1 尚未在当前数据库启用。",
            http_status=409,
        )
    request_id, idempotency_key = _idempotency_facts(payload)
    existing = MasterProductionScheduleRun.objects.prefetch_related(
        "lines__demand_allocations"
    ).filter(company_id=user.company_id, idempotency_key=idempotency_key).first()
    if existing:
        return existing, None, True

    demands = Demand.objects.select_for_update().select_related(
        "sales_order_item__sales_order", "sales_order_item__uom", "material", "product_definition"
    ).filter(
        department__company_id=user.company_id,
        source_type="sales_order",
        status="confirmed",
        manufacturing_output__release_status="released_to_manufacturing",
        mps_allocation__isnull=True,
        sales_order_item__sales_order__status__in=(
            "manufacturing_ready", "in_progress", "delivering", "completed"
        ),
    )
    demand_ids = payload.get("demandIds") or []
    if demand_ids:
        demands = demands.filter(pk__in=demand_ids)
    demands = list(demands.order_by("required_date", "product_definition_id", "material_id", "id"))
    if not demands:
        raise PlanningBusinessError(
            "MPS_ELIGIBLE_DEMAND_REQUIRED",
            "没有制造准备完成且尚未进入主生产计划的订单需求。",
            http_status=409,
        )
    if demand_ids and len({int(value) for value in demand_ids}) != len(demands):
        raise PlanningBusinessError(
            "MPS_DEMAND_NOT_ELIGIBLE",
            "所选需求中存在未就绪、已计划或不属于当前组织的需求。",
            http_status=409,
        )

    run = MasterProductionScheduleRun.objects.create(
        run_no=f"TMP-MPS-{timezone.now().timestamp()}", company_id=user.company_id,
        request_id=request_id, idempotency_key=idempotency_key, created_by=user,
    )
    run.run_no = _number("MPS", run)
    run.save(update_fields=["run_no"])
    groups = {}
    for demand in demands:
        key = (
            demand.product_definition_id, demand.material_id, demand.sales_order_item.uom_id,
            demand.required_date, demand.sales_order_item.engineering_mode,
        )
        groups.setdefault(key, []).append(demand)
    for line_no, (key, group) in enumerate(groups.items(), 1):
        product_id, material_id, uom_id, required_date, engineering_mode = key
        line = MasterProductionScheduleLine.objects.create(
            run=run, line_no=line_no, product_definition_id=product_id,
            material_id=material_id, uom_id=uom_id, required_date=required_date,
            total_qty=sum((value.required_qty for value in group), Decimal("0")),
            engineering_mode=engineering_mode,
        )
        MPSDemandAllocation.objects.bulk_create([
            MPSDemandAllocation(
                mps_line=line, demand=value, allocated_qty=value.required_qty,
            ) for value in group
        ])
    audit = record_audit(
        user=user, action_code="planning.mps.generate", target=run,
        target_type="MasterProductionScheduleRun", target_no=run.run_no,
        before={}, after={
            "status": run.status, "demandIds": [value.pk for value in demands],
            "lineCount": len(groups), "requestId": request_id,
            "idempotencyKey": idempotency_key,
        }, authorization=authorization,
    )
    return run, audit, False


def _proposal_supply_type(bom_item):
    if bom_item.supply_type == "MAKE":
        return "MAKE", "形成生产建议（未下达）", ""
    if bom_item.supply_type == "BUY":
        return "BUY", "形成采购建议（未下单）", ""
    return "UNRESOLVED", "维护供应方式后重算", f"BOM供应方式 {bom_item.supply_type} 尚未形成唯一MAKE/BUY决策"


@transaction.atomic
def generate_mrp_proposal(*, user, mps_run_id, payload, authorization):
    if not order_planning_schema_ready():
        raise PlanningBusinessError(
            "ORDER_PLANNING_NOT_ENABLED",
            "订单计划链 V1 尚未在当前数据库启用。",
            http_status=409,
        )
    request_id, idempotency_key = _idempotency_facts(payload)
    existing = MaterialRequirementsPlanningRun.objects.prefetch_related("proposals").filter(
        company_id=user.company_id, idempotency_key=idempotency_key,
    ).first()
    if existing:
        if existing.mps_run_id != mps_run_id:
            raise PlanningBusinessError(
                "MRP_IDEMPOTENCY_CONFLICT", "该幂等键已用于其他MPS运行。", http_status=409,
            )
        return existing, None, True
    mps = MasterProductionScheduleRun.objects.select_for_update().prefetch_related(
        "lines__demand_allocations__demand__sales_order_item__sales_order",
        "lines__demand_allocations__demand__manufacturing_output__bom_version__items__material",
        "lines__demand_allocations__demand__manufacturing_output__bom_version__items__uom",
    ).filter(pk=mps_run_id, company_id=user.company_id).first()
    if not mps:
        raise PlanningBusinessError("MPS_RUN_NOT_FOUND", "主生产计划运行不存在。", http_status=404)
    if hasattr(mps, "mrp_run"):
        return mps.mrp_run, None, True

    run = MaterialRequirementsPlanningRun.objects.create(
        run_no=f"TMP-MRP-{timezone.now().timestamp()}", company_id=user.company_id,
        mps_run=mps, request_id=request_id, idempotency_key=idempotency_key,
        created_by=user,
    )
    run.run_no = _number("MRP", run)
    run.save(update_fields=["run_no"])
    inventory_total = {}
    inventory_remaining = {}
    proposal_line = 0
    blocked = False

    def inventory(material):
        if material.pk not in inventory_total:
            inventory_total[material.pk] = available_inventory(material)
            inventory_remaining[material.pk] = inventory_total[material.pk]
        return inventory_total[material.pk], inventory_remaining[material.pk]

    def create_proposal(*, line, demand, material, uom, required_qty, supply_type,
                        suggested_action, block_reason="", bom_version=None, bom_item=None):
        nonlocal proposal_line, blocked
        proposal_line += 1
        current, remaining = inventory(material)
        allocated = min(current if remaining == current else remaining, required_qty)
        inventory_remaining[material.pk] = max(remaining - allocated, Decimal("0"))
        net = max(required_qty - allocated, Decimal("0"))
        is_blocked = bool(block_reason) or supply_type == "UNRESOLVED"
        blocked = blocked or is_blocked
        return MaterialRequirementProposal.objects.create(
            mrp_run=run, line_no=proposal_line, mps_line=line, demand=demand,
            product_definition=demand.product_definition, material=material, uom=uom,
            source_bom_version=bom_version, source_bom_item=bom_item,
            required_qty=required_qty, current_inventory=current,
            allocated_inventory=allocated, net_requirement=net,
            required_date=demand.required_date, supply_type=supply_type,
            suggested_action=suggested_action, status="blocked" if is_blocked else "proposed",
            block_reason=block_reason,
            trace_facts={
                "salesOrderId": demand.sales_order_item.sales_order_id,
                "salesOrderItemId": demand.sales_order_item_id,
                "demandId": demand.pk, "mpsRunId": mps.pk, "mpsLineId": line.pk,
                "manufacturingOutputId": demand.manufacturing_output_id,
                "bomVersionId": bom_version.pk if bom_version else None,
                "bomItemId": bom_item.pk if bom_item else None,
                "inventorySource": "procurement.InventoryBalance",
                "inventoryWriteCount": 0,
            },
        )

    for line in mps.lines.all().order_by("line_no"):
        for allocation in line.demand_allocations.all().order_by("demand_id"):
            demand = allocation.demand
            output = demand.manufacturing_output
            if not output or output.release_status != "released_to_manufacturing":
                create_proposal(
                    line=line, demand=demand, material=demand.material, uom=demand.sales_order_item.uom,
                    required_qty=allocation.allocated_qty, supply_type="UNRESOLVED",
                    suggested_action="补齐正式制造输出/BOM后重算",
                    block_reason="订单需求未引用已发布的正式制造输出/BOM",
                )
                continue
            bom_version = output.bom_version
            bom_items = list(bom_version.items.filter(
                is_active=True,
            ).filter(
                models.Q(effective_from__isnull=True) | models.Q(effective_from__lte=demand.required_date),
            ).filter(
                models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=demand.required_date),
            ).select_related("material", "uom").order_by("line_no", "id"))
            if not bom_items:
                create_proposal(
                    line=line, demand=demand, material=demand.material, uom=demand.sales_order_item.uom,
                    required_qty=allocation.allocated_qty, supply_type="UNRESOLVED",
                    suggested_action="维护已发布BOM明细后重算",
                    block_reason="正式制造输出引用的BOM没有有效明细", bom_version=bom_version,
                )
                continue
            for bom_item in bom_items:
                required_qty = allocation.allocated_qty * bom_item.quantity
                supply_type, suggested_action, block_reason = _proposal_supply_type(bom_item)
                if bom_item.scrap_rate_status != "maintained":
                    supply_type, suggested_action = "UNRESOLVED", "维护损耗率后重算"
                    block_reason = "BOM损耗率尚未维护，禁止默认补零"
                elif bom_item.scrap_rate:
                    required_qty = required_qty / (Decimal("1") - bom_item.scrap_rate)
                create_proposal(
                    line=line, demand=demand, material=bom_item.material, uom=bom_item.uom,
                    required_qty=required_qty.quantize(Decimal("0.0001")),
                    supply_type=supply_type, suggested_action=suggested_action,
                    block_reason=block_reason, bom_version=bom_version, bom_item=bom_item,
                )
    if blocked:
        run.status = "blocked"
        run.save(update_fields=["status"])
    audit = record_audit(
        user=user, action_code="planning.mrp.generate", target=run,
        target_type="MaterialRequirementsPlanningRun", target_no=run.run_no,
        before={}, after={
            "status": run.status, "mpsRunId": mps.pk,
            "proposalCount": proposal_line, "requestId": request_id,
            "idempotencyKey": idempotency_key, "inventoryWriteCount": 0,
        }, authorization=authorization,
    )
    return run, audit, False


@transaction.atomic
def calculate_requirement(*, user, demand_id, authorization):
    demand = Demand.objects.select_for_update().select_related("material", "department").filter(pk=demand_id).first()
    if not demand:
        raise PlanningBusinessError("DEMAND_NOT_FOUND", "需求不存在。", http_status=404)
    existing = PlanningRequirement.objects.filter(demand=demand).first()
    if existing:
        return existing, None
    available = available_inventory(demand.material)
    net_required = max(demand.required_qty - available, Decimal("0"))
    supply_type, supply_resolution = requirement_supply_type_for(demand)
    row = create_business_object_with_initial_state(
        model=PlanningRequirement,
        initial_state="draft",
        requirement_no=f"TMP-REQ-{timezone.now().timestamp()}",
        demand=demand,
        material=demand.material,
        demand_qty=demand.required_qty,
        available_qty=available,
        net_required_qty=net_required,
        required_date=demand.required_date,
        supply_type=supply_type,
        calculation_facts={
            "supplyResolution": supply_resolution,
            "formula": "max(demandQty - availableInventory, 0)",
            "inventorySource": "procurement.InventoryBalance",
            "inventorySemantic": "AGGREGATE_SNAPSHOT_NOT_ORDER_ALLOCATION",
            "inventoryAllocationStatus": "UNALLOCATED_SNAPSHOT",
            "inventorySnapshotCapturedAt": timezone.now().isoformat(),
            "calculatedAt": timezone.now().isoformat(),
            "inventoryWriteCount": 0,
            "materialSupplyFacts": {
                "isPurchased": demand.material.is_purchased,
                "isProduced": demand.material.is_produced,
            },
        },
        created_by=user,
    )
    row.requirement_no = _number("REQ", row)
    row.full_clean()
    row.save(update_fields=["requirement_no", "updated_at"])
    audit_state = {
        "demandId": demand.pk,
        "demandNo": demand.demand_no,
        "demandQty": str(row.demand_qty),
        "availableQty": str(row.available_qty),
        "netRequiredQty": str(row.net_required_qty),
        "supplyType": row.supply_type,
        "supplyResolution": supply_resolution,
        "inventoryWriteCount": 0,
    }
    initialization_audit = record_audit(
        user=user,
        action_code="planning.requirement.calculate",
        target=row,
        target_type="PlanningRequirement",
        target_no=row.requirement_no,
        before={"status": ""},
        after={**audit_state, "status": "draft"},
        authorization=authorization,
    )
    record_projected_business_transition(
        object_type="PlanningRequirement",
        object_id=row.pk,
        source_state="",
        target_state="draft",
        action_code="planning.requirement.calculate",
        operator=user,
        reason=f"需求 {demand.demand_no} 的计划需求 {row.requirement_no} 状态初始化",
        audit_reference=f"OrganizationOperatingAuditRecord:{initialization_audit.pk}",
        allowed_transitions={("", "draft")},
    )
    audit = record_audit(
        user=user,
        action_code="planning.requirement.calculate",
        target=row,
        target_type="PlanningRequirement",
        target_no=row.requirement_no,
        before={"status": "draft"},
        after={**audit_state, "status": "calculated"},
        authorization=authorization,
    )
    transition_business_object(
        business_object=row,
        object_type="PlanningRequirement",
        source_state="draft",
        target_state="calculated",
        action_code="planning.requirement.calculate",
        operator=user,
        reason=f"需求 {demand.demand_no} 的计划需求 {row.requirement_no} 完成既有净需求计算",
        audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}",
        allowed_transitions={("draft", "calculated")},
        version_field=None,
    )
    return row, audit


@transaction.atomic
def confirm_supply_plan(*, user, requirement_id, authorization):
    requirement = PlanningRequirement.objects.select_for_update().select_related(
        "material", "demand"
    ).filter(pk=requirement_id).first()
    if not requirement:
        raise PlanningBusinessError("REQUIREMENT_NOT_FOUND", "计划需求不存在。", http_status=404)
    if requirement.net_required_qty <= 0:
        raise PlanningBusinessError(
            "NET_REQUIREMENT_ZERO", "净需求为 0，不生成采购计划或生产计划。", http_status=409
        )
    if requirement.supply_type == "ambiguous":
        raise PlanningBusinessError(
            "SUPPLY_TYPE_AMBIGUOUS",
            "物料采购/自制属性无法唯一分流，必须由物料主数据责任人确认。",
            http_status=409,
            data={"riskCode": "SUPPLY_TYPE_AMBIGUOUS", "riskOpen": True},
        )
    if requirement.supply_type == "purchase":
        existing = PurchasePlan.objects.filter(planning_requirement=requirement).first()
        if existing:
            return existing, None
        plan = PurchasePlan.objects.create(
            plan_no=f"TMP-PP-{timezone.now().timestamp()}",
            planning_requirement=requirement,
            material=requirement.material,
            required_qty=requirement.demand_qty,
            available_qty=requirement.available_qty,
            net_required_qty=requirement.net_required_qty,
            required_date=requirement.required_date,
            source_id=str(requirement.pk),
            planning_engine="DIRECT_V1",
            run_batch=f"DIRECT-{requirement.pk}",
            source_version="DIRECT-V1",
            status="confirmed",
            confirmed_by=user,
        )
        prefix, action_code, target_type = "PP", "planning.purchase_plan.confirm", "PurchasePlan"
        quantity = plan.net_required_qty
    else:
        existing = ProductionPlan.objects.filter(planning_requirement=requirement).first()
        if existing:
            return existing, None
        plan = create_business_object_with_initial_state(
            model=ProductionPlan,
            initial_state="draft",
            plan_no=f"TMP-MP-{timezone.now().timestamp()}",
            planning_requirement=requirement,
            material=requirement.material,
            planned_qty=requirement.net_required_qty,
            required_date=requirement.required_date,
            source_id=str(requirement.pk),
            planning_engine="DIRECT_V1",
            run_batch=f"DIRECT-{requirement.pk}",
            source_version="DIRECT-V1",
            confirmed_by=user,
        )
        prefix, action_code, target_type = "MP", "planning.production_plan.confirm", "ProductionPlan"
        quantity = plan.planned_qty
    plan.plan_no = _number(prefix, plan)
    plan.full_clean()
    plan.save(update_fields=["plan_no", "updated_at"])
    if isinstance(plan, ProductionPlan):
        audit_state = {
            "planNo": plan.plan_no,
            "sourceRequirementId": requirement.pk,
            "sourceRequirementNo": requirement.requirement_no,
            "demandId": requirement.demand_id,
            "demandNo": requirement.demand.demand_no,
            "planQty": str(quantity),
            "planningEngine": plan.planning_engine,
            "runBatch": plan.run_batch,
            "sourceVersion": plan.source_version,
            "mpsSourceId": plan.mps_source_id,
            "mrpSourceId": plan.mrp_source_id,
        }
        initialization_audit = record_audit(
            user=user,
            action_code=action_code,
            target=plan,
            target_type=target_type,
            target_no=plan.plan_no,
            before={"status": ""},
            after={**audit_state, "status": "draft"},
            authorization=authorization,
        )
        record_projected_business_transition(
            object_type=target_type,
            object_id=plan.pk,
            source_state="",
            target_state="draft",
            action_code=action_code,
            operator=user,
            reason=f"计划需求 {requirement.requirement_no} 的生产计划 {plan.plan_no} 状态初始化",
            audit_reference=f"OrganizationOperatingAuditRecord:{initialization_audit.pk}",
            allowed_transitions={("", "draft")},
        )
        audit = record_audit(
            user=user,
            action_code=action_code,
            target=plan,
            target_type=target_type,
            target_no=plan.plan_no,
            before={"status": "draft"},
            after={**audit_state, "status": "confirmed"},
            authorization=authorization,
        )
        transition_business_object(
            business_object=plan,
            object_type=target_type,
            source_state="draft",
            target_state="confirmed",
            action_code=action_code,
            operator=user,
            reason=f"计划需求 {requirement.requirement_no} 的生产计划 {plan.plan_no} 正式确认",
            audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}",
            allowed_transitions={("draft", "confirmed")},
            version_field=None,
        )
        # Production confirmation owns the plan lifecycle, not its source's.
        return plan, audit
    requirement.status = "confirmed"
    requirement.save(update_fields=["status", "updated_at"])
    audit = record_audit(
        user=user,
        action_code=action_code,
        target=plan,
        target_type=target_type,
        target_no=plan.plan_no,
        before={},
        after={
            "planNo": plan.plan_no,
            "sourceRequirementNo": requirement.requirement_no,
            "planQty": str(quantity),
            "status": plan.status,
            "planningEngine": plan.planning_engine,
            "runBatch": plan.run_batch,
            "sourceVersion": plan.source_version,
            "mpsSourceId": plan.mps_source_id,
            "mrpSourceId": plan.mrp_source_id,
        },
        authorization=authorization,
    )
    return plan, audit


def validation_for(requirement):
    demand = requirement.demand
    try:
        plan = requirement.purchase_plan
    except PurchasePlan.DoesNotExist:
        try:
            plan = requirement.production_plan
        except ProductionPlan.DoesNotExist:
            plan = None
    plan_qty = None
    if isinstance(plan, PurchasePlan):
        plan_qty = plan.net_required_qty
    elif isinstance(plan, ProductionPlan):
        plan_qty = plan.planned_qty
    expected_net = max(requirement.demand_qty - requirement.available_qty, Decimal("0"))
    purchase_request = None
    purchase_orders = []
    if isinstance(plan, PurchasePlan):
        try:
            purchase_request = plan.purchase_request
        except PurchaseRequest.DoesNotExist:
            purchase_request = None
        purchase_orders = list(purchase_request.purchase_orders.prefetch_related("items").all()) if purchase_request else []
    request_items = list(purchase_request.request_items.all()) if purchase_request else []
    order_items = [item for order in purchase_orders for item in order.items.all()]
    request_qty = sum((item.quantity for item in request_items), Decimal("0"))
    order_qty = sum((item.quantity for item in order_items), Decimal("0"))
    order_amount = sum((item.amount for item in order_items), Decimal("0"))
    return {
        "sourceComplete": bool(
            demand.source_document_type and demand.source_document_id and demand.source_document_no
        ),
        "materialValid": bool(requirement.material_id and requirement.material.is_active),
        "inventoryRead": requirement.calculation_facts.get("inventorySource") == "procurement.InventoryBalance",
        "netRequirementCorrect": requirement.net_required_qty == expected_net,
        "supplyTypeValid": requirement.supply_type in {"purchase", "production"},
        "planQuantityCorrect": plan_qty == requirement.net_required_qty if plan else False,
        "sourceTraceComplete": bool(plan and plan.source_id == str(requirement.pk)),
        "purchaseRequestExists": bool(purchase_request),
        "purchaseOrderExists": bool(purchase_orders),
        "purchaseRequestSourceComplete": bool(
            purchase_request and purchase_request.source_purchase_plan_id == getattr(plan, "pk", None)
        ),
        "quantityRelationCorrect": bool(
            purchase_request and request_qty == plan_qty
            and (not purchase_orders or order_qty == request_qty)
        ),
        "materialConsistent": bool(
            purchase_request
            and request_items
            and all(item.material_id == requirement.material_id for item in request_items)
            and all(item.material_id == requirement.material_id for item in order_items)
        ),
        "statusRelationCorrect": bool(
            purchase_request
            and plan.status == "released"
            and purchase_request.status in {"draft", "submitted", "approved", "converted", "closed"}
            and all(order.status in {"draft", "submitted", "approved", "reviewed", "final_approved",
                                     "received", "inspected", "stored", "closed"} for order in purchase_orders)
        ),
        "priceAdmissionValid": bool(
            purchase_orders and order_items
            and all(item.supplier_material_price_id and item.unit_price_snapshot is not None for item in order_items)
        ),
        "amountCorrect": bool(
            purchase_orders
            and order_amount == sum((order.total_amount for order in purchase_orders), Decimal("0"))
        ),
        "duplicateExecutionProtected": bool(
            not isinstance(plan, PurchasePlan)
            or PurchaseRequest.objects.filter(source_purchase_plan=plan).count() <= 1
        ),
        "inventoryUnchanged": requirement.calculation_facts.get("inventoryWriteCount") == 0,
        "readOnly": True,
        "businessWriteCount": 0,
    }
