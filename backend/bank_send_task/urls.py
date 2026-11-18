from django.urls import path

from .views import (
    BankSendTaskCreateView,
    BankSendTaskCanaryPoolReplenishView,
    BankSendTaskCanaryBlockedAttemptView,
    BankSendTaskDetailView,
    BankSendTaskListView,
)


urlpatterns = [
    path("", BankSendTaskListView.as_view(), name="bank-send-task-list"),
    path(
        "<int:task_id>",
        BankSendTaskDetailView.as_view(),
        name="bank-send-task-detail",
    ),
    path(
        "from-preparation/<int:preparation_id>/create",
        BankSendTaskCreateView.as_view(),
        name="bank-send-task-create",
    ),
    path(
        "canary-pool/replenish",
        BankSendTaskCanaryPoolReplenishView.as_view(),
        name="bank-send-task-canary-pool-replenish",
    ),
    path(
        "canary-pool/blocked/<str:scenario_code>/attempt",
        BankSendTaskCanaryBlockedAttemptView.as_view(),
        name="bank-send-task-canary-blocked-attempt",
    ),
]
