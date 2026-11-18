"""Formal, auditable current CRM source binding for an existing SalesOrder.

The binding reuses the existing ``ExternalIdentity`` authority.  It never
rewrites an ``EngineeringSourceRecord`` payload and it deliberately does not
create a CRM review or any PDE admission relation.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json

from django.db import transaction

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from pde.crm_sales_order_identity import normalize_business_text, source_business_identity
from pde.models import EngineeringSourceRecord, ProductDesignItem
from system.models import OrganizationOperatingAuditRecord

from .models import SalesOrder
from .order_business_identity_correction import (
    SalesOrderBusinessIdentityCorrectionError,
    _assert_actor_authorized,
)


SOURCE_SYSTEM = "PCE_ENGINEERING_SOURCE"
SOURCE_TYPE = "FORMAL_CRM_CURRENT_SOURCE"
SOURCE_OBJECT_TYPE = "ENGINEERING_SOURCE_RECORD"
TARGET_ENTITY_TYPE = "SalesOrder"
ACTION_CODE = "sales.order.crm_source.establish"


class SalesOrderCRMSourceEstablishmentError(ValueError):
    def __init__(self, code, message, *, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class CRMCurrentSourceBinding:
    identity: ExternalIdentity
    source: EngineeringSourceRecord
    scope: dict

    def as_dict(self):
        return {
            "identityId": self.identity.pk,
            "sourceRecordId": self.source.pk,
            "sourceNo": self.source.source_no,
            "sourceOrderNo": self.scope["sourceOrderNo"],
            "sourceVersion": self.source.source_version,
            "sourceContentHash": self.source.content_hash,
            "sourceStatus": self.source.status,
            "salesOrderId": self.scope["salesOrderId"],
            "salesOrderNo": self.scope["salesOrderNo"],
            "engineeringRowCount": self.scope["engineeringRowCount"],
            "commercialLineCount": self.scope["commercialLineCount"],
            "designDistribution": self.scope["designDistribution"],
            "establishedAt": self.identity.first_seen.isoformat(),
            "statusCode": "CRM_ORDER_CURRENT_SOURCE_VALID",
            "statusLabel": "当前正式CRM来源已建立",
        }


def _canonical_hash(value):
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest().upper()


def _external_id(source):
    return f"EngineeringSourceRecord:{source.pk}:{source.source_version}"


def _binding_query(*, order, lock=False):
    rows = ExternalIdentity.objects.filter(
        organization_id=order.company_id,
        source_system=SOURCE_SYSTEM,
        source_type=SOURCE_TYPE,
        source_object_type=SOURCE_OBJECT_TYPE,
        target_entity_type=TARGET_ENTITY_TYPE,
        target_entity_id=str(order.pk),
        mapping_status=ExternalIdentity.MappingStatus.MATCH,
    ).order_by("pk")
    return rows.select_for_update() if lock else rows


def _raise(code, message, **details):
    raise SalesOrderCRMSourceEstablishmentError(
        code, message, details=details,
    )


def _validate_source_and_order(*, source, order):
    if source.company_id != order.company_id:
        _raise(
            "CRM_SOURCE_COMPANY_MISMATCH",
            "CRM来源与销售订单不属于同一公司，已失败关闭。",
            sourceCompanyId=source.company_id,
            salesOrderCompanyId=order.company_id,
        )
    if source.status != "confirmed":
        _raise(
            "CRM_SOURCE_NOT_CONFIRMED",
            "只有当前已确认的工程来源可以建立正式CRM来源关系。",
            sourceRecordId=source.pk,
            sourceStatus=source.status,
        )
    current_ids = list(
        EngineeringSourceRecord.objects.filter(
            company_id=source.company_id,
            source_no=source.source_no,
            status="confirmed",
        ).values_list("pk", flat=True)[:3]
    )
    if current_ids != [source.pk]:
        _raise(
            "CRM_SOURCE_CURRENT_VERSION_AMBIGUOUS",
            "同一来源号存在多个当前已确认版本，禁止建立当前关系。",
            sourceRecordIds=current_ids,
        )

    expected = source_business_identity(source)
    comparisons = {
        "customer": {
            "source": expected["customerName"],
            "order": order.customer.name,
            "matches": bool(expected["customerName"]) and (
                normalize_business_text(expected["customerName"])
                == normalize_business_text(order.customer.name)
            ),
        },
        "project": {
            "source": expected["projectReference"],
            "order": order.project_reference,
            "matches": bool(expected["projectReference"])
            and bool(order.project_reference)
            and (
                normalize_business_text(expected["projectReference"])
                == normalize_business_text(order.project_reference)
            ),
        },
        "externalSourceNo": {
            "source": expected["sourceOrderNo"],
            "order": order.external_source_no,
            "matches": bool(expected["sourceOrderNo"])
            and expected["sourceOrderNo"] == str(order.external_source_no or "").strip(),
        },
    }
    failures = [key for key, value in comparisons.items() if not value["matches"]]
    if failures:
        _raise(
            "CRM_SOURCE_BUSINESS_IDENTITY_MISMATCH",
            "CRM来源与销售订单的客户、项目或外部来源号不一致，禁止建立关系。",
            failedFields=failures,
            comparisons=comparisons,
        )

    payload = source.source_payload if isinstance(source.source_payload, dict) else {}
    engineering_rows = payload.get("engineeringRows")
    if not isinstance(engineering_rows, list) or not engineering_rows:
        _raise(
            "CRM_SOURCE_ENGINEERING_SCOPE_REQUIRED",
            "CRM来源没有可核验的稳定工程行范围，禁止建立关系。",
            sourceRecordId=source.pk,
        )
    stable_ids = [
        str(row.get("id") or "").strip()
        for row in engineering_rows if isinstance(row, dict)
    ]
    if (
        len(stable_ids) != len(engineering_rows)
        or any(not value for value in stable_ids)
        or len(set(stable_ids)) != len(stable_ids)
    ):
        _raise(
            "CRM_SOURCE_ENGINEERING_SCOPE_INVALID",
            "CRM来源工程行稳定身份缺失或重复，禁止建立关系。",
            sourceRecordId=source.pk,
        )

    design_rows = list(
        ProductDesignItem.objects.filter(source_record=source)
        .values("pk", "sales_order_item_id", "sales_order_item__line_no", "sales_order_item__sales_order_id")
        .order_by("sales_order_item__line_no", "pk")
    )
    distinct_order_ids = sorted({row["sales_order_item__sales_order_id"] for row in design_rows})
    current_item_ids = set(order.items.values_list("pk", flat=True))
    design_item_ids = {row["sales_order_item_id"] for row in design_rows}
    if (
        len(design_rows) != len(engineering_rows)
        or distinct_order_ids != [order.pk]
        or not current_item_ids
        or design_item_ids != current_item_ids
    ):
        _raise(
            "CRM_SOURCE_ORDER_SCOPE_MISMATCH",
            "CRM来源的持久化设计范围没有唯一、完整地覆盖当前销售订单，禁止建立关系。",
            sourceRecordId=source.pk,
            salesOrderId=order.pk,
            engineeringRowCount=len(engineering_rows),
            productDesignItemCount=len(design_rows),
            linkedSalesOrderIds=distinct_order_ids,
            currentSalesOrderItemIds=sorted(current_item_ids),
            linkedSalesOrderItemIds=sorted(design_item_ids),
        )
    distribution = {}
    for row in design_rows:
        key = str(row["sales_order_item__line_no"])
        distribution[key] = distribution.get(key, 0) + 1
    return {
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "sourceOrderNo": expected["sourceOrderNo"],
        "engineeringRowCount": len(engineering_rows),
        "commercialLineCount": len(current_item_ids),
        "designDistribution": distribution,
        "identityComparisons": comparisons,
        "projectNormalization": {
            "source": normalize_business_text(expected["projectReference"]),
            "order": normalize_business_text(order.project_reference),
        },
    }


def resolve_current_crm_source(*, order, lock=False):
    """Return the sole valid independent current-source binding, if present."""

    bindings = list(_binding_query(order=order, lock=lock)[:3])
    if not bindings:
        return None
    if len(bindings) != 1:
        _raise(
            "CRM_ORDER_CURRENT_SOURCE_AMBIGUOUS",
            "当前销售订单存在多个正式CRM来源关系，已失败关闭。",
            salesOrderId=order.pk,
            identityIds=[row.pk for row in bindings],
        )
    identity = bindings[0]
    metadata = identity.audit_metadata if isinstance(identity.audit_metadata, dict) else {}
    source_id = metadata.get("sourceRecordId")
    try:
        source_id = int(source_id)
    except (TypeError, ValueError):
        _raise(
            "CRM_SOURCE_BINDING_INVALID",
            "当前CRM来源关系缺少有效来源记录身份，已失败关闭。",
            identityId=identity.pk,
        )
    source = EngineeringSourceRecord.objects.filter(
        pk=source_id, company_id=order.company_id,
    ).first()
    if not source:
        _raise(
            "CRM_SOURCE_BINDING_INVALID",
            "当前CRM来源关系指向的来源不存在或跨公司，已失败关闭。",
            identityId=identity.pk,
            sourceRecordId=source_id,
        )
    expected_metadata = {
        "sourceVersion": source.source_version,
        "sourceContentHash": source.content_hash,
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
    }
    metadata_mismatch = {
        key: {"expected": value, "actual": metadata.get(key)}
        for key, value in expected_metadata.items()
        if metadata.get(key) != value
    }
    if (
        identity.external_id != _external_id(source)
        or identity.source_fingerprint.lower() != source.content_hash.lower()
        or metadata_mismatch
    ):
        _raise(
            "CRM_SOURCE_BINDING_STALE",
            "当前CRM来源关系与来源版本、Hash或订单身份不一致，已失败关闭。",
            identityId=identity.pk,
            metadataMismatch=metadata_mismatch,
        )
    scope = _validate_source_and_order(source=source, order=order)
    return CRMCurrentSourceBinding(identity=identity, source=source, scope=scope)


def inspect_crm_source_establishment(*, order, source, actor=None):
    """Read-only preflight shared by tests, command preview and execution."""

    scope = _validate_source_and_order(source=source, order=order)
    existing = list(_binding_query(order=order)[:3])
    actor_facts = None
    authorization = None
    workflow_responsibility_id = None
    if actor is not None:
        try:
            authorization, actor_facts, workflow_mapping = _assert_actor_authorized(
                actor=actor, order=order,
            )
        except SalesOrderBusinessIdentityCorrectionError as error:
            raise SalesOrderCRMSourceEstablishmentError(
                error.code, error.message, details=error.details,
            ) from error
        workflow_responsibility_id = workflow_mapping.pk
    return {
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "sourceRecordId": source.pk,
        "sourceVersion": source.source_version,
        "sourceContentHash": source.content_hash,
        "sourceStatus": source.status,
        "currentSourceCount": len(existing),
        "currentSourceIdentityIds": [row.pk for row in existing],
        "scope": scope,
        "actor": actor_facts,
        "authorizationDecision": (
            authorization.get("decisionCode") if authorization else None
        ),
        "workflowResponsibilityId": workflow_responsibility_id,
        "businessWriteCount": 0,
    }


def _idempotent_result(*, order, source, identity, request, audit):
    binding = resolve_current_crm_source(order=order, lock=True)
    if not binding or binding.identity.pk != identity.pk or binding.source.pk != source.pk:
        _raise(
            "CRM_SOURCE_ESTABLISHMENT_REPLAY_MISMATCH",
            "既有幂等结果与当前CRM来源关系不一致，禁止重复执行。",
            identityId=identity.pk,
        )
    return {
        "actionCode": ACTION_CODE,
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "sourceRecordId": source.pk,
        "sourceVersion": source.source_version,
        "sourceIdentityId": identity.pk,
        "writeRequestId": request.pk,
        "organizationAuditId": audit.pk,
        "currentSourceCount": 1,
        "currentSource": binding.as_dict(),
        "idempotent": True,
        "businessWriteCount": 0,
        "reviewWriteCount": 0,
        "relation0032WriteCount": 0,
        "relation0033WriteCount": 0,
        "authorizationWriteCount": 0,
    }


@transaction.atomic
def establish_sales_order_current_crm_source(
    *, actor, order_id, expected_order_no, source_record_id,
    expected_source_version, expected_source_content_hash,
    expected_customer_name, expected_project_reference,
    expected_external_source_no, expected_engineering_row_count,
    idempotency_key, reason,
):
    """Establish exactly one current CRM Source without creating review chains."""

    key = str(idempotency_key or "").strip()
    reason = str(reason or "").strip()
    if not key:
        _raise("CRM_SOURCE_IDEMPOTENCY_REQUIRED", "建立当前CRM来源必须提供幂等键。")
    if not reason:
        _raise("CRM_SOURCE_REASON_REQUIRED", "建立当前CRM来源必须提供明确办理依据。")

    order = SalesOrder.objects.select_for_update().select_related(
        "company", "department", "customer",
    ).filter(pk=order_id).first()
    if not order or order.order_no != expected_order_no:
        _raise(
            "CRM_SOURCE_ORDER_MISMATCH",
            "销售订单不存在或编号已变化，禁止建立来源关系。",
            salesOrderId=order_id,
            expectedOrderNo=expected_order_no,
        )
    if order.business_purpose != SalesOrder.BusinessPurpose.FORMAL_SALE:
        _raise(
            "CRM_SOURCE_FORMAL_SALE_REQUIRED",
            "只有持久化为FORMAL_SALE的订单可以建立正式CRM来源。",
            salesOrderId=order.pk,
            businessPurpose=order.business_purpose,
        )
    if order.status == "cancelled":
        _raise(
            "CRM_SOURCE_CANCELLED_ORDER_FORBIDDEN",
            "已取消订单禁止建立当前CRM来源。",
            salesOrderId=order.pk,
        )
    if order.status != "draft":
        _raise(
            "CRM_SOURCE_DRAFT_ORDER_REQUIRED",
            "本动作只允许在销售订单草稿阶段建立当前CRM来源。",
            salesOrderId=order.pk,
            orderStatus=order.status,
        )
    try:
        authorization, actor_facts, workflow_mapping = _assert_actor_authorized(
            actor=actor, order=order,
        )
    except SalesOrderBusinessIdentityCorrectionError as error:
        raise SalesOrderCRMSourceEstablishmentError(
            error.code, error.message, details=error.details,
        ) from error

    source = EngineeringSourceRecord.objects.select_for_update().filter(
        pk=source_record_id,
    ).first()
    if not source:
        _raise(
            "CRM_SOURCE_NOT_FOUND",
            "未找到授权建立关系的CRM来源。",
            sourceRecordId=source_record_id,
        )
    actual = {
        "sourceVersion": source.source_version,
        "sourceContentHash": source.content_hash,
        "customerName": source_business_identity(source)["customerName"],
        "projectReference": source_business_identity(source)["projectReference"],
        "externalSourceNo": source_business_identity(source)["sourceOrderNo"],
        "engineeringRowCount": len(
            (source.source_payload or {}).get("engineeringRows") or []
        ) if isinstance(source.source_payload, dict) else 0,
    }
    expected = {
        "sourceVersion": expected_source_version,
        "sourceContentHash": expected_source_content_hash,
        "customerName": expected_customer_name,
        "projectReference": expected_project_reference,
        "externalSourceNo": expected_external_source_no,
        "engineeringRowCount": int(expected_engineering_row_count),
    }
    if actual != expected:
        _raise(
            "CRM_SOURCE_EXPECTED_FACTS_MISMATCH",
            "CRM来源当前事实与受控执行参数不一致，禁止写入。",
            expected=expected,
            actual=actual,
        )
    scope = _validate_source_and_order(source=source, order=order)

    request_payload = {
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "sourceRecordId": source.pk,
        "sourceVersion": source.source_version,
        "sourceContentHash": source.content_hash,
        "scope": scope,
    }
    request_hash = _canonical_hash(request_payload)
    existing_request = MasterDataWriteRequest.objects.select_for_update().filter(
        organization_id=order.company_id,
        action_code=ACTION_CODE,
        entity_type="SalesOrderCRMCurrentSource",
        idempotency_key=key,
    ).first()
    if existing_request:
        if existing_request.request_hash != request_hash:
            _raise(
                "CRM_SOURCE_IDEMPOTENCY_CONFLICT",
                "同一幂等键已用于不同的CRM来源建立请求。",
                writeRequestId=existing_request.pk,
            )
        identity = existing_request.source_identity
        audit_id = (existing_request.result or {}).get("organizationAuditId")
        audit = OrganizationOperatingAuditRecord.objects.filter(pk=audit_id).first()
        if (
            existing_request.status != MasterDataWriteRequest.Status.COMMITTED
            or not audit
        ):
            _raise(
                "CRM_SOURCE_IDEMPOTENCY_RESULT_INCOMPLETE",
                "既有幂等请求没有完整提交结果，禁止重复写入。",
                writeRequestId=existing_request.pk,
            )
        return _idempotent_result(
            order=order,
            source=source,
            identity=identity,
            request=existing_request,
            audit=audit,
        )

    existing_bindings = list(_binding_query(order=order, lock=True)[:3])
    if existing_bindings:
        _raise(
            "CRM_ORDER_CURRENT_SOURCE_ALREADY_ESTABLISHED",
            "销售订单已存在当前正式CRM来源，禁止重复建立。",
            identityIds=[row.pk for row in existing_bindings],
        )
    source_bindings = list(
        ExternalIdentity.objects.select_for_update().filter(
            organization_id=order.company_id,
            source_system=SOURCE_SYSTEM,
            source_type=SOURCE_TYPE,
            source_object_type=SOURCE_OBJECT_TYPE,
            external_id=_external_id(source),
            mapping_status=ExternalIdentity.MappingStatus.MATCH,
        ).order_by("pk")[:3]
    )
    if source_bindings:
        _raise(
            "CRM_SOURCE_ALREADY_BOUND_TO_ORDER",
            "该CRM来源已经绑定其他正式销售订单，禁止重复关联。",
            identityIds=[row.pk for row in source_bindings],
            targetSalesOrderIds=[row.target_entity_id for row in source_bindings],
        )

    source_before = {
        "id": source.pk,
        "sourceVersion": source.source_version,
        "contentHash": source.content_hash,
        "status": source.status,
        "sourcePayload": deepcopy(source.source_payload),
    }
    order_before = {
        "id": order.pk,
        "orderNo": order.order_no,
        "status": order.status,
        "businessPurpose": order.business_purpose,
        "version": order.version,
        "customerId": order.customer_id,
        "projectReference": order.project_reference,
        "externalSourceNo": order.external_source_no,
    }
    identity = ExternalIdentity(
        organization_id=order.company_id,
        source_system=SOURCE_SYSTEM,
        source_type=SOURCE_TYPE,
        source_object_type=SOURCE_OBJECT_TYPE,
        external_id=_external_id(source),
        target_entity_type=TARGET_ENTITY_TYPE,
        target_entity_id=str(order.pk),
        mapping_status=ExternalIdentity.MappingStatus.MATCH,
        source_fingerprint=source.content_hash,
        audit_metadata={
            "sourceRecordId": source.pk,
            "sourceVersion": source.source_version,
            "sourceContentHash": source.content_hash,
            "salesOrderId": order.pk,
            "salesOrderNo": order.order_no,
            "sourceOrderNo": scope["sourceOrderNo"],
            "engineeringRowCount": scope["engineeringRowCount"],
            "commercialLineCount": scope["commercialLineCount"],
            "designDistribution": scope["designDistribution"],
            "projectNormalization": scope["projectNormalization"],
            "idempotencyKey": key,
            "actor": actor_facts,
            "formalRelationVersion": "CRM-CURRENT-SOURCE-V1",
        },
    )
    identity.full_clean()
    identity.save()
    request = MasterDataWriteRequest.objects.create(
        organization_id=order.company_id,
        action_code=ACTION_CODE,
        entity_type="SalesOrderCRMCurrentSource",
        idempotency_key=key,
        request_hash=request_hash,
        source_identity=identity,
        status=MasterDataWriteRequest.Status.RESERVED,
        audit_metadata={
            "reason": reason,
            "actor": actor_facts,
            "authorizationDecision": authorization.get("decisionCode"),
            "workflowResponsibilityId": workflow_mapping.pk,
        },
    )
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=ACTION_CODE,
        actor=actor,
        organization_id=order.company_id,
        target_type="SalesOrder",
        target_id=order.pk,
        target_label=order.order_no,
        reason=reason,
        before_snapshot={
            "currentSourceCount": 0,
            "salesOrder": order_before,
            "source": source_before,
        },
        after_snapshot={
            "currentSourceCount": 1,
            "sourceIdentityId": identity.pk,
            "sourceRecordId": source.pk,
            "sourceVersion": source.source_version,
            "sourceContentHash": source.content_hash,
            "salesOrder": order_before,
            "sourceUnchanged": True,
            "salesOrderUnchanged": True,
            "reviewWriteCount": 0,
            "relation0032WriteCount": 0,
            "relation0033WriteCount": 0,
            "authorizationWriteCount": 0,
            "idempotencyKey": key,
            "actor": actor_facts,
            "scope": scope,
        },
    )
    request.status = MasterDataWriteRequest.Status.COMMITTED
    request.target_entity_id = str(order.pk)
    request.result = {
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "sourceRecordId": source.pk,
        "sourceIdentityId": identity.pk,
        "organizationAuditId": audit.pk,
    }
    request.save(update_fields=[
        "status", "target_entity_id", "result", "updated_at",
    ])
    binding = resolve_current_crm_source(order=order, lock=True)
    return {
        "actionCode": ACTION_CODE,
        "salesOrderId": order.pk,
        "salesOrderNo": order.order_no,
        "sourceRecordId": source.pk,
        "sourceVersion": source.source_version,
        "sourceIdentityId": identity.pk,
        "writeRequestId": request.pk,
        "organizationAuditId": audit.pk,
        "currentSourceCount": 1,
        "currentSource": binding.as_dict(),
        "idempotent": False,
        "businessWriteCount": 3,
        "reviewWriteCount": 0,
        "relation0032WriteCount": 0,
        "relation0033WriteCount": 0,
        "authorizationWriteCount": 0,
    }
