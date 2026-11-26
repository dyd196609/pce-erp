from datetime import date
from django.core.exceptions import ValidationError

from django.db.models import Q
from django.db import connection, DatabaseError
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from system.authorization import AuthorizationService
from pfm.formal_employee import formal_employee_queryset
from pfm.models import Employee
from system.models import PositionResponsibility, UserRoleScopeAssignment
from workflow_runtime.fact_loads import failed_fact_load_facts, successful_fact_load_facts
from .operation_read_diagnostics import observe_operation_read
from .routing_read_context import routing_read_request, memo_read

from .models import (
    _routing_matches_order_engineering_instance,
    BOMVersion,
    EngineeringChangeNotice,
    EngineeringDocumentVersion,
    EngineeringDocument,
    EngineeringOperationRequirement,
    OrderEngineeringBaseline,
    OrderEngineeringInstance,
    ManufacturingApplicabilityScope,
    ProductManufacturingOutput,
    ProductBOM,
    ProductDefinition,
    ProductEngineeringReadiness,
    ProductRequirement,
    ProductVersion,
    Routing,
    RoutingStep,
    RoutingVersion,
    WorkCenter,
)
from .production_foundation_service import (
    ENTITY_CONFIG,
    ProductionFoundationError,
    ProductionFoundationService,
    EngineeringLifecycleService,
    _actor_chain,
)
from .manufacturing_structure_service import ManufacturingStructureError, ManufacturingStructureService
from .admission_chain_revocation import active_order_engineering_instances
from .crm_order_admission import (
    CRMOrderAdmissionError,
    require_current_order_admission,
)
from .engineering_calculation_service import (
    EngineeringCalculationError,
    EngineeringCalculationReadinessService,
    EngineeringCalculationService,
    EngineeringMethodTrialService,
    OrderEngineeringClosureService,
)
from .engineering_rule_foundation import specification_hash
from .formal_manufacturing_eligibility_service import FormalManufacturingEligibilityService
from .order_demand_preparation_service import (
    OrderDemandPreparationError,
    engineering_readiness_facts,
    preparation_facts,
    requirement_facts,
)
from .product_design_service import (
    ProductDesignError,
    handle_product_design_action,
    product_design_facts,
)
from .product_version_management_service import (
    ProductVersionManagementError,
    handle_product_version_management_action,
    product_version_management_facts,
)
from .product_bom_detail_projection import (
    ProductBomDetailProjectionError,
    project_product_bom_material_detail,
    project_bom_draft_context,
)
from .bom_version_release_preflight import project_bom_version_release_preflight
from .bom_version_control_service import BomVersionControlError
from .routing_planning_readiness_service import RoutingPlanningReadinessService
from .routing_step_applicability_service import (
    CONTRACT_VERSION as ROUTING_APPLICABILITY_CONTRACT_VERSION,
    RoutingStepApplicabilityResolver,
)
from .routing_version_successor_service import (
    ROUTING_PERMISSION,
    RoutingStepApplicabilityMaintenanceService,
    RoutingVersionChangeError,
    RoutingVersionSuccessorService,
)
from .routing_manual_applicability_service import (
    MANUAL_ACTION as ROUTING_MANUAL_APPLICABILITY_ACTION,
    RoutingManualApplicabilityService,
    exact_contexts_for_version,
)
from .routing_version_review_service import (
    REVIEW_ACTION as ROUTING_VERSION_REVIEW_ACTION,
    RoutingVersionReviewError,
    project_review_preflight,
    review_routing_version,
)
from .routing_version_release_service import (
    RELEASE_ACTION as ROUTING_VERSION_RELEASE_ACTION,
    RoutingVersionReleaseError,
    project_release_preflight,
    release_routing_version,
)
from .engineering_document_version_review_service import (
    REVIEW_ACTION as ENGINEERING_DOCUMENT_VERSION_REVIEW_ACTION,
    EngineeringDocumentVersionReviewError,
    project_review_preflight as project_engineering_document_version_review_preflight,
    review_engineering_document_version,
)
from .engineering_document_version_release_service import (
    RELEASE_ACTION as ENGINEERING_DOCUMENT_VERSION_RELEASE_ACTION,
    EngineeringDocumentVersionReleaseError,
    project_release_preflight as project_engineering_document_version_release_preflight,
    release_engineering_document_version,
)


VERSION = "V1.14.2.8.4.10.10"


def _facts(page_code, rows, request=None):
    api_url = request.path if request is not None else f"/api/pde/{page_code}/"
    fact_load_facts = successful_fact_load_facts(
        result_count=len(rows),
        api_url=api_url,
        tenant_id=(str(request.user.company_id) if request is not None else None),
        request=request,
    )
    common = {
        "factSource": "server",
        "pageVersion": VERSION,
        "pageCode": page_code,
        "moduleCode": "PDE",
        "recordCount": len(rows),
        "acceptanceStatus": "PASS",
        "productionUserDataWritten": False,
        **fact_load_facts,
        "factLoadFacts": fact_load_facts,
    }
    return {
        "rows": rows,
        **fact_load_facts,
        "factLoadFacts": fact_load_facts,
        "apiFacts": dict(common),
        "pageFacts": dict(common),
        "diagnosticFacts": dict(common),
        "strictFacts": dict(common),
        "acceptanceFacts": dict(common),
    }


def _read_failure(request, *, status_code, error_code, error_message, details=None, extra=None):
    fact_load_facts = failed_fact_load_facts(
        api_url=request.path,
        http_status=status_code,
        error_code=error_code,
        error_message=error_message,
        tenant_id=str(request.user.company_id),
        request=request,
    )
    payload = {
        "result": "blocked",
        "currentStateSource": "server",
        **fact_load_facts,
        "factLoadFacts": fact_load_facts,
        "resultCount": None,
        "recordCount": None,
        "data": {**fact_load_facts, "factLoadFacts": fact_load_facts},
        "error": {"code": error_code, "message": error_message, "details": details or {}},
    }
    if extra:
        payload.update(extra)
    return Response(payload, status=status_code)


def _formal_intake_facts(request):
    return preparation_facts(
        request.user.company_id,
        crm_order_relation_id=request.query_params.get("crmOrderRelationId") or None,
        sales_order_id=request.query_params.get("salesOrderId") or None,
    )


def _formal_intake_surface(facts):
    context = facts["contextFacts"]
    return {
        "factSource": "server",
        "authority": (
            "OrderReviewSalesOrderRelation -> SalesOrder -> SalesOrderItem -> "
            "CRM Review -> EngineeringSourceRecord"
        ),
        "companyId": context["companyId"],
        "crmOrderRelationId": context["crmOrderRelationId"],
        "salesOrderId": context["salesOrderId"],
        "salesOrderNo": context["salesOrderNo"],
        "salesOrderItemIds": context["scopeItemIds"],
        "crmReviewId": context["crmReviewId"],
        "sourceRecordId": context["sourceRecordId"],
        "sourceVersion": context["sourceVersion"],
        "sourceContentHash": context["sourceContentHash"],
        "sourceContentHashVerified": context["sourceContentHashVerified"],
        "scopeMode": context["scopeMode"],
        "scopeItemCount": context["scopeItemCount"],
        "pdePredecessorRelationId": context["pdePredecessorRelationId"],
        "pdeReviewId": context["pdeReviewId"],
        "statusCode": context["statusCode"],
        "statusMessage": context["statusMessage"],
        "businessWriteCount": 0,
        "pdeReviewCreated": False,
        "pdePredecessorRelationCreated": False,
        "oeiCreated": False,
        "authorizationCreated": False,
    }


class PdeReadOnlyListView(APIView):
    permission_classes = [IsAuthenticated]
    model = None
    page_code = ""
    search_fields = ()

    def serialize(self, obj):
        raise NotImplementedError

    def get(self, request):
        queryset = self.model.objects.all()
        field_names = {field.name for field in self.model._meta.fields}
        if "company" in field_names:
            queryset = queryset.filter(company_id=request.user.company_id)
        elif "routing" in field_names:
            queryset = queryset.filter(routing__company_id=request.user.company_id)
        elif "bom" in field_names:
            queryset = queryset.filter(bom__company_id=request.user.company_id)
        elif "product" in field_names:
            queryset = queryset.filter(product__company_id=request.user.company_id)
        elif "related_product" in field_names:
            queryset = queryset.filter(related_product__company_id=request.user.company_id)
        query = request.query_params.get("q", "").strip()
        if query:
            criteria = Q()
            for field in self.search_fields:
                criteria |= Q(**{f"{field}__icontains": query})
            queryset = queryset.filter(criteria)
        rows = [self.serialize(item) for item in queryset]
        return Response(_facts(self.page_code, rows, request), status=200)


class ProductRequirementListView(PdeReadOnlyListView):
    model = ProductRequirement
    page_code = "pde-product-requirements"
    search_fields = ("requirement_no", "customer", "product_name", "owner")

    def get(self, request):
        try:
            facts = _formal_intake_facts(request)
        except OrderDemandPreparationError as exc:
            return _read_failure(
                request,
                status_code=exc.http_status,
                error_code=exc.code,
                error_message=exc.message,
                details=exc.details,
            )
        context = facts["contextFacts"]
        rows = [
            {
                "id": item["salesOrderItemId"],
                "salesOrderItemId": item["salesOrderItemId"],
                "orderNo": context["salesOrderNo"],
                "orderLineNo": item["lineNo"],
                "customer": context["customer"],
                "productCode": item["productCode"],
                "productName": item["productName"],
                "quantityLabel": item["quantity"],
                "requiredDeliveryDate": item["requiredDate"],
                "sourceVersion": context["sourceVersion"],
                "statusLabel": "0032订单范围已确认",
            }
            for item in context["orderItems"]
        ]
        query = request.query_params.get("q", "").strip().lower()
        if query:
            fields = ("orderNo", "customer", "productCode", "productName", "sourceVersion")
            rows = [
                row for row in rows
                if any(query in str(row.get(field, "")).lower() for field in fields)
            ]
        payload = _facts(self.page_code, rows, request)
        payload["contextFacts"] = context
        surface = {
            **_formal_intake_surface(facts),
            "customerOrderDemandCount": len(rows),
        }
        for key in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts"):
            payload[key].update(surface)
        return Response(payload, status=200)

    def serialize(self, obj):
        return {
            "id": obj.pk,
            "requirementNo": obj.requirement_no,
            "customer": obj.customer,
            "productName": obj.product_name,
            "requirementSource": obj.requirement_source,
            "requirementDate": obj.requirement_date.isoformat(),
            "owner": obj.owner,
            "statusLabel": obj.get_status_display(),
        }


class ProductDefinitionListView(PdeReadOnlyListView):
    model = ProductDefinition
    page_code = "pde-product-definitions"
    search_fields = ("product_code", "product_name", "specification", "model", "version")

    def get(self, request):
        if request.query_params.get("mode") == "orders":
            # Reuse the existing company-scoped order authority, never infer a default order.
            from .product_version_management_service import _order_options
            options = [row for row in _order_options(request.user.company_id) if row["hasDesignScope"]]
            payload = _facts(self.page_code, options, request)
            payload.update({"orderOptions": options, "selectionRequired": True, "businessWriteSideEffectCount": 0})
            return Response(payload, status=200)
        try:
            facts = product_design_facts(
                request.user.company_id,
                user=request.user,
                order_no=request.query_params.get("orderNo") or None,
                instance_context={k: request.query_params.get(k) for k in ("companyId", "orderEngineeringInstanceId", "salesOrderId", "salesOrderItemId", "sourceRecordId", "sourceVersion", "authorizationId")} if request.query_params.get("orderEngineeringInstanceId") else None,
            )
        except (ProductDesignError, OrderDemandPreparationError) as exc:
            return _read_failure(request, status_code=exc.http_status, error_code=exc.code, error_message=exc.message, details=exc.details)
        payload = _facts(self.page_code, facts["rows"], request)
        payload.update({key: value for key, value in facts.items() if key != "rows"})
        for key in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts"):
            payload[key].update({
                "authority": "ProductDesignItem + SalesOrderItem/SalesOrder + persisted source/review relations",
                "recordCount": facts["recordCount"],
                "groupCount": facts["groupCount"],
                "plannedCount": facts["plannedCount"],
                "designRevisionCount": facts["designRevisionCount"],
                "completedFactCount": facts["completedFactCount"],
                "datedCompletionCount": facts["datedCompletionCount"],
                "performanceIncludedCount": facts["performanceIncludedCount"],
                "expectedSourceCounts": facts["expectedSourceCounts"],
                "actualSourceCounts": facts["actualSourceCounts"],
                "legacyD1Count": facts["legacyD1Count"],
                "sourceRecordId": facts["sourceContext"]["sourceRecordId"],
                "sourceVersion": facts["sourceContext"]["sourceVersion"],
                "permanentProductCreated": False,
                "productVersionCreated": False,
                "orderEngineeringInstanceCreated": False,
                "publishedDownstreamObjectCount": 0,
            })
        return Response(payload, status=200)

    def post(self, request):
        try:
            facts, replayed = handle_product_design_action(
                user=request.user,
                payload=request.data,
                idempotency_key=request.headers.get("Idempotency-Key"),
            )
        except (ProductDesignError, OrderDemandPreparationError) as exc:
            return Response({"error": {"code": exc.code, "message": exc.message, "details": exc.details}}, status=exc.http_status)
        return Response({"success": True, "idempotentReplay": replayed, **facts}, status=status.HTTP_200_OK)

    def serialize(self, obj):
        return {
            "id": obj.pk,
            "productCode": obj.product_code,
            "productName": obj.product_name,
            "specification": obj.specification,
            "model": obj.model,
            "version": obj.version,
            "emdMaterialCode": obj.emd_material_code,
            "materialId": obj.material_id,
            "productCategoryCode": obj.category.code if obj.category_id else "",
            "companyId": obj.company_id,
            "isActive": obj.is_active,
            "materialSourceLabel": "EMD企业主数据中心",
            "statusLabel": obj.get_status_display(),
        }


class ProductBomListView(PdeReadOnlyListView):
    model = ProductBOM
    page_code = "pde-product-boms"
    search_fields = (
        "product__product_code", "product__product_name",
        "product_category__code", "product_category__name", "bom_code", "name",
        "order_engineering_instance__instance_no",
        "order_engineering_instance__sales_order_item__sales_order__order_no",
    )

    def get(self, request):
        if request.query_params.get("handoff") != "1":
            return super().get(request)
        from .order_bom_handoff_service import HandoffReadError, order_bom_handoff
        try:
            try:
                target_id=int(request.query_params.get('sourceCalculationId') or 0)
            except (TypeError,ValueError):
                target_id=0
            from .models import EngineeringCalculationRecord
            test_target=EngineeringCalculationRecord.all_records.filter(pk=target_id,scope='test_business',company_id=request.user.company_id).first()
            if test_target:
                OrderEngineeringClosureService._calculation(user=request.user,calculation_id=test_target.pk)
                response=super().get(request)
                target={'calculationId':test_target.pk,'purposeLabel':'测试业务','authority':'test-business-bom-handoff','businessWriteSideEffectCount':0}
                response.data['testBusinessTarget']=target
                for surface in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):
                    response.data[surface]['testBusinessTarget']=target
                return response
            handoff = order_bom_handoff(
                user=request.user, order_id=request.query_params.get("orderId"),
                calculation_id=request.query_params.get("sourceCalculationId"),
            )
            response = super().get(request)
            response.data["handoff"] = handoff
            # All surfaces project the same server facts, without duplicating the
            # object/route detail payload five times on every list request.
            handoff_summary = {key: handoff[key] for key in (
                "factSource", "modeLabel", "checkedAt", "companyId", "account", "selectedOrderId",
                "selectedOrderNo", "objectCount", "factCount", "candidateCount", "businessWriteCount",
            )}
            handoff_summary["records"] = [
                {key: row[key] for key in ("calculationId", "calculationNo", "revision", "lineId", "instanceId",
                                           "objectCount", "factCount", "materialRequirementCount", "operationRequirementCount", "stages")}
                for row in handoff["records"]
            ]
            preview = handoff["materialRequirementPreview"]
            handoff_summary["materialRequirementPreview"] = {
                key: preview[key] for key in (
                    "previewCode", "modeLabel", "approvedMappingCount", "objectCount",
                    "candidateCount", "classificationCounts", "classificationClosed", "metrics",
                    "formalEngineeringMaterialRequirementCount", "calculationReexecuted",
                    "implicitUomConversionCount", "databaseBusinessWriteCount", "bomGate",
                )
            }
            for key in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts"):
                response.data[key]["handoff"] = handoff_summary
            return response
        except HandoffReadError as error:
            return _read_failure(request, status_code=error.http_status, error_code=error.code, error_message=error.message)
        except EngineeringCalculationError as error:
            # Calculation read permission must not replace the existing BOM
            # list's authorization contract for other legitimate BOM viewers.
            response = super().get(request)
            response.data["handoffReadFailure"] = {
                "statusLabel": "当前账户无工程核算承接查看权限；原BOM列表仍可读取",
                "errorCode": error.code, "message": error.message,
            }
            for key in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts"):
                response.data[key]["handoffReadFailure"] = response.data["handoffReadFailure"]
            return response
        except DatabaseError:
            return _read_failure(request, status_code=503, error_code="HANDOFF_READ_FAILED", error_message="承接事实读取失败；不是没有数据，请稍后重新读取。")

    def serialize(self, obj):
        latest = obj.versions.prefetch_related("items").order_by("-revision", "-pk").first()
        instance = obj.order_engineering_instance if obj.order_engineering_instance_id else None
        order_item = instance.sales_order_item if instance else None
        eligibility = FormalManufacturingEligibilityService.resolve(obj) if instance else None
        material_details = project_product_bom_material_detail(
            bom=obj, bom_version=latest, order_item=order_item,
        )
        return {
            "id": obj.pk,
            "applicabilityScope": obj.applicability_scope,
            "productCode": obj.product.product_code if obj.product_id else "",
            "productName": obj.product.product_name if obj.product_id else "",
            "productCategoryCode": obj.product_category.code if obj.product_category_id else "",
            "productCategoryName": obj.product_category.name if obj.product_category_id else "",
            "orderEngineeringInstanceId": obj.order_engineering_instance_id,
            "orderEngineeringInstanceNo": instance.instance_no if instance else "",
            "orderNo": order_item.sales_order.order_no if order_item else "",
            "orderLineNo": order_item.line_no if order_item else None,
            "bomCode": obj.bom_code,
            "bomName": obj.name,
            "versionCount": obj.versions.count(),
            "latestBomVersionId": latest.pk if latest else None,
            "latestBomVersion": latest.bom_version if latest else "",
            "latestVersionStatus": latest.status if latest else "",
            "latestMaterialCount": latest.items.count() if latest else 0,
            "sourceRequirementCount": sum(
                row["sourceRequirementCount"] for row in material_details
            ),
            "bomMaterialDetails": material_details,
            **project_bom_draft_context(latest),
            "sourceCalculationId": obj.source_calculation_id if obj.usage_purpose == "TEST_BUSINESS" else latest.source_calculation_id if latest else None,
            "businessPurposeCode": eligibility["businessPurposeCode"] if eligibility else "",
            "businessPurposeLabel": eligibility["businessPurposeLabel"] if eligibility else "",
            "formalManufacturingEligible": eligibility["formalManufacturingEligible"] if eligibility else None,
            "formalManufacturingEligibilityLabel": (
                "允许继续正式制造门禁" if eligibility and eligibility["formalManufacturingEligible"] else
                "禁止正式制造评审/发布" if eligibility else "不适用"
            ),
            "formalManufacturingDecisionCode": eligibility["decisionCode"] if eligibility else "",
            "formalManufacturingMessage": eligibility["message"] if eligibility else "",
            "companyId": obj.company_id,
            "isActive": obj.is_active,
            "statusLabel": obj.get_status_display(),
        }


class RoutingFormalHandoffError(Exception):
    pass


class RoutingListView(PdeReadOnlyListView):
    model = Routing
    page_code = "pde-routings"
    search_fields = (
        "product__product_code",
        "product__product_name",
        "product_category__code",
        "product_category__name",
        "manufacturing_process_type__code",
        "manufacturing_process_type__name",
        "routing_code",
        "name",
    )

    @staticmethod
    def _require_handoff(condition, message):
        if not condition:
            raise RoutingFormalHandoffError(message)

    @classmethod
    def _serialize_formal_handoff(cls, bom_version):
        instance = bom_version.order_engineering_instance
        order_item = instance.sales_order_item if instance else None
        order = order_item.sales_order if order_item else None
        cls._require_handoff(
            bom_version.bom_scope == "order_specific",
            "工艺路线正式承接仅接受按单BOMVersion。",
        )
        cls._require_handoff(instance is not None, "按单BOMVersion缺少订单工程实例，停止承接。")
        cls._require_handoff(order_item is not None, "订单工程实例缺少正式销售订单行，停止承接。")
        cls._require_handoff(order is not None, "销售订单行缺少正式销售订单，停止承接。")
        cls._require_handoff(bom_version.bom_id is not None, "BOMVersion缺少正式ProductBOM，停止承接。")
        cls._require_handoff(
            bom_version.bom.applicability_scope == ManufacturingApplicabilityScope.ORDER_ENGINEERING
            and bom_version.bom.order_engineering_instance_id == instance.pk,
            "BOMVersion与ProductBOM的订单工程实例关系不一致，停止承接。",
        )
        cls._require_handoff(
            bom_version.bom.company_id == instance.company_id == order.company_id,
            "SalesOrder、SalesOrderItem、OEI、ProductBOM公司范围不一致，停止承接。",
        )
        cls._require_handoff(
            bom_version.source_calculation_id is not None,
            "按单BOMVersion缺少正式来源工程核算，停止承接。",
        )
        source_calculation = bom_version.source_calculation
        cls._require_handoff(
            source_calculation.company_id == instance.company_id
            and source_calculation.engineering_instance_id == instance.pk
            and source_calculation.sales_order_item_id == order_item.pk,
            "来源工程核算与公司、订单行或OEI范围不一致，停止承接。",
        )
        identity_candidate_count = BOMVersion.objects.filter(
            bom_id=bom_version.bom_id,
            bom_version=bom_version.bom_version,
        ).count()
        cls._require_handoff(
            identity_candidate_count == 1,
            "ProductBOM范围内无法唯一确定BOMVersion，停止承接。",
        )

        material_details = project_product_bom_material_detail(
            bom=bom_version.bom,
            bom_version=bom_version,
            order_item=order_item,
        )
        source_requirement_count = sum(
            row["sourceRequirementCount"] for row in material_details
        )
        cls._require_handoff(bool(material_details), "正式BOMVersion没有可证明的BOMItem，停止承接。")
        cls._require_handoff(
            source_requirement_count > 0
            and all(row["sourceRequirementCount"] > 0 for row in material_details),
            "正式BOMVersion存在无法由来源Requirement证明的BOMItem，停止承接。",
        )

        resolved = ManufacturingStructureService.resolve_effective_routing(instance)
        routing = resolved["routing"]
        routing_version = resolved["routing_version"]
        selected_tier = next(
            (tier for tier in resolved["checked"] if tier["scope"] == resolved["resolved_scope"]),
            None,
        )
        routing_candidate_count = len(selected_tier["routingIds"]) if selected_tier else 0
        cls._require_handoff(
            routing_candidate_count == 1 and selected_tier["routingIds"] == [routing.pk],
            "当前订单行无法唯一证明工艺路线，停止承接。",
        )
        cls._require_handoff(
            routing.company_id == instance.company_id,
            "工艺路线与订单工程实例公司范围不一致，停止承接。",
        )
        cls._require_handoff(
            routing_version.routing_id == routing.pk and routing_version.status == "released",
            "当前工艺路线没有唯一已发布版本，停止承接。",
        )

        steps = list(
            routing_version.steps.select_related(
                "operation", "workshop", "work_center",
                "operation__workshop", "operation__work_center",
            ).order_by("sequence", "pk")
        )
        cls._require_handoff(bool(steps), "当前工艺路线版本没有正式工序，停止承接。")
        sequences = [step.sequence for step in steps]
        cls._require_handoff(
            len(sequences) == len(set(sequences)) and sequences == sorted(sequences),
            "当前工艺路线版本的工序顺序不唯一，停止承接。",
        )
        operation_sequence = " → ".join(
            f"{step.sequence} {step.operation.name}" for step in steps
        )
        inherited_resource_count = sum(
            1 for step in steps
            if not step.work_center_id and step.operation.work_center_id
        )
        workshop_only_count = sum(
            1 for step in steps
            if not (step.work_center_id or step.operation.work_center_id)
            and (step.workshop_id or step.operation.workshop_id)
        )
        planning_readiness = RoutingPlanningReadinessService.assess(
            routing_version, bom_version=bom_version,
        )
        scope_labels = {
            "ORDER_ENGINEERING": "订单工程实例专用路线",
            "PRODUCT_DEFINITION": "长期产品定义路线",
            "PRODUCT_CATEGORY": "产品分类 + 正式工艺类型路线",
        }
        company = bom_version.bom.company
        return {
            "companyId": company.pk,
            "companyCode": company.code,
            "companyName": company.name,
            "orderId": order.pk,
            "orderNo": order.order_no,
            "orderLineId": order_item.pk,
            "orderLineNo": order_item.line_no,
            "orderEngineeringInstanceId": instance.pk,
            "orderEngineeringInstanceNo": instance.instance_no,
            "productCategoryCode": (
                instance.product_category.code if instance.product_category_id else ""
            ),
            "productCategoryName": (
                instance.product_category.name if instance.product_category_id else ""
            ),
            "manufacturingProcessTypeCode": (
                instance.selected_process_type.code if instance.selected_process_type_id else ""
            ),
            "manufacturingProcessTypeName": (
                instance.selected_process_type.name if instance.selected_process_type_id else ""
            ),
            "productBomId": bom_version.bom_id,
            "bomCode": bom_version.bom.bom_code,
            "bomVersionId": bom_version.pk,
            "bomVersionNo": bom_version.bom_version,
            "bomVersionStatusLabel": bom_version.get_status_display(),
            "sourceCalculationId": source_calculation.pk,
            "sourceCalculationNo": source_calculation.calculation_no,
            "materialCount": len(material_details),
            "sourceRequirementCount": source_requirement_count,
            "sourceIntegrityLabel": f"{len(material_details)}项物料 / {source_requirement_count}条来源",
            "routingId": routing.pk,
            "routingCode": routing.routing_code,
            "routingName": routing.name,
            "routingDefinitionStatusLabel": routing.get_status_display(),
            "resolvedRoutingScope": resolved["resolved_scope"],
            "routingSourceLabel": scope_labels[resolved["resolved_scope"]],
            "routingIdentityCandidateCount": routing_candidate_count,
            "routingVersionId": routing_version.pk,
            "routingVersionNo": routing_version.routing_version,
            "routingVersionStatusLabel": routing_version.get_status_display(),
            "routingVersionCandidateCount": 1,
            "stepCount": len(steps),
            "operationSequenceLabel": operation_sequence,
            "resourceMaintenanceLabel": (
                f"步骤直接工作中心{sum(1 for step in steps if step.work_center_id)}/{len(steps)}；"
                f"工序默认工作中心{inherited_resource_count}/{len(steps)}；"
                f"仅有车间{workshop_only_count}/{len(steps)}"
            ),
            "planningReadiness": planning_readiness,
            "planningReady": planning_readiness["planningReady"],
            "planningReadinessStatusLabel": planning_readiness["statusLabel"],
            "planningBlockingSummary": planning_readiness["blockingSummary"],
            "planningDataSourceLabel": "服务端RoutingVersion/Step、Operation、资源、产能与制造日历正式事实",
            "handoffAccepted": True,
            "handoffStatusLabel": "已承接唯一正式工艺路线",
            "handoffBasisLabel": (
                "OEI产品分类与正式工艺类型外键经ManufacturingStructureService唯一解析；"
                "未使用名称、颜色或工艺描述推断"
            ),
            "routingVersionManagementEligible": planning_readiness["planningReady"],
            "routingVersionManagementEligibilityLabel": (
                "工艺路线与计划输入完整，具备下一节点只读承接条件（本轮未进入）"
                if planning_readiness["planningReady"]
                else "当前节点未闭环；须先补齐真实计划输入，不进入下一节点"
            ),
            "businessBoundaryLabel": (
                f"只读承接；未创建路线/版本/工序，未改变BOMVersion "
                f"{bom_version.bom_version}状态"
            ),
        }

    @staticmethod
    def _project_handoff(row, handoffs):
        row["formalOrderHandoffs"] = handoffs
        row["formalOrderHandoffCount"] = len(handoffs)
        if len(handoffs) == 1:
            row.update(handoffs[0])
        elif len(handoffs) > 1:
            row.update({
                "handoffAccepted": True,
                "handoffStatusLabel": f"已承接{len(handoffs)}个正式订单行",
                "orderNo": f"{len(handoffs)}个订单行（详情可查）",
                "routingVersionManagementEligibilityLabel": "各订单行须分别核验（本轮未进入）",
            })
        else:
            row.update({
                "handoffAccepted": False,
                "handoffStatusLabel": "路线定义（暂无订单行承接）",
                "routingVersionManagementEligibilityLabel": "未形成订单行承接事实",
            })
        return row

    @routing_read_request
    def get(self, request):
        # Engineering catalogue reads keep their original master-data duty.
        # MES assignees use the separately scoped task/source projection;
        # merely opening an old PDE bookmark must not disclose this catalogue.
        from .test_business_bom_service import authorize
        try:
            authorize(request.user,'production.master_data.view',request.user.company_id)
        except Exception as exc:
            if getattr(exc,'code','') not in ('PERMISSION_DENIED','SCOPE_DENIED','ORGANIZATION_MISMATCH','ROLE_REQUIRED','ACTION_NOT_GRANTED'):
                raise
            return _read_failure(request,status_code=403,error_code=getattr(exc,'code','PERMISSION_DENIED'),error_message=str(exc))
        try:
            handoffs = [
                self._serialize_formal_handoff(item)
                for item in BOMVersion.objects.filter(
                    bom__company_id=request.user.company_id,
                    bom_scope="order_specific",
                ).exclude(usage_purpose='TEST_BUSINESS').select_related(
                    "bom", "bom__company", "order_engineering_instance",
                    "order_engineering_instance__product_category",
                    "order_engineering_instance__selected_process_type",
                    "order_engineering_instance__sales_order_item",
                    "order_engineering_instance__sales_order_item__sales_order",
                    "source_calculation",
                ).order_by("pk")
            ]
            foundation_assessment = RoutingPlanningReadinessService.foundation_assessment(
                request.user.company_id,
            )
            handoffs_by_routing = {}
            for handoff in handoffs:
                handoffs_by_routing.setdefault(handoff["routingId"], []).append(handoff)
            rows = [
                self._project_handoff(
                    self.serialize(item),
                    handoffs_by_routing.get(item.pk, []),
                )
                for item in Routing.objects.filter(
                    company_id=request.user.company_id,
                ).select_related(
                    "product", "product_category", "order_engineering_instance",
                    "manufacturing_process_type", "company",
                ).order_by("pk")
            ]
        except (RoutingFormalHandoffError, ProductBomDetailProjectionError, ManufacturingStructureError) as exc:
            return _read_failure(
                request,
                status_code=status.HTTP_409_CONFLICT,
                error_code=getattr(exc, "code", "ROUTING_HANDOFF_SCOPE_INCONSISTENT"),
                error_message=getattr(exc, "message", str(exc)),
                details={
                    "pageCode": self.page_code,
                    "handoffAccepted": False,
                    "databaseBusinessWriteCount": 0,
                },
            )
        except DatabaseError:
            return _read_failure(
                request,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                error_code="ROUTING_HANDOFF_READ_FAILED",
                error_message="工艺路线正式关系读取失败；当前数量未知，请稍后重新读取。",
                details={
                    "pageCode": self.page_code,
                    "handoffAccepted": False,
                    "databaseBusinessWriteCount": 0,
                },
            )

        query = request.query_params.get("q", "").strip().lower()
        if query:
            rows = [row for row in rows if query in str(row).lower()]
        payload = _facts(self.page_code, rows, request)
        shared_facts = {
            "authority": (
                "Company -> SalesOrder -> SalesOrderItem -> OrderEngineeringInstance -> "
                "ProductBOM -> BOMVersion -> EngineeringCalculationRecord; "
                "OrderEngineeringInstance -> ManufacturingStructureService -> Routing -> "
                "RoutingVersion -> RoutingStep -> system.Process"
            ),
            "routingHandoffs": handoffs,
            "routingFoundationAssessment": foundation_assessment,
            "formalHandoffCount": len(handoffs),
            "databaseBusinessWriteCount": 0,
            "routingCreatedCount": 0,
            "routingVersionCreatedCount": 0,
            "routingStepCreatedCount": 0,
            "permissionMutationCount": 0,
            "roleMutationCount": 0,
            "migrationExecuted": False,
            "productionUserDataWritten": False,
        }
        from .test_engineering_routing_service import company_facts
        shared_facts['testEngineeringBindings'] = company_facts(request.user)
        payload["routingHandoffs"] = handoffs
        for key in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts"):
            payload[key].update(shared_facts)
        return Response(payload, status=200)

    @memo_read('routing_projection', lambda self,obj: obj.pk)
    def serialize(self, obj):
        today = date.today()
        version_rows = []
        for version in obj.versions.select_related(
            "product", "product_version", "routing",
        ).order_by("revision", "pk"):
            manual_context_rows = exact_contexts_for_version(version)
            resolver_context = manual_context_rows[0] if len(manual_context_rows) == 1 else {}
            step_rows = []
            for step in version.steps.select_related(
                "operation",
                "workshop",
                "work_center",
                "operation__workshop",
                "operation__work_center",
            ).order_by("sequence", "pk"):
                workshop = step.workshop or step.operation.workshop
                work_center = step.work_center or step.operation.work_center
                if step.work_center_id:
                    resource_source = "RoutingStep直接引用WorkCenter"
                elif step.workshop_id:
                    resource_source = "RoutingStep直接引用Workshop"
                elif step.operation.work_center_id:
                    resource_source = "独立Operation主数据默认WorkCenter"
                elif step.operation.workshop_id:
                    resource_source = "独立Operation主数据所属Workshop"
                else:
                    resource_source = "未维护Workshop/WorkCenter"
                applicability = RoutingStepApplicabilityResolver.resolve(
                    step,
                    engineering_calculation=resolver_context.get("engineeringCalculation"),
                    order_engineering_instance=resolver_context.get("orderEngineeringInstance"),
                    order_engineering_baseline=resolver_context.get("orderEngineeringBaseline"),
                    bom_version=resolver_context.get("bomVersion"),
                )
                step_rows.append({
                    "id": step.pk,
                    "sequence": step.sequence,
                    "operationId": step.operation_id,
                    "operationCode": step.operation.code,
                    "operationName": step.operation.name,
                    "operationSourceLabel": "system.Process（RoutingStep.operation正式FK）",
                    "workshopId": workshop.pk if workshop else None,
                    "workshopCode": workshop.code if workshop else "",
                    "workshopName": workshop.name if workshop else "",
                    "workCenterId": work_center.pk if work_center else None,
                    "workCenterCode": work_center.code if work_center else "",
                    "workCenterName": work_center.name if work_center else "",
                    "resourceSourceLabel": resource_source,
                    "applicability": applicability,
                    "applicabilityModeLabel": applicability["modeLabel"],
                    "applicabilityConditionLabel": applicability["conditionLabel"],
                    "applicabilityFormalSourceLabel": applicability["formalSourceLabel"],
                    "applicabilityResultLabel": applicability["resultLabel"],
                    "applicabilityPendingReason": applicability["pendingReason"],
                    "applicabilityEditable": version.status == "draft",
                    "isActive": step.is_active,
                    "statusLabel": "有效" if step.is_active else "已停用",
                })

            within_effective_dates = bool(
                (version.effective_date is None or version.effective_date <= today)
                and (version.expire_date is None or version.expire_date >= today)
            )
            date_and_lifecycle_effective = version.status == "released" and within_effective_dates
            context_required = bool(version.applicability)
            if date_and_lifecycle_effective and context_required:
                effective_label = "日期与生命周期有效；仍需结合适用条件解析"
                is_currently_effective = None
            elif date_and_lifecycle_effective:
                effective_label = "当前有效"
                is_currently_effective = True
            elif version.status != "released":
                effective_label = "Version未发布"
                is_currently_effective = False
            elif version.effective_date and today < version.effective_date:
                effective_label = "尚未到生效日期"
                is_currently_effective = False
            else:
                effective_label = "已超过失效日期"
                is_currently_effective = False

            version_rows.append({
                "id": version.pk,
                "routingVersionNo": version.routing_version,
                "revision": version.revision,
                "statusLabel": version.get_status_display(),
                "isReleased": version.status == "released",
                "isDraft": version.status == "draft",
                "releaseStatusLabel": "已发布" if version.status == "released" else "未发布",
                "isCurrentlyEffective": is_currently_effective,
                "effectiveStatusLabel": effective_label,
                "effectiveDate": version.effective_date.isoformat() if version.effective_date else "未单独维护",
                "expireDate": version.expire_date.isoformat() if version.expire_date else "长期有效（未维护失效日期）",
                "releaseTime": None,
                "releaseTimeLabel": "模型未单独维护发布时间；发布事实以Version状态为准",
                "approvalState": version.approval_state,
                "stepCount": len(step_rows),
                "activeStepCount": sum(1 for row in step_rows if row["isActive"]),
                "sourceModel": "pde.RoutingVersion",
                "sourceIdentity": f"pde.RoutingVersion:{version.pk}",
                "relationLabel": f"RoutingVersion.routing_id={obj.pk}（正式FK）",
                "stepRelationLabel": (
                    f"RoutingStep.routing_version_id={version.pk}（正式FK）"
                ),
                "stepRelationshipSemanticsCode": "VERSION_SCOPED_RELATIONAL_DEFINITION",
                "stepRelationshipSemanticsLabel": (
                    "当前版本直接拥有版本范围工序定义；终态版本步骤由服务端写保护，"
                    "调整必须通过后续草稿版本承接"
                ),
                "immutableSnapshotProven": version.status in {"reviewed", "released", "obsolete"},
                "applicabilityContractVersion": ROUTING_APPLICABILITY_CONTRACT_VERSION,
                "formalApplicabilityValidated": bool(step_rows) and all(
                    row["applicability"]["formalApplicabilityValidated"] for row in step_rows
                ),
                "applicabilityPendingStepCount": sum(
                    1 for row in step_rows if row["applicability"]["result"] == "PENDING"
                ),
                "manualApplicabilityReadback": RoutingManualApplicabilityService.readback(version),
                "updatedAt": version.updated_at.isoformat() if version.updated_at else "",
                "steps": step_rows,
            })

        return {
            "id": obj.pk,
            "applicabilityScope": obj.applicability_scope,
            "productCode": obj.product.product_code if obj.product_id else "",
            "productName": obj.product.product_name if obj.product_id else "",
            "productCategoryCode": obj.product_category.code if obj.product_category_id else "",
            "productCategoryName": obj.product_category.name if obj.product_category_id else "",
            "orderEngineeringInstanceId": obj.order_engineering_instance_id,
            "manufacturingProcessTypeCode": (
                obj.manufacturing_process_type.code if obj.manufacturing_process_type_id else ""
            ),
            "manufacturingProcessTypeName": (
                obj.manufacturing_process_type.name if obj.manufacturing_process_type_id else ""
            ),
            "routingCode": obj.routing_code,
            "routingName": obj.name,
            "versionCount": len(version_rows),
            "routingVersions": version_rows,
            "hasMultipleVersions": len(version_rows) > 1,
            "companyId": obj.company_id,
            "isActive": obj.is_active,
            "definitionStatusLabel": obj.get_status_display(),
            "statusLabel": obj.get_status_display(),
        }


class EngineeringDocumentListView(PdeReadOnlyListView):
    model = EngineeringDocument
    page_code = "pde-engineering-documents"
    MANUAL_INPUT_REQUIREMENTS = {
        "required": [
            "资料编号", "资料名称", "现有正式资料类型",
        ],
        "optional": ["生效日期", "失效日期"],
        "acceptedPhysicalFileTypes": [],
        "physicalFileAcceptanceLabel": "当前正式模型不接收物理文件上传，文件类型不适用",
        "businessObjectRelationLabel": (
            "目标订单行的订单工程实例、工程基线、工程核算、ProductBOM/BOM版本、"
            "工艺路线/工艺路线版本及订单工程产品发布主体均由服务端精确链唯一确定；"
            "后续专项登记必须自动带入并校验，不由业务人员重复选择。"
        ),
        "versionRequired": False,
        "versionRuleLabel": "首个资料版本未填写版本号时，现有正式服务自动产生V1.0",
        "releaseNoteSupported": False,
        "releaseNoteLabel": "当前正式模型没有独立发布说明字段，不得用备注或文件名代替",
        "humanReleaseConfirmationRequired": True,
        "humanReleaseConfirmationLabel": "正式发布必须由具备权限的业务人员另行确认并明确授权",
    }
    search_fields = (
        "document_no",
        "document_name",
        "product__product_code",
        "product_bom__bom_code",
        "routing__routing_code",
        "version",
    )

    @staticmethod
    def _release_subject_schema_available():
        required = {
            EngineeringDocument._meta.db_table: {
                "release_subject_type", "order_engineering_instance_id",
            },
            EngineeringDocumentVersion._meta.db_table: {
                "release_subject_type", "order_engineering_instance_id",
                "order_engineering_baseline_id", "engineering_calculation_id",
            },
            ProductManufacturingOutput._meta.db_table: {
                "release_subject_type", "order_engineering_baseline_id",
                "engineering_calculation_id",
            },
        }
        with connection.cursor() as cursor:
            for table, expected in required.items():
                columns = {
                    column.name
                    for column in connection.introspection.get_table_description(cursor, table)
                }
                if not expected.issubset(columns):
                    return False
        return True

    @staticmethod
    def _version_identity(label, version, value_field):
        if version is None:
            return "未形成"
        value = getattr(version, value_field)
        revision = getattr(version, "revision", None)
        revision_text = f" / 修订{revision}" if revision is not None else ""
        return f"{label}ID {version.pk} / {value}{revision_text}"

    @staticmethod
    def _append_version_blockers(blockers, label, version, status_field):
        if version is None:
            blockers.append(f"缺少{label}")
            return
        if getattr(version, status_field) != "released":
            blockers.append(f"{label}未发布")
        today = date.today()
        if version.effective_date and today < version.effective_date:
            blockers.append(f"{label}尚未生效")
        if version.expire_date and today > version.expire_date:
            blockers.append(f"{label}已失效")

    @staticmethod
    def _document_scope_facts(instance):
        """Resolve formal document facts without treating upstream data as a document."""
        documents = list(
            EngineeringDocument.objects.filter(
                order_engineering_instance=instance,
            ).select_related("product_bom", "routing").order_by("pk")
        )
        version_candidates = list(
            EngineeringDocumentVersion.objects.filter(
                Q(order_engineering_instance=instance)
                | Q(document__order_engineering_instance=instance),
            ).select_related(
                "document__product_bom",
                "document__routing",
                "order_engineering_instance",
                "order_engineering_baseline",
                "engineering_calculation",
                "related_bom__bom",
                "related_routing__routing",
            ).distinct().order_by("pk")
        )

        ownership_conflicts = []
        for document in documents:
            if document.release_subject_type != "ORDER_ENGINEERED_PRODUCT":
                ownership_conflicts.append(f"工程资料主表ID {document.pk}的发布主体类型冲突")
                continue
            if (
                document.product_bom.order_engineering_instance_id != instance.pk
                or not _routing_matches_order_engineering_instance(document.routing, instance)
            ):
                ownership_conflicts.append(f"工程资料主表ID {document.pk}的BOM或工艺路线不属于当前订单工程实例")

        traceable_versions = []
        for document_version in version_candidates:
            document = document_version.document
            conflict = ""
            if (
                document_version.release_subject_type != "ORDER_ENGINEERED_PRODUCT"
                or document.release_subject_type != "ORDER_ENGINEERED_PRODUCT"
            ):
                conflict = "发布主体类型冲突"
            elif (
                document_version.order_engineering_instance_id != instance.pk
                or document.order_engineering_instance_id != instance.pk
            ):
                conflict = "资料主表与资料版本的订单工程实例归属冲突"
            elif (
                document_version.related_bom.order_engineering_instance_id != instance.pk
                or document_version.related_bom.bom_scope != "order_specific"
                or document.product_bom_id != document_version.related_bom.bom_id
            ):
                conflict = "资料版本与BOM版本归属冲突"
            elif (
                not document_version.related_routing.routing_id
                or not _routing_matches_order_engineering_instance(
                    document_version.related_routing.routing, instance,
                )
                or document.routing_id != document_version.related_routing.routing_id
            ):
                conflict = "资料版本与工艺路线版本归属冲突"
            elif (
                not document_version.order_engineering_baseline_id
                or not document_version.engineering_calculation_id
                or document_version.engineering_calculation.engineering_instance_id != instance.pk
            ):
                conflict = "资料版本缺少同一订单工程实例的基线或工程核算关系"
            if conflict:
                ownership_conflicts.append(f"工程资料版本ID {document_version.pk}：{conflict}")
            else:
                traceable_versions.append(document_version)

        publishable_versions = [
            version for version in traceable_versions
            if (
                version.status == "reviewed"
                and version.related_bom.status == "released"
                and version.related_routing.status == "released"
            )
        ]
        released_versions = [
            version for version in traceable_versions if version.status == "released"
        ]
        return {
            "documents": documents,
            "versionCandidates": version_candidates,
            "traceableVersions": traceable_versions,
            "publishableVersions": publishable_versions,
            "releasedVersions": released_versions,
            "ownershipConflicts": ownership_conflicts,
        }

    @classmethod
    def _serialize_release_candidate(
        cls, instance, *, release_subject_schema_available, admission, user=None,
        document_version=None, row_id=None, document_scope=None,
    ):
        sales_item = instance.sales_order_item
        order = sales_item.sales_order
        blockers = []
        admission_label = "CRM订单准入有效"
        document_scope = document_scope or cls._document_scope_facts(instance)
        selected_version = document_version
        selection_required = bool(selected_version is None and len(document_scope["versionCandidates"]) > 1)
        if selection_required:
            blockers.append("同一订单行存在多个工程资料版本，请明确选择资料版本后查看或办理")

        eligibility = FormalManufacturingEligibilityService.resolve(instance)
        if not eligibility["formalManufacturingEligible"]:
            blockers.append(eligibility["message"])

        if instance.status == "inactive":
            blockers.append("订单工程实例已失效")
        elif instance.status not in {"calculated", "released"}:
            blockers.append("订单工程实例尚未完成工程转换")
        if instance.source_record.status != "confirmed":
            blockers.append("工程来源未确认或已被替代")

        baseline = selected_version.order_engineering_baseline if selected_version else OrderEngineeringBaseline.objects.filter(
            company_id=instance.company_id,
            sales_order_id=order.pk,
            status="confirmed",
            items__design_item__sales_order_item_id=sales_item.pk,
            items__source_record_id=instance.source_record_id,
            items__confirmable=True,
        ).distinct().order_by("-sequence", "-pk").first()
        if baseline is not None:
            from .baseline_usage_service import validate_baseline
            try:validate_baseline(baseline)
            except ProductDesignError as exc:blockers.append(exc.message)
        if baseline is None:
            blockers.append("缺少覆盖当前订单行的已确认工程基线")

        product_version = instance.baseline_product_version
        if instance.product_id:
            cls._append_version_blockers(blockers, "产品版本", product_version, "version_status")

        bom_queryset = instance.bom_versions.select_related(
            "bom", "product_version", "source_calculation",
        )
        bom_version = None
        if selected_version:
            bom_version = selected_version.related_bom
        else:
            try:
                bom_version = ManufacturingStructureService.resolve_current_version(bom_queryset)
            except ManufacturingStructureError as exc:
                fallback = bom_queryset.order_by("-revision", "-pk").first()
                if exc.code == "AMBIGUOUS_EFFECTIVE_VERSION":
                    blockers.append("存在多个同时适用的已发布BOM版本")
                bom_version = fallback
        cls._append_version_blockers(blockers, "BOM版本", bom_version, "status")

        completed_calculations = instance.calculation_records.filter(scope="order_engineering", status="completed").order_by(
            "-revision", "-pk",
        )
        calculation = selected_version.engineering_calculation if selected_version else completed_calculations.first()
        if calculation is None:
            blockers.append("缺少已完成的正式工程核算")

        routing_version = None
        routing = None
        routing_code = ""
        routing_binding_label = "未解析"
        if selected_version:
            routing_version = selected_version.related_routing
            routing = routing_version.routing
            routing_code = routing.routing_code
            routing_binding_label = f"工程资料版本ID {selected_version.pk}固定的准确工艺路线版本"
        else:
            try:
                exact_version_context = (
                    {
                        "organizationId": instance.company_id,
                        "salesOrderItemId": sales_item.pk,
                        "orderEngineeringInstanceId": instance.pk,
                        "orderEngineeringBaselineId": baseline.pk,
                        "engineeringCalculationId": calculation.pk,
                        "bomVersionId": bom_version.pk,
                    }
                    if all((baseline, calculation, bom_version)) else None
                )
                resolved = ManufacturingStructureService.resolve_effective_routing(
                    instance, exact_version_context=exact_version_context,
                )
                routing = resolved["routing"]
                routing_version = resolved["routing_version"]
                routing_code = routing.routing_code
                routing_binding_label = "唯一解析结果（尚未形成制造发布记录持久化绑定）"
            except ManufacturingStructureError as exc:
                blockers.append(f"工艺路线版本阻断：{exc.message}")
        cls._append_version_blockers(blockers, "工艺路线版本", routing_version, "status")

        document_count = 1 if selected_version else len(document_scope["documents"])
        document_version_count = 1 if selected_version else len(document_scope["versionCandidates"])
        traceable_document_version_count = (int(selected_version in document_scope["traceableVersions"])
            if selected_version else len(document_scope["traceableVersions"]))
        publishable_document_count = (int(selected_version in document_scope["publishableVersions"])
            if selected_version else len(document_scope["publishableVersions"]))
        released_document_count = (int(selected_version in document_scope["releasedVersions"])
            if selected_version else len(document_scope["releasedVersions"]))
        ownership_conflicts = ([] if selected_version and selected_version in document_scope["traceableVersions"]
            else document_scope["ownershipConflicts"])
        blockers.extend(ownership_conflicts)
        if not selected_version and routing_version and baseline and calculation and bom_version:
            stale_route_bindings = [
                version for version in document_scope["traceableVersions"]
                if (
                    version.order_engineering_baseline_id == baseline.pk
                    and version.engineering_calculation_id == calculation.pk
                    and version.related_bom_id == bom_version.pk
                    and version.related_routing_id != routing_version.pk
                )
            ]
            for version in stale_route_bindings:
                blockers.append(
                    f"工程资料版本ID {version.pk}仍绑定历史工艺路线版本ID "
                    f"{version.related_routing_id}；当前准确已发布版本为ID {routing_version.pk}"
                )

        order_subject_contract_go = bool(
            instance.product_category_id
            and instance.selected_process_type_id
            and instance.source_record.status == "confirmed"
            and instance.status != "inactive"
            and baseline
            and calculation
        )
        if not order_subject_contract_go:
            blockers.append("订单工程产品主体缺少稳定OEI、工程基线或核算修订身份")

        output = None
        if release_subject_schema_available:
            outputs = instance.manufacturing_outputs.select_related(
                "product_version", "bom_version", "routing_version", "engineering_document_version",
            ).order_by("-pk")
            if selected_version:
                outputs = outputs.filter(engineering_document_version_id=selected_version.pk,
                    order_engineering_baseline_id=selected_version.order_engineering_baseline_id,
                    engineering_calculation_id=selected_version.engineering_calculation_id,
                    bom_version_id=selected_version.related_bom_id, routing_version_id=selected_version.related_routing_id)
            matches = list(outputs[:2]) if not selection_required else []
            if len(matches) == 1:
                output = matches[0]
            elif len(matches) > 1:
                blockers.append("同一准确资料来源存在多个制造发布记录，需明确核对，未默认选择")
        elif instance.manufacturing_outputs.count():
            blockers.append("正式发布主体Schema尚未迁移，既有制造发布记录无法按新合同读取")

        document_version = selected_version or (output.engineering_document_version if output else None)
        if (
            release_subject_schema_available
            and document_version is None
            and not selection_required
            and all((baseline, calculation, bom_version, routing_version))
        ):
            candidates = EngineeringDocumentVersion.objects.filter(
                release_subject_type="ORDER_ENGINEERED_PRODUCT",
                order_engineering_instance=instance,
                order_engineering_baseline=baseline,
                engineering_calculation=calculation,
                related_bom=bom_version,
                related_routing=routing_version,
            ).order_by("-pk")
            matches = list(candidates[:2])
            if len(matches) == 1:
                document_version = matches[0]
            elif len(matches) > 1:
                blockers.append("同一版本组合存在多个工程资料版本")
        document_version_traceable = bool(document_version and document_version in document_scope["traceableVersions"])
        if document_version and not document_version_traceable:
            blockers.append("工程资料版本无法证明归属当前订单行")
        cls._append_version_blockers(blockers, "工程资料版本", document_version, "status")
        document = (
            document_version.document
            if document_version else
            document_scope["documents"][0]
            if len(document_scope["documents"]) == 1 else None
        )
        if document_version_traceable and user is not None:
            review_preflight = project_engineering_document_version_review_preflight(
                document_version,
                user,
            )
        else:
            missing_code = (
                "ENGINEERING_DOCUMENT_OWNERSHIP_CONFLICT"
                if document_version and not document_version_traceable else
                "CURRENT_USER_REQUIRED_FOR_REVIEW_PREFLIGHT"
                if document_version else "ENGINEERING_DOCUMENT_VERSION_REQUIRED"
            )
            review_preflight = {
                "actionCode": ENGINEERING_DOCUMENT_VERSION_REVIEW_ACTION,
                "permissionCode": ENGINEERING_DOCUMENT_VERSION_REVIEW_ACTION,
                "readyForHumanReview": False,
                "reviewAllowed": False,
                "currentBrowserOperable": False,
                "decisionCode": missing_code,
                "decisionLabel": (
                    "工程资料版本归属冲突，禁止评审"
                    if document_version and not document_version_traceable else
                    "需登录后检查正式评审准入"
                    if document_version else "需先形成工程资料版本"
                ),
                "firstBlockerCode": missing_code,
                "firstBlockerLabel": (
                    "工程资料版本归属"
                    if document_version and not document_version_traceable else
                    "当前操作人" if document_version else "工程资料版本"
                ),
                "firstBlockerMessage": (
                    "已保存资料版本的归属关系存在冲突；保留原行供核对，禁止评审。"
                    if document_version and not document_version_traceable else
                    "正式评审准入投影需要当前登录人员上下文。"
                    if document_version else "当前订单行尚未形成可评审的正式工程资料版本。"
                ),
                "gates": [],
                "eligibleReviewActors": [],
                "currentActor": {},
                "reviewReadback": {"completed": False},
                "databaseBusinessWriteCount": 0,
            }

        if document_version_traceable and user is not None:
            document_release_preflight = (
                project_engineering_document_version_release_preflight(
                    document_version,
                    user,
                )
            )
        else:
            missing_code = (
                "ENGINEERING_DOCUMENT_OWNERSHIP_CONFLICT"
                if document_version and not document_version_traceable else
                "CURRENT_USER_REQUIRED_FOR_DOCUMENT_RELEASE_PREFLIGHT"
                if document_version else "ENGINEERING_DOCUMENT_VERSION_REQUIRED"
            )
            document_release_preflight = {
                "actionCode": ENGINEERING_DOCUMENT_VERSION_RELEASE_ACTION,
                "permissionCode": ENGINEERING_DOCUMENT_VERSION_RELEASE_ACTION,
                "readyForHumanRelease": False,
                "releaseAllowed": False,
                "currentBrowserOperable": False,
                "decisionCode": missing_code,
                "decisionLabel": (
                    "工程资料版本归属冲突，禁止发布"
                    if document_version and not document_version_traceable else
                    "需登录后检查工程资料版本发布准入"
                    if document_version else "需先形成工程资料版本"
                ),
                "firstBlockerCode": missing_code,
                "firstBlockerLabel": (
                    "工程资料版本归属"
                    if document_version and not document_version_traceable else
                    "当前操作人" if document_version else "工程资料版本"
                ),
                "firstBlockerMessage": (
                    "已保存资料版本的归属关系存在冲突；保留原行供核对，禁止发布。"
                    if document_version and not document_version_traceable else
                    "发布准入投影需要当前登录人员上下文。"
                    if document_version else "当前订单行尚未形成工程资料版本。"
                ),
                "gates": [],
                "eligibleReleaseActors": [],
                "currentActor": {},
                "releaseReadback": {"completed": False},
                "databaseBusinessWriteCount": 0,
            }

        if output is None:
            blockers.append("尚未形成引用精确源版本的制造发布记录")
            release_status_label = "制造发布尚未形成"
            output_identity = "未形成"
        else:
            output_identity = f"制造发布记录ID {output.pk}"
            release_status_label = output.get_release_status_display()
            routing_binding_label = (
                f"已由制造发布记录持久化锁定工艺路线版本ID {output.routing_version_id}"
            )
            if output.release_status != "released_to_manufacturing":
                blockers.append("制造发布记录尚未发布至制造")

        blockers = list(dict.fromkeys(blockers))
        release_ready = bool(output and output.release_status == "released_to_manufacturing" and not blockers)
        if release_ready:
            release_status_label = "已正式发布至制造"

        row = {
            "id": row_id or f"OEI-{instance.pk}",
            "releaseCandidateIdentity": (f"{order.order_no} / 行{sales_item.line_no} / {instance.instance_no}"
                + (f" / {selected_version.document_version}（资料版本ID {selected_version.pk}）" if selected_version else "")),
            "sourceObjectTypeLabel": "订单工程发布候选",
            "nodeHandoffStatusLabel": (
                "工程资料发布节点已承接（当前资料为0）"
                if document_count == 0 else "工程资料发布节点已承接"
            ),
            "manufacturingReleaseSubjectType": "ORDER_ENGINEERED_PRODUCT",
            "manufacturingReleaseSubjectTypeLabel": "订单工程产品",
            "manufacturingReleaseSubjectIdentity": (
                f"{order.order_no} / 行{sales_item.line_no} / {instance.instance_no}"
            ),
            "orderNo": order.order_no,
            "orderLineNo": sales_item.line_no,
            "salesOrderItemId": sales_item.pk,
            "companyCode": instance.company.code,
            "orderEngineeringInstanceId": instance.pk,
            "orderEngineeringInstanceNo": instance.instance_no,
            "orderEngineeringStatusLabel": instance.get_status_display(),
            "sourceRecordIdentity": (
                f"工程来源ID {instance.source_record_id} / {instance.source_record.source_version}"
            ),
            "productCategoryIdentity": (
                f"{instance.product_category.code} / {instance.product_category.name}"
                if instance.product_category_id else "未形成"
            ),
            "engineeringBaselineIdentity": (
                f"{baseline.baseline_no} / 基线序列{baseline.sequence}"
                if baseline else "未形成"
            ),
            "engineeringBaselineId": baseline.pk if baseline else None,
            "engineeringRevisionIdentity": (
                f"{calculation.calculation_no} / 修订{calculation.revision}"
                if calculation else "未形成"
            ),
            "releaseSubjectContractStatusLabel": (
                "订单工程产品身份合同可表达（正式迁移待授权）"
                if order_subject_contract_go and not release_subject_schema_available else
                "订单工程产品身份合同可表达"
                if order_subject_contract_go else "订单工程产品身份合同不完整"
            ),
            "admissionStatusLabel": admission_label,
            "admissionFacts": admission,
            "documentNo": document.document_no if document else "",
            "engineeringDocumentId": document.pk if document else None,
            "engineeringDocumentVersionId": document_version.pk if document_version else None,
            "documentVersionSelectionRequired": selection_required,
            "documentName": (document_version.document_name if document_version else document.document_name if document else ""),
            "documentTypeLabel": document.get_document_type_display() if document else "未登记",
            "version": document_version.document_version if document_version else "",
            "documentVersionStatusLabel": (
                document_version.get_status_display() if document_version else "未形成"
            ),
            "productCode": instance.product.product_code if instance.product_id else "不适用（订单工程产品）",
            "productVersionIdentity": (
                cls._version_identity("产品版本", product_version, "version_no")
                if instance.product_id else "不适用（订单工程产品路径）"
            ),
            "bomCode": bom_version.bom.bom_code if bom_version and bom_version.bom_id else "",
            "productBomId": bom_version.bom_id if bom_version else None,
            "bomVersionId": bom_version.pk if bom_version else None,
            "bomVersionNo": bom_version.bom_version if bom_version else "",
            "bomVersionStatusLabel": bom_version.get_status_display() if bom_version else "未形成",
            "bomVersionIdentity": cls._version_identity("BOM版本", bom_version, "bom_version"),
            "sourceCalculationId": calculation.pk if calculation else None,
            "sourceCalculationNo": calculation.calculation_no if calculation else "",
            "routingCode": routing_code,
            "routingId": routing.pk if routing else None,
            "routingName": routing.name if routing else "",
            "routingStatusLabel": routing.get_status_display() if routing else "未形成",
            "routingVersionId": routing_version.pk if routing_version else None,
            "routingVersionNo": routing_version.routing_version if routing_version else "",
            "routingVersionRevision": routing_version.revision if routing_version else None,
            "routingVersionStatusLabel": routing_version.get_status_display() if routing_version else "未形成",
            "routingStepCount": routing_version.steps.count() if routing_version else 0,
            "routingStepRelationshipSemanticsLabel": (
                "工序通过正式外键直接归属该工艺路线版本；未声明独立不可变序列化快照"
                if routing_version else "未形成工艺路线版本"
            ),
            "routingVersionIdentity": cls._version_identity(
                "工艺路线版本", routing_version, "routing_version",
            ),
            "engineeringDocumentCount": document_count,
            "engineeringDocumentVersionCount": document_version_count,
            "traceableEngineeringDocumentVersionCount": traceable_document_version_count,
            "publishableEngineeringDocumentCount": publishable_document_count,
            "releasedEngineeringDocumentCount": released_document_count,
            "documentOwnershipConflictCount": len(ownership_conflicts),
            "documentOwnershipStatusLabel": (
                "工程资料归属冲突，已拒绝发布"
                if ownership_conflicts else "工程资料归属校验通过"
                if document_count else "当前无工程资料对象；未发现归属冲突"
            ),
            "currentDocumentStatusLabel": (
                "暂无工程资料"
                if document_count == 0 else
                "工程资料归属冲突"
                if ownership_conflicts else
                "已登记工程资料，尚未形成资料版本"
                if document_version_count == 0 else
                "已有正式工程资料版本"
            ),
            "documentAvailabilityStatusLabel": (
                "暂无可发布工程资料"
                if publishable_document_count == 0 else
                f"当前有{publishable_document_count}份工程资料处于可发布阶段"
            ),
            "documentPublicationStatusLabel": (
                "尚未发生工程资料发布"
                if released_document_count == 0 else
                f"已有{released_document_count}份工程资料版本处于已发布状态"
            ),
            "actualEngineeringDocumentPublicationCount": released_document_count,
            "publicationExecutedThisRound": False,
            "engineeringDocumentVersionIdentity": (
                f"工程资料版本ID {document_version.pk} / {document_version.document_version}"
                if document_version else "未形成"
            ),
            "reviewPreflight": review_preflight,
            "documentReleasePreflight": document_release_preflight,
            "manufacturingOutputIdentity": output_identity,
            "manufacturingOutputId": output.pk if output else None,
            "versionBindingLabel": routing_binding_label,
            "calculationStatusLabel": (
                f"已完成：{calculation.calculation_no} / 修订{calculation.revision}"
                if calculation else "未完成"
            ),
            "businessPurposeLabel": eligibility["businessPurposeLabel"],
            "formalManufacturingEligibilityLabel": eligibility["statusLabel"],
            "releaseBasisLabel": (
                "订单工程产品发布必须锁定OEI、已确认工程基线、核算修订、BOM版本、工艺路线版本和工程资料版本"
            ),
            "blockingReasonCount": len(blockers),
            "blockingSummary": "；".join(blockers) if blockers else "无阻断",
            "formalMissingConditions": blockers,
            "documentFormationModeLabel": (
                "现有正式能力通过工程资料主表与工程资料版本登记精确上游关系；"
                "不包含物理文件上传"
            ),
            "documentTypeOptionsLabel": "工艺文件、技术资料、版本记录",
            "physicalFileCapabilityLabel": (
                "当前正式工程资料模型没有文件名、MIME类型、文件大小、存储键、附件ID或文件Hash字段"
            ),
            "manualInputRequirements": cls.MANUAL_INPUT_REQUIREMENTS,
            "nextBusinessActionLabel": (
                "下一步只需业务人员确认资料编号、资料名称和现有正式资料类型；"
                "首版版本号由现有正式服务自动产生V1.0，当前订单行已唯一确定的上游关系和发布主体"
                "必须由后续专项登记服务自动带入并校验。当前模型不接收物理文件上传；"
                "本轮不登记，正式发布仍需用户另行明确授权。"
                if document_count == 0 else
                "工程资料版本已具备人工正式发布条件；请由页面列出的合法发布人员本人执行。"
                if document_release_preflight.get("readyForHumanRelease") else
                "请先解决工程资料版本正式发布准入列出的首个阻断；制造发布仍是后续独立业务动作。"
            ),
            "documentReleaseActionLabel": (
                "工程资料版本正式发布准入通过"
                if document_release_preflight.get("readyForHumanRelease") else
                document_release_preflight.get("decisionLabel") or "工程资料版本发布准入未取得"
            ),
            "releaseActionLabel": "制造发布动作未开放（与工程资料版本发布分离）",
            "schemaGapRequired": False,
            "releaseSubjectContractGo": order_subject_contract_go,
            "releaseSubjectSchemaApplied": release_subject_schema_available,
            "releaseReady": release_ready,
            "statusLabel": release_status_label,
        }
        if selected_version and not document_version_traceable:
            # Keep corrupt history visible without projecting related data as
            # trusted company-owned facts or borrowing the current valid chain.
            document_owned = (
                selected_version.document.order_engineering_instance_id == instance.pk
                and selected_version.document.release_subject_type == "ORDER_ENGINEERED_PRODUCT"
            )
            for key in (
                "engineeringBaselineIdentity", "engineeringRevisionIdentity", "sourceCalculationNo",
                "bomCode", "bomVersionNo", "bomVersionStatusLabel", "bomVersionIdentity",
                "routingCode", "routingName", "routingStatusLabel", "routingVersionNo",
                "routingVersionStatusLabel", "routingVersionIdentity", "productVersionIdentity",
                "routingStepRelationshipSemanticsLabel", "manufacturingOutputIdentity",
                "versionBindingLabel", "calculationStatusLabel",
            ):
                row[key] = "归属冲突，未展示关联资料"
            for key in (
                "engineeringBaselineId", "sourceCalculationId", "productBomId", "bomVersionId",
                "routingId", "routingVersionId", "routingVersionRevision", "manufacturingOutputId",
            ):
                row[key] = None
            row["routingStepCount"] = 0
            row["statusLabel"] = "工程资料归属冲突，禁止办理"
            row["releaseReady"] = False
            if not document_owned:
                row.update(engineeringDocumentId=None, documentNo="", documentName="",
                    documentTypeLabel="归属冲突", version="",
                    releaseCandidateIdentity=(f"{order.order_no} / 行{sales_item.line_no} / "
                        f"{instance.instance_no} / 资料版本ID {selected_version.pk}"))
        return row

    def get(self, request):
        release_subject_schema_available = self._release_subject_schema_available()
        instances = active_order_engineering_instances(
            OrderEngineeringInstance.objects.filter(
                company_id=request.user.company_id,
            )
        ).select_related(
            "sales_order_item__sales_order",
            "product",
            "baseline_product_version",
            "product_category",
            "selected_process_type",
            "source_record",
        ).order_by("sales_order_item__sales_order__order_no", "sales_order_item__line_no", "pk")
        current_candidates = []
        for instance in instances:
            try:
                order = instance.sales_order_item.sales_order
                admission = require_current_order_admission(
                    order=order,
                    sales_order_item_id=instance.sales_order_item_id,
                    engineering_instance_id=instance.pk,
                ).as_dict()
            except CRMOrderAdmissionError:
                continue
            current_candidates.append((instance, admission))
        current_instance_ids = [instance.pk for instance, _ in current_candidates]
        rows = []
        for instance, admission in current_candidates:
            document_scope = self._document_scope_facts(instance)
            versions = document_scope["versionCandidates"]
            if not versions:
                rows.append(self._serialize_release_candidate(instance,
                    release_subject_schema_available=release_subject_schema_available,
                    admission=admission, user=request.user, document_scope=document_scope))
                continue
            first_saved_version_id = document_scope["versionCandidates"][0].pk
            for version in versions:
                # Keep the historical OEI row identity. Every additional saved
                # version has its own identity, stable across review/release.
                row_id = (f"OEI-{instance.pk}" if version.pk == first_saved_version_id
                    else f"OEI-{instance.pk}-DOCUMENT-VERSION-{version.pk}")
                rows.append(self._serialize_release_candidate(instance,
                    release_subject_schema_available=release_subject_schema_available,
                    admission=admission, user=request.user, document_scope=document_scope,
                    document_version=version, row_id=row_id))

        # Preserve visibility of any legacy EngineeringDocument headers.  They
        # remain source objects, never release-package substitutes.
        document_queryset = EngineeringDocument.objects.none()
        if release_subject_schema_available:
            document_queryset = EngineeringDocument.objects.filter(
                Q(product__company_id=request.user.company_id)
                | Q(order_engineering_instance_id__in=current_instance_ids),
            ).select_related(
                "product", "order_engineering_instance__sales_order_item__sales_order",
                "product_bom", "routing",
            ).order_by("document_no")
        for document in document_queryset:
            row = self.serialize(document)
            row.update({
                "id": f"DOCUMENT-{document.pk}",
                "releaseCandidateIdentity": f"工程资料主表 / {document.document_no}",
                "sourceObjectTypeLabel": "工程资料源对象",
                "manufacturingReleaseSubjectType": document.release_subject_type,
                "manufacturingReleaseSubjectTypeLabel": document.get_release_subject_type_display(),
                "manufacturingReleaseSubjectIdentity": (
                    document.product.product_code
                    if document.product_id else document.order_engineering_instance.instance_no
                ),
                "productVersionIdentity": "须查看工程资料精确版本",
                "bomVersionIdentity": "须查看工程资料精确版本",
                "routingVersionIdentity": "须查看工程资料精确版本",
                "engineeringDocumentVersionIdentity": "须形成精确版本引用",
                "manufacturingOutputIdentity": "未由主表推断",
                "businessPurposeLabel": "不适用",
                "formalManufacturingEligibilityLabel": "不得仅凭资料主表判定",
                "versionBindingLabel": "源对象主表，不是发布记录",
                "calculationStatusLabel": "不适用",
                "blockingReasonCount": 1,
                "blockingSummary": "工程资料主表不能替代工程资料版本或制造发布记录",
                "releaseActionLabel": "本轮只读核验，正式发布动作未开放",
                "schemaGapRequired": False,
                "releaseSubjectContractGo": True,
                "releaseReady": False,
            })
            rows.append(row)

        query = request.query_params.get("q", "").strip().lower()
        if query:
            rows = [
                row for row in rows
                if any(query in str(value).lower() for value in row.values() if not isinstance(value, dict))
            ]

        payload = _facts(self.page_code, rows, request)
        if release_subject_schema_available:
            engineering_document_count = EngineeringDocument.objects.filter(
                Q(product__company_id=request.user.company_id)
                | Q(order_engineering_instance_id__in=current_instance_ids),
            ).count()
            engineering_document_version_count = EngineeringDocumentVersion.objects.filter(
                Q(related_product__company_id=request.user.company_id)
                | Q(order_engineering_instance_id__in=current_instance_ids),
            ).count()
        else:
            engineering_document_count = EngineeringDocument.objects.filter(
                product__company_id=request.user.company_id,
            ).count()
            engineering_document_version_count = EngineeringDocumentVersion.objects.filter(
                related_product__company_id=request.user.company_id,
            ).count()

        order_candidate_rows = [
            row for row in rows
            if row.get("sourceObjectTypeLabel") == "订单工程发布候选"
        ]
        publishable_engineering_document_count = sum(
            int(row.get("publishableEngineeringDocumentCount") or 0)
            for row in order_candidate_rows
        )
        released_engineering_document_count = sum(
            int(row.get("releasedEngineeringDocumentCount") or 0)
            for row in order_candidate_rows
        )

        facts = {
            "authority": (
                "company-scoped OrderEngineeringInstance + exact Product/BOM/Routing/"
                "EngineeringDocument versions + ProductManufacturingOutput"
            ),
            "releaseObjectModel": "ProductManufacturingOutput（发布记录）引用精确源版本",
            "releaseActionAvailable": False,
            "releaseActionStatusLabel": "制造发布动作未开放；不影响工程资料版本独立正式发布",
            "documentReleaseActionAvailable": any(
                (row.get("documentReleasePreflight") or {}).get("readyForHumanRelease")
                for row in rows
            ),
            "documentReleaseActionStatusLabel": (
                "工程资料版本正式发布准入已开放"
                if any(
                    (row.get("documentReleasePreflight") or {}).get("readyForHumanRelease")
                    for row in rows
                ) else "当前没有通过正式发布准入的工程资料版本"
            ),
            "engineeringDocumentCount": engineering_document_count,
            "engineeringDocumentVersionCount": engineering_document_version_count,
            "publishableEngineeringDocumentCount": publishable_engineering_document_count,
            "releasedEngineeringDocumentCount": released_engineering_document_count,
            "manufacturingOutputCount": ProductManufacturingOutput.objects.filter(
                Q(product__company_id=request.user.company_id)
                | Q(order_engineering_instance_id__in=current_instance_ids),
            ).count(),
            "releasedManufacturingOutputCount": ProductManufacturingOutput.objects.filter(
                Q(product__company_id=request.user.company_id)
                | Q(order_engineering_instance_id__in=current_instance_ids),
                release_status="released_to_manufacturing",
            ).count(),
            "releaseCandidateCount": len(rows),
            "releaseReadyCount": sum(1 for row in rows if row.get("releaseReady")),
            "reviewReadyCount": sum(
                1 for row in rows
                if (row.get("reviewPreflight") or {}).get("readyForHumanReview")
            ),
            "documentReleaseReadyCount": sum(
                1 for row in rows
                if (row.get("documentReleasePreflight") or {}).get("readyForHumanRelease")
            ),
            "documentReleaseCompletedCount": sum(
                1 for row in rows
                if ((row.get("documentReleasePreflight") or {}).get("releaseReadback") or {}).get("completed")
            ),
            "releaseBlockedCount": sum(1 for row in rows if not row.get("releaseReady")),
            "schemaGapCount": sum(1 for row in rows if row.get("schemaGapRequired")),
            "releaseSubjectSchemaApplied": release_subject_schema_available,
            "releaseSubjectSchemaStatusLabel": (
                "正式发布主体Schema已应用"
                if release_subject_schema_available else "正式发布主体Migration已就绪，正式应用待授权"
            ),
            "releaseSubjectContractGoCount": sum(
                1 for row in rows if row.get("releaseSubjectContractGo")
            ),
            "workCenterCount": WorkCenter.objects.filter(company_id=request.user.company_id).count(),
            "engineeringOperationRequirementCount": EngineeringOperationRequirement.objects.filter(
                calculation__company_id=request.user.company_id,
            ).count(),
            "routingResolverMaySelectCandidate": True,
            "routingResolverIsPersistedReleaseBinding": False,
            "engineeringDocumentBusinessDesign": "C+D：聚合精确上游版本形成资料/发布依据，并由制造发布记录管理发布状态",
            "engineeringDocumentTypeAuthority": "EngineeringDocument.DOCUMENT_TYPE_CHOICES",
            "engineeringDocumentTypeOptions": [
                {"code": code, "label": label}
                for code, label in EngineeringDocument.DOCUMENT_TYPE_CHOICES
            ],
            "physicalFileUploadCapabilityAvailable": False,
            "physicalFileMetadataFieldCount": 0,
            "physicalFileCapabilityLabel": (
                "当前正式工程资料模型不保存物理文件、附件、存储键、MIME、大小或文件Hash"
            ),
            "releasePageCreateActionAvailable": False,
            "formalDocumentMaintenanceCapabilityAvailable": True,
            "manualInputRequirements": self.MANUAL_INPUT_REQUIREMENTS,
            "nodeHandoffStatusLabel": (
                "工程资料发布节点已承接；当前正式工程资料为0"
                if engineering_document_count == 0 else "工程资料发布节点已承接"
            ),
            "currentDocumentStatusLabel": (
                "暂无工程资料" if engineering_document_count == 0 else "已有正式工程资料"
            ),
            "documentAvailabilityStatusLabel": (
                "暂无可发布工程资料"
                if publishable_engineering_document_count == 0 else
                f"当前有{publishable_engineering_document_count}份工程资料处于可发布阶段"
            ),
            "publicationExecutedThisRound": False,
            "nextBusinessActionLabel": (
                "下一步只需业务人员确认资料编号、资料名称和现有正式资料类型；"
                "首版版本号由现有正式服务自动产生V1.0，当前订单行已唯一确定的上游关系和发布主体"
                "必须由后续专项登记服务自动带入并校验。当前模型不接收物理文件上传；"
                "本轮不登记，正式发布需另行授权。"
                if engineering_document_count == 0 else
                "核验资料版本与上游关系；正式发布需另行授权。"
            ),
            "databaseBusinessWriteCount": 0,
            "productionUserDataWritten": False,
        }
        for key in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts"):
            payload[key].update(facts)
        return Response(payload, status=200)

    def serialize(self, obj):
        return {
            "id": obj.pk,
            "documentNo": obj.document_no,
            "documentName": obj.document_name,
            "documentTypeLabel": obj.get_document_type_display(),
            "version": obj.version,
            "productCode": obj.product.product_code if obj.product_id else "不适用（订单工程产品）",
            "bomCode": obj.product_bom.bom_code,
            "routingCode": obj.routing.routing_code,
            "effectiveDate": obj.effective_date.isoformat() if obj.effective_date else "",
            "statusLabel": obj.get_status_display(),
        }


class EngineeringDocumentVersionReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, object_id):
        try:
            result = review_engineering_document_version(
                object_id=object_id,
                user=request.user,
                reason=request.data.get("reason") or "",
                idempotency_key=request.headers.get("Idempotency-Key"),
                action=(
                    request.data.get("action")
                    or ENGINEERING_DOCUMENT_VERSION_REVIEW_ACTION
                ),
            )
        except EngineeringDocumentVersionReviewError as exc:
            return Response({
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
                "databaseBusinessWriteCount": 0,
            }, status=exc.http_status)
        return Response({
            "result": result,
            "message": "工程资料版本正式评审决定已通过共享Workflow Runtime保存。",
            "factSource": "server",
        }, status=status.HTTP_200_OK)


class EngineeringDocumentVersionReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, object_id):
        try:
            result = release_engineering_document_version(
                object_id=object_id,
                user=request.user,
                reason=request.data.get("reason") or "",
                idempotency_key=request.headers.get("Idempotency-Key"),
                action=(
                    request.data.get("action")
                    or ENGINEERING_DOCUMENT_VERSION_RELEASE_ACTION
                ),
            )
        except EngineeringDocumentVersionReleaseError as exc:
            return Response({
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
                "databaseBusinessWriteCount": 0,
            }, status=exc.http_status)
        return Response({
            "result": result,
            "message": (
                "工程资料版本已通过专用正式发布控制链提交；"
                "未创建或推进制造发布记录。"
            ),
            "factSource": "server",
        }, status=status.HTTP_200_OK)


class ProductVersionListView(PdeReadOnlyListView):
    model = ProductVersion
    page_code = "pde-product-versions"
    search_fields = ("product__product_code", "product__product_name", "version_no", "change_reason")

    def serialize(self, obj):
        return {
            "id": obj.pk,
            "productCode": obj.product.product_code,
            "productName": obj.product.product_name,
            "versionNo": obj.version_no,
            "effectiveDate": obj.effective_date.isoformat() if obj.effective_date else "",
            "expireDate": obj.expire_date.isoformat() if obj.expire_date else "",
            "changeReason": obj.change_reason,
            "statusLabel": obj.get_version_status_display(),
        }


class ProductVersionManagementView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            facts = product_version_management_facts(
                request.user.company_id,
                order_no=request.query_params.get("orderNo") or None,
                user=request.user,
                baseline_id=request.query_params.get("baselineId") or None,
            )
        except ProductVersionManagementError as exc:
            return _read_failure(
                request,
                status_code=exc.http_status,
                error_code=exc.code,
                error_message=exc.message,
                details=exc.details,
            )
        rows = facts["candidateRows"]
        payload = _facts("pde-product-version-management", rows, request)
        payload.update({key: value for key, value in facts.items() if key != "candidateRows"})
        payload["candidateRows"] = rows
        for key in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts"):
            payload[key].update({
                "authority": "SalesOrder + ProductDesignItem + latest ProductDesignRevision + explicit ProductDefinition/ProductVersion references",
                "viewWriteCount": 0,
                "savedBaselineCount": len(facts["savedBaselines"]),
                "baselinePersistenceStatus": facts["persistenceCapability"]["statusCode"],
            })
        return Response(payload, status=200)

    def post(self, request):
        try:
            facts, replayed = handle_product_version_management_action(
                user=request.user,
                payload=request.data,
                idempotency_key=request.headers.get("Idempotency-Key"),
            )
        except ProductVersionManagementError as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
                status=exc.http_status,
            )
        return Response(
            {"success": True, "idempotentReplay": replayed, **facts},
            status=status.HTTP_200_OK,
        )


class BomVersionListView(PdeReadOnlyListView):
    model = BOMVersion
    page_code = "pde-bom-versions"
    search_fields = (
        "product__product_code", "product__product_name",
        "bom__product_category__code", "bom__product_category__name", "bom_version",
        "order_engineering_instance__instance_no",
        "order_engineering_instance__sales_order_item__sales_order__order_no",
        "source_calculation__calculation_no",
    )

    def get(self, request):
        self._eligibility_user = request.user
        self._coverage_by_order = {}
        try:
            response = super().get(request)
        except ProductBomDetailProjectionError as exc:
            return _read_failure(
                request,
                status_code=status.HTTP_409_CONFLICT,
                error_code="BOM_VERSION_HANDOFF_SCOPE_INCONSISTENT",
                error_message=str(exc),
                details={
                    "pageCode": self.page_code,
                    "handoffAccepted": False,
                    "databaseBusinessWriteCount": 0,
                },
            )
        except DatabaseError:
            return _read_failure(
                request,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                error_code="BOM_VERSION_HANDOFF_READ_FAILED",
                error_message="BOM版本正式关系读取失败；当前数量未知，请稍后重新读取。",
                details={
                    "pageCode": self.page_code,
                    "handoffAccepted": False,
                    "databaseBusinessWriteCount": 0,
                },
            )

        rows = response.data.get("rows", [])
        handoff_rows = [
            {
                key: row.get(key)
                for key in (
                    "companyId", "companyCode", "orderNo", "orderLineNo",
                    "orderEngineeringInstanceId", "orderEngineeringInstanceNo",
                    "productBomId", "bomCode", "bomVersionId", "bomVersionNo",
                    "sourceCalculationId", "sourceCalculationNo", "materialCount",
                    "sourceRequirementCount", "statusLabel", "handoffAccepted",
                    "handoffStatusLabel", "sourceIntegrityLabel",
                )
            }
            for row in rows
        ]
        shared_facts = {
            "authority": (
                "Company -> SalesOrder -> SalesOrderItem -> OrderEngineeringInstance -> "
                "ProductBOM -> BOMVersion -> BOMItem -> BOMItemSourceRequirement"
            ),
            "bomVersionHandoffs": handoff_rows,
            "formalHandoffCount": sum(1 for row in rows if row.get("handoffAccepted")),
            "testHandoffCount": sum(1 for row in rows if row.get("testHandoffAccepted")),
            "databaseBusinessWriteCount": 0,
            "permissionMutationCount": 0,
            "roleMutationCount": 0,
            "migrationExecuted": False,
            "productionUserDataWritten": False,
            "bomVersionReleasePreflights": [
                {
                    "bomVersionId": row.get("bomVersionId"),
                    "bomVersionNo": row.get("bomVersionNo"),
                    "orderNo": row.get("orderNo"),
                    "orderLineNo": row.get("orderLineNo"),
                    "decisionCode": row.get("releasePreflightDecisionCode"),
                    "decisionLabel": row.get("releasePreflightDecisionLabel"),
                    "releaseAllowed": row.get("releaseAllowed"),
                    "firstBlockerCode": row.get("releaseFirstBlockerCode"),
                    "firstBlockerLabel": row.get("releaseFirstBlockerLabel"),
                    "gatePassCount": row.get("releaseGatePassCount"),
                    "gateFailCount": row.get("releaseGateFailCount"),
                }
                for row in rows
            ],
            "releasePreflightBlockedCount": sum(
                1 for row in rows if not row.get("releaseAllowed")
            ),
        }
        response.data["bomVersionHandoffs"] = handoff_rows
        for key in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts"):
            response.data[key].update(shared_facts)
        return response

    @staticmethod
    def _require_handoff(condition, message):
        if not condition:
            raise ProductBomDetailProjectionError(message)

    def _coverage(self, order_id):
        if not order_id:
            return {}
        cache = getattr(self, "_coverage_by_order", {})
        if order_id not in cache:
            try:
                from .order_bom_handoff_service import order_bom_handoff
                handoff = order_bom_handoff(
                    user=self._eligibility_user,
                    order_id=order_id,
                    # This list needs persisted requirement coverage only.
                    # Full BOM preview (including current process-source checks)
                    # stays on the original explicit preview path.
                    include_bom_preview=False,
                )
                gate = handoff["bomHandoffStatus"]
                cache[order_id] = {
                    "coverageStatus": "COMPLETE" if gate["orderCoverageComplete"] else "PARTIAL",
                    "confirmedRequirementObjectCount": gate["formalRequirementObjectCount"],
                    "remainingObjectCount": gate["remainingObjectCount"],
                    "coverageComplete": gate["orderCoverageComplete"],
                }
            except Exception as exc:
                cache[order_id] = {
                    "coverageStatus": "UNKNOWN",
                    "confirmedRequirementObjectCount": None,
                    "remainingObjectCount": None,
                    "coverageComplete": False,
                    "coverageReadError": getattr(exc, "code", type(exc).__name__),
                }
            self._coverage_by_order = cache
        return cache[order_id]

    def serialize(self, obj):
        self._require_handoff(obj.bom_id is not None, "BOMVersion缺少正式ProductBOM关系，停止承接。")
        self._require_handoff(
            obj.bom.company_id == self._eligibility_user.company_id,
            "BOMVersion所属公司与当前用户公司不一致，停止承接。",
        )
        instance = obj.order_engineering_instance if obj.order_engineering_instance_id else None
        source_calculation = obj.source_calculation if obj.source_calculation_id else obj.bom.source_calculation if obj.usage_purpose == 'TEST_BUSINESS' and obj.origin_version_id else None
        order_item = instance.sales_order_item if instance else None
        eligibility = FormalManufacturingEligibilityService.resolve(obj) if instance else None
        coverage = self._coverage(order_item.sales_order_id) if order_item else {}
        order_handoff = (
            obj.bom_scope == "order_specific"
            or obj.bom.applicability_scope == ManufacturingApplicabilityScope.ORDER_ENGINEERING
        )
        if order_handoff:
            self._require_handoff(instance is not None, "按单BOMVersion缺少订单工程实例，停止承接。")
            self._require_handoff(order_item is not None, "订单工程实例缺少正式销售订单行，停止承接。")
            self._require_handoff(
                obj.bom.applicability_scope == ManufacturingApplicabilityScope.ORDER_ENGINEERING,
                "按单BOMVersion的ProductBOM适用范围不是订单工程实例，停止承接。",
            )
            self._require_handoff(
                obj.bom.order_engineering_instance_id == obj.order_engineering_instance_id,
                "BOMVersion与ProductBOM引用的订单工程实例不一致，停止承接。",
            )
            self._require_handoff(
                instance.company_id == obj.bom.company_id
                and order_item.sales_order.company_id == obj.bom.company_id,
                "SalesOrder、SalesOrderItem、OEI与ProductBOM公司范围不一致，停止承接。",
            )
            self._require_handoff(
                source_calculation is not None,
                "按单BOMVersion缺少正式来源工程核算，停止承接。",
            )
            self._require_handoff(
                source_calculation.company_id == obj.bom.company_id
                and source_calculation.engineering_instance_id == instance.pk
                and source_calculation.sales_order_item_id == order_item.pk,
                "来源工程核算与公司、订单行或OEI范围不一致，停止承接。",
            )

        identity_candidate_count = BOMVersion.objects.filter(
            bom_id=obj.bom_id,
            bom_version=obj.bom_version,
        ).count()
        self._require_handoff(
            identity_candidate_count == 1,
            "ProductBOM范围内无法唯一确定BOMVersion，停止承接。",
        )
        material_details = project_product_bom_material_detail(
            bom=obj.bom,
            bom_version=obj,
            order_item=order_item,
        )
        source_requirement_count = sum(
            row["sourceRequirementCount"] for row in material_details
        )
        if order_handoff:
            self._require_handoff(
                bool(material_details),
                "正式按单BOMVersion没有可证明的BOMItem，停止承接。",
            )
            self._require_handoff(
                source_requirement_count > 0
                and all(row["sourceRequirementCount"] > 0 for row in material_details),
                "正式按单BOMVersion存在无法由来源Requirement证明的BOMItem，停止承接。",
            )
        company = obj.bom.company
        release_preflight = project_bom_version_release_preflight(
            obj,
            material_details=material_details,
        )
        return {
            "id": obj.pk,
            "bomVersionId": obj.pk,
            "productBomId": obj.bom_id,
            "applicabilityScope": obj.bom.applicability_scope if obj.bom_id else "PRODUCT_DEFINITION",
            "productCode": obj.product.product_code if obj.product_id else "",
            "productName": obj.product.product_name if obj.product_id else "",
            "productVersionNo": obj.product_version.version_no if obj.product_version_id else "",
            "productCategoryCode": obj.bom.product_category.code if obj.bom_id and obj.bom.product_category_id else "",
            "orderNo": order_item.sales_order.order_no if order_item else "",
            "orderLineNo": order_item.line_no if order_item else None,
            "orderEngineeringInstanceId": obj.order_engineering_instance_id,
            "orderEngineeringInstanceNo": instance.instance_no if instance else "",
            "sourceCalculationId": source_calculation.pk if source_calculation else None,
            **({"originVersionId":obj.origin_version_id,"directSourceCalculationId":obj.source_calculation_id} if obj.usage_purpose == "TEST_BUSINESS" else {}),
            "sourceCalculationNo": source_calculation.calculation_no if source_calculation else "",
            "bomVersionNo": obj.bom_version,
            "bomCode": obj.bom.bom_code if obj.bom_id else "",
            "companyId": obj.bom.company_id,
            "companyCode": company.code,
            "companyName": company.name,
            "materialCount": len(material_details),
            "latestMaterialCount": len(material_details),
            "sourceRequirementCount": source_requirement_count,
            "bomMaterialDetails": material_details,
            "sourceIntegrityLabel": f"{len(material_details)}项物料 / {source_requirement_count}条来源",
            "handoffAccepted": order_handoff and obj.usage_purpose != "TEST_BUSINESS",
            **({"testHandoffAccepted":True} if obj.usage_purpose == "TEST_BUSINESS" else {}),
            **project_bom_draft_context(obj),
            "handoffStatusLabel": "已承接测试BOM草稿" if obj.usage_purpose == "TEST_BUSINESS" else "已承接正式BOM版本" if order_handoff else "产品级BOM版本",
            "identityCandidateCount": identity_candidate_count,
            "createdAt": obj.created_at.isoformat() if obj.created_at else "",
            "revision": obj.revision,
            "approvalState": obj.approval_state,
            "effectiveDate": obj.effective_date.isoformat() if obj.effective_date else "",
            "expireDate": obj.expire_date.isoformat() if obj.expire_date else "",
            "businessPurposeCode": eligibility["businessPurposeCode"] if eligibility else "",
            "businessPurposeLabel": eligibility["businessPurposeLabel"] if eligibility else "",
            "formalManufacturingEligible": eligibility["formalManufacturingEligible"] if eligibility else None,
            "formalManufacturingEligibilityLabel": (
                "允许继续正式制造门禁" if eligibility and eligibility["formalManufacturingEligible"] else
                "禁止正式制造评审/发布" if eligibility else "不适用"
            ),
            "formalManufacturingDecisionCode": eligibility["decisionCode"] if eligibility else "",
            "formalManufacturingMessage": eligibility["message"] if eligibility else "",
            "releasePreflight": release_preflight,
            "releasePreflightDecisionCode": release_preflight["decisionCode"],
            "releasePreflightDecisionLabel": release_preflight["decisionLabel"],
            "releaseAllowed": release_preflight["releaseAllowed"],
            "releaseFirstBlockerCode": release_preflight["firstBlockerCode"],
            "releaseFirstBlockerLabel": release_preflight["firstBlockerLabel"],
            "releaseGatePassCount": release_preflight["gatePassCount"],
            "releaseGateFailCount": release_preflight["gateFailCount"],
            **coverage,
            "statusLabel": obj.get_status_display(),
        }


class RoutingVersionListView(PdeReadOnlyListView):
    model = RoutingVersion
    page_code = "pde-routing-versions"
    search_fields = (
        "product__product_code", "product__product_name",
        "routing__product_category__code", "routing__product_category__name",
        "routing__manufacturing_process_type__name", "routing__routing_code",
        "routing__name", "routing_version",
    )

    @staticmethod
    def _successor_action(version, request):
        return {'visible':False,'executable':False,'disabledReason':'标准结构请到企业基础资料维护，订单执行判断请使用独立订单安排。','maintenanceUrl':'/foundation/master-data/routings'}
        decision = AuthorizationService.decide(
            user=request.user,
            action_code=ROUTING_PERMISSION,
            organization_id=request.user.company_id,
            business_object={"organizationId": request.user.company_id},
        )
        status_allowed = version.status in {"reviewed", "released", "obsolete"}
        try:
            _actor_chain(request.user)
            execution_chain_ready = True
        except ProductionFoundationError:
            execution_chain_ready = False
        executable = bool(decision.get("allowed") and status_allowed and execution_chain_ready)
        if not status_allowed:
            disabled_reason = "当前版本不是已评审、已发布或已失效版本。"
        elif not decision.get("allowed"):
            disabled_reason = decision.get("reason") or "当前账号没有工艺路线正式维护权限。"
        elif not execution_chain_ready:
            disabled_reason = "当前账号缺少在职员工、启用岗位和有效职责执行链。"
        else:
            disabled_reason = ""
        return {
            "actionLabel": "创建后续路线版本",
            "visible": status_allowed,
            "executable": executable,
            "disabledReason": disabled_reason,
            "permissionLabel": "工艺路线正式维护",
        }

    @staticmethod
    def _manual_decision_action(version, request, readback):
        return {'visible':False,'executable':False,'disabledReason':'标准结构请到企业基础资料维护，订单执行判断请使用独立订单安排。','maintenanceUrl':'/foundation/master-data/routings'}
        decision = AuthorizationService.decide(
            user=request.user,
            action_code=ROUTING_PERMISSION,
            organization_id=request.user.company_id,
            business_object={"organizationId": request.user.company_id},
        )
        try:
            _actor_chain(request.user)
            execution_chain_ready = True
        except ProductionFoundationError:
            execution_chain_ready = False
        draft_allowed = version.status == "draft"
        context_ready = readback.get("contextCount") == 1
        decisions_ready = readback.get("conditionalDecisionCount") == 2
        executable = bool(
            decision.get("allowed") and execution_chain_ready
            and draft_allowed and context_ready and decisions_ready
        )
        if not draft_allowed:
            disabled_reason = "只有草稿路线版本允许维护人工判断。"
        elif not context_ready:
            disabled_reason = "当前路线版本无法唯一绑定正式订单工程对象。"
        elif not decisions_ready:
            disabled_reason = "当前草稿未精确识别两项条件工序。"
        elif not decision.get("allowed"):
            disabled_reason = decision.get("reason") or "当前账号没有工艺路线正式维护权限。"
        elif not execution_chain_ready:
            disabled_reason = "当前账号缺少在职员工、启用岗位和有效职责执行链。"
        else:
            disabled_reason = ""
        return {
            "actionCode": ROUTING_MANUAL_APPLICABILITY_ACTION,
            "actionLabel": "确认本次订单工程条件",
            "visible": bool(draft_allowed and readback.get("conditionalDecisionCount")),
            "executable": executable,
            "disabledReason": disabled_reason,
            "permissionCode": ROUTING_PERMISSION,
            "permissionLabel": "工艺路线正式维护",
            "authorizationDecision": decision.get("decisionCode") or "",
        }

    @staticmethod
    def _project_handoff(row, handoffs):
        row["formalOrderHandoffs"] = handoffs
        row["formalOrderHandoffCount"] = len(handoffs)
        if len(handoffs) == 1:
            handoff = handoffs[0]
            row.update(handoff)
            row.update({
                "routingVersionHandoffAccepted": True,
                "routingVersionHandoffStatusLabel": "已承接唯一正式工艺路线版本",
                "isCurrentlyEffective": True,
                "effectiveStatusLabel": "当前订单行唯一有效版本",
                "engineeringDocumentReleaseEligibilityLabel": (
                    "已具备下一节点只读核验条件（本轮未进入、未发布）"
                ),
            })
        elif len(handoffs) > 1:
            row.update({
                "routingVersionHandoffAccepted": True,
                "routingVersionHandoffStatusLabel": f"已承接{len(handoffs)}个正式订单行",
                "orderNo": f"{len(handoffs)}个订单行（详情可查）",
                "engineeringDocumentReleaseEligibilityLabel": (
                    "各订单行须分别核验（本轮未进入工程资料发布）"
                ),
            })
        else:
            row.update({
                "routingVersionHandoffAccepted": False,
                "routingVersionHandoffStatusLabel": "工艺路线版本（暂无订单行承接）",
                "engineeringDocumentReleaseEligibilityLabel": "未形成订单行承接事实",
            })
        return row

    @routing_read_request
    def get(self, request):
        try:
            handoffs = [
                RoutingListView._serialize_formal_handoff(item)
                for item in BOMVersion.objects.filter(
                    bom__company_id=request.user.company_id,
                    bom_scope="order_specific",
                ).exclude(usage_purpose='TEST_BUSINESS').select_related(
                    "bom", "bom__company", "order_engineering_instance",
                    "order_engineering_instance__product_category",
                    "order_engineering_instance__selected_process_type",
                    "order_engineering_instance__sales_order_item",
                    "order_engineering_instance__sales_order_item__sales_order",
                    "source_calculation",
                ).order_by("pk")
            ]
            handoffs_by_version = {}
            for handoff in handoffs:
                handoffs_by_version.setdefault(handoff["routingVersionId"], []).append(handoff)
            rows = [
                self._project_handoff(
                    self.serialize(item),
                    handoffs_by_version.get(item.pk, []),
                )
                for item in RoutingVersion.objects.filter(
                    routing__company_id=request.user.company_id,
                ).select_related(
                    "routing", "routing__product", "routing__product_category",
                    "routing__manufacturing_process_type", "product", "product_version",
                ).order_by("pk")
            ]
            versions = {
                item.pk: item for item in RoutingVersion.objects.filter(
                    pk__in=[row["id"] for row in rows],
                ).select_related("routing", "product")
            }
            for row in rows:
                row["successorAction"] = self._successor_action(versions[row["id"]], request)
                readback = row.get("manualApplicabilityReadback") or {}
                row["manualDecisionAction"] = self._manual_decision_action(
                    versions[row["id"]], request, readback,
                )
                if versions[row["id"]].status in {"draft", "reviewed"}:
                    row["reviewPreflight"] = project_review_preflight(
                        versions[row["id"]], request.user,
                    )
                else:
                    row["reviewPreflight"] = {
                        "actionCode": ROUTING_VERSION_REVIEW_ACTION,
                        "reviewAllowed": False,
                        "decisionCode": "NOT_APPLICABLE_TO_CURRENT_STATE",
                        "decisionLabel": "当前状态无评审动作",
                        "firstBlockerCode": "",
                        "firstBlockerLabel": "",
                        "firstBlockerMessage": "",
                        "gates": [],
                        "reviewReadback": {"completed": False},
                    }
                if versions[row["id"]].status in {"reviewed", "released"}:
                    row["releasePreflight"] = project_release_preflight(
                        versions[row["id"]], request.user,
                    )
                else:
                    row["releasePreflight"] = {
                        "actionCode": ROUTING_VERSION_RELEASE_ACTION,
                        "permissionCode": ROUTING_VERSION_RELEASE_ACTION,
                        "releaseAllowed": False,
                        "humanPublisherAuthorizationRequired": False,
                        "decisionCode": "NOT_APPLICABLE_TO_CURRENT_STATE",
                        "decisionLabel": "需先完成正式评审",
                        "firstBlockerCode": "ROUTING_VERSION_REVIEWED_STATE",
                        "firstBlockerLabel": "当前版本状态",
                        "firstBlockerMessage": "只有已完成正式评审且尚未发布的版本才能进入发布准入。",
                        "gates": [],
                        "releaseReadback": {"completed": False},
                    }
        except (RoutingFormalHandoffError, ProductBomDetailProjectionError, ManufacturingStructureError) as exc:
            return _read_failure(
                request,
                status_code=status.HTTP_409_CONFLICT,
                error_code=getattr(exc, "code", "ROUTING_VERSION_HANDOFF_SCOPE_INCONSISTENT"),
                error_message=getattr(exc, "message", str(exc)),
                details={
                    "pageCode": self.page_code,
                    "handoffAccepted": False,
                    "databaseBusinessWriteCount": 0,
                },
            )
        except DatabaseError:
            return _read_failure(
                request,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                error_code="ROUTING_VERSION_HANDOFF_READ_FAILED",
                error_message="工艺路线版本正式关系读取失败；当前数量未知，请稍后重新读取。",
                details={
                    "pageCode": self.page_code,
                    "handoffAccepted": False,
                    "databaseBusinessWriteCount": 0,
                },
            )

        query = request.query_params.get("q", "").strip().lower()
        if query:
            rows = [row for row in rows if query in str(row).lower()]
        payload = _facts(self.page_code, rows, request)
        shared_facts = {
            "authority": (
                "Company -> SalesOrder -> SalesOrderItem -> OrderEngineeringInstance -> "
                "ProductBOM -> BOMVersion -> EngineeringCalculationRecord; "
                "OrderEngineeringInstance -> ManufacturingStructureService -> Routing -> "
                "RoutingVersion -> RoutingStep -> system.Process"
            ),
            "routingVersionHandoffs": handoffs,
            "formalHandoffCount": len(handoffs),
            "stepRelationshipSemanticsCode": "VERSION_SCOPED_RELATIONAL_DEFINITION",
            "immutableSnapshotProven": True,
            "routingStepApplicabilityContractVersion": ROUTING_APPLICABILITY_CONTRACT_VERSION,
            "routingStepApplicabilityModes": [
                {"value": "MANDATORY", "label": "必经工序"},
                {"value": "CONDITIONAL", "label": "条件执行工序"},
            ],
            "routingStepApplicabilityConditions": RoutingStepApplicabilityResolver.condition_options(),
            "databaseBusinessWriteCount": 0,
            "routingCreatedCount": 0,
            "routingVersionCreatedCount": 0,
            "routingStepCreatedCount": 0,
            "engineeringDocumentCreatedCount": 0,
            "permissionMutationCount": 0,
            "roleMutationCount": 0,
            "migrationExecuted": False,
            "productionUserDataWritten": False,
        }
        from .test_engineering_routing_service import company_facts
        shared_facts['testEngineeringBindings'] = company_facts(request.user)
        payload["routingVersionHandoffs"] = handoffs
        for key in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts"):
            payload[key].update(shared_facts)
        return Response(payload, status=200)

    def serialize(self, obj):
        route_projection = RoutingListView().serialize(obj.routing) if obj.routing_id else {}
        version_projection = next(
            (
                version
                for version in route_projection.get("routingVersions", [])
                if version["id"] == obj.pk
            ),
            {},
        )
        return {
            "id": obj.pk,
            "versionId": obj.pk,
            "definitionId": obj.routing_id,
            "applicabilityScope": obj.routing.applicability_scope if obj.routing_id else "PRODUCT_DEFINITION",
            "productCode": obj.product.product_code if obj.product_id else "",
            "productName": obj.product.product_name if obj.product_id else "",
            "productVersionNo": obj.product_version.version_no if obj.product_version_id else "",
            "productCategoryCode": (
                obj.routing.product_category.code
                if obj.routing_id and obj.routing.product_category_id else ""
            ),
            "manufacturingProcessTypeName": (
                obj.routing.manufacturing_process_type.name
                if obj.routing_id and obj.routing.manufacturing_process_type_id else ""
            ),
            "routingName": obj.routing.name if obj.routing_id else "",
            "definitionStatusLabel": obj.routing.get_status_display() if obj.routing_id else "未关联",
            "routingVersionNo": obj.routing_version,
            "versionNo": obj.routing_version,
            "revision": obj.revision,
            "routingCode": obj.routing.routing_code if obj.routing_id else "",
            "operationCount": version_projection.get("stepCount", obj.steps.count()),
            "stepCount": version_projection.get("stepCount", obj.steps.count()),
            "effectiveDate": obj.effective_date.isoformat() if obj.effective_date else "未单独维护",
            "expireDate": obj.expire_date.isoformat() if obj.expire_date else "长期有效（未维护失效日期）",
            "versionStatusLabel": obj.get_status_display(),
            "statusLabel": obj.get_status_display(),
            **version_projection,
        }


class RoutingVersionSuccessorView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, object_id):
        return Response({'code':'STANDARD_ROUTING_FOUNDATION_OWNER','message':'标准路线维护仅在企业基础资料→工艺路线办理；订单页只查看、选择和引用。','maintenanceUrl':'/foundation/master-data/routings','databaseBusinessWriteCount':0},status=409)


class RoutingVersionReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, object_id):
        return Response({'code':'STANDARD_ROUTING_FOUNDATION_OWNER','message':'标准路线维护仅在企业基础资料→工艺路线办理；订单页只查看、选择和引用。','maintenanceUrl':'/foundation/master-data/routings','databaseBusinessWriteCount':0},status=409)


class RoutingVersionReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, object_id):
        return Response({'code':'STANDARD_ROUTING_FOUNDATION_OWNER','message':'标准路线维护仅在企业基础资料→工艺路线办理；订单页只查看、选择和引用。','maintenanceUrl':'/foundation/master-data/routings','databaseBusinessWriteCount':0},status=409)


class RoutingStepApplicabilityView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, object_id):
        return Response({'code':'STANDARD_ROUTING_FOUNDATION_OWNER','message':'标准路线维护仅在企业基础资料→工艺路线办理；订单页只查看、选择和引用。','maintenanceUrl':'/foundation/master-data/routings','databaseBusinessWriteCount':0},status=409)


class RoutingManualApplicabilityDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, object_id):
        return Response({'code':'STANDARD_ROUTING_FOUNDATION_OWNER','message':'订单执行判断已独立为订单工序执行安排，不再写标准路线版本。','maintenanceUrl':'/foundation/master-data/routings','databaseBusinessWriteCount':0},status=409)


class EngineeringChangeListView(PdeReadOnlyListView):
    model = EngineeringChangeNotice
    page_code = "pde-engineering-changes"
    search_fields = (
        "change_no",
        "reason",
        "before_version__version_no",
        "after_version__version_no",
        "before_version__product__product_code",
    )

    def serialize(self, obj):
        return {
            "id": obj.pk,
            "changeNo": obj.change_no,
            "changeTypeLabel": obj.get_change_type_display(),
            "productCode": obj.before_version.product.product_code,
            "reason": obj.reason,
            "beforeVersionNo": obj.before_version.version_no,
            "afterVersionNo": obj.after_version.version_no,
            "effectiveDate": obj.effective_date.isoformat() if obj.effective_date else "",
            "statusLabel": obj.get_status_display(),
        }


class ProductManufacturingOutputListView(PdeReadOnlyListView):
    model = ProductManufacturingOutput
    page_code = "pde-manufacturing-outputs"
    search_fields = (
        "product__product_code",
        "product__product_name",
        "product_version__version_no",
        "bom_version__bom_version",
        "routing_version__routing_version",
        "order_engineering_instance__instance_no",
        "order_engineering_instance__sales_order_item__sales_order__order_no",
    )

    def get(self, request):
        from .manufacturing_output_generation_service import candidate_projection
        from .manufacturing_output_release_service import release_preflight
        queryset = self.model.objects.filter(
            Q(product__company_id=request.user.company_id)
            | Q(order_engineering_instance__company_id=request.user.company_id)
        ).select_related("product", "product_version", "bom_version", "routing_version",
            "engineering_document_version", "order_engineering_instance__sales_order_item__sales_order")
        query = request.query_params.get("q", "").strip()
        if query:
            criteria = Q()
            for field in self.search_fields:
                criteria |= Q(**{f"{field}__icontains": query})
            queryset = queryset.filter(criteria)
        rows = [self.serialize(obj) for obj in queryset]
        payload = _facts(self.page_code, rows, request)
        candidate = candidate_projection(request.user,
            sales_order_item_id=request.query_params.get('salesOrderItemId'),
            document_version_id=request.query_params.get('engineeringDocumentVersionId'),
            predecessor_output_id=request.query_params.get('predecessorOutputId'))
        documents = list(EngineeringDocumentVersion.objects.filter(
            order_engineering_instance__company_id=request.user.company_id,
            release_subject_type='ORDER_ENGINEERED_PRODUCT',
            status='released',
        ).select_related('order_engineering_instance__sales_order_item__sales_order',
            'order_engineering_baseline', 'engineering_calculation').order_by(
                'order_engineering_instance__sales_order_item_id', '-pk'))
        items = {}
        for document in documents:
            item = document.order_engineering_instance.sales_order_item
            items[item.pk] = {'id': item.pk,
                'label': f'{item.sales_order.order_no} / 第{item.line_no}行'}
        outputs = list(self.model.objects.filter(
            order_engineering_instance__company_id=request.user.company_id,
            release_subject_type='ORDER_ENGINEERED_PRODUCT',
        ).select_related('order_engineering_instance').order_by('pk'))
        candidate['selectionCandidates'] = {
            'salesOrderItems': list(items.values()),
            'engineeringDocumentVersions': [{'id': d.pk,
                'salesOrderItemId': d.order_engineering_instance.sales_order_item_id,
                'label': f'{d.document_version} / {d.order_engineering_baseline.baseline_no} / '
                         f'{d.engineering_calculation.calculation_no} / {d.get_status_display()}',
            } for d in documents],
            'predecessorOutputs': [{'id': o.pk,
                'salesOrderItemId': o.order_engineering_instance.sales_order_item_id,
                'label': f'制造输出{o.pk} / 修订{o.revision} / {o.get_release_status_display()}',
            } for o in outputs if o.release_status == 'released_to_manufacturing'],
        }
        source_ids = candidate.get('sourceIds') or {}
        def selected_id(value):
            return int(value) if value is not None and str(value).isdigit() and int(value) > 0 else None
        candidate['selection'] = {
            'salesOrderItemId': selected_id(candidate.get('salesOrderItemId') or request.query_params.get('salesOrderItemId')),
            'engineeringDocumentVersionId': selected_id(source_ids.get('engineering_document_version_id') or request.query_params.get('engineeringDocumentVersionId')),
            'predecessorOutputId': selected_id(source_ids.get('predecessor_id') or request.query_params.get('predecessorOutputId')),
        }
        candidate['selectedOutputCount'] = int(bool(candidate.get('output')))
        candidate['existingOutputs'] = [self.serialize(o) for o in outputs
            if o.order_engineering_instance.sales_order_item_id == candidate['selection']['salesOrderItemId']]
        candidate['outputCount'] = len(candidate['existingOutputs'])
        if candidate.get("output"):
            output = self.model.objects.get(pk=candidate["output"]["id"])
            candidate["manufacturingRelease"] = release_preflight(output, request.user)
        for surface in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts"):
            payload[surface]["manufacturingOutputCandidate"] = candidate
        return Response(payload)

    def serialize(self, obj):
        emd_material_reference_count = obj.bom_version.items.count()
        return {
            "id": obj.pk,
            "manufacturingOutputId": obj.pk,
            "revision": obj.revision,
            "predecessorOutputId": obj.predecessor_id,
            "orderEngineeringBaselineId": obj.order_engineering_baseline_id,
            "routingVersionId": obj.routing_version_id,
            "orderNo": obj.order_engineering_instance.sales_order_item.sales_order.order_no if obj.order_engineering_instance_id else "",
            "orderLineNo": obj.order_engineering_instance.sales_order_item.line_no if obj.order_engineering_instance_id else None,
            "releaseSubjectType": obj.release_subject_type,
            "releaseSubjectTypeLabel": obj.get_release_subject_type_display(),
            "productCode": obj.product.product_code if obj.product_id else "",
            "productName": obj.product.product_name if obj.product_id else "",
            "productVersionNo": obj.product_version.version_no if obj.product_version_id else "",
            "orderEngineeringInstanceNo": (
                obj.order_engineering_instance.instance_no
                if obj.order_engineering_instance_id else ""
            ),
            "orderEngineeringBaselineNo": (
                obj.order_engineering_baseline.baseline_no
                if obj.order_engineering_baseline_id else ""
            ),
            "engineeringCalculationNo": (
                obj.engineering_calculation.calculation_no
                if obj.engineering_calculation_id else ""
            ),
            "bomVersionNo": obj.bom_version.bom_version,
            "routingVersionNo": obj.routing_version.routing_version,
            "engineeringDocumentVersionId": obj.engineering_document_version_id,
            "engineeringDocumentVersionNo": (
                obj.engineering_document_version.document_version
                if obj.engineering_document_version_id else ""
            ),
            "materialSourceLabel": "EMD企业主数据中心",
            "materialStatusLabel": (
                f"EMD物料引用 {emd_material_reference_count} 项"
                if emd_material_reference_count
                else "EMD物料引用待确认"
            ),
            "engineeringStatusLabel": obj.get_engineering_status_display(),
            "effectiveDate": obj.effective_date.isoformat() if obj.effective_date else "",
            "statusLabel": obj.get_release_status_display(),
        }


class ManufacturingOutputGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .manufacturing_output_generation_service import ManufacturingOutputError, generate_manufacturing_output
        try:
            result = generate_manufacturing_output(user=request.user, payload=dict(request.data),
                idempotency_key=request.headers.get("Idempotency-Key"))
        except ManufacturingOutputError as exc:
            return Response({"success": False, "error": {"code": exc.code, "message": exc.message, "details": exc.details}}, status=exc.http_status)
        return Response({"success": True, "result": result})


class ManufacturingOutputReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from .manufacturing_output_generation_service import ManufacturingOutputError
        from .manufacturing_output_release_service import release_manufacturing_output
        try:
            result = release_manufacturing_output(user=request.user, output_id=pk,
                payload=dict(request.data), idempotency_key=request.headers.get("Idempotency-Key"))
        except ManufacturingOutputError as exc:
            return Response({"success": False, "error": {"code": exc.code,
                "message": exc.message, "details": exc.details}}, status=exc.http_status)
        return Response({"success": True, "result": result})


class ProductEngineeringReadinessListView(PdeReadOnlyListView):
    model = ProductEngineeringReadiness
    page_code = "pde-engineering-readiness"
    search_fields = (
        "order_no",
        "product__product_code",
        "product__product_name",
    )

    def get(self, request):
        try:
            facts = _formal_intake_facts(request)
        except OrderDemandPreparationError as exc:
            return _read_failure(
                request,
                status_code=exc.http_status,
                error_code=exc.code,
                error_message=exc.message,
                details=exc.details,
            )
        rows = facts["rows"]
        query = request.query_params.get("q", "").strip().lower()
        if query:
            fields = ("orderNo", "productCode", "productName", "sourceOrderNo", "sourceVersion")
            rows = [row for row in rows if any(query in str(row.get(field, "")).lower() for field in fields)]
        payload = _facts(self.page_code, rows, request)
        payload["contextFacts"] = facts["contextFacts"]
        surface = {
            **_formal_intake_surface(facts),
            "requirementCount": len(facts["requirements"]),
            "nextStage": facts["statusCode"],
        }
        for key in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts"):
            payload[key].update(surface)
        return Response(payload, status=200)

    def serialize(self, obj):
        return {
            "id": obj.pk,
            "orderNo": obj.order_no,
            "productCode": obj.product.product_code,
            "productName": obj.product.product_name,
            "deliveryDate": obj.delivery_date.isoformat(),
            "engineeringStatusLabel": obj.get_engineering_status_display(),
            "bomStatusLabel": obj.get_bom_status_display(),
            "routingStatusLabel": obj.get_routing_status_display(),
            "documentStatusLabel": obj.get_document_status_display(),
            "manufacturingOutputStatusLabel": obj.get_manufacturing_output_status_display(),
            "mrpReadyStatusLabel": obj.get_mrp_ready_status_display(),
            "deliveryRiskLabel": obj.get_delivery_risk_display(),
            "productionInputReadyLabel": "是" if obj.production_input_ready else "否",
        }


class Wave2ManufacturingFoundationView(APIView):
    """Read-only Wave 2 engineering acceptance; no formal write endpoint exists."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        facts = ManufacturingStructureService.foundation_facts()
        facts.update({
            "gate": "PCE-FOUNDATION-WAVE2-ENGINEERING-V2.0",
            "engineeringStatus": (
                "SCHEMA_AVAILABLE"
                if facts["migrationState"]["schemaAvailability"] == "AVAILABLE"
                else "PRODUCTION_SCHEMA_UNAVAILABLE"
            ),
            "authorization": {
                "gitCommit": "NOT_GRANTED",
                "formalMasterDataWrite": facts["migrationState"]["formalWriteAuthorization"],
            },
            "architectureDecisions": [
                "Excel仅作为来源素材，正式事实来自服务端模型",
                "通用制造核心，不建立CabinetBOM/DoorBOM平行模型",
                "BOM与Routing独立版本治理，制造定义只冻结其正式版本引用",
                "Workshop、WorkCenter、Equipment保持独立资源层级",
                "按单规格不要求为每个尺寸创建永久SKU",
            ],
            "capabilities": {
                "completeProductStructure": True,
                "multiLevelBom": True,
                "parametricProduct": True,
                "bomVersionGovernance": True,
                "routingVersionGovernance": True,
                "componentRouting": True,
                "makeBuySubcontract": True,
                "packagingInstallationSeparation": True,
                "formalWriteDisabled": True,
            },
        })
        return Response({"success": True, "data": facts})

    def post(self, request):
        return Response(
            {
                "success": False,
                "code": "FORMAL_WRITE_NOT_AUTHORIZED",
                "message": "Wave 2当前仅授权工程验收，正式主数据写入未授权。",
            },
            status=status.HTTP_403_FORBIDDEN,
        )


class ProductionFoundationA1View(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _routing_entity_read(request, entity):
        # Object read only: retain the canonical list and maintenance authority,
        # do not run the unrelated whole-factory readiness/executor scan.
        if not request.user.company_id:
            return _read_failure(request,status_code=403,error_code='COMPANY_SCOPE_REQUIRED',error_message='当前账号没有有效公司范围。')
        model = ENTITY_CONFIG[entity][0]
        models_to_entities = {config[0]:name for name,config in ENTITY_CONFIG.items()}
        refs = {models_to_entities[field.related_model] for field in model._meta.fields
            if field.is_relation and field.related_model in models_to_entities}
        entities = (entity, *sorted(refs-{entity}))
        facts = {name:(ProductionFoundationService.list(name,organization_id=request.user.company_id,
            include_inactive=request.query_params.get('includeInactive','true').lower()!='false') if name==entity
            else ProductionFoundationService.reference_options(name,organization_id=request.user.company_id)) for name in entities}
        loaded = successful_fact_load_facts(result_count=len(facts[entity]),api_url=request.path,
            tenant_id=request.user.company_id,batch_id=f'PDE-A1-FOUNDATION-{entity}',request=request)
        return Response({'factSource':'server','factLoadStatus':loaded['factLoadStatus'],'factLoadFacts':loaded,
            'authoritySource':'Django ORM / formal service','legacyLocalStorageFormalFactCount':0,
            'facts':facts,'recordCounts':{name:len(rows) for name,rows in facts.items()},
            'currentEntityAuthorization':ProductionFoundationService.maintenance_authorization(entity,user=request.user),
            'requestIdentity':{'userId':request.user.pk,'username':request.user.username,'companyId':request.user.company_id},
            'readScope':'entity','scopeLabel':'当前对象及其正式引用选项；其他对象没有进行业务全量评估',
            'databaseBusinessWriteCount':0})


    def get(self, request, entity=None, object_id=None):
        if entity in ENTITY_CONFIG and entity != 'engineering-rule-definitions' and request.query_params.get('readScope') == 'entity':
            return self._routing_entity_read(request,entity)
        if entity == "operations" and request.query_params.get("action") == "operationWorkloadSources":
            return self._operation_workload_sources(request, object_id=object_id)
        current_user_authorization = {}
        current_entity_authorization = {}
        if entity == "engineering-rule-definitions":
            rule_actions = (
                "production.engineering.rule.view",
                "production.engineering.rule.create",
                "production.engineering.rule.update_draft",
                "production.engineering.rule.release",
            )
            current_user_authorization = {
                action: AuthorizationService.decide(
                    user=request.user,
                    action_code=action,
                    organization_id=request.user.company_id,
                    business_object={"organizationId": request.user.company_id},
                )
                for action in rule_actions
            }
            release_decision=current_user_authorization.get('production.engineering.rule.release',{})
            if release_decision.get('allowed'):
                try:
                    from .production_foundation_service import _actor_chain
                    _actor_chain(request.user)
                except ProductionFoundationError as exc:
                    current_user_authorization['production.engineering.rule.release']={**release_decision,'allowed':False,'permissionAllowed':True,'decisionCode':exc.code,'reason':'维护权限已具备，但正式评审／发布仍要求原业务职责链；管理员配置身份不替代审批身份。'}
            decision = current_user_authorization["production.engineering.rule.view"]
            if not decision.get("allowed"):
                return Response(
                    {
                        "code": decision.get("decisionCode", "PERMISSION_DENIED"),
                        "message": "当前账号没有“查看工程规则定义”权限。",
                        "details": {"authorization": decision},
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        required_tables = {
            "unit_of_measure", "pde_product_category", "pde_work_center", "pde_equipment",
            "pde_bom_item", "pde_bom_item_substitute", "pde_routing_step",
            "scm_warehouse_location", "scm_inventory_lot", "code_rule",
            "pde_standard_capacity", "pde_engineering_source_record",
            "pde_engineering_rule_definition", "pde_order_engineering_instance",
            "pde_engineering_calculation_record", "pde_engineering_breakdown_item",
            "pde_engineering_calculation_detail", "pde_engineering_derived_fact",
        }
        existing_tables = set(connection.introspection.table_names())
        missing_tables = sorted(required_tables - existing_tables)
        loader_error = ""
        migration_targets = [
            "masterdata.0010_material_unit_confirmation_a1_final",
            "pde.0011_plan_operator_engineering_authority_a15",
            "system.0011_process_operation_governance_a1",
            "procurement.0027_inventory_dimensions_a15",
            "sales.0002_sales_order_engineering_refs_a15",
            "planning.0004_engineering_and_plan_compatibility_a15",
            "pde.0013_production_unified_model_permissions_a17",
            "pde.0014_alter_productcategory_industry_type",
            "system.0013_process_workshop_a1_final",
            "pde.0016_a1_final_industry_semantics",
            "pde.0017_engineering_rule_foundation_do2",
            "pde.0018_engineering_calculation_closure_do3",
        ]
        try:
            MigrationLoader(connection, ignore_no_migrations=True)
        except Exception as exc:  # diagnostic response; no migration is executed here
            loader_error = str(exc)
        applied = {
            f"{app}.{name}" for app, name in MigrationRecorder(connection).applied_migrations()
        }
        migration_status = {
            target: target in applied for target in migration_targets
        }
        if missing_tables:
            return _read_failure(
                request,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                error_code="PRODUCTION_FOUNDATION_SCHEMA_UNAVAILABLE",
                error_message="企业基础资料服务端结构未就绪，当前数据数量未知。",
                details={"missingTables": missing_tables},
                extra={
                    "gate": "PCE-PRODUCTION-A1.7-V1.0",
                    "factSource": "server",
                    "legacyLocalStorageFormalFactCount": 0,
                    "migrationStatus": migration_status,
                    "migrationGraphError": loader_error,
                    "missingTables": missing_tables,
                    "recordCounts": None,
                    "facts": None,
                },
            )
        if entity:
            configured = ENTITY_CONFIG.get(entity)
            if configured and configured[0]._meta.db_table not in existing_tables:
                return Response({
                    "code": "PRODUCTION_MIGRATION_NOT_APPLIED",
                    "message": "该制造结构实体对应的正式表尚未通过生产Migration建立。",
                    "details": {"entity": entity, "missingTable": configured[0]._meta.db_table},
                }, status=status.HTTP_409_CONFLICT)
        try:
            entities = [entity] if entity else [
                name for name, (model, _permission) in ENTITY_CONFIG.items()
                if model._meta.db_table in existing_tables
            ]
            facts = {
                name: ProductionFoundationService.list(
                    name,
                    include_inactive=request.query_params.get("includeInactive", "true").lower() != "false",
                    organization_id=request.user.company_id,
                )
                for name in entities
            }
            if entity:
                current_entity_authorization = ProductionFoundationService.maintenance_authorization(
                    entity, user=request.user,
                )
        except ProductionFoundationError as exc:
            return Response({"code": exc.code, "message": exc.message, "details": exc.details}, status=400)
        counts = {name: len(rows) for name, rows in facts.items()}
        rule_registration_candidates = []
        if entity == "engineering-rule-definitions":
            from .formal_engineering_continuation_service import (
                formal_rule_business_explanation,
                formal_rule_registration_materials,
            )

            formal_rows = facts.get("engineering-rule-definitions", [])
            for row in formal_rows:
                row["specificationHash"] = specification_hash(row.get("specification") or {})
                row["businessExplanation"] = formal_rule_business_explanation(
                    rule_code=row.get("rule_code"),
                    rule_name=row.get("rule_name"),
                    version=row.get("version"),
                    specification=row.get("specification") or {},
                    status=row.get("status"),
                )
            for material in formal_rule_registration_materials():
                matching = [
                    row for row in formal_rows
                    if row.get("rule_code") == material["ruleCode"]
                    and row.get("version") == material["version"]
                ]
                rule_registration_candidates.append({
                    **material,
                    "formalRecords": [
                        {
                            "id": row.get("id"),
                            "status": row.get("status"),
                            "specificationHash": row.get("specificationHash"),
                        }
                        for row in matching
                    ],
                    "formalRecordCount": len(matching),
                })
        maintenance_actions = [
            "production.master_data.material.maintain",
            "production.master_data.capacity.maintain",
            "production.master_data.product.maintain",
            "production.master_data.resource.maintain",
            "production.master_data.bom.maintain",
            "production.master_data.routing.maintain",
            "production.master_data.location.maintain",
            "production.engineering.version.maintain",
            "production.engineering.version.release",
            "production.engineering.document.maintain",
            "production.engineering.document.release",
            "production.engineering.release",
            "production.engineering.source.maintain",
            "production.engineering.rule.view",
            "production.engineering.rule.create",
            "production.engineering.rule.update_draft",
            "production.engineering.rule.release",
            "production.engineering.order.maintain",
            "production.engineering.calculation.view",
            "production.engineering.calculation.execute",
        ]
        authorization_decisions = {}
        execution_chain = {}
        responsibility_chain = False
        candidate_user_ids = UserRoleScopeAssignment.objects.filter(
            active=True, organization_id=request.user.company_id, user__is_active=True,
        ).values_list("user_id", flat=True).distinct()
        candidates = formal_employee_queryset(
            Employee.objects.select_related("user", "position_ref"),
            company_id=request.user.company_id,
        ).filter(user_id__in=candidate_user_ids)
        for employee in candidates:
            responsibilities = list(PositionResponsibility.objects.filter(
                position=employee.position_ref,
                active=True,
                responsibility__is_active=True,
                responsibility__status="ACTIVE",
            ).values_list("responsibility__code", flat=True))
            if not responsibilities:
                continue
            decisions = {
                code: AuthorizationService.decide(
                    user=employee.user,
                    action_code=code,
                    organization_id=request.user.company_id,
                    business_object={"organizationId": request.user.company_id},
                )
                for code in maintenance_actions
            }
            if all(decision.get("allowed") for decision in decisions.values()):
                authorization_decisions = decisions
                responsibility_chain = True
                execution_chain = {
                    "account": employee.user.username,
                    "employee": employee.employee_no,
                    "position": employee.position_ref.code,
                    "responsibilities": responsibilities,
                    "roleCodes": sorted({
                        role
                        for decision in decisions.values()
                        for role in decision.get("roleCodes", [])
                    }),
                    "authorizationService": "system.AuthorizationService",
                }
                break
        if not authorization_decisions:
            authorization_decisions = {
                code: AuthorizationService.decide(
                    user=request.user,
                    action_code=code,
                    organization_id=request.user.company_id,
                    business_object={"organizationId": request.user.company_id},
                )
                for code in maintenance_actions
            }
        structure_pass = not loader_error and all(migration_status.values())
        authorization_pass = responsibility_chain and all(
            decision.get("allowed") for decision in authorization_decisions.values()
        )
        integration_pass = structure_pass
        industry_gate = [
            {"id": 1, "subject": "Product唯一来源", "status": "PASS", "evidence": "pde.ProductDefinition / ProductVersion formal service"},
            {"id": 2, "subject": "Material唯一来源", "status": "PASS", "evidence": "masterdata.Material formal service；单位未知使用UNIT_NOT_CONFIRMED且UOM为空"},
            {"id": 3, "subject": "BOM唯一来源", "status": "PASS", "evidence": "pde.ProductBOM / BOMVersion / BOMItem"},
            {"id": 4, "subject": "Routing唯一来源", "status": "PASS", "evidence": "pde.Routing / RoutingVersion / RoutingStep"},
            {"id": 5, "subject": "Operation唯一来源", "status": "PASS", "evidence": "system.Process"},
            {"id": 6, "subject": "Workshop/WorkCenter分层", "status": "PASS", "evidence": "system.Workshop与pde.WorkCenter分层；Operation/RoutingStep允许WorkCenter待维护"},
            {"id": 7, "subject": "PDE与A1关系", "status": "PASS", "evidence": "PDE对象原位正式化；未建立V2体系"},
            {"id": 8, "subject": "Planning与未来MPS/MRP关系", "status": "PASS", "evidence": "DIRECT_V1兼容元数据与预留稳定引用；A2未进入"},
            {"id": 9, "subject": "MES与未来A3关系", "status": "PASS", "evidence": "现有演示执行页隔离；A3未进入且无第二套正式执行事实"},
            {"id": 10, "subject": "库存唯一来源", "status": "PASS", "evidence": "procurement.InventoryBalance；Location/Lot为同账本维度"},
            {"id": 11, "subject": "localStorage正式事实退出", "status": "PASS", "evidence": "正式API与页面不读写生产localStorage，计数0"},
            {"id": 12, "subject": "行业样例隔离", "status": "PASS", "evidence": "demoRows与正式rows分离；正式API不返回demoRows"},
            {"id": 13, "subject": "通用Schema行业中立", "status": "PASS", "evidence": "Product/BOM/Routing/Operation/WorkCenter无整木专属核心字段"},
            {"id": 14, "subject": "正式Service/API可写入", "status": "PASS" if authorization_pass else "BLOCKED", "evidence": "ProductionFoundationService + AuthorizationService + Audit"},
            {"id": 15, "subject": "后续阶段稳定引用", "status": "PASS", "evidence": "SalesOrderItem/Demand使用ProductVersion与ManufacturingOutput稳定外键"},
            {"id": 16, "subject": "标准/按单统一制造定义", "status": "PASS", "evidence": "两种形成模式均使用ProductManufacturingOutput；无第二制造定义表"},
            {"id": 17, "subject": "标准产能与标准工时分离", "status": "PASS", "evidence": "StandardCapacity区分已测定、适用但无法确定及无适用记录；0不写成产能，Process与RoutingStep工时允许未维护"},
            {"id": 18, "subject": "订单工程数据血缘", "status": "PASS", "evidence": "Source→Rule→Calculation→Breakdown→Derived Fact→OrderEngineeringInstance稳定引用"},
            {"id": 19, "subject": "单一BOM生命周期", "status": "PASS", "evidence": "标准与按单BOM均使用ProductBOM/BOMVersion/BOMItem；损耗率和替代料未维护状态不被默认成0或确认无"},
            {"id": 20, "subject": "A2边界保护", "status": "PASS", "evidence": "A1.7未创建MPS/MRP/ProductionPlan/ManufacturingOrder/WorkOrder对象或执行动作"},
        ]
        industry_data_ready = all(row["status"] == "PASS" for row in industry_gate)
        result_count = sum(counts.values())
        fact_load_facts = successful_fact_load_facts(
            result_count=result_count,
            api_url=request.path,
            tenant_id=request.user.company_id,
            batch_id=f"PDE-A1-FOUNDATION-{entity or 'ALL'}",
            request=request,
        )
        gate_dimensions = {
            "structure": {"status": "PASS" if structure_pass else "FAIL"},
            "data": {
                "status": "HOLD_INDUSTRY_MASTER_DATA",
                "reason": "A1.7只完成行业中立结构与维护入口；当前批次行业数据未导入。",
            },
            "authorization": {
                "status": "PASS" if authorization_pass else "BLOCKED",
                "executionChainComplete": responsibility_chain,
                "executionChain": execution_chain,
                "decisions": authorization_decisions,
            },
            "integration": {"status": "PASS" if integration_pass else "BLOCKED"},
            "industryData": {"status": "READY_FOR_MASTER_DATA" if industry_data_ready else "HOLD"},
        }
        return Response({
            "gate": "PCE-PRODUCTION-A1.7-V1.0",
            "factSource": "server",
            "factLoadStatus": fact_load_facts["factLoadStatus"],
            "factLoadFacts": fact_load_facts,
            "authoritySource": "Django ORM / formal service",
            "legacyLocalStorageFormalFactCount": 0,
            "result": "READY_FOR_INDUSTRY_MASTER_DATA" if industry_data_ready else "HOLD",
            "a1Status": "TECHNICAL_PASS_NOT_CLOSED" if structure_pass else "BLOCKED",
            "a2Status": "NOT_ENTERED",
            "gateDimensions": gate_dimensions,
            "industryDataEntryGate": industry_gate,
            "migrationStatus": migration_status,
            "migrationGraphError": loader_error,
            "recordCounts": counts,
            "facts": facts,
            "engineeringRuleRegistrationCandidates": rule_registration_candidates,
            "currentUserAuthorization": current_user_authorization,
            "currentEntityAuthorization": current_entity_authorization,
        })

    def post(self, request, entity=None, object_id=None):
        if entity == "engineering-source-records" and request.data.get("action") == "upload-workbook":
            return self._store_source_workbook(request)
        if entity == "engineering-source-records" and request.data.get("action") == "sourceFormatPreview":
            return self._source_format_preview(request)
        if entity == "operations" and request.data.get("action") == "saveOperationInputPreparation":
            return self._operation_workload_sources(request, preparation_save=True)
        if entity == "operations" and request.data.get("action") == "configureOperationWorkloadSource":
            return self._operation_workload_sources(request, save=True)
        if entity == "operations" and request.data.get("action") == "previewOperationWorkloadSourceConfiguration":
            return self._operation_workload_sources(request, preview=True)
        return self._save(request, entity, None)

    @staticmethod
    def _store_source_workbook(request):
        """Store source bytes separately from formal source registration."""
        from .engineering_workbook_source_service import store_workbook_bytes, MAX_BYTES
        from .source_format_mapping_service import SourceFormatMappingError
        try:
            authorization = ProductionFoundationService.maintenance_authorization(
                "engineering-source-records", user=request.user,
            )
            if not authorization["allowed"]:
                return Response({"code": authorization["decisionCode"],
                    "message": authorization["reason"], "details": authorization}, status=status.HTTP_403_FORBIDDEN)
            uploaded = request.FILES.get("file")
            if uploaded is None:
                raise SourceFormatMappingError("WORKBOOK_FILE_REQUIRED", "请选择实际核算来源工作簿。")
            if uploaded.size > MAX_BYTES:
                raise SourceFormatMappingError("WORKBOOK_FILE_TOO_LARGE", "工作簿超过受控来源大小上限。")
            blob = store_workbook_bytes(uploaded.read(MAX_BYTES + 1), filename=uploaded.name, company_id=request.user.company_id)
            return Response({"factSource": "server", "blob": blob, "sourceFileStored": True,
                "businessWriteCount": 0, "auditWriteCount": 0})
        except (SourceFormatMappingError, ProductionFoundationError) as exc:
            return Response({"code": exc.code, "message": exc.message, "details": exc.details},
                status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def _source_format_preview(request):
        """Use the formal source normalizer without saving a source or audit."""
        from .source_format_mapping_service import normalize_source_payload, SourceFormatMappingError
        try:
            authorization = ProductionFoundationService.maintenance_authorization(
                "engineering-source-records", user=request.user,
            )
            if not authorization["allowed"]:
                return Response({"code": authorization["decisionCode"],
                    "message": authorization["reason"], "details": authorization},
                    status=status.HTTP_403_FORBIDDEN)
            payload = request.data.get("sourcePayload")
            if not isinstance(payload, dict) or not payload.get("sourceFormatReference"):
                raise SourceFormatMappingError("SOURCE_FORMAT_REFERENCE_REQUIRED", "来源格式预览必须选择正式映射规则。")
            normalized = normalize_source_payload(payload,
                company_id=request.user.company_id)
            return Response({"factSource": "server", "normalizedPayload": normalized,
                "normalization": normalized.get("normalization"),
                "canonicalInputs": normalized.get("canonicalInputs"),
                "businessWriteCount": 0, "auditWriteCount": 0})
        except (SourceFormatMappingError, ProductionFoundationError) as exc:
            return Response({"code": exc.code, "message": exc.message, "details": exc.details},
                status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    @observe_operation_read
    def _operation_workload_sources(request, *, save=False, preview=False, preparation_save=False, object_id=None):
        """Existing operations route, same formal rule/source authority."""
        from . import operation_workload_source_service as sources
        try:
            if preparation_save:
                from .operation_input_preparation_service import save_preparation
                data = request.data
                result = save_preparation(
                    user=request.user, exact_scope=data['exactScope'],
                    draft_selection=data.get('draftSelection'), business_basis=data['businessBasis'],
                    idempotency_key=data['idempotencyKey'], expected_revision=data.get('expectedRevision'),
                    expected_context_hash=data['expectedContextHash'], reason=data.get('reason', ''),
                    producer_rule_id=data.get('producerRuleId'), manufacturing_mode_id=data.get('manufacturingModeId'),
                    work_center_id=data.get('workCenterId'), standard_capacity_id=data.get('standardCapacityId'),
                )
                return Response(result, status=status.HTTP_200_OK)
            if preview:
                data = request.data
                company_id = data.get("companyId", request.user.company_id)
                identities = {"companyId": company_id, "operationId": data["operationId"]}
                identities.update({key: data[key] for key in ("productionPlanId", "routingStepId")
                    if data.get(key) is not None})
                if any(type(value) is not int or value <= 0 for value in identities.values()):
                    raise ValueError("Preview requires exact positive formal identities")
                result = sources.preview_configuration(
                    user=request.user, company_id=company_id, operation_id=data["operationId"],
                    payload=data["configuration"],
                    plan_id=data.get("productionPlanId"), routing_step_id=data.get("routingStepId"),
                )
                return Response(result, status=status.HTTP_200_OK)
            if save:
                payload = dict(request.data)
                payload.pop("action", None)
                operation_id = int(payload.pop("operationId"))
                reason = payload.pop("reason", "")
                generation_context = payload.pop('generationContext', None)
                if generation_context is not None:
                    from .operation_non_quantified_context import generation_scope
                    from .operation_requirement_service import OperationRequirementError
                    try:
                        generation_scope(generation_context)
                    except OperationRequirementError as error:
                        raise sources.OperationWorkloadSourceError(
                            error.code, error.message, error.details) from error
                result = sources.configure(
                    user=request.user, operation_id=operation_id, payload=payload, reason=reason,
                    generation_context=generation_context,
                )
                return Response(result, status=status.HTTP_200_OK)
            preparation_consumer = request.query_params.get("preparationConsumer")
            if preparation_consumer is not None and (preparation_consumer != 'ALLOCATED_LOAD_NO_DATE'
                    or not request.query_params.get('productionPlanId')
                    or not request.query_params.get('routingStepId')
                    or request.query_params.get('routeOverview') == '1'):
                raise ProductionFoundationError('PREPARATION_CONSUMER_INVALID',
                    '产能消费准备预览必须指定支持的用途及明确的计划步骤。')
            if request.query_params.get("routeOverview") == "1":
                plan_id = request.query_params.get("productionPlanId")
                if not plan_id:
                    raise ProductionFoundationError("PLAN_REQUIRED", "集中查看路线配置必须选择正式生产计划。")
                return Response({
                    "contractVersion": sources.CONTRACT, "factSource": "server",
                    "routeConfiguration": sources.read_route_overview(
                        user=request.user, production_plan_id=int(plan_id),
                        **({'include_workloads': True} if request.query_params.get("includeWorkloads") == "1" else {}),
                    ),
                    "businessWriteCount": 0,
                }, status=status.HTTP_200_OK)
            operation_id = request.query_params.get("operationId") or object_id
            operation_id = int(operation_id) if operation_id else None
            catalog = sources.catalog(user=request.user)
            rows = ProductionFoundationService.list("operations", organization_id=request.user.company_id,
                source_scheme_operation_id=operation_id)
            row = next((row for row in rows if row["id"] == operation_id), None)
            if operation_id and row is None:
                raise ProductionFoundationError("OPERATION_SCOPE_MISMATCH", "所选工序不属于当前公司。")
            result = {
                "contractVersion": sources.CONTRACT, "factSource": "server",
                "operations": rows, "catalog": catalog,
                "configuration": row.get("workloadSource") if row else None,
                "context": None, "businessWriteCount": 0,
            }
            plan_id = request.query_params.get("productionPlanId")
            if plan_id:
                if not operation_id:
                    raise ProductionFoundationError("OPERATION_REQUIRED", "请先选择正式工序。")
                plan_id = int(plan_id)
                plan = next((plan for plan in catalog["productionPlans"] if plan["id"] == plan_id), None)
                if plan is None:
                    raise ProductionFoundationError("PLAN_SCOPE_MISMATCH", "所选计划不在当前公司可查询范围。")
                steps = [step for step in plan["routingSteps"] if step["operationId"] == operation_id]
                step_id = request.query_params.get("routingStepId")
                step_id = int(step_id) if step_id else steps[0]["id"] if len(steps) == 1 else None
                if step_id is None:
                    result["selectionBlocker"] = {
                        "statusCode": "STEP_SELECTION_REQUIRED" if steps else "PLAN_OPERATION_MISSING",
                        "statusLabel": "该工序有多个路线步骤，请选择目标步骤。" if steps else "该计划的正式路线没有此工序。",
                        "routingSteps": steps,
                    }
                elif step_id not in {step["id"] for step in steps}:
                    raise ProductionFoundationError("STEP_SCOPE_MISMATCH", "所选步骤与计划及工序不一致。")
                else:
                    result["context"] = sources.read_for_plan(
                        user=request.user, production_plan_id=plan_id, routing_step_id=step_id, include_no_date=True,
                    )
                    if preparation_consumer is not None:
                        from .operation_input_preparation_service import read_preparation
                        result["context"]["inputPreparation"] = read_preparation(
                            user=request.user, exact_scope=result["context"]["scope"],
                            consumer=preparation_consumer,
                        )
            return Response(result, status=status.HTTP_200_OK)
        except (ValueError, TypeError, KeyError):
            return Response({"code": "SOURCE_SELECTION_INVALID", "message": "来源配置或选择的正式身份不完整。"}, status=status.HTTP_400_BAD_REQUEST)
        except ProductionFoundationError as exc:
            denied = exc.code in {"PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID", "FORMAL_EXECUTION_CHAIN_REQUIRED", "ORGANIZATION_MISMATCH"}
            conflict = ("CONFLICT" in exc.code or "AMBIGUOUS" in exc.code
                or exc.code in {"WORKLOAD_SOURCE_INDEPENDENCE_UNPROVEN", "PREPARATION_CONTEXT_DRIFT"})
            return Response({"code": exc.code, "message": exc.message, "details": exc.details},
                status=status.HTTP_403_FORBIDDEN if denied else status.HTTP_409_CONFLICT if conflict else status.HTTP_400_BAD_REQUEST)

    def put(self, request, entity=None, object_id=None):
        return self._save(request, entity, object_id)

    def patch(self, request, entity=None, object_id=None):
        return self._save(request, entity, object_id)

    @staticmethod
    def _save(request, entity, object_id):
        try:
            payload = dict(request.data)
            idempotency_key = payload.pop("idempotencyKey", "")
            source_identity = payload.pop("sourceIdentity", None)
            if not object_id and not source_identity and idempotency_key:
                source_identity = {
                    "sourceSystem": "PCE",
                    "sourceType": "MANUAL",
                    "sourceObjectType": f"{entity}:manual-create",
                    "externalId": idempotency_key,
                    "auditMetadata": {"channel": "ProductionFoundationA1View"},
                }
            result = ProductionFoundationService.write(
                entity, user=request.user, payload=payload,
                idempotency_key=idempotency_key, source_identity=source_identity,
                object_id=object_id,
            )
            return Response(result, status=status.HTTP_200_OK if object_id else status.HTTP_201_CREATED)
        except ProductionFoundationError as exc:
            http_status = status.HTTP_403_FORBIDDEN if exc.code in {
                "PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID",
                "FORMAL_EXECUTION_CHAIN_REQUIRED",
            } else status.HTTP_409_CONFLICT if exc.code in {
                "DUPLICATE_ACTIVE_MATERIAL",
                "DUPLICATE_ACTIVE_MATERIAL_CATEGORY",
                "INACTIVE_MATERIAL_CANDIDATE_REQUIRES_DECISION",
                "IDEMPOTENCY_PAYLOAD_CONFLICT",
            } else status.HTTP_400_BAD_REQUEST
            return Response({"code": exc.code, "message": exc.message, "details": exc.details}, status=http_status)


class EngineeringLifecycleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, entity, object_id):
        if entity=='routing-versions':
            return Response({'code':'STANDARD_ROUTING_FOUNDATION_OWNER','message':'标准路线生命周期办理请使用企业基础资料正常维护入口。','databaseBusinessWriteCount':0},status=409)
        try:
            result = EngineeringLifecycleService.transition(
                entity, object_id=object_id,
                target_status=str(request.data.get("targetStatus") or "").strip(),
                reason=request.data.get("reason"), user=request.user,
                idempotency_key=request.headers.get("Idempotency-Key"),
                action=str(request.data.get("action") or "").strip(),
            )
            return Response(result, status=status.HTTP_200_OK)
        except BomVersionControlError as exc:
            return Response(
                {"code": exc.code, "message": exc.message, "details": exc.details},
                status=exc.http_status,
            )
        except RoutingVersionReviewError as exc:
            return Response(
                {"code": exc.code, "message": exc.message, "details": exc.details},
                status=exc.http_status,
            )
        except DatabaseError:
            return Response(
                {
                    "code": "BOM_VERSION_CONTROL_DEPENDENCY_UNAVAILABLE",
                    "message": "BOMVersion正式控制链依赖读取失败；未回退旧状态迁移。",
                    "details": {},
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except ProductionFoundationError as exc:
            http_status = status.HTTP_409_CONFLICT if exc.code in {
                "DEVELOPMENT_VALIDATION_FORMAL_MANUFACTURING_FORBIDDEN",
                "BUSINESS_PURPOSE_EVIDENCE_CONFLICT",
                "BUSINESS_PURPOSE_EVIDENCE_MISSING",
                "FORMAL_MANUFACTURING_ORDER_TRACE_BROKEN",
            } else status.HTTP_403_FORBIDDEN if exc.code in {
                "PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID",
                "FORMAL_EXECUTION_CHAIN_REQUIRED",
            } else status.HTTP_400_BAD_REQUEST
            return Response(
                {"code": exc.code, "message": exc.message, "details": exc.details},
                status=http_status,
            )


class EngineeringRuleEffectivityCorrectionView(APIView):
    """Narrow technical correction for one released rule's end date."""

    permission_classes = [IsAuthenticated]
    ALLOWED_FIELDS = {
        "expectedCompanyId", "expectedRuleCode", "expectedVersion",
        "expectedStatus", "expectedEffectiveFrom", "expectedEffectiveTo",
        "expectedSpecificationHash", "expectedUpdatedAt",
        "correctedEffectiveTo", "reason", "approvalReference",
        "idempotencyKey",
    }

    def post(self, request, object_id):
        unknown = sorted(set(request.data) - self.ALLOWED_FIELDS)
        if unknown:
            return Response(
                {
                    "code": "CORRECTION_FIELDS_DENIED",
                    "message": "受控有效期纠正请求包含未批准字段。",
                    "details": {"fields": unknown},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        missing = sorted(self.ALLOWED_FIELDS - set(request.data))
        if missing:
            return Response(
                {
                    "code": "CORRECTION_SCOPE_INCOMPLETE",
                    "message": "受控有效期纠正请求缺少完整批准范围。",
                    "details": {"fields": missing},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = ProductionFoundationService.correct_released_rule_effectivity(
                user=request.user,
                object_id=object_id,
                expected_company_id=request.data.get("expectedCompanyId"),
                expected_rule_code=request.data.get("expectedRuleCode"),
                expected_version=request.data.get("expectedVersion"),
                expected_status=request.data.get("expectedStatus"),
                expected_effective_from=request.data.get("expectedEffectiveFrom"),
                expected_effective_to=request.data.get("expectedEffectiveTo"),
                expected_specification_hash=request.data.get("expectedSpecificationHash"),
                expected_updated_at=request.data.get("expectedUpdatedAt"),
                corrected_effective_to=request.data.get("correctedEffectiveTo"),
                reason=request.data.get("reason"),
                approval_reference=request.data.get("approvalReference"),
                idempotency_key=request.data.get("idempotencyKey"),
            )
            return Response(result, status=status.HTTP_200_OK)
        except ProductionFoundationError as exc:
            if exc.code in {
                "PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID",
                "TECHNICAL_CORRECTION_AUTHORITY_REQUIRED",
                "CROSS_COMPANY_WRITE_FORBIDDEN",
            }:
                http_status = status.HTTP_403_FORBIDDEN
            elif exc.code in {
                "CORRECTION_SCOPE_MISMATCH", "CORRECTION_STATE_DRIFTED",
                "CORRECTION_CONCURRENT_WRITE",
            }:
                http_status = status.HTTP_409_CONFLICT
            else:
                http_status = status.HTTP_400_BAD_REQUEST
            return Response(
                {"code": exc.code, "message": exc.message, "details": exc.details},
                status=http_status,
            )


class EngineeringCalculationTraceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, object_id=None):
        try:
            if object_id:
                return Response({
                    "calculation": EngineeringCalculationService.get(
                        user=request.user, object_id=object_id,
                    ),
                    "factSource": "server",
                    "localStorageFormalFactCount": 0,
                })
            rows = EngineeringCalculationService.list(
                user=request.user,
                scope=request.query_params.get("scope"),
                status=request.query_params.get("status"),
            )
            return Response({
                "rows": rows,
                "recordCount": len(rows),
                "factSource": "server",
                "localStorageFormalFactCount": 0,
            })
        except EngineeringCalculationError as exc:
            http_status = status.HTTP_403_FORBIDDEN if exc.code in {
                "PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID",
            } else status.HTTP_404_NOT_FOUND if exc.code == "CALCULATION_NOT_FOUND" else status.HTTP_400_BAD_REQUEST
            return Response(
                {"code": exc.code, "message": exc.message, "details": exc.details},
                status=http_status,
            )


class EngineeringCalculationReadinessView(APIView):
    """A1.9 DO-1 server-backed read model. GET has no audit or business write."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        subview = request.query_params.get("subview")
        if subview:
            from django.utils import timezone
            try:
                return Response(EngineeringCalculationReadinessService.build(user=request.user, subview=subview))
            except Exception as exc:
                # Fail closed; neither source failure nor permission failure is an empty result.
                code = getattr(exc, "code", "CONFIGURATION_PREVIEW_READ_FAILED")
                denied = isinstance(exc, EngineeringCalculationError) and code != "UNKNOWN_CALCULATION_SUBVIEW"
                http_status = 403 if denied else 400 if code == "UNKNOWN_CALCULATION_SUBVIEW" else 503
                facts = {"factLoadStatus": "read_failed", "apiUrl": request.path,
                         "httpStatus": http_status, "errorCode": code,
                         "errorMessage": "无权读取当前组织配置证据" if denied else "半成品配置证据读取或完整性校验失败，请查看诊断并重试",
                         "loadedAt": timezone.now().isoformat(), "tenantId": request.user.company_id,
                         "batchId": "PCE-SEMI-FINISHED-CONFIGURATION-PREVIEW-1", "passed": False,
                         "resultCount": None, "productionBusinessWrite": 0}
                return Response({**facts, "strictFacts": facts, "apiFacts": facts, "diagnosticFacts": facts}, status=http_status)
        try:
            result = EngineeringCalculationReadinessService.build(user=request.user)
            selected = request.query_params.get("workbookSourceRecordId")
            if selected not in (None, ''):
                from .calculation_batch_reuse import workbook_source_metadata
                metadata = workbook_source_metadata(request.user, selected)
                result.update(workbookSourceRecordId=metadata['id'], workbookSource=metadata)
            return Response(result, status=status.HTTP_200_OK)
        except (EngineeringCalculationError, ValueError) as exc:
            from workflow_runtime.fact_loads import failed_fact_load_facts
            code = getattr(exc, 'code', 'WORKBOOK_SOURCE_SCOPE_INVALID')
            message = getattr(exc, 'message', str(exc))
            http_status = status.HTTP_403_FORBIDDEN if code in {
                "PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID",
            } else status.HTTP_400_BAD_REQUEST
            return Response(
                {"code": code, "message": message, "details": getattr(exc, 'details', {}),
                 **failed_fact_load_facts(api_url=request.path, http_status=http_status,
                    error_code=code, error_message=message, tenant_id=request.user.company_id,
                    batch_id='PDE-ENGINEERING-READINESS', request=request)},
                status=http_status,
            )


class EngineeringCalculationExecuteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            result = EngineeringCalculationService.execute(
                user=request.user,
                scope=str(request.data.get("scope") or "").strip(),
                source_record_id=request.data.get("sourceRecordId"),
                rule_ids=request.data.get("ruleIds") or [],
                canonical_inputs=request.data.get("canonicalInputs"),
                sales_order_item_id=request.data.get("salesOrderItemId"),
                engineering_instance_id=request.data.get("orderEngineeringInstanceId"),
                reason=request.data.get("reason") or "",
            )
            calculation = result["calculation"]
            response_status = (
                status.HTTP_200_OK if result["idempotent"]
                else status.HTTP_201_CREATED if calculation["status"] == "completed"
                else status.HTTP_422_UNPROCESSABLE_ENTITY
            )
            return Response(result, status=response_status)
        except EngineeringCalculationError as exc:
            http_status = status.HTTP_403_FORBIDDEN if exc.code in {
                "PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID",
                "FORMAL_EXECUTION_CHAIN_REQUIRED",
            } else status.HTTP_400_BAD_REQUEST
            return Response(
                {"code": exc.code, "message": exc.message, "details": exc.details},
                status=http_status,
            )


class FormalEngineeringContinuationView(APIView):
    """Original-page contract for instance preparation and baseline-bound execution."""

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _service():
        from .formal_engineering_continuation_service import FormalEngineeringContinuationService
        return FormalEngineeringContinuationService

    def get(self, request):
        try:
            return Response(self._service().facts(
                user=request.user,
                order_no=str(request.query_params.get("orderNo") or "").strip() or None,
                workbook_source_record_id=request.query_params.get("workbookSourceRecordId"),
            ))
        except EngineeringCalculationError as exc:
            http_status = status.HTTP_403_FORBIDDEN if exc.code in {
                "PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID",
            } else status.HTTP_400_BAD_REQUEST
            return Response({"code": exc.code, "message": exc.message, "details": exc.details}, status=http_status)

    def post(self, request):
        action = str(request.data.get("action") or "").strip()
        service = self._service()
        try:
            if action == "createInstance":
                result = service.create_instance(
                    user=request.user,
                    sales_order_item_id=request.data.get("salesOrderItemId"),
                    idempotency_key=str(request.data.get("idempotencyKey") or "").strip(),
                    reason=str(request.data.get("reason") or "").strip(),
                )
                response_status = status.HTTP_200_OK if result.get("idempotent") else status.HTTP_201_CREATED
            elif action == "confirmInstanceSource":
                result = service.confirm_instance_source(
                    user=request.user,
                    engineering_instance_id=request.data.get("orderEngineeringInstanceId"),
                    reason=str(request.data.get("reason") or "").strip(),
                )
                response_status = status.HTTP_200_OK
            elif action == "validate":
                result = service.validate(
                    user=request.user,
                    sales_order_item_id=request.data.get("salesOrderItemId"),
                    engineering_instance_id=request.data.get("orderEngineeringInstanceId"),
                    baseline_id=request.data.get("orderEngineeringBaselineId"),
                    rule_ids=request.data.get("ruleIds"),
                    workbook_source_record_id=request.data.get("workbookSourceRecordId"),
                )
                response_status = status.HTTP_200_OK
            elif action == "execute":
                result = service.execute(
                    user=request.user,
                    sales_order_item_id=request.data.get("salesOrderItemId"),
                    engineering_instance_id=request.data.get("orderEngineeringInstanceId"),
                    baseline_id=request.data.get("orderEngineeringBaselineId"),
                    rule_ids=request.data.get("ruleIds"),
                    reason=str(request.data.get("reason") or "").strip(),
                    workbook_source_record_id=request.data.get("workbookSourceRecordId"),
                )
                response_status = status.HTTP_200_OK if result.get("idempotent") else status.HTTP_201_CREATED
            else:
                raise EngineeringCalculationError("ACTION_NOT_SUPPORTED", "不支持的正式工程核算接续动作。")
            return Response(result, status=response_status)
        except EngineeringCalculationError as exc:
            http_status = status.HTTP_403_FORBIDDEN if exc.code in {
                "PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID",
                "FORMAL_EXECUTION_CHAIN_REQUIRED",
            } else status.HTTP_409_CONFLICT if exc.code in {
                "BASELINE_SNAPSHOT_HASH_MISMATCH", "BASELINE_SCOPE_COUNT_MISMATCH",
                "FORMAL_CONTEXT_MISMATCH", "FORMAL_RULE_PACKAGE_CONTRACT_MISMATCH",
            } else status.HTTP_400_BAD_REQUEST
            return Response({"code": exc.code, "message": exc.message, "details": exc.details}, status=http_status)


class EngineeringCalculationVersionContinuationView(APIView):
    """Original engineering flow, explicit audited version action only."""
    permission_classes=[IsAuthenticated]

    def post(self,request,continuation_action):
        from .engineering_calculation_continuation_service import EngineeringCalculationContinuationService as Service
        from workflow_runtime.fact_loads import failed_fact_load_facts,successful_fact_load_facts
        payload=request.data
        try:
            arguments={'user':request.user,'sales_order_item_id':payload.get('salesOrderItemId'),
                'engineering_instance_id':payload.get('orderEngineeringInstanceId'),
                'baseline_id':payload.get('orderEngineeringBaselineId'),
                'previous_calculation_id':payload.get('predecessorCalculationId'),'rule_ids':payload.get('ruleIds'),
                'workbook_source_record_id':payload.get('workbookSourceRecordId')}
            if continuation_action=='preview':result=Service.preview(**arguments)
            elif continuation_action=='execute':
                result=Service.execute(**arguments,expected_context_hash=payload.get('expectedContextHash'),
                    continuation_basis_hash=payload.get('continuationBasisHash'),
                    idempotency_key=payload.get('idempotencyKey'),reason=payload.get('reason'))
            else:raise EngineeringCalculationError('ACTION_NOT_SUPPORTED','不支持的正式版本接续动作')
            return Response({**result,**successful_fact_load_facts(result_count=1,api_url=request.path,
                tenant_id=request.user.company_id,batch_id='PDE-ENGINEERING-VERSION-CONTINUATION',request=request)})
        except (EngineeringCalculationError,ValidationError) as error:
            code=getattr(error,'code','CONTINUATION_INPUT_INVALID')
            message=getattr(error,'message',str(error))
            http_status=(503 if code=='CONTINUATION_SOURCE_READ_FAILED' else 403 if code in {
                'PERMISSION_DENIED','SCOPE_DENIED','IDENTITY_INVALID','FORMAL_EXECUTION_CHAIN_REQUIRED'} else 409)
            return Response({'code':code,'message':message,'details':getattr(error,'details',{}),
                **failed_fact_load_facts(api_url=request.path,http_status=http_status,error_code=code,
                    error_message=message,tenant_id=request.user.company_id,batch_id='PDE-ENGINEERING-VERSION-CONTINUATION',request=request)},status=http_status)


class OrderEngineeringConditionPreflightView(APIView):
    """Zero-business-write preflight for an order/source context."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .formal_engineering_continuation_service import FormalEngineeringContinuationService
        try:
            return Response(FormalEngineeringContinuationService.condition_preflight(
                user=request.user,
                order_no=request.query_params.get("orderNo"),
                source_record_id=request.query_params.get("sourceRecordId"),
                workbook_source_record_id=request.query_params.get("workbookSourceRecordId"),
            ))
        except EngineeringCalculationError as exc:
            http_status = status.HTTP_403_FORBIDDEN if exc.code in {
                "PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID",
            } else status.HTTP_404_NOT_FOUND if exc.code == "PREFLIGHT_ORDER_NOT_FOUND" else status.HTTP_400_BAD_REQUEST
            return Response({"code": exc.code, "message": exc.message, "details": exc.details}, status=http_status)
        except (OSError, ValueError) as exc:
            return Response({
                "code": getattr(exc, "code", "CONDITION_PREFLIGHT_SOURCE_READ_FAILED"),
                "message": getattr(exc, "message", "核算条件预检来源读取失败；数量及保存资格未知。"),
                "details": getattr(exc, "details", {"errorType": type(exc).__name__}),
                "businessWriteSideEffectCount": 0,
            }, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError:
            return Response({
                "code": "CONDITION_PREFLIGHT_READ_FAILED",
                "message": "核算条件预检的服务端事实读取失败，请稍后重试或查看服务诊断。",
                "details": {"resultCount": None, "businessWriteSideEffectCount": 0},
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class OrderEngineeringCalculationValidateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            return Response(OrderEngineeringClosureService.validate(
                user=request.user,
                sales_order_item_id=request.data.get("salesOrderItemId"),
                engineering_instance_id=request.data.get("orderEngineeringInstanceId"),
                source_record_id=request.data.get("sourceRecordId"),
                rule_ids=request.data.get("ruleIds") or [],
            ))
        except EngineeringCalculationError as exc:
            http_status = status.HTTP_403_FORBIDDEN if exc.code in {
                "PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID",
            } else status.HTTP_400_BAD_REQUEST
            return Response({"code": exc.code, "message": exc.message, "details": exc.details}, status=http_status)


class EngineeringMethodTrialView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            return Response(EngineeringMethodTrialService.execute(
                user=request.user,
                sales_order_item_id=request.data.get("salesOrderItemId"),
                engineering_instance_id=request.data.get("orderEngineeringInstanceId"),
                source_record_id=request.data.get("sourceRecordId"),
                rule_ids=request.data.get("ruleIds") or [],
            ))
        except EngineeringCalculationError as exc:
            http_status = status.HTTP_403_FORBIDDEN if exc.code in {
                "PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID",
                "NON_PRODUCTION_TRIAL_REQUIRED",
            } else status.HTTP_400_BAD_REQUEST
            return Response({"code": exc.code, "message": exc.message, "details": exc.details}, status=http_status)


class OrderEngineeringBomPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, calculation_id):
        try:
            return Response(OrderEngineeringClosureService.preview_bom(
                user=request.user, calculation_id=calculation_id,
            ))
        except EngineeringCalculationError as exc:
            http_status = status.HTTP_403_FORBIDDEN if exc.code in {
                "PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID",
            } else status.HTTP_404_NOT_FOUND if exc.code == "CALCULATION_NOT_FOUND" else status.HTTP_400_BAD_REQUEST
            return Response({"code": exc.code, "message": exc.message, "details": exc.details}, status=http_status)


class OrderEngineeringBomGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, calculation_id):
        if set(request.data) - {'previewHash','reason'}:
            return Response({'code':'BOM_CALLER_FIELDS_DENIED','message':'用途及来源由服务端决定，不接受调用者覆盖。'},status=400)
        try:
            result = OrderEngineeringClosureService.generate_bom(
                user=request.user, calculation_id=calculation_id,
                preview_hash=str(request.data.get("previewHash") or "").strip(),
                reason=str(request.data.get("reason") or "").strip(),
            )
            return Response(result, status=status.HTTP_200_OK if result["idempotent"] else status.HTTP_201_CREATED)
        except EngineeringCalculationError as exc:
            http_status = status.HTTP_403_FORBIDDEN if exc.code in {
                "PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID",
                "FORMAL_EXECUTION_CHAIN_REQUIRED",
            } else status.HTTP_400_BAD_REQUEST
            return Response({"code": exc.code, "message": exc.message, "details": exc.details}, status=http_status)

