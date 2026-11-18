from django.urls import path

from .views import (
    GenerateView,
    GenerationResultView,
    PrepareBySourceView,
    PrepareDetailView,
    PrepareListView,
    ValidateView,
)

urlpatterns = [
    path("", PrepareListView.as_view(), name="payable-confirmation-prepare-list"),
    path("validate", ValidateView.as_view(), name="payable-confirmation-prepare-validate"),
    path("generate", GenerateView.as_view(), name="payable-confirmation-prepare-generate"),
    path(
        "generation-results/<str:idempotency_key>",
        GenerationResultView.as_view(),
        name="payable-confirmation-prepare-generation-result",
    ),
    path(
        "by-source/<int:draft_id>",
        PrepareBySourceView.as_view(),
        name="payable-confirmation-prepare-by-source",
    ),
    path(
        "<int:prepare_id>",
        PrepareDetailView.as_view(),
        name="payable-confirmation-prepare-detail",
    ),
]
