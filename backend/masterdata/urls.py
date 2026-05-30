from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'categories', views.MaterialCategoryViewSet)
router.register(r'materials', views.MaterialViewSet)
router.register(r'code-rules', views.CodeRuleViewSet)

urlpatterns = [
    path('', include(router.urls)),
]