from django.urls import path

from .risk_views import ProcurementRiskActionView, ProcurementRiskDirectoryView

urlpatterns = [
    path("<str:order_no>/", ProcurementRiskDirectoryView.as_view(), name="enterprise-procurement-risk-directory"),
    path("<str:order_no>/<int:risk_id>/<slug:action>/", ProcurementRiskActionView.as_view(),
        name="enterprise-procurement-risk-action"),
]
