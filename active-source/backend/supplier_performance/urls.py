from django.urls import path
from .views import (
    BuyerExceptionAnalysisListView,
    BuyerPerformanceListView,
    SupplierPerformanceListView,
    SupplierPayableConfirmationListView,
    SupplierPaymentRequestListView,
    SupplierPaymentStatusRecordListView,
    SupplierSettlementCompletionListView,
    SupplierSettlementWorkflowActionView,
    SupplierSettlementFormalActionView,
    SupplierSettlementFormalChainReadbackView,
    SupplierReconciliationConfirmationListView,
    SupplierReconciliationDifferenceListView,
    SupplierReconciliationListView,
)

urlpatterns = [
    path("supplier-reconciliations/", SupplierReconciliationListView.as_view()),
    path("buyer-performance/", BuyerPerformanceListView.as_view()),
    path("supplier-performance/", SupplierPerformanceListView.as_view()),
    path("supplier-reconciliation-differences/", SupplierReconciliationDifferenceListView.as_view()),
    path("supplier-reconciliation-confirmations/", SupplierReconciliationConfirmationListView.as_view()),
    path("buyer-exception-analysis/", BuyerExceptionAnalysisListView.as_view()),
    path("supplier-payable-confirmations/", SupplierPayableConfirmationListView.as_view()),
    path("supplier-payment-requests/", SupplierPaymentRequestListView.as_view()),
    path("supplier-payment-status/", SupplierPaymentStatusRecordListView.as_view()),
    path("supplier-settlement-completions/", SupplierSettlementCompletionListView.as_view()),
    path("supplier-settlement-workflow-actions/", SupplierSettlementWorkflowActionView.as_view()),
    path("supplier-settlement-formal-actions/", SupplierSettlementFormalActionView.as_view()),
    path("supplier-settlement-formal-chain/<int:order_id>/", SupplierSettlementFormalChainReadbackView.as_view()),
]
