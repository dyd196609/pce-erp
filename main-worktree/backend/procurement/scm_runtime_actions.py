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


class ScmRuntimeActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, action, object_id):
        try:
            if action == "create-purchase-order":
                value = PurchaseOrderCreationService.create_from_price_approval(object_id, request.user.id)
            elif action in {
                "submit-purchase-order", "approve-purchase-order",
                "review-purchase-order", "release-purchase-order",
            }:
                action_code = {
                    "submit-purchase-order": "procurement.purchase_order.submit",
                    "approve-purchase-order": "procurement.purchase_order.approve",
                    "review-purchase-order": "procurement.purchase_order.review",
                    "release-purchase-order": "procurement.purchase_order.release",
                }[action]
                value = PurchaseOrderExecutionService.transition(object_id, action_code, request.user)
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
