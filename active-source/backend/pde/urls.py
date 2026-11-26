from .test_business_bom_views import TestBusinessBomHandoffView
from .design_approval_views import DesignRevisionApprovalView
from .test_calculation_preview import TestCalculationPreviewView
from .test_calculation_persistence import TestCalculationPersistenceView
from django.urls import path
from .calculation_batch_views import EngineeringCalculationBatchView
from .engineering_workload_summary_views import EngineeringWorkloadCalculationTraceView
from .order_review_views import ProductionFeasibilityReviewView
from .plan_step_version_handoff_views import PlanStepVersionHandoffView
from .manufacturing_admission_read_views import ManufacturingAdmissionHistoryView, MrpInputSourceReadView

from .views import (
    BomVersionListView,
    EngineeringChangeListView,
    EngineeringDocumentListView,
    EngineeringDocumentVersionReviewView,
    EngineeringDocumentVersionReleaseView,
    ProductBomListView,
    ProductDefinitionListView,
    ProductEngineeringReadinessListView,
    ProductManufacturingOutputListView,
    ManufacturingOutputGenerateView,
    ManufacturingOutputReleaseView,
    ProductRequirementListView,
    ProductVersionListView,
    ProductVersionManagementView,
    RoutingListView,
    RoutingVersionListView,
    RoutingVersionReviewView,
    RoutingVersionReleaseView,
    RoutingVersionSuccessorView,
    RoutingStepApplicabilityView,
    RoutingManualApplicabilityDecisionView,
    ProductionFoundationA1View,
    EngineeringLifecycleView,
    EngineeringRuleEffectivityCorrectionView,
    EngineeringCalculationTraceView,
    EngineeringCalculationReadinessView,
    EngineeringCalculationExecuteView,
    FormalEngineeringContinuationView,
    EngineeringCalculationVersionContinuationView,
    OrderEngineeringConditionPreflightView,
    OrderEngineeringCalculationValidateView,
    EngineeringMethodTrialView,
    OrderEngineeringBomPreviewView,
    OrderEngineeringBomGenerateView,
    Wave2ManufacturingFoundationView,
)
from .foundation_import_preview_views import FoundationImportPreviewView
from .test_engineering_routing_views import TestEngineeringRoutingView
from .daily_capacity_views import DailyCapacityDatePreviewView
from .order_engineering_intake_views import OrderEngineeringIntakeView
from .formal_import_views import (
    FormalImportCommitView, FormalImportCurrentActorContextView,
    FormalImportPreviewView, FormalImportTemplateView,
)
from .product_design_import_views import (
    ProductDesignExportView, ProductDesignImportCommitView, ProductDesignImportPreviewView,
    ProductDesignImportTemplateView,
)

urlpatterns = [
    path("test-business-bom-handoff/",TestBusinessBomHandoffView.as_view(),name="test-business-bom-handoff"),
    path("design-revision-approvals/", DesignRevisionApprovalView.as_view(), name="pde-design-revision-approvals"),
    path("plan-step-version-handoffs/", PlanStepVersionHandoffView.as_view(), name="pde-plan-step-version-handoffs"),
    path("aps/daily-capacity/date-preview/", DailyCapacityDatePreviewView.as_view(), name="pde-aps-daily-capacity-date-preview"),
    path("manufacturing-admissions/", ManufacturingAdmissionHistoryView.as_view(), name="pde-manufacturing-admission-history"),
    path("mrp-input-preparation/", MrpInputSourceReadView.as_view(), name="pde-mrp-input-source-read"),
    path("a1-engineering/calculations/batch-reuse/", EngineeringCalculationBatchView.as_view(), name="pde-engineering-calculation-batch-reuse"),
    path("product-requirements/", ProductRequirementListView.as_view(), name="pde-product-requirements"),
    path("production-feasibility-reviews/", ProductionFeasibilityReviewView.as_view(), name="pde-production-feasibility-reviews"),
    path("product-definitions/", ProductDefinitionListView.as_view(), name="pde-product-definitions"),
    path("product-definitions/import-template/", ProductDesignImportTemplateView.as_view(), name="pde-product-design-import-template"),
    path("product-definitions/import-preview/", ProductDesignImportPreviewView.as_view(), name="pde-product-design-import-preview"),
    path("product-definitions/import-commit/", ProductDesignImportCommitView.as_view(), name="pde-product-design-import-commit"),
    path("product-definitions/export/", ProductDesignExportView.as_view(), name="pde-product-design-export"),
    path("product-boms/", ProductBomListView.as_view(), name="pde-product-boms"),
    path("routings/", RoutingListView.as_view(), name="pde-routings"),
    path('routings/test-engineering-binding/', TestEngineeringRoutingView.as_view(), name='pde-test-engineering-routing-binding'),
    path("engineering-documents/", EngineeringDocumentListView.as_view(), name="pde-engineering-documents"),
    path("engineering-document-versions/<int:object_id>/review/", EngineeringDocumentVersionReviewView.as_view(), name="pde-engineering-document-version-review"),
    path("engineering-document-versions/<int:object_id>/release/", EngineeringDocumentVersionReleaseView.as_view(), name="pde-engineering-document-version-release"),
    path("product-versions/", ProductVersionListView.as_view(), name="pde-product-versions"),
    path("product-version-management/", ProductVersionManagementView.as_view(), name="pde-product-version-management"),
    path("bom-versions/", BomVersionListView.as_view(), name="pde-bom-versions"),
    path("routing-versions/", RoutingVersionListView.as_view(), name="pde-routing-versions"),
    path("routing-versions/<int:object_id>/review/", RoutingVersionReviewView.as_view(), name="pde-routing-version-review"),
    path("routing-versions/<int:object_id>/release/", RoutingVersionReleaseView.as_view(), name="pde-routing-version-release"),
    path("routing-versions/<int:object_id>/successor/", RoutingVersionSuccessorView.as_view(), name="pde-routing-version-successor"),
    path("routing-versions/<int:object_id>/manual-applicability/", RoutingManualApplicabilityDecisionView.as_view(), name="pde-routing-version-manual-applicability"),
    path("routing-steps/<int:object_id>/applicability/", RoutingStepApplicabilityView.as_view(), name="pde-routing-step-applicability"),
    path("engineering-changes/", EngineeringChangeListView.as_view(), name="pde-engineering-changes"),
    path("manufacturing-outputs/", ProductManufacturingOutputListView.as_view(), name="pde-manufacturing-outputs"),
    path("manufacturing-outputs/generate/", ManufacturingOutputGenerateView.as_view(), name="pde-manufacturing-output-generate"),
    path("manufacturing-outputs/<int:pk>/release/", ManufacturingOutputReleaseView.as_view(), name="pde-manufacturing-output-release"),
    path("engineering-readiness/", ProductEngineeringReadinessListView.as_view(), name="pde-engineering-readiness"),
    path("engineering-readiness/order-engineering-intake/", OrderEngineeringIntakeView.as_view(), name="pde-order-engineering-intake"),
    path("a1-foundation/", ProductionFoundationA1View.as_view(), name="pde-a1-foundation"),
    path("wave2-manufacturing-foundation/", Wave2ManufacturingFoundationView.as_view(), name="pde-wave2-manufacturing-foundation"),
    path("a1-foundation/<slug:entity>/", ProductionFoundationA1View.as_view(), name="pde-a1-foundation-entity"),
    path("a1-foundation/<slug:entity>/<int:object_id>/", ProductionFoundationA1View.as_view(), name="pde-a1-foundation-object"),
    path("foundation-import-preview/", FoundationImportPreviewView.as_view(), name="pde-foundation-import-preview"),
    path("formal-import/<slug:entity>/template/", FormalImportTemplateView.as_view(), name="pde-formal-import-template"),
    path("formal-import/<slug:entity>/preview/", FormalImportPreviewView.as_view(), name="pde-formal-import-preview"),
    path("formal-import/<slug:entity>/commit/", FormalImportCommitView.as_view(), name="pde-formal-import-commit"),
    path("formal-import/current-context/", FormalImportCurrentActorContextView.as_view(), name="pde-formal-import-current-context"),
    path("a1-engineering/<slug:entity>/<int:object_id>/transition/", EngineeringLifecycleView.as_view(), name="pde-a1-engineering-transition"),
    path("a1-engineering/rules/<int:object_id>/correct-effectivity/", EngineeringRuleEffectivityCorrectionView.as_view(), name="pde-engineering-rule-effectivity-correction"),
    path("a1-engineering/calculations/", EngineeringCalculationTraceView.as_view(), name="pde-engineering-calculation-list"),
    path("a1-engineering/calculations/readiness/", EngineeringCalculationReadinessView.as_view(), name="pde-engineering-calculation-readiness"),
    path("a1-engineering/calculations/<int:object_id>/", EngineeringWorkloadCalculationTraceView.as_view(), name="pde-engineering-calculation-detail"),
    path("a1-engineering/calculations/execute/", EngineeringCalculationExecuteView.as_view(), name="pde-engineering-calculation-execute"),
    path("a1-engineering/calculations/test-preview/", TestCalculationPreviewView.as_view(), name="pde-engineering-test-preview"),
    path("a1-engineering/calculations/test-records/", TestCalculationPersistenceView.as_view(), name="pde-engineering-test-records"),
    path("a1-engineering/calculations/formal-continuation/", FormalEngineeringContinuationView.as_view(), name="pde-engineering-formal-continuation"),
    path('a1-engineering/calculations/version-continuation/preview/',EngineeringCalculationVersionContinuationView.as_view(),
        {'continuation_action':'preview'},name='pde-engineering-version-continuation-preview'),
    path('a1-engineering/calculations/version-continuation/execute/',EngineeringCalculationVersionContinuationView.as_view(),
        {'continuation_action':'execute'},name='pde-engineering-version-continuation-execute'),
    path("a1-engineering/order-calculation/condition-preflight/", OrderEngineeringConditionPreflightView.as_view(), name="pde-order-engineering-condition-preflight"),
    path("a1-engineering/order-calculation/validate/", OrderEngineeringCalculationValidateView.as_view(), name="pde-order-engineering-calculation-validate"),
    path("a1-engineering/order-calculation/method-trial/", EngineeringMethodTrialView.as_view(), name="pde-engineering-method-trial"),
    path("a1-engineering/calculations/<int:calculation_id>/bom-preview/", OrderEngineeringBomPreviewView.as_view(), name="pde-order-engineering-bom-preview"),
    path("a1-engineering/calculations/<int:calculation_id>/bom-generate/", OrderEngineeringBomGenerateView.as_view(), name="pde-order-engineering-bom-generate"),
]

from .foundation_routing_views import FoundationRoutingControlView
from .order_routing_execution_views import OrderRoutingExecutionView
urlpatterns += [
    path('a1-foundation/routings/<int:object_id>/initial-version/',FoundationRoutingControlView.as_view(),kwargs={'action':'initial-version'},name='foundation-routing-initial-version'),
    path('a1-foundation/routings/<int:object_id>/versions/',FoundationRoutingControlView.as_view(),name='foundation-routing-versions'),
    path('a1-foundation/routing-versions/<int:object_id>/<slug:action>/',FoundationRoutingControlView.as_view(),name='foundation-routing-version-action'),
    path('a1-foundation/routing-steps/<int:object_id>/<slug:action>/',FoundationRoutingControlView.as_view(),name='foundation-routing-step-action'),
    path('order-routing-execution/',OrderRoutingExecutionView.as_view(),name='pde-order-routing-execution'),
]
