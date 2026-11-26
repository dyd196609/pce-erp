from django.urls import path

from .views import (
    ActionPermissionContractView,
    ActionPermissionMatrixView,
    ActionPermissionValidationView,
    AcceptanceObservabilityView,
    CanaryActorSessionView,
)


urlpatterns = [
    path(
        "acceptance-observability/<str:page_code>",
        AcceptanceObservabilityView.as_view(),
        name="acceptance-observability",
    ),
    path("", ActionPermissionMatrixView.as_view(), name="action-permission-matrix"),
    path(
        "contract",
        ActionPermissionContractView.as_view(),
        name="action-permission-contract",
    ),
    path(
        "validate",
        ActionPermissionValidationView.as_view(),
        name="action-permission-validate",
    ),
    path(
        "canary-session",
        CanaryActorSessionView.as_view(),
        name="action-permission-canary-session",
    ),
]
