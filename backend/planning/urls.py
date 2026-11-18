from .enterprise_work_summary_views import EnterpriseWorkSummaryView
from .operation_handover_views import OperationHandoverFactsView, OperationHandoverPrepareView, OperationHandoverDispatchView, OperationHandoverReceiveView, OperationHandoverCancelView, OperationHandoverForwardView, OperationHandoverReturnView, OperationHandoverInputConfirmView, OperationHandoverRangeReleaseView, OperationHandoverExceptionView, OperationHandoverExceptionConfirmView
from .operation_output_views import OperationOutputFactsView, OperationOutputConfirmView, OperationOutputExcessReportView, OperationOutputExcessReviewView, OperationOutputCorrectionView
from .operation_completion_views import OperationCompletionFactsView, OperationCompletionRequestView, OperationCompletionApproveView, OperationCompletionWithdrawReplaceView
from django.urls import path
from .finished_goods_views import FinishedGoodsFactsView,FinishedGoodsPrepareView,FinishedGoodsDispatchView,FinishedGoodsCancelView,FinishedGoodsReceiveView
from .operation_handover_views import OperationHandoverRangeReceiveView
from .operation_report_views import OperationReportFactsView, OperationReportView, OperationExecutionConfirmationView
from .mes_execution_entry import MesExecutionEntryView

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


from .operation_completion_views import OperationCompletionDirectoryView

from .coverage_views import OrderManufacturingBatchView, OrderManufacturingBatchCancelView

urlpatterns = [
    path('order-lines/<int:item_id>/manufacturing-batches/', OrderManufacturingBatchView.as_view()),
    path('order-lines/<int:item_id>/manufacturing-batches/<int:demand_id>/cancel/', OrderManufacturingBatchCancelView.as_view()),
    path('operation-completions/directory/', OperationCompletionDirectoryView.as_view()),
    path('enterprise-work-summary/',EnterpriseWorkSummaryView.as_view()),
    path('mes-test-entry/',MesExecutionEntryView.as_view()),
    path('finished-goods-handovers/',FinishedGoodsFactsView.as_view()),
    path('finished-goods-handovers/prepare/',FinishedGoodsPrepareView.as_view()),
    path('finished-goods-handovers/<int:transfer_id>/dispatch/',FinishedGoodsDispatchView.as_view()),
    path('finished-goods-handovers/<int:transfer_id>/cancel/',FinishedGoodsCancelView.as_view()),
    path('finished-goods-handovers/<int:transfer_id>/receive/',FinishedGoodsReceiveView.as_view()),
    path('operation-handovers/ranges/receive/',OperationHandoverRangeReceiveView.as_view()),
    path('operation-handovers/', OperationHandoverFactsView.as_view(), name='planning-operation-handover-facts'),
    path('operation-handovers/prepare/', OperationHandoverPrepareView.as_view()),
    path('operation-handovers/forward/', OperationHandoverForwardView.as_view()),
    path('operation-handovers/return/', OperationHandoverReturnView.as_view()),
    path('operation-handovers/inputs/confirm/', OperationHandoverInputConfirmView.as_view()),
    path('operation-handovers/ranges/release/', OperationHandoverRangeReleaseView.as_view()),
    path('operation-handovers/exceptions/', OperationHandoverExceptionView.as_view()),
    path('operation-handovers/exceptions/<int:exception_id>/resolve/', OperationHandoverExceptionConfirmView.as_view()),
    path('operation-handovers/<int:handover_id>/dispatch/', OperationHandoverDispatchView.as_view()),
    path('operation-handovers/<int:handover_id>/receive/', OperationHandoverReceiveView.as_view()),
    path('operation-handovers/<int:handover_id>/cancel/', OperationHandoverCancelView.as_view()),
    path('operation-outputs/', OperationOutputFactsView.as_view(), name='planning-operation-output-facts'),
    path('operation-outputs/confirm/', OperationOutputConfirmView.as_view()),
    path('operation-outputs/excess-reports/', OperationOutputExcessReportView.as_view()),
    path('operation-outputs/excess-reports/<int:output_id>/review/', OperationOutputExcessReviewView.as_view()),
    path('operation-outputs/corrections/', OperationOutputCorrectionView.as_view()),
    path('operation-completions/<int:task_id>/withdraw-and-replace/', OperationCompletionWithdrawReplaceView.as_view()),
    path("operation-completions/", OperationCompletionFactsView.as_view(), name="planning-operation-completion-facts"),
    path("operation-completions/<int:task_id>/request/", OperationCompletionRequestView.as_view(), name="planning-operation-completion-request"),
    path("operation-completions/<int:task_id>/approve/", OperationCompletionApproveView.as_view(), name="planning-operation-completion-approve"),
    path('operation-reports/',OperationReportFactsView.as_view()),
    path('operation-reports/<int:task_id>/report/',OperationReportView.as_view()),
    path('operation-reports/<int:task_id>/confirm-execution/',OperationExecutionConfirmationView.as_view()),
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


# Restored native formal HTTP entries; TEST URLs preserved.
from .work_order_reception_views import ProductionWorkOrderReceptionView
from .work_order_execution_views import ProductionWorkOrderGenerateView, ProductionWorkOrderReleaseView
from .formal_scheduling_views import FormalSchedulingView, FormalSchedulingAdmissionView, FormalSchedulingCapacityScopeView, FormalSchedulingCancelView
from .views import ProductionPlanStartDateView
from .work_order_workshop_receipt_views import ProductionWorkOrderWorkshopReceptionView, ProductionWorkOrderWorkshopReceiveView
from .workshop_task_views import WorkshopTaskFactsView, WorkshopTaskDraftView, WorkshopTaskDispatchView
from .operation_start_views import OperationStartFactsView, OperationStartView
from .operation_resource_handoff_views import ResourceHandoffFactsView, ResourceHandoffConfirmView
from .operation_resource_selection_views import OperationResourceFactsView, OperationResourceSelectView, OperationResourceReceiveView
urlpatterns += [
path("operation-resources/", OperationResourceFactsView.as_view(), name="planning-operation-resource-facts"),
path("operation-resources/<int:operation_id>/select/", OperationResourceSelectView.as_view(), name="planning-operation-resource-select"),
path("operation-resources/<int:operation_id>/receive/", OperationResourceReceiveView.as_view(), name="planning-operation-resource-receive"),
path("resource-handoffs/", ResourceHandoffFactsView.as_view(), name="planning-resource-handoff-facts"),
path("resource-handoffs/<int:operation_id>/confirm/", ResourceHandoffConfirmView.as_view(), name="planning-resource-handoff-confirm"),
path("operation-starts/", OperationStartFactsView.as_view(), name="planning-operation-start-facts"),
path("operation-starts/<int:task_id>/start/", OperationStartView.as_view(), name="planning-operation-start"),
path("workshop-tasks/", WorkshopTaskFactsView.as_view(), name="planning-workshop-task-facts"),
path("workshop-tasks/draft/", WorkshopTaskDraftView.as_view(), name="planning-workshop-task-draft"),
path("workshop-tasks/<int:task_id>/dispatch/", WorkshopTaskDispatchView.as_view(), name="planning-workshop-task-dispatch"),
path("work-order-workshop-reception/", ProductionWorkOrderWorkshopReceptionView.as_view(), name="planning-work-order-workshop-reception"),
path("work-orders/<int:work_order_id>/workshops/<int:workshop_id>/receive/", ProductionWorkOrderWorkshopReceiveView.as_view(), name="planning-work-order-workshop-receive"),
path("production-plans/<int:production_plan_id>/work-order-reception/", ProductionWorkOrderReceptionView.as_view(), name="planning-work-order-reception"),
path("production-plans/<int:production_plan_id>/work-order/generate/", ProductionWorkOrderGenerateView.as_view(), name="planning-work-order-generate"),
path("production-plans/<int:production_plan_id>/work-order/release/", ProductionWorkOrderReleaseView.as_view(), name="planning-work-order-release"),
path("production-plans/<int:production_plan_id>/formal-scheduling/", FormalSchedulingView.as_view(), name="planning-formal-scheduling"),
path("production-plans/<int:production_plan_id>/formal-scheduling/admission/", FormalSchedulingAdmissionView.as_view(), name="planning-formal-scheduling-admission"),
path("production-plans/<int:production_plan_id>/formal-scheduling/capacity-scope/", FormalSchedulingCapacityScopeView.as_view(), name="planning-formal-scheduling-capacity-scope"),
path("production-plans/<int:production_plan_id>/formal-schedules/<int:schedule_id>/cancel/", FormalSchedulingCancelView.as_view(), name="planning-formal-scheduling-cancel"),
path("production-plans/<int:production_plan_id>/start-date/", ProductionPlanStartDateView.as_view(), name="planning-production-plan-start-date")
]
