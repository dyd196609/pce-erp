from django.db import OperationalError, ProgrammingError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PriceApprovalPreparation, QuoteComparisonFact
from .legacy_quote_comparison_adapter import LegacyQuoteComparisonAdapter
from .price_approval_preparation_service import (
    build_supplier_recommendation_context,
    create_price_approval_preparation,
    create_price_approval_preparation_from_projection,
    serialize_legacy_projection_candidate,
    serialize_quote_comparison_candidate,
    serialize_price_approval_preparation,
    transition_price_approval_preparation,
    is_supplier_recommendation_eligible,
    resolve_supplier_recommendation_blocked_reason,
)


def _failure(code, message, status=409):
    return Response({
        "success": False, "data": None,
        "error": {"code": code, "message": message},
        "meta": {"module": "SCM", "source": "server", "productionUserDataWritten": False},
    }, status=status)


class PriceApprovalPreparationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            rows = [serialize_price_approval_preparation(item) for item in
                PriceApprovalPreparation.objects.select_related("source_comparison").all()]
            available_comparisons = [serialize_quote_comparison_candidate(item) for item in
                QuoteComparisonFact.objects.filter(price_approval_preparation__isnull=True)[:200]]
            used_projection_ids = set(PriceApprovalPreparation.objects.exclude(
                source_projection_id__isnull=True).values_list("source_projection_id", flat=True))
            available_comparisons.extend(serialize_legacy_projection_candidate(item)
                for item in LegacyQuoteComparisonAdapter().list_projections()
                if item.projectionId not in used_projection_ids)
        except (OperationalError, ProgrammingError):
            return _failure("QUOTE_COMPARISON_FACT_NOT_DEPLOYED",
                "正式QuoteComparisonFact事实层尚未部署，禁止回退到Legacy、Demo或页面缓存。", 409)
        return Response({
            "success": True,
            "data": {"records": rows, "resultCount": len(rows),
                "availableComparisons": available_comparisons,
                "availableComparisonCount": len(available_comparisons), "dataMode": "production",
                "factSource": "QuoteComparisonFact", "purchaseOrderCreated": False},
            "error": None,
            "meta": {"module": "SCM", "source": "server", "readOnly": True,
                "businessWriteCount": 0, "productionUserDataWritten": False},
        })

    def post(self, request):
        try:
            source_projection_id = request.data.get("sourceProjectionId")
            if source_projection_id:
                preparation, created = create_price_approval_preparation_from_projection(source_projection_id)
            else:
                preparation, created = create_price_approval_preparation(request.data.get("sourceComparisonNo"))
        except QuoteComparisonFact.DoesNotExist:
            return _failure("QUOTE_COMPARISON_FACT_NOT_FOUND", "来源报价比较事实不存在。", 404)
        except (OperationalError, ProgrammingError):
            return _failure("QUOTE_COMPARISON_FACT_NOT_DEPLOYED", "正式报价比较事实层尚未部署。", 409)
        except ValueError as error:
            return _failure("LEGACY_FACT_PROJECTION_BLOCKED", str(error), 409)
        return Response({
            "success": True,
            "data": {"created": created, "preparation": serialize_price_approval_preparation(preparation),
                "supplierRecommendationCreated": False, "purchaseOrderCreated": False},
            "error": None,
            "meta": {"module": "SCM", "source": "server", "businessWriteCount": 1 if created else 0,
                "productionUserDataWritten": bool(created)},
        }, status=201 if created else 200)


class PriceApprovalPreparationTransitionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, preparation_id):
        actor = getattr(request.user, "username", "") or str(request.user)
        try:
            preparation = transition_price_approval_preparation(
                preparation_id, request.data.get("targetStatus"), request.data, actor
            )
        except PriceApprovalPreparation.DoesNotExist:
            return _failure("PRICE_APPROVAL_PREPARATION_NOT_FOUND", "核价准备对象不存在。", 404)
        except ValueError as error:
            return _failure("PRICE_APPROVAL_ACTION_BLOCKED", str(error), 409)
        return Response({
            "success": True,
            "data": {"preparation": serialize_price_approval_preparation(preparation),
                "supplierRecommendationContext": build_supplier_recommendation_context(preparation)
                    if is_supplier_recommendation_eligible(preparation) else None,
                "supplierRecommendationBlockedReason": ""
                    if is_supplier_recommendation_eligible(preparation)
                    else resolve_supplier_recommendation_blocked_reason(preparation),
                "purchaseOrderCreated": False},
            "error": None,
            "meta": {"module": "SCM", "source": "server", "businessWriteCount": 1,
                "productionUserDataWritten": True},
        })
