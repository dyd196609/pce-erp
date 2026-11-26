"""Controlled SalesOrderItem engineering identity and OEI intake.

This service closes only the approved transition from PDE preparation to one
OrderEngineeringInstance. It never creates design, version, baseline,
calculation, BOM or planning facts.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from sales.models import SalesOrderItem
from system.authorization import AuthorizationService

from .models import (
    ManufacturingProcessType,
    OrderEngineeringInstance,
    PDEEngineeringPreparationAuthorization,
    ProductCategory,
)
from .admission_chain_revocation import (
    active_order_engineering_instances,
    active_pde_authorizations,
)
from .pde_engineering_preparation_admission import (
    PDEEngineeringPreparationAdmissionError,
    require_pde_engineering_preparation_admission,
)
from .production_foundation_service import (
    ProductionFoundationError,
    ProductionFoundationService,
    _actor_chain,
    _audit,
    _snapshot,
)


ACTION_CODE = "production.engineering.order.maintain"


class OrderEngineeringIntakeError(ValueError):
    def __init__(self, code, message, *, details=None, http_status=409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.http_status = http_status


def _item_queryset(*, lock=False):
    queryset = SalesOrderItem.objects.select_related(
        "sales_order", "material", "product_definition", "product_version",
    )
    return queryset.select_for_update() if lock else queryset


def _authorization(authorization_id):
    return active_pde_authorizations(
        PDEEngineeringPreparationAuthorization.objects.select_related(
            "predecessor_relation__pde_review__source_record",
            "predecessor_relation__crm_order_relation",
        )
    ).get(pk=authorization_id)


def _identity_payload(item, instance=None):
    category = instance.product_category if instance and instance.product_category_id else None
    process_type = instance.selected_process_type if instance and instance.selected_process_type_id else None
    return {
        "salesOrderId": item.sales_order_id,
        "salesOrderNo": item.sales_order.order_no,
        "salesOrderItemId": item.pk,
        "lineNo": item.line_no,
        "materialId": item.material_id,
        "materialCode": item.material.code,
        "materialName": item.material.name,
        "customerProductName": item.customer_product_name,
        "engineeringModeCode": item.engineering_mode,
        "engineeringModeLabel": item.get_engineering_mode_display(),
        "productDefinitionId": item.product_definition_id,
        "productVersionId": item.product_version_id,
        "productCategoryId": category.pk if category else None,
        "productCategoryCode": category.code if category else "",
        "productCategoryName": category.name if category else "",
        "selectedProcessTypeId": process_type.pk if process_type else None,
        "selectedProcessTypeCode": process_type.code if process_type else "",
        "selectedProcessTypeName": process_type.name if process_type else "",
    }


def _instance_payload(instance):
    if not instance:
        return None
    return {
        "id": instance.pk,
        "instanceNo": instance.instance_no,
        "statusCode": instance.status,
        "statusLabel": instance.get_status_display(),
        "salesOrderItemId": instance.sales_order_item_id,
        "productId": instance.product_id,
        "baselineProductVersionId": instance.baseline_product_version_id,
        "productCategoryId": instance.product_category_id,
        "selectedProcessTypeId": instance.selected_process_type_id,
        "sourceRecordId": instance.source_record_id,
        "authorizationId": instance.engineering_preparation_authorization_id,
    }


class OrderEngineeringIntakeService:
    @classmethod
    def facts(cls, *, user, sales_order_item_id):
        item = _item_queryset().filter(
            pk=sales_order_item_id,
            sales_order__company_id=user.company_id,
        ).first()
        if not item:
            raise OrderEngineeringIntakeError(
                "SALES_ORDER_ITEM_NOT_FOUND",
                "订单行不存在或不属于当前公司。",
                http_status=404,
            )
        try:
            admission = require_pde_engineering_preparation_admission(
                company_id=user.company_id,
                sales_order_item_id=item.pk,
            )
        except PDEEngineeringPreparationAdmissionError as exc:
            raise OrderEngineeringIntakeError(
                exc.code, exc.message, details=exc.details, http_status=exc.http_status,
            ) from exc
        authorization = _authorization(admission.authorization_id)
        instance = active_order_engineering_instances(
            OrderEngineeringInstance.objects.select_related(
                "product_category", "selected_process_type", "source_record",
            )
        ).filter(sales_order_item=item).first()
        decision = AuthorizationService.decide(
            user=user,
            action_code=ACTION_CODE,
            organization_id=user.company_id,
            business_object={
                "organizationId": user.company_id,
                "salesOrderId": item.sales_order_id,
                "salesOrderItemId": item.pk,
            },
        )
        source = authorization.predecessor_relation.pde_review.source_record
        from .order_engineering_identity_carry import enabled as identity_carry_enabled
        return {
            "factSource": "server",
            "controlledIdentityCarryEnabled": identity_carry_enabled(),
            "confirmActionLabel": "确认按单工程身份并建立工程实例",
            "orderVersion": item.sales_order.version,
            "actionCode": ACTION_CODE,
            "permissionAllowed": bool(decision.get("allowed")),
            "authorizationDecision": decision,
            "admission": admission.as_dict(),
            "source": {
                "sourceRecordId": source.pk,
                "sourceVersion": source.source_version,
                "sourceContentHash": source.content_hash,
                "statusCode": source.status,
                "statusLabel": source.get_status_display(),
            },
            "identity": _identity_payload(item, instance),
            "productCategories": list(
                ProductCategory.objects.filter(
                    company_id=user.company_id, is_active=True,
                ).order_by("code").values("id", "code", "name")
            ),
            "processTypes": list(
                ManufacturingProcessType.objects.filter(
                    company_id=user.company_id, is_active=True,
                ).order_by("code").values("id", "code", "name")
            ),
            "oei": _instance_payload(instance),
            "canCreate": bool(decision.get("allowed")) and instance is None,
            "businessWriteCount": 0,
            "downstreamCreated": {
                "productDesignItem": False,
                "engineeringBaseline": False,
                "engineeringCalculation": False,
                "bom": False,
                "productionPlan": False,
            },
        }

    @classmethod
    @transaction.atomic
    def confirm_identity_and_create(
        cls,
        *,
        user,
        sales_order_item_id,
        customer_product_name,
        product_category_id,
        selected_process_type_id,
        source_record_id,
        authorization_id,
        idempotency_key,
        reason="",
        expected_order_version=None,
        expected_source_content_hash=None,
    ):
        item = _item_queryset(lock=True).filter(
            pk=sales_order_item_id,
            sales_order__company_id=user.company_id,
        ).first()
        if not item:
            raise OrderEngineeringIntakeError(
                "SALES_ORDER_ITEM_NOT_FOUND",
                "订单行不存在或不属于当前公司。",
                http_status=404,
            )
        if expected_order_version is not None and str(expected_order_version) != str(item.sales_order.version):
            raise OrderEngineeringIntakeError("ORDER_VERSION_CHANGED", "订单版本已变化，请保留输入并重新核对。")
        customer_product_name = str(customer_product_name or "").strip()
        if not customer_product_name:
            raise OrderEngineeringIntakeError(
                "CUSTOMER_PRODUCT_NAME_REQUIRED",
                "订单工程产品必须确认客户产品名称。",
                http_status=400,
            )
        if item.product_definition_id or item.product_version_id:
            raise OrderEngineeringIntakeError(
                "STANDARD_PRODUCT_REFERENCE_CONFLICT",
                "订单工程路径不得保留或自动匹配ProductDefinition/ProductVersion。",
                details={
                    "productDefinitionId": item.product_definition_id,
                    "productVersionId": item.product_version_id,
                },
            )
        try:
            admission = require_pde_engineering_preparation_admission(
                company_id=user.company_id,
                sales_order_item_id=item.pk,
                authorization_id=authorization_id,
                lock=True,
            )
        except PDEEngineeringPreparationAdmissionError as exc:
            raise OrderEngineeringIntakeError(
                exc.code, exc.message, details=exc.details, http_status=exc.http_status,
            ) from exc
        authorization = _authorization(admission.authorization_id)
        source = authorization.predecessor_relation.pde_review.source_record
        if expected_source_content_hash is not None and expected_source_content_hash != source.content_hash:
            raise OrderEngineeringIntakeError("SOURCE_CONTENT_CHANGED", "来源内容已变化，请保留输入并重新核对。")
        try:
            supplied_source_id = int(source_record_id)
        except (TypeError, ValueError) as exc:
            raise OrderEngineeringIntakeError(
                "SOURCE_RECORD_ID_INVALID", "工程来源记录标识无效。", http_status=400,
            ) from exc
        if supplied_source_id != source.pk:
            raise OrderEngineeringIntakeError(
                "SOURCE_RECORD_AUTHORIZATION_MISMATCH",
                "工程身份来源必须与Authorization继承的PDE评审来源一致。",
                details={
                    "expectedSourceRecordId": source.pk,
                    "actualSourceRecordId": supplied_source_id,
                },
            )
        category = ProductCategory.objects.filter(
            pk=product_category_id, company_id=user.company_id, is_active=True,
        ).first()
        if not category:
            raise OrderEngineeringIntakeError(
                "PRODUCT_CATEGORY_NOT_AVAILABLE",
                "产品分类不存在、未启用或不属于当前公司。",
                http_status=400,
            )
        process_type = ManufacturingProcessType.objects.filter(
            pk=selected_process_type_id, company_id=user.company_id, is_active=True,
        ).first()
        if not process_type:
            raise OrderEngineeringIntakeError(
                "PROCESS_TYPE_NOT_AVAILABLE",
                "正式工艺类型不存在、未启用或不属于当前公司。",
                http_status=400,
            )
        decision = AuthorizationService.decide(
            user=user,
            action_code=ACTION_CODE,
            organization_id=user.company_id,
            business_object={
                "organizationId": user.company_id,
                "salesOrderId": item.sales_order_id,
                "salesOrderItemId": item.pk,
            },
        )
        if not decision.get("allowed"):
            raise OrderEngineeringIntakeError(
                decision.get("decisionCode", "PERMISSION_DENIED"),
                decision.get("reason", "当前账户无权维护订单工程实例。"),
                details={"authorization": decision},
                http_status=403,
            )
        existing = active_order_engineering_instances(
            OrderEngineeringInstance.objects.select_for_update()
        ).filter(sales_order_item=item).first()
        expected_existing = {
            "product_category_id": category.pk,
            "selected_process_type_id": process_type.pk,
            "source_record_id": source.pk,
            "engineering_preparation_authorization_id": admission.authorization_id,
        }
        if existing:
            mismatches = {
                field: {"expected": value, "actual": getattr(existing, field)}
                for field, value in expected_existing.items()
                if getattr(existing, field) != value
            }
            if (
                item.engineering_mode != "ORDER_ENGINEERED"
                or item.customer_product_name != customer_product_name
            ):
                mismatches["salesOrderItemIdentity"] = {
                    "expected": {
                        "engineeringMode": "ORDER_ENGINEERED",
                        "customerProductName": customer_product_name,
                    },
                    "actual": {
                        "engineeringMode": item.engineering_mode,
                        "customerProductName": item.customer_product_name,
                    },
                }
            if mismatches:
                raise OrderEngineeringIntakeError(
                    "ORDER_ENGINEERING_IDENTITY_CONFLICT",
                    "订单行已经存在不同的正式工程身份或OEI，禁止覆盖。",
                    details={"mismatches": mismatches, "oeiId": existing.pk},
                )
            from .order_engineering_identity_carry import enabled as identity_carry_enabled, validated_identity_proof
            existing_proof = None
            if identity_carry_enabled():
                relation = authorization.predecessor_relation.crm_order_relation
                from .crm_order_version_carry_forward import matching_proof, CarryForwardError
                try:
                    existing_proof = matching_proof(relation)
                except CarryForwardError as exc:
                    raise OrderEngineeringIntakeError("ENGINEERING_IDENTITY_CARRY_INVALID", str(exc)) from exc
                if existing_proof is None:
                    raise OrderEngineeringIntakeError("ENGINEERING_IDENTITY_CARRY_INVALID", "既有工程实例缺少匹配的受控承接证明，禁止重放成功。")
            return {
                "engineeringIdentityCarryProofId": existing_proof.pk if existing_proof else None,
                "identity": _identity_payload(item, existing),
                "oei": _instance_payload(existing),
                "admission": admission.as_dict(),
                "idempotent": True,
                "businessWriteCount": 0,
                "itemAuditId": None,
                "oeiAuditId": None,
            }
        from .order_engineering_identity_carry import enabled as carry_enabled, capture_basis, append_proof
        carry_basis = None
        if carry_enabled():
            try:
                carry_basis = capture_basis(item, admission)
            except ValueError as exc:
                raise OrderEngineeringIntakeError("ENGINEERING_IDENTITY_CARRY_REQUIRED", str(exc)) from exc
        execution_chain = _actor_chain(user)
        before_item = _snapshot(item)
        item.engineering_mode = "ORDER_ENGINEERED"
        item.customer_product_name = customer_product_name
        try:
            item.full_clean()
        except ValidationError as exc:
            raise OrderEngineeringIntakeError(
                "SALES_ORDER_ITEM_ENGINEERING_IDENTITY_INVALID",
                "订单行工程身份校验失败。",
                details=exc.message_dict,
                http_status=400,
            ) from exc
        item.save(update_fields=("engineering_mode", "customer_product_name"))
        item_audit = _audit(
            user=user,
            organization_id=user.company_id,
            action_code=ACTION_CODE,
            instance=item,
            before=before_item,
            after=_snapshot(item),
            reason=reason or "确认订单行按单工程身份",
            authorization=decision,
            execution_chain=execution_chain,
        )
        payload = {
            "company_id": user.company_id,
            "sales_order_item_id": item.pk,
            "product_id": None,
            "baseline_product_version_id": None,
            "product_category_id": category.pk,
            "selected_process_type_id": process_type.pk,
            "source_record_id": source.pk,
            "engineering_preparation_authorization_id": admission.authorization_id,
            "reason": reason or "基于PDE工程准备授权建立唯一订单工程实例",
        }
        try:
            created = ProductionFoundationService.write(
                "order-engineering-instances",
                user=user,
                payload=payload,
                idempotency_key=idempotency_key,
                source_identity={
                    "sourceSystem": "PDE_ORDER_ENGINEERING_INTAKE",
                    "sourceType": "BUSINESS_ACTION_SCOPE",
                    "sourceObjectType": "SalesOrderItem",
                    "externalId": f"order-engineering-instance:{item.pk}",
                    "sourceFingerprint": source.content_hash,
                    "auditMetadata": {
                        "salesOrderId": item.sales_order_id,
                        "salesOrderItemId": item.pk,
                        "crmOrderRelationId": admission.crm_order_relation_id,
                        "pdeReviewId": admission.pde_review_id,
                        "predecessorRelationId": admission.predecessor_relation_id,
                        "authorizationId": admission.authorization_id,
                        "sourceRecordId": source.pk,
                        "sourceVersion": source.source_version,
                        "sourceContentHash": source.content_hash,
                        "engineeringMode": "ORDER_ENGINEERED",
                        "productCategoryId": category.pk,
                        "selectedProcessTypeId": process_type.pk,
                    },
                },
            )
        except ProductionFoundationError as exc:
            raise OrderEngineeringIntakeError(
                exc.code,
                exc.message,
                details=exc.details,
                http_status=(
                    403
                    if exc.code in {"PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID"}
                    else 400
                ),
            ) from exc
        instance = OrderEngineeringInstance.objects.select_related(
            "product_category", "selected_process_type", "source_record",
        ).get(pk=created["row"]["id"])
        carry_proof = None
        if carry_basis:
            try:
                carry_proof = append_proof(item=item, instance=instance, item_audit=item_audit,
                    admission=admission, user=user, basis=carry_basis)
            except ValueError as exc:
                raise OrderEngineeringIntakeError("ENGINEERING_IDENTITY_CARRY_INVALID", str(exc)) from exc
        return {
            "engineeringIdentityCarryProofId": carry_proof.pk if carry_proof else None,
            "identity": _identity_payload(item, instance),
            "oei": _instance_payload(instance),
            "admission": admission.as_dict(),
            "source": {
                "sourceRecordId": source.pk,
                "sourceVersion": source.source_version,
                "sourceContentHash": source.content_hash,
            },
            "idempotent": False,
            "businessWriteCount": 2,
            "itemAuditId": item_audit.pk,
            "oeiAuditId": created.get("auditId"),
            "downstreamCreated": {
                "productDesignItem": False,
                "engineeringBaseline": False,
                "engineeringCalculation": False,
                "bom": False,
                "productionPlan": False,
            },
        }

