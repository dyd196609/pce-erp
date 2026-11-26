"""Governed whole-house source intake through the original SalesOrder chain."""
from django.db import transaction
from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from system.models import Department
from .models import Customer, SalesOrder
from .services import SalesBusinessError, create_order
from .whole_house_preview import whole_house_order_preview
from .source_review import (
    SOURCE_SYSTEM, SOURCE_TYPE, SOURCE_OBJECT_TYPE, ACTIONS,
    canonical_hash as _canonical_hash, governed_source_contract, identity_query,
    review_state, validate_resolution, source_actor, mapping_candidates,
)

ACTION_CODE = "sales.order.source_intake.create"


def build_whole_house_intake_preview(company_id, user=None):
    preview = whole_house_order_preview()
    state = review_state(company_id)
    candidates = mapping_candidates(company_id)
    engineering_by_code = {r["sourceCode"]: r for r in candidates["engineeringMaterials"]}
    for row in preview["sourceLineIdentities"]:
        row["engineeringMapping"] = engineering_by_code.get(row["engineeringSourceCode"])
        row["savedProposedSalesLines"] = [i for i, line in enumerate(state["resolution"]["lines"], 1) if row["salesOrderItemNo"] in line["sourceLineIds"]]
    actions = []
    for key, (label, permission) in ACTIONS.items():
        allowed, reason = False, "请使用正常登录身份办理。"
        if user:
            try:
                source_actor(user, key, state["resolution"].get("departmentId"))
                allowed, reason = True, ""
            except SalesBusinessError as error:
                reason = error.message
        if key == "create-draft" and not state["allowed"]:
            allowed, reason = False, "先保存映射并分别完成来源、映射及数量确认。"
        if key != "create-draft" and state["targetOrderId"]:
            allowed, reason = False, "来源已建档；后续变更请走原销售订单。"
        actions.append({"action": key, "label": label, "requiredPermission": permission, "allowed": allowed, "reason": reason})
    links = [
        {"label": "返回销售订单（草稿提交、审批另行办理）", "path": "/sales/orders"},
        {"label": "返回 CRM 流程", "path": "/process-center?module=CRM"},
    ]
    common = {"sourceFingerprint": state["binding"]["sourceFingerprint"], "binding": state["binding"],
        "qualificationStatus": "QUALIFIED" if "confirm-source" in state["effectiveConfirmations"] else "AWAITING_USER_VALIDATION",
        "sourceRecordCount": len(preview["sourceLineIdentities"]), "categorySummaryCount": len(preview["productGroups"]),
        "proposedSalesLineCount": len(state["resolution"]["lines"]), "review": state,
        "businessWriteCount": 0, "planningWriteCount": 0,
        "sourceRows": preview["sourceLineIdentities"], "masterMappings": candidates, "quantityPrecision": preview["quantityPrecision"],
        "factSource": "archived normalized evidence + current organization master data + persistent source audits"}
    return {**preview, "readOnly": False, "rawSourceReadOnly": True,
        "previewStatus": common["qualificationStatus"],
        "readiness": {"customerResolvedId": candidates["resolvedCustomerId"],
            "sourceStatusLabel": state["sourceStatusLabel"], "mappingStatusLabel": state["mappingStatusLabel"],
            "draftCreationAllowed": state["allowed"]},
        "sourceFingerprint": common["sourceFingerprint"], "review": state, "actions": actions,
        "databaseResolution": candidates, "navigation": links,
        "maintenanceLinks": [
            {"label": "正式客户维护", "path": "/foundation/erp/customers"},
            {"label": "正式物料及基本单位", "path": "/foundation/erp/materials"},
            {"label": "产品设计管理", "path": "/pde/product-definitions"},
            {"label": "部门体系", "path": "/organization-model/departments"},
        ],
        "formalApplication": {"status": "READY" if state["allowed"] else "BLOCKED", "statusLabel": state["statusLabel"],
            "allowed": state["allowed"], "businessWriteCount": 0, "blockers": state["blockers"]},
        "stageReadiness": [
            {"label": "来源与映射", "statusLabel": state["statusLabel"], "reason": "按凭据关联；工程量不自动计入销售量。"},
            {"label": "订单草稿", "statusLabel": "可办理" if state["allowed"] else "尚未满足建档条件", "reason": "只建草稿；正式提交审批仍走原订单。"},
            {"label": "需求与制造准备", "statusLabel": "独立门禁", "reason": "建档不是需求授权，工程与制造输出须独立就绪。"},
            {"label": "有限产能排程", "statusLabel": "未部署", "reason": "交期排序不等于资源排程。"},
        ], "apiFacts": common, "pageFacts": common, "diagnosticFacts": common, "strictFacts": common}


@transaction.atomic
def commit_source_intake(*, user, resolver, authorization, failure_injector=None):
    """Apply one qualified source through the existing ``create_order`` service."""

    contract = governed_source_contract()
    identity_query(user.company_id).select_for_update().first()
    state = review_state(user.company_id)
    actor, authorization = source_actor(user, "create-draft", state["resolution"].get("departmentId"))
    if not state["allowed"]:
        raise SalesBusinessError("SOURCE_NOT_QUALIFIED", "来源资格、映射或商业数量确认尚未完成；不能创建草稿。", 409)
    if resolver.get("binding") != state["binding"] or resolver.get("confirmed") is not True:
        raise SalesBusinessError("SOURCE_PREVIEW_STALE", "请显式确认同一来源及映射版本后创建草稿。", 409)
    items, checks = validate_resolution(user.company_id, state["resolution"])
    order_payload = {
        "customerId": state["resolution"]["customerId"], "departmentId": state["resolution"]["departmentId"],
        "orderDate": contract["order"]["orderDate"], "requiredDate": contract["order"]["deliveryDate"],
        "orderType": "standard", "orderSource": "import", "projectReference": contract["order"]["project"],
        "externalSourceNo": contract["order"]["externalOrderNo"], "items": items,
        "remark": "来源资格及映射确认后建档；不含后续订单审批、需求及计划授权。",
        "sourceIntakeFacts": {"sourceFingerprint": contract["sourceFingerprint"], "binding": state["binding"],
            "resolver": state["resolution"], "quantityChecks": checks, "confirmationAuditIds": state["effectiveConfirmations"]},
    }
    if not str(resolver.get("idempotencyKey") or "").strip():
        raise SalesBusinessError("IDEMPOTENCY_KEY_REQUIRED", "来源应用必须提供幂等键。", 400)
    if not Customer.objects.filter(pk=order_payload["customerId"], company_id=user.company_id, is_active=True).exists():
        raise SalesBusinessError("CUSTOMER_INVALID", "正式客户解析结果无效。", 409)
    if not Department.objects.filter(pk=order_payload["departmentId"], company_id=user.company_id, is_active=True).exists():
        raise SalesBusinessError("DEPARTMENT_INVALID", "正式销售部门解析结果无效。", 409)

    request_hash = _canonical_hash(order_payload)
    external_id = contract["order"]["externalOrderNo"]
    identity, created = ExternalIdentity.objects.select_for_update().get_or_create(
        organization_id=user.company_id,
        source_system=SOURCE_SYSTEM,
        source_type=SOURCE_TYPE,
        source_object_type=SOURCE_OBJECT_TYPE,
        external_id=external_id,
        defaults={
            "target_entity_type": "SalesOrder",
            "mapping_status": ExternalIdentity.MappingStatus.REVIEW,
            "source_fingerprint": contract["sourceFingerprint"],
            "audit_metadata": {"source": contract["source"]},
        },
    )
    if not created and identity.source_fingerprint and identity.source_fingerprint != contract["sourceFingerprint"]:
        raise SalesBusinessError("SOURCE_IDENTITY_CONFLICT", "同一外部订单身份对应的来源指纹已变化。", 409)

    write_request, request_created = MasterDataWriteRequest.objects.select_for_update().get_or_create(
        organization_id=user.company_id,
        action_code=ACTION_CODE,
        entity_type="SalesOrder",
        idempotency_key=str(resolver["idempotencyKey"]).strip(),
        defaults={
            "request_hash": request_hash,
            "source_identity": identity,
            "audit_metadata": {"requestId": str(resolver.get("requestId") or "")},
        },
    )
    if not request_created:
        if write_request.request_hash != request_hash or write_request.source_identity_id != identity.pk:
            raise SalesBusinessError("IDEMPOTENCY_CONFLICT", "同一幂等键已用于不同来源应用请求。", 409)
        if write_request.status == MasterDataWriteRequest.Status.COMMITTED:
            order = SalesOrder.objects.filter(pk=write_request.target_entity_id, company_id=user.company_id).first()
            if not order:
                raise SalesBusinessError("IDEMPOTENCY_RESULT_MISSING", "幂等记录指向的正式订单不存在。", 409)
            return order, None, write_request, True

    if identity.mapping_status == ExternalIdentity.MappingStatus.MATCH and identity.target_entity_id:
        previous_hash = (identity.audit_metadata or {}).get("requestHash")
        if previous_hash != request_hash:
            raise SalesBusinessError(
                "SOURCE_TARGET_ALREADY_MAPPED",
                "同一外部订单身份已映射正式订单，但本次解析载荷不同；禁止重复或静默改写。",
                409,
            )
        order = SalesOrder.objects.filter(pk=identity.target_entity_id, company_id=user.company_id).first()
        if not order:
            raise SalesBusinessError("SOURCE_TARGET_MISSING", "来源身份指向的正式订单不存在。", 409)
        write_request.status = MasterDataWriteRequest.Status.COMMITTED
        write_request.target_entity_id = str(order.pk)
        write_request.result = {
            "salesOrderId": order.pk,
            "orderNo": order.order_no,
            "auditId": (identity.audit_metadata or {}).get("auditId"),
        }
        write_request.save(update_fields=["status", "target_entity_id", "result", "updated_at"])
        return order, None, write_request, True

    row, _item, audit = create_order(
        user=user,
        payload=order_payload,
        authorization=authorization,
        business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
    )
    if failure_injector:
        failure_injector("after_order_create", row)
    identity.target_entity_type = "SalesOrder"
    identity.target_entity_id = str(row.pk)
    identity.mapping_status = ExternalIdentity.MappingStatus.MATCH
    identity.source_fingerprint = contract["sourceFingerprint"]
    identity.audit_metadata = {
        **(identity.audit_metadata or {}),
        "source": contract["source"], "auditId": audit.pk, "requestHash": request_hash,
    }
    identity.full_clean()
    identity.save()
    write_request.status = MasterDataWriteRequest.Status.COMMITTED
    write_request.target_entity_id = str(row.pk)
    write_request.result = {"salesOrderId": row.pk, "orderNo": row.order_no, "auditId": audit.pk}
    write_request.save(update_fields=["status", "target_entity_id", "result", "updated_at"])
    return row, audit, write_request, False
