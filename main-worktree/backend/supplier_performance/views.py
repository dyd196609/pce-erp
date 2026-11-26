from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, Sum
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from system.authentication import JWTAuthentication
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.authentication import CanaryActorAuthentication

from .models import (
    BuyerPerformanceMetric,
    SupplierPerformanceMetric,
    SupplierPayableConfirmation,
    SupplierPaymentRequest,
    SupplierPaymentStatusRecord,
    SupplierSettlementCompletion,
    SupplierSettlementActionAudit,
    SupplierReconciliation,
    SupplierReconciliationConfirmation,
    SupplierReconciliationDifference,
)
from .services import (
    STATUS_LABELS,
    VERSION,
    V83_VERSION,
    V831_VERSION,
    V84_VERSION,
    available_v831_actions,
    base_facts,
    execute_v831_action,
    inspect_v831_action,
    serialize_v831_audits,
)
from .formal_services import (
    ACTION_LABELS as FORMAL_ACTION_LABELS,
    BATCH_ID as FORMAL_BATCH_ID,
    FORMAL_VERSION,
    FormalActionBlocked,
    execute_formal_action,
    formal_chain_readback,
    inspect_formal_action,
)


def apply_common_filters(query, request, field_map):
    for parameter, model_field in field_map.items():
        value = request.query_params.get(parameter, "").strip()
        if value:
            query = query.filter(**{model_field: value})
    period_from = request.query_params.get("periodFrom", "").strip()[:7]
    period_to = request.query_params.get("periodTo", "").strip()[:7]
    if period_from:
        query = query.filter(period__gte=period_from)
    if period_to:
        query = query.filter(period__lte=period_to)
    return query


def envelope(results, facts, facts_key):
    count = len(results)
    acceptance = {
        "contractVersion": "PCE-ACCEPTANCE-OBSERVABILITY-CONTRACT-V1.0",
        "factSource": "server", "recordCount": count, "actionCount": facts["actionCount"],
        "dangerActionCount": 0, "businessProgressWriteCount": 0,
        "downstreamObjectCount": 0, "acceptanceStatus": "PASS", "unknownReason": "",
        "workflowActionCount": facts.get("workflowActionCount", 0),
        "availableActionCount": facts.get("availableActionCount", 0),
        "executedActionCount": facts.get("executedActionCount", 0),
        "auditRecordCount": facts.get("auditRecordCount", 0),
        "detailViewMode": facts.get("detailViewMode", ""),
    }
    return Response({
        "success": True, "version": VERSION,
        "data": {"recordCount": count, "results": results, facts_key: facts,
                 "diagnosticFacts": dict(facts), "strictFacts": dict(facts),
                 "acceptanceFacts": acceptance},
        "error": None, "meta": {"source": "server", "version": VERSION},
    })


def serialize_business_state_history(object_type, object_id, status_labels):
    def business_reason(value):
        result = str(value or "")
        for status_code, status_label in sorted(
            status_labels.items(), key=lambda item: len(item[0]), reverse=True
        ):
            result = result.replace(status_code, status_label)
        return result

    rows = BusinessStateTransition.objects.filter(
        object_type=object_type, object_id=object_id
    ).select_related("operator").order_by("version", "pk")
    return [
        {
            "version": row.version,
            "beforeStatus": status_labels.get(
                row.source_state, "业务对象建立"
            ),
            "afterStatus": status_labels.get(
                row.target_state, row.target_state
            ),
            "operator": row.operator.get_username(),
            "timestamp": row.timestamp.isoformat(),
            "reason": business_reason(row.reason),
        }
        for row in rows
    ]


def supplier_source_chain(reconciliation):
    if reconciliation is None:
        return [
            {"label": label, "count": 0, "references": []}
            for label in (
                "采购订单", "收货", "质量检验", "入库", "供应商对账"
            )
        ]
    return [
        {
            "label": "采购订单",
            "count": len(reconciliation.purchase_order_ids),
            "references": reconciliation.purchase_order_ids,
        },
        {
            "label": "收货",
            "count": len(reconciliation.receipt_ids),
            "references": reconciliation.receipt_ids,
        },
        {
            "label": "质量检验",
            "count": len(reconciliation.inspection_ids),
            "references": reconciliation.inspection_ids,
        },
        {
            "label": "入库",
            "count": len(reconciliation.warehouse_receipt_ids),
            "references": reconciliation.warehouse_receipt_ids,
        },
        {
            "label": "供应商对账",
            "count": 1,
            "references": [reconciliation.reconciliation_no],
        },
    ]


def payable_business_detail(obj, history, audits):
    reconciliation = SupplierReconciliation.objects.filter(
        reconciliation_no=obj.reconciliation_no
    ).first()
    return {
        "detailViewMode": "business_card",
        "basicInformation": {
            "number": obj.payable_confirmation_no,
            "supplier": obj.supplier_name,
            "period": obj.period,
            "sourceDocument": obj.reconciliation_no,
        },
        "amountInformation": {
            "confirmedAmount": str(obj.confirmed_amount),
            "deductionAmount": str(obj.deduction_amount),
            "finalAmount": str(obj.final_payable_amount),
        },
        "businessSourceChain": supplier_source_chain(reconciliation),
        "currentStatus": obj.get_status_display(),
        "stateHistory": history,
        "operationRecords": audits,
    }


def request_business_detail(obj, history, audits):
    payable = SupplierPayableConfirmation.objects.filter(
        payable_confirmation_no=obj.payable_confirmation_no
    ).first()
    reconciliation = (
        SupplierReconciliation.objects.filter(
            reconciliation_no=payable.reconciliation_no
        ).first()
        if payable else None
    )
    return {
        "detailViewMode": "business_card",
        "basicInformation": {
            "number": obj.payment_request_no,
            "supplier": obj.supplier_name,
            "period": obj.period,
            "sourceDocument": obj.payable_confirmation_no,
        },
        "amountInformation": {
            "confirmedAmount": str(
                payable.confirmed_amount if payable else obj.request_amount
            ),
            "deductionAmount": str(
                payable.deduction_amount if payable else 0
            ),
            "finalAmount": str(obj.request_amount),
        },
        "businessSourceChain": supplier_source_chain(reconciliation),
        "currentStatus": obj.get_status_display(),
        "stateHistory": history,
        "operationRecords": audits,
    }


class SupplierReconciliationListView(APIView):
    permission_classes = []

    def get(self, request):
        query = SupplierReconciliation.objects.order_by("reconciliation_no")
        keyword = request.query_params.get("q", "").strip()
        if keyword:
            query = query.filter(Q(reconciliation_no__icontains=keyword) | Q(supplier_name__icontains=keyword))
        query = apply_common_filters(query, request, {
            "reconciliationNo": "reconciliation_no",
            "supplierName": "supplier_name",
            "statusCode": "status",
        })
        results = []
        for obj in query:
            history = list(BusinessStateTransition.objects.filter(
                object_type="SupplierReconciliation", object_id=obj.pk
            ).order_by("version").values("source_state", "target_state", "version", "audit_reference"))
            results.append({
                "id": obj.id, "reconciliationNo": obj.reconciliation_no,
                "supplierId": obj.supplier_id, "supplierName": obj.supplier_name,
                "period": obj.period, "purchaseOrderIds": obj.purchase_order_ids,
                "receiptIds": obj.receipt_ids, "inspectionIds": obj.inspection_ids,
                "warehouseReceiptIds": obj.warehouse_receipt_ids,
                "inventoryTransactionIds": obj.inventory_transaction_ids,
                "sourceCounts": {"purchaseOrder": len(obj.purchase_order_ids), "receipt": len(obj.receipt_ids),
                                 "inspection": len(obj.inspection_ids), "warehouseReceipt": len(obj.warehouse_receipt_ids),
                                 "inventoryTransaction": len(obj.inventory_transaction_ids)},
                "purchaseAmount": str(obj.purchase_amount), "receivedAmount": str(obj.received_amount),
                "qualifiedAmount": str(obj.qualified_amount), "reconciliationAmount": str(obj.reconciliation_amount),
                "statusCode": obj.status, "statusLabel": STATUS_LABELS[obj.status],
                "internalReviewStatus": "通过" if obj.status in {"supplier_confirming", "completed"} else ("审核中" if obj.status == "internal_review" else "未开始"),
                "supplierConfirmationStatus": "已确认" if obj.status == "completed" else ("确认中" if obj.status == "supplier_confirming" else "未开始"),
                "completed": obj.status == "completed", "stateHistory": history,
            })
        counts = {status: sum(row["statusCode"] == status for row in results) for status in STATUS_LABELS}
        facts = base_facts(len(results), "SupplierReconciliationFacts", "/api/scm/supplier-reconciliations/", **{
            "draftCount": counts["draft"], "internalReviewCount": counts["internal_review"],
            "supplierConfirmingCount": counts["supplier_confirming"], "completedCount": counts["completed"],
        })
        return envelope(results, facts, "reconciliationFacts")


class BuyerPerformanceListView(APIView):
    permission_classes = []

    def get(self, request):
        query = apply_common_filters(
            BuyerPerformanceMetric.objects.order_by("buyer_id"),
            request,
            {"buyerId": "buyer_id", "buyerName": "buyer_name"},
        )
        results = [{
            "metricNo": obj.metric_no, "buyerId": obj.buyer_id, "buyerName": obj.buyer_name,
            "period": obj.period, "purchaseOrderCount": obj.purchase_order_count,
            "onTimePurchaseRate": str(obj.on_time_purchase_rate),
            "priceOptimizationRate": str(obj.price_optimization_rate),
            "supplierIssueResponseTime": str(obj.supplier_issue_response_time),
            "processComplianceRate": str(obj.process_compliance_rate),
            "overallScore": str(obj.overall_score), "sourcePurchaseOrderIds": obj.source_purchase_order_ids,
        } for obj in query]
        facts = base_facts(len(results), "BuyerPerformanceFacts", "/api/scm/buyer-performance/", **{
            "metricCount": len(results), "sourcePurchaseOrderCount": sum(row["purchaseOrderCount"] for row in results)
        })
        return envelope(results, facts, "performanceFacts")


class SupplierPerformanceListView(APIView):
    permission_classes = []

    def get(self, request):
        query = apply_common_filters(
            SupplierPerformanceMetric.objects.order_by("supplier_id"),
            request,
            {"supplierId": "supplier_id", "supplierName": "supplier_name"},
        )
        results = [{
            "metricNo": obj.metric_no, "supplierId": obj.supplier_id, "supplierName": obj.supplier_name,
            "period": obj.period, "deliveryOnTimeRate": str(obj.delivery_on_time_rate),
            "qualityPassRate": str(obj.quality_pass_rate), "priceTrendScore": str(obj.price_trend_score),
            "serviceScore": str(obj.service_score), "reconciliationAccuracyRate": str(obj.reconciliation_accuracy_rate),
            "overallScore": str(obj.overall_score), "sourceReconciliationIds": obj.source_reconciliation_ids,
        } for obj in query]
        facts = base_facts(len(results), "SupplierPerformanceFacts", "/api/scm/supplier-performance/", **{
            "metricCount": len(results), "sourceReconciliationCount": sum(len(row["sourceReconciliationIds"]) for row in results)
        })
        return envelope(results, facts, "performanceFacts")


class SupplierReconciliationDifferenceListView(APIView):
    permission_classes = []

    def get(self, request):
        query = SupplierReconciliationDifference.objects.order_by("difference_no")
        keyword = request.query_params.get("q", "").strip()
        if keyword:
            query = query.filter(
                Q(difference_no__icontains=keyword)
                | Q(reconciliation_no__icontains=keyword)
                | Q(supplier_name__icontains=keyword)
                | Q(buyer_name__icontains=keyword)
            )
        query = apply_common_filters(query, request, {
            "supplierName": "supplier_name",
            "differenceType": "difference_type",
            "responsibilityType": "responsibility_type",
            "statusCode": "status",
        })
        occurred_from = request.query_params.get("occurredAtFrom", "").strip()
        occurred_to = request.query_params.get("occurredAtTo", "").strip()
        if occurred_from:
            query = query.filter(occurred_at__gte=occurred_from)
        if occurred_to:
            query = query.filter(occurred_at__lte=occurred_to)
        type_labels = dict(SupplierReconciliationDifference.DifferenceType.choices)
        responsibility_labels = dict(SupplierReconciliationDifference.ResponsibilityType.choices)
        status_labels = dict(SupplierReconciliationDifference.Status.choices)
        results = []
        for obj in query:
            history = list(BusinessStateTransition.objects.filter(
                object_type="SupplierReconciliationDifference", object_id=obj.pk
            ).order_by("version").values(
                "source_state", "target_state", "version", "audit_reference"
            ))
            results.append({
                "id": obj.id,
                "differenceNo": obj.difference_no,
                "reconciliationNo": obj.reconciliation_no,
                "supplierId": obj.supplier_id,
                "supplierName": obj.supplier_name,
                "buyerId": obj.buyer_id,
                "buyerName": obj.buyer_name,
                "differenceType": obj.difference_type,
                "differenceTypeLabel": type_labels[obj.difference_type],
                "differenceAmount": str(obj.difference_amount),
                "differenceQuantity": str(obj.difference_quantity),
                "responsibilityType": obj.responsibility_type,
                "responsibilityLabel": responsibility_labels[obj.responsibility_type],
                "occurredAt": obj.occurred_at.isoformat(),
                "statusCode": obj.status,
                "statusLabel": status_labels[obj.status],
                "sourceObjectRefs": obj.source_object_refs,
                "stateHistory": history,
            })
        amount = sum((obj.difference_amount for obj in query), 0)
        facts = base_facts(len(results), "SupplierReconciliationDifferenceFacts",
                           "/api/scm/supplier-reconciliation-differences/", **{
                               "differenceCount": len(results),
                               "differenceAmount": str(amount),
                               "supplierCount": len({row["supplierId"] for row in results}),
                               "closedCount": sum(row["statusCode"] == "closed" for row in results),
                           })
        return envelope(results, facts, "differenceFacts")


class SupplierReconciliationConfirmationListView(APIView):
    permission_classes = []

    def get(self, request):
        query = SupplierReconciliationConfirmation.objects.order_by("confirmation_no")
        differences = {
            item.difference_no: item
            for item in SupplierReconciliationDifference.objects.all()
        }
        keyword = request.query_params.get("q", "").strip()
        if keyword:
            matching_difference_nos = [
                item.difference_no for item in differences.values()
                if keyword.lower() in item.supplier_name.lower()
            ]
            query = query.filter(
                Q(confirmation_no__icontains=keyword)
                | Q(difference_no__icontains=keyword)
                | Q(difference_no__in=matching_difference_nos)
            )
        supplier_name = request.query_params.get("supplierName", "").strip()
        if supplier_name:
            matching = [
                item.difference_no for item in differences.values()
                if item.supplier_name == supplier_name
            ]
            query = query.filter(difference_no__in=matching)
        status_code = request.query_params.get("statusCode", "").strip()
        if status_code:
            query = query.filter(status=status_code)
        confirmed_from = request.query_params.get("confirmedAtFrom", "").strip()
        confirmed_to = request.query_params.get("confirmedAtTo", "").strip()
        if confirmed_from:
            query = query.filter(confirmed_at__date__gte=confirmed_from)
        if confirmed_to:
            query = query.filter(confirmed_at__date__lte=confirmed_to)
        status_labels = dict(SupplierReconciliationConfirmation.Status.choices)
        response_labels = {"accepted": "认可", "disputed": "有异议", "pending": "待回复"}
        results = []
        for obj in query:
            difference = differences.get(obj.difference_no)
            results.append({
                "id": obj.id,
                "confirmationNo": obj.confirmation_no,
                "differenceNo": obj.difference_no,
                "supplierId": obj.supplier_id,
                "supplierName": difference.supplier_name if difference else "",
                "supplierResponse": obj.supplier_response,
                "supplierResponseLabel": response_labels.get(obj.supplier_response, obj.supplier_response),
                "supplierComment": obj.supplier_comment,
                "confirmedBy": obj.confirmed_by,
                "confirmedAt": obj.confirmed_at.isoformat() if obj.confirmed_at else "",
                "statusCode": obj.status,
                "statusLabel": status_labels[obj.status],
            })
        facts = base_facts(len(results), "SupplierReconciliationConfirmationFacts",
                           "/api/scm/supplier-reconciliation-confirmations/", **{
                               "confirmationCount": len(results),
                               "waitingSupplierCount": sum(row["statusCode"] == "waiting_supplier" for row in results),
                               "completedCount": sum(row["statusCode"] == "completed" for row in results),
                           })
        return envelope(results, facts, "confirmationFacts")


class BuyerExceptionAnalysisListView(APIView):
    permission_classes = []

    def get(self, request):
        query = apply_common_filters(
            BuyerPerformanceMetric.objects.order_by("buyer_id"),
            request,
            {"buyerId": "buyer_id", "buyerName": "buyer_name"},
        )
        keyword = request.query_params.get("q", "").strip()
        if keyword:
            query = query.filter(Q(buyer_name__icontains=keyword) | Q(buyer_id__icontains=keyword))
        results = [{
            "id": obj.id,
            "buyerId": obj.buyer_id,
            "buyerName": obj.buyer_name,
            "period": obj.period,
            "purchaseOrderCount": obj.purchase_order_count,
            "differenceResponsibilityCount": obj.difference_responsibility_count,
            "supplierIssueCount": obj.supplier_issue_count,
            "priceDifferenceCount": obj.price_difference_count,
            "deliveryDelayCount": obj.delivery_delay_count,
            "managementScore": str(obj.overall_score),
        } for obj in query]
        facts = base_facts(len(results), "BuyerExceptionAnalysisFacts",
                           "/api/scm/buyer-exception-analysis/", **{
                               "buyerCount": len(results),
                               "differenceCount": sum(row["differenceResponsibilityCount"] for row in results),
                               "supplierIssueCount": sum(row["supplierIssueCount"] for row in results),
                           })
        return envelope(results, facts, "exceptionFacts")


class SupplierPayableConfirmationListView(APIView):
    permission_classes = []

    def get(self, request):
        query = SupplierPayableConfirmation.objects.order_by("payable_confirmation_no")
        keyword = request.query_params.get("q", "").strip()
        if keyword:
            query = query.filter(
                Q(payable_confirmation_no__icontains=keyword)
                | Q(reconciliation_no__icontains=keyword)
                | Q(supplier_name__icontains=keyword)
            )
        query = apply_common_filters(query, request, {
            "supplierName": "supplier_name",
            "statusCode": "status",
        })
        status_labels = dict(SupplierPayableConfirmation.Status.choices)
        results = []
        for obj in query:
            history = serialize_business_state_history(
                "SupplierPayableConfirmation", obj.pk, status_labels
            )
            audits = serialize_v831_audits(
                "SupplierPayableConfirmation", obj.pk
            )
            results.append({
                "id": obj.id,
                "payableConfirmationNo": obj.payable_confirmation_no,
                "supplierId": obj.supplier_id,
                "supplierName": obj.supplier_name,
                "reconciliationNo": obj.reconciliation_no,
                "period": obj.period,
                "confirmedAmount": str(obj.confirmed_amount),
                "qualifiedAmount": str(obj.qualified_amount),
                "deductionAmount": str(obj.deduction_amount),
                "finalPayableAmount": str(obj.final_payable_amount),
                "sourceObjectRefs": obj.source_object_refs,
                "batchId": obj.batch_id,
                "statusCode": obj.status,
                "statusLabel": status_labels[obj.status],
                "stateHistory": history,
                "availableActions": [] if obj.batch_id == FORMAL_BATCH_ID else available_v831_actions(
                    "SupplierPayableConfirmation", obj.status
                ),
                "actionAuditTrail": audits,
                "businessDetail": payable_business_detail(
                    obj, history, audits
                ),
            })
        facts = base_facts(
            len(results), "SupplierPayableConfirmationFacts",
            "/api/scm/supplier-payable-confirmations/",
            confirmationCount=len(results),
            supplierCount=len({row["supplierId"] for row in results}),
            confirmedAmount=str(sum((obj.final_payable_amount for obj in query), 0)),
            pendingCount=sum(row["statusCode"] in {"draft", "internal_review"} for row in results),
            confirmedCount=sum(
                row["statusCode"] in {"confirmed", "ready_for_payment_request"} for row in results
            ),
            readyForPaymentRequestCount=sum(
                row["statusCode"] == "ready_for_payment_request" for row in results
            ),
            paymentExecutionCount=0,
            batchId="SUPPLIER-SETTLEMENT-V83",
            workflowActionCount=3,
            availableActionCount=sum(len(row["availableActions"]) for row in results),
            executedActionCount=SupplierSettlementActionAudit.objects.filter(
                object_type="SupplierPayableConfirmation",
                object_id__in=[row["id"] for row in results],
            ).count(),
            auditRecordCount=SupplierSettlementActionAudit.objects.filter(
                object_type="SupplierPayableConfirmation",
                object_id__in=[row["id"] for row in results],
            ).count(),
            detailViewMode="business_card",
        )
        response = envelope(results, facts, "payableConfirmationFacts")
        response.data["version"] = V831_VERSION
        response.data["meta"]["version"] = V831_VERSION
        return response


class SupplierPaymentRequestListView(APIView):
    permission_classes = []

    def get(self, request):
        query = SupplierPaymentRequest.objects.order_by("payment_request_no")
        keyword = request.query_params.get("q", "").strip()
        if keyword:
            query = query.filter(
                Q(payment_request_no__icontains=keyword)
                | Q(payable_confirmation_no__icontains=keyword)
                | Q(supplier_name__icontains=keyword)
            )
        query = apply_common_filters(query, request, {
            "supplierName": "supplier_name",
            "statusCode": "status",
        })
        status_labels = dict(SupplierPaymentRequest.Status.choices)
        results = []
        for obj in query:
            history = serialize_business_state_history(
                "SupplierPaymentRequest", obj.pk, status_labels
            )
            audits = serialize_v831_audits(
                "SupplierPaymentRequest", obj.pk
            )
            results.append({
                "id": obj.id,
                "paymentRequestNo": obj.payment_request_no,
                "payableConfirmationNo": obj.payable_confirmation_no,
                "supplierId": obj.supplier_id,
                "supplierName": obj.supplier_name,
                "period": obj.period,
                "requestAmount": str(obj.request_amount),
                "requestReason": obj.request_reason,
                "requestedBy": obj.requested_by,
                "batchId": obj.batch_id,
                "statusCode": obj.status,
                "statusLabel": status_labels[obj.status],
                "stateHistory": history,
                "availableActions": [] if obj.batch_id == FORMAL_BATCH_ID else available_v831_actions(
                    "SupplierPaymentRequest", obj.status
                ),
                "actionAuditTrail": audits,
                "businessDetail": request_business_detail(
                    obj, history, audits
                ),
            })
        facts = base_facts(
            len(results), "SupplierPaymentRequestFacts",
            "/api/scm/supplier-payment-requests/",
            requestCount=len(results),
            supplierCount=len({row["supplierId"] for row in results}),
            requestAmount=str(sum((obj.request_amount for obj in query), 0)),
            paymentPendingCount=sum(row["statusCode"] == "payment_pending" for row in results),
            paymentExecutionCount=0,
            fundDeductionCount=0,
            bankTransactionCount=0,
            batchId="SUPPLIER-SETTLEMENT-V83",
            workflowActionCount=3,
            availableActionCount=sum(len(row["availableActions"]) for row in results),
            executedActionCount=SupplierSettlementActionAudit.objects.filter(
                object_type="SupplierPaymentRequest",
                object_id__in=[row["id"] for row in results],
            ).count(),
            auditRecordCount=SupplierSettlementActionAudit.objects.filter(
                object_type="SupplierPaymentRequest",
                object_id__in=[row["id"] for row in results],
            ).count(),
            detailViewMode="business_card",
        )
        response = envelope(results, facts, "paymentRequestFacts")
        response.data["version"] = V831_VERSION
        response.data["meta"]["version"] = V831_VERSION
        return response


class SupplierPaymentStatusRecordListView(APIView):
    permission_classes = []

    def get(self, request):
        query = SupplierPaymentStatusRecord.objects.order_by("payment_request_no")
        keyword = request.query_params.get("q", "").strip()
        if keyword:
            query = query.filter(
                Q(payment_request_no__icontains=keyword)
                | Q(supplier_name__icontains=keyword)
                | Q(operator__icontains=keyword)
            )
        supplier_name = request.query_params.get("supplierName", "").strip()
        payment_status = request.query_params.get("paymentStatus", "").strip()
        if supplier_name:
            query = query.filter(supplier_name=supplier_name)
        if payment_status:
            query = query.filter(status=payment_status)
        labels = dict(SupplierPaymentStatusRecord.Status.choices)

        def business_remark(value):
            result = value or ""
            for code, label in sorted(
                labels.items(), key=lambda item: len(item[0]), reverse=True
            ):
                result = result.replace(code, label)
            return result

        results = []
        for obj in query:
            history = serialize_business_state_history(
                "SupplierPaymentStatusRecord", obj.pk, labels
            )
            results.append({
                "id": obj.pk,
                "paymentRequestNo": obj.payment_request_no,
                "supplierId": obj.supplier_id,
                "supplierName": obj.supplier_name,
                "paymentAmount": str(obj.payment_amount),
                "paymentStatus": obj.status,
                "statusLabel": labels[obj.status],
                "statusHistory": history,
                "operator": obj.operator,
                "operateTime": obj.operate_time.isoformat(),
                "remark": business_remark(obj.remark),
            })
        facts = base_facts(
            len(results),
            "SupplierPaymentStatusRecordFacts",
            "/api/scm/supplier-payment-status/",
            actionCount=3,
            draftCount=sum(row["paymentStatus"] == "draft" for row in results),
            paymentScheduledCount=sum(
                row["paymentStatus"] == "payment_scheduled" for row in results
            ),
            paymentCompletedCount=sum(
                row["paymentStatus"] == "payment_completed" for row in results
            ),
            settlementCompletedCount=sum(
                row["paymentStatus"] == "settlement_completed" for row in results
            ),
            batchId="SUPPLIER-SETTLEMENT-V84",
        )
        response = envelope(results, facts, "paymentStatusFacts")
        response.data["version"] = V84_VERSION
        response.data["meta"]["version"] = V84_VERSION
        return response


class SupplierSettlementCompletionListView(APIView):
    permission_classes = []

    def get(self, request):
        query = SupplierSettlementCompletion.objects.order_by("settlement_no")
        keyword = request.query_params.get("q", "").strip()
        if keyword:
            query = query.filter(
                Q(settlement_no__icontains=keyword)
                | Q(reconciliation_no__icontains=keyword)
                | Q(payment_request_no__icontains=keyword)
                | Q(supplier_name__icontains=keyword)
            )
        supplier_name = request.query_params.get("supplierName", "").strip()
        completion_status = request.query_params.get("completionStatus", "").strip()
        if supplier_name:
            query = query.filter(supplier_name=supplier_name)
        if completion_status:
            query = query.filter(status=completion_status)
        labels = dict(SupplierSettlementCompletion.Status.choices)
        results = [{
            "id": obj.pk,
            "settlementNo": obj.settlement_no,
            "supplierId": obj.supplier_id,
            "supplierName": obj.supplier_name,
            "reconciliationNo": obj.reconciliation_no,
            "paymentRequestNo": obj.payment_request_no,
            "completionStatus": obj.status,
            "statusLabel": labels[obj.status],
            "completionDate": (
                obj.completion_date.isoformat() if obj.completion_date else ""
            ),
            "performanceUpdateFlag": obj.performance_update_flag,
            "performanceUpdateLabel": (
                "绩效来源已更新" if obj.performance_update_flag else "待更新"
            ),
        } for obj in query]
        facts = base_facts(
            len(results),
            "SupplierSettlementCompletionFacts",
            "/api/scm/supplier-settlement-completions/",
            actionCount=1,
            completedCount=sum(
                row["completionStatus"] == "completed" for row in results
            ),
            pendingCount=sum(
                row["completionStatus"] == "pending" for row in results
            ),
            performanceUpdatedCount=sum(
                row["performanceUpdateFlag"] for row in results
            ),
            supplierPerformanceSource="SupplierSettlementCompletion",
            buyerPerformanceSource="SupplierSettlementCompletion",
            batchId="SUPPLIER-SETTLEMENT-V84",
        )
        response = envelope(results, facts, "settlementCompletionFacts")
        response.data["version"] = V84_VERSION
        response.data["meta"]["version"] = V84_VERSION
        return response


class SupplierSettlementWorkflowActionView(APIView):
    authentication_classes = [CanaryActorAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        action_code = str(
            request.query_params.get("actionCode", "")
        ).strip()
        object_id = request.query_params.get("objectId")
        try:
            definition, obj, decision = inspect_v831_action(
                user=request.user,
                action_code=action_code,
                object_id=int(object_id),
            )
        except (TypeError, ValueError) as error:
            return Response(
                {
                    "result": "blocked",
                    "error": {
                        "code": str(error),
                        "message": "动作或当前状态不允许",
                    },
                },
                status=409,
            )
        except PermissionError as error:
            return Response(
                {
                    "result": "blocked",
                    "error": {
                        "code": str(error),
                        "message": "当前角色无权执行该动作",
                    },
                },
                status=403,
            )
        except ObjectDoesNotExist:
            return Response(
                {
                    "result": "blocked",
                    "error": {
                        "code": "WORKFLOW_OBJECT_NOT_FOUND",
                        "message": "业务对象不存在",
                    },
                },
                status=404,
            )
        return Response({
            "result": "passed",
            "version": V831_VERSION,
            "currentStateSource": "server",
            "data": {
                "objectId": obj.pk,
                "actionCode": action_code,
                "actionLabel": definition["label"],
                "currentStatus": obj.status,
                "targetStatus": definition["target"],
                "role": definition["role"],
                "permissionGranted": decision["granted"],
                "registrySource": "PCE Business Action Registry",
            },
        })

    def post(self, request):
        action_code = str(request.data.get("actionCode", "")).strip()
        object_id = request.data.get("objectId")
        reason = str(request.data.get("reason", "")).strip() or "页面业务操作"
        try:
            result = execute_v831_action(
                user=request.user,
                action_code=action_code,
                object_id=int(object_id),
                reason=reason,
            )
        except (TypeError, ValueError) as error:
            return Response(
                {"result": "blocked", "error": {"code": str(error), "message": "动作或当前状态不允许"}},
                status=409,
            )
        except PermissionError as error:
            return Response(
                {"result": "blocked", "error": {"code": str(error), "message": "当前角色无权执行该动作"}},
                status=403,
            )
        except ObjectDoesNotExist:
            return Response(
                {"result": "blocked", "error": {"code": "WORKFLOW_OBJECT_NOT_FOUND", "message": "业务对象不存在"}},
                status=404,
            )
        return Response({
            "result": "passed",
            "version": V831_VERSION,
            "currentStateSource": "server",
            "data": result,
            "safety": {
                "paymentExecutionWriteCount": 0,
                "bankSendWriteCount": 0,
                "fundDeductionCount": 0,
                "financialImpactWriteCount": 0,
            },
        })


class SupplierSettlementFormalActionView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        action_code = str(request.query_params.get("actionCode", "")).strip()
        source_id = request.query_params.get("sourceId")
        try:
            context = inspect_formal_action(
                user=request.user, action_code=action_code, source_id=int(source_id)
            )
        except (TypeError, ValueError) as error:
            if isinstance(error, FormalActionBlocked):
                return Response(
                    {"success": False, "error": {"code": error.code, "message": error.message}},
                    status=error.http_status,
                )
            return Response(
                {"success": False, "error": {"code": "FORMAL_ACTION_INPUT_INVALID", "message": "动作参数无效。"}},
                status=400,
            )
        return Response({
            "success": True,
            "data": {
                "formalVersion": FORMAL_VERSION,
                "actionCode": action_code,
                "actionLabel": FORMAL_ACTION_LABELS[action_code],
                "sourceId": int(source_id),
                "authorization": context["identity"],
                "executable": True,
            },
            "error": None,
            "meta": {"source": "server", "readOnly": True},
        })

    def post(self, request):
        action_code = str(request.data.get("actionCode", "")).strip()
        source_id = request.data.get("sourceId")
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            return Response(
                {"success": False, "error": {"code": "ACTION_REASON_REQUIRED", "message": "业务动作原因不能为空。"}},
                status=400,
            )
        try:
            result = execute_formal_action(
                user=request.user,
                action_code=action_code,
                source_id=int(source_id),
                reason=reason,
            )
        except (TypeError, ValueError) as error:
            if isinstance(error, FormalActionBlocked):
                return Response(
                    {"success": False, "error": {"code": error.code, "message": error.message}},
                    status=error.http_status,
                )
            return Response(
                {"success": False, "error": {"code": "FORMAL_ACTION_INPUT_INVALID", "message": str(error)}},
                status=409,
            )
        return Response({
            "success": True,
            "data": result,
            "error": None,
            "meta": {"source": "server", "businessWrite": True, "demoSeedCalled": False},
        })


class SupplierSettlementFormalChainReadbackView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        try:
            facts = formal_chain_readback(order_id)
        except FormalActionBlocked as error:
            return Response(
                {"success": False, "error": {"code": error.code, "message": error.message}},
                status=error.http_status,
            )
        return Response({
            "success": True,
            "data": facts,
            "error": None,
            "meta": {"source": "server", "readOnly": True, "demoSeedCalled": False},
        })
