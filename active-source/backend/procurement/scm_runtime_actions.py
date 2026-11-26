from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.middleware.csrf import get_token

from .scm_runtime_services import (
    PurchaseInspectionService,
    PurchaseOrderCreationService,
    PurchaseOrderExecutionService,
    PurchaseReceiptService,
    ScmRuntimeActionError,
    WarehouseInboundService,
)
from .procurement_mode_router import DirectPurchaseAuthorization, ProcurementModeRouter


def _payload(value):
    return {
        "objectId": value.pk,
        "objectType": value.__class__.__name__,
        "objectNo": value.object_no,
        "status": value.status,
    }


ORDER_APPROVAL_ACTIONS = {
    'submit-purchase-order': 'procurement.purchase_order.submit',
    'approve-purchase-order': 'procurement.purchase_order.approve',
    'review-purchase-order': 'procurement.purchase_order.review',
    'release-purchase-order': 'procurement.purchase_order.release',
}


def order_approval_response(request, object_id, action_code):
    from .comparison_registration_api import invoke
    from .comparison_registration_service import ComparisonRegistrationError
    from . import purchase_order_approval_service as service
    contract = next(x for x in service.ACTION_CONTRACTS if x['actionCode'] == action_code)
    if request.method == 'GET':
        if set(request.query_params) - {'idempotencyKey'}:
            return Response({'success': False, 'data': None, 'error': {'code': 'ORDER_ACTION_INPUT_INVALID', 'message': '只接受本次动作结果键，不接受自报身份或范围。'}, 'meta': {'actionContract': contract}}, status=400)
        key = request.query_params.get('idempotencyKey')
        operation = (lambda: service.action_result(user=request.user, order_id=object_id, action=action_code, key=key)) if key else (
            lambda: service.action_context(user=request.user, order_id=object_id, action=action_code))
    else:
        operation = lambda: service.execute_action(user=request.user, order_id=object_id, action=action_code, payload=request.data)
    def original_business_result():
        try:
            return operation()
        except ScmRuntimeActionError as error:
            raise ComparisonRegistrationError(error.code, str(error), error.http_status) from error
    response = invoke(original_business_result)
    response.data['meta']['actionContract'] = contract
    return response


class ScmRuntimeActionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, action, object_id):
        if request.query_params.get('usagePurpose') == 'PRODUCTION_USE':
            from .material_allocation_api import raw_source_response
            return raw_source_response(request, action, object_id)
        if action not in ORDER_APPROVAL_ACTIONS:
            return Response({'success': False, 'error': {'code': 'ACTION_NOT_REGISTERED', 'message': '没有该动作的订单只读合同。'}}, status=404)
        return order_approval_response(request, object_id, ORDER_APPROVAL_ACTIONS[action])

    def post(self, request, action, object_id):
        if request.data.get('usagePurpose') == 'PRODUCTION_USE':
            from .material_allocation_api import raw_source_response
            return raw_source_response(request, action, object_id)
        if action in ORDER_APPROVAL_ACTIONS:
            return order_approval_response(request, object_id, ORDER_APPROVAL_ACTIONS[action])
        try:
            if action == "create-purchase-order":
                value = PurchaseOrderCreationService.create_from_price_approval(object_id, request.user.id)
            elif action == "confirm-receipt":
                value = PurchaseReceiptService.confirm(object_id, request.data.get("quantity"), request.user)
            elif action == "create-inspection":
                value = PurchaseInspectionService.create_from_receipt(object_id, request.user)
            elif action == "transition-inspection":
                value = PurchaseInspectionService.transition(
                    object_id,
                    request.data.get("targetStatus"),
                    request.data.get("qualifiedQuantity"),
                    request.user,
                )
            elif action == "confirm-inbound":
                value = WarehouseInboundService.confirm(
                    object_id, request.data.get("quantity"),
                    request.data.get("warehouseCode"), request.user,
                    location_code=request.data.get("locationCode"),
                    lot_numbers=request.data.get("lotNumbers"),
                )
            elif action == "complete-purchase-order":
                value = PurchaseOrderExecutionService.complete(object_id, request.user)
            else:
                return Response({"success": False, "error": {"code": "ACTION_NOT_REGISTERED", "message": "SCM动作未登记"}}, status=404)
        except ScmRuntimeActionError as error:
            return Response({
                "success": False,
                "data": None,
                "error": {"code": error.code, "message": error.message},
                "meta": {"productionUserDataWritten": False},
            }, status=error.http_status)
        return Response({
            "success": True,
            "data": _payload(value),
            "error": None,
            "meta": {"actionSource": "explicit_user_post", "productionUserDataWritten": True},
        })


@method_decorator(ensure_csrf_cookie, name="dispatch")
class PurchaseOrderGateCreationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if 'priceConfirmationResultId' in request.query_params:
            from masterdata.views import _formal_price_invoke
            from .formal_price_confirmation_service import standard_order_context, ORDER_SOURCE_ACTION_CONTRACT
            return _formal_price_invoke(lambda: standard_order_context(user=request.user,result_id=request.query_params['priceConfirmationResultId']),action_contract=ORDER_SOURCE_ACTION_CONTRACT)
        authorization = DirectPurchaseAuthorization.decide_any_scope(request.user)
        return Response({
            "success": True,
            "data": {"actionCode": "CREATE_PURCHASE_ORDER_FROM_GATE", "confirmationRequired": True,
                     "purchaseMode": "DIRECT", "creationMode": "DIRECT_SELECTION",
                     "authorization": authorization, "routeAllowed": authorization["allowed"],
                     "csrfToken": get_token(request)},
            "error": None,
            "meta": {"readOnly": True, "productionUserDataWritten": False},
        })

    def post(self, request):
        try:
            preview = request.data.get("previewOnly") is True
            direct_creation = request.data.get("creationMode") == "DIRECT_SELECTION"
            agreed_price_creation = request.data.get("creationMode") == "AGREED_PRICE_CONFIRMATION"
            if direct_creation:
                values, created_count = PurchaseOrderCreationService.create_from_direct_request(
                    request.data, request.user, preview=preview
                )
            elif agreed_price_creation:
                values, created_count = PurchaseOrderCreationService.create_from_agreed_price_request(
                    request.data, request.user, preview=preview
                )
            elif request.data.get("creationMode") == "MANUAL_SELECTION":
                raise ScmRuntimeActionError(
                    "MANUAL_STANDARD_CREATION_RETIRED",
                    "旧人工STANDARD采购订单入口已经停用；标准采购必须沿完整业务流程进入。",
                )
            else:
                values, created_count = PurchaseOrderCreationService.create_from_gate_request(
                    request.data, request.user.id, preview=preview
                )
        except ScmRuntimeActionError as error:
            return Response({
                "success": False,
                "data": None,
                "error": {"code": error.code, "message": error.message},
                "meta": {"productionUserDataWritten": False, "businessWriteCount": 0},
            }, status=error.http_status)
        if preview:
            first_context = values[0] if values else {}
            return Response({
                "success": True,
                "data": {
                    "result": "PASS", "creationAllowed": True,
                    "contextCount": len(values), "contexts": values,
                    "gateStatus": first_context.get("gateStatus", "PASS"),
                    "gateCode": first_context.get("gateCode", "PURCHASE-ORDER-GATE-001"),
                    "admissionToken": first_context.get("admissionToken", ""),
                    "checks": first_context.get("checks", []),
                },
                "error": None,
                "meta": {"readOnly": True, "productionUserDataWritten": False,
                         "businessWriteCount": 0},
            })
        purchase_orders = [{
            **_payload(value),
            "supplierId": value.supplier_id,
            "supplierCode": value.supplier.code,
            "supplierName": value.supplier.name,
            "purchaseDate": value.order_date.isoformat() if value.order_date else None,
            "deliveryDate": value.expected_date.isoformat() if value.expected_date else None,
            "urgency": value.urgency_level,
            "itemCount": value.items.count(),
            "sourcePurchaseRequestId": value.source_purchase_request_id,
            "sourcePurchaseRequestNo": (value.source_purchase_request.request_no
                                        if value.source_purchase_request_id else ""),
        } for value in values]
        first = purchase_orders[0]
        return Response({
            "success": True,
            "data": {
                **first,
                "creationRequestId": request.data.get("requestId"),
                "created": created_count > 0,
                "createdCount": created_count,
                "supplierCount": (1 if direct_creation else
                                  len({value.supplier_id for value in values}) if agreed_price_creation else
                                  len(request.data.get("supplierGroups") or [])),
                "purchaseOrderCount": len(purchase_orders),
                "purchaseOrders": purchase_orders,
            },
            "error": None,
            "meta": {
                "actionSource": ("explicit_direct_purchase_order_creation"
                                 if direct_creation else "explicit_gate_creation_request"),
                "productionUserDataWritten": created_count > 0,
                "businessWriteCount": (created_count * (1 + first["itemCount"])
                                       if direct_creation else created_count),
            },
        })


class ProcurementModeRoutingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        result = ProcurementModeRouter.resolve(
            request.query_params.get("purchaseMode"), request.user,
            request.query_params.get("legalEntityId"),
        )
        return Response({"success": True, "data": result, "error": None,
                         "meta": {"readOnly": True, "productionUserDataWritten": False}})
