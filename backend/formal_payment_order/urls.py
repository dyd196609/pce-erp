from django.urls import path

from .views import (
    FormalPaymentOrderApprovalHistoryView,
    FormalPaymentOrderApproveView,
    FormalPaymentOrderBySourceView,
    FormalPaymentOrderDetailView,
    FormalPaymentOrderFreezeView,
    FormalPaymentOrderGenerateView,
    FormalPaymentOrderGenerationResultView,
    FormalPaymentOrderListView,
    FormalPaymentOrderSubmitView,
)


urlpatterns = [
    path("", FormalPaymentOrderListView.as_view(), name="formal-payment-order-list"),
    path("generate", FormalPaymentOrderGenerateView.as_view(), name="formal-payment-order-generate"),
    path("by-source/<int:source_id>", FormalPaymentOrderBySourceView.as_view(), name="formal-payment-order-by-source"),
    path("generation-results/<str:idempotency_key>", FormalPaymentOrderGenerationResultView.as_view(), name="formal-payment-order-generation-result"),
    path("<int:order_id>/submit", FormalPaymentOrderSubmitView.as_view(), name="formal-payment-order-submit"),
    path("<int:order_id>/approve", FormalPaymentOrderApproveView.as_view(), name="formal-payment-order-approve"),
    path("<int:order_id>/freeze", FormalPaymentOrderFreezeView.as_view(), name="formal-payment-order-freeze"),
    path("<int:order_id>/approval-history", FormalPaymentOrderApprovalHistoryView.as_view(), name="formal-payment-order-approval-history"),
    path("<int:order_id>", FormalPaymentOrderDetailView.as_view(), name="formal-payment-order-detail"),
]
