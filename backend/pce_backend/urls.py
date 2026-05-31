from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from purchase.views import PurchaseOrderViewSet
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
    path("api/purchase/", include(router.urls)),
]
