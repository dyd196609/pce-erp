from django.urls import path

from .views import (
    EligibilityView,
    GenerateView,
    GenerationResultView,
    PaymentDataResultView,
    PaymentDataView,
    PrepareBySourceView,
    PrepareDetailView,
    PrepareListView,
    ValidateView,
    ValidationIssuesView,
    ValidationResultView,
)


urlpatterns = [
    path("", PrepareListView.as_view(), name="payment-request-prepare-list"),
    path("generate", GenerateView.as_view(), name="payment-request-prepare-generate"),
    path(
        "generation-results/<str:idempotency_key>",
        GenerationResultView.as_view(),
        name="payment-request-prepare-generation-result",
    ),
    path(
        "payment-data-results/<str:idempotency_key>",
        PaymentDataResultView.as_view(),
        name="payment-request-prepare-payment-data-result",
    ),
    path(
        "validation-results/<str:idempotency_key>",
        ValidationResultView.as_view(),
        name="payment-request-prepare-validation-result",
    ),
    path(
        "by-source/<int:confirmation_prepare_id>",
        PrepareBySourceView.as_view(),
        name="payment-request-prepare-by-source",
    ),
    path(
        "<int:prepare_id>/payment-data",
        PaymentDataView.as_view(),
        name="payment-request-prepare-payment-data",
    ),
    path(
        "<int:prepare_id>/validate",
        ValidateView.as_view(),
        name="payment-request-prepare-validate",
    ),
    path(
        "<int:prepare_id>/validation-issues",
        ValidationIssuesView.as_view(),
        name="payment-request-prepare-validation-issues",
    ),
    path(
        "<int:prepare_id>/payment-request-eligibility",
        EligibilityView.as_view(),
        name="payment-request-prepare-eligibility",
    ),
    path(
        "<int:prepare_id>",
        PrepareDetailView.as_view(),
        name="payment-request-prepare-detail",
    ),
]
