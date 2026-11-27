from django.urls import path

from .operational_risk_views import OperationalRiskActionView, OperationalRiskDirectoryView


urlpatterns = [
    path("<slug:kind>/", OperationalRiskDirectoryView.as_view(), name="operational-risk-directory"),
    path("<slug:kind>/<int:risk_id>/<slug:action>/", OperationalRiskActionView.as_view(),
         name="operational-risk-action"),
]
