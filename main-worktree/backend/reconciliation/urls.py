from django.urls import path

from .views import (
    BySourceView,
    CompleteReconciliationCheckView,
    GenerateView,
    GenerationResultView,
    ReconciliationDetailView,
    ReconciliationDifferencesView,
    ReconciliationEligibilityView,
    ReconciliationListView,
)

urlpatterns = [
    path("", ReconciliationListView.as_view(), name="purchase-reconciliation-list"),
    path("generate", GenerateView.as_view(), name="purchase-reconciliation-generate"),
    path("generation-results/<str:idempotency_key>", GenerationResultView.as_view(), name="purchase-reconciliation-result"),
    path("by-source/<path:source_key>", BySourceView.as_view(), name="purchase-reconciliation-by-source"),
    path("<int:reconciliation_id>", ReconciliationDetailView.as_view(), name="purchase-reconciliation-detail"),
    path("<int:reconciliation_id>/differences", ReconciliationDifferencesView.as_view(), name="purchase-reconciliation-differences"),
    path("<int:reconciliation_id>/invoice-prepare-eligibility", ReconciliationEligibilityView.as_view(), name="purchase-reconciliation-eligibility"),
    path("<int:reconciliation_id>/complete-check", CompleteReconciliationCheckView.as_view(), name="purchase-reconciliation-complete-check"),
]
