from .read_scope import restrict_orders, view_evidence
from time import sleep
from django.db import OperationalError, connection
from pde.crm_sales_order_identity import formal_order_source_scope
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from decimal import Decimal, InvalidOperation

from masterdata.models import Material, UnitOfMeasure
from planning.quantity_semantics import planning_quantity_facts
from planning.models import Demand
from planning.views import demand_row
from planning.schema import order_planning_schema_ready
from pde.crm_order_admission import (
    CRMOrderAdmissionError,
    current_crm_sales_order_admission_facts,
    require_crm_order_admission,
)
from pde.crm_sales_order_identity import normalize_business_text, source_business_identity
from pde.models import (
    EngineeringDocumentVersion, OrderCrossFunctionalReview,
    ProductConfiguration, ProductDefinition, ProductManufacturingOutput,
)
from pfm.models import Employee
from system.authorization import AuthorizationService
from system.models import Department, OrganizationOperatingAuditRecord
from workflow_runtime.fact_loads import successful_fact_load_facts

from .models import Customer, SalesOrder, SalesOrderItemEngineeringAttribute
from .order_business_purpose_service import order_business_purpose_facts
from .source_intake import build_whole_house_intake_preview, commit_source_intake
from .source_review import perform_source_action
from .services import (
    SalesBusinessError, confirm_order, create_engineering_attribute, create_order,
    engineering_readiness_facts, generate_demand, order_business_classification,
    order_stage_readiness_facts, perform_order_action,
    transition_facts, update_order, update_order_item,
)
from .whole_house_preview import whole_house_order_preview


def envelope(data=None, error=None, http_status=200):
    return Response({"success": error is None, "data": data, "error": error, "meta": {"module": "SALES", "source": "server", "status": http_status}}, status=http_status)


def related(obj, name):
    try:
        return getattr(obj, name)
    except Exception:
        return None


def planning_sources(item):
    """Preserve every immutable source; never choose a version by ordering."""
    if item is None:
        return []
    if not hasattr(item, "_planning_sources"):
        item._planning_sources = list(Demand.objects.filter(sales_order_item=item).select_related(
            "manufacturing_output", "planning_requirement__purchase_plan",
            "planning_requirement__production_plan",
        ).order_by("pk"))
    return item._planning_sources


def single_planning_source(item):
    sources = planning_sources(item)
    return sources[0] if len(sources) == 1 else None


def planning_source_rows(item):
    result = []
    for demand in planning_sources(item):
        output = demand.manufacturing_output
        requirement = related(demand, "planning_requirement")
        plan = (related(requirement, "purchase_plan") or related(requirement, "production_plan")) if requirement else None
        result.append({
            "demandId": demand.pk, "demandNo": demand.demand_no,
            "statusLabel": demand.get_status_display(),
            "manufacturingOutputId": demand.manufacturing_output_id,
            "engineeringCalculationId": output.engineering_calculation_id if output else None,
            "orderEngineeringBaselineId": output.order_engineering_baseline_id if output else None,
            "routingVersionId": output.routing_version_id if output else None,
            "requirementId": requirement.pk if requirement else None,
            "planId": plan.pk if plan else None, "planNo": plan.plan_no if plan else "",
        })
    return result


def iso_value(value):
    return value.isoformat() if hasattr(value, "isoformat") else str(value or "")


def decimal_value(value):
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def delivery_facts(row, items):
    source = row.delivery_information if isinstance(row.delivery_information, dict) else {}
    source_batches = source.get("batches") if isinstance(source.get("batches"), list) else []
    batches = []
    unmatched_batches = []
    seen_batch_keys = set()
    for index, batch in enumerate(source_batches, 1):
        if not isinstance(batch, dict):
            continue
        item_id, line_no = batch.get("salesOrderItemId"), batch.get("lineNo")
        item_by_id = next((value for value in items if value.pk == item_id), None)
        item_by_line = next((value for value in items if value.line_no == line_no), None) if line_no is not None else None
        batch_no = str(batch.get("batchNo") or f"BATCH-{index}")
        batch_key = str(batch.get("id") or batch_no)
        issues = []
        if item_by_id and item_by_line and item_by_id.pk != item_by_line.pk:
            issues.append("订单行稳定ID与行号指向不同明细")
        item = item_by_id or item_by_line
        if item is None or issues:
            unmatched_batches.append({
                "sourceIndex": index, "batchNo": batch_no,
                "salesOrderItemId": item_id, "lineNo": line_no,
                "reason": issues[0] if issues else "未找到同一订单内匹配的有效明细",
            })
            continue
        if batch_key in seen_batch_keys:
            issues.append("交付批次标识重复")
        seen_batch_keys.add(batch_key)
        batch_uom = str(batch.get("uomCode") or (item.uom.code if item.uom_id else ""))
        if item.uom_id and batch_uom and batch_uom != item.uom.code:
            issues.append("交付批次单位与订单行单位不一致")
        quantity = decimal_value(batch.get("quantity"))
        actual_date = str(batch.get("actualDeliveryDate") or "")
        batches.append({
            "id": batch.get("id") or f"delivery-{row.pk}-{index}",
            "batchNo": batch_no,
            "salesOrderItemId": item.pk, "lineNo": item.line_no,
            "quantity": str(quantity), "uomCode": batch_uom,
            "customerRequiredDate": str(batch.get("customerRequiredDate") or iso_value(item.required_date)),
            "committedDeliveryDate": str(batch.get("committedDeliveryDate") or ""),
            "plannedCompletionDate": str(batch.get("plannedCompletionDate") or ""),
            "actualDeliveryDate": actual_date,
            "status": str(batch.get("status") or ("delivered" if actual_date else "planned")),
            "statusLabel": str(batch.get("statusLabel") or ("已交付" if actual_date else "待交付")),
            "associationStatus": "CONFLICT" if issues else "MATCHED",
            "associationIssues": issues,
        })
    line_facts = []
    for item in items:
        item_batches = [batch for batch in batches if batch["salesOrderItemId"] == item.pk]
        delivered_qty = sum((
            decimal_value(batch["quantity"])
            for batch in item_batches
            if batch["actualDeliveryDate"] and batch["associationStatus"] == "MATCHED"
        ), Decimal("0"))
        remaining_qty = max(item.quantity - delivered_qty, Decimal("0"))
        over_delivered_qty = max(delivered_qty - item.quantity, Decimal("0"))
        line_facts.append({
            "salesOrderItemId": item.pk, "lineNo": item.line_no,
            "orderedQty": str(item.quantity), "deliveredQty": str(delivered_qty),
            "remainingQty": str(remaining_qty),
            "overDeliveredQty": str(over_delivered_qty),
            "deliveryQuantityStatus": "OVER_DELIVERED" if over_delivered_qty > 0 else ("DELIVERED" if remaining_qty == 0 else "PENDING"),
            "uomCode": item.uom.code if item.uom_id else "",
            "customerRequiredDate": iso_value(item.required_date),
            "committedDeliveryDate": str(source.get("committedDeliveryDate") or ""),
            "batches": item_batches,
        })
    return {
        "source": "SalesOrder.delivery_information",
        "customerRequiredDate": iso_value(row.required_delivery_date),
        "committedDeliveryDate": str(source.get("committedDeliveryDate") or ""),
        "plannedCompletionDate": str(source.get("plannedCompletionDate") or ""),
        "actualDeliveryDate": str(source.get("actualDeliveryDate") or ""),
        "lines": line_facts, "batches": batches,
        "unmatchedBatches": unmatched_batches,
        "associationConflictCount": len(unmatched_batches) + sum(1 for batch in batches if batch["associationIssues"]),
    }


def order_row(row):
    planning_enabled = order_planning_schema_ready()
    items = list(row.items.select_related(
        "material", "uom", "product_definition__category", "product_version",
        "manufacturing_output", "product_configuration__template",
        "engineering_document_version__document",
    ).order_by("line_no", "id"))
    item = items[0] if items else None
    demand = single_planning_source(item)
    requirement = related(demand, "planning_requirement") if demand else None
    plan = related(requirement, "purchase_plan") if requirement else None
    readiness = engineering_readiness_facts(row)
    total_amount = sum((value.amount for value in items), 0)
    planning_lines = []
    for value in items:
        item_demand = single_planning_source(value)
        item_requirement = related(item_demand, "planning_requirement") if item_demand else None
        purchase_plan = related(item_requirement, "purchase_plan") if item_requirement else None
        production_plan = related(item_requirement, "production_plan") if item_requirement else None
        supply_plan = purchase_plan or production_plan
        quantity_facts = planning_quantity_facts(
            demand_qty=item_demand.required_qty if item_demand else value.quantity,
            requirement=item_requirement,
            plan=supply_plan,
        )
        allocation = related(item_demand, "mps_allocation") if item_demand and planning_enabled else None
        mps_line = allocation.mps_line if allocation else None
        mps_run = mps_line.run if mps_line else None
        mrp_run = related(mps_run, "mrp_run") if mps_run else None
        proposals = list(mrp_run.proposals.filter(demand=item_demand).select_related(
            "material", "uom", "source_bom_version",
        ).order_by("line_no")) if mrp_run else []
        planning_lines.append({
            "salesOrderItemId": value.pk,
            "planningSources": planning_source_rows(value),
            "sourceSelectionRequired": len(planning_sources(value)) > 1,
            "sourceSelectionMessage": "存在多个制造来源，请明确选择。" if len(planning_sources(value)) > 1 else "",
            "demandId": item_demand.pk if item_demand else None,
            "demandNo": item_demand.demand_no if item_demand else "",
            "demandStatus": item_demand.status if item_demand else "not_generated",
            "requiredQty": str(item_demand.required_qty) if item_demand else str(value.quantity),
            "requiredDate": iso_value(item_demand.required_date) if item_demand else iso_value(value.required_date),
            "requirementId": item_requirement.pk if item_requirement else None,
            "requirementNo": item_requirement.requirement_no if item_requirement else "",
            "availableQty": str(item_requirement.available_qty) if item_requirement else "",
            "netRequiredQty": str(item_requirement.net_required_qty) if item_requirement else "",
            "supplyType": item_requirement.supply_type if item_requirement else "",
            "supplyTypeLabel": item_requirement.get_supply_type_display() if item_requirement else "",
            "planId": supply_plan.pk if supply_plan else None,
            "planNo": supply_plan.plan_no if supply_plan else "",
            "plannedQty": quantity_facts["effectivePlanQty"],
            "effectivePlanQty": quantity_facts["effectivePlanQty"],
            "pendingPlanQty": quantity_facts["pendingNetPlanQty"],
            "pendingNetPlanQty": quantity_facts["pendingNetPlanQty"],
            "overPlannedQty": quantity_facts["overPlannedQty"],
            "inventorySnapshotQty": quantity_facts["inventorySnapshotQty"],
            "inventoryAllocationStatus": quantity_facts["inventoryAllocationStatus"],
            "effectiveInventoryCoverageQty": quantity_facts["effectiveInventoryCoverageQty"],
            "uncoveredDemandQty": quantity_facts["uncoveredDemandQty"],
            "orderCoverageStatus": quantity_facts["orderCoverageStatus"],
            "planningQuantityStatus": quantity_facts["netRequirementPlanCoverageStatus"],
            "planStatus": supply_plan.status if supply_plan else "not_generated",
            "mpsRunId": mps_run.pk if mps_run else None,
            "mpsRunNo": mps_run.run_no if mps_run else "",
            "mpsLineId": mps_line.pk if mps_line else None,
            "mpsQty": str(mps_line.total_qty) if mps_line else "",
            "mrpRunId": mrp_run.pk if mrp_run else None,
            "mrpRunNo": mrp_run.run_no if mrp_run else "",
            "mrpStatus": mrp_run.status if mrp_run else "not_generated",
            "mrpProposals": [{
                "id": proposal.pk, "materialCode": proposal.material.code,
                "materialName": proposal.material.name,
                "requiredQty": str(proposal.required_qty),
                "netRequirement": str(proposal.net_requirement),
                "uomCode": proposal.uom.code if proposal.uom_id else "",
                "supplyType": proposal.supply_type,
                "suggestedAction": proposal.suggested_action,
                "status": proposal.status, "blockReason": proposal.block_reason,
                "sourceBomVersionId": proposal.source_bom_version_id,
            } for proposal in proposals],
        })
    state_facts = {
        "engineeringStatus": (
            "制造准备完成" if row.status in {"manufacturing_ready", "in_progress", "delivering", "completed", "closed"}
            else "工程准备中" if row.status == "engineering" else "未进入"
        ),
        "manufacturingReadinessStatus": "已就绪" if readiness["manufacturingReady"] else (
            "不适用（BUY）" if readiness["lines"] and all(not value["manufacturingApplicable"] for value in readiness["lines"])
            else "未就绪"
        ),
        "deliveryStatus": "交付中" if row.status == "delivering" else ("已完成" if row.status in {"completed", "closed"} else "未交付"),
        "settlementStatus": "未集成",
    }
    delivery = delivery_facts(row, items)
    return {
        "id": row.pk, "orderNo": row.order_no, "customerId": row.customer_id,
        "customerCode": row.customer.code, "customerName": row.customer.name,
        "departmentId": row.department_id, "departmentCode": row.department.code, "departmentName": row.department.name,
        "orderDate": iso_value(row.order_date), "requiredDate": iso_value(row.required_delivery_date),
        "status": row.status, "statusLabel": row.get_status_display(), "version": row.version,
        "currency": row.currency, "projectReference": row.project_reference,
        "orderType": row.order_type, "orderTypeLabel": row.get_order_type_display(),
        "orderSource": row.order_source, "orderSourceLabel": row.get_order_source_display(),
        "businessPurpose": row.business_purpose,
        "businessPurposeLabel": (
            row.get_business_purpose_display() if row.business_purpose else "待确认"
        ),
        "businessPurposeFacts": order_business_purpose_facts(row),
        "totalAmount": str(total_amount),
        "contractReference": row.contract_reference,
        "salesOrganizationId": row.department_id,
        "salesOrganizationCode": row.department.code,
        "salesOrganizationName": row.department.name,
        "salesOwnerId": row.sales_owner_id,
        "salesOwnerEmployeeNo": row.sales_owner.employee_no if row.sales_owner_id else "",
        "salesOwnerName": row.sales_owner.full_name if row.sales_owner_id else "",
        "deliveryInformation": row.delivery_information,
        "deliveryFacts": delivery,
        "externalSourceNo": row.external_source_no, "remark": row.remark,
        "engineeringDocumentVersionId": row.engineering_document_version_id,
        "engineeringDocumentReference": (
            f"{row.engineering_document_version.document.document_no}/{row.engineering_document_version.document_version}"
            if row.engineering_document_version_id else ""
        ),
        "materialId": item.material_id if item else None, "materialCode": item.material.code if item else "",
        "materialName": item.material.name if item else "", "quantity": str(item.quantity) if item else "",
        "salesOrderItemId": item.pk if item else None, "demandId": demand.pk if demand else None,
        "demandNo": demand.demand_no if demand else "", "requirementId": requirement.pk if requirement else None,
        "requirementNo": requirement.requirement_no if requirement else "", "purchasePlanId": plan.pk if plan else None,
        "purchasePlanNo": plan.plan_no if plan else "", "purchaseRequestExists": bool(related(plan, "purchase_request")) if plan else False,
        "acceptanceMarker": row.acceptance_marker, "engineeringReadiness": readiness,
        "crmAdmission": current_crm_sales_order_admission_facts(row),
        "reviewLinks": [{
            "sourceRecordId": relation.review.source_record_id,
            "sourceVersion": relation.review.source_version,
            "sourceContentHash": relation.source_content_hash_snapshot,
            "relationId": relation.pk,
            "reviewId": relation.review_id,
            "reviewVersion": relation.review.review_version,
            "lineNos": [item.line_no_snapshot for item in relation.scope_items.all()],
        } for relation in row.order_review_relations.select_related("review").prefetch_related("scope_items")],
        "stageReadiness": order_stage_readiness_facts(row),
        "businessClassification": order_business_classification(row),
        "planningChain": {
            "lines": planning_lines,
            "demandCount": sum(1 for value in planning_lines if value["demandId"]),
            "mpsCount": len({value["mpsRunId"] for value in planning_lines if value["mpsRunId"]}),
            "mrpCount": len({value["mrpRunId"] for value in planning_lines if value["mrpRunId"]}),
        },
        **state_facts, **transition_facts(row),
        "items": [{
            "id": value.pk, "lineNo": value.line_no,
            "materialId": value.material_id, "materialCode": value.material.code,
            "materialName": value.material.name, "quantity": str(value.quantity),
            "uomId": value.uom_id, "uomCode": value.uom.code if value.uom_id else "",
            "requiredDate": iso_value(value.required_date),
            "productDefinitionId": value.product_definition_id,
            "productCode": value.product_definition.product_code if value.product_definition_id else "",
            "productVersionId": value.product_version_id,
            "productVersionNo": value.product_version.version_no if value.product_version_id else "",
            "manufacturingOutputId": value.manufacturing_output_id,
            "productConfigurationId": value.product_configuration_id,
            "productConfigurationNo": value.product_configuration.configuration_no if value.product_configuration_id else "",
            "engineeringMode": value.engineering_mode,
            "engineeringModeLabel": value.get_engineering_mode_display(),
            "spaceCode": value.space_code, "spaceName": value.space_name,
            "installationArea": value.installation_area,
            "componentCategory": value.component_category,
            "unitPrice": str(value.unit_price), "amount": str(value.amount),
            "taxRate": str(value.tax_rate), "priceTaxMode": value.price_tax_mode,
            "status": row.status, "statusLabel": row.get_status_display(),
            "productCategoryId": value.product_definition.category_id if value.product_definition_id else None,
            "productCategoryCode": (
                value.product_definition.category.code
                if value.product_definition_id and value.product_definition.category_id else ""
            ),
            "customerProductName": value.customer_product_name,
            "customerProductDescription": value.customer_product_description,
            "specification": value.specification,
            "configurationReference": value.configuration_reference,
            "engineeringRequirements": value.engineering_requirements,
            "qualityRequirements": value.quality_requirements,
            "remark": value.remark, "externalLineNo": value.external_line_no,
            "engineeringDocumentVersionId": value.engineering_document_version_id,
            "engineeringDocumentReference": (
                f"{value.engineering_document_version.document.document_no}/{value.engineering_document_version.document_version}"
                if value.engineering_document_version_id else ""
            ),
            "engineeringAttributes": [{
                "id": attribute.pk, "sequence": attribute.sequence,
                "rawSource": attribute.raw_source, "rawSheet": attribute.raw_sheet,
                "externalSource": attribute.external_source, "rawField": attribute.raw_field,
                "rawValue": attribute.raw_value, "canonicalField": attribute.canonical_field,
                "normalizedValue": attribute.normalized_value, "valueType": attribute.value_type,
                "unitId": attribute.unit_id, "unitCode": attribute.unit.code if attribute.unit_id else "",
                "sourceType": attribute.source_type,
                "engineeringDocumentVersionId": attribute.engineering_document_version_id,
            } for attribute in value.engineering_attributes.all()],
            "demandId": single_planning_source(value).pk if single_planning_source(value) else None,
            "demandNo": single_planning_source(value).demand_no if single_planning_source(value) else "",
            "planningSources": planning_source_rows(value),
            "sourceSelectionRequired": len(planning_sources(value)) > 1,
        } for value in items],
    }


def crm_order_admission_candidates(company_id):
    """Return only server-validated, unused CRM review sources.

    This is a read projection for order creation preparation. The write path
    still repeats the same authoritative gate inside sales.services.
    """

    candidates = []
    seen_sources = set()
    reviews = OrderCrossFunctionalReview.objects.select_related(
        "source_record",
    ).filter(
        company_id=company_id,
        review_type="CRM_ORDER_REVIEW",
        record_status="SUBMITTED",
        sales_order_relation__isnull=True,
    ).order_by("-review_version", "-pk")
    for review in reviews:
        identity = (
            review.source_record_id,
            review.source_order_no,
            review.source_version,
        )
        if identity in seen_sources:
            continue
        try:
            admission = require_crm_order_admission(
                company_id=company_id,
                source_record_id=review.source_record_id,
                source_order_no=review.source_order_no,
                source_version=review.source_version,
            )
        except CRMOrderAdmissionError:
            continue
        if admission.review_id != review.pk:
            continue
        identity_facts = source_business_identity(review.source_record, review)
        matching_customers = [
            customer for customer in Customer.objects.filter(
                company_id=company_id, is_active=True,
            ).order_by("pk")
            if normalize_business_text(customer.name)
            == normalize_business_text(identity_facts["customerName"])
        ]
        formal_scope = formal_order_source_scope(review.source_record)
        if (
            len(matching_customers) != 1
            or not identity_facts["projectReference"]
            or not isinstance(formal_scope, dict)
            or not isinstance(formal_scope.get("items"), list)
            or not formal_scope["items"]
        ):
            continue
        seen_sources.add(identity)
        candidates.append({
            "key": (
                f"{admission.source_record_id}:"
                f"{admission.source_version}:{admission.review_id}"
            ),
            **admission.as_dict(),
            "sourceNo": review.source_record.source_no,
            "sourceName": review.source_record.source_name,
            "sourceContentHash": review.source_content_hash,
            "customerId": matching_customers[0].pk,
            "customerName": matching_customers[0].name,
            "projectReference": identity_facts["projectReference"],
            "contractReference": identity_facts["contractReference"],
            "sourceBusinessIdentityStatusCode": "MATCH",
            "formalSalesOrderScope": formal_scope,
            "templateVersion": review.template_version,
            "defaultReviewScopeMode": "WHOLE_ORDER",
        })
    return candidates


class SalesBaseView(APIView):
    permission_classes=[permissions.IsAuthenticated]
    def authorize(self, request, action, department_id=None):
        decision=AuthorizationService.decide(user=request.user, action_code=action, organization_id=str(request.user.company_id), business_object={"organizationId": str(request.user.company_id), "departmentId": department_id})
        if action == "sales.order.view" and not view_evidence(request.user):
            decision = {**decision, "allowed": False, "decisionCode": "SALES_VIEW_SCOPE_DENIED", "reason": "当前账号无有效销售订单查看范围。"}
        return decision, None if decision["allowed"] else envelope({"authorization": decision}, {"code": decision["decisionCode"], "message": decision["reason"]}, 403)
    def fail(self, error): return envelope(error.data, {"code": error.code, "message": error.message}, error.http_status)


class SalesFactsView(SalesBaseView):
    def get(self, request):
        decision, denied=self.authorize(request, "sales.order.view")
        if denied: return denied
        orders=SalesOrder.objects.select_related(
            "customer", "department", "sales_owner", "engineering_document_version__document",
        ).prefetch_related(
            "items__material", "items__uom", "items__planning_demands",
            "items__product_definition__category", "items__product_version",
            "items__manufacturing_output", "items__engineering_document_version__document",
            "items__engineering_attributes__unit",
        ).filter(company_id=request.user.company_id)
        orders = restrict_orders(orders, request.user)
        search = str(request.query_params.get("search") or "").strip()
        if search:
            orders = orders.filter(Q(order_no__icontains=search) | Q(customer__code__icontains=search) | Q(customer__name__icontains=search) | Q(project_reference__icontains=search) | Q(items__material__code__icontains=search) | Q(items__material__name__icontains=search)).distinct()
        if request.query_params.get("status"):
            orders = orders.filter(status=request.query_params["status"])
        if request.query_params.get("customerId"):
            orders = orders.filter(customer_id=request.query_params["customerId"])
        if request.query_params.get("dateFrom"):
            orders = orders.filter(order_date__gte=request.query_params["dateFrom"])
        if request.query_params.get("dateTo"):
            orders = orders.filter(order_date__lte=request.query_params["dateTo"])
        ordering = request.query_params.get("ordering")
        if ordering in {"order_no", "-order_no", "order_date", "-order_date", "required_delivery_date", "-required_delivery_date", "created_at", "-created_at"}:
            orders = orders.order_by(ordering)
        action_codes = [
            "sales.order.create", "sales.order.update", "sales.order.submit", "sales.order.approve",
            "sales.order.engineering.start", "sales.order.engineering.complete",
            "sales.order.execution.start", "sales.order.delivery.start",
            "sales.order.complete", "sales.order.close", "sales.order.cancel",
            "sales.order.confirm", "sales.order.generate_demand", "sales.order.engineering_input.maintain",
        ]
        actions={code: AuthorizationService.decide(user=request.user, action_code=code, organization_id=str(request.user.company_id), business_object={"organizationId": str(request.user.company_id)}) for code in action_codes}
        audits=OrganizationOperatingAuditRecord.objects.filter(action_code__startswith="sales.order.", organization_id=request.user.company_id).order_by("-id")[:30]
        orders = list(orders)
        admission_candidates = crm_order_admission_candidates(
            request.user.company_id,
        )
        fact_load_facts = successful_fact_load_facts(
            result_count=len(orders),
            api_url="/api/sales/facts/",
            tenant_id=str(request.user.company_id),
            request=request,
        )
        common={"factSource":"server", "traceSource":"formal foreign keys", "inventoryWriteCount":0, "currentStateSource":"server", "purchaseRequestCreated":False, "purchaseOrderCreated":False, "crmAdmissionCandidateCount":len(admission_candidates), **fact_load_facts, "factLoadFacts": fact_load_facts}
        return envelope({
            "orders":[order_row(x) for x in orders],
            "crmAdmissionCandidates":admission_candidates,
            "customers":[{"id":x.pk,"code":x.code,"name":x.name} for x in Customer.objects.filter(company_id=request.user.company_id,is_active=True)],
            "materials":[{"id":x.pk,"code":x.code,"name":x.name,"baseUomId":x.base_uom_id,"specification":x.specification or ""} for x in Material.objects.filter(company_id=request.user.company_id,is_active=True)],
            "units":[{"id":x.pk,"code":x.code,"name":x.name} for x in UnitOfMeasure.objects.filter(company_id=request.user.company_id,is_active=True)],
            "products":[{"id":x.pk,"code":x.product_code,"name":x.product_name,"categoryId":x.category_id,"materialId":x.material_id,"mode":x.manufacturing_definition_mode} for x in ProductDefinition.objects.filter(company_id=request.user.company_id,is_active=True)],
            "productConfigurations":[{"id":x.pk,"configurationNo":x.configuration_no,"templateCode":x.template.template_code,"templateName":x.template.name,"status":x.status} for x in ProductConfiguration.objects.select_related("template").filter(template__company_id=request.user.company_id)],
            "manufacturingOutputs":[{"id":x.pk,"productId":x.product_id,"productVersionId":x.product_version_id,"releaseStatus":x.release_status,"definitionMode":x.definition_mode} for x in ProductManufacturingOutput.objects.filter(product__company_id=request.user.company_id)],
            "documentVersions":[{"id":x.pk,"documentNo":x.document.document_no,"version":x.document_version,"name":x.document_name} for x in EngineeringDocumentVersion.objects.select_related("document","related_product").filter(related_product__company_id=request.user.company_id)],
            "employees":[{"id":x.pk,"employeeNo":x.employee_no,"name":x.full_name} for x in Employee.objects.filter(status="active",department_ref__company_id=request.user.company_id)],
            "departments":[{"id":x.pk,"code":x.code,"name":x.name} for x in Department.objects.filter(company_id=request.user.company_id,is_active=True)],
            "sourceTypes":[value for value,_ in SalesOrderItemEngineeringAttribute.SOURCE_TYPE_CHOICES],
            "valueTypes":[value for value,_ in SalesOrderItemEngineeringAttribute.VALUE_TYPE_CHOICES],
            "capabilities":{k:v["allowed"] for k,v in actions.items()}, "authorization":decision,
            "audits":[{"id":x.pk,"actionCode":x.action_code,"targetType":x.target_type,"targetLabel":x.target_label,"actor":x.actor.username,"createdAt":x.created_at.isoformat()} for x in audits],
            "factLoadFacts":fact_load_facts,
            "apiFacts":common,"pageFacts":common,"diagnosticFacts":common,"strictFacts":common,
        })


class WholeHouseOrderPreviewView(SalesBaseView):
    def get(self, request):
        decision, denied = self.authorize(request, "sales.order.view")
        if denied:
            return denied
        preview = build_whole_house_intake_preview(request.user.company_id, request.user)
        return envelope({
            "preview": preview,
            "authorization": decision,
            **{key: preview[key] for key in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts")},
        })


class WholeHouseOrderSourceIntakeView(SalesBaseView):
    def get(self, request):
        decision, denied = self.authorize(request, "sales.order.view")
        if denied:
            return denied
        return envelope({
            "preview": build_whole_house_intake_preview(request.user.company_id, request.user),
            "authorization": decision,
        })

    def post(self, request):
        payload = dict(request.data or {})
        payload["idempotencyKey"] = request.headers.get("Idempotency-Key", "")
        payload["requestId"] = request.headers.get("X-Request-Id", "")
        decision, denied = self.authorize(request, "sales.order.create", payload.get("departmentId"))
        if denied:
            return denied
        try:
            row, audit, write_request, idempotent = commit_source_intake(
                user=request.user, resolver=payload, authorization=decision,
            )
        except SalesBusinessError as error:
            return self.fail(error)
        row = SalesOrder.objects.select_related("customer", "department").prefetch_related(
            "items__material", "items__uom",
        ).get(pk=row.pk)
        return envelope({
            "order": order_row(row),
            "auditId": audit.pk if audit else write_request.result.get("auditId"),
            "writeRequestId": write_request.pk,
            "idempotent": idempotent,
            "authorization": decision,
        }, http_status=status.HTTP_200_OK if idempotent else status.HTTP_201_CREATED)


class WholeHouseSourceActionView(SalesBaseView):
    def post(self, request, action):
        try:
            perform_source_action(user=request.user, action=action, payload=dict(request.data or {}))
        except SalesBusinessError as error:
            return self.fail(error)
        preview = build_whole_house_intake_preview(request.user.company_id, request.user)
        return envelope({"preview": preview, **{key: preview[key] for key in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts")}})


class SalesOrderCreateView(SalesBaseView):
    def post(self, request):
        decision, denied=self.authorize(request,"sales.order.create",(request.data or {}).get("departmentId"))
        if denied:return denied
        for attempt in range(4):
            try:
                row, item, audit = create_order(
                    user=request.user, payload=request.data or {}, authorization=decision,
                    business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
                )
                break
            except SalesBusinessError as error:
                return self.fail(error)
            except OperationalError as error:
                if (connection.vendor != "sqlite" or "locked" not in str(error).lower()
                        or str(request.data.get("orderSource") or "").lower() != "crm"):
                    raise
                if attempt == 3:
                    return envelope(error={"code": "CRM_ORDER_BUSY", "message": "来源正在建单，请刷新后核对订单。"}, http_status=409)
                sleep(0.05 * (attempt + 1))
        row=SalesOrder.objects.select_related("customer","department").prefetch_related("items__material").get(pk=row.pk)
        return envelope({"order":order_row(row),"auditId":audit.pk,"authorization":decision},http_status=status.HTTP_201_CREATED)

    def patch(self, request):
        return envelope(error={"code":"METHOD_NOT_ALLOWED","message":"请使用订单详情地址编辑。"}, http_status=405)


class SalesOrderDetailView(SalesBaseView):
    def get(self, request, order_id):
        decision, denied = self.authorize(request, "sales.order.view")
        if denied: return denied
        row = SalesOrder.objects.select_related(
            "customer", "department", "sales_owner", "engineering_document_version__document",
        ).prefetch_related("items__material", "items__engineering_attributes").filter(
            pk=order_id, company_id=request.user.company_id,
        ).first()
        if row and not restrict_orders(SalesOrder.objects.filter(pk=row.pk), request.user).exists():
            return envelope(error={"code": "SALES_VIEW_SCOPE_DENIED", "message": "当前查看授权不覆盖此订单。"}, http_status=403)
        if not row: return self.fail(SalesBusinessError("SALES_ORDER_NOT_FOUND", "销售订单不存在。", 404))
        from pde.order_review_approval import build_approval_facts

        data = order_row(row)
        bound_risks = {}
        for relation in row.order_review_relations.select_related("review").all():
            review = relation.review
            if review.company_id != row.company_id or review.record_status != "SUBMITTED":
                continue
            bound_risks[review.pk] = {
                "disagreements": [{
                    "itemCode": item.item_code,
                    "itemText": item.item_text,
                    "reason": item.disagreement_reason_code,
                    "reasonText": item.disagreement_reason_text,
                    "evidence": item.evidence_note,
                    "responsibleName": item.responsible_employee.full_name if item.responsible_employee else "",
                    "signedAt": item.signed_at.isoformat() if item.signed_at else None,
                } for item in review.items.select_related("responsible_employee").filter(decision="DISAGREE")],
                "finalDecision": build_approval_facts(user=request.user, review=review).get("finalDecision"),
            }
        for link in data["reviewLinks"]:
            link["risk"] = bound_risks.get(link["reviewId"])
        return envelope({"order": data, "authorization": decision})

    def patch(self, request, order_id):
        row = SalesOrder.objects.filter(pk=order_id, company_id=request.user.company_id).first()
        decision, denied = self.authorize(request, "sales.order.update", row.department_id if row else None)
        if denied: return denied
        try: row, audit = update_order(user=request.user, order_id=order_id, payload=request.data or {}, authorization=decision)
        except SalesBusinessError as error: return self.fail(error)
        row = SalesOrder.objects.select_related("customer", "department").prefetch_related("items__material").get(pk=row.pk)
        return envelope({"order": order_row(row), "auditId": audit.pk, "authorization": decision})


class SalesOrderActionView(SalesBaseView):
    def post(self, request, order_id, action):
        definition = {
            "submit": "sales.order.submit", "approve": "sales.order.approve",
            "start-engineering": "sales.order.engineering.start",
            "complete-engineering": "sales.order.engineering.complete",
            "start-execution": "sales.order.execution.start",
            "start-delivery": "sales.order.delivery.start", "complete": "sales.order.complete",
            "close": "sales.order.close", "cancel": "sales.order.cancel",
        }
        action_code = definition.get(action)
        if not action_code: return self.fail(SalesBusinessError("SALES_ORDER_ACTION_INVALID", "未知销售订单动作。", 404))
        row = SalesOrder.objects.filter(pk=order_id, company_id=request.user.company_id).first()
        decision, denied = self.authorize(request, action_code, row.department_id if row else None)
        if denied: return denied
        payload = dict(request.data or {})
        payload.setdefault("idempotencyKey", request.headers.get("Idempotency-Key", ""))
        payload.setdefault("requestId", request.headers.get("X-Request-Id", ""))
        try:
            row, audit, action_request, idempotent = perform_order_action(
                user=request.user, order_id=order_id, action=action,
                payload=payload, authorization=decision,
            )
        except SalesBusinessError as error: return self.fail(error)
        row = SalesOrder.objects.select_related("customer", "department").prefetch_related("items__material").get(pk=row.pk)
        return envelope({
            "order": order_row(row), "auditId": audit.pk,
            "actionRequestId": action_request.pk, "idempotent": idempotent,
            "authorization": decision,
        })


class SalesOrderItemDetailView(SalesBaseView):
    def patch(self, request, order_id, item_id):
        row = SalesOrder.objects.filter(pk=order_id, company_id=request.user.company_id).first()
        decision, denied = self.authorize(request, "sales.order.update", row.department_id if row else None)
        if denied: return denied
        try:
            row, item, audit = update_order_item(
                user=request.user, order_id=order_id, item_id=item_id,
                payload=request.data or {}, authorization=decision,
            )
        except SalesBusinessError as error: return self.fail(error)
        return envelope({
            "salesOrderId": row.pk, "salesOrderItemId": item.pk,
            "version": row.version, "auditId": audit.pk, "authorization": decision,
        })


class SalesOrderConfirmView(SalesBaseView):
    def post(self, request, order_id):
        row=SalesOrder.objects.filter(pk=order_id).first(); decision,denied=self.authorize(request,"sales.order.confirm",row.department_id if row else None)
        if denied:return denied
        try: row,audit=confirm_order(user=request.user,order_id=order_id,authorization=decision)
        except SalesBusinessError as error:return self.fail(error)
        row=SalesOrder.objects.select_related("customer","department").prefetch_related("items__material").get(pk=row.pk)
        return envelope({"order":order_row(row),"auditId":audit.pk if audit else None,"idempotent":audit is None,"authorization":decision})


class SalesOrderDemandView(SalesBaseView):
    def post(self, request, order_id):
        row=SalesOrder.objects.filter(pk=order_id).first(); decision,denied=self.authorize(request,"sales.order.generate_demand",row.department_id if row else None)
        if denied:return denied
        try: demands,audits=generate_demand(
            user=request.user,order_id=order_id,authorization=decision,return_all=True,
            sales_order_item_id=request.data.get("salesOrderItemId"),
            manufacturing_output_ids=request.data.get("manufacturingOutputIds"),
        )
        except SalesBusinessError as error:return self.fail(error)
        return envelope({
            "demand": demand_row(demands[0]) if demands else None,
            "demands": [demand_row(value) for value in demands],
            "auditId": audits[0].pk if audits else None,
            "auditIds": [value.pk for value in audits],
            "idempotent": not audits,
            "authorization": decision,
        },http_status=status.HTTP_201_CREATED)


class SalesOrderEngineeringAttributeCreateView(SalesBaseView):
    def post(self, request, order_id, item_id):
        row=SalesOrder.objects.filter(pk=order_id).first()
        decision,denied=self.authorize(
            request,"sales.order.engineering_input.maintain",row.department_id if row else None,
        )
        if denied:return denied
        try:
            attribute,audit=create_engineering_attribute(
                user=request.user,order_id=order_id,item_id=item_id,
                payload=request.data or {},authorization=decision,
            )
        except SalesBusinessError as error:return self.fail(error)
        return envelope({
            "engineeringAttribute":{
                "id":attribute.pk,"salesOrderItemId":attribute.sales_order_item_id,
                "rawSource":attribute.raw_source,"rawSheet":attribute.raw_sheet,
                "externalSource":attribute.external_source,"rawField":attribute.raw_field,
                "rawValue":attribute.raw_value,"canonicalField":attribute.canonical_field,
                "normalizedValue":attribute.normalized_value,"valueType":attribute.value_type,
                "unitId":attribute.unit_id,"sourceType":attribute.source_type,
                "engineeringDocumentVersionId":attribute.engineering_document_version_id,
            },"auditId":audit.pk,"authorization":decision,
        },http_status=status.HTTP_201_CREATED)
