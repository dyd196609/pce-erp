from django.urls import path

from .views import (
    RiskReviewDetailView,
    RiskReviewEligibilityView,
    RiskReviewExecuteView,
    RiskReviewListView,
)


urlpatterns = [
    path("", RiskReviewListView.as_view(), name="payment-risk-review-list"),
    path("<int:review_id>", RiskReviewDetailView.as_view(), name="payment-risk-review-detail"),
    path("<int:review_id>/execute", RiskReviewExecuteView.as_view(), name="payment-risk-review-execute"),
    path("<int:review_id>/eligibility", RiskReviewEligibilityView.as_view(), name="payment-risk-review-eligibility"),
]
