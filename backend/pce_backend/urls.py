from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from purchase.views import (
    PurchaseOrderViewSet,
    purchase_order_create,
    purchase_order_delete,
    purchase_order_detail,
    purchase_order_update,
    purchase_order_v6_detail,
    purchase_order_v6_list,
)
from system.admin import import_org_view
from system.views import api_login

# 创建路由器并注册订单视图集
router = DefaultRouter()
router.register(r"orders", PurchaseOrderViewSet, basename="purchase-order")

urlpatterns = [
    path("admin/import-org/", import_org_view, name="import_org"),
    path("admin/", admin.site.urls),
    path("api/auth/login/", api_login, name="api_login"),
    path("api/", include("system.urls")),
    path("api/pfm/", include("pfm.urls")),
    path("api/masterdata/", include("masterdata.urls")),
    path("api/procurement/", include("procurement.urls")),
    path("api/purchase/order/list", purchase_order_v6_list, name="purchase-order-v6-list"),
    path("api/purchase/order/detail", purchase_order_v6_detail, name="purchase-order-v6-detail"),
    path(
        "api/purchase/order/detail/<int:pk>",
        purchase_order_detail,
        name="purchase-order-detail",
    ),
    path("api/purchase/order/create", purchase_order_create, name="purchase-order-create"),
    path(
        "api/purchase/order/update/<int:pk>",
        purchase_order_update,
        name="purchase-order-update",
    ),
    path(
        "api/purchase/order/delete/<int:pk>",
        purchase_order_delete,
        name="purchase-order-delete",
    ),
    path("api/purchase/", include(router.urls)),
]
