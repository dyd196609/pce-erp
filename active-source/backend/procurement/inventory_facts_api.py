"""Formal WMS/QMS read models for A1.5.

These endpoints expose the existing procurement inventory and inspection facts.
They intentionally contain no demo/fixture/localStorage fallback and perform no
business write.
"""
from procurement.quantity_contract import exact_total

from django.db.models import Sum
from django.db import DatabaseError
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from system.authorization import AuthorizationService
from reconciliation.models import PayableCheckAuthorityRecord, SupplierSettlementAuthorityRecord

from .models import (
    InventoryBalance,
    InventoryLot,
    InventoryTransaction,
    PurchaseReceipt,
    PurchaseInspection,
    Warehouse,
    WarehouseInbound,
    WarehouseLocation,
)


INVENTORY_READ_PERMISSION = "warehouse.inventory.read"
INVENTORY_TRANSACTION_READ_PERMISSION = "warehouse.inventory_transaction.read"
PURCHASE_RECEIPT_READ_PERMISSION = "procurement.receipt.read"
PURCHASE_INSPECTION_READ_PERMISSION = "quality.purchase_inspection.read"
PAYABLE_CHECK_READ_PERMISSION = "finance.payable_check.read"


def _authorize(request, action_code):
    decision = AuthorizationService.decide(
        user=request.user,
        action_code=action_code,
        organization_id=str(request.user.company_id),
        business_object={"organizationId": str(request.user.company_id)},
    )
    if not decision.get("allowed"):
        return decision, Response({
            "success": False,
            "error": {
                "code": decision.get("decisionCode", "PERMISSION_DENIED"),
                "message": decision.get("reason", "当前账户无权读取正式业务事实。"),
            },
            "authorization": decision,
        }, status=403)
    return decision, None


def _material_stock_unit(material):
    if material.unit_status != "confirmed":
        return None
    return material.base_uom.name if material.base_uom_id else (material.unit or None)


def _inventory_movement(row):
    issue = getattr(row, "material_issue", None)
    direction_label, quantity_label = {
        "IN": ("入库", "增加"),
        "OUT": ("出库", "减少"),
    }.get(row.direction, (None, None))
    source_type = None
    document_label = None
    unit_label = _material_stock_unit(row.material)
    if row.direction == "IN":
        source_type = "WarehouseInbound"
        document_label = f"入库单 {row.source_inbound.inbound_no}"
    elif row.direction == "OUT" and issue:
        source_type = "ProductionMaterialIssue"
        direction_label = "发料出库"
        document_label = f"发料单 ID {issue.pk}"
        unit_label = issue.allocation.uom.name
    return {
        "materialIssueId": issue.pk if issue else None,
        "transactionBusinessSourceType": source_type,
        "directionLabel": direction_label,
        "movementDocumentLabel": document_label,
        "quantityChangeLabel": quantity_label,
        "quantityUnitLabel": unit_label,
    }


class FormalInventoryFactsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        decision, denied = _authorize(request, INVENTORY_READ_PERMISSION)
        if denied:
            return denied
        transaction_decision, denied = _authorize(request, INVENTORY_TRANSACTION_READ_PERMISSION)
        if denied:
            return denied
        company_id = request.user.company_id
        warehouses = Warehouse.objects.filter(company_id=company_id).order_by("code")
        locations = WarehouseLocation.objects.filter(warehouse__company_id=company_id).select_related("warehouse")
        lots = InventoryLot.objects.filter(company_id=company_id).select_related("material", "warehouse")
        balances = InventoryBalance.objects.filter(warehouse__company_id=company_id).select_related(
            "warehouse", "material__base_uom", "location", "lot",
        )
        transactions = InventoryTransaction.objects.filter(warehouse__company_id=company_id).select_related(
            "warehouse", "material__base_uom", "location", "lot", "source_inbound",
            "material_issue__allocation__uom", "material_issue",
        )
        total_quantity = exact_total(balances,'quantity')
        return Response({
            "success": True,
            "factSource": "server",
            "authoritySource": "procurement.InventoryBalance/InventoryTransaction",
            "formalFact": True,
            "demoFixtureIncluded": False,
            "localStorageFormalFactCount": 0,
            "authorization": {
                "inventoryRead": decision,
                "inventoryTransactionRead": transaction_decision,
            },
            "warehouses": [{
                "id": row.pk, "code": row.code, "name": row.name,
                "isActive": row.is_active,
            } for row in warehouses],
            "locations": [{
                "id": row.pk, "warehouseId": row.warehouse_id,
                "warehouseCode": row.warehouse.code, "code": row.code,
                "name": row.name, "isActive": row.is_active,
            } for row in locations],
            "lots": [{
                "id": row.pk, "lotNo": row.lot_no, "materialId": row.material_id,
                "materialCode": row.material.code,
                "warehouseId": row.warehouse_id,
                "warehouseCode": row.warehouse.code if row.warehouse_id else "",
                "isActive": row.is_active,
            } for row in lots],
            "balances": [{
                "id": row.pk, "warehouseId": row.warehouse_id,
                "warehouseCode": row.warehouse.code, "materialId": row.material_id,
                "materialCode": row.material.code, "materialName": row.material.name,
                "locationId": row.location_id,
                "locationCode": row.location.code if row.location_id else "",
                "lotId": row.lot_id, "lotNo": row.lot.lot_no if row.lot_id else "",
                "quantity": str(row.quantity), "quantityDisplay": format(row.quantity, ".6f"),
                "quantityUnitLabel": _material_stock_unit(row.material),
                "updatedAt": row.updated_at.isoformat(),
            } for row in balances],
            "transactions": [{
                "id": row.pk, "transactionNo": row.transaction_no,
                "sourceInboundId": row.source_inbound_id,
                "sourceInboundNo": row.source_inbound.inbound_no,
                **_inventory_movement(row),
                "warehouseCode": row.warehouse.code,
                "materialCode": row.material.code, "materialName": row.material.name,
                "locationCode": row.location.code if row.location_id else "",
                "lotNo": row.lot.lot_no if row.lot_id else "",
                "direction": row.direction, "quantity": str(row.quantity),
                "beforeQuantity": str(row.before_quantity),
                "afterQuantity": str(row.after_quantity),
                "afterQuantityDisplay": format(row.after_quantity, ".6f"),
                "occurredAt": row.occurred_at.isoformat(),
            } for row in transactions],
            "summary": {
                "warehouseCount": warehouses.count(), "locationCount": locations.count(),
                "lotCount": lots.count(), "balanceCount": balances.count(),
                "transactionCount": transactions.count(), "totalQuantity": str(total_quantity),
            },
        })


class FormalQualityFactsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            return self._read_quality(request)
        except DatabaseError:
            return Response({
                "success": False,
                "error": {
                    "code": "RAW_QUALITY_READ_FAILED",
                    "message": "来料检验及逐行放行事实读取失败，不能显示为0或空成功。",
                },
            }, status=500)

    def _read_quality(self, request):
        from .material_stock_authority import quality_projection
        decision, denied = _authorize(request, PURCHASE_INSPECTION_READ_PERMISSION)
        if denied:
            return denied
        company_id = request.user.company_id
        inspections = PurchaseInspection.objects.filter(
            source_receipt__source_purchase_order__company_id=company_id,
        ).select_related(
            "source_receipt", "source_receipt__source_purchase_order",
            "source_receipt__source_purchase_order__supplier", "inspector_employee",
        )
        inbounds = WarehouseInbound.objects.filter(
            source_inspection__source_receipt__source_purchase_order__company_id=company_id,
        ).select_related("source_inspection", "warehouse", "location")
        return Response({
            "success": True,
            "factSource": "server",
            "authoritySource": "procurement.PurchaseInspection/WarehouseInbound",
            "formalFact": True,
            "demoFixtureIncluded": False,
            "localStorageFormalWriteCount": 0,
            "authorization": decision,
            "inspections": [{
                **quality_projection(row),
                "id": row.pk, "inspectionNo": row.inspection_no,
                "receiptNo": row.source_receipt.receipt_no,
                "purchaseOrderNo": row.source_receipt.source_purchase_order.po_no,
                "supplierId": row.source_receipt.source_purchase_order.supplier_id,
                "supplierName": row.source_receipt.source_purchase_order.supplier.name,
                "inspectorName": row.inspector_employee.full_name,
                "status": row.status,
                "statusLabel": row.get_status_display() if row.status in dict(PurchaseInspection.STATUS_CHOICES) else None,
                "quantity": str(row.quantity),
                "items": row.items if isinstance(row.items, list) else [],
                "qualifiedQuantity": str(row.qualified_quantity),
                "rejectedQuantity": str(row.rejected_quantity),
                "inspectionDate": row.inspection_date.isoformat() if row.inspection_date else "",
            } for row in inspections],
            "inbounds": [{
                "id": row.pk, "inboundNo": row.inbound_no,
                "inspectionNo": row.source_inspection.inspection_no,
                "warehouseCode": row.warehouse.code,
                "locationCode": row.location.code if row.location_id else "",
                "status": row.status, "quantity": str(row.quantity),
                "inboundDate": row.inbound_date.isoformat(),
            } for row in inbounds],
            "summary": {
                "inspectionCount": inspections.count(), "inboundCount": inbounds.count(),
            },
        })


class FormalPurchaseReceiptFactsView(APIView):
    """Read-only PurchaseReceipt projection used by the completed-module UI."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        decision, denied = _authorize(request, PURCHASE_RECEIPT_READ_PERMISSION)
        if denied:
            return denied
        receipts = PurchaseReceipt.objects.filter(
            source_purchase_order__company_id=request.user.company_id,
        ).select_related(
            "source_purchase_order", "source_purchase_order__supplier",
        ).prefetch_related("inspections").order_by("-id")
        rows = []
        for row in receipts:
            order = row.source_purchase_order
            items = row.items if isinstance(row.items, list) else []
            rows.append({
                "id": row.pk,
                "receiptNo": row.receipt_no,
                "sourceOrderId": order.pk,
                "sourceOrderNo": order.po_no,
                "supplierId": order.supplier_id,
                "supplierName": order.supplier.name,
                "status": row.status,
                "receiptDate": row.receipt_date.isoformat(),
                "quantity": str(row.quantity),
                "amount": str(row.amount),
                "lines": items,
                "inspectionCount": row.inspections.count(),
                "formalAuthority": True,
                "authoritySource": "procurement.PurchaseReceipt",
                "createdAt": row.created_at.isoformat() if row.created_at else None,
            })
        return Response({
            "success": True,
            "factSource": "server",
            "authoritySource": "procurement.PurchaseReceipt",
            "formalFact": True,
            "demoFixtureIncluded": False,
            "localStorageFormalFactCount": 0,
            "authorization": decision,
            "receipts": rows,
            "summary": {"receiptCount": len(rows)},
        })


class FormalPayableCheckFactsView(APIView):
    """Read-only projection of governed PayableCheck authority records."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        decision, denied = _authorize(request, PAYABLE_CHECK_READ_PERMISSION)
        if denied:
            return denied
        checks = PayableCheckAuthorityRecord.objects.filter(
            company_id=request.user.company_id,
        ).order_by("-occurred_at", "-id")
        settlements = SupplierSettlementAuthorityRecord.objects.filter(
            company_id=request.user.company_id,
        ).order_by("-occurred_at", "-id")
        rows = [{
            "id": row.pk,
            "payableCheckNo": row.payable_check_no,
            "supplierId": row.supplier_id,
            "legalEntityId": row.legal_entity_id,
            "ledgerBookId": row.ledger_book_id,
            "currency": row.currency,
            "totalCheckedAmount": str(row.checked_amount),
            "totalCheckedQty": str(row.checked_quantity),
            "checkStatus": row.business_status,
            "businessHash": row.business_hash,
            "occurredAt": row.occurred_at.isoformat(),
            "formalAuthority": True,
            "authoritySource": "reconciliation.PayableCheckAuthorityRecord",
        } for row in checks]
        return Response({
            "success": True,
            "factSource": "server",
            "authoritySource": "reconciliation.PayableCheckAuthorityRecord",
            "formalFact": True,
            "demoFixtureIncluded": False,
            "localStorageFormalFactCount": 0,
            "authorization": decision,
            "payableChecks": rows,
            "supplierSettlements": [{
                "id": row.pk,
                "authorityObjectId": row.authority_object_id,
                "settlementNo": row.settlement_no,
                "supplierId": row.supplier_id,
                "supplierName": row.supplier_name,
                "currency": row.currency,
                "settlementAmount": str(row.amount),
                "settlementQuantity": str(row.quantity),
                "settlementStatus": row.business_status,
                "reconciliationStatus": row.business_status,
                "businessHash": row.business_hash,
                "occurredAt": row.occurred_at.isoformat(),
                "nextStepReadiness": "not_ready",
                "formalAuthority": True,
                "authoritySource": "reconciliation.SupplierSettlementAuthorityRecord",
            } for row in settlements],
            "summary": {
                "payableCheckCount": len(rows),
                "supplierSettlementCount": settlements.count(),
            },
        })
