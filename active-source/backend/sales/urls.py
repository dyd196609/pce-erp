from django.urls import path
from .views import (
    SalesFactsView, SalesOrderActionView, SalesOrderCreateView, SalesOrderConfirmView,
    SalesOrderDemandView, SalesOrderDetailView, SalesOrderEngineeringAttributeCreateView,
    SalesOrderItemDetailView,
    WholeHouseOrderPreviewView, WholeHouseOrderSourceIntakeView, WholeHouseSourceActionView,
)
from .engineering_source_formalization_views import EngineeringSourceFormalizationPreviewView
from .development_contract_sample_views import DevelopmentContractEntryView, DevelopmentContractQuoteCalculateView, DevelopmentContractSampleView
from .order_review_views import CrmOrderReviewView
from .supply_admission_views import SupplyAdmissionView

from .new_order_source import ConfirmOrderSourceView, NewOrderSourceView, RegisterOrderSourceScopeView

from .followup_views import (
    CustomerBindingView, CustomerOrderProgressView, CustomerProgressPublicationView, FollowupDirectoryView, FollowupOrderView,
)

urlpatterns = [
    path("production-followup/", FollowupDirectoryView.as_view(), name="enterprise-production-followup"),
    path("production-followup/<str:order_no>/", FollowupOrderView.as_view(), name="enterprise-production-followup-detail"),
    path("customer-bindings/", CustomerBindingView.as_view(), name="enterprise-customer-binding"),
    path("customer-progress/orders/", CustomerOrderProgressView.as_view(), name="customer-progress-list"),
    path("customer-progress/orders/<str:order_no>/", CustomerOrderProgressView.as_view(), name="customer-progress-order"),
    path("customer-progress/publication/<str:order_no>/", CustomerProgressPublicationView.as_view(), name="customer-progress-publication"),
    path("orders/new-sources/<int:source_record_id>/formal-scope/", RegisterOrderSourceScopeView.as_view()),
    path("orders/new-sources/<int:source_record_id>/confirm/", ConfirmOrderSourceView.as_view()),
    path("orders/new-sources/", NewOrderSourceView.as_view()),
    path("orders/new-sources/<int:source_record_id>/", NewOrderSourceView.as_view()),
    path("orders/<int:order_id>/items/<int:item_id>/supply-admission/", SupplyAdmissionView.as_view(), name="sales-order-item-supply-admission"),
    path("facts/", SalesFactsView.as_view()),
    path("order-reviews/", CrmOrderReviewView.as_view(), name="crm-order-reviews"),
    path("previews/whole-house-order/", WholeHouseOrderPreviewView.as_view()),
    path("orders/source-intake/whole-house/", WholeHouseOrderSourceIntakeView.as_view()),
    path("orders/source-intake/whole-house/actions/<slug:action>/", WholeHouseSourceActionView.as_view()),
    path("orders/source-intake/development-contract-entry/", DevelopmentContractEntryView.as_view()),
    path("orders/source-intake/engineering-sources/<int:source_record_id>/", EngineeringSourceFormalizationPreviewView.as_view()),
    path("orders/source-intake/engineering-sources/<int:source_record_id>/development-contract/", DevelopmentContractSampleView.as_view()),
    path("orders/source-intake/engineering-sources/<int:source_record_id>/development-contract/calculate/", DevelopmentContractQuoteCalculateView.as_view()),
    path("orders/", SalesOrderCreateView.as_view()),
    path("orders/<int:order_id>/", SalesOrderDetailView.as_view()),
    path("orders/<int:order_id>/actions/<slug:action>/", SalesOrderActionView.as_view()),
    path("orders/<int:order_id>/items/<int:item_id>/", SalesOrderItemDetailView.as_view()),
    path("orders/<int:order_id>/confirm/", SalesOrderConfirmView.as_view()),
    path("orders/<int:order_id>/generate-demand/", SalesOrderDemandView.as_view()),
    path(
        "orders/<int:order_id>/items/<int:item_id>/engineering-attributes/",
        SalesOrderEngineeringAttributeCreateView.as_view(),
    ),
]
