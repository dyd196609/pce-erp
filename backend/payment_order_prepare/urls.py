from django.urls import path

from .views import (
    EligibilityView,
    GenerateView,
    GenerationResultView,
    OrderDataResultView,
    OrderDataView,
    PrepareBySourceView,
    PrepareDetailView,
    PrepareListView,
    ValidateView,
    ValidationIssuesView,
    ValidationResultView,
)


urlpatterns = [
    path("", PrepareListView.as_view(), name="payment-order-prepare-list"),
    path("generate", GenerateView.as_view(), name="payment-order-prepare-generate"),
    path(
        "generation-results/<str:idempotency_key>",
        GenerationResultView.as_view(),
        name="payment-order-prepare-generation-result",
    ),
    path(
        "order-data-results/<str:idempotency_key>",
        OrderDataResultView.as_view(),
        name="payment-order-prepare-data-result",
    ),
    path(
        "validation-results/<str:idempotency_key>",
        ValidationResultView.as_view(),
        name="payment-order-prepare-validation-result",
    ),
    path(
        "by-source/<int:source_id>",
        PrepareBySourceView.as_view(),
        name="payment-order-prepare-by-source",
    ),
    path(
        "<int:prepare_id>/order-data",
        OrderDataView.as_view(),
        name="payment-order-prepare-data",
    ),
    path(
        "<int:prepare_id>/validate",
        ValidateView.as_view(),
        name="payment-order-prepare-validate",
    ),
    path(
        "<int:prepare_id>/validation-issues",
        ValidationIssuesView.as_view(),
        name="payment-order-prepare-validation-issues",
    ),
    path(
        "<int:prepare_id>/payment-order-draft-eligibility",
        EligibilityView.as_view(),
        name="payment-order-prepare-eligibility",
    ),
    path(
        "<int:prepare_id>",
        PrepareDetailView.as_view(),
        name="payment-order-prepare-detail",
    ),
]
