from django.urls import path
from .views import (
    CanaryContextView,
    CanaryOperationDataView,
    CanaryScenarioListView,
    PurchaseInquiryCanaryRuntimeView,
    SupplierQuotationCanaryRuntimeView,
    QuoteComparisonCanaryRuntimeView,
    PriceApprovalCanaryRuntimeView,
)

urlpatterns = [
    path("context", CanaryContextView.as_view(), name="purchase-canary-context"),
    path("scenarios", CanaryScenarioListView.as_view(), name="purchase-canary-scenarios"),
    path("operation-data", CanaryOperationDataView.as_view(), name="purchase-canary-operation-data"),
    path("purchase-inquiry-runtime", PurchaseInquiryCanaryRuntimeView.as_view(), name="purchase-inquiry-canary-runtime"),
    path("supplier-quotation-runtime", SupplierQuotationCanaryRuntimeView.as_view(), name="supplier-quotation-canary-runtime"),
    path("quote-comparison-runtime", QuoteComparisonCanaryRuntimeView.as_view(), name="quote-comparison-canary-runtime"),
    path("price-approval-runtime", PriceApprovalCanaryRuntimeView.as_view(), name="price-approval-canary-runtime"),
]
