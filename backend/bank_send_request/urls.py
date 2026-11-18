from django.urls import path
from .views import (
    BankSendRequestBlockedAttemptView, BankSendRequestCreateView,
    BankSendRequestListView, BankSendRequestRevalidateView,
)

urlpatterns = [
    path("", BankSendRequestListView.as_view(), name="bank-send-request-list"),
    path("from-gate/<int:gate_id>/create", BankSendRequestCreateView.as_view(), name="bank-send-request-create"),
    path("<int:request_id>/revalidate", BankSendRequestRevalidateView.as_view(), name="bank-send-request-revalidate"),
    path("canary-pool/blocked/<str:scenario_code>/attempt", BankSendRequestBlockedAttemptView.as_view(), name="bank-send-request-blocked-attempt"),
]
