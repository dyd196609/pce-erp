from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SupplierViewSet, PurchaseOrderViewSet, ReportViewSet
from .scm_page_facts import ScmStandardPageFactsView
from .purchase_inquiry_api import PurchaseInquiryFromRequestView
from .supplier_quotation_api import SupplierQuotationSaveView, SupplierQuotationSubmitView
from .comparison_registration_api import QuoteComparisonRegistrationView
from .price_approval_preparation_api import (
    PriceApprovalPreparationListCreateView,
    PriceApprovalPreparationTransitionView,
)
from .scm_runtime_actions import ScmRuntimeActionView, PurchaseOrderGateCreationView, ProcurementModeRoutingView
from .purchase_request_api import PurchaseRequestReferenceView, PurchaseRequestViewSet
from .purchase_fulfillment_api import PurchaseOrderFulfillmentFactsView
from .inventory_facts_api import (
    FormalInventoryFactsView,
    FormalPayableCheckFactsView,
    FormalPurchaseReceiptFactsView,
    FormalQualityFactsView,
)

router = DefaultRouter()
router.register(r"suppliers", SupplierViewSet)
router.register(r"purchase_orders", PurchaseOrderViewSet)
router.register(r"purchase-requests", PurchaseRequestViewSet, basename="purchase-request")

from .order_stock_allocation_views import OrderStockAllocateView, OrderStockReleaseView
from .material_allocation_api import MaterialAllocationView, RawSourceDirectoryView
from .material_preparation_api import MaterialPreparationView
from .material_issue_api import MaterialIssueView,MaterialReceiptView

urlpatterns = [
    path('scm-runtime-actions/<str:action>/sources/', RawSourceDirectoryView.as_view(), name='raw-source-directory'),
    path('material-issues/', MaterialIssueView.as_view(), name='production-material-issue'),
    path('material-receipts/', MaterialReceiptView.as_view(), name='production-material-receipt'),
    path('material-preparations/', MaterialPreparationView.as_view(), name='production-material-preparation'),
    path('material-stock-allocations/', MaterialAllocationView.as_view(), name='production-material-stock-allocation'),
    path("quote-comparisons/register/", QuoteComparisonRegistrationView.as_view(), name="quote-comparison-register"),
    path('order-lines/<int:item_id>/stock-allocations/', OrderStockAllocateView.as_view()),
    path('order-stock-allocations/<int:allocation_id>/release/', OrderStockReleaseView.as_view()),
    path("formal-inventory-facts/", FormalInventoryFactsView.as_view(), name="formal-inventory-facts"),
    path("formal-quality-facts/", FormalQualityFactsView.as_view(), name="formal-quality-facts"),
    path("formal-purchase-receipt-facts/", FormalPurchaseReceiptFactsView.as_view(), name="formal-purchase-receipt-facts"),
    path("formal-payable-check-facts/", FormalPayableCheckFactsView.as_view(), name="formal-payable-check-facts"),
    path(
        "purchase-order-fulfillment/<int:order_id>/",
        PurchaseOrderFulfillmentFactsView.as_view(),
        name="purchase-order-fulfillment-facts",
    ),
    path("procurement-mode-routing/", ProcurementModeRoutingView.as_view(), name="procurement-mode-routing"),
    path(
        "purchase-order-gate-creation/",
        PurchaseOrderGateCreationView.as_view(),
        name="purchase-order-gate-creation",
    ),
    path("price-approval-preparations/", PriceApprovalPreparationListCreateView.as_view(), name="price-approval-preparation-list-create"),
    path("price-approval-preparations/<int:preparation_id>/transition/", PriceApprovalPreparationTransitionView.as_view(), name="price-approval-preparation-transition"),
    path("supplier-quotations/save/", SupplierQuotationSaveView.as_view(), name="supplier-quotation-save"),
    path("supplier-quotations/<int:quotation_id>/submit/", SupplierQuotationSubmitView.as_view(), name="supplier-quotation-submit"),
    path(
        "purchase-inquiries/from-request/<int:request_id>/",
        PurchaseInquiryFromRequestView.as_view(),
        name="purchase-inquiry-from-request",
    ),
    path(
        "purchase-request-references/<str:reference_type>/",
        PurchaseRequestReferenceView.as_view(),
        name="purchase-request-reference",
    ),
    path(
        "scm-runtime-actions/<str:action>/<int:object_id>/",
        ScmRuntimeActionView.as_view(),
        name="scm-runtime-action",
    ),
    path(
        "scm-page-facts/<str:page_code>/",
        ScmStandardPageFactsView.as_view(),
        name="scm-standard-page-facts",
    ),
    path("", include(router.urls)),
    path(
        "reports/",
        include(
            [
                path(
                    "department-purchase/",
                    ReportViewSet.as_view({"get": "department_purchase_report"}),
                    name="report-department-purchase",
                ),
                path(
                    "buyer-performance/",
                    ReportViewSet.as_view({"get": "buyer_performance_report"}),
                    name="report-buyer-performance",
                ),
                path(
                    "supplier-performance/",
                    ReportViewSet.as_view({"get": "supplier_performance_report"}),
                    name="report-supplier-performance",
                ),
            ]
        ),
    ),
]
