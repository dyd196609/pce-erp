from django.urls import path

from .views import (
    DemandCreateView,
    MPSGenerateView,
    MRPGenerateView,
    PlanningFactsView,
    PlanningTraceView,
    PlanningValidationView,
    PurchasePlanConvertView,
    ProductionBatchFoundationPreviewView,
    RequirementCalculateView,
    SupplyPlanConfirmView,
)


urlpatterns = [
    path("production-batch-foundation/preview/", ProductionBatchFoundationPreviewView.as_view(), name="production-batch-foundation-preview"),
    path("facts/", PlanningFactsView.as_view(), name="planning-facts"),
    path("demands/", DemandCreateView.as_view(), name="planning-demand-create"),
    path("mps/runs/", MPSGenerateView.as_view(), name="planning-mps-generate"),
    path("mps/runs/<int:mps_run_id>/mrp/", MRPGenerateView.as_view(), name="planning-mrp-generate"),
    path("demands/<int:demand_id>/calculate/", RequirementCalculateView.as_view(), name="planning-calculate"),
    path("requirements/<int:requirement_id>/confirm-plan/", SupplyPlanConfirmView.as_view(), name="planning-confirm-plan"),
    path("requirements/<int:requirement_id>/validate/", PlanningValidationView.as_view(), name="planning-validate"),
    path("purchase-plans/<int:purchase_plan_id>/convert-to-purchase-request/", PurchasePlanConvertView.as_view(), name="planning-purchase-plan-convert"),
    path("trace/", PlanningTraceView.as_view(), name="planning-trace"),
]
