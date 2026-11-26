from procurement.quantity_contract import exact_total
import re

from django.core.paginator import Paginator
from django.db.models import Sum
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    PriceApproval,
    PriceApprovalPreparation,
    QuoteComparisonFact,
    PurchaseInquiry,
    PurchaseInspection,
    PurchaseOrder,
    PurchaseRequestItem,
    PurchaseReceipt,
    PurchaseRequest,
    SupplierQuotation,
    WarehouseInbound,
)
from .price_approval_preparation_service import serialize_price_approval_preparation
from .purchase_inquiry_service import eligible_purchase_request_rows
from .supplier_quotation_service import supplier_quotation_source_rows
from .fact_read_access import (PAGE_READ_PERMISSIONS, READ_SCOPE_FACTS,
                               reference_visible, scoped_queryset)


SCM_STANDARD_PAGE_VERSION = "V1.14.2.8.4.14"

PAGE_FACT_SOURCES = {
    "purchase-request": {"schema": "PurchaseRequestSchema", "model": PurchaseRequest},
    "purchase-inquiry": {"schema": "PurchaseInquirySchema", "model": PurchaseInquiry},
    "supplier-quotation": {"schema": "SupplierQuotationSchema", "model": SupplierQuotation},
    "supplier-quote-workbench": {"schema": "SupplierQuotationSchema", "model": SupplierQuotation},
    "price-approval": {"schema": "PriceApprovalPreparationSchema", "model": PriceApprovalPreparation},
    "quote-comparison": {"schema": "QuoteComparisonFactSchema", "model": QuoteComparisonFact},
    "purchase-order": {"schema": "PurchaseOrderSchema", "model": PurchaseOrder},
    "purchase-receive-preview": {"schema": "PurchaseReceiveSchema", "model": PurchaseReceipt},
    "incoming-inspection": {"schema": "IncomingInspectionSchema", "model": PurchaseInspection},
    "inventory-balances": {"schema": "InventoryBalanceSchema", "model": WarehouseInbound},
}

STATUS_LABELS = {
    "draft": "草稿", "submitted": "已提交", "approved": "已审批", "reviewing": "评审中",
    "rejected": "不合格", "final_approved": "已审批下达", "received": "已收货",
    "pending": "待检验", "inspecting": "检验中", "qualified": "合格",
    "planned": "待入库", "processing": "处理中", "completed": "已完成", "closed": "已关闭",
}

URGENCY_LABELS = {
    "urgent": "特急", "emergency": "紧急", "normal": "一般",
    "relaxed": "宽松", "completed": "已完成", "unscheduled": "待排期",
}


def _object_reference(value):
    if value is None:
        return None
    return {
        "objectId": value.pk,
        "objectType": value.__class__.__name__,
        "objectNo": value.object_no,
    }


def _first_related(value, related_name):
    relation = getattr(value, related_name, None)
    return relation.order_by("id").first() if relation is not None else None


def _source_and_target(value):
    if isinstance(value, PurchaseRequest):
        return None, (
            _first_related(value, "inquiries")
            or _first_related(value, "purchase_orders")
        )
    if isinstance(value, PurchaseInquiry):
        return value.source_purchase_request, (
            _first_related(value, "supplier_quotations")
            or _first_related(value, "price_approvals")
        )
    if isinstance(value, SupplierQuotation):
        return value.source_inquiry, None
    if isinstance(value, PriceApproval):
        return value.source_inquiry, _first_related(value, "purchase_orders")
    if isinstance(value, PurchaseOrder):
        return (
            value.source_purchase_request or value.source_price_approval,
            _first_related(value, "scm_receipts"),
        )
    if isinstance(value, PurchaseReceipt):
        return value.source_purchase_order, _first_related(value, "inspections")
    if isinstance(value, PurchaseInspection):
        return value.source_receipt, _first_related(value, "warehouse_inbounds")
    if isinstance(value, WarehouseInbound):
        return value.source_inspection, None
    return None, None


PURCHASE_REQUEST_REMARK_TAG = re.compile(r"\[(?:PurchaseRequestItem|SourcePurchaseRequest):[^\]]+\]")
PURCHASE_REQUEST_TRACE_KEYS = {
    "purchaseRequestId", "purchaseRequestNo", "purchaseRequestItemId", "purchaseRequestItemIds",
    "sourcePurchaseRequestId", "sourcePurchaseRequestNo", "sourcePurchaseRequestItemId",
    "sourceRequestId", "sourceRequestNo",
}


def _purchase_order_item_fact(order, row, read_user=None):
    remark = row.remark or ""
    request_item_match = re.search(r"\[PurchaseRequestItem:(\d+)\]", remark)
    request_no_match = re.search(r"\[SourcePurchaseRequest:([^\]]+)\]", remark)
    quotation_match = re.search(r"\[SourceQuotation:([^\]]+)\]", remark)
    relation_match = re.search(r"\[MaterialSupplierRelation:([^\]]+)\]", remark)
    price_source_match = re.search(r"\[PriceSource:([^\]]+)\]", remark)
    delivery_source_match = re.search(r"\[DeliverySource:([^\]]+)\]", remark)
    source_item = None
    if request_item_match:
        source_item = PurchaseRequestItem.objects.select_related(
            "purchase_request", "material"
        ).filter(pk=int(request_item_match.group(1))).first()
    is_manual_creation = order.source_type == "MANUAL_STANDARD_PURCHASE_ORDER_CREATION"
    if source_item is None and not is_manual_creation:
        request_no = request_no_match.group(1).strip() if request_no_match else ""
        if not request_no:
            legacy_match = re.search(r"\bPI-(\d{12,})", order.remark or "")
            request_no = f"PR{legacy_match.group(1)}" if legacy_match else ""
        if request_no and row.material_id:
            source_item = PurchaseRequestItem.objects.select_related(
                "purchase_request", "material"
            ).filter(purchase_request__request_no=request_no,
                     material_id=row.material_id).first()
    source_item = row.source_purchase_request_item or source_item
    if read_user is not None and source_item is not None and not reference_visible(read_user, source_item.purchase_request):
        source_item = None
    if read_user is not None and source_item is None:
        remark = PURCHASE_REQUEST_REMARK_TAG.sub("", remark).strip()
    material = row.material or (source_item.material if source_item else None)
    is_linked_standard = order.purchase_mode in {"STANDARD", "DIRECT", "AGREED_PRICE"} and bool(row.supplier_material_price_id)
    specification = (row.specification_snapshot if is_linked_standard else "") or (
        row.specification or (source_item.specification if source_item else "")
        or (material.specification if material else "") or ""
    )
    unit = (row.unit_snapshot if is_linked_standard else "") or (
        (material.unit if material else "") or (source_item.unit if source_item else "") or ""
    )
    price_source = price_source_match.group(1).strip() if price_source_match else ""
    delivery_source = delivery_source_match.group(1).strip() if delivery_source_match else ""
    if not delivery_source and source_item and row.expected_date == source_item.required_date:
        delivery_source = "PurchaseRequest.requiredDate"
    price_source_labels = {
        "SupplierQuoteItem.unitPrice": "供应商报价明细",
        "SupplierMaterialPrice": "供应商物料价格",
    }
    delivery_source_labels = {
        "SupplierQuote.deliveryDate": "供应商报价交期",
        "SupplierMaterialPrice.deliveryPeriod": "供应商物料交期",
        "PurchaseRequest.requiredDate": "采购申请需求日期",
    }
    return {
        "id": row.pk,
        "purchaseOrderId": order.pk,
        "poId": order.pk,
        "purchaseRequestItemId": source_item.pk if source_item else None,
        "sourcePurchaseRequestNo": source_item.purchase_request.request_no if source_item else "",
        "materialMasterId": material.pk if material else None,
        "materialMasterBound": bool(material),
        "materialMaintenanceStatus": "已维护" if material else "物料主数据未维护",
        "supplierMasterId": order.supplier_id,
        "supplierCode": (order.supplier_code_snapshot if is_linked_standard else order.supplier.code),
        "supplierName": (order.supplier_name_snapshot if is_linked_standard else order.supplier.name),
        "materialCode": (row.material_code_snapshot if is_linked_standard else "")
                        or (material.code if material else (source_item.material_code if source_item else "")),
        "materialName": (row.material_name_snapshot if is_linked_standard else "")
                        or row.product_name or (source_item.material_name if source_item else "")
                        or (material.name if material else ""),
        "specification": specification,
        "unit": unit,
        "quantity": str(row.quantity),
        "unitPrice": str(row.unit_price_snapshot if is_linked_standard else row.unit_price),
        "amount": str(row.amount),
        "supplierMaterialPriceId": row.supplier_material_price_id,
        "supplierMaterialPriceNo": (row.supplier_material_price.price_no
                                    if row.supplier_material_price_id else ""),
        "priceApprovalResultId": row.price_approval_result_id,
        "priceApprovalResultNo": (row.price_approval_result.result_no
                                  if row.price_approval_result_id else ""),
        "sourceQuoteComparisonId": (row.price_approval_result.original_source_reference
                                    if row.price_approval_result_id else ""),
        "priceEffectiveDate": (row.supplier_material_price.effective_date.isoformat()
                               if row.supplier_material_price_id else None),
        "taxRate": (str(row.tax_rate_snapshot) if row.tax_rate_snapshot is not None else ""),
        "currency": row.currency_snapshot,
        "plannedDeliveryDate": row.expected_date.isoformat() if row.expected_date else None,
        "expectedDate": row.expected_date.isoformat() if row.expected_date else None,
        "sourceQuotationNo": quotation_match.group(1).strip() if quotation_match else "",
        "materialSupplierRelationSource": relation_match.group(1).strip() if relation_match else "",
        "priceSource": price_source,
        "priceSourceLabel": price_source_labels.get(price_source, "来源未追溯"),
        "deliverySource": delivery_source,
        "deliverySourceLabel": delivery_source_labels.get(delivery_source, "来源未追溯"),
        "sourceTrace": {
            "sourceType": ("ManualSelection" if is_manual_creation else
                           ("PurchaseRequestItem" if source_item else "UNRESOLVED")),
            "sourceObjectId": source_item.pk if source_item else None,
            "sourceRequestNo": source_item.purchase_request.request_no if source_item else "",
            "materialMasterId": material.pk if material else None,
            "priceApprovalResultId": (row.price_approval_result.result_no
                                      if row.price_approval_result_id else None),
            "supplierMaterialPriceId": (row.supplier_material_price.price_no
                                        if row.supplier_material_price_id else None),
        },
        "remark": remark,
    }


def _normalized_object(value, read_user=None):
    source, target = _source_and_target(value)
    if read_user is not None:
        source = source if reference_visible(read_user, source) else None
        target = target if reference_visible(read_user, target) else None
        if isinstance(value, (PurchaseInquiry, SupplierQuotation)) and isinstance(target, PriceApproval):
            # The legacy approval is a different object from the authorized
            # preparation; this new read contract does not grant its details.
            target = None
    status_code = value.quotation_status if isinstance(value, SupplierQuotation) else value.status
    status_label = (
        value.get_quotation_status_display()
        if isinstance(value, SupplierQuotation)
        else STATUS_LABELS.get(status_code, value.get_status_display())
    )
    if isinstance(value, PurchaseOrder):
        quantity = exact_total(value.items,'quantity')
        amount = value.total_amount
        items = [_purchase_order_item_fact(value, row, read_user=read_user)
                 for row in value.items.select_related(
                     "material", "source_purchase_request_item__purchase_request",
                     "source_purchase_request_item__material", "price_approval_result",
                     "supplier_material_price",
                 ).all()]
    else:
        quantity = value.quantity
        amount = value.amount
        items = value.items
    normalized = {
        "objectId": value.pk,
        "objectType": value.__class__.__name__,
        "objectNo": value.object_no,
        "sourceObjectId": source.pk if source else None,
        "sourceObjectType": source.__class__.__name__ if source else None,
        "sourceObject": _object_reference(source),
        "targetObject": _object_reference(target),
        "statusCode": status_code,
        "statusLabel": status_label,
        "status": status_code,
        "items": items,
        "quantity": str(quantity),
        "amount": str(amount),
        "createdAt": value.created_at.isoformat() if value.created_at else None,
    }
    if isinstance(value, PurchaseOrder):
        gate_match = re.search(r"\bGate:([^;]+)", value.remark or "")
        snapshot_supplier = value.purchase_mode in {"STANDARD", "DIRECT", "AGREED_PRICE"} and value.price_trace_status == "CURRENT_LINKED"
        phone = (value.supplier_phone_snapshot if snapshot_supplier else value.supplier.contact_phone) or ""
        masked_phone = (f"{phone[:3]}****{phone[-4:]}" if len(phone) >= 7 else phone)
        source_trace = value.source_trace or {}
        source_reference = value.source_reference
        remark = value.remark or ""
        if read_user is not None:
            has_request_source = isinstance(source, PurchaseRequest)
            if not has_request_source:
                source_trace = {key: entry for key, entry in source_trace.items()
                                if key not in PURCHASE_REQUEST_TRACE_KEYS}
                if value.source_purchase_request_id or re.fullmatch(r"PR\d+", source_reference or ""):
                    source_reference = ""
                remark = PURCHASE_REQUEST_REMARK_TAG.sub("", remark)
            if "purchaseRequestIds" in source_trace:
                # Standard batch creation records request numbers in this array.
                # Release only the numbers proved by an authorized header or line.
                visible_numbers = {item["sourcePurchaseRequestNo"] for item in items
                                   if item["sourcePurchaseRequestNo"]}
                if has_request_source:
                    visible_numbers.add(source.request_no)
                trace_numbers = source_trace["purchaseRequestIds"]
                source_trace = {**source_trace, "purchaseRequestIds": [
                    number for number in trace_numbers if str(number) in visible_numbers
                ] if isinstance(trace_numbers, list) else []}
        normalized.update({
            "supplierId": value.supplier_id,
            "supplierCode": (value.supplier_code_snapshot if snapshot_supplier else value.supplier.code),
            "supplierName": (value.supplier_name_snapshot if snapshot_supplier else value.supplier.name),
            "supplierContact": ((value.supplier_contact_snapshot if snapshot_supplier
                                  else value.supplier.contact_person) or ""),
            "supplierPhone": masked_phone,
            "supplierAddress": ((value.supplier_address_snapshot if snapshot_supplier
                                 else value.supplier.address) or ""),
            "supplierDeliveryAddress": ((value.delivery_address_snapshot if snapshot_supplier
                                         else value.supplier.delivery_address) or ""),
            "supplierInformationSource": ("PurchaseOrder SupplierMaster Snapshot"
                                          if snapshot_supplier else "SupplierMaster"),
            "purchaseMode": value.purchase_mode,
            "purchaseModeLabel": value.get_purchase_mode_display(),
            "purchaseOrderTypeLabel": value.get_purchase_mode_display(),
            "priceTraceStatus": value.price_trace_status,
            "priceTraceStatusLabel": value.get_price_trace_status_display(),
            "priceSourceType": "SupplierMaterialPrice" if snapshot_supplier else "",
            "priceSourceLabel": "供应商物料有效价格" if snapshot_supplier else "来源未追溯",
            "sourceType": value.source_type,
            "sourceReference": source_reference,
            "sourcePurchaseRequestId": (value.source_purchase_request_id if read_user is None or source is not None else None),
            "sourcePurchaseRequestNo": (value.source_purchase_request.request_no
                                        if value.source_purchase_request_id and (read_user is None or source is not None) else ""),
            "sourceTrace": source_trace,
            "paymentTerms": str((value.source_trace or {}).get("paymentTerms") or ""),
            "deliveryAddress": ((value.delivery_address_snapshot if snapshot_supplier
                                  else value.supplier.delivery_address) or ""),
            "deliveryRequirements": str((value.source_trace or {}).get("deliveryRequirements") or ""),
            "remark": re.sub(r"^\[ManualCreation:[^\]]+\]\[SupplierMaterialPrice:[^\]]+\]\s*",
                             "", remark),
            "currency": next((item.get("currency") for item in items if item.get("currency")), ""),
            "buyerName": value.buyer or "",
            "purchaseDate": value.order_date.isoformat() if value.order_date else None,
            "orderDate": value.order_date.isoformat() if value.order_date else None,
            "deliveryDate": value.expected_date.isoformat() if value.expected_date else None,
            "plannedDeliveryDate": value.expected_date.isoformat() if value.expected_date else None,
            "earliestArrivalDate": value.expected_date.isoformat() if value.expected_date else None,
            "urgency": value.urgency_level,
            "urgencyLevel": value.urgency_level,
            "deliveryUrgency": value.urgency_level,
            "deliveryUrgencyCode": value.urgency_level,
            "deliveryUrgencyLabel": URGENCY_LABELS.get(value.urgency_level, "待确认"),
            "sourceGateId": (gate_match.group(1).strip() if gate_match else
                             str((value.source_trace or {}).get("gateCode") or "")),
            "totalQuantity": str(quantity),
            "totalAmount": str(amount),
        })
    if isinstance(value, PurchaseRequest):
        persisted_items = list(value.request_items.all())
        inquiry_eligible = value.status == "approved" and value.purchase_mode == "STANDARD"
        agreed_price_orders = list(value.purchase_orders.filter(purchase_mode="AGREED_PRICE").order_by("id"))
        agreed_price_created = bool(agreed_price_orders)
        if read_user is not None:
            agreed_price_orders = [order for order in agreed_price_orders if reference_visible(read_user, order)]
        agreed_price_ready = (value.status == "approved" and value.purchase_mode == "AGREED_PRICE"
                              and not agreed_price_created)
        lifecycle_status = ("purchase_order_created" if agreed_price_created
                            else "waiting_agreed_price_confirmation" if agreed_price_ready
                            else "approved" if value.status == "approved" else "created")
        lifecycle_label = ("已生成采购订单" if agreed_price_created
                           else "等待既定价格确认" if agreed_price_ready
                           else "已批准" if value.status == "approved" else "已创建")
        request_items = [{
            "purchaseRequestItemId": row.pk,
            "lineNo": row.line_no,
            "materialId": row.material_id,
            "materialCode": row.material_code,
            "materialName": row.material_name,
            "specification": row.specification,
            "unit": row.unit,
            "materialCategory": row.material_category,
            "purchaseAttribute": row.purchase_attribute,
            "suggestedSupplierId": row.suggested_supplier_id,
            "suggestedSupplierCode": row.suggested_supplier_code,
            "suggestedSupplierName": row.suggested_supplier_name,
            "supplierId": row.supplier_id,
            "supplierMaterialPriceId": row.supplier_material_price_id,
            "priceRecordCode": row.price_record_code,
            "unitPriceSnapshot": (str(row.unit_price_snapshot)
                                  if row.unit_price_snapshot is not None else ""),
            "taxRateSnapshot": (str(row.tax_rate_snapshot)
                                if row.tax_rate_snapshot is not None else ""),
            "currencySnapshot": row.currency_snapshot,
            "priceEffectiveDateSnapshot": (row.price_effective_date_snapshot.isoformat()
                                           if row.price_effective_date_snapshot else None),
            "demandReason": row.demand_reason,
            "technicalRequirements": row.technical_requirements,
            "brandRequirements": row.brand_requirements,
            "substituteRequirement": row.substitute_requirement,
            "substituteMaterialId": row.substitute_material_id,
            "substituteMaterialCode": row.substitute_material_code,
            "substituteMaterialName": row.substitute_material_name,
            "purchaseRemark": row.purchase_remark,
            "quantity": str(row.quantity),
            "requiredDate": row.required_date.isoformat(),
            "remark": row.remark,
        } for row in persisted_items] if persisted_items else (value.items or [])
        normalized.update({
            "requestNo": value.request_no,
            "requestDate": value.request_date.isoformat() if value.request_date else None,
            "requester": value.requester,
            "department": value.department,
            "purchaseDepartment": value.purchase_department,
            "usageDepartment": value.usage_department,
            "requesterEmployeeId": value.requester_employee_id,
            "requesterEmployeeNo": value.requester_employee_no,
            "departmentId": value.department_master_id,
            "usageDepartmentId": value.usage_department_master_id,
            "purchaseDepartmentId": value.purchase_department_master_id,
            "projectId": value.project_id,
            "projectCode": value.project_code,
            "projectName": value.project_name,
            "projectStage": value.project_stage,
            "projectOwner": value.project.owner if value.project_id else "",
            "costCenterId": value.cost_center_id,
            "costCenterCode": value.cost_center_code,
            "costCenterName": value.cost_center_name,
            "costCenterDepartmentName": value.cost_center.department.name if value.cost_center_id and value.cost_center.department_id else "",
            "expenseCategoryId": value.expense_category_id,
            "expenseCategoryCode": value.expense_category_code,
            "expenseCategoryName": value.expense_category_name,
            "budgetCategoryId": value.budget_category_id,
            "budgetCategoryCode": value.budget_category_code,
            "budgetCategoryName": value.budget_category_name,
            "applicationReason": value.application_reason,
            "purchasePurpose": value.purchase_purpose,
            "technicalDescription": value.technical_description,
            "deliveryRequirements": value.delivery_requirements,
            "noteDescription": value.note_description,
            "approvalStatus": value.approval_status,
            "approvalCurrentNode": value.approval_current_node,
            "approvalCurrentApprover": value.approval_current_approver,
            "approvalResult": value.approval_result,
            "businessLifecycleStatus": lifecycle_status,
            "businessLifecycleStatusLabel": lifecycle_label,
            "purchaseOrders": [{"id": order.pk, "purchaseOrderNo": order.po_no,
                                "supplierId": order.supplier_id}
                               for order in agreed_price_orders],
            "approvalHistory": [{
                "action": row.action,
                "fromStatus": row.from_status,
                "toStatus": row.to_status,
                "nodeName": row.node_name,
                "actor": row.actor,
                "comment": row.comment,
                "createdAt": row.created_at.isoformat(),
            } for row in value.approval_records.all()],
            "inquiryEligibility": {
                "eligible": inquiry_eligible,
                "reason": ("既定价格采购已审批，等待既定价格确认；禁止进入询价准备" if agreed_price_ready
                           else "审批通过，可进入询价准备" if inquiry_eligible else "采购申请尚未审批通过"),
                "nextStatus": ("AGREED_PRICE_PURCHASE_REQUEST_READY_FOR_PRICE_CONFIRMATION" if agreed_price_ready
                               else "INQUIRY_PREPARATION_READY" if inquiry_eligible else "PURCHASE_REQUEST_APPROVAL_PENDING"),
                "items": [{
                    "lineNo": item.line_no,
                    "materialCode": item.material_code,
                    "materialName": item.material_name,
                    "specification": item.specification,
                    "unit": item.unit,
                    "quantity": str(item.quantity),
                    "requiredDate": item.required_date.isoformat(),
                    "demandReason": item.demand_reason,
                    "technicalRequirements": item.technical_requirements,
                    "brandRequirements": item.brand_requirements,
                    "substituteRequirement": item.substitute_requirement,
                    "suggestedSupplierCode": item.suggested_supplier_code,
                    "suggestedSupplierName": item.suggested_supplier_name,
                } for item in persisted_items] if inquiry_eligible else [],
                "inquiryObjectCreated": False,
            },
            "requestType": value.request_type,
            "requestTypeLabel": value.get_request_type_display(),
            "purchaseMode": value.purchase_mode,
            "purchaseModeLabel": value.get_purchase_mode_display(),
            "sourceType": value.source_type,
            "sourceTypeLabel": value.get_source_type_display(),
            "items": request_items,
            "requiredDate": value.required_date.isoformat() if value.required_date else None,
            "totalQuantity": str(value.quantity),
            "materialSummary": "、".join(
                str(item.get("materialName") or item.get("materialCode") or item.get("materialId") or "物料")
                for item in request_items
            ),
        })
    if isinstance(value, SupplierQuotation):
        normalized.update({
            "quotationNo": value.quotation_no,
            "sourceInquiryId": value.source_inquiry_id,
            "sourceInquiryNo": value.source_inquiry.inquiry_no,
            "supplierId": value.supplier_id,
            "supplierName": value.supplier_name,
            "items": value.items,
            "quantity": str(value.quantity),
            "price": str(value.price),
            "currency": value.currency,
            "quotationStatus": value.quotation_status,
            "quotationStatusLabel": value.get_quotation_status_display(),
            "receivedAt": value.received_at.isoformat() if value.received_at else None,
            "createdAt": value.created_at.isoformat() if value.created_at else None,
        })
    if isinstance(value, PurchaseInquiry):
        quotation = value.quotation if isinstance(value.quotation, dict) else {}
        lines = value.items if isinstance(value.items, list) else []
        suppliers = quotation.get("supplierCandidates") or quotation.get("suppliers") or []
        if not suppliers and value.supplier:
            suppliers = [{"supplierCode": value.supplier, "supplierName": value.supplier}]
        sent = value.status in {"sent", "quoted", "approved", "closed"}
        quoted = value.status in {"quoted", "approved", "closed"}
        normalized.update({
            "inquiryNo": value.inquiry_no,
            "inquiryTitle": quotation.get("inquiryTitle") or f"{value.inquiry_no} 采购询价",
            "inquiryDate": value.created_at.date().isoformat() if value.created_at else None,
            "sourceRequestNo": value.source_purchase_request.request_no,
            "sourcePurchaseRequestId": value.source_purchase_request_id,
            "sourcePurchaseRequestNo": value.source_purchase_request.request_no,
            "materials": lines,
            "quantity": str(value.quantity),
            "demandDepartment": quotation.get("demandDepartment") or "",
            "purchaseDepartment": quotation.get("purchaseDepartment") or "",
            "createdAt": value.created_at.isoformat() if value.created_at else None,
            "buyerName": quotation.get("buyerName") or "",
            "supplierCount": len(suppliers),
            "lineCount": len(lines),
            "currency": quotation.get("currency") or "CNY",
            "runtimeState": quotation.get("runtimeState") or value.status,
            "supplierSendStatus": quotation.get("supplierSendStatus") or ("sent" if sent else "pending"),
            "supplierSendStatusLabel": quotation.get("supplierSendStatusLabel") or ("已发送" if sent else "待发送"),
            "quoteReceiveStatus": quotation.get("quoteReceiveStatus") or ("received" if quoted else "pending"),
            "quoteReceiveStatusLabel": quotation.get("quoteReceiveStatusLabel") or ("已接收" if quoted else "待接收"),
            "lines": lines,
            "suppliers": suppliers,
            "supplierCandidates": suppliers,
            "sourceEvidence": {
                "sourceType": "PurchaseRequest",
                "sourceRequestNo": value.source_purchase_request.request_no,
                "sourceObjectId": value.source_purchase_request_id,
            },
        })
    return normalized


def _positive_order_parameter(params, key, default):
    raw = params.get(key)
    if raw is None:
        return default
    if not re.fullmatch(r"[0-9]{1,12}", raw) or int(raw) < 1:
        raise ValidationError({key: "请输入正整数。"})
    return int(raw)


def _purchase_order_read_window(queryset, params, authorized_count):
    """Apply the requested window only to the proven order read scope."""
    if "order_id" in params:
        order_id = _positive_order_parameter(params, "order_id", None)
        order = queryset.filter(pk=order_id).first()
        if order is None:
            raise NotFound("未找到可查看的采购订单。")
        return [order], 1, 1, None

    if "page" not in params:
        return queryset[:100], authorized_count, 100, None

    page_number = _positive_order_parameter(params, "page", 1)
    page_size = _positive_order_parameter(params, "page_size", 10)
    if page_size > 100:
        raise ValidationError({"page_size": "每页最多 100 条。"})
    for key in ("order_no", "quick_order_no"):
        term = params.get(key, "").strip()
        if len(term) > 100:
            raise ValidationError({key: "采购订单编号不得超过 100 个字符。"})
        if term:
            queryset = queryset.filter(po_no__icontains=term)
    status_code = params.get("status", "").strip()
    if status_code:
        queryset = queryset.filter(status=status_code)

    paginator = Paginator(queryset, page_size)
    page = paginator.get_page(page_number)
    return page.object_list, paginator.count, page_size, {
        "number": page.number,
        "size": page_size,
        "pages": paginator.num_pages,
        "authorizedTotal": authorized_count,
    }


class ScmStandardPageFactsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, page_code):
        definition = PAGE_FACT_SOURCES.get(page_code)
        if definition is None:
            return Response({
                "success": False,
                "error": {"code": "SCM_PAGE_NOT_REGISTERED", "message": "页面未登记到SCM标准页面契约。"},
                "meta": {"source": "server", "productionUserDataWritten": False},
            }, status=404)

        model = definition["model"]
        ordering = ("-generated_at", "-fact_version") if model is QuoteComparisonFact else ("-id",)
        queryset = scoped_queryset(model.objects.all().order_by(*ordering), request.user,
                                   PAGE_READ_PERMISSIONS.get(page_code))
        record_count = queryset.count()
        result_limit = 100
        pagination = None
        if model is PurchaseOrder:
            window, record_count, result_limit, pagination = _purchase_order_read_window(
                queryset, request.query_params, record_count)
            rows = [_normalized_object(value, read_user=request.user) for value in window]
        elif model is QuoteComparisonFact:
            from .comparison_registration_service import serialize_registered_comparison
            rows = [serialize_registered_comparison(value) for value in queryset[:100]]
        else:
            rows = ([serialize_price_approval_preparation(value) for value in
            queryset.select_related("source_comparison")[:100]]
            if model is PriceApprovalPreparation
            else [_normalized_object(value, read_user=request.user) for value in queryset[:100]])
        api_endpoint = f"/api/procurement/scm-page-facts/{page_code}/"
        facts = {
            "version": SCM_STANDARD_PAGE_VERSION,
            "pageCode": page_code,
            "schema": definition["schema"],
            "factSource": "QuoteComparisonFact" if model is PriceApprovalPreparation else "server",
            "apiEndpoint": api_endpoint,
            "recordCount": record_count,
            "status": "available",
            "objects": rows,
            "resultLimit": result_limit,
            "fullScmScanPerformed": False,
            "dangerousActionCount": 0,
            "businessProgressWriteCount": 0,
            "productionUserDataWritten": False,
            "readScopeFacts": dict(READ_SCOPE_FACTS),
        }
        if pagination is not None:
            facts["pagination"] = pagination
        if page_code == "purchase-request":
            facts["itemCount"] = PurchaseRequestItem.objects.filter(purchase_request_id__in=queryset.values("pk")).count()
        if page_code == "purchase-inquiry":
            facts["eligibleSourceRequests"] = eligible_purchase_request_rows(read_user=request.user)
            facts["eligibleSourceRequestCount"] = len(facts["eligibleSourceRequests"])
            facts["eligibleSourceRequestCountScope"] = "RETURNED_AUTHORIZED_CANDIDATES"
        if page_code in {"supplier-quotation", "supplier-quote-workbench"}:
            facts["sourceInquiryRows"] = supplier_quotation_source_rows(read_user=request.user)
            facts["sourceInquiryRowCount"] = len(facts["sourceInquiryRows"])
            facts["sourceInquiryRowCountScope"] = "RETURNED_AUTHORIZED_CANDIDATE_ROWS"
        if page_code in {"purchase-inquiry", "supplier-quotation", "supplier-quote-workbench", "price-approval"}:
            facts["readScopeFacts"].update(
                contract="USER_APPROVED_SCM_THREE_READ_PERMISSIONS_20261116",
                readDoesNotAuthorizeExecution=True,
                sourceRange="ORIGINAL_AUTHORIZED_NATIVE_PURCHASE_REQUEST")
        return Response({
            "success": True,
            "data": facts,
            "error": None,
            "meta": {"module": "SCM", "source": "server", "readOnly": True},
        })
