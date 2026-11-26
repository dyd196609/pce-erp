from django.core.exceptions import ObjectDoesNotExist
from django.db import models, OperationalError, IntegrityError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from masterdata.models import Material
from system.authorization import AuthorizationService
from system.models import Department, OrganizationOperatingAuditRecord
from workflow_runtime.fact_loads import successful_fact_load_facts

from .models import (
    Demand, MasterProductionScheduleRun, MaterialRequirementsPlanningRun,
    PlanningRequirement, ProductionPlan, PurchasePlan,
)
from .services import (
    PlanningBusinessError,
    calculate_requirement,
    confirm_supply_plan,
    convert_purchase_plan_to_request,
    create_manual_demand,
    generate_mps_proposal,
    generate_mrp_proposal,
    validation_for,
)
from .schema import order_planning_schema_status
from .production_batch_preview import build_foundation_preview
from .quantity_semantics import planning_quantity_facts


def envelope(data=None, *, error=None, http_status=status.HTTP_200_OK):
    return Response({
        "success": error is None,
        "data": data,
        "error": error,
        "meta": {"module": "PLAN", "source": "server", "status": http_status},
    }, status=http_status)


def _related(obj, name):
    try:
        return getattr(obj, name)
    except ObjectDoesNotExist:
        return None


def source_document_fields(row):
    # Codes written by the native manual-demand and sales-demand services.
    # Unknown legacy codes remain unknown; never infer a type from its number.
    labels = {"SalesOrderItem": "销售订单（明细来源）", "ManualDemand": "人工需求",
              "BOMItem": "已发布BOM原料明细", "EngineeringMaterialRequirement": "正式工程材料需求明细"}
    code = row.source_document_type
    return {
        "sourceDocumentTypeLabel": labels.get(code),
        "sourceDocumentTypeStatus": "PROVIDED" if code in labels else (
            "UNKNOWN_TYPE" if code else "NOT_PROVIDED"
        ),
    }


def requirement_row(row):
    demand = row.demand
    purchase_plan = _related(row, "purchase_plan")
    production_plan = _related(row, "production_plan")
    plan = purchase_plan or production_plan
    plan_qty = purchase_plan.net_required_qty if purchase_plan else (
        production_plan.planned_qty if production_plan else None
    )
    quantity_facts = planning_quantity_facts(
        demand_qty=row.demand_qty, requirement=row, plan=plan,
    )
    purchase_request = _related(purchase_plan, "purchase_request") if purchase_plan else None
    purchase_orders = list(purchase_request.purchase_orders.select_related("supplier").all()) if purchase_request else []
    return {
        "id": row.pk,
        "requirementNo": row.requirement_no,
        "demandId": demand.pk,
        "demandNo": demand.demand_no,
        "sourceType": demand.source_type,
        "sourceTypeLabel": demand.get_source_type_display(),
        "sourceDocumentType": demand.source_document_type,
        "sourceDocumentId": demand.source_document_id,
        "sourceDocumentNo": demand.source_document_no,
        **source_document_fields(demand),
        "materialId": row.material_id,
        "materialCode": row.material.code,
        "materialName": row.material.name,
        "departmentId": demand.department_id,
        "departmentCode": demand.department.code,
        "departmentName": demand.department.name,
        "demandQty": str(row.demand_qty),
        "availableQty": str(row.available_qty) if row.available_qty is not None else None,
        "netRequiredQty": None if row.calculation_facts.get("purchaseArrangement") else str(row.net_required_qty),
        "actualPurchaseQty": str(row.net_required_qty) if row.calculation_facts.get("purchaseArrangement") else None,
        "quantityFacts": quantity_facts,
        "inventorySnapshotQty": quantity_facts["inventorySnapshotQty"],
        "inventoryAllocationStatus": quantity_facts["inventoryAllocationStatus"],
        "effectiveInventoryCoverageQty": quantity_facts["effectiveInventoryCoverageQty"],
        "effectivePlanQty": quantity_facts["effectivePlanQty"],
        "pendingNetPlanQty": quantity_facts["pendingNetPlanQty"],
        "uncoveredDemandQty": quantity_facts["uncoveredDemandQty"],
        "requiredDate": row.required_date.isoformat(),
        "supplyType": row.supply_type,
        "supplyTypeLabel": row.get_supply_type_display(),
        "status": row.status,
        "statusLabel": ({"calculated":"已登记采购数量安排","confirmed":"采购数量安排已确认"}.get(row.status,row.get_status_display()) if row.calculation_facts.get("purchaseArrangement") else row.get_status_display()),
        "planType": "PurchasePlan" if purchase_plan else ("ProductionPlan" if production_plan else ""),
        "planId": plan.pk if plan else None,
        "planNo": plan.plan_no if plan else "",
        "planQty": str(plan_qty) if plan_qty is not None else "",
        "planStatus": plan.status if plan else "",
        "planStatusLabel": plan.get_status_display() if plan else "",
        "planningEngine": plan.planning_engine if plan else "",
        "runBatch": plan.run_batch if plan else "",
        "sourceVersion": plan.source_version if plan else "",
        "mpsSourceId": plan.mps_source_id if plan else "",
        "mrpSourceId": plan.mrp_source_id if plan else "",
        "purchaseRequestId": purchase_request.pk if purchase_request else None,
        "purchaseRequestNo": purchase_request.request_no if purchase_request else "",
        "purchaseRequestQty": str(purchase_request.quantity) if purchase_request else "",
        "purchaseRequestStatus": purchase_request.status if purchase_request else "",
        "purchaseRequestStatusLabel": purchase_request.get_status_display() if purchase_request else "",
        "purchaseMode": purchase_request.purchase_mode if purchase_request else "",
        "remainingPlanQty": str(max(
            (purchase_plan.net_required_qty if purchase_plan else 0)
            - (purchase_request.quantity if purchase_request else 0), 0
        )) if purchase_plan else "",
        "purchaseOrders": [{
            "id": order.pk,
            "poNo": order.po_no,
            "status": order.status,
            "statusLabel": order.get_status_display(),
            "supplierCode": order.supplier.code,
            "supplierName": order.supplier.name,
            "totalAmount": str(order.total_amount),
        } for order in purchase_orders],
        "calculationFacts": row.calculation_facts,
        "validation": validation_for(row),
    }


def demand_row(row):
    from .material_demand_service import source_fields
    material_source = source_fields(row)
    requirement = _related(row, "planning_requirement")
    purchase_plan = _related(requirement, "purchase_plan") if requirement else None
    production_plan = _related(requirement, "production_plan") if requirement else None
    plan = purchase_plan or production_plan
    quantity_facts = planning_quantity_facts(
        demand_qty=row.quantity_text, requirement=requirement, plan=plan,
    )
    item = row.sales_order_item if row.sales_order_item_id else None
    order = item.sales_order if item else None
    output = row.manufacturing_output
    readiness_status = (
        "READY"
        if item and output and output.release_status == "released_to_manufacturing"
        else "BLOCKED" if item else "NOT_APPLICABLE"
    )
    return {
        "id": row.pk,
        "demandNo": row.demand_no,
        "sourceType": row.source_type,
        "sourceTypeLabel": row.get_source_type_display(),
        "sourceDocumentType": row.source_document_type,
        "sourceDocumentId": row.source_document_id,
        "sourceDocumentNo": row.source_document_no,
        **material_source,
        **source_document_fields(row),
        "salesOrderItemId": row.sales_order_item_id,
        "salesOrderId": row.sales_order_item.sales_order_id if row.sales_order_item_id else None,
        "salesOrderNo": row.sales_order_item.sales_order.order_no if row.sales_order_item_id else "",
        "companyId": order.company_id if order else row.department.company_id,
        "customerId": order.customer_id if order else None,
        "customerName": order.customer.name if order else "",
        "productDefinitionId": row.product_definition_id,
        "productVersionId": row.product_version_id,
        "manufacturingOutputId": row.manufacturing_output_id,
        "productConfigurationId": item.product_configuration_id if item else None,
        "orderEngineeringInstanceId": output.order_engineering_instance_id if output else None,
        "engineeringMode": item.engineering_mode if item else "",
        "engineeringReadinessStatus": readiness_status,
        "engineeringReadinessSnapshot": {
            "source": "SalesOrderItem → ProductManufacturingOutput",
            "salesOrderItemId": item.pk if item else None,
            "manufacturingOutputId": row.manufacturing_output_id,
            "releaseStatus": output.release_status if output else "",
        },
        "uomId": material_source.get("uomId") if row.source_type == "production_material" else (item.uom_id if item else None),
        "uomCode": material_source.get("uomCode") if row.source_type == "production_material" else (item.uom.code if item and item.uom_id else ""),
        "materialId": row.material_id,
        "materialCode": row.material.code,
        "materialName": row.material.name,
        "requiredQty": row.quantity_text,
        "requiredDate": row.required_date.isoformat(),
        "customerRequiredDate": row.required_date.isoformat(),
        "committedDeliveryDate": str((order.delivery_information or {}).get("committedDeliveryDate") or "") if order else "",
        "plannedCompletionDate": str((order.delivery_information or {}).get("plannedCompletionDate") or "") if order else "",
        "departmentId": row.department_id,
        "departmentCode": row.department.code,
        "departmentName": row.department.name,
        "reason": row.reason,
        "acceptanceMarker": row.acceptance_marker,
        "status": row.status,
        "statusLabel": row.get_status_display(),
        "requirementId": requirement.pk if requirement else None,
        "requirementNo": requirement.requirement_no if requirement else "",
        "availableQty": str(requirement.available_qty) if requirement else (None if row.source_type == "production_material" else ""),
        "netRequiredQty": str(requirement.net_required_qty) if requirement else (None if row.source_type == "production_material" else ""),
        "quantityFacts": quantity_facts,
        "inventorySnapshotQty": quantity_facts["inventorySnapshotQty"],
        "inventoryAllocationStatus": quantity_facts["inventoryAllocationStatus"],
        "effectiveInventoryCoverageQty": quantity_facts["effectiveInventoryCoverageQty"],
        "planId": plan.pk if plan else None,
        "planNo": plan.plan_no if plan else "",
        "planType": "PurchasePlan" if purchase_plan else ("ProductionPlan" if production_plan else ""),
        "planStatus": plan.status if plan else "",
        "plannedQty": quantity_facts["effectivePlanQty"],
        "effectivePlanQty": quantity_facts["effectivePlanQty"],
        "pendingPlanQty": quantity_facts["pendingNetPlanQty"],
        "pendingNetPlanQty": quantity_facts["pendingNetPlanQty"],
        "uncoveredDemandQty": quantity_facts["uncoveredDemandQty"],
        "overPlannedQty": quantity_facts["overPlannedQty"],
        "planningQuantityStatus": quantity_facts["netRequirementPlanCoverageStatus"],
        "orderCoverageStatus": quantity_facts["orderCoverageStatus"],
        "planStatusLabel": plan.get_status_display() if plan else "尚未生成",
    }


def mps_run_row(row):
    return {
        "id": row.pk, "runNo": row.run_no, "status": row.status,
        "statusLabel": row.get_status_display(), "sourceVersion": row.source_version,
        "createdAt": row.created_at.isoformat(),
        "lines": [{
            "id": line.pk, "lineNo": line.line_no,
            "productDefinitionId": line.product_definition_id,
            "productCode": line.product_definition.product_code if line.product_definition_id else "",
            "materialId": line.material_id, "materialCode": line.material.code,
            "materialName": line.material.name, "uomId": line.uom_id,
            "uomCode": line.uom.code if line.uom_id else "",
            "requiredDate": line.required_date.isoformat(), "totalQty": str(line.total_qty),
            "engineeringMode": line.engineering_mode,
            "demands": [{
                "demandId": allocation.demand_id,
                "demandNo": allocation.demand.demand_no,
                "allocatedQty": str(allocation.allocated_qty),
                "salesOrderId": allocation.demand.sales_order_item.sales_order_id,
                "salesOrderNo": allocation.demand.sales_order_item.sales_order.order_no,
                "salesOrderItemId": allocation.demand.sales_order_item_id,
            } for allocation in line.demand_allocations.all()],
        } for line in row.lines.all()],
    }


def mrp_run_row(row):
    return {
        "id": row.pk, "runNo": row.run_no, "mpsRunId": row.mps_run_id,
        "mpsRunNo": row.mps_run.run_no, "status": row.status,
        "statusLabel": row.get_status_display(), "sourceVersion": row.source_version,
        "createdAt": row.created_at.isoformat(),
        "proposals": [{
            "id": proposal.pk, "lineNo": proposal.line_no,
            "demandId": proposal.demand_id, "demandNo": proposal.demand.demand_no,
            "salesOrderId": proposal.demand.sales_order_item.sales_order_id,
            "salesOrderNo": proposal.demand.sales_order_item.sales_order.order_no,
            "salesOrderItemId": proposal.demand.sales_order_item_id,
            "productDefinitionId": proposal.product_definition_id,
            "productCode": proposal.product_definition.product_code if proposal.product_definition_id else "",
            "materialId": proposal.material_id, "materialCode": proposal.material.code,
            "materialName": proposal.material.name, "uomId": proposal.uom_id,
            "uomCode": proposal.uom.code if proposal.uom_id else "",
            "requiredQty": str(proposal.required_qty),
            "currentInventory": str(proposal.current_inventory) if proposal.current_inventory is not None else None,
            "allocatedInventory": str(proposal.allocated_inventory),
            "netRequirement": str(proposal.net_requirement),
            "requiredDate": proposal.required_date.isoformat(),
            "supplyType": proposal.supply_type,
            "supplyTypeLabel": proposal.get_supply_type_display(),
            "suggestedAction": proposal.suggested_action,
            "inventoryStatus": proposal.inventory_status,
            "status": proposal.status, "statusLabel": proposal.get_status_display(),
            "blockReason": proposal.block_reason,
            "sourceBomVersionId": proposal.source_bom_version_id,
            "sourceBomItemId": proposal.source_bom_item_id,
            "traceFacts": proposal.trace_facts,
        } for proposal in row.proposals.all()],
    }


class AuthorizedPlanningView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def authorize(self, request, action_code, department_id=None, business_object=None):
        object_facts = {
            "organizationId": str(request.user.company_id),
            "departmentId": department_id,
        }
        object_facts.update(business_object or {})
        decision = AuthorizationService.decide(
            user=request.user,
            action_code=action_code,
            organization_id=str(request.user.company_id),
            business_object=object_facts,
        )
        if not decision["allowed"]:
            return decision, envelope(
                data={"authorization": decision},
                error={"code": decision["decisionCode"], "message": decision["reason"]},
                http_status=status.HTTP_403_FORBIDDEN,
            )
        return decision, None

    def authorize_read_or_handoff(self, request, department_id=None):
        planning_decision, planning_denied = self.authorize(request, "planning.view", department_id)
        handoff_decision, handoff_denied = self.authorize(
            request,
            "procurement.purchase_request.create",
            department_id,
            {"ownerUserId": request.user.pk},
        )
        if planning_denied and handoff_denied:
            return planning_decision, handoff_decision, planning_denied
        return planning_decision, handoff_decision, None

    def fail(self, error):
        return envelope(
            data=error.data,
            error={"code": error.code, "message": error.message},
            http_status=error.http_status,
        )


class ProductionBatchFoundationPreviewView(APIView):
    """Read-only schema and deterministic scheduling examples; no write method."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return envelope({
            **build_foundation_preview(),
            "factLoadStatus": "success",
            "apiMode": "READ_ONLY_PREVIEW",
            "userValidated": False,
        })


class PlanningFactsView(AuthorizedPlanningView):
    def get(self, request):
        planning_decision, handoff_decision, denied = self.authorize_read_or_handoff(request)
        if denied:
            return denied
        demands = Demand.objects.select_related(
            "material", "department", "sales_order_item__uom",
            "sales_order_item__sales_order__customer", "manufacturing_output"
        ).filter(
            department__company_id=request.user.company_id
        ).order_by("-id")
        requirements = PlanningRequirement.objects.select_related(
            "demand__department", "material"
        ).filter(demand__department__company_id=request.user.company_id).order_by("-id")
        can_plan = planning_decision["allowed"]
        can_handoff = handoff_decision["allowed"]
        mps_decision = AuthorizationService.decide(
            user=request.user, action_code="planning.mps.generate",
            organization_id=str(request.user.company_id),
            business_object={"organizationId": str(request.user.company_id)},
        )
        mrp_decision = AuthorizationService.decide(
            user=request.user, action_code="planning.mrp.generate",
            organization_id=str(request.user.company_id),
            business_object={"organizationId": str(request.user.company_id)},
        )
        if not can_plan:
            requirements = requirements.filter(supply_type="purchase", purchase_plan__isnull=False)
            demands = demands.filter(planning_requirement__in=requirements)
        material_rows = Material.objects.filter(
            company_id=request.user.company_id, is_active=True
        ).order_by("code")
        department_rows = Department.objects.filter(
            company_id=request.user.company_id, is_active=True
        ).order_by("code")
        audit_rows = OrganizationOperatingAuditRecord.objects.filter(
            models.Q(action_code__startswith="planning.")
            | models.Q(action_code__in=[
                "procurement.purchase_request.create",
                "purchase_request.submit",
                "purchase_request.approve",
                "procurement.purchase_order.create",
            ]),
            organization_id=request.user.company_id,
        ).order_by("-id")[:30]
        planning_schema = order_planning_schema_status()
        planning_enabled = planning_schema["deployed"]
        mps_runs = []
        mrp_runs = []
        if planning_enabled:
            mps_runs = MasterProductionScheduleRun.objects.filter(
                company_id=request.user.company_id,
            ).prefetch_related(
                "lines__material", "lines__uom", "lines__product_definition",
                "lines__demand_allocations__demand__sales_order_item__sales_order",
            ).order_by("-id")
            mrp_runs = MaterialRequirementsPlanningRun.objects.filter(
                company_id=request.user.company_id,
            ).select_related("mps_run").prefetch_related(
                "proposals__demand__sales_order_item__sales_order", "proposals__product_definition",
                "proposals__material", "proposals__uom",
            ).order_by("-id")
        demands = list(demands)
        requirements = list(requirements)
        mps_runs = list(mps_runs)
        mrp_runs = list(mrp_runs)
        fact_load_facts = successful_fact_load_facts(
            result_count=len(demands) + len(requirements) + len(mps_runs) + len(mrp_runs),
            api_url="/api/planning/facts/",
            tenant_id=str(request.user.company_id),
            request=request,
        )
        common_facts = {
            "factSource": "server",
            "inventorySource": "procurement.InventoryBalance",
            "inventoryWriteCount": 0,
            "supplyTypeSource": "masterdata.Material.supply_type (derived from governed legacy columns)",
            "traceSource": "planning foreign keys",
            "readOnlyValidation": True,
            "orderPlanningV1SchemaEnabled": planning_enabled,
            "orderPlanningSchema": planning_schema,
            **fact_load_facts,
            "factLoadFacts": fact_load_facts,
        }
        try:
            demand_rows = [demand_row(row) for row in demands]
        except PlanningBusinessError as error:
            return self.fail(error)
        return envelope({
            "demands": demand_rows,
            "requirements": [requirement_row(row) for row in requirements],
            "mpsRuns": [mps_run_row(row) for row in mps_runs] if planning_enabled else None,
            "mrpRuns": [mrp_run_row(row) for row in mrp_runs] if planning_enabled else None,
            "materials": [{
                "id": row.pk,
                "code": row.code,
                "name": row.name,
                "unit": row.unit,
                "isPurchased": row.is_purchased,
                "isProduced": row.is_produced,
                "supplyType": row.supply_type,
                "supplyTypeLabel": row.supply_type_display,
            } for row in material_rows],
            "departments": [{"id": row.pk, "code": row.code, "name": row.name} for row in department_rows],
            "audits": [{
                "id": row.pk,
                "actionCode": row.action_code,
                "targetType": row.target_type,
                "targetId": row.target_id,
                "targetLabel": row.target_label,
                "actor": row.actor.username if row.actor else "",
                "createdAt": row.created_at.isoformat(),
            } for row in audit_rows],
            "authorization": planning_decision if can_plan else handoff_decision,
            "capabilities": {
                "canPlan": can_plan, "canConvertPurchasePlan": can_handoff,
                "canGenerateMps": planning_enabled and mps_decision["allowed"],
                "canGenerateMrp": planning_enabled and mrp_decision["allowed"],
            },
            "factLoadFacts": fact_load_facts,
            "apiFacts": common_facts,
            "pageFacts": common_facts,
            "diagnosticFacts": common_facts,
            "strictFacts": common_facts,
        })


class MPSGenerateView(AuthorizedPlanningView):
    def post(self, request):
        decision, denied = self.authorize(request, "planning.mps.generate")
        if denied:
            return denied
        try:
            run, audit, idempotent = generate_mps_proposal(
                user=request.user, payload=request.data or {}, authorization=decision,
            )
        except PlanningBusinessError as error:
            return self.fail(error)
        run = MasterProductionScheduleRun.objects.prefetch_related(
            "lines__material", "lines__uom", "lines__product_definition",
            "lines__demand_allocations__demand__sales_order_item__sales_order",
        ).get(pk=run.pk)
        return envelope({
            "mpsRun": mps_run_row(run), "auditId": audit.pk if audit else None,
            "idempotent": idempotent, "authorization": decision,
        })


class MRPGenerateView(AuthorizedPlanningView):
    def post(self, request, mps_run_id):
        decision, denied = self.authorize(request, "planning.mrp.generate")
        if denied:
            return denied
        try:
            run, audit, idempotent = generate_mrp_proposal(
                user=request.user, mps_run_id=mps_run_id,
                payload=request.data or {}, authorization=decision,
            )
        except PlanningBusinessError as error:
            return self.fail(error)
        run = MaterialRequirementsPlanningRun.objects.select_related("mps_run").prefetch_related(
            "proposals__demand__sales_order_item__sales_order", "proposals__product_definition",
            "proposals__material", "proposals__uom",
        ).get(pk=run.pk)
        return envelope({
            "mrpRun": mrp_run_row(run), "auditId": audit.pk if audit else None,
            "idempotent": idempotent, "authorization": decision,
        })


class DemandCreateView(AuthorizedPlanningView):
    def material_call(self, callback):
        from django.db import OperationalError, IntegrityError
        from pde.product_design_service import ProductDesignError
        from sales.manufacturing_input import ManufacturingInputError
        try:
            return envelope(callback())
        except PlanningBusinessError as error:
            return self.fail(error)
        except (ProductDesignError, ManufacturingInputError) as error:
            return envelope(error={"code": error.code, "message": error.message}, http_status=getattr(error, "http_status", 409))
        except OperationalError as error:
            concurrent = "locked" in str(error).lower()
            return envelope(error={"code": "MATERIAL_DEMAND_CONCURRENT_CHANGE" if concurrent else "MATERIAL_DEMAND_READ_FAILED",
                "message": "并发结果待核实，请查询同次动作，不自动重放。" if concurrent else "原正式来源读取失败，未取得当前事实。"}, http_status=409 if concurrent else 500)
        except IntegrityError:
            return envelope(error={"code": "MATERIAL_DEMAND_CONCURRENT_CHANGE", "message": "提交冲突，请查询同一次动作结果，不自动重放。"}, http_status=409)

    def get(self, request):
        from . import material_demand_service as native
        if request.query_params.get('sourceCandidates') is not None:
            allowed={'sourceCandidates','productionPlanId','rangeStart','rangeEnd'}
            if request.query_params.get('sourceCandidates')!='1' or set(request.query_params)-allowed:
                return envelope(error={'code':'MATERIAL_SOURCE_SELECTION_REQUIRED','message':'来源目录须明确计划及批准范围，不接受其他对象或客户端范围授权。'},http_status=400)
            try:
                plan_id=int(request.query_params.get('productionPlanId',''))
                if 'rangeStart' not in request.query_params and 'rangeEnd' not in request.query_params:
                    return self.material_call(lambda:native.source_scope(user=request.user,plan_id=plan_id))
                if any(name not in request.query_params for name in ['rangeStart','rangeEnd']):
                    raise ValueError()
            except (TypeError,ValueError):
                return envelope(error={'code':'MATERIAL_SOURCE_SELECTION_REQUIRED','message':'请选择准确生产计划及本次批准范围。'},http_status=400)
            return self.material_call(lambda:native.source_candidates(user=request.user,plan_id=plan_id,
                range_start=request.query_params['rangeStart'],range_end=request.query_params['rangeEnd']))
        if request.query_params.get('purchaseResultKey') is not None:
            from .material_purchase_service import result_query
            try: demand_id=int(request.query_params.get('demandId',''))
            except (TypeError,ValueError):
                return envelope(error={'code':'MATERIAL_PURCHASE_DEMAND_REQUIRED','message':'须选择准确需求。'},http_status=400)
            return self.material_call(lambda:result_query(user=request.user,demand_id=demand_id,key=request.query_params['purchaseResultKey']))
        if request.query_params.get('purchaseContext') == '1':
            from .material_purchase_service import context
            try: demand_id=int(request.query_params.get('demandId',''))
            except (TypeError,ValueError):
                return envelope(error={'code':'MATERIAL_PURCHASE_DEMAND_REQUIRED','message':'须选择准确需求。'},http_status=400)
            return self.material_call(lambda:context(user=request.user,demand_id=demand_id))
        if request.query_params.get("demandId") is not None and not request.query_params.get("resultKey"):
            try:
                demand_id=int(request.query_params["demandId"])
                selected={}
                for name in ["productionPlanId","sourceLineId","sourceObjectType","rangeStart","rangeEnd"]:
                    if name in request.query_params:
                        selected[name]=int(request.query_params[name]) if name in {"productionPlanId","sourceLineId"} else request.query_params[name]
            except (TypeError,ValueError):
                return envelope(error={"code":"MATERIAL_DEMAND_INPUT_INVALID","message":"须准确需求、生产计划及来源行身份。"},http_status=400)
            return self.material_call(lambda:native.action_context(user=request.user,demand_id=demand_id,selection=selected,
                expected_fingerprint=request.query_params.get("expectedSourceFingerprint",native.SOURCE_EXPECTATION_UNSET)))
        try:
            plan_id = int(request.query_params.get("productionPlanId", ""))
            if request.query_params.get("resultKey"):
                return self.material_call(lambda: native.result_query(user=request.user, plan_id=plan_id,
                    key=request.query_params["resultKey"], action=request.query_params.get("action")))
            selection = {"productionPlanId": plan_id, "sourceObjectType": request.query_params.get("sourceObjectType"),
                "sourceLineId": int(request.query_params.get("sourceLineId", "")),
                "rangeStart": request.query_params.get("rangeStart"), "rangeEnd": request.query_params.get("rangeEnd")}
        except (TypeError, ValueError):
            return envelope(error={"code": "MATERIAL_SOURCE_SELECTION_REQUIRED", "message": "须明确准确计划、来源对象及原料行。"}, http_status=400)
        return self.material_call(lambda: native.preview(user=request.user, selection=selection,
            expected_fingerprint=request.query_params.get("expectedSourceFingerprint",native.SOURCE_EXPECTATION_UNSET)))

    def post(self, request):
        if (request.data or {}).get("sourceType") == "production_material":
            from . import material_demand_service as native
            payload = dict(request.data)
            payload.pop("sourceType")
            action = payload.pop("action", None)
            key = payload.pop("idempotencyKey", None)
            if action not in {"register", "confirm"}:
                return envelope(error={"code": "MATERIAL_DEMAND_ACTION_INVALID", "message": "须明确登记或确认意图。"}, http_status=400)
            service = native.register if action == "register" else native.confirm
            return self.material_call(lambda: service(user=request.user, payload=payload, key=key))
        department_id = (request.data or {}).get("departmentId")
        decision, denied = self.authorize(request, "planning.demand.create", department_id)
        if denied:
            return denied
        try:
            row, audit = create_manual_demand(
                user=request.user, payload=request.data or {}, authorization=decision
            )
        except PlanningBusinessError as error:
            return self.fail(error)
        return envelope({"demand": demand_row(row), "auditId": audit.pk, "authorization": decision})


class RequirementCalculateView(AuthorizedPlanningView):
    def post(self, request, demand_id):
        demand = Demand.objects.filter(pk=demand_id).first()
        department_id = demand.department_id if demand else None
        decision, denied = self.authorize(request, "planning.requirement.calculate", department_id)
        if denied:
            return denied
        try:
            row, audit = calculate_requirement(
                user=request.user, demand_id=demand_id, authorization=decision, purchase_arrangement=request.data or {}
            )
        except (OperationalError,IntegrityError) as error:
            if not demand or demand.source_type!='production_material':raise
            concurrent=isinstance(error,IntegrityError) or 'locked' in str(error).lower()
            return envelope(error={'code':'MATERIAL_PURCHASE_CONCURRENT_CHANGE' if concurrent else 'MATERIAL_PURCHASE_WRITE_FAILED',
                'message':'并发结果待核，请查询同一次动作，不自动重放。' if concurrent else '供应安排提交失败，未取得成功事实。'},http_status=409 if concurrent else 500)
        except PlanningBusinessError as error:
            return self.fail(error)
        row = PlanningRequirement.objects.select_related("demand__department", "material").get(pk=row.pk)
        return envelope({
            "requirement": requirement_row(row),
            "auditId": audit.pk if audit else None,
            "idempotent": audit is None,
            "authorization": decision,
        })


class SupplyPlanConfirmView(AuthorizedPlanningView):
    def post(self, request, requirement_id):
        requirement = PlanningRequirement.objects.select_related("demand").filter(pk=requirement_id).first()
        department_id = requirement.demand.department_id if requirement else None
        action_code = "planning.production_plan.confirm" if (
            requirement and requirement.supply_type == "production"
        ) else "planning.purchase_plan.confirm"
        decision, denied = self.authorize(request, action_code, department_id)
        if denied:
            return denied
        try:
            plan, audit = confirm_supply_plan(
                user=request.user, requirement_id=requirement_id, authorization=decision
            )
        except PlanningBusinessError as error:
            return self.fail(error)
        return envelope({
            "plan": {
                "id": plan.pk,
                "type": plan.__class__.__name__,
                "planNo": plan.plan_no,
                "status": plan.status,
                "statusLabel": plan.get_status_display(),
            },
            "auditId": audit.pk if audit else None,
            "idempotent": audit is None,
            "authorization": decision,
        })


class PlanningValidationView(AuthorizedPlanningView):
    def get(self, request, requirement_id):
        decision, handoff_decision, denied = self.authorize_read_or_handoff(request)
        if denied:
            return denied
        if not decision["allowed"]:
            decision = handoff_decision
        row = PlanningRequirement.objects.select_related("demand__department", "material").filter(
            pk=requirement_id, demand__department__company_id=request.user.company_id
        ).first()
        if not row:
            return envelope(error={"code": "REQUIREMENT_NOT_FOUND", "message": "计划需求不存在。"}, http_status=404)
        if request.query_params.get("purchaseConfirmation") == "1":
            if row.demand.source_type != "production_material":
                return envelope(
                    error={"code": "MATERIAL_PURCHASE_CONTEXT_INAPPLICABLE", "message": "本条需求沿原供应计划确认流程办理。"},
                    http_status=400,
                )
            _, action_denied = self.authorize(request, "planning.purchase_plan.confirm", row.demand.department_id)
            if action_denied:
                return action_denied
            from .material_purchase_service import purchase_confirmation_context
            try:
                context = purchase_confirmation_context(user=request.user, requirement=row)
            except PlanningBusinessError as error:
                return self.fail(error)
            return envelope({"purchaseConfirmation": context, "facts": {"readOnly": True, "businessWriteCount": 0}})
        return envelope({
            "requirementNo": row.requirement_no,
            "validation": validation_for(row),
            "facts": {"readOnly": True, "businessWriteCount": 0},
            "authorization": decision,
        })


class PlanningTraceView(AuthorizedPlanningView):
    def get(self, request):
        decision, handoff_decision, denied = self.authorize_read_or_handoff(request)
        if denied:
            return denied
        if not decision["allowed"]:
            decision = handoff_decision
        reference = str(request.query_params.get("reference") or "").strip()
        rows = PlanningRequirement.objects.select_related("demand__department", "material").filter(
            demand__department__company_id=request.user.company_id
        )
        if reference:
            rows = rows.filter(
                models.Q(requirement_no=reference)
                | models.Q(demand__demand_no=reference)
                | models.Q(demand__sales_order_item__sales_order__order_no=reference)
                | models.Q(purchase_plan__plan_no=reference)
                | models.Q(purchase_plan__purchase_request__request_no=reference)
                | models.Q(purchase_plan__purchase_request__purchase_orders__po_no=reference)
                | models.Q(production_plan__plan_no=reference)
            ).distinct()
        traces = []
        for row in rows:
            purchase_plan = _related(row, "purchase_plan")
            production_plan = _related(row, "production_plan")
            plan = purchase_plan or production_plan
            purchase_request = _related(purchase_plan, "purchase_request") if purchase_plan else None
            purchase_orders = list(purchase_request.purchase_orders.all()) if purchase_request else []
            traces.append({
                "source": {"type": row.demand.source_document_type, "id": row.demand.source_document_id, "no": row.demand.source_document_no,
                           "salesOrderId": row.demand.sales_order_item.sales_order_id if row.demand.sales_order_item_id else None,
                           "salesOrderNo": row.demand.sales_order_item.sales_order.order_no if row.demand.sales_order_item_id else ""},
                "demand": {"id": row.demand_id, "no": row.demand.demand_no},
                "requirement": {"id": row.pk, "no": row.requirement_no},
                "plan": {"type": plan.__class__.__name__, "id": plan.pk, "no": plan.plan_no} if plan else None,
                "purchaseRequest": ({"id": purchase_request.pk, "no": purchase_request.request_no}
                                    if purchase_request else None),
                "purchaseOrders": [{"id": order.pk, "no": order.po_no} for order in purchase_orders],
                "bidirectional": bool(
                    plan and plan.source_id == str(row.pk)
                    and (not purchase_request or purchase_request.source_purchase_plan_id == purchase_plan.pk)
                    and all(order.source_purchase_request_id == purchase_request.pk for order in purchase_orders)
                ),
            })
        return envelope({"traces": traces, "readOnly": True, "authorization": decision})


class PurchasePlanConvertView(AuthorizedPlanningView):
    def post(self, request, purchase_plan_id):
        plan = PurchasePlan.objects.select_related("planning_requirement__demand").filter(
            pk=purchase_plan_id
        ).first()
        department_id = plan.planning_requirement.demand.department_id if plan else None
        decision, denied = self.authorize(
            request,
            "procurement.purchase_request.create",
            department_id,
            {"ownerUserId": request.user.pk},
        )
        if denied:
            return denied
        try:
            purchase_request, audit = convert_purchase_plan_to_request(
                user=request.user,
                purchase_plan_id=purchase_plan_id,
                authorization=decision,
            )
        except PlanningBusinessError as error:
            return self.fail(error)
        return envelope({
            "purchaseRequest": {
                "id": purchase_request.pk,
                "requestNo": purchase_request.request_no,
                "status": purchase_request.status,
                "statusLabel": purchase_request.get_status_display(),
                "sourcePurchasePlanId": purchase_request.source_purchase_plan_id,
                "sourcePurchasePlanNo": purchase_request.source_purchase_plan.plan_no,
                "quantity": str(purchase_request.quantity),
                "purchaseMode": purchase_request.purchase_mode,
            },
            "auditId": audit.pk,
            "authorization": decision,
        })


# Native formal continuation: individually restored symbols; existing proofs preserved.
from django.db import DatabaseError, models

from workflow_runtime.fact_loads import failed_fact_load_facts, successful_fact_load_facts

from .services import (
    PlanningBusinessError,
    calculate_requirement,
    confirm_supply_plan,
    convert_purchase_plan_to_request,
    create_manual_demand,
    generate_mps_proposal,
    generate_mrp_proposal,
    read_production_plan_start_date,
    save_production_plan_start_date,
    validation_for,
)

class ProductionPlanStartDateView(AuthorizedPlanningView):
    """Bounded plan metadata maintenance; never creates a schedule or occupancy."""

    def failure(self, code, message, http_status):
        facts = failed_fact_load_facts(request=self.request, api_url=self.request.path,
            http_status=http_status, error_code=code, error_message=message,
            tenant_id=str(self.request.user.company_id) if getattr(self.request.user, "company_id", None) else None)
        surface = {**facts, "passed": False, "resultCount": None,
                   "businessWriteCount": 0, "auditWriteCount": 0,
                   "productionScheduleCreatedCount": 0, "resourceOccupancyCreatedCount": 0}
        return envelope({**surface, "factLoadFacts": facts,
                         **{key: dict(surface) for key in (
                             "apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts")}},
                        error={"code": code, "message": message}, http_status=http_status)

    def handle_exception(self, exc):
        from rest_framework.exceptions import APIException
        if isinstance(exc, APIException):
            return self.failure(str(getattr(exc, "default_code", "API_ERROR")), str(exc.detail), exc.status_code)
        return super().handle_exception(exc)

    def result(self, start_date_facts, *, audit=None, saved=False):
        loaded = successful_fact_load_facts(request=self.request, result_count=1,
            api_url=self.request.path, tenant_id=str(start_date_facts["companyId"]))
        surface = {**loaded, "passed": True, "resultCount": 1,
                   "startDateFacts": start_date_facts,
                   "businessWriteCount": int(audit is not None), "auditWriteCount": int(audit is not None),
                   "productionScheduleCreatedCount": 0, "resourceOccupancyCreatedCount": 0}
        return envelope({**surface, "plan": start_date_facts, "auditId": audit.pk if audit else None,
                         "idempotent": bool(saved and audit is None), "factLoadFacts": loaded,
                         **{key: dict(surface) for key in (
                             "apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts")}})

    def get(self, request, production_plan_id):
        try:
            facts = read_production_plan_start_date(user=request.user, production_plan_id=production_plan_id)
            return self.result(facts)
        except PlanningBusinessError as error:
            return self.failure(error.code, error.message, error.http_status)
        except DatabaseError:
            return self.failure("PLAN_START_DATE_READ_FAILED", "计划开始日期读取失败。", 503)

    def patch(self, request, production_plan_id):
        try:
            facts, audit = save_production_plan_start_date(
                user=request.user, production_plan_id=production_plan_id, payload=request.data)
            return self.result(facts, audit=audit, saved=True)
        except PlanningBusinessError as error:
            return self.failure(error.code, error.message, error.http_status)
        except DatabaseError:
            return self.failure("PLAN_START_DATE_SAVE_FAILED", "计划开始日期保存失败，未完成事务。", 503)
