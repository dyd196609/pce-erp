from django.db import transaction

from .models import PurchaseInquiry, PurchaseRequest


def _request_lines(request):
    persisted = list(request.request_items.all().order_by("line_no", "id"))
    if persisted:
        return [{
            "lineNo": row.line_no,
            "materialId": row.material_id,
            "materialCode": row.material_code,
            "materialName": row.material_name,
            "specification": row.specification,
            "unit": row.unit,
            "quantity": str(row.quantity),
            "requiredDate": row.required_date.isoformat(),
            "demandReason": row.demand_reason,
            "technicalRequirements": row.technical_requirements,
            "brandRequirements": row.brand_requirements,
            "suggestedSupplierId": row.suggested_supplier_id,
            "suggestedSupplierCode": row.suggested_supplier_code,
            "suggestedSupplierName": row.suggested_supplier_name,
        } for row in persisted]
    return list(request.items) if isinstance(request.items, list) else []


def _supplier_candidates(lines):
    candidates = {}
    for line in lines:
        code = str(line.get("suggestedSupplierCode") or "").strip()
        name = str(line.get("suggestedSupplierName") or "").strip()
        if not code and not name:
            continue
        key = code or name
        candidates[key] = {
            "supplierId": line.get("suggestedSupplierId"),
            "supplierCode": code,
            "supplierName": name,
            "source": "PurchaseRequestSuggestedSupplier",
            "selectionStatus": "candidate",
        }
    return list(candidates.values())


def build_inquiry_preparation_object(request):
    lines = _request_lines(request)
    candidates = _supplier_candidates(lines)
    return {
        "objectType": "InquiryPreparationObject",
        "preparationNo": f"IP-{request.request_no}",
        "sourcePurchaseRequestId": request.pk,
        "sourcePurchaseRequestNo": request.request_no,
        "sourceStatus": request.status,
        "sourceApprovalStatus": request.approval_status,
        "materials": lines,
        "supplierCandidates": candidates,
        "demandDepartment": request.usage_department or request.department,
        "purchaseDepartment": request.purchase_department,
        "status": "ready_for_inquiry",
    }


def validate_inquiry_creation_source(request, preparation):
    errors = []
    if request.purchase_mode != "STANDARD":
        errors.append("PURCHASE_MODE_NOT_ELIGIBLE_FOR_INQUIRY")
    if request.status != "approved" or request.approval_status != "completed":
        errors.append("PURCHASE_REQUEST_NOT_APPROVED")
    if not preparation["materials"]:
        errors.append("PURCHASE_REQUEST_MATERIALS_REQUIRED")
    if not preparation["supplierCandidates"]:
        errors.append("SUPPLIER_CANDIDATES_REQUIRED")
    return errors


@transaction.atomic
def create_purchase_inquiry_from_request(request_id, actor=""):
    request = PurchaseRequest.objects.select_for_update().get(pk=request_id)
    existing = PurchaseInquiry.objects.filter(source_purchase_request=request).order_by("id").first()
    if existing:
        return existing, False, build_inquiry_preparation_object(request)

    preparation = build_inquiry_preparation_object(request)
    errors = validate_inquiry_creation_source(request, preparation)
    if errors:
        raise ValueError(",".join(errors))

    inquiry_no = f"PI-{request.request_no[2:] if request.request_no.startswith('PR') else request.request_no}"
    candidates = preparation["supplierCandidates"]
    inquiry = PurchaseInquiry.objects.create(
        inquiry_no=inquiry_no,
        source_purchase_request=request,
        supplier=",".join(candidate["supplierCode"] or candidate["supplierName"] for candidate in candidates),
        quotation={
            "inquiryTitle": f"采购申请 {request.request_no} 询价",
            "buyerName": actor,
            "currency": "CNY",
            "sourcePurchaseRequestId": request.pk,
            "sourcePurchaseRequestNo": request.request_no,
            "demandDepartment": preparation["demandDepartment"],
            "purchaseDepartment": preparation["purchaseDepartment"],
            "supplierCandidates": candidates,
            "inquiryPreparation": {
                "objectType": preparation["objectType"],
                "preparationNo": preparation["preparationNo"],
                "status": preparation["status"],
            },
            "runtimeState": "inquiry_draft",
            "supplierSendStatus": "pending",
            "supplierSendStatusLabel": "待发送",
            "quoteReceiveStatus": "pending",
            "quoteReceiveStatusLabel": "待接收",
        },
        items=preparation["materials"],
        quantity=request.quantity,
        amount=0,
        status="draft",
    )
    return inquiry, True, preparation


def eligible_purchase_request_rows(*, read_user=None):
    queryset = PurchaseRequest.objects.filter(
        status="approved", approval_status="completed", purchase_mode="STANDARD",
    ).exclude(inquiries__isnull=False).prefetch_related("request_items").order_by("-id")
    if read_user is not None:
        from .fact_read_access import scoped_queryset
        from .scm_read_permission_catalog import INQUIRY_SCOPE
        queryset = scoped_queryset(queryset, read_user, INQUIRY_SCOPE)
    rows = []
    for request in queryset[:100]:
        preparation = build_inquiry_preparation_object(request)
        rows.append({
            "id": request.pk,
            "requestId": request.pk,
            "requestNo": request.request_no,
            "requestDate": request.request_date.isoformat(),
            "requester": request.requester,
            "demandDepartment": preparation["demandDepartment"],
            "purchaseDepartment": preparation["purchaseDepartment"],
            "materialCount": len(preparation["materials"]),
            "quantity": str(request.quantity),
            "supplierCandidateCount": len(preparation["supplierCandidates"]),
            "statusCode": request.status,
            "statusLabel": "已审批",
            "approvalStatus": request.approval_status,
            "inquiryPreparationStatus": preparation["status"],
            "actionCode": "CREATE_PURCHASE_INQUIRY_FROM_APPROVED_REQUEST",
        })
    return rows
