from django.urls import path

from .views import (
    AccountsPayableDraftEligibilityView,
    GenerateView,
    GenerationResultView,
    InvoiceDataView,
    PrepareBySourceView,
    PrepareDetailView,
    PrepareListView,
    ValidateInvoiceDataView,
    ValidationIssuesView,
    ValidationResultView,
)

urlpatterns = [
    path("", PrepareListView.as_view(), name="purchase-invoice-prepare-list"),
    path("generate", GenerateView.as_view(), name="purchase-invoice-prepare-generate"),
    path(
        "generation-results/<str:idempotency_key>",
        GenerationResultView.as_view(),
        name="purchase-invoice-prepare-generation-result",
    ),
    path(
        "by-source/<int:reconciliation_id>",
        PrepareBySourceView.as_view(),
        name="purchase-invoice-prepare-by-source",
    ),
    path(
        "validation-results/<str:idempotency_key>",
        ValidationResultView.as_view(),
        name="purchase-invoice-validation-result",
    ),
    path(
        "<int:prepare_id>/invoice-data",
        InvoiceDataView.as_view(),
        name="purchase-invoice-data",
    ),
    path(
        "<int:prepare_id>/validate",
        ValidateInvoiceDataView.as_view(),
        name="purchase-invoice-validate",
    ),
    path(
        "<int:prepare_id>/validation-issues",
        ValidationIssuesView.as_view(),
        name="purchase-invoice-validation-issues",
    ),
    path(
        "<int:prepare_id>/accounts-payable-draft-eligibility",
        AccountsPayableDraftEligibilityView.as_view(),
        name="purchase-invoice-ap-draft-eligibility",
    ),
    path("<int:prepare_id>", PrepareDetailView.as_view(), name="purchase-invoice-prepare-detail"),
]
