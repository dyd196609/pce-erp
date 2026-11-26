from django.urls import path

from .views import (
    ProductionIsolationGateListView,
    RecoveryResolveView,
    SimulationAuditListView,
    SimulationCreateView,
    SimulationListView,
)


urlpatterns = [
    path("", SimulationListView.as_view(), name="bank-send-simulation-list"),
    path(
        "from-request/<int:request_id>/create",
        SimulationCreateView.as_view(),
        name="bank-send-simulation-create",
    ),
    path(
        "recoveries/<int:recovery_id>/resolve",
        RecoveryResolveView.as_view(),
        name="bank-send-simulation-recovery-resolve",
    ),
    path(
        "audits",
        SimulationAuditListView.as_view(),
        name="bank-send-simulation-audit-list",
    ),
    path(
        "isolation-gates",
        ProductionIsolationGateListView.as_view(),
        name="bank-send-production-isolation-gate-list",
    ),
]
