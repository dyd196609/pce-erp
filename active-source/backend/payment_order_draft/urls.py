from django.urls import path

from .views import (
    EligibilityView,
    GenerateView,
    GenerationResultView,
    DraftDataResultView,
    DraftDataView,
    PrepareBySourceView,
    PrepareDetailView,
    PrepareListView,
    ReviewView,
    ReviewIssuesView,
    ReviewResultView,
)


urlpatterns = [
    path("", PrepareListView.as_view(), name="payment-order-draft-list"),
    path("generate", GenerateView.as_view(), name="payment-order-draft-generate"),
    path(
        "generation-results/<str:idempotency_key>",
        GenerationResultView.as_view(),
        name="payment-order-draft-generation-result",
    ),
    path(
        "draft-data-results/<str:idempotency_key>",
        DraftDataResultView.as_view(),
        name="payment-order-draft-data-result",
    ),
    path(
        "review-results/<str:idempotency_key>",
        ReviewResultView.as_view(),
        name="payment-order-draft-review-result",
    ),
    path(
        "by-source/<int:source_id>",
        PrepareBySourceView.as_view(),
        name="payment-order-draft-by-source",
    ),
    path(
        "<int:prepare_id>/draft-data",
        DraftDataView.as_view(),
        name="payment-order-draft-data",
    ),
    path(
        "<int:prepare_id>/review",
        ReviewView.as_view(),
        name="payment-order-draft-review",
    ),
    path(
        "<int:prepare_id>/review-issues",
        ReviewIssuesView.as_view(),
        name="payment-order-draft-review-issues",
    ),
    path(
        "<int:prepare_id>/payment-risk-review-eligibility",
        EligibilityView.as_view(),
        name="payment-order-draft-eligibility",
    ),
    path(
        "<int:prepare_id>",
        PrepareDetailView.as_view(),
        name="payment-order-draft-detail",
    ),
]
