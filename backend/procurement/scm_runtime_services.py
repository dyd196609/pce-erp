from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import models, transaction
from django.db.models import Sum
from django.conf import settings
from django.core import signing
from django.utils import timezone

from masterdata.material_supplier_relation_runtime import MaterialSupplierRelationRuntime
from masterdata.models import Material, PriceApprovalResult, SupplierMaterialPrice
from pfm.formal_employee import formal_employee_queryset, is_formal_employee
from pfm.models import Employee

from .models import (
    InventoryBalance,
    InventoryLot,
    InventoryTransaction,
    PurchaseInspection,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequest,
    PurchaseRequestItem,
    PurchaseReceipt,
    Supplier,
    Warehouse,
    WarehouseInbound,
    WarehouseLocation,
)
from system.models import PositionWorkflowResponsibility
from workflow_runtime.models import WorkflowNodeDefinition
from .procurement_mode_router import DirectPurchaseAuthorization
from .business_action_control import authorize_action, record_action_audit


class ScmRuntimeActionError(Exception):
    def __init__(self, code, message, http_status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def _decimal(value, field_name, *, positive=False):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ScmRuntimeActionError("INVALID_QUANTITY", f"{field_name}不是有效数字")
    if positive and result <= 0:
        raise ScmRuntimeActionError("INVALID_QUANTITY", f"{field_name}必须大于0")
    return result


def _business_date():
    return timezone.localdate() if settings.USE_TZ else date.today()


def _next_number(prefix, model, field_name, *, include_test=False):
    day = (timezone.localdate() if settings.USE_TZ else date.today()).strftime("%Y%m%d")
    stem = f"{prefix}{day}"
    number_manager=model.all_objects if include_test else model.objects
    last = number_manager.filter(**{f"{field_name}__startswith": stem}).order_by(f"-{field_name}").first()
    sequence = 1
    if last:
        suffix = str(getattr(last, field_name) or "")[len(stem):]
        sequence = int(suffix) + 1 if suffix.isdigit() else number_manager.filter(**{f"{field_name}__startswith": stem}).count() + 1
    return f"{stem}{sequence:04d}"


def _identity_values(raw, payload):
    values = []
    for key in (
        "priceApprovalResultId", "priceApprovalResultNo",
    ):
        value = raw.get(key)
        if value not in (None, ""):
            values.append(str(value).strip())
    for key in (
        "priceApprovalResultIds", "priceApprovalResultNos",
    ):
        for value in raw.get(key) or payload.get(key) or []:
            if value not in (None, ""):
                values.append(str(value).strip())
    return {value for value in values if value}


def _result_identities(result):
    return {str(result.pk), result.result_no} - {""}


def _result_inquiry_no(result):
    preparation = result.preparation
    if not preparation:
        return ""
    if preparation.source_comparison_id:
        return str(preparation.source_comparison.source_inquiry_no or "").strip()
    return str((preparation.source_projection_snapshot or {}).get("sourceInquiryNo") or "").strip()


def _resolve_standard_effective_price(*, supplier, material, raw, payload, order_date):
    """Resolve only the PriceApprovalResult selected by this STANDARD flow."""
    candidates = list(PriceApprovalResult.objects.select_for_update().select_related(
        "preparation__source_comparison", "supplier", "material", "effective_price"
    ).filter(
        supplier=supplier, material=material, approval_conclusion="pass",
    ))
    explicit = _identity_values(raw, payload)
    if not explicit:
        raise ScmRuntimeActionError(
            "PRICE_APPROVAL_RESULT_IDENTITY_REQUIRED",
            f"物料{material.code}必须显式携带本次核价结果PAR编号或数据库ID",
        )
    candidates = [row for row in candidates if _result_identities(row) & explicit]
    if len(candidates) != 1:
        code = "PRICE_APPROVAL_RESULT_REQUIRED" if not candidates else "PRICE_APPROVAL_RESULT_NOT_UNIQUE"
        raise ScmRuntimeActionError(
            code,
            f"物料{material.code}无法唯一追溯本次核价结果（匹配{len(candidates)}条）",
        )
    result = candidates[0]
    try:
        price = result.effective_price
    except SupplierMaterialPrice.DoesNotExist:
        raise ScmRuntimeActionError(
            "SUPPLIER_MATERIAL_PRICE_REQUIRED",
            f"核价结果{result.result_no}尚未形成正式供应商物料有效价格",
        )
    if price.status != "ACTIVE":
        raise ScmRuntimeActionError("SUPPLIER_MATERIAL_PRICE_INACTIVE", f"有效价格{price.price_no}当前非有效状态")
    if price.effective_date > order_date or (price.expiry_date and price.expiry_date < order_date):
        raise ScmRuntimeActionError("SUPPLIER_MATERIAL_PRICE_DATE_INVALID", f"有效价格{price.price_no}不在订单日期有效期内")
    if price.supplier_id != supplier.pk or price.material_id != material.pk:
        raise ScmRuntimeActionError("SUPPLIER_MATERIAL_PRICE_MASTER_MISMATCH", f"有效价格{price.price_no}主数据身份不一致")
    if price.price_approval_result_id != result.pk:
        raise ScmRuntimeActionError("SUPPLIER_MATERIAL_PRICE_RESULT_MISMATCH", f"有效价格{price.price_no}未引用本次核价结果")
    return result, price


class PurchaseOrderCreationService:
    MANUAL_CREATION_MODE = "MANUAL_SELECTION"
    MANUAL_ADMISSION_SALT = "pce.purchase-order.manual-admission.v1"
    DIRECT_CREATION_MODE = "DIRECT_SELECTION"
    DIRECT_ADMISSION_SALT = "pce.purchase-order.direct-admission.v1"
    AGREED_PRICE_CREATION_MODE = "AGREED_PRICE_CONFIRMATION"
    AGREED_PRICE_ADMISSION_SALT = "pce.purchase-order.agreed-price-admission.v1"

    @staticmethod
    def _direct_identity(payload):
        rows = payload.get("items") if isinstance(payload.get("items"), list) else []
        return {
            "creationMode": str(payload.get("creationMode") or "").strip(),
            "purchaseMode": str(payload.get("purchaseMode") or "").strip(),
            "idempotencyKey": str(payload.get("idempotencyKey") or "").strip(),
            "supplierId": str(payload.get("supplierId") or "").strip(),
            "purchaseRequestId": str(payload.get("purchaseRequestId") or "").strip(),
            "orderDate": str(payload.get("orderDate") or "").strip(),
            "buyerEmployeeId": str(payload.get("buyerEmployeeId") or "").strip(),
            "items": [{
                "lineNo": index,
                "materialId": str(row.get("materialId") or "").strip(),
                "quantity": str(row.get("quantity") or "").strip(),
                "supplierMaterialPriceId": str(row.get("supplierMaterialPriceId") or "").strip(),
                "supplierMaterialPriceNo": str(row.get("supplierMaterialPriceNo") or "").strip(),
                "expectedDate": str(row.get("expectedDate") or "").strip(),
                "remark": str(row.get("remark") or "").strip(),
            } for index, row in enumerate(rows, start=1)],
        }

    @classmethod
    def _resolve_direct_context(cls, payload, user):
        identity = cls._direct_identity(payload)
        if identity["creationMode"] != cls.DIRECT_CREATION_MODE or identity["purchaseMode"] != "DIRECT":
            raise ScmRuntimeActionError("DIRECT_PURCHASE_CONTEXT_REQUIRED", "当前入口只允许直接采购创建上下文。")
        if not identity["idempotencyKey"]:
            raise ScmRuntimeActionError("PURCHASE_ORDER_IDEMPOTENCY_KEY_REQUIRED", "采购订单创建请求缺少幂等键。")
        try:
            supplier_id = int(identity["supplierId"])
        except (TypeError, ValueError):
            raise ScmRuntimeActionError("SUPPLIER_REQUIRED", "尚未选择供应商。")
        supplier = Supplier.objects.filter(pk=supplier_id, is_active=True).first()
        if not supplier:
            raise ScmRuntimeActionError("SUPPLIER_MASTER_NOT_FOUND", "该供应商不存在或未启用。")
        authorization = DirectPurchaseAuthorization.decide(user, supplier.company_id)
        if not authorization["allowed"]:
            raise ScmRuntimeActionError("DIRECT_PURCHASE_NOT_AUTHORIZED", authorization["reason"], 403)
        try:
            order_date = date.fromisoformat(identity["orderDate"])
        except (TypeError, ValueError):
            raise ScmRuntimeActionError("PURCHASE_ORDER_DATE_REQUIRED", "请选择采购日期。")
        try:
            buyer = formal_employee_queryset(company_id=supplier.company_id).get(
                pk=int(identity["buyerEmployeeId"]), position_ref__name__contains="采购"
            )
        except (TypeError, ValueError, Employee.DoesNotExist):
            raise ScmRuntimeActionError("PURCHASE_ORDER_BUYER_REQUIRED", "请选择正式人员档案中的在职采购员。")
        if not identity["items"]:
            raise ScmRuntimeActionError("PURCHASE_ORDER_LINES_REQUIRED", "直接采购订单至少需要一条物料明细。")
        relations = MaterialSupplierRelationRuntime.list_runtime_models()
        lines, checks, total, material_ids = [], [], Decimal("0.00"), set()
        for row in identity["items"]:
            line_no = row["lineNo"]
            try:
                material_id = int(row["materialId"])
                material = Material.objects.get(pk=material_id, is_active=True, is_purchased=True)
            except (TypeError, ValueError, Material.DoesNotExist):
                raise ScmRuntimeActionError("MATERIAL_MASTER_NOT_PURCHASABLE", f"第{line_no}行物料不存在、未启用或不允许采购。")
            if material.pk in material_ids:
                raise ScmRuntimeActionError("DIRECT_PURCHASE_DUPLICATE_MATERIAL", f"第{line_no}行物料与前序明细重复，请在同一行维护数量。")
            material_ids.add(material.pk)
            if not str(material.specification or "").strip() or not str(material.unit or "").strip():
                raise ScmRuntimeActionError("MATERIAL_MASTER_FIELDS_REQUIRED", f"第{line_no}行物料规格或单位未维护完整。")
            quantity = _decimal(row["quantity"], f"第{line_no}行采购数量", positive=True)
            try:
                expected_date = date.fromisoformat(row["expectedDate"])
            except (TypeError, ValueError):
                raise ScmRuntimeActionError("PURCHASE_ORDER_EXPECTED_DATE_REQUIRED", f"第{line_no}行请选择计划到货日期。")
            if expected_date < order_date:
                raise ScmRuntimeActionError("PURCHASE_ORDER_EXPECTED_DATE_INVALID", f"第{line_no}行计划到货日期不得早于采购日期。")
            try:
                price_id = int(row["supplierMaterialPriceId"])
            except (TypeError, ValueError):
                raise ScmRuntimeActionError("SUPPLIER_MATERIAL_PRICE_REQUIRED", f"第{line_no}行尚未选择正式价格批次。")
            price = SupplierMaterialPrice.objects.select_related("price_approval_result").filter(
                pk=price_id, price_no=row["supplierMaterialPriceNo"], supplier=supplier, material=material,
            ).first()
            if not price:
                raise ScmRuntimeActionError("SUPPLIER_MATERIAL_PRICE_MASTER_MISMATCH", f"第{line_no}行价格不属于当前供应商和物料。")
            if price.status != "ACTIVE" or price.effective_date > order_date or (price.expiry_date and price.expiry_date < order_date):
                raise ScmRuntimeActionError("SUPPLIER_MATERIAL_PRICE_DATE_INVALID", f"第{line_no}行价格在采购日期不可用。")
            current = SupplierMaterialPrice.objects.filter(
                supplier=supplier, material=material, currency=price.currency, status="ACTIVE",
                effective_date__lte=order_date,
            ).filter(models.Q(expiry_date__isnull=True) | models.Q(expiry_date__gte=order_date)).order_by(
                "confirmed_at", "created_at", "price_no", "id").last()
            if not current or current.pk != price.pk:
                raise ScmRuntimeActionError("HISTORICAL_SUPPLIER_MATERIAL_PRICE_BLOCKED", f"第{line_no}行选择了历史价格，不能用于新直接采购订单。")
            result = price.price_approval_result
            if result and result.approval_conclusion != "pass":
                raise ScmRuntimeActionError("PRICE_APPROVAL_RESULT_NOT_APPROVED", f"第{line_no}行价格对应的核价结果未通过。")
            if not result and price.price_source_type != "MANUAL_MAINTENANCE":
                raise ScmRuntimeActionError("PRICE_FORMAL_SOURCE_REQUIRED", f"第{line_no}行价格没有受治理的正式来源。")
            relation = next((value for value in relations if value.supplierId == supplier.pk
                             and value.materialId == material.pk and value.status == "enabled"), None)
            if not relation:
                raise ScmRuntimeActionError(
                    "MATERIAL_SUPPLIER_RELATION_REQUIRED", f"第{line_no}行供应商与物料没有正式供应关系。"
                )
            amount = (quantity * price.approved_price).quantize(Decimal("0.01"))
            total += amount
            lines.append({"lineNo": line_no, "material": material, "relation": relation,
                          "quantity": quantity, "expectedDate": expected_date, "price": price,
                          "priceApprovalResult": result, "amount": amount, "remark": row["remark"]})
            checks.append({"checkCode": "DIRECT_PURCHASE_LINE_ADMISSION", "checkName": f"第{line_no}行价格准入",
                           "currentValue": f"{material.code} / {price.price_no}", "result": "PASS",
                           "reason": f"第{line_no}行供应关系、数量、日期、当前正式价格及核价结果全部通过。"})
        checks.insert(0, {"checkCode": "DIRECT_PURCHASE_AUTHORIZATION", "checkName": "直接采购正式授权",
                          "currentValue": authorization["permissionCode"], "result": "PASS", "reason": authorization["reason"]})
        return {"identity": identity, "supplier": supplier, "buyer": buyer, "authorization": authorization,
                "orderDate": order_date, "lines": lines, "checks": checks, "totalAmount": total.quantize(Decimal("0.01"))}

    @classmethod
    @transaction.atomic
    def create_from_direct_request(cls, payload, user, *, preview=False):
        context = cls._resolve_direct_context(payload, user)
        identity = context["identity"]
        if preview:
            token = signing.dumps(identity, salt=cls.DIRECT_ADMISSION_SALT, compress=True)
            return [{"purchaseMode": "DIRECT", "gateStatus": "PASS", "gateCode": "DIRECT-PURCHASE-ORDER-GATE-R2",
                     "admissionToken": token, "checks": context["checks"], "itemCount": len(context["lines"]),
                     "totalAmount": str(context["totalAmount"]), "idempotencyKey": identity["idempotencyKey"]}], 0
        if payload.get("humanConfirmed") is not True:
            raise ScmRuntimeActionError("PURCHASE_ORDER_HUMAN_CONFIRMATION_REQUIRED", "当前采购信息尚未完成人工确认。")
        try:
            token_identity = signing.loads(str(payload.get("admissionToken") or ""), salt=cls.DIRECT_ADMISSION_SALT, max_age=1800)
        except signing.BadSignature:
            raise ScmRuntimeActionError("PURCHASE_ORDER_GATE_TOKEN_INVALID", "采购订单准入结果无效或已经过期，请重新检查。")
        if token_identity != identity:
            raise ScmRuntimeActionError("PURCHASE_ORDER_CONTEXT_CHANGED_AFTER_GATE", "准入后订单或明细发生变化，请重新检查。")
        existing = list(PurchaseOrder.objects.select_for_update().filter(
            source_type="DIRECT_PURCHASE_ORDER_CREATION",
            source_trace__idempotencyKey=identity["idempotencyKey"],
        ).select_related("supplier"))
        if not existing:
            existing = list(PurchaseOrder.objects.select_for_update().filter(
                source_type="DIRECT_PURCHASE_ORDER_CREATION",
                source_reference=identity["idempotencyKey"],
            ).select_related("supplier"))
        if existing:
            return existing, 0
        supplier = context["supplier"]
        request_no = _next_number("PR", PurchaseRequest, "request_no")
        request_value = PurchaseRequest.objects.create(
            request_no=request_no, request_date=context["orderDate"],
            requester=(str(getattr(user, "real_name", "") or "").strip()
                       or user.get_username() or f"User-{user.pk}")[:120],
            department="直接采购授权", purchase_department="采购部",
            usage_department="直接采购需求", request_type="other", source_type="ManualRequest",
            purchase_mode="DIRECT", required_date=max(line["expectedDate"] for line in context["lines"]),
            quantity=sum((line["quantity"] for line in context["lines"]), Decimal("0")),
            amount=context["totalAmount"], status="approved", approval_status="completed",
            approval_current_node="高管直接采购授权", approval_current_approver=user.get_username(),
            approval_result="通过", application_reason="直接采购工作台一次录入生成",
        )
        request_items = []
        legacy_items = []
        for line in context["lines"]:
            material, price = line["material"], line["price"]
            request_item = PurchaseRequestItem.objects.create(
                purchase_request=request_value, material=material, supplier=supplier,
                suggested_supplier=supplier, supplier_material_price=price,
                material_code=material.code, material_name=material.name,
                specification=material.specification, unit=material.unit,
                purchase_attribute="可采购", quantity=line["quantity"],
                required_date=line["expectedDate"], line_no=line["lineNo"],
                price_record_code=price.price_no, unit_price_snapshot=price.approved_price,
                tax_rate_snapshot=price.tax_rate, currency_snapshot=price.currency,
                price_effective_date_snapshot=price.effective_date,
                purchase_remark=line["remark"],
                remark=f"[SupplierMaterialPrice:{price.price_no}][PurchaseMode:DIRECT] {line['remark']}",
            )
            request_items.append(request_item)
            legacy_items.append({"lineNo": line["lineNo"], "supplierId": supplier.pk,
                "materialId": material.pk, "materialCode": material.code, "materialName": material.name,
                "quantity": str(line["quantity"]), "requiredDate": line["expectedDate"].isoformat(),
                "supplierMaterialPriceId": price.pk, "priceRecordCode": price.price_no,
                "unitPriceSnapshot": str(price.approved_price), "taxRateSnapshot": str(price.tax_rate),
                "currencySnapshot": price.currency})
        request_value.items = legacy_items
        request_value.save(update_fields=["items", "updated_at"])
        order = PurchaseOrder.objects.create(
            po_no=_next_number("PO", PurchaseOrder, "po_no"), supplier=supplier,
            order_date=context["orderDate"], expected_date=max(line["expectedDate"] for line in context["lines"]),
            status="draft", total_amount=context["totalAmount"], buyer=context["buyer"].full_name[:50],
            buyer_employee=context["buyer"],
            company_id=supplier.company_id, created_by=user.id, purchase_mode="DIRECT",
            source_type="DIRECT_PURCHASE_ORDER_CREATION", source_reference=request_value.request_no,
            source_purchase_request=request_value,
            source_trace={"creationMode": cls.DIRECT_CREATION_MODE, "explicitCreation": True, "humanConfirmed": True,
                          "gateCode": "DIRECT-PURCHASE-ORDER-GATE-R2", "gateStatus": "PASS",
                          "gateCheckedAt": timezone.now().isoformat(), "idempotencyKey": identity["idempotencyKey"],
                          "purchaseRequestId": request_value.pk, "purchaseRequestNo": request_value.request_no,
                          "supplierMaterialPriceIds": [line["price"].price_no for line in context["lines"]]},
            price_trace_status="CURRENT_LINKED", supplier_code_snapshot=supplier.code,
            supplier_name_snapshot=supplier.name, supplier_contact_snapshot=supplier.contact_person or "",
            supplier_phone_snapshot=supplier.contact_phone or "", supplier_address_snapshot=supplier.address or "",
            delivery_address_snapshot=str(payload.get("deliveryAddress") or supplier.delivery_address or ""),
            remark=f"[DirectCreation:{identity['idempotencyKey']}] {str(payload.get('remark') or '').strip()}",
        )
        for line, request_item in zip(context["lines"], request_items):
            material, price, result = line["material"], line["price"], line["priceApprovalResult"]
            PurchaseOrderItem.objects.create(
                po=order, material=material, source_purchase_request_item=request_item,
                price_approval_result=result, supplier_material_price=price,
                material_code_snapshot=material.code, material_name_snapshot=material.name,
                specification_snapshot=material.specification, unit_snapshot=material.unit,
                product_name=material.name, specification=material.specification, quantity=line["quantity"],
                unit_price=price.approved_price, unit_price_snapshot=price.approved_price,
                tax_rate_snapshot=price.tax_rate, currency_snapshot=price.currency, amount=line["amount"],
                expected_date=line["expectedDate"],
                remark=(f"[DirectLine:{line['lineNo']}]"
                        f"[MaterialSupplierRelation:{line['relation'].relationCode}]"
                        f"[PriceApprovalResult:{result.result_no if result else '-'}]"
                        f"[SupplierMaterialPrice:{price.price_no}]"
                        "[PriceSource:SupplierMaterialPrice]"),
            )
        # Record this new creation at its real transaction boundary.  Existing
        # orders returned above remain untouched; do not reconstruct history.
        record_action_audit(
            user=user, action_code="procurement.purchase_order.create",
            organization_id=order.company_id, target_type="PurchaseOrder",
            target_id=order.pk, target_no=order.po_no,
            before={"exists": False},
            after={
                "exists": True, "status": order.status,
                "purchaseMode": order.purchase_mode,
                "sourcePurchaseRequestId": request_value.pk,
                "sourcePurchaseRequestNo": request_value.request_no,
                "directCreationIdentity": identity,
                "purchaseOrderItemIds": list(order.items.values_list("pk", flat=True)),
            },
            authorization=context["authorization"],
            reason="原直接采购显式创建，记录真实制单人及准确来源；不批准或下达",
        )
        return [order], 1

    @classmethod
    def _agreed_price_identity(cls, payload):
        rows = payload.get("items") if isinstance(payload.get("items"), list) else []
        return {
            "creationMode": str(payload.get("creationMode") or "").strip(),
            "purchaseMode": str(payload.get("purchaseMode") or "").strip(),
            "purchaseRequestId": str(payload.get("purchaseRequestId") or "").strip(),
            "idempotencyKey": str(payload.get("idempotencyKey") or "").strip(),
            "orderDate": str(payload.get("orderDate") or "").strip(),
            "buyerEmployeeId": str(payload.get("buyerEmployeeId") or "").strip(),
            "items": [{
                "purchaseRequestItemId": str(row.get("purchaseRequestItemId") or "").strip(),
                "supplierMaterialPriceId": str(row.get("supplierMaterialPriceId") or "").strip(),
                "supplierMaterialPriceNo": str(row.get("supplierMaterialPriceNo") or "").strip(),
            } for row in rows],
        }

    @classmethod
    def _resolve_agreed_price_context(cls, payload, user):
        identity = cls._agreed_price_identity(payload)
        if (identity["creationMode"] != cls.AGREED_PRICE_CREATION_MODE
                or identity["purchaseMode"] != "AGREED_PRICE"):
            raise ScmRuntimeActionError(
                "AGREED_PRICE_CONTEXT_REQUIRED", "当前入口只允许既定价格采购确认上下文。"
            )
        if not identity["idempotencyKey"]:
            raise ScmRuntimeActionError(
                "PURCHASE_ORDER_IDEMPOTENCY_KEY_REQUIRED", "采购订单创建请求缺少幂等键。"
            )
        try:
            request_id = int(identity["purchaseRequestId"])
        except (TypeError, ValueError):
            raise ScmRuntimeActionError("PURCHASE_REQUEST_REQUIRED", "缺少来源采购申请。")
        request_value = PurchaseRequest.objects.select_for_update().filter(pk=request_id).first()
        if not request_value:
            raise ScmRuntimeActionError("PURCHASE_REQUEST_NOT_FOUND", "来源采购申请不存在。", 404)
        if request_value.purchase_mode != "AGREED_PRICE":
            raise ScmRuntimeActionError("PURCHASE_REQUEST_MODE_MISMATCH", "来源采购申请不是既定价格采购。")
        if request_value.status != "approved" or request_value.approval_status != "completed":
            raise ScmRuntimeActionError("PURCHASE_REQUEST_NOT_APPROVED", "来源采购申请尚未完成审批。")
        organization_id = (
            request_value.department_master.company_id if request_value.department_master_id
            else getattr(user, "company_id", None)
        )
        authorization = authorize_action(
            user=user,
            action_code="procurement.purchase_order.create",
            organization_id=organization_id,
            business_object={
                "organizationId": organization_id,
                "departmentId": request_value.purchase_department_master_id,
            },
        )
        if not authorization["allowed"]:
            raise ScmRuntimeActionError(
                authorization["decisionCode"], authorization["reason"], 403
            )
        try:
            order_date = date.fromisoformat(identity["orderDate"])
        except (TypeError, ValueError):
            raise ScmRuntimeActionError("PURCHASE_ORDER_DATE_REQUIRED", "采购订单日期无效。")
        try:
            buyer = formal_employee_queryset(company_id=organization_id).get(
                pk=int(identity["buyerEmployeeId"]), position_ref__name__contains="采购"
            )
        except (TypeError, ValueError, Employee.DoesNotExist):
            raise ScmRuntimeActionError("PURCHASE_ORDER_BUYER_REQUIRED", "请选择正式人员档案中的在职采购员。")
        request_items = list(request_value.request_items.select_related("material").order_by("line_no", "id"))
        if not request_items:
            raise ScmRuntimeActionError("PURCHASE_REQUEST_ITEMS_REQUIRED", "来源采购申请没有正式明细。")
        if len(identity["items"]) != len(request_items):
            raise ScmRuntimeActionError(
                "AGREED_PRICE_ITEM_COUNT_MISMATCH", "每条采购申请明细都必须明确选择一条正式价格。"
            )
        selected = {row["purchaseRequestItemId"]: row for row in identity["items"]}
        if len(selected) != len(request_items):
            raise ScmRuntimeActionError(
                "AGREED_PRICE_ITEM_SELECTION_DUPLICATE", "价格确认明细存在重复的采购申请行。"
            )
        relations = MaterialSupplierRelationRuntime.list_runtime_models()
        lines, checks, total = [], [], Decimal("0.00")
        for item in request_items:
            raw = selected.get(str(item.pk))
            if not raw:
                raise ScmRuntimeActionError(
                    "AGREED_PRICE_ITEM_SELECTION_REQUIRED", f"第{item.line_no}行尚未选择正式价格。"
                )
            material = item.material
            if not material or not material.is_active or not material.is_purchased:
                raise ScmRuntimeActionError(
                    "MATERIAL_MASTER_NOT_PURCHASABLE", f"第{item.line_no}行物料不存在、未启用或不允许采购。"
                )
            quantity = _decimal(item.quantity, f"第{item.line_no}行申请数量", positive=True)
            if not item.required_date or item.required_date < order_date:
                raise ScmRuntimeActionError(
                    "PURCHASE_ORDER_EXPECTED_DATE_INVALID", f"第{item.line_no}行计划到货日期不得早于采购订单日期。"
                )
            try:
                price_id = int(raw["supplierMaterialPriceId"])
            except (TypeError, ValueError):
                raise ScmRuntimeActionError(
                    "SUPPLIER_MATERIAL_PRICE_REQUIRED", f"第{item.line_no}行尚未选择正式价格记录。"
                )
            price = SupplierMaterialPrice.objects.select_related(
                "supplier", "material", "price_approval_result"
            ).filter(pk=price_id, price_no=raw["supplierMaterialPriceNo"], material=material).first()
            if not price or not price.supplier.is_active:
                raise ScmRuntimeActionError(
                    "SUPPLIER_MATERIAL_PRICE_MASTER_MISMATCH", f"第{item.line_no}行价格与物料或供应商主数据不一致。"
                )
            if price.status != "ACTIVE" or price.effective_date > order_date or (
                    price.expiry_date and price.expiry_date < order_date):
                raise ScmRuntimeActionError(
                    "SUPPLIER_MATERIAL_PRICE_DATE_INVALID", f"第{item.line_no}行价格在采购订单日期不是有效价格。"
                )
            current = SupplierMaterialPrice.objects.filter(
                supplier=price.supplier, material=material, currency=price.currency,
                status="ACTIVE", effective_date__lte=order_date,
            ).filter(models.Q(expiry_date__isnull=True) | models.Q(expiry_date__gte=order_date)).order_by(
                "confirmed_at", "created_at", "price_no", "id"
            ).last()
            if not current or current.pk != price.pk:
                raise ScmRuntimeActionError(
                    "HISTORICAL_SUPPLIER_MATERIAL_PRICE_BLOCKED", f"第{item.line_no}行选择了历史价格，不能用于新采购订单。"
                )
            relation = next((value for value in relations if value.supplierId == price.supplier_id
                             and value.materialId == material.pk and value.status == "enabled"), None)
            if not relation:
                raise ScmRuntimeActionError(
                    "MATERIAL_SUPPLIER_RELATION_REQUIRED", f"第{item.line_no}行供应商与物料没有正式供应关系。"
                )
            if (price.price_approval_result_id
                    and price.price_approval_result.approval_conclusion != "pass"):
                raise ScmRuntimeActionError(
                    "PRICE_APPROVAL_RESULT_NOT_APPROVED", f"第{item.line_no}行价格对应的核价结果未通过。"
                )
            if (not price.price_approval_result_id
                    and price.price_source_type != "MANUAL_MAINTENANCE"):
                raise ScmRuntimeActionError(
                    "PRICE_FORMAL_SOURCE_REQUIRED", f"第{item.line_no}行价格没有受治理的正式来源。"
                )
            amount = (quantity * price.approved_price).quantize(Decimal("0.01"))
            total += amount
            lines.append({"item": item, "material": material, "supplier": price.supplier,
                          "price": price, "relation": relation, "quantity": quantity,
                          "expectedDate": item.required_date, "amount": amount})
            checks.append({"checkCode": "AGREED_PRICE_LINE_ADMISSION",
                           "checkName": f"第{item.line_no}行既定价格准入",
                           "currentValue": f"{material.code} / {price.price_no}", "result": "PASS",
                           "reason": "申请明细、供应关系、当前正式价格、数量与计划到货日期全部通过。"})
        supplier_groups = {}
        for line in lines:
            supplier_groups.setdefault(line["supplier"].pk, []).append(line)
        checks.insert(0, {"checkCode": "AGREED_PRICE_PURCHASE_REQUEST_APPROVAL",
                          "checkName": "既定价格采购申请审批", "currentValue": request_value.request_no,
                          "result": "PASS", "reason": "采购申请已审批，采购方式为既定价格采购。"})
        checks.append({"checkCode": "AGREED_PRICE_SUPPLIER_SPLIT", "checkName": "按供应商拆单",
                       "currentValue": f"{len(supplier_groups)} 张采购订单", "result": "PASS",
                       "reason": "每张采购订单只包含一个正式供应商。"})
        return {"identity": identity, "request": request_value, "buyer": buyer, "orderDate": order_date,
                "lines": lines, "supplierGroups": supplier_groups, "checks": checks,
                "totalAmount": total.quantize(Decimal("0.01")), "user": user,
                "organizationId": organization_id, "authorization": authorization}

    @classmethod
    @transaction.atomic
    def create_from_agreed_price_request(cls, payload, user, *, preview=False):
        context = cls._resolve_agreed_price_context(payload, user)
        identity, request_value = context["identity"], context["request"]
        existing = list(PurchaseOrder.objects.select_for_update().filter(
            source_purchase_request=request_value, purchase_mode="AGREED_PRICE"
        ).select_related("supplier"))
        if preview and existing:
            raise ScmRuntimeActionError(
                "AGREED_PRICE_PURCHASE_ORDER_ALREADY_CREATED", "该采购申请已经生成正式采购订单，不得重复创建。"
            )
        if preview:
            token = signing.dumps(identity, salt=cls.AGREED_PRICE_ADMISSION_SALT, compress=True)
            return [{"purchaseMode": "AGREED_PRICE", "gateStatus": "PASS",
                     "gateCode": "AGREED-PRICE-PURCHASE-ORDER-GATE-R5", "admissionToken": token,
                     "checks": context["checks"], "itemCount": len(context["lines"]),
                     "supplierCount": len(context["supplierGroups"]),
                     "totalAmount": str(context["totalAmount"])}], 0
        if payload.get("humanConfirmed") is not True:
            raise ScmRuntimeActionError(
                "PURCHASE_ORDER_HUMAN_CONFIRMATION_REQUIRED", "当前采购信息尚未完成人工确认。"
            )
        try:
            token_identity = signing.loads(str(payload.get("admissionToken") or ""),
                                           salt=cls.AGREED_PRICE_ADMISSION_SALT, max_age=1800)
        except signing.BadSignature:
            raise ScmRuntimeActionError(
                "PURCHASE_ORDER_GATE_TOKEN_INVALID", "采购订单准入结果无效或已经过期，请重新检查。"
            )
        if token_identity != identity:
            raise ScmRuntimeActionError(
                "PURCHASE_ORDER_CONTEXT_CHANGED_AFTER_GATE", "准入后价格确认上下文发生变化，请重新检查。"
            )
        if existing:
            same_key = all((row.source_trace or {}).get("idempotencyKey") == identity["idempotencyKey"]
                           for row in existing)
            if same_key:
                return existing, 0
            raise ScmRuntimeActionError(
                "AGREED_PRICE_PURCHASE_ORDER_ALREADY_CREATED", "该采购申请已经生成正式采购订单，不得重复创建。"
            )
        orders = []
        for supplier_id, lines in context["supplierGroups"].items():
            supplier = lines[0]["supplier"]
            order = PurchaseOrder.objects.create(
                po_no=_next_number("PO", PurchaseOrder, "po_no"), supplier=supplier,
                order_date=context["orderDate"], expected_date=max(line["expectedDate"] for line in lines),
                status="draft", total_amount=sum((line["amount"] for line in lines), Decimal("0.00")),
                buyer=context["buyer"].full_name[:50], buyer_employee=context["buyer"],
                company_id=supplier.company_id,
                created_by=user.pk, purchase_mode="AGREED_PRICE",
                source_type="AGREED_PRICE_PURCHASE_CONFIRMATION", source_reference=request_value.request_no,
                source_purchase_request=request_value,
                source_trace={"creationMode": cls.AGREED_PRICE_CREATION_MODE, "explicitCreation": True,
                              "humanConfirmed": True, "gateCode": "AGREED-PRICE-PURCHASE-ORDER-GATE-R5",
                              "gateStatus": "PASS", "gateCheckedAt": timezone.now().isoformat(),
                              "idempotencyKey": identity["idempotencyKey"],
                              "purchaseRequestId": request_value.pk,
                              "purchaseRequestNo": request_value.request_no,
                              "supplierMaterialPriceIds": [line["price"].price_no for line in lines]},
                price_trace_status="CURRENT_LINKED", supplier_code_snapshot=supplier.code,
                supplier_name_snapshot=supplier.name, supplier_contact_snapshot=supplier.contact_person or "",
                supplier_phone_snapshot=supplier.contact_phone or "", supplier_address_snapshot=supplier.address or "",
                delivery_address_snapshot=supplier.delivery_address or "",
                remark=f"[AgreedPriceConfirmation:{identity['idempotencyKey']}] 来源采购申请 {request_value.request_no}",
            )
            for line in lines:
                item, material, price = line["item"], line["material"], line["price"]
                item.supplier = supplier
                item.supplier_material_price = price
                item.price_record_code = price.price_no
                item.unit_price_snapshot = price.approved_price
                item.tax_rate_snapshot = price.tax_rate
                item.currency_snapshot = price.currency
                item.price_effective_date_snapshot = price.effective_date
                item.save(update_fields=["supplier", "supplier_material_price", "price_record_code",
                                         "unit_price_snapshot", "tax_rate_snapshot", "currency_snapshot",
                                         "price_effective_date_snapshot"])
                PurchaseOrderItem.objects.create(
                    po=order, material=material, source_purchase_request_item=item,
                    price_approval_result=price.price_approval_result, supplier_material_price=price,
                    material_code_snapshot=material.code, material_name_snapshot=material.name,
                    specification_snapshot=item.specification, unit_snapshot=item.unit,
                    product_name=material.name, specification=item.specification, quantity=line["quantity"],
                    unit_price=price.approved_price, unit_price_snapshot=price.approved_price,
                    tax_rate_snapshot=price.tax_rate, currency_snapshot=price.currency,
                    amount=line["amount"], expected_date=item.required_date,
                    remark=(f"[PurchaseRequestItem:{item.pk}]"
                            f"[MaterialSupplierRelation:{line['relation'].relationCode}]"
                            f"[SupplierMaterialPrice:{price.price_no}]"
                            "[PurchaseMode:AGREED_PRICE]"),
                )
            record_action_audit(
                user=user,
                action_code="procurement.purchase_order.create",
                organization_id=context["organizationId"],
                target_type="PurchaseOrder",
                target_id=order.pk,
                target_no=order.po_no,
                before={
                    "exists": False,
                    "sourcePurchaseRequestId": request_value.pk,
                    "sourcePurchaseRequestNo": request_value.request_no,
                    "sourcePurchaseRequestStatus": request_value.status,
                },
                after={
                    "exists": True,
                    "status": order.status,
                    "purchaseMode": order.purchase_mode,
                    "sourcePurchaseRequestId": order.source_purchase_request_id,
                    "sourcePurchaseRequestNo": request_value.request_no,
                    "itemCount": order.items.count(),
                    "totalAmount": str(order.total_amount),
                },
                authorization=context["authorization"],
            )
            orders.append(order)
        return orders, len(orders)

    @staticmethod
    def _manual_identity(payload):
        return {
            "creationMode": str(payload.get("creationMode") or "").strip(),
            "purchaseMode": str(payload.get("purchaseMode") or "").strip(),
            "idempotencyKey": str(payload.get("idempotencyKey") or "").strip(),
            "supplierId": str(payload.get("supplierId") or "").strip(),
            "materialId": str(payload.get("materialId") or "").strip(),
            "quantity": str(payload.get("quantity") or "").strip(),
            "supplierMaterialPriceId": str(payload.get("supplierMaterialPriceId") or "").strip(),
            "supplierMaterialPriceNo": str(payload.get("supplierMaterialPriceNo") or "").strip(),
            "orderDate": str(payload.get("orderDate") or "").strip(),
            "expectedDate": str(payload.get("expectedDate") or "").strip(),
        }

    @classmethod
    def _resolve_manual_context(cls, payload):
        identity = cls._manual_identity(payload)
        if identity["creationMode"] != cls.MANUAL_CREATION_MODE:
            raise ScmRuntimeActionError(
                "PURCHASE_ORDER_CREATION_MODE_REQUIRED",
                "当前创建请求不是人工选择采购订单创建上下文。",
            )
        if identity["purchaseMode"] != "STANDARD":
            raise ScmRuntimeActionError(
                "PURCHASE_MODE_NOT_AVAILABLE",
                "当前批次仅开放STANDARD（标准采购）；既定价格采购和直接采购将在后续批次开放。",
            )
        if not identity["idempotencyKey"]:
            raise ScmRuntimeActionError(
                "PURCHASE_ORDER_IDEMPOTENCY_KEY_REQUIRED",
                "采购订单创建请求缺少幂等键。",
            )
        try:
            supplier_id = int(identity["supplierId"])
        except (TypeError, ValueError):
            raise ScmRuntimeActionError("SUPPLIER_REQUIRED", "尚未选择供应商。")
        supplier = Supplier.objects.filter(pk=supplier_id, is_active=True).first()
        if not supplier:
            raise ScmRuntimeActionError(
                "SUPPLIER_MASTER_NOT_FOUND",
                "该供应商尚未建立或启用正式供应商主数据，请先维护供应商资料。",
            )
        try:
            material_id = int(identity["materialId"])
        except (TypeError, ValueError):
            raise ScmRuntimeActionError("MATERIAL_REQUIRED", "尚未选择物料。")
        material = Material.objects.filter(
            pk=material_id, is_active=True, is_purchased=True,
        ).first()
        if not material:
            raise ScmRuntimeActionError(
                "MATERIAL_MASTER_NOT_PURCHASABLE",
                "该物料不存在、未启用或不允许采购。",
            )
        if not str(material.specification or "").strip() or not str(material.unit or "").strip():
            raise ScmRuntimeActionError(
                "MATERIAL_MASTER_FIELDS_REQUIRED",
                "所选物料的规格或单位尚未维护完整。",
            )
        relation = next((row for row in MaterialSupplierRelationRuntime.list_runtime_models()
                         if row.supplierId == supplier.pk and row.materialId == material.pk
                         and row.status == "enabled"), None)
        if relation is None:
            raise ScmRuntimeActionError(
                "MATERIAL_SUPPLIER_RELATION_REQUIRED",
                "当前供应商与该物料尚未建立正式供应关系。",
            )
        quantity = _decimal(identity["quantity"], "采购数量", positive=True)
        try:
            order_date = date.fromisoformat(identity["orderDate"])
        except (TypeError, ValueError):
            raise ScmRuntimeActionError("PURCHASE_ORDER_DATE_REQUIRED", "请选择采购日期。")
        try:
            expected_date = date.fromisoformat(identity["expectedDate"])
        except (TypeError, ValueError):
            raise ScmRuntimeActionError("PURCHASE_ORDER_EXPECTED_DATE_REQUIRED", "请选择计划到货日期。")
        if expected_date < order_date:
            raise ScmRuntimeActionError(
                "PURCHASE_ORDER_EXPECTED_DATE_INVALID",
                "计划到货日期不得早于采购日期。",
            )
        try:
            price_id = int(identity["supplierMaterialPriceId"])
        except (TypeError, ValueError):
            raise ScmRuntimeActionError(
                "SUPPLIER_MATERIAL_PRICE_REQUIRED",
                "尚未选择正式供应商物料价格批次。",
            )
        price = SupplierMaterialPrice.objects.select_related(
            "supplier", "material", "price_approval_result"
        ).filter(pk=price_id, price_no=identity["supplierMaterialPriceNo"]).first()
        if not price:
            raise ScmRuntimeActionError(
                "SUPPLIER_MATERIAL_PRICE_NOT_FOUND",
                "所选供应商物料价格批次不存在。",
            )
        if price.supplier_id != supplier.pk or price.material_id != material.pk:
            raise ScmRuntimeActionError(
                "SUPPLIER_MATERIAL_PRICE_MASTER_MISMATCH",
                "所选价格不属于当前供应商和物料。",
            )
        if price.status != "ACTIVE":
            raise ScmRuntimeActionError(
                "SUPPLIER_MATERIAL_PRICE_INACTIVE",
                "当前价格已经停用。",
            )
        if price.effective_date > order_date or (price.expiry_date and price.expiry_date < order_date):
            raise ScmRuntimeActionError(
                "SUPPLIER_MATERIAL_PRICE_DATE_INVALID",
                "当前价格不在采购日期的有效期内。",
            )
        current_prices = SupplierMaterialPrice.objects.filter(
            supplier=supplier, material=material, currency=price.currency, status="ACTIVE",
            effective_date__lte=order_date,
        ).filter(
            models.Q(expiry_date__isnull=True) | models.Q(expiry_date__gte=order_date)
        ).order_by("confirmed_at", "created_at", "price_no", "id")
        current_price = current_prices.last()
        if not current_price or current_price.pk != price.pk:
            raise ScmRuntimeActionError(
                "HISTORICAL_SUPPLIER_MATERIAL_PRICE_BLOCKED",
                "所选价格是历史价格，不能用于普通新采购订单。请选择当前适用价格。",
            )
        result = price.price_approval_result
        if result.approval_conclusion != "pass":
            raise ScmRuntimeActionError(
                "PRICE_APPROVAL_RESULT_NOT_APPROVED",
                "所选价格对应的核价结果未通过。",
            )
        amount = (quantity * price.approved_price).quantize(Decimal("0.01"))
        checks = [
            {"checkCode": "PURCHASE_ORDER_SUPPLIER_MASTER", "checkName": "供应商主数据",
             "currentValue": f"{supplier.code} / {supplier.name}", "result": "PASS", "reason": "正式供应商主数据已绑定。"},
            {"checkCode": "PURCHASE_ORDER_MATERIAL_MASTER", "checkName": "物料主数据",
             "currentValue": f"{material.code} / {material.name}", "result": "PASS", "reason": "正式可采购物料已绑定。"},
            {"checkCode": "MATERIAL_SUPPLIER_RELATION", "checkName": "物料供应商关系",
             "currentValue": relation.relationCode, "result": "PASS", "reason": "正式供应关系存在。"},
            {"checkCode": "PURCHASE_ORDER_QUANTITY", "checkName": "采购数量",
             "currentValue": str(quantity), "result": "PASS", "reason": "采购数量大于0。"},
            {"checkCode": "PURCHASE_ORDER_PRICE_ADMISSION", "checkName": "价格准入",
             "currentValue": price.price_no, "result": "PASS", "reason": "人工选择的当前适用正式价格已通过准入。"},
            {"checkCode": "PURCHASE_ORDER_CREATION_CONTEXT", "checkName": "创建上下文",
             "currentValue": identity["idempotencyKey"], "result": "PASS", "reason": "显式人工创建上下文完整。"},
        ]
        return {
            "identity": identity, "supplier": supplier, "material": material,
            "relation": relation, "quantity": quantity, "orderDate": order_date,
            "expectedDate": expected_date, "price": price, "priceApprovalResult": result,
            "amount": amount, "checks": checks,
        }

    @classmethod
    @transaction.atomic
    def create_from_manual_request(cls, payload, actor_id=None, *, preview=False):
        raise ScmRuntimeActionError(
            "MANUAL_STANDARD_CREATION_RETIRED",
            "旧人工STANDARD采购订单入口已经停用；标准采购必须沿完整业务流程进入。",
        )
        # Historical Batch2.2 implementation is intentionally retained below as
        # audit evidence, but is unreachable and cannot create new legacy rows.
        context = cls._resolve_manual_context(payload)
        identity = context["identity"]
        if preview:
            token = signing.dumps(identity, salt=cls.MANUAL_ADMISSION_SALT, compress=True)
            return [{
                "purchaseMode": "STANDARD",
                "gateStatus": "PASS",
                "gateCode": "PURCHASE-ORDER-GATE-001",
                "admissionToken": token,
                "checks": context["checks"],
                "idempotencyKey": identity["idempotencyKey"],
                "supplierId": context["supplier"].pk,
                "supplierCode": context["supplier"].code,
                "supplierName": context["supplier"].name,
                "materialSupplierRelationCode": context["relation"].relationCode,
                "materialId": context["material"].pk,
                "materialCode": context["material"].code,
                "materialName": context["material"].name,
                "specification": context["material"].specification,
                "unit": context["material"].unit,
                "quantity": str(context["quantity"]),
                "supplierMaterialPriceId": context["price"].pk,
                "supplierMaterialPriceNo": context["price"].price_no,
                "priceApprovalResultId": context["priceApprovalResult"].pk,
                "priceApprovalResultNo": context["priceApprovalResult"].result_no,
                "unitPrice": str(context["price"].approved_price),
                "taxRate": str(context["price"].tax_rate),
                "currency": context["price"].currency,
                "effectiveDate": context["price"].effective_date.isoformat(),
                "expiryDate": context["price"].expiry_date.isoformat() if context["price"].expiry_date else None,
                "amount": str(context["amount"]),
                "orderDate": context["orderDate"].isoformat(),
                "expectedDate": context["expectedDate"].isoformat(),
            }], 0
        if payload.get("humanConfirmed") is not True:
            raise ScmRuntimeActionError(
                "PURCHASE_ORDER_HUMAN_CONFIRMATION_REQUIRED",
                "当前采购信息尚未完成人工确认。",
            )
        token = str(payload.get("admissionToken") or "").strip()
        try:
            token_identity = signing.loads(
                token, salt=cls.MANUAL_ADMISSION_SALT, max_age=1800,
            )
        except signing.BadSignature:
            raise ScmRuntimeActionError(
                "PURCHASE_ORDER_GATE_TOKEN_INVALID",
                "采购订单准入结果无效或已经过期，请重新执行准入检查。",
            )
        if token_identity != identity:
            raise ScmRuntimeActionError(
                "PURCHASE_ORDER_CONTEXT_CHANGED_AFTER_GATE",
                "准入检查后采购信息发生变化，请重新执行准入检查。",
            )
        existing = list(PurchaseOrder.objects.select_for_update().filter(
            source_type="MANUAL_STANDARD_PURCHASE_ORDER_CREATION",
            source_reference=identity["idempotencyKey"],
        ).select_related("supplier").order_by("id"))
        if existing:
            return existing, 0
        supplier = context["supplier"]
        material = context["material"]
        price = context["price"]
        result = context["priceApprovalResult"]
        order = PurchaseOrder.objects.create(
            po_no=_next_number("PO", PurchaseOrder, "po_no"),
            supplier=supplier,
            order_date=context["orderDate"],
            expected_date=context["expectedDate"],
            status="draft",
            total_amount=context["amount"],
            buyer=str(payload.get("buyer") or payload.get("confirmedBy") or "")[:50],
            company_id=supplier.company_id,
            created_by=actor_id,
            purchase_mode="STANDARD",
            source_type="MANUAL_STANDARD_PURCHASE_ORDER_CREATION",
            source_reference=identity["idempotencyKey"],
            source_trace={
                "creationMode": cls.MANUAL_CREATION_MODE,
                "explicitCreation": True,
                "humanConfirmed": True,
                "gateCode": "PURCHASE-ORDER-GATE-001",
                "gateStatus": "PASS",
                "gateCheckedAt": timezone.now().isoformat(),
                "materialSupplierRelationCode": context["relation"].relationCode,
                "priceApprovalResultIds": [result.result_no],
                "supplierMaterialPriceIds": [price.price_no],
                "paymentTerms": str(payload.get("paymentTerms") or ""),
                "deliveryRequirements": str(payload.get("deliveryRequirements") or ""),
            },
            price_trace_status="CURRENT_LINKED",
            supplier_code_snapshot=supplier.code,
            supplier_name_snapshot=supplier.name,
            supplier_contact_snapshot=supplier.contact_person or "",
            supplier_phone_snapshot=supplier.contact_phone or "",
            supplier_address_snapshot=supplier.address or "",
            delivery_address_snapshot=(str(payload.get("deliveryAddress") or "").strip()
                                       or supplier.delivery_address or ""),
            remark=(f"[ManualCreation:{identity['idempotencyKey']}]"
                    f"[SupplierMaterialPrice:{price.price_no}] "
                    f"{str(payload.get('remark') or '').strip()}"),
        )
        PurchaseOrderItem.objects.create(
            po=order,
            material=material,
            source_purchase_request_item=None,
            price_approval_result=result,
            supplier_material_price=price,
            material_code_snapshot=material.code,
            material_name_snapshot=material.name,
            specification_snapshot=material.specification,
            unit_snapshot=material.unit,
            product_name=material.name,
            specification=material.specification,
            quantity=context["quantity"],
            unit_price=price.approved_price,
            unit_price_snapshot=price.approved_price,
            tax_rate_snapshot=price.tax_rate,
            currency_snapshot=price.currency,
            amount=context["amount"],
            expected_date=context["expectedDate"],
            remark=(f"[MaterialMaster:{material.pk}]"
                    f"[SupplierMaster:{supplier.pk}]"
                    f"[MaterialSupplierRelation:{context['relation'].relationCode}]"
                    f"[PriceApprovalResult:{result.result_no}]"
                    f"[SupplierMaterialPrice:{price.price_no}]"
                    "[PriceSource:SupplierMaterialPrice]"),
        )
        return [order], 1

    @staticmethod
    @transaction.atomic
    def create_from_gate_request(payload, actor_id=None, *, preview=False):
        request_id = str(payload.get("requestId") or "").strip()
        gate_id = str(payload.get("gateId") or "").strip()
        admission_result_id = str(payload.get("admissionResultId") or "").strip()
        if not request_id or not gate_id or not admission_result_id:
            raise ScmRuntimeActionError(
                "GATE_CREATION_REQUEST_REQUIRED",
                "采购订单创建请求缺少Gate或准入结果来源",
            )
        if payload.get("status") != "PENDING_CONFIRMATION":
            raise ScmRuntimeActionError(
                "GATE_CREATION_REQUEST_NOT_CONFIRMABLE",
                "采购订单创建请求当前不可确认",
            )

        marker = f"[CreationRequest:{request_id}]"
        raw_groups = payload.get("supplierGroups")
        if not isinstance(raw_groups, list) or not raw_groups:
            raise ScmRuntimeActionError(
                "PURCHASE_ORDER_SUPPLIER_GROUPS_REQUIRED",
                "采购订单创建请求缺少Gate供应商拆单事实",
            )
        supplier_codes = [str(group.get("supplierCode") or "").strip() for group in raw_groups]
        if any(not code for code in supplier_codes) or len(set(supplier_codes)) != len(supplier_codes):
            raise ScmRuntimeActionError("SUPPLIER_SPLIT_INVALID", "Gate供应商拆单存在空值或重复供应商")

        if not preview:
            existing = list(PurchaseOrder.objects.select_for_update().filter(
                remark__contains=marker
            ).select_related("supplier").order_by("id"))
            if not existing:
                existing = list(PurchaseOrder.objects.select_for_update().filter(
                    purchase_mode="STANDARD", source_trace__gateId=gate_id,
                ).select_related("supplier").order_by("id"))
            if existing:
                if len(existing) != len(raw_groups):
                    raise ScmRuntimeActionError(
                        "SUPPLIER_SPLIT_IDEMPOTENCY_CONFLICT",
                        "同一创建请求的历史订单数量与当前供应商拆单数量不一致",
                    )
                from .formal_price_confirmation_service import validate_creation_replay
                from .comparison_registration_service import ComparisonRegistrationError
                try:
                    validate_creation_replay(existing,payload,actor_id)
                except ComparisonRegistrationError as error:
                    raise ScmRuntimeActionError(error.code,str(error),error.http_status) from error
                return existing, 0

        prepared = []
        order_date = timezone.localdate() if settings.USE_TZ else date.today()
        resolved_supplier_ids = set()
        source_request_nos = [str(value or "").strip()
                              for value in (payload.get("purchaseRequestIds") or [])
                              if str(value or "").strip()]
        source_inquiry_ids = payload.get("inquiryIds") or []
        for group_index, group in enumerate(raw_groups, start=1):
            try:
                supplier_id = int(group.get("supplierId"))
            except (TypeError, ValueError):
                raise ScmRuntimeActionError("SUPPLIER_REQUIRED", f"第{group_index}家供应商未完成人工主数据确认")
            supplier = Supplier.objects.filter(pk=supplier_id, is_active=True).first()
            if not supplier:
                raise ScmRuntimeActionError("SUPPLIER_NOT_FOUND", f"第{group_index}家供应商不存在或已停用")
            if supplier.pk in resolved_supplier_ids:
                raise ScmRuntimeActionError(
                    "SUPPLIER_SPLIT_DUPLICATE_MASTER",
                    f"多个Gate供应商被映射到同一正式供应商{supplier.code}，已阻断重复拆单",
                )
            resolved_supplier_ids.add(supplier.pk)
            raw_lines = group.get("materialLines")
            if not isinstance(raw_lines, list) or not raw_lines:
                raise ScmRuntimeActionError("PURCHASE_ORDER_LINES_REQUIRED", f"供应商{supplier.code}没有所属物料明细")
            lines = []
            for line_index, raw in enumerate(raw_lines, start=1):
                material_code = str(raw.get("materialCode") or "").strip()
                request_no = str(raw.get("sourceRequestNo") or "").strip()
                allowed_request_nos = [request_no] if request_no else source_request_nos
                if not material_code or not allowed_request_nos:
                    raise ScmRuntimeActionError(
                        "PURCHASE_REQUEST_ITEM_SOURCE_REQUIRED",
                        f"第{group_index}组第{line_index}行缺少采购申请物料来源身份",
                    )
                source_items = list(PurchaseRequestItem.objects.select_related(
                    "purchase_request", "material"
                ).filter(
                    purchase_request__request_no__in=allowed_request_nos,
                    material_code=material_code,
                )[:2])
                if len(source_items) != 1:
                    raise ScmRuntimeActionError(
                        "PURCHASE_REQUEST_ITEM_SOURCE_NOT_UNIQUE",
                        f"物料{material_code}无法唯一映射到采购申请明细",
                    )
                source_item = source_items[0]
                material = source_item.material
                if not material or str(material.code or "").strip() != material_code:
                    raise ScmRuntimeActionError(
                        "MATERIAL_MASTER_NOT_MAINTAINED",
                        f"物料{material_code}主数据未维护",
                    )
                if not material.is_active or not material.is_purchased:
                    raise ScmRuntimeActionError(
                        "MATERIAL_MASTER_NOT_PURCHASABLE",
                        f"物料{material_code}不是启用的可采购物料",
                    )
                specification = str(source_item.specification or material.specification or "").strip()
                unit = str(material.unit or source_item.unit or "").strip()
                if not specification or not unit:
                    raise ScmRuntimeActionError(
                        "MATERIAL_MASTER_FIELDS_REQUIRED",
                        f"物料{material_code}的规格或单位未维护",
                    )
                quantity = _decimal(source_item.quantity, f"第{group_index}组第{line_index}行数量", positive=True)
                price_result, effective_price = _resolve_standard_effective_price(
                    supplier=supplier, material=material, raw=raw, payload=payload,
                    order_date=order_date,
                )
                from .formal_price_confirmation_service import is_native_result, validate_standard_line
                if is_native_result(price_result):
                    from .comparison_registration_service import ComparisonRegistrationError
                    try:
                        validate_standard_line(result=price_result,price=effective_price,item=source_item,quantity=quantity,
                            unit=unit,order_date=order_date,raw=raw,payload=payload,actor_id=actor_id)
                    except ComparisonRegistrationError as error:
                        raise ScmRuntimeActionError(error.code,str(error),error.http_status) from error
                supplied_price_no = str(raw.get("supplierMaterialPriceNo") or "").strip()
                supplied_currency = str(raw.get("currency") or "").strip()
                supplied_effective_date = str(raw.get("effectiveDate") or "").strip()
                if (
                    supplied_price_no != effective_price.price_no
                    or _decimal(raw.get("unitPrice"), "创建上下文价格", positive=True)
                    != effective_price.approved_price
                    or _decimal(raw.get("taxRate"), "创建上下文税率") != effective_price.tax_rate
                    or supplied_currency != effective_price.currency
                    or supplied_effective_date != effective_price.effective_date.isoformat()
                ):
                    raise ScmRuntimeActionError(
                        "STANDARD_PRICE_VALUE_CONSISTENCY_FAILED",
                        f"物料{material_code}的可见创建上下文与{effective_price.price_no}当前值不一致",
                    )
                unit_price = effective_price.approved_price
                expected_date = source_item.required_date
                lines.append({
                    "material": material,
                    "source_purchase_request_item": source_item,
                    "price_approval_result": price_result,
                    "supplier_material_price": effective_price,
                    "product_name": str(material.name)[:200],
                    "specification": specification[:200],
                    "material_code_snapshot": str(material.code)[:50],
                    "material_name_snapshot": str(material.name)[:200],
                    "specification_snapshot": specification[:200],
                    "unit_snapshot": unit[:40],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "unit_price_snapshot": unit_price,
                    "tax_rate_snapshot": effective_price.tax_rate,
                    "currency_snapshot": effective_price.currency,
                    "amount": (quantity * unit_price).quantize(Decimal("0.01")),
                    "expected_date": expected_date,
                    "remark": (f"[PurchaseRequestItem:{source_item.pk}]"
                               f"[SourcePurchaseRequest:{source_item.purchase_request.request_no}]"
                               f"[MaterialMaster:{material.pk}]"
                               f"[Unit:{unit}]"
                               f"[SupplierMaster:{supplier.pk}]"
                               f"[PriceApprovalResult:{price_result.result_no}]"
                               f"[SupplierMaterialPrice:{effective_price.price_no}]"
                               f"[PriceSource:SupplierMaterialPrice]"
                               f"[DeliverySource:PurchaseRequest.requiredDate] "
                               f"采购申请来源物料：{material_code}"),
                })
            prepared.append((group, supplier, lines))

        if preview:
            contexts = []
            for group, supplier, lines in prepared:
                for line in lines:
                    source_item = line["source_purchase_request_item"]
                    result = line["price_approval_result"]
                    price = line["supplier_material_price"]
                    contexts.append({
                        "purchaseMode": "STANDARD",
                        "purchaseRequestNo": source_item.purchase_request.request_no,
                        "purchaseRequestItemId": source_item.pk,
                        "priceApprovalResultId": result.pk,
                        "priceApprovalResultNo": result.result_no,
                        "supplierMaterialPriceId": price.pk,
                        "supplierMaterialPriceNo": price.price_no,
                        "supplierId": supplier.pk,
                        "supplierCode": supplier.code,
                        "supplierName": supplier.name,
                        "materialId": line["material"].pk,
                        "materialCode": line["material_code_snapshot"],
                        "materialName": line["material_name_snapshot"],
                        "quantity": str(line["quantity"]),
                        "unitPrice": str(price.approved_price),
                        "taxRate": str(price.tax_rate),
                        "currency": price.currency,
                        "effectiveDate": price.effective_date.isoformat(),
                        "expiryDate": price.expiry_date.isoformat() if price.expiry_date else None,
                        "priceValueConsistent": (
                            line["unit_price"] == price.approved_price
                            and line["unit_price_snapshot"] == price.approved_price
                            and line["tax_rate_snapshot"] == price.tax_rate
                            and line["currency_snapshot"] == price.currency
                        ),
                    })
            if not contexts or any(not row["priceValueConsistent"] for row in contexts):
                raise ScmRuntimeActionError(
                    "STANDARD_PRICE_VALUE_CONSISTENCY_FAILED",
                    "标准采购价格、快照、税率或币种与唯一SupplierMaterialPrice不一致",
                )
            return contexts, 0

        orders = []
        for group, supplier, lines in prepared:
            supplier_code = str(group.get("supplierCode") or "").strip()
            supplier_name = str(group.get("supplierName") or "").strip()
            order = PurchaseOrder.objects.create(
                po_no=_next_number("PO", PurchaseOrder, "po_no"),
                supplier=supplier,
                order_date=order_date,
                expected_date=min(line["expected_date"] for line in lines),
                status="draft",
                total_amount=sum((line["amount"] for line in lines), Decimal("0")),
                buyer=str(payload.get("confirmedBy") or "")[:50],
                company_id=supplier.company_id,
                created_by=actor_id,
                purchase_mode="STANDARD",
                source_type="STANDARD_PURCHASE_FLOW",
                source_reference=request_id,
                source_trace={
                    "purchaseRequestIds": source_request_nos,
                    "inquiryIds": [str(value) for value in source_inquiry_ids],
                    "quoteComparisonIds": [str(value) for value in (payload.get("quoteComparisonIds") or [])],
                    "priceApprovalResultIds": [line["price_approval_result"].result_no for line in lines],
                    "supplierMaterialPriceIds": [line["supplier_material_price"].price_no for line in lines],
                    "gateId": gate_id,
                    "admissionResultId": admission_result_id,
                    "creationRequestId": request_id,
                },
                price_trace_status="CURRENT_LINKED",
                supplier_code_snapshot=supplier.code,
                supplier_name_snapshot=supplier.name,
                supplier_contact_snapshot=supplier.contact_person or "",
                supplier_phone_snapshot=supplier.contact_phone or "",
                supplier_address_snapshot=supplier.address or "",
                delivery_address_snapshot=supplier.delivery_address or "",
                remark=(f"{marker}[GateSupplier:{supplier_code}] Gate:{gate_id}; "
                        f"Admission:{admission_result_id}; Gate供应商:{supplier_code}/{supplier_name}"),
            )
            PurchaseOrderItem.objects.bulk_create([
                PurchaseOrderItem(po=order, **line) for line in lines
            ])
            from .formal_price_confirmation_service import record_standard_creation
            from .comparison_registration_service import ComparisonRegistrationError
            try:
                record_standard_creation(order,payload,actor_id)
            except ComparisonRegistrationError as error:
                raise ScmRuntimeActionError(error.code,str(error),error.http_status) from error
            orders.append(order)
        return orders, len(orders)

    @staticmethod
    @transaction.atomic
    def create_from_price_approval(approval_id, actor_id=None):
        raise ScmRuntimeActionError(
            "STANDARD_PURCHASE_GATE_REQUIRED",
            "旧核价直建订单入口已关闭：标准采购必须从正式Gate引用SupplierMaterialPrice创建",
            409,
        )


def _order_business_fact(order):
    return {
        "organizationId": order.company_id,
        "companyId": order.company_id,
        "departmentId": order.purchase_department_id or order.department_id,
        "ownerUserId": order.created_by,
    }


def _authorize_fulfillment(*, user, action_code, order):
    decision = authorize_action(
        user=user, action_code=action_code, organization_id=order.company_id,
        business_object=_order_business_fact(order),
    )
    if not decision.get("allowed"):
        raise ScmRuntimeActionError(decision.get("decisionCode", "PERMISSION_DENIED"), decision.get("reason", "无权执行该业务动作"), 403)
    employee = _fulfillment_actor(user=user, action_code=action_code, company_id=order.company_id)
    return decision, employee


def _fulfillment_actor(*, user, action_code, company_id):
    """Original execution identity/duty contract, shared with source discovery."""
    employee = getattr(user, "employee_profile", None)
    position = getattr(employee, "position_ref", None) if employee else None
    if not is_formal_employee(employee, company_id=company_id):
        raise ScmRuntimeActionError("EXECUTION_IDENTITY_INCOMPLETE", "当前账号没有有效的员工—岗位任职关系，禁止形成业务执行事实", 403)
    node = WorkflowNodeDefinition.objects.filter(
        process_definition__definition_code="PROCUREMENT_PURCHASE_REQUEST_TO_ORDER",
        business_action_code=action_code, active=True,
    ).first()
    if not node or not PositionWorkflowResponsibility.objects.filter(
        position=position, workflow_node=node, active=True,
        responsibility__is_active=True, responsibility__status="ACTIVE",
    ).exists():
        raise ScmRuntimeActionError("POSITION_RESPONSIBILITY_DENIED", "当前岗位没有该正式流程节点的有效职责关系", 403)
    return employee


def _receipt_line_items(order, current):
    prior = {}
    for receipt_items in order.scm_receipts.values_list("items", flat=True):
        for row in receipt_items or []:
            item_id = int(row.get("purchaseOrderItemId") or 0)
            prior[item_id] = prior.get(item_id, Decimal("0")) + _decimal(row.get("quantity") or 0, "历史收货数量")
    remaining = current
    result = []
    for item in order.items.select_related("material").order_by("id"):
        available = item.quantity - prior.get(item.pk, Decimal("0"))
        allocated = min(max(available, Decimal("0")), remaining)
        if allocated <= 0:
            continue
        unit_price = item.unit_price_snapshot if item.unit_price_snapshot is not None else item.unit_price
        result.append({
            "purchaseOrderItemId": item.pk,
            "materialId": item.material_id,
            "materialCode": item.material_code_snapshot or getattr(item.material, "code", ""),
            "materialName": item.material_name_snapshot or item.product_name or getattr(item.material, "name", ""),
            "unit": item.unit_snapshot,
            "quantity": str(allocated),
            "unitPrice": str(unit_price),
            "amount": str((unit_price * allocated).quantize(Decimal("0.01"))),
        })
        remaining -= allocated
        if remaining == 0:
            break
    if remaining != 0:
        raise ScmRuntimeActionError("RECEIPT_LINE_ALLOCATION_FAILED", "收货数量无法完整分配到采购订单明细")
    return result


class PurchaseOrderExecutionService:
    TRANSITIONS = {
        "procurement.purchase_order.submit": ("draft", "submitted"),
        "procurement.purchase_order.approve": ("submitted", "approved"),
        "procurement.purchase_order.review": ("approved", "reviewed"),
        "procurement.purchase_order.release": ("reviewed", "final_approved"),
    }

    @classmethod
    def transition(cls, order_id, action_code, user, payload=None):
        from .purchase_order_approval_service import execute_action
        return execute_action(user=user, order_id=order_id, action=action_code, payload=payload)

    @staticmethod
    @transaction.atomic
    def complete(order_id, user):
        order = PurchaseOrder.objects.select_for_update().get(pk=order_id)
        action_code = "procurement.purchase_order.complete"
        if order.status != "stored":
            raise ScmRuntimeActionError("PURCHASE_ORDER_NOT_STORED", "采购订单只有完成正式入库后才能正常结案")
        planned = order.items.aggregate(total=Sum("quantity"))["total"] or Decimal("0")
        received = order.scm_receipts.aggregate(total=Sum("quantity"))["total"] or Decimal("0")
        qualified = PurchaseInspection.objects.filter(source_receipt__source_purchase_order=order, status="qualified").aggregate(total=Sum("qualified_quantity"))["total"] or Decimal("0")
        inbound = WarehouseInbound.objects.filter(source_inspection__source_receipt__source_purchase_order=order, status="completed").aggregate(total=Sum("quantity"))["total"] or Decimal("0")
        rejected = PurchaseInspection.objects.filter(source_receipt__source_purchase_order=order).aggregate(total=Sum("rejected_quantity"))["total"] or Decimal("0")
        if not (planned > 0 and received == qualified == inbound == planned and rejected == 0):
            raise ScmRuntimeActionError("PURCHASE_ORDER_QUANTITY_NOT_CLOSED", "收货、合格、入库数量尚未与订单数量完全闭合，禁止正常结案")
        decision, _ = _authorize_fulfillment(user=user, action_code=action_code, order=order)
        order.status = "closed"
        order.save(update_fields=["status", "updated_at"])
        record_action_audit(
            user=user, action_code=action_code, organization_id=order.company_id,
            target_type="PurchaseOrder", target_id=order.pk, target_no=order.po_no,
            before={"status": "stored"}, after={"status": "closed", "completionType": "NORMAL"},
            authorization=decision,
        )
        return order


class PurchaseReceiptService:
    @staticmethod
    @transaction.atomic
    def confirm(order_id, quantity, user=None, *, material_payload=None):
        if material_payload is not None:
            from .material_stock_authority import execute
            return execute(user=user,action='confirm-receipt',object_id=order_id,payload=material_payload)
        try:
            order = PurchaseOrder.objects.select_for_update().get(pk=order_id)
        except PurchaseOrder.DoesNotExist:
            raise ScmRuntimeActionError("PURCHASE_ORDER_NOT_FOUND", "无法确认收货：采购订单不存在", 404)
        if order.status not in {"final_approved", "received"}:
            raise ScmRuntimeActionError("PURCHASE_ORDER_NOT_ISSUED", "无法确认收货：采购订单未完成审批下达")
        decision, employee = _authorize_fulfillment(
            user=user, action_code="procurement.receipt.receive", order=order
        )
        received = order.scm_receipts.aggregate(total=Sum("quantity"))["total"] or Decimal("0")
        planned = order.items.aggregate(total=Sum("quantity"))["total"] or Decimal("0")
        current = _decimal(quantity, "收货数量", positive=True)
        if current + received > planned:
            raise ScmRuntimeActionError("RECEIPT_QUANTITY_EXCEEDED", f"无法确认收货：累计收货数量{current + received}超过订单数量{planned}")
        lines = _receipt_line_items(order, current)
        receipt = PurchaseReceipt.objects.create(
            receipt_no=_next_number("RC", PurchaseReceipt, "receipt_no"),
            source_purchase_order=order,
            status="received",
            quantity=current,
            amount=(order.total_amount * current / planned).quantize(Decimal("0.01")) if planned else Decimal("0"),
            items=lines,
            receipt_date=_business_date(),
            operator_employee=employee,
            operator_account_id=user.pk,
        )
        for item in order.items.all():
            actual = Decimal("0")
            for receipt_items in order.scm_receipts.values_list("items", flat=True):
                actual += sum((_decimal(row.get("quantity") or 0, "收货数量") for row in receipt_items or [] if int(row.get("purchaseOrderItemId") or 0) == item.pk), Decimal("0"))
            item.actual_quantity = actual
            item.actual_unit_price = item.unit_price_snapshot if item.unit_price_snapshot is not None else item.unit_price
            item.actual_amount = (item.actual_unit_price * actual).quantize(Decimal("0.01"))
            item.actual_arrival_date = _business_date()
            item.save(update_fields=["actual_quantity", "actual_unit_price", "actual_amount", "actual_arrival_date"])
        if current + received == planned:
            order.status = "received"
            order.actual_receive_date = _business_date()
            order.save(update_fields=["status", "actual_receive_date", "updated_at"])
        record_action_audit(
            user=user, action_code="procurement.receipt.receive", organization_id=order.company_id,
            target_type="PurchaseReceipt", target_id=receipt.pk, target_no=receipt.receipt_no,
            before={"orderStatus": "final_approved", "receivedQuantity": str(received)},
            after={"status": receipt.status, "quantity": str(receipt.quantity), "orderStatus": order.status},
            authorization=decision,
        )
        return receipt


class PurchaseInspectionService:
    ALLOWED_TRANSITIONS = {
        "pending": {"inspecting"},
        "inspecting": {"qualified", "rejected"},
        "qualified": set(),
        "rejected": set(),
    }

    @staticmethod
    @transaction.atomic
    def create_from_receipt(receipt_id, user, *, material_payload=None):
        if material_payload is not None:
            from .material_stock_authority import execute
            return execute(user=user,action='create-inspection',object_id=receipt_id,payload=material_payload)
        try:
            receipt = PurchaseReceipt.objects.select_for_update().get(pk=receipt_id)
        except PurchaseReceipt.DoesNotExist:
            raise ScmRuntimeActionError("PURCHASE_RECEIPT_NOT_FOUND", "无法创建质量检验：收货记录不存在", 404)
        if receipt.status != "received":
            raise ScmRuntimeActionError("RECEIPT_NOT_CONFIRMED", "无法创建质量检验：收货尚未确认")
        if receipt.inspections.exists():
            existing = receipt.inspections.order_by("id").first()
            raise ScmRuntimeActionError("INSPECTION_ALREADY_EXISTS", f"无法创建质量检验：已存在检验记录 {existing.inspection_no}")
        order = receipt.source_purchase_order
        decision, employee = _authorize_fulfillment(
            user=user, action_code="quality.purchase.inspect", order=order
        )
        inspection = PurchaseInspection.objects.create(
            inspection_no=_next_number("IQC", PurchaseInspection, "inspection_no"),
            source_receipt=receipt,
            status="pending",
            quantity=receipt.quantity,
            amount=receipt.amount,
            items=receipt.items,
            inspector_employee=employee,
            inspector_account_id=user.pk,
        )
        record_action_audit(
            user=user, action_code="quality.purchase.inspect", organization_id=order.company_id,
            target_type="PurchaseInspection", target_id=inspection.pk, target_no=inspection.inspection_no,
            before={"exists": False, "receiptStatus": receipt.status},
            after={"status": inspection.status, "quantity": str(inspection.quantity)}, authorization=decision,
        )
        return inspection

    @classmethod
    @transaction.atomic
    def transition(cls, inspection_id, target_status, qualified_quantity=None, user=None, *, material_payload=None):
        if material_payload is not None:
            from .material_stock_authority import execute
            return execute(user=user,action='transition-inspection',object_id=inspection_id,payload=material_payload)
        try:
            inspection = PurchaseInspection.objects.select_for_update().get(pk=inspection_id)
        except PurchaseInspection.DoesNotExist:
            raise ScmRuntimeActionError("PURCHASE_INSPECTION_NOT_FOUND", "无法更新质量检验：检验记录不存在", 404)
        allowed = cls.ALLOWED_TRANSITIONS.get(inspection.status, set())
        if target_status not in allowed:
            raise ScmRuntimeActionError("ILLEGAL_INSPECTION_TRANSITION", f"无法更新质量检验：禁止从{inspection.status}进入{target_status}")
        order = inspection.source_receipt.source_purchase_order
        decision, employee = _authorize_fulfillment(
            user=user, action_code="quality.purchase.inspect", order=order
        )
        if inspection.inspector_employee_id != employee.pk:
            raise ScmRuntimeActionError("INSPECTION_OPERATOR_MISMATCH", "检验单必须由创建该检验事实的检验员工继续执行", 403)
        before_status = inspection.status
        if target_status == "qualified":
            accepted = _decimal(qualified_quantity, "检验合格数量", positive=True)
            if accepted > inspection.quantity:
                raise ScmRuntimeActionError("QUALIFIED_QUANTITY_EXCEEDED", f"无法更新质量检验：合格数量{accepted}超过检验数量{inspection.quantity}")
            inspection.qualified_quantity = accepted
            inspection.rejected_quantity = inspection.quantity - accepted
            inspection.inspection_date = _business_date()
        elif target_status == "rejected":
            inspection.qualified_quantity = Decimal("0")
            inspection.rejected_quantity = inspection.quantity
            inspection.inspection_date = _business_date()
        inspection.status = target_status
        inspection.save(update_fields=["status", "qualified_quantity", "rejected_quantity", "inspection_date", "updated_at"])
        if target_status == "qualified":
            all_receipts = order.scm_receipts.count()
            qualified_receipts = PurchaseInspection.objects.filter(source_receipt__source_purchase_order=order, status="qualified").count()
            if all_receipts and all_receipts == qualified_receipts:
                order.status = "inspected"
                order.save(update_fields=["status", "updated_at"])
        record_action_audit(
            user=user, action_code="quality.purchase.inspect", organization_id=order.company_id,
            target_type="PurchaseInspection", target_id=inspection.pk, target_no=inspection.inspection_no,
            before={"status": before_status},
            after={"status": inspection.status, "qualifiedQuantity": str(inspection.qualified_quantity), "rejectedQuantity": str(inspection.rejected_quantity)},
            authorization=decision,
        )
        return inspection


class WarehouseInboundService:
    @staticmethod
    @transaction.atomic
    def confirm(
        inspection_id, quantity, warehouse_code, user=None,
        location_code=None, lot_numbers=None, material_payload=None,
    ):
        if material_payload is not None:
            from .material_stock_authority import execute
            return execute(user=user,action='confirm-inbound',object_id=inspection_id,payload=material_payload)
        try:
            inspection = PurchaseInspection.objects.select_for_update().get(pk=inspection_id)
        except PurchaseInspection.DoesNotExist:
            raise ScmRuntimeActionError("PURCHASE_INSPECTION_NOT_FOUND", "无法确认入库：检验记录不存在", 404)
        if inspection.status != "qualified":
            raise ScmRuntimeActionError("INSPECTION_NOT_QUALIFIED", "无法确认入库：质量检验未合格")
        order = inspection.source_receipt.source_purchase_order
        decision, employee = _authorize_fulfillment(
            user=user, action_code="warehouse.purchase.putaway", order=order
        )
        warehouse = Warehouse.objects.select_for_update().filter(
            code=str(warehouse_code or "").strip(), company_id=order.company_id, is_active=True
        ).first()
        if not warehouse:
            raise ScmRuntimeActionError("FORMAL_WAREHOUSE_NOT_FOUND", "未找到该组织下启用的正式仓库", 404)
        location = None
        if location_code:
            location = WarehouseLocation.objects.filter(
                warehouse=warehouse, code=str(location_code).strip(), is_active=True,
            ).first()
            if not location:
                raise ScmRuntimeActionError(
                    "FORMAL_LOCATION_NOT_FOUND", "未找到该仓库下启用的正式库位", 404,
                )
        lot_numbers = lot_numbers or {}
        current = _decimal(quantity, "入库数量", positive=True)
        completed = inspection.warehouse_inbounds.aggregate(total=Sum("quantity"))["total"] or Decimal("0")
        if current + completed > inspection.qualified_quantity:
            raise ScmRuntimeActionError("INBOUND_QUANTITY_EXCEEDED", f"无法确认入库：累计入库数量{current + completed}超过检验合格数量{inspection.qualified_quantity}")
        source_lines = inspection.items or []
        remaining = current
        inbound_lines = []
        for row in source_lines:
            available = _decimal(row.get("quantity") or 0, "检验明细数量")
            allocated = min(available, remaining)
            if allocated <= 0:
                continue
            material_key = str(row.get("materialId") or row.get("materialCode") or "")
            lot_no = str(lot_numbers.get(material_key) or "").strip()
            inbound_lines.append({
                **row, "quantity": str(allocated), "warehouseCode": warehouse.code,
                "locationCode": location.code if location else "", "lotNo": lot_no,
            })
            remaining -= allocated
            if remaining == 0:
                break
        if remaining != 0:
            raise ScmRuntimeActionError("INBOUND_LINE_ALLOCATION_FAILED", "入库数量无法完整分配到检验明细")
        inbound = WarehouseInbound.objects.create(
            inbound_no=_next_number("IN", WarehouseInbound, "inbound_no"),
            source_inspection=inspection,
            status="completed",
            quantity=current,
            amount=inspection.amount,
            items=inbound_lines,
            warehouse=warehouse,
            location=location,
            inbound_date=_business_date(),
            operator_employee=employee,
            operator_account_id=user.pk,
        )
        material_quantities = {}
        for row in inbound_lines:
            material_id = int(row.get("materialId") or 0)
            if not material_id:
                raise ScmRuntimeActionError("INBOUND_MATERIAL_REQUIRED", "入库明细缺少正式物料主数据")
            dimension_key = (material_id, str(row.get("lotNo") or "").strip())
            material_quantities[dimension_key] = material_quantities.get(dimension_key, Decimal("0")) + _decimal(row["quantity"], "入库明细数量")
        for (material_id, lot_no), material_quantity in material_quantities.items():
            lot = None
            if lot_no:
                lot = InventoryLot.objects.filter(
                    company_id=order.company_id, material_id=material_id,
                    warehouse=warehouse, lot_no=lot_no, is_active=True,
                ).first()
                if not lot:
                    raise ScmRuntimeActionError(
                        "FORMAL_LOT_NOT_FOUND", f"未找到物料{material_id}在仓库{warehouse.code}下启用的正式批号{lot_no}", 404,
                    )
            from .inventory_posting import post_inbound_stock
            post_inbound_stock(inbound=inbound,warehouse=warehouse,location=location,material_id=material_id,
                lot=lot,quantity=material_quantity,employee=employee,user=user)
        total_inbound = WarehouseInbound.objects.filter(
            source_inspection__source_receipt__source_purchase_order=order, status="completed"
        ).aggregate(total=Sum("quantity"))["total"] or Decimal("0")
        planned = order.items.aggregate(total=Sum("quantity"))["total"] or Decimal("0")
        if total_inbound == planned:
            order.status = "stored"
            order.save(update_fields=["status", "updated_at"])
        record_action_audit(
            user=user, action_code="warehouse.purchase.putaway", organization_id=order.company_id,
            target_type="WarehouseInbound", target_id=inbound.pk, target_no=inbound.inbound_no,
            before={"inboundQuantity": str(completed), "orderStatus": "inspected"},
            after={
                "quantity": str(inbound.quantity), "warehouseCode": warehouse.code,
                "locationCode": location.code if location else "",
                "lotNumbers": sorted({row.get("lotNo") for row in inbound_lines if row.get("lotNo")}),
                "orderStatus": order.status,
            },
            authorization=decision,
        )
        return inbound
