from django.urls import path

from .views import (
    BankSendExecutionGateCanaryBlockedAttemptView,
    BankSendExecutionGateCreateView,
    BankSendExecutionGateListView,
)


urlpatterns = [
    path(
        "",
        BankSendExecutionGateListView.as_view(),
        name="bank-send-execution-gate-list",
    ),
    path(
        "from-task/<int:task_id>/create",
        BankSendExecutionGateCreateView.as_view(),
        name="bank-send-execution-gate-create",
    ),
    path(
        "canary-pool/blocked/<str:scenario_code>/attempt",
        BankSendExecutionGateCanaryBlockedAttemptView.as_view(),
        name="bank-send-execution-gate-canary-blocked-attempt",
    ),
]
