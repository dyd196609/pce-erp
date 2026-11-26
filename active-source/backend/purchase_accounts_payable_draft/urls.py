from django.urls import path

from .views import (
    DraftBySourceView,
    DraftDetailView,
    DraftListView,
    GenerateView,
    GenerationResultView,
)

urlpatterns = [
    path("", DraftListView.as_view(), name="purchase-accounts-payable-draft-list"),
    path("generate", GenerateView.as_view(), name="purchase-accounts-payable-draft-generate"),
    path(
        "generation-results/<str:idempotency_key>",
        GenerationResultView.as_view(),
        name="purchase-accounts-payable-draft-generation-result",
    ),
    path(
        "by-source/<int:prepare_id>",
        DraftBySourceView.as_view(),
        name="purchase-accounts-payable-draft-by-source",
    ),
    path(
        "<int:draft_id>",
        DraftDetailView.as_view(),
        name="purchase-accounts-payable-draft-detail",
    ),
]
