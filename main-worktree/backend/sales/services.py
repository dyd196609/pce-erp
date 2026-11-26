import hashlib
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from masterdata.models import Material, UnitOfMeasure
from pde.models import (
    EngineeringDocumentVersion, OrderCrossFunctionalReview,
    OrderReviewSalesOrderRelation, OrderReviewScopeItem,
    ProductConfiguration, ProductDefinition,
)
from pde.crm_order_admission import (
    CRMOrderAdmissionError,
    require_crm_order_admission,
    require_current_crm_sales_order_admission,
)
from pde.crm_sales_order_identity import assess_crm_sales_order_identity
from pfm.models import Employee
from planning.models import Demand
from pde.models import ManufacturingInputReference, ProductEngineeringReadiness
from system.models import Company, Department, OrganizationOperatingAuditRecord, PositionWorkflowResponsibility
from workflow_runtime.models import (
    ApprovalDecision, ApprovalTask, BusinessStateTransition, ProcessDefinition,
    WorkflowInstance, WorkflowNodeDefinition,
)
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state, record_projected_business_transition,
    transition_business_object,
)

from .models import (
    Customer, SalesOrder, SalesOrderActionRequest, SalesOrderItem,
    SalesOrderItemEngineeringAttribute,
)


def order_business_classification(row):
    # Acceptance fixtures carry an explicit persisted marker.  The business
    # classification must not depend on a historical order number or on a
    # hard-coded marker value: new fixture records remain isolated while
    # unmarked orders are evaluated by the normal company, permission, state,
    # CRM admission and formal-relation checks in their owning service paths.
    excluded = bool(str(row.acceptance_marker or "").strip())
    return {
        "code": "TEST_SYSTEM_ACCEPTANCE_NON_BUSINESS_SAMPLE" if excluded else "BUSINESS_ORDER",
        "label": "TEST / SYSTEM ACCEPTANCE / NON-BUSINESS SAMPLE" if excluded else "BUSINESS ORDER",
        "realBusinessAcceptanceEligible": not excluded,
        "planningDemandEligible": not excluded,
        "reason": (
            "历史采购/系统流程验收数据；保留记录，但排除真实业务验收、真实订单流程与未来 Planning Demand。"
            if excluded else "订单未携带非业务验收标记，继续执行正式业务条件校验。"
        ),
    }


PROCESS_CODE = "SALES_ORDER_TO_SUPPLY_PLAN"
ACTIONS = {
    "sales.order.view": {"states": ["*"]},
    "sales.order.create": {"states": ["not_created"]},
    "sales.order.confirm": {"states": ["draft"]},
    "sales.order.generate_demand": {"states": ["confirmed"]},
    "sales.order.engineering_input.maintain": {"states": ["draft", "confirmed"]},
    "sales.order.update": {"states": ["draft"]},
    "sales.order.submit": {"states": ["draft"]},
    "sales.order.approve": {"states": ["submitted"]},
    "sales.order.engineering.start": {"states": ["approved", "confirmed"]},
    "sales.order.engineering.complete": {"states": ["engineering"]},
    "sales.order.execution.start": {"states": ["manufacturing_ready"]},
    "sales.order.delivery.start": {"states": ["in_progress"]},
    "sales.order.complete": {"states": ["in_progress", "delivering"]},
    "sales.order.close": {"states": ["completed"]},
    "sales.order.cancel": {"states": ["draft", "submitted", "approved", "confirmed", "engineering", "manufacturing_ready"]},
}

ORDER_ACTIONS = {
    "submit": ("sales.order.submit", {"draft"}, "submitted", "提交订单审核"),
    "approve": ("sales.order.approve", {"submitted"}, "approved", "批准销售订单"),
    "start-engineering": ("sales.order.engineering.start", {"approved", "confirmed"}, "engineering", "进入工程准备"),
    "complete-engineering": ("sales.order.engineering.complete", {"engineering"}, "manufacturing_ready", "工程准备完成"),
    "start-execution": ("sales.order.execution.start", {"manufacturing_ready"}, "in_progress", "开始订单执行"),
    "start-delivery": ("sales.order.delivery.start", {"in_progress"}, "delivering", "开始交付"),
    "complete": ("sales.order.complete", {"in_progress", "delivering"}, "completed", "完成订单"),
    "close": ("sales.order.close", {"completed"}, "closed", "关闭订单"),
    "cancel": ("sales.order.cancel", {"draft", "submitted", "approved", "confirmed", "engineering", "manufacturing_ready"}, "cancelled", "取消订单"),
}

ORDER_ALLOWED_TRANSITIONS = {
    (source, target)
    for _, sources, target, _ in ORDER_ACTIONS.values()
    for source in sources
} | {("draft", "confirmed"), ("confirmed", "closed")}


class SalesBusinessError(Exception):
    def __init__(self, code, message, http_status=400, data=None):
        self.code, self.message, self.http_status, self.data = code, message, http_status, data
        super().__init__(message)


def _crm_source_context(*, payload=None, order=None):
    payload = payload or {}
    delivery = (payload.get("deliveryInformation") if order is None else order.delivery_information) or {}
    intake = payload.get("sourceIntakeFacts") or {}
    source_order_no = payload.get("externalSourceNo") if order is None else order.external_source_no
    source_record_ids = {
        str(value).strip() for value in (intake.get("sourceRecordId"), delivery.get("sourceRecordId"))
        if value is not None and str(value).strip()
    }
    source_versions = {
        str(value).strip() for value in (intake.get("sourceVersion"), delivery.get("sourceVersion"))
        if value is not None and str(value).strip()
    }
    relation = None
    if order is not None:
        relation = order.order_review_relations.select_related("review").order_by("-review__review_version", "-pk").first()
    source_hashes = {
        str(value).strip() for value in (
            intake.get("sourceContentHash"), delivery.get("sourceContentHash"),
            relation.review.source_content_hash if relation else None,
        ) if value is not None and str(value).strip()
    }
    # CRM admission applicability is a formal source-type fact.  An external
    # number or an import/intake identity alone does not make an order a CRM
    # order.  Existing relation-backed orders remain governed even if their
    # historical order_source value predates the explicit CRM enum usage.
    source_linked = bool(
        (order is None and str(payload.get("orderSource") or "").lower() == "crm")
        or (
            order is not None
            and (
                str(order.order_source or "").lower() == "crm"
                or relation is not None
            )
        )
    )
    if not source_linked:
        return None
    return {
        "source_record_id": source_record_ids,
        "source_order_no": source_order_no,
        "source_version": source_versions,
        "source_content_hash": source_hashes or None,
    }


def _require_crm_admission(*, company_id, payload=None, order=None, lock=False):
    if order is not None:
        if _crm_source_context(order=order) is None:
            return None
        try:
            return require_current_crm_sales_order_admission(
                order=order,
                lock=lock,
            )
        except CRMOrderAdmissionError as exc:
            raise SalesBusinessError(
                exc.code, exc.message, exc.http_status,
                {"crmOrderAdmission": exc.details},
            ) from exc
    context = _crm_source_context(payload=payload, order=order)
    if context is None:
        return None
    try:
        return require_crm_order_admission(company_id=company_id, lock=lock, **context)
    except CRMOrderAdmissionError as exc:
        raise SalesBusinessError(
            exc.code, exc.message, exc.http_status, {"crmOrderAdmission": exc.details},
        ) from exc


def _identity_hash(parts):
    return hashlib.sha256("|".join(str(value) for value in parts).encode("utf-8")).hexdigest()


def _persist_order_review_relation(*, user, payload, admission, sales_order, items):
    """Persist the Gate-selected review and explicit item scope in this order transaction."""

    if admission is None:
        return None
    scope_mode = str(payload.get("reviewScopeMode") or "").strip().upper()
    if scope_mode not in {"WHOLE_ORDER", "SELECTED_ITEMS"}:
        raise SalesBusinessError(
            "ORDER_REVIEW_SCOPE_MODE_REQUIRED",
            "CRM订单必须明确WHOLE_ORDER或SELECTED_ITEMS评审范围；新流程禁止UNRESOLVED。",
            409,
        )
    scope_reason = str(payload.get("reviewScopeReason") or "").strip()
    selected_items = list(items)
    if scope_mode == "SELECTED_ITEMS":
        raw_line_nos = payload.get("reviewScopeItemLineNos")
        if not isinstance(raw_line_nos, list) or not raw_line_nos:
            raise SalesBusinessError(
                "ORDER_REVIEW_SCOPE_ITEMS_REQUIRED",
                "SELECTED_ITEMS必须明确提供至少一个订单行号。",
                409,
            )
        try:
            selected_line_nos = [int(value) for value in raw_line_nos]
        except (TypeError, ValueError) as exc:
            raise SalesBusinessError(
                "ORDER_REVIEW_SCOPE_ITEMS_INVALID", "评审范围订单行号必须为正整数。", 409,
            ) from exc
        if any(value <= 0 for value in selected_line_nos) or len(selected_line_nos) != len(set(selected_line_nos)):
            raise SalesBusinessError(
                "ORDER_REVIEW_SCOPE_ITEMS_INVALID", "评审范围订单行号必须为不重复的正整数。", 409,
            )
        by_line_no = {item.line_no: item for item in items}
        if set(selected_line_nos) - set(by_line_no):
            raise SalesBusinessError(
                "ORDER_REVIEW_SCOPE_ITEMS_INVALID", "评审范围包含不属于本订单的行号。", 409,
            )
        if not scope_reason:
            raise SalesBusinessError(
                "ORDER_REVIEW_SCOPE_REASON_REQUIRED", "SELECTED_ITEMS必须保存明确范围原因。", 409,
            )
        selected_items = [by_line_no[value] for value in selected_line_nos]

    review = OrderCrossFunctionalReview.objects.select_for_update().select_related(
        "source_record",
    ).filter(
        pk=admission.review_id,
        company_id=user.company_id,
        review_type="CRM_ORDER_REVIEW",
        record_status="SUBMITTED",
    ).first()
    if not review or review.review_version != admission.review_version:
        raise SalesBusinessError(
            "ORDER_REVIEW_GATE_RESULT_STALE",
            "P0 Gate返回的订单评审版本已失效，关系未建立。",
            409,
        )
    existing_candidates = list(
        SalesOrder.objects.select_for_update().filter(
            company_id=sales_order.company_id,
            external_source_no=sales_order.external_source_no,
            acceptance_marker="",
        ).exclude(pk=sales_order.pk).values_list("pk", flat=True)[:3]
    )
    if existing_candidates:
        raise SalesBusinessError(
            "CRM_SALES_ORDER_CANDIDATE_NOT_UNIQUE",
            "同一CRM来源已存在其它正式销售订单候选，系统无法唯一确认业务对象，已失败关闭。",
            409,
            {"candidateSalesOrderIds": existing_candidates},
        )
    identity = assess_crm_sales_order_identity(
        source=review.source_record,
        review=review,
        company_id=sales_order.company_id,
        customer_name=sales_order.customer.name,
        project_reference=sales_order.project_reference,
        contract_reference=sales_order.contract_reference,
        external_source_no=sales_order.external_source_no,
        scope_mode=scope_mode,
        order_items=selected_items,
        selected_source_scope_keys=payload.get("reviewScopeSourceItemKeys"),
    )
    if not identity["allowed"]:
        code = (
            "CRM_SALES_ORDER_BUSINESS_IDENTITY_CONFLICT"
            if identity["statusCode"] == "CONFLICT"
            else "CRM_SALES_ORDER_BUSINESS_IDENTITY_NOT_PROVEN"
        )
        raise SalesBusinessError(
            code,
            "CRM评审来源与拟创建销售订单的业务身份或订单行范围不一致，已失败关闭且未建立0032关系。",
            409,
            {"businessIdentity": identity},
        )
    relation = OrderReviewSalesOrderRelation(
        company_id=user.company_id,
        review=review,
        sales_order=sales_order,
        scope_mode=scope_mode,
        order_version_snapshot=sales_order.version,
        source_content_hash_snapshot=review.source_content_hash,
        resolution_basis="RUNTIME_GATE",
        scope_reason=scope_reason,
        created_by=user,
        audit_hash=_identity_hash((
            "ORDER_REVIEW_SALES_ORDER_RELATION", user.company_id,
            review.pk, review.review_version, sales_order.pk, sales_order.version,
            scope_mode, *(item.pk for item in selected_items),
        )),
    )
    try:
        relation.save()
        for item in selected_items:
            OrderReviewScopeItem.objects.create(
                relation=relation,
                sales_order_item=item,
                line_no_snapshot=item.line_no,
                external_line_no_snapshot=item.external_line_no,
                item_identity_hash=_identity_hash((
                    "ORDER_REVIEW_SCOPE_ITEM", relation.audit_hash, item.pk,
                    item.line_no, item.external_line_no, item.material_id,
                    item.quantity, item.uom_id,
                )),
            )
    except Exception as exc:
        if isinstance(exc, SalesBusinessError):
            raise
        raise SalesBusinessError(
            "ORDER_REVIEW_RELATION_INVALID",
            f"订单评审正式关系校验失败：{exc}",
            409,
        ) from exc
    return relation


def _number(prefix, row):
    return f"{prefix}{date.today():%Y%m%d}{row.pk:04d}"


def _actor(user):
    employee = getattr(user, "employee_profile", None)
    position = getattr(employee, "position_ref", None) if employee else None
    return employee, position


def _related(obj, name):
    try:
        return getattr(obj, name)
    except Exception:
        return None


def _workflow_actor(user, action_code):
    employee, position = _actor(user)
    if not employee or employee.status != "active" or not position or not position.is_active:
        raise SalesBusinessError("SALES_ACTOR_EMPLOYEE_REQUIRED", "销售执行账户必须关联在职员工和正式营销岗位。", 409)
    mapping = PositionWorkflowResponsibility.objects.select_related(
        "responsibility", "position", "workflow_node__process_definition",
    ).filter(
        workflow_node__process_definition__definition_code=PROCESS_CODE,
        workflow_node__process_definition__active=True,
        workflow_node__business_action_code=action_code,
        workflow_node__active=True,
        position=position, active=True,
        responsibility__code="RESP_SALES_ORDER_002", responsibility__is_active=True,
    ).order_by("workflow_node__sequence", "pk").first()
    node = mapping.workflow_node if mapping else None
    if not mapping:
        raise SalesBusinessError("SALES_WORKFLOW_RESPONSIBILITY_DENIED", "当前岗位未承担销售需求与订单协调职责。", 403)
    return employee, position, node, mapping


def _audit(*, user, action_code, target, before, after, authorization, reason="订单运作系统正式业务动作"):
    employee, position = _actor(user)
    return OrganizationOperatingAuditRecord.objects.create(
        action_code=action_code, actor=user, organization_id=user.company_id,
        target_type=target.__class__.__name__, target_id=target.pk,
        target_label=(
            target.order_no if isinstance(target, SalesOrder)
            else target.demand_no if isinstance(target, Demand)
            else f"{target.sales_order_item.sales_order.order_no}:{target.sales_order_item.line_no}:{target.canonical_field}"
        ),
        reason=reason,
        before_snapshot={"state": before},
        after_snapshot={
            "state": after,
            "actor": {"account": user.username, "employeeNo": getattr(employee, "employee_no", ""), "positionCode": getattr(position, "code", "")},
            "authorization": authorization,
            "inventoryWriteCount": 0,
        },
    )


def _document_version(*, company_id, value, field_label):
    if not value:
        return None
    document = EngineeringDocumentVersion.objects.select_related("related_product").filter(
        pk=value, related_product__company_id=company_id,
    ).first()
    if not document:
        raise SalesBusinessError("DOCUMENT_REFERENCE_INVALID", f"{field_label}不存在或不属于当前组织。")
    return document


def _engineering_attribute(*, user, item, payload):
    if not isinstance(payload, dict):
        raise SalesBusinessError("ENGINEERING_ATTRIBUTE_INVALID", "工程属性必须是结构化对象。")
    missing = [key for key in ("rawSource", "rawField", "rawValue", "canonicalField", "valueType", "sourceType") if key not in payload]
    if missing:
        raise SalesBusinessError("ENGINEERING_ATTRIBUTE_REQUIRED", f"工程属性缺少字段：{', '.join(missing)}")
    unit = None
    if payload.get("unitId"):
        unit = UnitOfMeasure.objects.filter(
            pk=payload["unitId"], company_id=item.sales_order.company_id, is_active=True,
        ).first()
        if not unit:
            raise SalesBusinessError("ENGINEERING_ATTRIBUTE_UOM_INVALID", "工程属性单位不存在、已停用或不属于当前组织。")
    document = _document_version(
        company_id=item.sales_order.company_id,
        value=payload.get("engineeringDocumentVersionId"),
        field_label="工程属性资料版本",
    )
    attribute = SalesOrderItemEngineeringAttribute(
        sales_order_item=item,
        sequence=int(payload.get("sequence") or 1),
        raw_source=str(payload.get("rawSource") or ""),
        raw_sheet=str(payload.get("rawSheet") or ""),
        external_source=str(payload.get("externalSource") or ""),
        raw_field=str(payload.get("rawField") or ""),
        raw_value=payload.get("rawValue"),
        canonical_field=str(payload.get("canonicalField") or ""),
        normalized_value=payload.get("normalizedValue"),
        value_type=str(payload.get("valueType") or ""),
        unit=unit,
        source_type=str(payload.get("sourceType") or ""),
        engineering_document_version=document,
        created_by=user,
    )
    try:
        attribute.full_clean()
    except Exception as exc:
        raise SalesBusinessError("ENGINEERING_ATTRIBUTE_INVALID", f"工程属性校验失败：{exc}")
    attribute.save()
    return attribute


def resolve_order_line_master_data(company_id, line, line_no):
    material = Material.objects.filter(
        pk=line.get("materialId"), company_id=company_id, is_active=True,
    ).first()
    if not material:
        raise SalesBusinessError("MATERIAL_INVALID", f"第{line_no}行物料不存在、已停用或不属于当前组织。")
    item_uom = None
    if line.get("uomId"):
        item_uom = UnitOfMeasure.objects.filter(
            pk=line["uomId"], company_id=company_id, is_active=True,
        ).first()
        if not item_uom:
            raise SalesBusinessError("ORDER_ITEM_UOM_INVALID", f"第{line_no}行计量单位不存在、已停用或不属于当前组织。")
    return material, item_uom


@transaction.atomic
def create_order(*, user, payload, authorization, business_purpose):
    employee, position, node, mapping = _workflow_actor(user, "sales.order.create")
    business_purpose = str(business_purpose or "").strip()
    if business_purpose not in SalesOrder.BusinessPurpose.values:
        raise SalesBusinessError(
            "BUSINESS_PURPOSE_INVALID",
            "创建销售订单必须由受控业务入口明确指定合法Business Purpose。",
        )
    customer = Customer.objects.filter(pk=payload.get("customerId"), company_id=user.company_id, is_active=True).first()
    department = Department.objects.filter(pk=payload.get("departmentId"), company_id=user.company_id, is_active=True).first()
    if not customer: raise SalesBusinessError("CUSTOMER_INVALID", "客户不存在、已停用或不属于当前组织。")
    if not department: raise SalesBusinessError("DEPARTMENT_INVALID", "销售部门不存在、已停用或不属于当前组织。")
    required_date = payload.get("requiredDate")
    if not required_date: raise SalesBusinessError("REQUIRED_DATE_REQUIRED", "交付日期不能为空。")
    item_payloads = payload.get("items") or [{
        "materialId": payload.get("materialId"), "quantity": payload.get("quantity"),
        "requiredDate": required_date,
        "productDefinitionId": payload.get("productDefinitionId"),
        "productVersionId": payload.get("productVersionId"),
        "manufacturingOutputId": payload.get("manufacturingOutputId"),
        "uomId": payload.get("uomId"),
        "customerProductName": payload.get("customerProductName"),
        "customerProductDescription": payload.get("customerProductDescription"),
        "specification": payload.get("specification"),
        "configurationReference": payload.get("configurationReference"),
        "engineeringRequirements": payload.get("engineeringRequirements"),
        "qualityRequirements": payload.get("qualityRequirements"),
        "remark": payload.get("itemRemark"),
        "externalLineNo": payload.get("externalLineNo"),
        "engineeringDocumentVersionId": payload.get("itemEngineeringDocumentVersionId"),
        "engineeringAttributes": payload.get("engineeringAttributes") or [],
    }]
    if not isinstance(item_payloads, list) or not item_payloads:
        raise SalesBusinessError("SALES_ORDER_ITEMS_REQUIRED", "销售订单至少需要一条有效明细。")
    owner = employee
    if payload.get("salesOwnerId"):
        owner = Employee.objects.select_related("department_ref", "user").filter(
            pk=payload["salesOwnerId"], status="active",
        ).first()
        owner_company_id = (
            owner.department_ref.company_id if owner and owner.department_ref_id
            else owner.user.company_id if owner and owner.user_id else None
        )
        if not owner or owner_company_id != user.company_id:
            raise SalesBusinessError("SALES_OWNER_INVALID", "销售负责人不存在、非在职或不属于当前组织。")
    delivery_information = payload.get("deliveryInformation") or {}
    if not isinstance(delivery_information, dict):
        raise SalesBusinessError("DELIVERY_INFORMATION_INVALID", "交付信息必须是结构化对象。")
    admission = _require_crm_admission(
        company_id=user.company_id, payload=payload, lock=True,
    )
    header_document = _document_version(
        company_id=user.company_id, value=payload.get("engineeringDocumentVersionId"),
        field_label="订单正式文档引用",
    )
    row = create_business_object_with_initial_state(
        model=SalesOrder, initial_state="draft", company_id=user.company_id,
        department=department, customer=customer, order_no=f"TMP-SO-{timezone.now().timestamp()}",
        order_date=payload.get("orderDate") or date.today(), required_delivery_date=required_date,
        currency=str(payload.get("currency") or "CNY").upper(),
        order_type=str(payload.get("orderType") or "standard"),
        order_source=str(payload.get("orderSource") or "manual"),
        project_reference=str(payload.get("projectReference") or ""),
        contract_reference=str(payload.get("contractReference") or ""),
        sales_owner=owner, delivery_information=delivery_information,
        external_source_no=str(payload.get("externalSourceNo") or ""),
        engineering_document_version=header_document,
        business_purpose=business_purpose,
        acceptance_marker=str(payload.get("acceptanceMarker") or ""),
        remark=str(payload.get("remark") or ""), created_by=user,
    )
    row.order_no = _number("SO", row); row.save(update_fields=["order_no", "updated_at"])
    items = []
    for line_no, item_payload in enumerate(item_payloads, 1):
        material, item_uom = resolve_order_line_master_data(user.company_id, item_payload, line_no)
        try:
            quantity = Decimal(str(item_payload.get("quantity") or "0"))
        except (InvalidOperation, TypeError):
            raise SalesBusinessError("QUANTITY_INVALID", f"第{line_no}行订单数量必须是有效数字。")
        if quantity <= 0:
            raise SalesBusinessError("QUANTITY_INVALID", f"第{line_no}行订单数量必须大于 0。")
        item_document = _document_version(
            company_id=user.company_id,
            value=item_payload.get("engineeringDocumentVersionId"),
            field_label=f"第{line_no}行图纸/工程资料引用",
        )
        engineering_mode = str(item_payload.get("engineeringMode") or "").strip()
        if not engineering_mode:
            # Backward-compatible inference for the established PDE order input API.
            # New workbench requests send the mode explicitly, while older callers
            # identified order engineering through ProductDefinition alone.
            if item_payload.get("productConfigurationId"):
                engineering_mode = "TEMPLATE_ASSISTED"
            elif item_payload.get("productDefinitionId") and ProductDefinition.objects.filter(
                pk=item_payload["productDefinitionId"],
                company_id=user.company_id,
                manufacturing_definition_mode="order_engineered",
            ).exists():
                engineering_mode = "ORDER_ENGINEERED"
            else:
                engineering_mode = "STANDARD"
        item = SalesOrderItem(
            sales_order=row, line_no=int(item_payload.get("lineNo") or line_no),
            material=material, quantity=quantity, uom=item_uom,
            required_date=item_payload.get("requiredDate") or required_date,
            product_definition_id=item_payload.get("productDefinitionId"),
            product_version_id=item_payload.get("productVersionId"),
            manufacturing_output_id=item_payload.get("manufacturingOutputId"),
            product_configuration_id=item_payload.get("productConfigurationId"),
            engineering_mode=engineering_mode,
            space_code=str(item_payload.get("spaceCode") or ""),
            space_name=str(item_payload.get("spaceName") or ""),
            installation_area=str(item_payload.get("installationArea") or ""),
            component_category=str(item_payload.get("componentCategory") or ""),
            unit_price=Decimal(str(item_payload.get("unitPrice") or "0")),
            tax_rate=Decimal(str(item_payload.get("taxRate") or "0")),
            price_tax_mode=str(item_payload.get("priceTaxMode") or "tax_exclusive"),
            customer_product_name=str(item_payload.get("customerProductName") or ""),
            customer_product_description=str(item_payload.get("customerProductDescription") or ""),
            specification=str(item_payload.get("specification") or ""),
            configuration_reference=str(item_payload.get("configurationReference") or ""),
            engineering_requirements=str(item_payload.get("engineeringRequirements") or ""),
            quality_requirements=str(item_payload.get("qualityRequirements") or ""),
            remark=str(item_payload.get("remark") or ""),
            external_line_no=str(item_payload.get("externalLineNo") or ""),
            engineering_document_version=item_document,
        )
        try:
            item.full_clean()
        except Exception as exc:
            raise SalesBusinessError("SALES_ORDER_ITEM_INVALID", f"第{line_no}行正式引用校验失败：{exc}")
        item.save()
        item.engineering_attribute_rows = [
            _engineering_attribute(user=user, item=item, payload=value)
            for value in (item_payload.get("engineeringAttributes") or [])
        ]
        items.append(item)
    review_relation = _persist_order_review_relation(
        user=user, payload=payload, admission=admission,
        sales_order=row, items=items,
    )
    audit = _audit(user=user, action_code="sales.order.create", target=row, before={}, after={
        "orderNo": row.order_no, "status": row.status, "customerCode": customer.code,
        "orderDate": str(row.order_date), "currency": row.currency,
        "projectReference": row.project_reference, "contractReference": row.contract_reference,
        "salesOwnerEmployeeNo": getattr(owner, "employee_no", ""),
        "salesOrganizationCode": department.code,
        "deliveryInformation": row.delivery_information,
        "externalSourceNo": row.external_source_no,
        "businessPurpose": row.business_purpose,
        "engineeringDocumentVersionId": row.engineering_document_version_id,
        "remark": row.remark,
        "itemCount": len(items),
        "orderReviewRelationId": review_relation.pk if review_relation else None,
        "orderReviewId": admission.review_id if admission else None,
        "orderReviewVersion": admission.review_version if admission else None,
        "orderReviewScopeMode": review_relation.scope_mode if review_relation else None,
        "sourceIntakeFacts": payload.get("sourceIntakeFacts") or {},
        "items": [{
            "salesOrderItemId": item.pk, "materialCode": item.material.code,
            "quantity": str(item.quantity), "productDefinitionId": item.product_definition_id,
            "productVersionId": item.product_version_id,
            "manufacturingOutputId": item.manufacturing_output_id,
            "productConfigurationId": item.product_configuration_id,
            "engineeringMode": item.engineering_mode,
            "spaceCode": item.space_code, "spaceName": item.space_name,
            "installationArea": item.installation_area,
            "componentCategory": item.component_category,
            "unitPrice": str(item.unit_price), "amount": str(item.amount),
            "taxRate": str(item.tax_rate), "priceTaxMode": item.price_tax_mode,
            "uomId": item.uom_id,
            "externalLineNo": item.external_line_no,
            "customerProductName": item.customer_product_name,
            "customerProductDescription": item.customer_product_description,
            "specification": item.specification,
            "configurationReference": item.configuration_reference,
            "engineeringRequirements": item.engineering_requirements,
            "qualityRequirements": item.quality_requirements,
            "remark": item.remark,
            "engineeringDocumentVersionId": item.engineering_document_version_id,
            "engineeringAttributeIds": [value.pk for value in item.engineering_attribute_rows],
        } for item in items],
        "requiredDate": str(required_date),
        "workflowNode": node.node_code, "responsibilityCode": mapping.responsibility.code,
    }, authorization=authorization)
    return row, items[0], audit


@transaction.atomic
def create_engineering_attribute(*, user, order_id, item_id, payload, authorization):
    order = SalesOrder.objects.select_for_update().filter(
        pk=order_id, company_id=user.company_id,
    ).first()
    if not order:
        raise SalesBusinessError("SALES_ORDER_NOT_FOUND", "销售订单不存在。", 404)
    _workflow_actor(user, "sales.order.engineering_input.maintain")
    if order.status not in {"draft", "confirmed"}:
        raise SalesBusinessError("ENGINEERING_INPUT_STATUS_INVALID", "只有草稿或已确认销售订单允许维护工程输入。", 409)
    item = SalesOrderItem.objects.select_related("sales_order").filter(
        pk=item_id, sales_order=order,
    ).first()
    if not item:
        raise SalesBusinessError("SALES_ORDER_ITEM_NOT_FOUND", "销售订单明细不存在。", 404)
    attribute = _engineering_attribute(user=user, item=item, payload=payload)
    audit = _audit(
        user=user, action_code="sales.order.engineering_input.maintain", target=attribute,
        before={}, after={
            "salesOrderId": order.pk, "salesOrderItemId": item.pk,
            "engineeringAttributeId": attribute.pk,
            "rawSource": attribute.raw_source, "rawSheet": attribute.raw_sheet,
            "externalSource": attribute.external_source,
            "rawField": attribute.raw_field, "rawValue": attribute.raw_value,
            "canonicalField": attribute.canonical_field,
            "normalizedValue": attribute.normalized_value,
            "sourceType": attribute.source_type, "valueType": attribute.value_type,
            "unitId": attribute.unit_id,
            "engineeringDocumentVersionId": attribute.engineering_document_version_id,
        }, authorization=authorization,
    )
    return attribute, audit


@transaction.atomic
def confirm_order(*, user, order_id, authorization):
    row = SalesOrder.objects.select_for_update().prefetch_related("items").filter(pk=order_id, company_id=user.company_id).first()
    if not row: raise SalesBusinessError("SALES_ORDER_NOT_FOUND", "销售订单不存在。", 404)
    if row.status == "confirmed": return row, None
    _require_crm_admission(company_id=user.company_id, order=row, lock=True)
    _workflow_actor(user, "sales.order.confirm")
    if row.status != "draft": raise SalesBusinessError("SALES_ORDER_STATUS_INVALID", "只有草稿销售订单允许确认。", 409)
    if not row.items.exists(): raise SalesBusinessError("SALES_ORDER_ITEMS_REQUIRED", "销售订单至少需要一条有效明细。", 409)
    audit = _audit(user=user, action_code="sales.order.confirm", target=row, before={"status": "draft"}, after={"status": "confirmed"}, authorization=authorization)
    transition_business_object(
        business_object=row, object_type="SalesOrder", source_state="draft", target_state="confirmed",
        action_code="sales.order.confirm", operator=user, reason="销售订单正式确认",
        audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}",
        allowed_transitions=ORDER_ALLOWED_TRANSITIONS,
    )
    row.confirmed_by=user; row.save(update_fields=["confirmed_by", "updated_at"])
    return row, audit


@transaction.atomic
def generate_demand(*, user, order_id, authorization, return_all=False,
                    sales_order_item_id=None, manufacturing_output_ids=None):
    from .manufacturing_input import ManufacturingInputError, resolve_demand_manufacturing_input
    row = SalesOrder.objects.select_for_update().select_related("department").prefetch_related(
        "items__material", "items__product_definition", "items__product_version",
        "items__manufacturing_output",
    ).filter(pk=order_id, company_id=user.company_id).first()
    if not row: raise SalesBusinessError("SALES_ORDER_NOT_FOUND", "销售订单不存在。", 404)
    classification = order_business_classification(row)
    if not classification["planningDemandEligible"]:
        raise SalesBusinessError(
            "SALES_ORDER_NON_BUSINESS_SAMPLE_EXCLUDED",
            "该订单属于 TEST / SYSTEM ACCEPTANCE / NON-BUSINESS SAMPLE，不允许生成新的 Planning Demand。",
            409,
            {"businessClassification": classification},
        )
    _workflow_actor(user, "sales.order.generate_demand")
    if row.status not in {"confirmed", "approved", "engineering", "manufacturing_ready", "in_progress", "delivering", "completed"}:
        raise SalesBusinessError("SALES_ORDER_NOT_APPROVED", "只有已确认或已批准销售订单允许生成正式需求。", 409)
    items = list(row.items.order_by("line_no", "id"))
    def positive_id(value):
        if type(value) is int and value > 0:
            return value
        if isinstance(value, str) and value.isascii() and value.isdecimal() and int(value) > 0:
            return int(value)
        raise SalesBusinessError("SALES_ORDER_SOURCE_SELECTION_INVALID", "来源选择必须使用有效的订单行及制造输出编号。", 409)

    if sales_order_item_id is not None:
        selected_item_id = positive_id(sales_order_item_id)
        items = [item for item in items if item.pk == selected_item_id]
        if not items:
            raise SalesBusinessError("SALES_ORDER_SOURCE_SELECTION_INVALID", "所选订单行不属于当前订单。", 409)
    if manufacturing_output_ids is not None and not isinstance(manufacturing_output_ids, dict):
        raise SalesBusinessError("SALES_ORDER_SOURCE_SELECTION_INVALID", "制造输出选择必须逐项对应订单行。", 409)
    selections = {}
    for item_id, output_id in (manufacturing_output_ids or {}).items():
        item_id, output_id = positive_id(item_id), positive_id(output_id)
        if item_id not in {item.pk for item in items} or item_id in selections:
            raise SalesBusinessError("SALES_ORDER_SOURCE_SELECTION_INVALID", "制造输出选择包含范围外或重复的订单行。", 409)
        selections[item_id] = output_id
    readiness = engineering_readiness_facts(row, manufacturing_output_ids=selections)
    readiness_by_item = {
        value["salesOrderItemId"]: value for value in readiness["lines"]
    }
    blocked = [
        readiness_by_item.get(item.pk, {"salesOrderItemId": item.pk, "ready": False, "blockers": ["未形成制造准备事实"]})
        for item in items
        if not readiness_by_item.get(item.pk, {}).get("ready")
    ]
    if blocked:
        if any(value.get("engineeringSourceSelectionRequired") for value in blocked):
            raise SalesBusinessError(
                "SALES_ORDER_MANUFACTURING_SOURCE_SELECTION_REQUIRED",
                "该订单行存在多个制造来源，请明确选择订单行及正式制造输出版本后办理。", 409,
                {"blockedLines": blocked},
            )
        missing_output = any(
            any("制造输出" in str(reason) for reason in value.get("blockers", []))
            for value in blocked
        )
        detail = "；相关订单行尚未形成并发布正式制造定义。" if missing_output else ""
        raise SalesBusinessError(
            "ORDER_DEMAND_MANUFACTURING_NOT_READY",
            f"存在制造准备未就绪的订单行，不允许进入正式计划需求{detail}",
            409,
            {"blockedLines": blocked},
        )
    # Resolve every source before the first creation. Admission and execution use
    # the same reader; an item FK is not the only order-engineering authority.
    inputs = {}
    for item in items:
        try:
            inputs[item.pk] = resolve_demand_manufacturing_input(
                item, supply_branch=readiness_by_item[item.pk]["supplyBranch"],
                output_id=selections.get(item.pk),
            )
        except ManufacturingInputError as exc:
            raise SalesBusinessError(exc.code, exc.message, 409) from exc
    existing_rows = list(Demand.objects.select_for_update().filter(
        sales_order_item__in=items).select_related("sales_order_item"))
    existing_by_source = {(value.sales_order_item_id, value.manufacturing_output_id): value
                          for value in existing_rows}
    selected_existing = {item.pk: existing_by_source.get((item.pk, inputs[item.pk]["output"].pk
                         if inputs[item.pk]["output"] else None)) for item in items}
    if any(selected_existing.values()) and not all(selected_existing.values()):
        raise SalesBusinessError(
            "SALES_ORDER_DEMAND_DUPLICATE",
            "所选来源仅有部分订单行已生成需求；为避免部分重复，请明确选择单个订单行办理。", 409,
            {"demands": [{"demandId": value.pk, "demandNo": value.demand_no,
                           "salesOrderItemId": value.sales_order_item_id,
                           "manufacturingOutputId": value.manufacturing_output_id}
                          for value in selected_existing.values() if value]},
        )
    if all(selected_existing.values()):
        ordered = [selected_existing[item.pk] for item in items]
        if return_all:
            return ordered, []
        return ordered[0], None
    demands, audits = [], []
    for item in items:
        manufacturing_input = inputs[item.pk]
        output = manufacturing_input["output"]
        if item.product_definition_id:
            if not item.product_version_id or not item.manufacturing_output_id:
                raise SalesBusinessError(
                    "ENGINEERING_OUTPUT_REQUIRED",
                    f"第{item.line_no}行尚未形成并发布正式制造定义，不得进入计划。",
                    409,
                )
            try:
                item.full_clean()
            except Exception as exc:
                raise SalesBusinessError(
                    "ENGINEERING_OUTPUT_INVALID",
                    f"第{item.line_no}行制造定义校验失败：{exc}",
                    409,
                )
        demand_fields = dict(
            demand_no=f"TMP-DM-{timezone.now().timestamp()}-{item.pk}", source_type="sales_order",
            source_document_type="SalesOrderItem", source_document_id=str(item.pk), source_document_no=row.order_no,
            sales_order_item=item, product_definition=item.product_definition,
            product_version=item.product_version, manufacturing_output=output,
            material=item.material, required_qty=item.quantity, required_date=item.required_date,
            department=row.department, reason=f"销售订单 {row.order_no} 第{item.line_no}行客户交付需求",
            acceptance_marker=row.acceptance_marker, created_by=user,
        )
        Demand(**demand_fields).clean()
        demand = create_business_object_with_initial_state(
            model=Demand, initial_state="draft", **demand_fields,
        )
        demand.demand_no = _number("DM", demand)
        demand.save(update_fields=["demand_no", "updated_at"])
        if item.product_definition_id:
            ProductEngineeringReadiness.objects.create(
                sales_order=row, sales_order_item=item, order_no=row.order_no,
                product=item.product_definition, delivery_date=item.required_date,
            )
        if item.product_definition_id or manufacturing_input["facts"]["definitionMode"] == "ORDER_ENGINEERED_PRODUCT":
            ManufacturingInputReference.objects.create(
                target_module="MRP",
                source_object=f"ProductManufacturingOutput:{output.pk}",
                target_object=f"Demand:{demand.pk}",
                source_manufacturing_output=output,
                target_demand=demand, reference_status="active",
            )
        audit_state = {
            "salesOrderId": row.pk, "salesOrderNo": row.order_no, "salesOrderItemId": item.pk,
            "demandNo": demand.demand_no, "materialCode": item.material.code,
            "productDefinitionId": item.product_definition_id,
            "productVersionId": item.product_version_id,
            "manufacturingOutputId": output.pk if output else None,
            "manufacturingInput": manufacturing_input["facts"],
            "requiredQty": str(demand.required_qty), "requiredDate": demand.required_date.isoformat(),
            "initialState": "draft",
        }
        # Each persisted step has its own authoritative audit reference.
        initialization_audit = _audit(
            user=user, action_code="sales.order.generate_demand", target=demand,
            before={}, after={**audit_state, "status": "draft"},
            authorization=authorization, reason="销售订单需求状态初始化",
        )
        record_projected_business_transition(
            object_type="Demand", object_id=demand.pk,
            source_state="", target_state="draft",
            action_code="sales.order.generate_demand", operator=user,
            reason=f"销售订单 {row.order_no} 第{item.line_no}行需求初始化",
            audit_reference=f"OrganizationOperatingAuditRecord:{initialization_audit.pk}",
            allowed_transitions={("", "draft")},
        )
        audit = _audit(
            user=user, action_code="sales.order.generate_demand", target=demand,
            before={"status": "draft"}, after={**audit_state, "status": "confirmed"},
            authorization=authorization,
        )
        transition_business_object(
            business_object=demand, object_type="Demand",
            source_state="draft", target_state="confirmed",
            action_code="sales.order.generate_demand", operator=user,
            reason=f"销售订单 {row.order_no} 第{item.line_no}行客户交付需求确认",
            audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}",
            allowed_transitions={("draft", "confirmed")}, version_field=None,
        )
        demands.append(demand)
        audits.append(audit)
    if return_all:
        return demands, audits
    return demands[0], audits[0]


def transition_facts(row):
    history = list(BusinessStateTransition.objects.filter(object_type="SalesOrder", object_id=row.pk).order_by("version").values(
        "source_state", "target_state", "action_code", "version", "timestamp", "audit_reference"
    ))
    return {"statusTransitionHistory": history, "statusTransitionCount": len(history), "stateMachineConsistent": all(item["version"] == index for index, item in enumerate(history, 1))}


def engineering_readiness_facts(row, *, manufacturing_output_ids=None):
    from .supply_admission_service import supply_admission_facts
    from .manufacturing_input import (
        ManufacturingInputError, is_order_engineered_product, resolve_order_engineered_input,
    )
    lines, blocker_count = [], 0
    classification = order_business_classification(row)
    for item in row.items.select_related(
        "material", "product_configuration__template", "product_definition", "product_version",
        "manufacturing_output", "order_engineering_instance",
    ).order_by("line_no", "id"):
        blockers = []
        output = item.manufacturing_output
        order_engineered = is_order_engineered_product(item)
        manufacturing_input = None
        engineering_blocker_code = None
        engineering_selection = {}
        related_instance = _related(item, "order_engineering_instance")
        supply_admission = supply_admission_facts(item)
        supply_branch = supply_admission["supplyBranch"]
        manufacturing_applicable = supply_branch == "MAKE"
        if not classification["realBusinessAcceptanceEligible"]:
            blockers.append("历史测试/系统验收订单，已排除真实业务验收与未来 Planning Demand")
        if supply_branch == "UNRESOLVED":
            blockers.append("订单行供应承接事实未确认或无效，无法判定 MAKE / BUY")
        if manufacturing_applicable and order_engineered:
            try:
                resolved = resolve_order_engineered_input(
                    item, output_id=(manufacturing_output_ids or {}).get(item.pk),
                )
                output, manufacturing_input = resolved["output"], resolved["facts"]
            except ManufacturingInputError as exc:
                blockers.append(exc.message)
                engineering_blocker_code = exc.code
                engineering_selection = exc.details
        if manufacturing_applicable and not order_engineered and not item.product_definition_id:
            blockers.append("制造型订单行缺少正式销售产品身份/ProductDefinition")
        if item.engineering_mode == "TEMPLATE_ASSISTED":
            if not item.product_configuration_id:
                blockers.append("缺少正式产品配置")
            elif item.product_configuration.status != "resolved":
                blockers.append("产品配置尚未解析")
            if not item.product_definition_id:
                blockers.append("配置尚未解析为正式产品定义")
            if not output and not item.product_definition_id:
                blockers.append("缺少制造输出")
        if item.engineering_mode == "ORDER_ENGINEERED" and not order_engineered:
            instance = related_instance = _related(item, "order_engineering_instance")
            if not instance:
                blockers.append("缺少按单工程实例")
            elif instance.status != "released":
                blockers.append("按单工程实例尚未发布")
        if item.product_definition_id and not order_engineered:
            if not item.product_version_id:
                blockers.append("缺少正式产品版本")
            if not output:
                blockers.append("缺少制造输出")
            elif output.release_status != "released_to_manufacturing":
                blockers.append("制造输出尚未发布")
            elif not output.bom_version_id:
                blockers.append("制造输出缺少正式 BOM")
            elif not output.routing_version_id:
                blockers.append("制造输出缺少正式 Routing")
        readiness = _related(item, "engineering_readiness")
        manufacturing_ready = manufacturing_applicable and not blockers
        branch_ready = (
            supply_branch == "BUY" and classification["planningDemandEligible"]
        ) or manufacturing_ready
        blocker_count += len(blockers)
        lines.append({
            "salesOrderItemId": item.pk, "lineNo": item.line_no,
            "engineeringMode": item.engineering_mode,
            "definitionMode": "ORDER_ENGINEERED_PRODUCT" if order_engineered else "LONG_TERM_PRODUCT",
            "manufacturingInput": manufacturing_input,
            "engineeringBlockerCode": engineering_blocker_code,
            "engineeringSourceSelectionRequired": engineering_selection.get("selectionRequired", False),
            "manufacturingOutputCandidates": engineering_selection.get("manufacturingOutputIds", []),
            "ready": branch_ready, "manufacturingReady": manufacturing_ready,
            "manufacturingApplicable": manufacturing_applicable,
            "supplyBranch": supply_branch,
            "supplyAdmission": supply_admission,
            "planningDemandEligible": classification["planningDemandEligible"] and branch_ready,
            "blockers": blockers,
            "engineeringInstanceId": related_instance.pk if item.engineering_mode == "ORDER_ENGINEERED" and related_instance else None,
            "manufacturingOutputId": output.pk if output else None,
            "readinessId": readiness.pk if readiness else None,
            "engineeringStatus": readiness.engineering_status if readiness else ("manufacturing_ready" if manufacturing_ready else "not_started"),
            "bomStatus": manufacturing_input["bomStatus"] if manufacturing_input else (readiness.bom_status if readiness else "not_started"),
            "routingStatus": manufacturing_input["routingStatus"] if manufacturing_input else (readiness.routing_status if readiness else "not_started"),
            "documentStatus": manufacturing_input["documentStatus"] if manufacturing_input else (readiness.document_status if readiness else "not_started"),
            "manufacturingOutputStatus": readiness.manufacturing_output_status if readiness else ("manufacturing_ready" if manufacturing_ready else "not_started"),
            "deliveryRisk": readiness.delivery_risk if readiness else "on_track",
        })
    return {
        "ready": bool(lines) and all(value["ready"] for value in lines),
        "manufacturingReady": bool(lines) and all(value["manufacturingReady"] for value in lines),
        "businessClassification": classification,
        "blockerCount": blocker_count,
        "lines": lines,
    }


def order_stage_readiness_facts(row):
    """Keep order, demand, supply planning and scheduling admission distinct."""

    engineering = engineering_readiness_facts(row)
    lines = list(row.items.all())
    classification = engineering["businessClassification"]
    approved_states = {
        "approved", "confirmed", "engineering", "manufacturing_ready",
        "in_progress", "delivering", "completed",
    }
    demand_blockers = []
    if not classification["planningDemandEligible"]:
        demand_blockers.append(classification["reason"])
    if row.status not in approved_states:
        demand_blockers.append("订单尚未确认或批准；订单建档本身仍可查看和维护。")
    demand_blockers.extend(
        reason
        for line in engineering["lines"] if not line["planningDemandEligible"]
        for reason in line["blockers"]
    )
    demand_count = Demand.objects.filter(sales_order_item__in=lines).count() if lines else 0
    make_lines = [line for line in engineering["lines"] if line["manufacturingApplicable"]]
    buy_lines = [line for line in engineering["lines"] if line["supplyBranch"] == "BUY"]
    unresolved_lines = [line for line in engineering["lines"] if line["supplyBranch"] == "UNRESOLVED"]

    return {
        "orderRecord": {
            "status": "READY",
            "eligible": True,
            "reason": "订单头与订单行已建档；制造资源缺失不反向否定订单基础事实。",
        },
        "orderConfirmationAndDemand": {
            "status": "READY" if lines and not demand_blockers else "BLOCKED",
            "eligible": bool(lines) and not demand_blockers,
            "blockers": list(dict.fromkeys(demand_blockers)),
        },
        "supplyPlanPreparation": {
            "status": (
                "READY" if demand_count == len(lines) and lines and not unresolved_lines
                else "WAITING_FOR_DEMAND" if demand_count < len(lines)
                else "BLOCKED"
            ),
            "demandCount": demand_count,
            "orderLineCount": len(lines),
            "buyLineCount": len(buy_lines),
            "makeLineCount": len(make_lines),
            "unresolvedLineCount": len(unresolved_lines),
            "reason": "外购行不要求制造基础资料；自产行继续服从已发布制造输出门禁。",
        },
        "manufacturingPreparation": {
            "status": (
                "NOT_APPLICABLE" if not make_lines
                else "READY" if all(line["manufacturingReady"] for line in make_lines)
                else "BLOCKED"
            ),
            "applicableLineCount": len(make_lines),
            "blockers": list(dict.fromkeys(
                reason for line in make_lines if not line["manufacturingReady"]
                for reason in line["blockers"]
            )),
        },
        "finiteCapacityScheduling": {
            "status": "NOT_APPLICABLE" if not make_lines else "NOT_DEPLOYED",
            "eligible": False,
            "reason": (
                "外购行不进入制造资源排程。" if not make_lines
                else "有限产能排程尚未部署；不得用客户交期排序或伪造资源日期替代。"
            ),
        },
    }


def _approval_instance(row):
    return WorkflowInstance.objects.filter(document_type="SalesOrder", document_id=row.pk).first()


@transaction.atomic
def update_order(*, user, order_id, payload, authorization):
    row = SalesOrder.objects.select_for_update().prefetch_related("items").filter(
        pk=order_id, company_id=user.company_id,
    ).first()
    if not row:
        raise SalesBusinessError("SALES_ORDER_NOT_FOUND", "销售订单不存在。", 404)
    _workflow_actor(user, "sales.order.update")
    if row.status != "draft":
        raise SalesBusinessError("SALES_ORDER_EDIT_STATUS_INVALID", "只有草稿订单允许编辑。", 409)
    expected_version = payload.get("version")
    if expected_version is not None and int(expected_version) != row.version:
        raise SalesBusinessError("SALES_ORDER_VERSION_CONFLICT", "订单已被其他操作更新，请刷新后重试。", 409)
    before = {
        "orderType": row.order_type, "orderSource": row.order_source,
        "requiredDate": str(row.required_delivery_date), "remark": row.remark,
    }
    field_map = {
        "orderType": "order_type", "orderSource": "order_source", "orderDate": "order_date",
        "requiredDate": "required_delivery_date", "currency": "currency",
        "projectReference": "project_reference", "contractReference": "contract_reference",
        "externalSourceNo": "external_source_no", "deliveryInformation": "delivery_information",
        "remark": "remark",
    }
    changed = []
    for api_name, model_name in field_map.items():
        if api_name in payload:
            setattr(row, model_name, payload[api_name])
            changed.append(model_name)
    row.version += 1
    changed.extend(["version", "updated_at"])
    row.save(update_fields=changed)
    audit = _audit(
        user=user, action_code="sales.order.update", target=row, before=before,
        after={"version": row.version, **{key: payload[key] for key in field_map if key in payload}},
        authorization=authorization, reason=str(payload.get("reason") or "编辑销售订单草稿"),
    )
    return row, audit


@transaction.atomic
def update_order_item(*, user, order_id, item_id, payload, authorization):
    row = SalesOrder.objects.select_for_update().filter(
        pk=order_id, company_id=user.company_id,
    ).first()
    if not row:
        raise SalesBusinessError("SALES_ORDER_NOT_FOUND", "销售订单不存在。", 404)
    _workflow_actor(user, "sales.order.update")
    if row.status != "draft":
        raise SalesBusinessError("SALES_ORDER_EDIT_STATUS_INVALID", "只有草稿订单允许编辑明细。", 409)
    item = SalesOrderItem.objects.select_for_update().filter(pk=item_id, sales_order=row).first()
    if not item:
        raise SalesBusinessError("SALES_ORDER_ITEM_NOT_FOUND", "销售订单明细不存在。", 404)
    expected_version = payload.get("version")
    if expected_version is not None and int(expected_version) != row.version:
        raise SalesBusinessError("SALES_ORDER_VERSION_CONFLICT", "订单已被其他操作更新，请刷新后重试。", 409)
    before = {
        "lineNo": item.line_no, "materialId": item.material_id,
        "quantity": str(item.quantity), "engineeringMode": item.engineering_mode,
    }
    field_map = {
        "lineNo": "line_no", "materialId": "material_id", "uomId": "uom_id",
        "productDefinitionId": "product_definition_id", "productVersionId": "product_version_id",
        "productConfigurationId": "product_configuration_id", "manufacturingOutputId": "manufacturing_output_id",
        "requiredDate": "required_date", "engineeringMode": "engineering_mode",
        "spaceCode": "space_code", "spaceName": "space_name",
        "installationArea": "installation_area", "componentCategory": "component_category",
        "customerProductName": "customer_product_name", "customerProductDescription": "customer_product_description",
        "specification": "specification", "configurationReference": "configuration_reference",
        "engineeringRequirements": "engineering_requirements", "qualityRequirements": "quality_requirements",
        "remark": "remark", "priceTaxMode": "price_tax_mode",
    }
    for api_name, model_name in field_map.items():
        if api_name in payload:
            setattr(item, model_name, payload[api_name] or None if model_name.endswith("_id") else payload[api_name])
    for api_name, model_name in (("quantity", "quantity"), ("unitPrice", "unit_price"), ("taxRate", "tax_rate")):
        if api_name in payload:
            try: setattr(item, model_name, Decimal(str(payload[api_name])))
            except (InvalidOperation, TypeError):
                raise SalesBusinessError("ORDER_ITEM_NUMBER_INVALID", f"{api_name}必须是有效数字。")
    try:
        item.full_clean()
    except Exception as exc:
        raise SalesBusinessError("SALES_ORDER_ITEM_INVALID", f"订单明细正式引用校验失败：{exc}")
    item.save()
    row.version += 1
    row.save(update_fields=["version", "updated_at"])
    audit = _audit(
        user=user, action_code="sales.order.update", target=row, before=before,
        after={
            "salesOrderItemId": item.pk, "version": row.version,
            "lineNo": item.line_no, "materialId": item.material_id,
            "quantity": str(item.quantity), "unitPrice": str(item.unit_price),
            "taxRate": str(item.tax_rate), "priceTaxMode": item.price_tax_mode,
            "engineeringMode": item.engineering_mode,
        }, authorization=authorization, reason=str(payload.get("reason") or "编辑销售订单明细"),
    )
    return row, item, audit


@transaction.atomic
def perform_order_action(*, user, order_id, action, payload, authorization):
    definition = ORDER_ACTIONS.get(action)
    if not definition:
        raise SalesBusinessError("SALES_ORDER_ACTION_INVALID", "未知销售订单动作。", 404)
    action_code, source_states, target_state, default_reason = definition
    row = SalesOrder.objects.select_for_update().prefetch_related("items").filter(
        pk=order_id, company_id=user.company_id,
    ).first()
    if not row:
        raise SalesBusinessError("SALES_ORDER_NOT_FOUND", "销售订单不存在。", 404)
    _workflow_actor(user, action_code)
    idempotency_key = str(payload.get("idempotencyKey") or "").strip()
    request_id = str(payload.get("requestId") or "").strip()
    if not idempotency_key or not request_id:
        raise SalesBusinessError("SALES_ACTION_IDEMPOTENCY_REQUIRED", "状态动作必须提供 idempotencyKey 和 requestId。", 400)
    previous = SalesOrderActionRequest.objects.filter(
        sales_order=row, action_code=action_code, idempotency_key=idempotency_key,
    ).select_related("audit_record").first()
    if previous:
        return row, previous.audit_record, previous, True
    if action not in {"cancel", "close"}:
        _require_crm_admission(company_id=user.company_id, order=row, lock=True)
    if row.status not in source_states:
        raise SalesBusinessError(
            "SALES_ORDER_STATUS_INVALID",
            f"当前状态“{row.get_status_display()}”不允许执行“{default_reason}”。", 409,
        )
    if not row.items.exists():
        raise SalesBusinessError("SALES_ORDER_ITEMS_REQUIRED", "销售订单至少需要一条有效明细。", 409)
    if action == "approve" and row.created_by_id == user.pk:
        raise SalesBusinessError("SALES_ORDER_SOD_DENIED", "订单创建人不得批准本人创建的订单。", 403)
    readiness = engineering_readiness_facts(row)
    if action == "complete-engineering" and not readiness["ready"]:
        raise SalesBusinessError(
            "SALES_ENGINEERING_NOT_READY", "工程或制造输出尚未齐套，不能完成工程准备。", 409,
            {"engineeringReadiness": readiness},
        )
    workflow_instance = _approval_instance(row)
    if action == "submit":
        process = ProcessDefinition.objects.get(definition_code=PROCESS_CODE, active=True)
        workflow_instance, _ = WorkflowInstance.objects.get_or_create(
            document_type="SalesOrder", document_id=row.pk,
            defaults={
                "instance_no": f"SO-APP-{row.pk:08d}", "process_definition": process,
                "status": WorkflowInstance.Status.PENDING, "current_step": 1,
                "total_steps": 1,
            },
        )
        ApprovalTask.objects.get_or_create(
            workflow_instance=workflow_instance, step_no=1,
            defaults={
                "task_no": f"SO-APP-TASK-{row.pk:08d}-01",
                "required_role_code": "sales_order_approver", "minimum_approvals": 1,
                "status": ApprovalTask.Status.PENDING,
            },
        )
    if action == "approve":
        if not workflow_instance:
            raise SalesBusinessError("SALES_APPROVAL_INSTANCE_REQUIRED", "订单未形成正式审批实例。", 409)
        task = workflow_instance.tasks.select_for_update().filter(status=ApprovalTask.Status.PENDING).first()
        if not task:
            raise SalesBusinessError("SALES_APPROVAL_TASK_REQUIRED", "订单没有待处理审批任务。", 409)
        digest = hashlib.sha256(f"{task.pk}|{user.pk}|{request_id}|approved".encode()).hexdigest()
        ApprovalDecision.objects.create(
            task=task, decision_sequence=task.decisions.count() + 1, actor=user,
            decision="approved", comment=str(payload.get("comment") or ""),
            action_id=request_id, idempotency_key=idempotency_key, decision_hash=digest,
        )
        task.status = ApprovalTask.Status.APPROVED
        task.completed_at = timezone.now()
        task.save(update_fields=["status", "completed_at", "version"])
        workflow_instance.status = WorkflowInstance.Status.APPROVED
        workflow_instance.completed_at = timezone.now()
        workflow_instance.save(update_fields=["status", "completed_at", "version"])
    reason = str(payload.get("reason") or default_reason)
    audit = _audit(
        user=user, action_code=action_code, target=row,
        before={"status": row.status, "version": row.version},
        after={
            "status": target_state, "requestId": request_id,
            "idempotencyKey": idempotency_key, "source": payload.get("source") or "api",
            "engineeringReadiness": readiness,
        }, authorization=authorization, reason=reason,
    )
    source_state = row.status
    transition_business_object(
        business_object=row, object_type="SalesOrder", source_state=source_state,
        target_state=target_state, action_code=action_code, operator=user, reason=reason,
        audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}",
        workflow_instance=workflow_instance, allowed_transitions=ORDER_ALLOWED_TRANSITIONS,
    )
    if action == "approve":
        row.approved_by = user
        row.save(update_fields=["approved_by", "updated_at"])
    action_request = SalesOrderActionRequest.objects.create(
        sales_order=row, action_code=action_code, idempotency_key=idempotency_key,
        request_id=request_id, source=str(payload.get("source") or "api"), actor=user,
        source_state=source_state, target_state=target_state, audit_record=audit,
    )
    return row, audit, action_request, False
