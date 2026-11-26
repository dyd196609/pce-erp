from django.urls import path

from .views import (
    EligibilityView,
    GenerateView,
    GenerationResultView,
    InstructionDataResultView,
    InstructionDataView,
    PrepareBySourceView,
    PrepareDetailView,
    PrepareListView,
    ValidateView,
    ValidationIssuesView,
    ValidationResultView,
)


urlpatterns = [
    path("", PrepareListView.as_view(), name="payment-instruction-prepare-list"),
    path("generate", GenerateView.as_view(), name="payment-instruction-prepare-generate"),
    path(
        "generation-results/<str:idempotency_key>",
        GenerationResultView.as_view(),
        name="payment-instruction-prepare-generation-result",
    ),
    path(
        "instruction-data-results/<str:idempotency_key>",
        InstructionDataResultView.as_view(),
        name="payment-instruction-prepare-data-result",
    ),
    path(
        "validation-results/<str:idempotency_key>",
        ValidationResultView.as_view(),
        name="payment-instruction-prepare-validation-result",
    ),
    path(
        "by-source/<int:payment_request_id>",
        PrepareBySourceView.as_view(),
        name="payment-instruction-prepare-by-source",
    ),
    path(
        "<int:prepare_id>/instruction-data",
        InstructionDataView.as_view(),
        name="payment-instruction-prepare-data",
    ),
    path(
        "<int:prepare_id>/validate",
        ValidateView.as_view(),
        name="payment-instruction-prepare-validate",
    ),
    path(
        "<int:prepare_id>/validation-issues",
        ValidationIssuesView.as_view(),
        name="payment-instruction-prepare-validation-issues",
    ),
    path(
        "<int:prepare_id>/payment-order-prepare-eligibility",
        EligibilityView.as_view(),
        name="payment-instruction-prepare-eligibility",
    ),
    path("<int:prepare_id>", PrepareDetailView.as_view(), name="payment-instruction-prepare-detail"),
]
