import uuid
import importlib
from decimal import Decimal, InvalidOperation


class _LazyPandas:
    def __getattr__(self, name):
        return getattr(importlib.import_module("pandas"), name)


pd = _LazyPandas()
from django.http import HttpResponse
from django.utils import timezone
from datetime import date
from django.db import transaction
from django.db.models import Q
from io import BytesIO
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from .models import MaterialCategory, Material, CodeRule, SupplierMaterialPrice
from procurement.models import Supplier
from procurement.procurement_mode_router import SupplierMaterialPriceAuthorization
from .material_master_runtime import MaterialMasterRuntimeAdapter
from .master_data_statistics_runtime import (
    MasterDataStatisticsRuntime,
    SupplierMaterialPriceRuntime,
    SupplierPriceFactRuntime,
)
from .material_supplier_relation_runtime import MaterialSupplierRelationRuntime
from .supplier_master_runtime import SupplierMasterRuntimeAdapter
from .serializers import MaterialCategorySerializer, MaterialSerializer, CodeRuleSerializer
from .enterprise_master_data import (
    MASTER_DATA_BATCH,
    MASTER_DATA_TENANT,
    MASTER_DATA_VERSION,
    get_master_data_definition,
)
from .base_data_comparison_runtime import build_batch1_comparison
from .base_data_readiness_runtime import build_base_data_readiness
from .group2_comparison_runtime import build_group2_comparison
from .group3_comparison_runtime import build_group3_comparison
from .group3a_operation_remediation_service import build_group3a_operation_revalidation


class BaseDataComparisonPreviewView(APIView):
    """Read-only Batch 1 comparison; there is deliberately no mutation method."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, entity_code):
        try:
            facts = build_batch1_comparison(entity_code, request.user.company_id)
        except KeyError:
            return Response(
                {"factLoadStatus": "read_failed", "errorCode": "COMPARISON_ENTITY_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(facts)


class BaseDataReadinessView(APIView):
    """Group 1-6 read-only acceptance facts; deliberately exposes GET only."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(build_base_data_readiness(request.user.company_id))


class Group2ComparisonPreviewView(APIView):
    """Read-only Group 2 reality check; deliberately exposes GET only."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, entity_code):
        try:
            facts = build_group2_comparison(entity_code, request.user.company_id)
        except KeyError:
            return Response(
                {"factLoadStatus": "read_failed", "errorCode": "GROUP2_COMPARISON_ENTITY_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(facts)


class Group3ComparisonPreviewView(APIView):
    """Read-only Group 3 manufacturing-engineering acceptance; GET only."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, entity_code):
        try:
            facts = build_group3_comparison(entity_code, request.user.company_id)
        except KeyError:
            return Response(
                {"factLoadStatus": "read_failed", "errorCode": "GROUP3_COMPARISON_ENTITY_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(facts)


class Group3AOperationTargetedRevalidationView(APIView):
    """Read-only targeted readback after the authorized Group 3A remediation."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(build_group3a_operation_revalidation(request.user.company_id))


class EnterpriseMasterDataFactsView(APIView):
    """Read-only, server-owned facts for the V85 enterprise master-data pages."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, entity_code):
        definition = get_master_data_definition(entity_code)
        if not definition:
            loaded_at = timezone.now().isoformat()
            facts = {
                "factLoadContractVersion": "PCE-FACT-LOAD-CONTRACT-V1.0",
                "factLoadStatus": "read_failed",
                "apiUrl": request.path,
                "httpStatus": 404,
                "errorCode": "MASTER_DATA_ENTITY_NOT_FOUND",
                "errorMessage": "未找到主数据实体",
                "loadedAt": loaded_at,
                "tenantId": MASTER_DATA_TENANT,
                "batchId": MASTER_DATA_BATCH,
            }
            return Response(
                {"factLoadFacts": facts, "strictFacts": facts, "acceptanceFacts": facts},
                status=status.HTTP_404_NOT_FOUND,
            )

        material_runtime = entity_code == "materials"
        supplier_runtime = entity_code == "suppliers"
        customer_runtime = entity_code == "customers"
        production_runtime = entity_code in {"boms", "routings", "warehouses"}
        if customer_runtime:
            from sales.models import Customer

            customers = Customer.objects.filter(
                company_id=request.user.company_id,
            ).order_by("code", "id")
            rows = [{
                "id": customer.pk,
                "customerCode": customer.code,
                "customerName": customer.name,
                "creditLevel": "",
                "contactName": "",
                "contactPhone": "",
                "businessStatus": "启用" if customer.is_active else "停用",
            } for customer in customers]
            runtime_facts = {
                "dataSource": "sales.Customer",
                "demoFixtureIncluded": False,
            }
        elif material_runtime:
            rows = [model.to_dict() for model in MaterialMasterRuntimeAdapter.list_runtime_models()]
            runtime_facts = {}
        elif supplier_runtime:
            supplier_facts = SupplierMasterRuntimeAdapter.facts()
            rows = [model.to_dict() for model in supplier_facts["models"]]
            runtime_facts = {
                "businessUsageCount": supplier_facts["businessUsageCount"],
                "mappedSupplierCount": supplier_facts["mappedSupplierCount"],
                "unresolvedSupplierMappings": supplier_facts["unresolved"],
                "duplicateSupplierCodes": supplier_facts["duplicateCodes"],
                "duplicateSupplierNames": supplier_facts["duplicateNames"],
                "duplicateSupplierReviews": supplier_facts["duplicateReviews"],
                "duplicateReviewMissingSupplierIds": supplier_facts["duplicateReviewMissingSupplierIds"],
                "fieldIncompleteCount": supplier_facts["fieldIncompleteCount"],
                "supplierFieldCompleteGate": supplier_facts["supplierFieldCompleteGate"],
                "supplierDuplicateReviewGate": supplier_facts["supplierDuplicateReviewGate"],
                "supplierDeliveryAddressGate": supplier_facts["supplierDeliveryAddressGate"],
            }
        elif entity_code == "boms":
            from pde.models import BOMVersion
            versions = BOMVersion.objects.select_related(
                "product", "product_version", "bom", "bom__product_category",
            ).prefetch_related("items__material", "items__uom").filter(
                bom__company_id=request.user.company_id,
            )
            rows = []
            for version in versions:
                items = list(version.items.all())
                if not items:
                    items = [None]
                for item in items:
                    rows.append({
                        "id": f"BOMV-{version.pk}-ITEM-{item.pk if item else 0}",
                        "bomId": version.bom_id, "bomVersionId": version.pk,
                        "bomNo": version.bom.bom_code if version.bom_id else "",
                        "applicabilityScope": version.bom.applicability_scope if version.bom_id else "PRODUCT_DEFINITION",
                        "productCode": version.product.product_code if version.product_id else "",
                        "productName": version.product.product_name if version.product_id else "",
                        "productCategory": (
                            version.bom.product_category.name
                            if version.bom_id and version.bom.product_category_id else ""
                        ),
                        "productVersion": version.product_version.version_no if version.product_version_id else "",
                        "bomVersion": version.bom_version,
                        "lineNo": item.line_no if item else None,
                        "componentCode": item.material.code if item else "",
                        "componentName": item.material.name if item else "",
                        "quantity": str(item.quantity) if item else "",
                        "unit": item.uom.code if item else "",
                        "businessStatus": version.status,
                    })
            runtime_facts = {"dataSource": "pde.BOMVersion/BOMItem", "demoFixtureIncluded": False}
        elif entity_code == "routings":
            from pde.models import RoutingVersion
            versions = RoutingVersion.objects.select_related(
                "product", "product_version", "routing",
                "routing__product_category", "routing__manufacturing_process_type",
            ).prefetch_related("steps__operation", "steps__work_center").filter(
                routing__company_id=request.user.company_id,
            )
            rows = []
            for version in versions:
                steps = list(version.steps.all())
                if not steps:
                    steps = [None]
                for step in steps:
                    rows.append({
                        "id": f"ROUTEV-{version.pk}-STEP-{step.pk if step else 0}",
                        "routingId": version.routing_id, "routingVersionId": version.pk,
                        "routingNo": version.routing.routing_code if version.routing_id else "",
                        "applicabilityScope": version.routing.applicability_scope if version.routing_id else "PRODUCT_DEFINITION",
                        "productCode": version.product.product_code if version.product_id else "",
                        "productCategory": (
                            version.routing.product_category.name
                            if version.routing_id and version.routing.product_category_id else ""
                        ),
                        "manufacturingProcessType": (
                            version.routing.manufacturing_process_type.name
                            if version.routing_id and version.routing.manufacturing_process_type_id else ""
                        ),
                        "productVersion": version.product_version.version_no if version.product_version_id else "",
                        "routingVersion": version.routing_version,
                        "sequence": step.sequence if step else None,
                        "operationCode": step.operation.code if step else "",
                        "operationName": step.operation.name if step else "",
                        "workCenterCode": step.work_center.code if step and step.work_center_id else "",
                        "standardHours": str(step.standard_hours) if step else "",
                        "businessStatus": version.status,
                    })
            runtime_facts = {"dataSource": "pde.RoutingVersion/RoutingStep", "demoFixtureIncluded": False}
        elif entity_code == "warehouses":
            from procurement.models import Warehouse
            warehouses = Warehouse.objects.prefetch_related("locations").filter(
                company_id=request.user.company_id,
            )
            rows = []
            for warehouse in warehouses:
                locations = list(warehouse.locations.all()) or [None]
                for location in locations:
                    rows.append({
                        "id": f"WH-{warehouse.pk}-LOC-{location.pk if location else 0}",
                        "warehouseId": warehouse.pk, "warehouseCode": warehouse.code,
                        "warehouseName": warehouse.name,
                        "locationId": location.pk if location else None,
                        "locationCode": location.code if location else "",
                        "locationName": location.name if location else "",
                        "businessStatus": "启用" if warehouse.is_active else "停用",
                    })
            runtime_facts = {"dataSource": "procurement.Warehouse/WarehouseLocation", "demoFixtureIncluded": False}
        else:
            rows = [dict(row) for row in definition["rows"]]
            runtime_facts = {}
        loaded_at = timezone.now().isoformat()
        canonical_runtime = customer_runtime or material_runtime or supplier_runtime or production_runtime
        tenant_id = "PCE-ENTERPRISE-MASTER" if canonical_runtime else MASTER_DATA_TENANT
        batch_id = ("CUSTOMER-MASTER-RUNTIME" if customer_runtime else
                    "MATERIAL-MASTER-RUNTIME" if material_runtime else
                    "SUPPLIER-MASTER-RUNTIME" if supplier_runtime else
                    "PRODUCTION-MASTER-RUNTIME" if production_runtime else MASTER_DATA_BATCH)
        fact_load_facts = {
            "factLoadContractVersion": "PCE-FACT-LOAD-CONTRACT-V1.0",
            "factLoadStatus": "success",
            "apiUrl": request.path,
            "httpStatus": 200,
            "loadedAt": loaded_at,
            "tenantId": tenant_id,
            "batchId": batch_id,
        }
        strict_facts = {
            **fact_load_facts,
            "factSource": "server",
            "moduleCode": "EMD",
            "processCode": "EMD_MASTER_DATA_MAINTENANCE",
            "nodeCode": definition["nodeCode"],
            "pageCode": definition["pageCode"],
            "pageVersion": ("V1.14.2.8.4.27.2.29" if customer_runtime else
                            "V1.14.2.8.4.27.2.23" if material_runtime else
                            "V1.14.2.8.4.27.2.28" if supplier_runtime else MASTER_DATA_VERSION),
            "acceptanceStatus": "PASS",
            "masterDataCode": definition["masterDataCode"],
            "recordCount": len(rows),
            "actionCount": 1,
            "dangerActionCount": 0,
            "businessProgressWriteCount": 0,
            "downstreamObjectCount": 0,
            "formalFact": canonical_runtime,
            "demoFixtureIncluded": False if canonical_runtime else bool(definition.get("demoRows")),
            **runtime_facts,
        }
        if material_runtime:
            strict_facts.update({
                "runtimeModelType": MaterialMasterRuntimeAdapter.runtime_model_type,
                "runtimeAdapterCode": MaterialMasterRuntimeAdapter.runtime_adapter_code,
                "dataSource": "masterdata.Material",
                "databaseTable": MaterialMasterRuntimeAdapter.database_table,
                "maintenanceEntry": "企业基础数据 → 物料数据",
            })
        if customer_runtime:
            strict_facts.update({
                "runtimeModelType": "Customer",
                "runtimeAdapterCode": "SalesCustomerReadOnlyAdapter",
                "dataSource": "sales.Customer",
                "databaseTable": "sales_customer",
                "maintenanceEntry": "企业基础数据 → 客户数据",
                "customerMasterSource": "CustomerMaster",
            })
        if supplier_runtime:
            strict_facts.update({
                "runtimeModelType": SupplierMasterRuntimeAdapter.runtime_model_type,
                "runtimeAdapterCode": SupplierMasterRuntimeAdapter.runtime_adapter_code,
                "dataSource": "procurement.Supplier",
                "databaseTable": SupplierMasterRuntimeAdapter.database_table,
                "maintenanceEntry": "企业基础数据 → 供应商数据",
                "supplierMasterSource": "SupplierMaster",
            })
        return Response(
            {
                **strict_facts,
                "title": definition["title"],
                "primaryField": definition["primaryField"],
                "rows": rows,
                "factLoadFacts": fact_load_facts,
                "strictFacts": strict_facts,
                "acceptanceFacts": strict_facts,
            }
        )


class MasterDataStatisticsFactsView(APIView):
    """Single read-only source for the enterprise foundation summary cards."""

    permission_classes = [AllowAny]

    def get(self, request):
        runtime_facts = MasterDataStatisticsRuntime.facts()
        loaded_at = timezone.now().isoformat()
        fact_load_facts = {
            "factLoadContractVersion": "PCE-FACT-LOAD-CONTRACT-V1.0",
            "factLoadStatus": "success",
            "apiUrl": request.path,
            "httpStatus": 200,
            "loadedAt": loaded_at,
            "tenantId": "PCE-ENTERPRISE-MASTER",
            "batchId": "MASTER-DATA-STATISTICS-RUNTIME",
        }
        strict_facts = {
            **fact_load_facts,
            **runtime_facts,
            "factSource": "server",
            "moduleCode": "EMD",
            "pageCode": "enterprise-foundation-data",
            "pageVersion": MasterDataStatisticsRuntime.version,
            "acceptanceStatus": "PASS",
            "databaseChanged": False,
        }
        return Response({
            **strict_facts,
            "factLoadFacts": fact_load_facts,
            "strictFacts": strict_facts,
            "acceptanceFacts": strict_facts,
        })


class MaterialSupplierRelationFactsView(APIView):
    """Read-only MaterialSupplierRelation Runtime and usage matrix."""

    permission_classes = [AllowAny]

    def get(self, request):
        runtime_facts = MaterialSupplierRelationRuntime.facts()
        rows = [model.to_dict() for model in runtime_facts["models"]]
        loaded_at = timezone.now().isoformat()
        fact_load_facts = {
            "factLoadContractVersion": "PCE-FACT-LOAD-CONTRACT-V1.0",
            "factLoadStatus": "success",
            "apiUrl": request.path,
            "httpStatus": 200,
            "loadedAt": loaded_at,
            "tenantId": "PCE-ENTERPRISE-MASTER",
            "batchId": "MATERIAL-SUPPLIER-RELATION-RUNTIME",
        }
        strict_facts = {
            **fact_load_facts,
            "factSource": "server",
            "moduleCode": "EMD",
            "pageCode": "material-supplier-relations",
            "pageVersion": MaterialSupplierRelationRuntime.runtime_version,
            "runtimeCode": MaterialSupplierRelationRuntime.runtime_code,
            "relationCount": runtime_facts["relationCount"],
            "usageMatrixCount": runtime_facts["usageMatrixCount"],
            "unresolvedMappingCount": len(runtime_facts["unresolvedMappings"]),
            "duplicateRelationCount": runtime_facts["duplicateRelationCount"],
            "businessProgressWriteCount": 0,
            "databaseStructureChanged": False,
            "acceptanceStatus": "PASS",
        }
        return Response({
            **strict_facts,
            "rows": rows,
            "usageMatrix": runtime_facts["usageMatrix"],
            "unresolvedMappings": runtime_facts["unresolvedMappings"],
            "sourceSummary": runtime_facts["sourceSummary"],
            "factLoadFacts": fact_load_facts,
            "strictFacts": strict_facts,
            "acceptanceFacts": strict_facts,
        })


class SupplierMaterialPriceFactsView(APIView):
    """Read-only enterprise effective-price runtime and migration assessment."""

    permission_classes = [AllowAny]

    def get(self, request):
        runtime_facts = SupplierMaterialPriceRuntime.facts()
        rows = [model.to_dict() for model in runtime_facts["models"]]
        relation_keys = {
            (model.supplierId, model.materialId)
            for model in MaterialSupplierRelationRuntime.list_runtime_models()
            if model.status == "enabled"
        }
        for row in rows:
            row["materialSupplierRelationValid"] = (
                row["supplierId"], row["materialId"]
            ) in relation_keys
        today = date.today().isoformat()
        version_groups = {}
        for row in rows:
            # The current model has no contract/plant/quantity scope columns.
            # DEFAULT is the only scope the server can truthfully express;
            # future scope dimensions extend this key in-place.
            scope_key = f'{row["supplierId"]}:{row["materialId"]}:{row["currency"]}:DEFAULT'
            row["scopeKey"] = scope_key
            row["scopeStatus"] = "DEFAULT_SCOPE_NO_DIMENSIONS"
            row["scopeDimensions"] = []
            version_groups.setdefault(scope_key, []).append(row)

        for members in version_groups.values():
            ordered = sorted(members, key=lambda item: (
                item.get("confirmedAt") or "", item.get("createdAt") or "", item["priceNo"],
            ))
            applicable = [item for item in ordered
                          if item["status"] == "ACTIVE"
                          and item["effectiveDate"] <= today
                          and (not item["expiryDate"] or item["expiryDate"] >= today)]
            current_price_no = applicable[-1]["priceNo"] if applicable else ""
            for index, row in enumerate(ordered):
                if row["status"] != "ACTIVE":
                    version_status, version_label = "DISABLED", "停用"
                elif row["effectiveDate"] > today:
                    version_status, version_label = "FUTURE", "未来生效"
                elif row["expiryDate"] and row["expiryDate"] < today:
                    version_status, version_label = "HISTORICAL", "历史价格"
                elif row["priceNo"] == current_price_no:
                    version_status, version_label = "CURRENT", "当前适用"
                else:
                    version_status, version_label = "HISTORICAL", "历史价格"
                row.update({
                    "versionNo": index + 1,
                    "versionStatus": version_status,
                    "versionStatusLabel": version_label,
                    "isCurrentApplicable": version_status == "CURRENT",
                    "previousPriceNo": ordered[index - 1]["priceNo"] if index else "",
                    "nextPriceNo": ordered[index + 1]["priceNo"] if index + 1 < len(ordered) else "",
                })

        for row in rows:
            overlaps = [candidate["priceNo"] for candidate in rows
                        if candidate["priceNo"] != row["priceNo"]
                        and candidate["supplierId"] == row["supplierId"]
                        and candidate["materialId"] == row["materialId"]
                        and candidate["status"] == "ACTIVE" and row["status"] == "ACTIVE"
                        and candidate["effectiveDate"] <= (row["expiryDate"] or "9999-12-31")
                        and row["effectiveDate"] <= (candidate["expiryDate"] or "9999-12-31")]
            row["overlappingPriceNos"] = overlaps
            row["overlapStatus"] = (
                "OVERLAPPING_EFFECTIVE_PRICE" if overlaps else "NO_EFFECTIVE_PERIOD_OVERLAP"
            )
            row["overlapClassification"] = (
                "B_HISTORICAL_VERSION_RELATION" if overlaps else "NO_OVERLAP"
            )
            row["effectiveIdentityStatus"] = {
                "CURRENT": "CURRENT_APPLICABLE_VERSION",
                "HISTORICAL": "HISTORICAL_VERSION_PRESERVED",
                "FUTURE": "FUTURE_VERSION_NOT_YET_APPLICABLE",
                "DISABLED": "DISABLED_VERSION",
            }[row["versionStatus"]]

        unfiltered_formal_price_count = len(rows)
        query_filters = {
            "supplierCode": str(request.query_params.get("supplierCode") or "").strip(),
            "materialCode": str(request.query_params.get("materialCode") or "").strip(),
            "currency": str(request.query_params.get("currency") or "").strip(),
        }
        for field, expected in query_filters.items():
            if expected:
                rows = [row for row in rows if str(row.get(field) or "") == expected]
        loaded_at = timezone.now().isoformat()
        fact_load_facts = {
            "factLoadContractVersion": "PCE-FACT-LOAD-CONTRACT-V1.0",
            "factLoadStatus": "success",
            "apiUrl": request.path,
            "httpStatus": 200,
            "loadedAt": loaded_at,
            "tenantId": "PCE-ENTERPRISE-MASTER",
            "batchId": "SUPPLIER-MATERIAL-PRICE-RUNTIME",
        }
        strict_facts = {
            **fact_load_facts,
            "factSource": "server",
            "moduleCode": "EMD",
            "pageCode": "foundation-supplier-material-prices",
            "pageVersion": SupplierMaterialPriceRuntime.runtime_version,
            "runtimeCode": SupplierMaterialPriceRuntime.runtime_code,
            "runtimeModelType": SupplierMaterialPriceRuntime.runtime_model_type,
            "schemaCode": "SupplierMaterialPriceSchema",
            "providerCode": "SupplierMaterialPriceRuntimeProvider",
            "formalPriceCount": len(rows),
            "unfilteredFormalPriceCount": unfiltered_formal_price_count,
            "migrationCandidateCount": runtime_facts["migrationCandidateCount"],
            "rejectedCandidateCount": runtime_facts["rejectedCandidateCount"],
            "migrationStatus": runtime_facts["migrationStatus"],
            "maintenanceMode": runtime_facts["maintenanceMode"],
            "referenceChain": runtime_facts["referenceChain"],
            "approvalChain": runtime_facts["approvalChain"],
            "allowedSourceTypes": runtime_facts["allowedSourceTypes"],
            "autoGenerationEnabled": runtime_facts["autoGenerationEnabled"],
            "sessionConfirmedPriceCount": runtime_facts["sessionConfirmedPriceCount"],
            "persistedPriceCount": runtime_facts["persistedPriceCount"],
            "priceApprovalResultCount": runtime_facts["priceApprovalResultCount"],
            "archiveEligibleResultCount": runtime_facts["archiveEligibleResultCount"],
            "sessionPersistence": runtime_facts["sessionPersistence"],
            "enterpriseProcurementDefaultTaxRate": runtime_facts["enterpriseProcurementDefaultTaxRate"],
            "enterpriseProcurementDefaultTaxRateSource": runtime_facts["enterpriseProcurementDefaultTaxRateSource"],
            "standardTaxRateOptions": runtime_facts["standardTaxRateOptions"],
            "confirmationResults": runtime_facts["confirmationResults"],
            "businessProgressWriteCount": 0,
            "databaseStructureChanged": False,
            "acceptanceStatus": "PASS",
            "manualMaintenanceAuthorization": SupplierMaterialPriceAuthorization.decide_any_scope(request.user),
            "overlappingEffectivePriceCount": sum(
                row["overlapStatus"] == "OVERLAPPING_EFFECTIVE_PRICE" for row in rows
            ),
            "currentPriceCount": sum(row["versionStatus"] == "CURRENT" for row in rows),
            "historicalPriceCount": sum(row["versionStatus"] == "HISTORICAL" for row in rows),
            "futurePriceCount": sum(row["versionStatus"] == "FUTURE" for row in rows),
            "disabledPriceCount": sum(row["versionStatus"] == "DISABLED" for row in rows),
            "versionGovernanceVersion": "SUPPLIER-MATERIAL-PRICE-MULTI-VERSION-001",
            "queryFilters": query_filters,
        }
        return Response({
            **strict_facts,
            "rows": rows,
            "migrationCandidates": runtime_facts["migrationCandidates"],
            "priceApprovalResults": runtime_facts["priceApprovalResults"],
            "lastBatchArchiveResult": runtime_facts["lastBatchArchiveResult"],
            "lastPreparationArchiveResult": runtime_facts["lastPreparationArchiveResult"],
            "taxMaintenanceAudit": runtime_facts["taxMaintenanceAudit"],
            "effectiveDateReconciliation": runtime_facts["effectiveDateReconciliation"],
            "factLoadFacts": fact_load_facts,
            "strictFacts": strict_facts,
            "acceptanceFacts": strict_facts,
        })


class SupplierMaterialPriceQuotationConfirmationView(APIView):
    """Explicit human quote confirmation; creates no database business object."""

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            SupplierMaterialPriceRuntime.confirm_quotation(request.data or {})
        except ValueError as exc:
            return Response({
                "factLoadStatus": "read_failed",
                "errorCode": str(exc),
                "errorMessage": str(exc),
                "businessProgressWriteCount": 0,
                "databaseStructureChanged": False,
            }, status=status.HTTP_400_BAD_REQUEST)
        return SupplierMaterialPriceFactsView().get(request)


class PriceApprovalResultView(APIView):
    """Record a human price-review outcome; this is not a second approval flow."""

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            SupplierMaterialPriceRuntime.record_approval_result(request.data or {})
        except ValueError as exc:
            return Response({
                "factLoadStatus": "read_failed",
                "errorCode": str(exc),
                "errorMessage": str(exc),
                "businessProgressWriteCount": 0,
                "databaseStructureChanged": False,
            }, status=status.HTTP_400_BAD_REQUEST)
        return SupplierMaterialPriceFactsView().get(request)


class PriceSourceConsistencyView(APIView):
    """Expose the real-quotation acceptance projection without a database write."""

    permission_classes = [AllowAny]

    def get(self, request):
        report = SupplierMaterialPriceRuntime.price_source_consistency_report()
        return Response({
            "success": report["status"] == "PASS",
            "data": report,
            "error": None if report["status"] == "PASS" else {
                "code": "REAL_SUPPLIER_QUOTATION_SOURCE_NOT_FOUND",
                "message": "没有可用于真实归档验收的SupplierQuotation明细。",
            },
            "meta": {
                "module": "SCM",
                "source": "SupplierQuotation",
                "businessWriteCount": 0,
                "productionUserDataWritten": False,
            },
        }, status=status.HTTP_200_OK if report["status"] == "PASS" else status.HTTP_409_CONFLICT)


class SupplierMaterialPriceBatchArchiveView(APIView):
    """Archive selected ACCEPT results with independent item-level validation."""

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            SupplierMaterialPriceRuntime.batch_archive((request.data or {}).get("resultIds"))
        except ValueError as exc:
            return Response({
                "factLoadStatus": "read_failed",
                "errorCode": str(exc),
                "errorMessage": str(exc),
                "businessProgressWriteCount": 0,
                "databaseStructureChanged": False,
            }, status=status.HTTP_400_BAD_REQUEST)
        return SupplierMaterialPriceFactsView().get(request)


class PriceApprovalPreparationArchiveView(APIView):
    """Explicitly archive selected completed PASS preparations, item by item."""

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            result = SupplierMaterialPriceRuntime.batch_archive_price_approval_preparations(
                (request.data or {}).get("items")
            )
        except ValueError as exc:
            return Response({
                "factLoadStatus": "read_failed",
                "errorCode": str(exc),
                "errorMessage": str(exc),
                "businessProgressWriteCount": 0,
                "databaseStructureChanged": False,
            }, status=status.HTTP_400_BAD_REQUEST)
        facts_response = SupplierMaterialPriceFactsView().get(request)
        facts_response.data["preparationArchiveResult"] = result
        return facts_response


class SupplierMaterialPriceMaintenanceView(APIView):
    """Maintain tax and validity only; source price identity remains immutable."""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, price_no):
        try:
            actor = getattr(request.user, "username", "") or str(request.user or "")
            SupplierMaterialPriceRuntime.update_session_price(price_no, request.data or {}, actor=actor)
        except ValueError as exc:
            return Response({
                "factLoadStatus": "read_failed",
                "errorCode": str(exc),
                "errorMessage": str(exc),
                "businessProgressWriteCount": 0,
                "databaseStructureChanged": False,
            }, status=status.HTTP_400_BAD_REQUEST)
        return SupplierMaterialPriceFactsView().get(request)

    # Keep the established endpoint backward compatible while PATCH is the
    # canonical maintenance method for V45.12.
    def post(self, request, price_no):
        return self.patch(request, price_no)


class SupplierMaterialPriceManualCreateView(APIView):
    """Create one audited formal price from explicit manual maintenance authority."""

    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        payload = request.data or {}
        company_id = getattr(request.user, "company_id", None)
        authorization = SupplierMaterialPriceAuthorization.decide(request.user, company_id)
        if not authorization["allowed"]:
            return Response({"errorCode": "SUPPLIER_MATERIAL_PRICE_MANUAL_NOT_AUTHORIZED", "errorMessage": authorization["reason"]}, status=403)
        try:
            supplier = Supplier.objects.get(pk=int(payload.get("supplierId")), company_id=company_id, is_active=True)
            material = Material.objects.get(pk=int(payload.get("materialId")), is_active=True, is_purchased=True)
        except (TypeError, ValueError, Supplier.DoesNotExist, Material.DoesNotExist):
            return Response({"errorCode": "PRICE_MASTER_IDENTITY_INVALID", "errorMessage": "供应商或物料主数据无效。"}, status=400)
        relation_exists = any(
            row.supplierId == supplier.pk and row.materialId == material.pk and row.status == "enabled"
            for row in MaterialSupplierRelationRuntime.list_runtime_models()
        )
        try:
            price = Decimal(str(payload.get("unitPrice")))
            tax_rate = Decimal(str(payload.get("taxRate")))
            effective_date = date.fromisoformat(str(payload.get("effectiveDate") or ""))
            expiry_date = date.fromisoformat(str(payload["expiryDate"])) if payload.get("expiryDate") else None
        except (InvalidOperation, TypeError, ValueError):
            return Response({"errorCode": "PRICE_MAINTENANCE_VALUE_INVALID", "errorMessage": "价格、税率或有效期格式无效。"}, status=400)
        currency = str(payload.get("currency") or "").strip().upper()
        reason = str(payload.get("maintenanceReason") or "").strip()
        if price <= 0 or tax_rate < 0 or not currency or not reason or (expiry_date and expiry_date < effective_date):
            return Response({"errorCode": "PRICE_MAINTENANCE_FIELDS_REQUIRED", "errorMessage": "请完整填写正数价格、非负税率、币种、有效期和维护原因。"}, status=400)
        overlapping = SupplierMaterialPrice.objects.filter(
            supplier=supplier, material=material, currency=currency, status="ACTIVE",
            effective_date__lte=expiry_date or date.max,
        ).filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=effective_date))
        if overlapping.exists():
            return Response({"errorCode": "PRICE_EFFECTIVE_PERIOD_OVERLAP", "errorMessage": "同一供应商、物料和币种已有重叠的正式价格，请先治理有效期。"}, status=409)
        actor = request.user.get_username()
        now = timezone.now()
        relation_code = f"MSR|{material.code}|{supplier.code}"
        relation_action = "REUSED_FORMAL_RELATION" if relation_exists else "ESTABLISHED_FORMAL_RELATION"
        model = SupplierMaterialPrice.objects.create(
            price_no=f"SMP-MANUAL-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}",
            supplier=supplier, material=material, approved_price=price, currency=currency,
            tax_rate=tax_rate, tax_rate_source="ManualMaintenance",
            effective_date=effective_date, expiry_date=expiry_date, status="ACTIVE",
            price_source_type="MANUAL_MAINTENANCE", price_source_label="人工维护",
            original_source_type="ManualMaintenance",
            original_source_reference=f"ManualMaintenance:{actor}:{now.isoformat()}",
            approved_by=actor, approved_at=now, confirmed_by=actor, confirmed_at=now,
            modified_by=actor, modified_at=now, modification_reason=reason,
            modification_audit=[{
                "action": "CREATE", "actor": actor, "at": now.isoformat(), "reason": reason,
                "relationAction": relation_action, "relationCode": relation_code,
                "relationConfirmed": True,
            }],
        )
        response = SupplierMaterialPriceFactsView().get(request)
        response.data["manualMaintenanceResult"] = {
            "priceId": model.pk, "priceNo": model.price_no,
            "relationCode": relation_code, "relationAction": relation_action,
        }
        return response


class MaterialSupplierRelationMaintenanceView(APIView):
    """Maintain delivery period only; no price field is accepted or changed."""

    permission_classes = [AllowAny]

    def post(self, request, relation_code):
        try:
            MaterialSupplierRelationRuntime.update_delivery_period(relation_code, request.data or {})
        except ValueError as exc:
            return Response({
                "factLoadStatus": "read_failed",
                "errorCode": str(exc),
                "errorMessage": str(exc),
                "businessProgressWriteCount": 0,
                "databaseStructureChanged": False,
            }, status=status.HTTP_400_BAD_REQUEST)
        return MaterialSupplierRelationFactsView().get(request)


class SupplierPriceFactFactsView(APIView):
    """Read-only SupplierPriceFact Runtime facts; no price maintenance actions."""

    permission_classes = [AllowAny]

    def get(self, request):
        runtime_facts = SupplierPriceFactRuntime.facts()
        rows = [model.to_dict() for model in runtime_facts["models"]]
        history_rows = [model.to_dict() for model in runtime_facts["historyModels"]]
        conflicts = [
            model.to_dict()
            for model in runtime_facts["duplicateEffectivePeriodCandidates"]
        ]
        intelligence_analysis = runtime_facts["intelligenceAnalysis"]
        quality = intelligence_analysis["quality"]
        loaded_at = timezone.now().isoformat()
        fact_load_facts = {
            "factLoadContractVersion": "PCE-FACT-LOAD-CONTRACT-V1.0",
            "factLoadStatus": "success",
            "apiUrl": request.path,
            "httpStatus": 200,
            "loadedAt": loaded_at,
            "tenantId": "PCE-ENTERPRISE-MASTER",
            "batchId": "SUPPLIER-PRICE-FACT-RUNTIME",
        }
        strict_facts = {
            **fact_load_facts,
            "factSource": "server",
            "moduleCode": "EMD",
            "pageCode": "foundation-supplier-price-facts",
            "pageVersion": SupplierPriceFactRuntime.runtime_version,
            "runtimeCode": SupplierPriceFactRuntime.runtime_code,
            "runtimeModelType": SupplierPriceFactRuntime.runtime_model_type,
            "priceFactCount": runtime_facts["priceFactCount"],
            "historyFactCount": runtime_facts["historyFactCount"],
            "duplicateEffectivePeriodCount": runtime_facts["duplicateEffectivePeriodCount"],
            "sourcePriority": runtime_facts["sourcePriority"],
            "sourceCounts": runtime_facts["sourceCounts"],
            "intelligenceExtensionPoints": runtime_facts["intelligenceExtensionPoints"],
            "intelligenceRuleVersion": intelligence_analysis["ruleVersion"],
            "analysisMode": intelligence_analysis["analysisMode"],
            "analysisSupplierCount": quality["supplierCount"],
            "analysisMaterialCount": quality["materialCount"],
            "analysisPriceFactCount": quality["priceFactCount"],
            "analysisHistoryPriceCount": quality["historyPriceCount"],
            "analysisAnomalyCount": intelligence_analysis["anomalyCount"],
            "purchasePriceReviewContextCount": runtime_facts["purchasePriceReviewContextCount"],
            "priceReviewRuleRuntimeCode": "PriceReviewRuleRuntime",
            "autoDecisionEnabled": False,
            "autoPriceApprovalEnabled": False,
            "autoSupplierSelectionEnabled": False,
            "businessProgressWriteCount": 0,
            "databaseStructureChanged": False,
            "acceptanceStatus": "PASS",
        }
        return Response({
            **strict_facts,
            "rows": rows,
            "historyRows": history_rows,
            "duplicateEffectivePeriodCandidates": conflicts,
            "intelligenceAnalysis": intelligence_analysis,
            "purchasePriceReviewContexts": runtime_facts["purchasePriceReviewContexts"],
            "factLoadFacts": fact_load_facts,
            "strictFacts": strict_facts,
            "acceptanceFacts": strict_facts,
        })


class MaterialPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 200


class FormalMasterDataWriteMixin:
    """Legacy API compatibility that delegates every mutation to one service."""

    formal_entity = ""
    input_fk_aliases = {}

    @staticmethod
    def _error_response(exc):
        from pde.production_foundation_service import ProductionFoundationError

        if not isinstance(exc, ProductionFoundationError):
            raise exc
        http_status = (
            status.HTTP_403_FORBIDDEN
            if exc.code in {
                "PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID",
                "FORMAL_EXECUTION_CHAIN_REQUIRED",
            }
            else status.HTTP_409_CONFLICT
            if exc.code in {
                "DUPLICATE_ACTIVE_MATERIAL",
                "DUPLICATE_ACTIVE_MATERIAL_CATEGORY",
                "INACTIVE_MATERIAL_CANDIDATE_REQUIRES_DECISION",
                "IDEMPOTENCY_PAYLOAD_CONFLICT",
            }
            else status.HTTP_400_BAD_REQUEST
        )
        return Response(
            {"code": exc.code, "message": exc.message, "details": exc.details},
            status=http_status,
        )

    def _payload_and_key(self, request, payload_override=None):
        request_payload = (
            request.data.dict() if hasattr(request.data, "dict") else dict(request.data)
        )
        payload = dict(request_payload) if payload_override is None else dict(payload_override)
        key = str(
            payload.pop("idempotencyKey", "")
            or request_payload.get("idempotencyKey", "")
            or request.headers.get("Idempotency-Key", "")
        ).strip()
        source_identity = payload.pop(
            "sourceIdentity", request_payload.get("sourceIdentity"),
        )
        for public_name, formal_name in self.input_fk_aliases.items():
            if public_name in payload and formal_name not in payload:
                payload[formal_name] = payload.pop(public_name)
        payload.setdefault("company_id", request.user.company_id)
        return payload, key, source_identity

    def _formal_write(self, request, *, object_id=None, payload_override=None):
        from pde.production_foundation_service import (
            ProductionFoundationError, ProductionFoundationService,
        )

        payload, key, source_identity = self._payload_and_key(request, payload_override)
        if not object_id and not source_identity and key:
            source_identity = {
                "sourceSystem": "PCE",
                "sourceType": "LEGACY_API_COMPATIBILITY",
                "sourceObjectType": f"{self.formal_entity}:manual-create",
                "externalId": key,
                "auditMetadata": {"channel": "masterdata.legacy-api"},
            }
        try:
            result = ProductionFoundationService.write(
                self.formal_entity,
                user=request.user,
                payload=payload,
                idempotency_key=key,
                source_identity=source_identity,
                object_id=object_id,
            )
        except ProductionFoundationError as exc:
            return None, self._error_response(exc)
        instance = self.get_queryset().get(pk=result["row"]["id"])
        data = dict(self.get_serializer(instance).data)
        data["formalWrite"] = {
            "auditId": result.get("auditId"),
            "actionRequestId": result.get("actionRequestId"),
            "idempotentReplay": result.get("idempotentReplay", False),
        }
        return data, None

    def create(self, request, *args, **kwargs):
        data, error = self._formal_write(request)
        return error or Response(data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        data, error = self._formal_write(request, object_id=kwargs.get("pk"))
        return error or Response(data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        payload = {
            "is_active": False,
            "reason": request.data.get("reason")
            or request.headers.get("X-Maintenance-Reason", ""),
        }
        data, error = self._formal_write(
            request, object_id=kwargs.get("pk"), payload_override=payload,
        )
        return error or Response(data, status=status.HTTP_200_OK)


class MaterialCategoryViewSet(FormalMasterDataWriteMixin, viewsets.ModelViewSet):
    queryset = MaterialCategory.objects.all()
    serializer_class = MaterialCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    formal_entity = "material-categories"
    input_fk_aliases = {"parent": "parent_id"}


class MaterialViewSet(FormalMasterDataWriteMixin, viewsets.ModelViewSet):
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MaterialPagination
    formal_entity = "materials"
    input_fk_aliases = {
        "category": "category_id",
        "base_uom": "base_uom_id",
        "purchase_uom": "purchase_uom_id",
    }

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def export_template(self, request):
        """下载导入模板（Excel）"""
        df = pd.DataFrame({
            '序号': [1],
            '物料编码': ['MT001'],
            '物料名称': ['示例物料'],
            '规格型号': ['规格ABC-123'],
            '单位': ['个'],
            '单价': [100.00],
            '物料类型': ['成品'],
            '物料分类': ['电子设备'],
            '安全库存': [10],
            '最高库存': [100],
            '补货点': [20],
            '采购件': ['是'],
            '生产件': ['否'],
            '标准成本': [80.00],
            '状态': ['启用'],
        })

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='物料模板', index=False)

        response = HttpResponse(output.getvalue(
        ), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="material_template.xlsx"'
        return response

    @action(detail=False, methods=['post'])
    def import_excel(self, request):
        """导入 Excel 或 CSV 文件"""
        return Response({
            "code": "LEGACY_MATERIAL_IMPORT_WRITE_CLOSED",
            "message": "旧Material导入不得绕过Canonical、权限、审计与幂等门禁；请使用企业基础资料正式导入。",
            "formalEndpoint": "/api/pde/formal-import/materials/commit/",
        }, status=status.HTTP_409_CONFLICT)

class CodeRuleViewSet(viewsets.ModelViewSet):
    queryset = CodeRule.objects.all()
    serializer_class = CodeRuleSerializer
    permission_classes = [permissions.IsAuthenticated]
