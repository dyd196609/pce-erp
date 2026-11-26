from django.db import OperationalError, ProgrammingError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PriceApprovalPreparation, QuoteComparisonFact
from .fact_read_access import (read_qualification, PAGE_READ_PERMISSIONS,
                               scoped_queryset, ReadScopeBlocked, READ_SCOPE_FACTS)
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


def _review_invoke(callback):
    from .comparison_registration_api import invoke
    from .preparation_review_service import ACTION_CONTRACT
    result = invoke(callback)
    result.data['meta']['actionContract'] = ACTION_CONTRACT
    return result


class PriceApprovalPreparationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        read_qualification(request.user, PAGE_READ_PERMISSIONS.get("price-approval"))
        try:
            rows = [serialize_price_approval_preparation(item, user=request.user) for item in
                scoped_queryset(PriceApprovalPreparation.objects.select_related("source_comparison").all(),
                                request.user, PAGE_READ_PERMISSIONS["price-approval"])]
            available_comparisons = [serialize_quote_comparison_candidate(item) for item in
                scoped_queryset(QuoteComparisonFact.objects.filter(price_approval_preparation__isnull=True),
                                request.user, PAGE_READ_PERMISSIONS["price-approval"])[:200]]
            # A legacy projection is not a typed native corporate source proof.
            # Retain its original records; never expose it by matching bare IDs.
            legacy_unproven = bool(LegacyQuoteComparisonAdapter().list_projections())
            if legacy_unproven and not rows and not available_comparisons:
                raise ReadScopeBlocked("SOURCE_OWNERSHIP_UNRESOLVED",
                    "历史核价来源尚无正式对象及归属证明，不能显示为空结果。", 409)
        except (OperationalError, ProgrammingError):
            return _failure("QUOTE_COMPARISON_FACT_NOT_DEPLOYED",
                "正式QuoteComparisonFact事实层尚未部署，禁止回退到Legacy、Demo或页面缓存。", 409)
        return Response({
            "success": True,
            "data": {"records": rows, "resultCount": len(rows),
                "availableComparisons": available_comparisons,
                "availableComparisonCount": len(available_comparisons), "dataMode": "production",
                "factSource": "QuoteComparisonFact", "purchaseOrderCreated": False,
                "readScopeFacts": {**READ_SCOPE_FACTS,
                    "contract": "USER_APPROVED_SCM_THREE_READ_PERMISSIONS_20261116",
                    "legacySourceBridge": "UNPROVEN_NOT_IMPORTED",
                    "readDoesNotAuthorizeExecution": True}},
            "error": None,
            "meta": {"module": "SCM", "source": "server", "readOnly": True,
                "businessWriteCount": 0, "productionUserDataWritten": False},
        })

    def post(self, request):
        from .comparison_registration_service import (ComparisonRegistrationError,
            execution_qualification, register_comparison)
        try:
            execution_qualification(request.user)
            if "inquiryId" in request.data:
                from .comparison_registration_api import invoke
                return invoke(lambda: register_comparison(user=request.user, payload=request.data))
            source_projection_id = request.data.get("sourceProjectionId")
            if source_projection_id:
                return _failure("LEGACY_PREPARATION_SOURCE_PENDING", "历史投影继续待核，不作为新正式登记来源。", 409)
            if set(request.data) - {"sourceComparisonNo", "sourceComparisonFactId", "sourceComparisonVersion"}:
                return _failure("COMPARISON_INPUT_INVALID", "仅接受准确比较事实及版本，或完整原登记动作。", 400)
            preparation, created = create_price_approval_preparation(request.data.get("sourceComparisonNo"),
                fact_id=request.data.get("sourceComparisonFactId"),
                expected_version=request.data.get("sourceComparisonVersion"), actor=request.user)
        except ComparisonRegistrationError as error:
            return _failure(error.code, str(error), error.http_status)
        except QuoteComparisonFact.DoesNotExist:
            return _failure("QUOTE_COMPARISON_FACT_NOT_FOUND", "来源报价比较事实不存在。", 404)
        except (OperationalError, ProgrammingError):
            return _failure("QUOTE_COMPARISON_FACT_NOT_DEPLOYED", "正式报价比较事实层尚未部署。", 409)
        except ValueError as error:
            return _failure("LEGACY_FACT_PROJECTION_BLOCKED", str(error), 409)
        return Response({
            "success": True,
            "data": {"created": created, "preparation": {"id": preparation.pk,
                "approvalPrepareNo": preparation.approval_prepare_no,
                "sourceComparisonFactId": str(preparation.source_comparison_id),
                "sourceComparisonVersion": preparation.source_comparison.fact_version,
                "statusCode": preparation.status, "statusLabel": preparation.get_status_display()},
                "supplierRecommendationCreated": False, "purchaseOrderCreated": False},
            "error": None,
            "meta": {"module": "SCM", "source": "server", "businessWriteCount": 1 if created else 0,
                "productionUserDataWritten": bool(created)},
        }, status=201 if created else 200)


class PriceApprovalPreparationTransitionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, preparation_id):
        from .preparation_review_service import review_context, action_result
        if set(request.query_params) - {'idempotencyKey'}:
            return _failure('PREPARATION_REVIEW_INPUT_INVALID', '仅接受同次动作查询键。', 400)
        return _review_invoke(lambda: action_result(user=request.user, preparation_id=preparation_id,
            key=request.query_params['idempotencyKey']) if 'idempotencyKey' in request.query_params
            else review_context(user=request.user, preparation_id=preparation_id))

    def post(self, request, preparation_id):
        if 'action' in request.data:
            return _review_invoke(lambda: transition_price_approval_preparation(
                preparation_id, None, request.data, request.user))
        from .comparison_registration_service import ComparisonRegistrationError
        actor = getattr(request.user, "username", "") or str(request.user)
        try:
            preparation = transition_price_approval_preparation(
                preparation_id, request.data.get("targetStatus"), request.data, actor
            )
        except ComparisonRegistrationError as error:
            return _failure(error.code, str(error), error.http_status)
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
