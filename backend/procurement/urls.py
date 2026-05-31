from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SupplierViewSet, PurchaseOrderViewSet, ReportViewSet

router = DefaultRouter()
router.register(r"suppliers", SupplierViewSet)
router.register(r"purchase_orders", PurchaseOrderViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path(
        "reports/",
        include(
            [
                path(
                    "department-purchase/",
                    ReportViewSet.as_view({"get": "department_purchase_report"}),
                    name="report-department-purchase",
                ),
                path(
                    "buyer-performance/",
                    ReportViewSet.as_view({"get": "buyer_performance_report"}),
                    name="report-buyer-performance",
                ),
                path(
                    "supplier-performance/",
                    ReportViewSet.as_view({"get": "supplier_performance_report"}),
                    name="report-supplier-performance",
                ),
            ]
        ),
    ),
]
