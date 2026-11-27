from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from purchase.views import (
    PurchaseOrderViewSet,
    purchase_order_create,
    purchase_order_delete,
    purchase_order_detail,
    purchase_order_update,
    purchase_order_v6_detail,
    purchase_order_v6_list,
)
from system.admin import import_org_view
from system.views import api_login
from workflow_runtime.exception_handler import pce_api_not_found
from bank_send_execution_simulation.views import (
    ChainTraceListView,
    FinalApprovalFirstSubmitView,
    FinalApprovalListView,
    FinalApprovalSecondSubmitView,
    DualIsolationCheckListView,
    ProductionReleaseDecisionSubmitView,
    ProductionReleaseReviewListView,
    ExecutionFrameworkReviewListView,
    ConnectorAdapterReviewListView,
    ProductionIsolationGateListView,
    SimulationAuditListView,
)

# 创建路由器并注册订单视图集
router = DefaultRouter()
router.register(r"orders", PurchaseOrderViewSet, basename="purchase-order")

urlpatterns = [
    path("admin/import-org/", import_org_view, name="import_org"),
    path("admin/", admin.site.urls),
    path("api/auth/login/", api_login, name="api_login"),
    path("api/", include("system.urls")),
    path("api/pfm/", include("pfm.urls")),
    path("api/masterdata/", include("masterdata.urls")),
    path("api/procurement/", include("procurement.urls")),
    path("api/scm/purchase-reconciliations/", include("reconciliation.urls")),
    path("api/scm/", include("supplier_performance.urls")),
    path("api/scm/purchase-invoice-prepares/", include("purchase_invoice_prepare.urls")),
    path(
        "api/scm/purchase-accounts-payable-drafts/",
        include("purchase_accounts_payable_draft.urls"),
    ),
    path(
        "api/finance/payable-confirmation-prepares/",
        include("payable_confirmation_prepare.urls"),
    ),
    path(
        "api/finance/payment-request-prepares/",
        include("payment_request_prepare.urls"),
    ),
    path(
        "api/finance/payment-requests/",
        include("payment_request.urls"),
    ),
    path(
        "api/finance/payment-instruction-prepares/",
        include("payment_instruction_prepare.urls"),
    ),
    path(
        "api/finance/payment-order-prepares/",
        include("payment_order_prepare.urls"),
    ),
    path(
        "api/finance/payment-order-drafts/",
        include("payment_order_draft.urls"),
    ),
    path(
        "api/finance/payment-risk-reviews/",
        include("payment_risk_review.urls"),
    ),
    path(
        "api/finance/formal-payment-orders/",
        include("formal_payment_order.urls"),
    ),
    path(
        "api/finance/bank-send-prepares/",
        include("bank_send_preparation.urls"),
    ),
    path(
        "api/finance/bank-send-tasks/",
        include("bank_send_task.urls"),
    ),
    path(
        "api/finance/bank-send-execution-gates/",
        include("bank_send_execution_gate.urls"),
    ),
    path(
        "api/finance/bank-send-requests/",
        include("bank_send_request.urls"),
    ),
    path(
        "api/finance/bank-send-simulations/",
        include("bank_send_execution_simulation.urls"),
    ),
    path(
        "api/finance/bank-send-simulation-audits/",
        SimulationAuditListView.as_view(),
        name="bank-send-simulation-audit-list-v65",
    ),
    path(
        "api/finance/bank-send-isolation-gates/",
        ProductionIsolationGateListView.as_view(),
        name="bank-send-isolation-gate-list-v65",
    ),
    path(
        "api/finance/bank-send-chain-traces/",
        ChainTraceListView.as_view(),
        name="bank-send-chain-trace-list-v66",
    ),
    path(
        "api/finance/bank-send-final-approvals/",
        FinalApprovalListView.as_view(),
        name="bank-send-final-approval-list-v66",
    ),
    path(
        "api/finance/bank-send-final-approvals/<int:approval_id>/first-approve/",
        FinalApprovalFirstSubmitView.as_view(),
        name="bank-send-final-approval-first-v66",
    ),
    path(
        "api/finance/bank-send-final-approvals/<int:approval_id>/second-approve/",
        FinalApprovalSecondSubmitView.as_view(),
        name="bank-send-final-approval-second-v66",
    ),
    path(
        "api/finance/bank-send-dual-isolation-checks/",
        DualIsolationCheckListView.as_view(),
        name="bank-send-dual-isolation-check-list-v67",
    ),
    path(
        "api/finance/bank-send-production-release-reviews/",
        ProductionReleaseReviewListView.as_view(),
        name="bank-send-production-release-review-list-v67",
    ),
    path(
        "api/finance/bank-send-production-release-reviews/<int:review_id>/<str:stage>-review/",
        ProductionReleaseDecisionSubmitView.as_view(),
        name="bank-send-production-release-decision-v67",
    ),
    path(
        "api/finance/bank-send-execution-framework-reviews/",
        ExecutionFrameworkReviewListView.as_view(),
        name="bank-send-execution-framework-review-list-v68",
    ),
    path(
        "api/finance/bank-connector-adapter-reviews/",
        ConnectorAdapterReviewListView.as_view(),
        name="bank-connector-adapter-review-list-v68",
    ),
    path(
        "api/workflow/action-permissions/",
        include("workflow_runtime.urls"),
    ),
    path("api/workflow/", include("workflow_runtime.definition_urls")),
    path("api/pce/purchase-canary/", include("purchase_canary.urls")),
    path("api/pde/", include("pde.urls")),
    path("api/planning/", include("planning.urls")),
    path("api/sales/", include("sales.urls")),
    path("api/analytics/procurement-risks/", include("reconciliation.risk_urls")),
    path("api/analytics/operational-risks/", include("reconciliation.operational_risk_urls")),
    path("api/purchase/order/list", purchase_order_v6_list, name="purchase-order-v6-list"),
    path("api/purchase/order/detail", purchase_order_v6_detail, name="purchase-order-v6-detail"),
    path(
        "api/purchase/order/detail/<int:pk>",
        purchase_order_detail,
        name="purchase-order-detail",
    ),
    path("api/purchase/order/create", purchase_order_create, name="purchase-order-create"),
    path(
        "api/purchase/order/update/<int:pk>",
        purchase_order_update,
        name="purchase-order-update",
    ),
    path(
        "api/purchase/order/delete/<int:pk>",
        purchase_order_delete,
        name="purchase-order-delete",
    ),
    path("api/purchase/", include(router.urls)),
    path("api/<path:unmatched_path>", pce_api_not_found, name="pce-api-not-found"),
]

handler404 = "workflow_runtime.exception_handler.pce_not_found_handler"
handler500 = "workflow_runtime.exception_handler.pce_server_error_handler"
