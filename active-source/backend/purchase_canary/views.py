import sqlite3

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import OperationalError

from .catalog import BATCH_ID
from .models import PurchaseCanaryBatch
from .models import PurchaseCanaryLineage
from .retention import canary_retention_policy
from .persistent_read_model import load_persistent_canary_context
from .purchase_inquiry_runtime import load_purchase_inquiry_canary_runtime
from .supplier_quotation_runtime import load_supplier_quotation_canary_runtime
from .quote_comparison_runtime import load_quote_comparison_canary_runtime
from .price_approval_runtime import load_price_approval_canary_runtime
from .scenario_mapping import resolve_scm_canary_mapping, scm_canary_scenario_catalog
from .operation_data import (
    CONTRACT_VERSION as OPERATION_CONTRACT_VERSION,
    operation_pool_enabled,
    payable_check_operation_facts,
    payable_check_operation_rows,
)


STRICT_STATUS = {
    "payable-prepare": "prepared",
    "payable-check": "checked",
    "supplier-settlement": "settlement_ready",
    "purchase-reconciliation": "matched",
    "invoice-prepare": "prepared",
    "account-payable-draft": "draft",
    "account-payable-confirm": "prepared",
    "payment-application": "prepared",
    "payment-request": "approved",
    "payment-instruction-prepare": "validated",
    "payment-order-prepare": "submitted",
}

STRICT_PREFIX = {
    "payable-prepare": "PYP",
    "payable-check": "PYC",
    "supplier-settlement": "SET",
    "purchase-reconciliation": "PRC",
    "invoice-prepare": "PIP",
    "account-payable-draft": "APD",
}


def strict_successful_pool(batch, module_code):
    lineages = list(PurchaseCanaryLineage.objects.filter(
        batch=batch,
        scenario_class="pass_through",
        downstream_eligible=True,
    ).order_by("scenario_code"))
    prefix = STRICT_PREFIX.get(module_code)
    rows = []
    if prefix:
        for lineage in lineages:
            matches = [
                value for value in lineage.upstream_object_nos
                if str(value).startswith(f"{prefix}20")
            ]
            object_no = matches[0] if matches else ""
            if not object_no:
                continue
            rows.append({
                "scenarioCode": lineage.scenario_code,
                "objectNo": object_no,
                "status": STRICT_STATUS[module_code],
                "sourceObjectNo": lineage.upstream_object_nos[max(
                    0, lineage.upstream_object_nos.index(object_no) - 1
                )] if lineage.upstream_object_nos else "",
                "currentStateSource": "server",
                "evidenceHash": lineage.source_relation_hash,
            })
        return rows

    model_config = {
        "account-payable-confirm": (
            "payable_confirmation_prepare.PayableConfirmationPrepare",
            "prepare_no", "source_ap_draft_no",
        ),
        "payment-application": (
            "payment_request_prepare.PaymentRequestPrepare",
            "prepare_no", "source_payable_confirmation_prepare_no",
        ),
        "payment-request": (
            "payment_request.PaymentRequest",
            "request_no", "source_payment_request_prepare_no",
        ),
        "payment-instruction-prepare": (
            "payment_instruction_prepare.PaymentInstructionPrepare",
            "prepare_no", "source_payment_request_no",
        ),
        "payment-order-prepare": (
            "payment_order_prepare.PaymentOrderPrepare",
            "prepare_no", "source_payment_instruction_prepare_no",
        ),
    }
    config = model_config.get(module_code)
    if not config:
        return rows
    from django.apps import apps
    app_model, number_field, source_field = config
    app_label, model_name = app_model.split(".")
    model = apps.get_model(app_label, model_name)
    objects = model.objects.filter(
        tenant_id=batch.tenant_id,
        status=STRICT_STATUS[module_code],
    ).order_by("id")[:8]
    for item in objects:
        rows.append({
            "scenarioCode": f"PERSISTED-{item.pk}",
            "objectNo": getattr(item, number_field),
            "status": item.status,
            "sourceObjectNo": getattr(item, source_field, ""),
            "currentStateSource": "server",
            "evidenceHash": getattr(item, "source_key", ""),
        })
    return rows


def envelope(data):
    return {"success": True, "data": data, "error": None, "meta": {"module": "purchase-canary", "source": "server"}}


class CanaryContextView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        batch_id = request.query_params.get("batchId") or BATCH_ID
        scenario_code = request.query_params.get("scenarioCode") or "HAPPY_PATH"
        module_code = request.query_params.get("moduleCode") or "supplier-settlement"
        try:
            return Response(envelope(self._orm_context(batch_id, scenario_code, module_code)))
        except (OperationalError, PurchaseCanaryBatch.DoesNotExist):
            return Response(envelope(load_persistent_canary_context(
                batch_id,
                scenario_code,
                module_code,
            )))

    @staticmethod
    def _orm_context(batch_id, scenario_code, module_code):
        batch = PurchaseCanaryBatch.objects.get(batch_id=batch_id)
        scenarios = list(batch.scenarios.order_by("id"))
        frozen_mapping = resolve_scm_canary_mapping(batch_id, scenario_code)
        source_scenario_code = frozen_mapping["sourceScenarioCode"] if frozen_mapping else scenario_code
        selected = next((item for item in scenarios if item.code == source_scenario_code), None)
        if selected is None:
            raise PurchaseCanaryBatch.DoesNotExist
        canary_object_count = sum(
            item.module_objects.filter(module_code=module_code).count()
            for item in scenarios
        )
        objects = list(selected.module_objects.order_by("sequence"))
        purchase_request_object = next(
            (item for item in objects if item.module_code == "purchase-request"), None
        )
        if frozen_mapping and (
            purchase_request_object is None
            or purchase_request_object.object_no != frozen_mapping["businessNo"]
        ):
            raise PurchaseCanaryBatch.DoesNotExist
        current = next((item for item in objects if item.module_code == module_code), objects[0])
        previous = objects[current.sequence - 2] if current.sequence > 1 else None
        following = objects[current.sequence] if current.sequence < len(objects) else None
        retention = canary_retention_policy(batch)
        def object_data(item):
            return None if item is None else {
                "moduleCode": item.module_code, "moduleName": item.module_name,
                "routePath": item.route_path, "objectNo": item.object_no,
                "status": item.object_status,
            }
        return {
            "batchId": batch.batch_id, "tenantId": batch.tenant_id, "purpose": batch.purpose,
            "dataType": retention["dataType"], "retentionPolicy": retention,
            "version": batch.version, "currentStateSource": "server",
            "scenario": {"code": scenario_code, "name": frozen_mapping["name"] if frozen_mapping else selected.name, "expectedOutcome": selected.expected_outcome},
            "scenarios": scm_canary_scenario_catalog() if frozen_mapping else [{"code": item.code, "name": item.name} for item in scenarios],
            "businessNo": frozen_mapping["businessNo"] if frozen_mapping else current.object_no,
            "sourceScenarioCode": source_scenario_code,
            "canaryObjectCount": canary_object_count,
            "previous": object_data(previous), "current": {
                **object_data(current), "upstreamObjectNo": current.upstream_object_no,
                "downstreamObjectNo": current.downstream_object_no,
                "nextStepAllowed": current.next_step_allowed, "blockReason": current.block_reason,
                "evidenceHash": current.evidence_hash,
            }, "next": object_data(following),
            "moduleObjects": [object_data(item) | {
                "nextStepAllowed": item.next_step_allowed, "blockReason": item.block_reason,
            } for item in objects],
            "strictSuccessfulPool": strict_successful_pool(batch, module_code),
        }


class CanaryScenarioListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        batch = PurchaseCanaryBatch.objects.get(batch_id=request.query_params.get("batchId") or BATCH_ID)
        return Response(envelope({
            "batchId": batch.batch_id,
            "dataType": canary_retention_policy(batch)["dataType"],
            "retentionPolicy": canary_retention_policy(batch),
            "scenarios": [{"code": item.code, "name": item.name, "expectedOutcome": item.expected_outcome}
                          for item in batch.scenarios.order_by("id")],
        }))


class CanaryOperationDataView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if not operation_pool_enabled():
            return Response({
                "result": "blocked",
                "contractVersion": OPERATION_CONTRACT_VERSION,
                "error": {
                    "code": "PCE_CANARY_OPERATION_DATA_DISABLED",
                    "message": "金丝雀操作数据能力未启用。",
                },
            }, status=404)
        module_code = request.query_params.get("moduleCode", "")
        if module_code != "payable-check":
            return Response({
                "result": "blocked",
                "contractVersion": OPERATION_CONTRACT_VERSION,
                "error": {
                    "code": "PCE_CANARY_OPERATION_MODULE_UNSUPPORTED",
                    "message": "当前模块尚未注册操作数据池。",
                },
            }, status=404)
        rows = payable_check_operation_rows()
        strict_facts = payable_check_operation_facts(rows)
        return Response(envelope({
            "result": (
                "passed"
                if strict_facts["operationPoolConsistent"]
                else "blocked"
            ),
            "contractVersion": OPERATION_CONTRACT_VERSION,
            "currentStateSource": "server",
            "count": len(rows),
            "results": rows,
            "strictFacts": strict_facts,
            "businessWriteRequestCount": 0,
            "productionUserDataWritten": False,
        }))


class PurchaseInquiryCanaryRuntimeView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        batch_id = request.query_params.get("canaryBatchId") or "SCM-CANARY-FLOW-V1"
        scenario_code = request.query_params.get("scenarioCode") or "HAPPY_PATH"
        try:
            return Response(envelope(load_purchase_inquiry_canary_runtime(batch_id, scenario_code)))
        except (LookupError, OperationalError, sqlite3.Error) as error:
            return Response({
                "success": False,
                "data": None,
                "error": {"code": "PURCHASE_INQUIRY_CANARY_NOT_FOUND", "message": str(error)},
                "meta": {"module": "purchase-canary", "source": "server", "readOnly": True},
            }, status=404)


class SupplierQuotationCanaryRuntimeView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        batch_id = request.query_params.get("canaryBatchId") or "SCM-CANARY-FLOW-V1"
        scenario_code = request.query_params.get("scenarioCode") or "HAPPY_PATH"
        try:
            return Response(envelope(load_supplier_quotation_canary_runtime(batch_id, scenario_code)))
        except (LookupError, OperationalError, sqlite3.Error) as error:
            return Response({
                "success": False, "data": None,
                "error": {"code": "SUPPLIER_QUOTATION_CANARY_NOT_FOUND", "message": str(error)},
                "meta": {"module": "purchase-canary", "source": "server", "readOnly": True},
            }, status=404)


class QuoteComparisonCanaryRuntimeView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        batch_id = request.query_params.get("canaryBatchId") or "SCM-CANARY-FLOW-V1"
        scenario_code = request.query_params.get("scenarioCode") or "HAPPY_PATH"
        try:
            return Response(envelope(load_quote_comparison_canary_runtime(batch_id, scenario_code)))
        except (LookupError, OperationalError, sqlite3.Error) as error:
            return Response({
                "success": False, "data": None,
                "error": {"code": "QUOTE_COMPARISON_CANARY_NOT_FOUND", "message": str(error)},
                "meta": {"module": "purchase-canary", "source": "server", "readOnly": True},
            }, status=404)


class PriceApprovalCanaryRuntimeView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        batch_id = request.query_params.get("canaryBatchId") or "SCM-CANARY-FLOW-V1"
        scenario_code = request.query_params.get("scenarioCode") or "HAPPY_PATH"
        try:
            return Response(envelope(load_price_approval_canary_runtime(batch_id, scenario_code)))
        except (LookupError, OperationalError, sqlite3.Error) as error:
            return Response({
                "success": False, "data": None,
                "error": {"code": "PRICE_APPROVAL_CANARY_NOT_FOUND", "message": str(error)},
                "meta": {"module": "purchase-canary", "source": "server", "readOnly": True,
                    "productionUserDataWritten": False},
            }, status=404)
