from django.urls import path

from .views import (
    BankMessagePreviewDetailView,
    BankMessagePreviewGenerateView,
    BankSendEligibilityView,
    BankSendGateView,
    BankSendPreparationDetailView,
    BankSendPreparationListView,
)


urlpatterns = [
    path(
        "",
        BankSendPreparationListView.as_view(),
        name="bank-send-preparation-list",
    ),
    path(
        "<int:preparation_id>",
        BankSendPreparationDetailView.as_view(),
        name="bank-send-preparation-detail",
    ),
    path(
        "<int:preparation_id>/eligibility",
        BankSendEligibilityView.as_view(),
        name="bank-send-eligibility",
    ),
    path(
        "<int:preparation_id>/gate",
        BankSendGateView.as_view(),
        name="bank-send-gate",
    ),
    path(
        "<int:preparation_id>/preview",
        BankMessagePreviewDetailView.as_view(),
        name="bank-message-preview-detail",
    ),
    path(
        "<int:preparation_id>/preview/generate",
        BankMessagePreviewGenerateView.as_view(),
        name="bank-message-preview-generate",
    ),
]

