from django.urls import path

from .views import (
    ApprovalHistoryView,
    ApprovalResultView,
    ApprovalRouteView,
    ApprovalTasksView,
    ApproveView,
    EligibilityView,
    GenerateView,
    GenerationResultView,
    PaymentRequestBySourceView,
    PaymentRequestDetailView,
    PaymentRequestListView,
    RejectView,
    RejectionResultView,
    SubmissionResultView,
    SubmitView,
)


urlpatterns = [
    path("", PaymentRequestListView.as_view(), name="payment-request-list"),
    path("generate", GenerateView.as_view(), name="payment-request-generate"),
    path("by-source/<int:prepare_id>", PaymentRequestBySourceView.as_view(), name="payment-request-by-source"),
    path("generation-results/<str:idempotency_key>", GenerationResultView.as_view(), name="payment-request-generation-result"),
    path("submission-results/<str:idempotency_key>", SubmissionResultView.as_view(), name="payment-request-submission-result"),
    path("approval-results/<str:idempotency_key>", ApprovalResultView.as_view(), name="payment-request-approval-result"),
    path("rejection-results/<str:idempotency_key>", RejectionResultView.as_view(), name="payment-request-rejection-result"),
    path("<int:request_id>", PaymentRequestDetailView.as_view(), name="payment-request-detail"),
    path("<int:request_id>/submit", SubmitView.as_view(), name="payment-request-submit"),
    path("<int:request_id>/tasks/<int:task_id>/approve", ApproveView.as_view(), name="payment-request-approve"),
    path("<int:request_id>/tasks/<int:task_id>/reject", RejectView.as_view(), name="payment-request-reject"),
    path("<int:request_id>/approval-route", ApprovalRouteView.as_view(), name="payment-request-approval-route"),
    path("<int:request_id>/approval-tasks", ApprovalTasksView.as_view(), name="payment-request-approval-tasks"),
    path("<int:request_id>/approval-history", ApprovalHistoryView.as_view(), name="payment-request-approval-history"),
    path("<int:request_id>/payment-instruction-prepare-eligibility", EligibilityView.as_view(), name="payment-request-instruction-eligibility"),
]

