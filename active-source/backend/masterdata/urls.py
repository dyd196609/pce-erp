from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .validated_fact_formalization_views import ValidatedFactFormalizationView

router = DefaultRouter()
router.register(r'categories', views.MaterialCategoryViewSet)
router.register(r'materials', views.MaterialViewSet)
router.register(r'code-rules', views.CodeRuleViewSet)

urlpatterns = [
    path(
        'validated-fact-formalization/',
        ValidatedFactFormalizationView.as_view(),
        name='validated-fact-formalization',
    ),
    path(
        'base-data-readiness/',
        views.BaseDataReadinessView.as_view(),
        name='base-data-readiness',
    ),
    path(
        'base-data-comparison/<str:entity_code>/',
        views.BaseDataComparisonPreviewView.as_view(),
        name='base-data-comparison-preview',
    ),
    path(
        'group2-comparison/<str:entity_code>/',
        views.Group2ComparisonPreviewView.as_view(),
        name='group2-comparison-preview',
    ),
    path(
        'group3-comparison/<str:entity_code>/',
        views.Group3ComparisonPreviewView.as_view(),
        name='group3-comparison-preview',
    ),
    path(
        'group3a-operation-targeted-revalidation/',
        views.Group3AOperationTargetedRevalidationView.as_view(),
        name='group3a-operation-targeted-revalidation',
    ),
    path(
        'prices/supplier-material-prices/runtime/confirm-quotation/',
        views.SupplierMaterialPriceQuotationConfirmationView.as_view(),
        name='supplier-material-price-confirm-quotation',
    ),
    path(
        'prices/supplier-material-prices/runtime/approval-results/',
        views.PriceApprovalResultView.as_view(),
        name='price-approval-result',
    ),
    path(
        'prices/supplier-material-prices/runtime/batch-archive/',
        views.SupplierMaterialPriceBatchArchiveView.as_view(),
        name='supplier-material-price-batch-archive',
    ),
    path(
        'prices/supplier-material-prices/runtime/price-approval-preparations/archive/',
        views.PriceApprovalPreparationArchiveView.as_view(),
        name='price-approval-preparation-archive',
    ),
    path(
        'prices/supplier-material-prices/runtime/price-source-consistency/',
        views.PriceSourceConsistencyView.as_view(),
        name='price-source-consistency',
    ),
    path(
        'prices/supplier-material-prices/runtime/manual-maintenance/',
        views.SupplierMaterialPriceManualCreateView.as_view(),
        name='supplier-material-price-manual-create',
    ),
    path(
        'prices/supplier-material-prices/runtime/<str:price_no>/maintenance/',
        views.SupplierMaterialPriceMaintenanceView.as_view(),
        name='supplier-material-price-maintenance',
    ),
    path(
        'relations/material-suppliers/runtime/<path:relation_code>/maintenance/',
        views.MaterialSupplierRelationMaintenanceView.as_view(),
        name='material-supplier-relation-maintenance',
    ),
    path(
        'prices/supplier-material-prices/runtime/facts/',
        views.SupplierMaterialPriceFactsView.as_view(),
        name='supplier-material-price-runtime-facts',
    ),
    path(
        'prices/supplier-price-facts/runtime/facts/',
        views.SupplierPriceFactFactsView.as_view(),
        name='supplier-price-fact-runtime-facts',
    ),
    path(
        'relations/material-suppliers/runtime/facts/',
        views.MaterialSupplierRelationFactsView.as_view(),
        name='material-supplier-relation-runtime-facts',
    ),
    path(
        'statistics/runtime/facts/',
        views.MasterDataStatisticsFactsView.as_view(),
        name='master-data-statistics-runtime-facts',
    ),
    path(
        'enterprise/<str:entity_code>/facts/',
        views.EnterpriseMasterDataFactsView.as_view(),
        name='enterprise-master-data-facts',
    ),
    path('', include(router.urls)),
]
