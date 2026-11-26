from decimal import Decimal

from django.db.models import Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from system.models import PositionWorkflowResponsibility
from workflow_runtime.models import WorkflowNodeDefinition

from .business_action_control import PROCESS_CODE, authorize_action
from .models import (
    InventoryBalance, InventoryTransaction, PurchaseInspection, PurchaseOrder,
    Warehouse, WarehouseInbound,
)


ACTION_LABELS = {
    "procurement.purchase_order.submit": "提交采购订单",
    "procurement.purchase_order.approve": "审核采购订单",
    "procurement.purchase_order.review": "复核采购订单",
    "procurement.purchase_order.release": "下达采购订单",
    "procurement.receipt.receive": "确认收货",
    "quality.purchase.inspect": "执行来料检验",
    "warehouse.purchase.putaway": "确认入库",
    "procurement.purchase_order.complete": "正常结案",
}


def _identity_chain(user, action_code, order):
    decision = authorize_action(
        user=user, action_code=action_code, organization_id=order.company_id,
        business_object={
            "organizationId": order.company_id,
            "departmentId": order.purchase_department_id or order.department_id,
            "ownerUserId": order.created_by,
        },
    )
    employee = getattr(user, "employee_profile", None)
    position = getattr(employee, "position_ref", None) if employee else None
    node = WorkflowNodeDefinition.objects.filter(
        process_definition__definition_code=PROCESS_CODE,
        business_action_code=action_code, active=True,
    ).first()
    mapping = PositionWorkflowResponsibility.objects.select_related("responsibility").filter(
        position=position, workflow_node=node, active=True,
        responsibility__is_active=True, responsibility__status="ACTIVE",
    ).first() if position and node else None
    executable = bool(
        decision.get("allowed") and employee and employee.status == "active"
        and position and position.is_active and mapping
    )
    reason = "" if executable else (
        decision.get("reason") if not decision.get("allowed")
        else "当前账号缺少有效的员工—岗位—职责—流程节点执行链。"
    )
    return {
        "actionCode": action_code,
        "label": ACTION_LABELS[action_code],
        "allowed": executable,
        "disabledReason": reason,
        "decisionCode": decision.get("decisionCode"),
        "permissionCodes": decision.get("permissionCodes", []),
        "roleCodes": decision.get("roleCodes", []),
        "scope": decision.get("scope", {}),
        "workflowNode": ({"id": node.pk, "code": node.node_code, "name": node.node_name}
                         if node else None),
        "responsibility": ({"code": mapping.responsibility.code,
                            "name": mapping.responsibility.name} if mapping else None),
        "position": ({"id": position.pk, "code": position.code, "name": position.name}
                     if position else None),
        "employee": ({"id": employee.pk, "employeeNo": employee.employee_no,
                      "name": employee.full_name} if employee else None),
        "account": {"id": user.pk, "username": user.username},
    }


def _inventory_rows(order):
    material_ids = list(order.items.exclude(material_id=None).values_list("material_id", flat=True))
    balances = InventoryBalance.objects.select_related("warehouse", "material").filter(
        material_id__in=material_ids, warehouse__company_id=order.company_id,
    )
    return [{
        "warehouseCode": row.warehouse.code,
        "warehouseName": row.warehouse.name,
        "locationCode": row.warehouse.location_code,
        "materialId": row.material_id,
        "materialCode": row.material.code,
        "materialName": row.material.name,
        "quantity": str(row.quantity),
    } for row in balances]


class PurchaseOrderFulfillmentFactsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        order = PurchaseOrder.objects.prefetch_related(
            "items__material", "scm_receipts__inspections__warehouse_inbounds"
        ).filter(pk=order_id).first()
        if not order:
            return Response({"success": False, "error": {"code": "PURCHASE_ORDER_NOT_FOUND", "message": "采购订单不存在"}}, status=404)

        receipts = list(order.scm_receipts.order_by("id"))
        inspections = list(PurchaseInspection.objects.filter(
            source_receipt__source_purchase_order=order
        ).select_related("source_receipt", "inspector_employee").order_by("id"))
        inbounds = list(WarehouseInbound.objects.filter(
            source_inspection__source_receipt__source_purchase_order=order
        ).select_related("source_inspection", "warehouse", "operator_employee").order_by("id"))
        transactions = InventoryTransaction.objects.filter(
            source_inbound__source_inspection__source_receipt__source_purchase_order=order
        ).select_related("warehouse", "material", "operator_employee").order_by("id")
        planned = order.items.aggregate(total=Sum("quantity"))["total"] or Decimal("0")
        received = sum((row.quantity for row in receipts), Decimal("0"))
        qualified = sum((row.qualified_quantity for row in inspections if row.status == "qualified"), Decimal("0"))
        rejected = sum((row.rejected_quantity for row in inspections), Decimal("0"))
        inbound_quantity = sum((row.quantity for row in inbounds if row.status == "completed"), Decimal("0"))
        actions = {code: _identity_chain(request.user, code, order) for code in ACTION_LABELS}
        warehouses = Warehouse.objects.filter(company_id=order.company_id, is_active=True).order_by("code")

        return Response({
            "success": True,
            "data": {
                "contractVersion": "PCE-PURCHASE-FULFILLMENT-V1.0",
                "order": {
                    "id": order.pk, "poNo": order.po_no, "status": order.status,
                    "statusLabel": order.get_status_display(), "supplierCode": order.supplier_code_snapshot or order.supplier.code,
                    "supplierName": order.supplier_name_snapshot or order.supplier.name,
                    "plannedQuantity": str(planned), "receivedQuantity": str(received),
                    "qualifiedQuantity": str(qualified), "rejectedQuantity": str(rejected),
                    "inboundQuantity": str(inbound_quantity), "completionType": "NORMAL" if order.status == "closed" else "",
                },
                "receipts": [{
                    "id": row.pk, "receiptNo": row.receipt_no, "status": row.status,
                    "statusLabel": row.get_status_display(), "quantity": str(row.quantity),
                    "receiptDate": row.receipt_date.isoformat(), "items": row.items,
                    "operatorEmployeeId": row.operator_employee_id,
                } for row in receipts],
                "inspections": [{
                    "id": row.pk, "inspectionNo": row.inspection_no,
                    "receiptId": row.source_receipt_id, "status": row.status,
                    "statusLabel": row.get_status_display(), "quantity": str(row.quantity),
                    "qualifiedQuantity": str(row.qualified_quantity),
                    "rejectedQuantity": str(row.rejected_quantity),
                    "inspectionDate": row.inspection_date.isoformat() if row.inspection_date else None,
                    "inspector": row.inspector_employee.full_name,
                } for row in inspections],
                "inbounds": [{
                    "id": row.pk, "inboundNo": row.inbound_no,
                    "inspectionId": row.source_inspection_id, "status": row.status,
                    "statusLabel": row.get_status_display(), "quantity": str(row.quantity),
                    "inboundDate": row.inbound_date.isoformat(), "warehouseCode": row.warehouse.code,
                    "warehouseName": row.warehouse.name, "operator": row.operator_employee.full_name,
                    "items": row.items,
                } for row in inbounds],
                "warehouses": [{"code": row.code, "name": row.name,
                                "locationCode": row.location_code} for row in warehouses],
                "inventoryBalances": _inventory_rows(order),
                "inventoryTransactions": [{
                    "transactionNo": row.transaction_no, "inboundId": row.source_inbound_id,
                    "warehouseCode": row.warehouse.code, "materialCode": row.material.code,
                    "materialName": row.material.name, "direction": row.direction,
                    "quantity": str(row.quantity), "beforeQuantity": str(row.before_quantity),
                    "afterQuantity": str(row.after_quantity),
                    "operator": row.operator_employee.full_name,
                    "occurredAt": row.occurred_at.isoformat(),
                } for row in transactions],
                "authorization": actions,
                "trace": [
                    {"type": "PurchaseRequest", "id": order.source_purchase_request_id,
                     "no": order.source_purchase_request.request_no if order.source_purchase_request_id else ""},
                    {"type": "PurchaseOrder", "id": order.pk, "no": order.po_no},
                    *[{"type": "PurchaseReceipt", "id": row.pk, "no": row.receipt_no} for row in receipts],
                    *[{"type": "PurchaseInspection", "id": row.pk, "no": row.inspection_no} for row in inspections],
                    *[{"type": "WarehouseInbound", "id": row.pk, "no": row.inbound_no} for row in inbounds],
                    *[{"type": "InventoryTransaction", "id": row.pk, "no": row.transaction_no} for row in transactions],
                ],
            },
            "error": None,
            "meta": {"source": "server", "readOnly": True, "productionUserDataWritten": False},
        })
