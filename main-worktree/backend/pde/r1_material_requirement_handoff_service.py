"""Audited R1 handoff from saved engineering facts to material requirements.

The service deliberately does not execute engineering rules.  It confirms an
explicitly authorized mapping against one immutable saved DerivedFact, releases
that mapping through the existing rule lifecycle, and only then persists the
matching EngineeringMaterialRequirement.  It never creates a BOM.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from masterdata.models import Material
from sales.models import SalesOrder
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord

from .engineering_rule_foundation import canonical_json, specification_hash, validate_specification
from .models import (
    EngineeringDerivedFact,
    EngineeringMaterialRequirement,
    EngineeringRuleDefinition,
)
from .production_foundation_service import (
    EngineeringLifecycleService,
    ProductionFoundationError,
    ProductionFoundationService,
)


SERVICE_CODE = "PCE-R1-SAVED-FACT-MATERIAL-REQUIREMENT-HANDOFF-V1"
MAPPING_CONTRACT_CODE = "PCE-MATERIAL-REQUIREMENT-MAPPING-V1"
AUTHORIZATION_REFERENCE = (
    "USER_INSTRUCTION:SO202609180003:MRC-003+MRC-004:2026-10-04"
)
REQUIREMENT_AUDIT_ACTION = "production.engineering.material_requirement.r1.create"


class R1MaterialRequirementHandoffError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class AuthorizedMaterialMapping:
    mapping_no: str
    order_no: str
    design_item_no: str
    source_fact_code: str
    expected_saved_value: str
    material_id: int
    material_code: str
    output_uom: str
    quantity_basis: str = "PER_SALES_ITEM_UNIT"
    sales_item_multiplier: str = "APPLY_ONCE"
    item_role: str = "MAIN_MATERIAL"
    requirement_type: str = "MANUFACTURING"
    supply_type: str = "PRODUCTION"
    mapping_version: str = "V1"

    @property
    def rule_code(self) -> str:
        return f"MRM.{self.order_no}.{self.mapping_no}"

    @property
    def idempotency_key(self) -> str:
        return f"{self.order_no}-{self.mapping_no}-{self.mapping_version}"


AUTHORIZED_SO202609180003_REPRESENTATIVES = (
    AuthorizedMaterialMapping(
        mapping_no="MRC-003",
        order_no="SO202609180003",
        design_item_no="SO202609180003-DES-03-SRC-0014",
        source_fact_code="S",
        expected_saved_value="0.031200",
        material_id=117,
        material_code="MAT202608000035",
        output_uom="m2",
    ),
    AuthorizedMaterialMapping(
        mapping_no="MRC-004",
        order_no="SO202609180003",
        design_item_no="SO202609180003-DES-04-SRC-0073",
        source_fact_code="S",
        expected_saved_value="1.860000",
        material_id=140,
        material_code="MAT202608000058",
        output_uom="m2",
    ),
)


def _fail(code: str, message: str, **details):
    raise R1MaterialRequirementHandoffError(code, message, details)


def _fact_decimal(fact: EngineeringDerivedFact) -> Decimal:
    value = fact.value.get("decimal") if isinstance(fact.value, dict) else fact.value
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        _fail("SAVED_FACT_DECIMAL_REQUIRED", "已保存DerivedFact不是合法十进制数量。", factId=fact.pk)
    if result <= 0:
        _fail("SAVED_FACT_MUST_BE_POSITIVE", "已保存DerivedFact数量必须大于0。", factId=fact.pk)
    return result


def _authorize(user, action_code: str, organization_id: int, business_object: dict) -> dict:
    decision = AuthorizationService.decide(
        user=user,
        action_code=action_code,
        organization_id=organization_id,
        business_object={"organizationId": organization_id, **business_object},
    )
    if not decision.get("allowed"):
        _fail(
            decision.get("decisionCode", "PERMISSION_DENIED"),
            decision.get("reason", "当前账户无权执行该动作。"),
            authorization=decision,
        )
    return decision


def _resolve_authorized_fact(approval: AuthorizedMaterialMapping, *, lock: bool = False):
    order = SalesOrder.objects.filter(order_no=approval.order_no).select_related("company").first()
    if not order:
        _fail("ORDER_NOT_FOUND", "授权订单不存在。", orderNo=approval.order_no)
    if order.acceptance_marker != "DEVELOPMENT_ONLY":
        _fail("DEVELOPMENT_VALIDATION_ORDER_REQUIRED", "本接续仅允许开发验证订单。")
    delivery = order.delivery_information if isinstance(order.delivery_information, dict) else {}
    if delivery.get("developmentOnly") is not True:
        _fail("DEVELOPMENT_VALIDATION_EVIDENCE_REQUIRED", "订单缺少开发验证用途持久证据。")
    query = EngineeringDerivedFact.objects
    if lock:
        query = query.select_for_update()
    fact = query.select_related(
        "source_detail__calculation__sales_order_item__sales_order",
        "source_detail__calculation__engineering_instance",
        "rule",
        "uom",
    ).filter(
        calculation__sales_order_item__sales_order=order,
        fact_code=f"{approval.design_item_no}:{approval.source_fact_code}",
        canonical_field=approval.source_fact_code,
        status="active",
    ).first()
    if not fact or not fact.source_detail_id:
        _fail("AUTHORIZED_SAVED_FACT_NOT_FOUND", "未找到授权对象的唯一已保存DerivedFact。")
    if fact.calculation.status != "completed" or fact.calculation.scope != "order_engineering":
        _fail("COMPLETED_CALCULATION_REQUIRED", "来源Calculation不是已完成整单工程核算。")
    if fact.trace.get("designItemNo") != approval.design_item_no:
        _fail("DESIGN_ITEM_IDENTITY_MISMATCH", "DerivedFact稳定设计对象身份不一致。")
    if fact.source_detail.calculation_id != fact.calculation_id:
        _fail("SOURCE_DETAIL_CHAIN_MISMATCH", "DerivedFact与CalculationDetail归属不一致。")
    if fact.source_detail.output_value != fact.value:
        _fail("SAVED_FACT_DETAIL_VALUE_MISMATCH", "DerivedFact与CalculationDetail保存值不一致。")
    if not fact.uom_id or fact.uom.code != approval.output_uom:
        _fail("SAVED_FACT_UOM_MISMATCH", "DerivedFact单位与授权输出单位不一致。")
    saved_value = _fact_decimal(fact).quantize(Decimal("0.000001"))
    expected_value = Decimal(approval.expected_saved_value).quantize(Decimal("0.000001"))
    if saved_value != expected_value:
        _fail(
            "AUTHORIZED_SAVED_VALUE_MISMATCH",
            "DerivedFact当前值与用户授权值不一致，已停止。",
            expected=str(expected_value),
            actual=str(saved_value),
        )
    material_query = Material.objects.select_related("base_uom")
    if lock:
        material_query = material_query.select_for_update()
    material = material_query.filter(
        pk=approval.material_id,
        company_id=order.company_id,
        code=approval.material_code,
        is_active=True,
        unit_status="confirmed",
    ).first()
    if not material or not material.base_uom_id or material.base_uom.code != approval.output_uom:
        _fail("AUTHORIZED_MATERIAL_MISMATCH", "正式Material身份或基础UOM与用户授权不一致。")
    order_quantity = Decimal(str(fact.calculation.sales_order_item.quantity)).quantize(Decimal("0.000001"))
    if approval.quantity_basis != "PER_SALES_ITEM_UNIT" or approval.sales_item_multiplier != "APPLY_ONCE":
        _fail("R1_QUANTITY_CONTRACT_DENIED", "本服务只接受本次授权的每销售项目单位、只乘一次合同。")
    return order, fact, material, saved_value, order_quantity


def _mapping_specification(
    approval: AuthorizedMaterialMapping,
    *,
    fact: EngineeringDerivedFact,
    material: Material,
) -> dict:
    source_rule_code = fact.trace.get("ruleCode") or fact.source_detail.rule_code
    source_rule_version = fact.trace.get("ruleVersion") or fact.source_detail.rule_version
    spec = {
        "contractCode": MAPPING_CONTRACT_CODE,
        "rulePackage": {"code": "PCE-MATERIAL-REQUIREMENT-MAPPING", "version": "V1"},
        "inputs": [{
            "canonicalName": "source_fact_value",
            "valueType": "decimal",
            "unit": approval.output_uom,
            "unitDimension": "area",
            "sourceType": "ENGINEERING_DERIVED",
            "required": True,
            "unitRequired": True,
        }],
        "outputs": [{
            "canonicalName": f"{approval.mapping_no.lower().replace('-', '_')}_material_quantity",
            "valueType": "decimal",
            "unit": approval.output_uom,
            "unitDimension": "area",
            "resultDomain": "MATERIAL_REQUIREMENT",
            "sourceFactCode": approval.source_fact_code,
            "materialId": material.pk,
            "materialCode": material.code,
            "outputUom": approval.output_uom,
            "quantityBasis": approval.quantity_basis,
            "quantityExpression": "SOURCE_FACT_VALUE",
            "quantitySource": {
                "type": "SAVED_DERIVED_FACT",
                "sourceFactCode": approval.source_fact_code,
                "sourceFactId": fact.pk,
                "sourceDetailId": fact.source_detail_id,
                "sourcePath": fact.source_path,
            },
            "salesItemMultiplier": approval.sales_item_multiplier,
            "scrapRate": None,
            "itemRole": approval.item_role,
            "requirementType": approval.requirement_type,
            "supplyType": approval.supply_type,
            "orderSpecification": {
                "materialCode": material.code,
                "materialSpecification": material.specification,
                "designItemNo": approval.design_item_no,
                "businessPurpose": "DEVELOPMENT_VALIDATION",
            },
            "sourceRuleVersion": f"{source_rule_code}@{source_rule_version}",
            "mappingVersion": approval.mapping_version,
        }],
        "expression": "source_fact_value",
        "dependencies": [],
        "decimalPrecision": 18,
        "outputScale": 6,
        "roundingMode": "ROUND_HALF_UP",
        "priority": 100,
        "sourceEvidence": {
            "reference": AUTHORIZATION_REFERENCE,
            "sourceFactId": fact.pk,
            "sourceDetailId": fact.source_detail_id,
            "calculationId": fact.calculation_id,
            "calculationResultHash": fact.calculation.result_hash,
        },
        "applicability": {
            "orderNo": approval.order_no,
            "designItemNo": approval.design_item_no,
        },
        "auditIdentity": {
            "authorizationReference": AUTHORIZATION_REFERENCE,
            "idempotencyKey": approval.idempotency_key,
            "mappingNo": approval.mapping_no,
            "approvedScope": "DEVELOPMENT_VALIDATION_REPRESENTATIVE",
        },
    }
    validate_specification(spec)
    return spec


def _assert_existing_mapping(rule, approval, expected_spec):
    expected = {
        "companyId": rule.company_id,
        "ruleCode": approval.rule_code,
        "version": approval.mapping_version,
        "kind": "mapping",
        "specification": expected_spec,
    }
    actual = {
        "companyId": rule.company_id,
        "ruleCode": rule.rule_code,
        "version": rule.version,
        "kind": rule.rule_kind,
        "specification": rule.specification,
    }
    if canonical_json(actual) != canonical_json(expected):
        _fail(
            "EXISTING_MAPPING_CONFLICT",
            "同一Mapping编码/版本已存在不同正式内容，禁止覆盖。",
            ruleId=rule.pk,
        )


@transaction.atomic
def confirm_authorized_mappings(*, user, approvals) -> dict:
    """Create/release only explicitly supplied mappings; exact replays write zero rows."""
    approvals = tuple(approvals)
    if not approvals:
        _fail("AUTHORIZED_MAPPING_REQUIRED", "至少需要一条明确授权Mapping。")
    if len({row.idempotency_key for row in approvals}) != len(approvals):
        _fail("DUPLICATE_MAPPING_AUTHORIZATION", "授权Mapping身份重复。")
    results, audit_ids, created_count, transition_count = [], [], 0, 0
    for approval in approvals:
        order, fact, material, _saved_value, _order_quantity = _resolve_authorized_fact(approval, lock=True)
        if user.company_id != order.company_id:
            _fail("CROSS_COMPANY_WRITE_FORBIDDEN", "只能处理当前账户所属公司的正式事实。")
        spec = _mapping_specification(approval, fact=fact, material=material)
        rule = EngineeringRuleDefinition.objects.select_for_update().filter(
            company_id=order.company_id,
            rule_code=approval.rule_code,
            version=approval.mapping_version,
        ).first()
        if rule:
            _assert_existing_mapping(rule, approval, spec)
        else:
            try:
                saved = ProductionFoundationService.save(
                    "engineering-rule-definitions",
                    user=user,
                    payload={
                        "company_id": order.company_id,
                        "rule_code": approval.rule_code,
                        "rule_name": f"{approval.mapping_no} 已保存S事实至主材需求映射",
                        "version": approval.mapping_version,
                        "rule_kind": "mapping",
                        "specification": spec,
                        "status": "draft",
                        "effective_from": datetime.now().date(),
                        "effective_to": None,
                        "reason": f"{AUTHORIZATION_REFERENCE}；仅确认{approval.mapping_no}",
                    },
                    audit_context={
                        "authorizationReference": AUTHORIZATION_REFERENCE,
                        "mappingNo": approval.mapping_no,
                        "calculationReexecuted": False,
                    },
                )
            except ProductionFoundationError as exc:
                raise R1MaterialRequirementHandoffError(exc.code, exc.message, exc.details) from exc
            rule = EngineeringRuleDefinition.objects.select_for_update().get(pk=saved["row"]["id"])
            audit_ids.append(saved["auditId"])
            created_count += 1
        for target_status in ("reviewed", "released"):
            if rule.status == target_status or rule.status == "released":
                break
            try:
                transitioned = EngineeringLifecycleService.transition(
                    "engineering-rule-definitions",
                    object_id=rule.pk,
                    target_status=target_status,
                    user=user,
                    reason=f"{AUTHORIZATION_REFERENCE}；{approval.mapping_no}正式确认",
                )
            except ProductionFoundationError as exc:
                raise R1MaterialRequirementHandoffError(exc.code, exc.message, exc.details) from exc
            if transitioned.get("auditId"):
                audit_ids.append(transitioned["auditId"])
                transition_count += 1
            rule.refresh_from_db()
        if rule.status != "released":
            _fail("MAPPING_RELEASE_REQUIRED", "Mapping未到达released，禁止继续Requirement。", ruleId=rule.pk)
        results.append({
            "mappingNo": approval.mapping_no,
            "ruleId": rule.pk,
            "ruleCode": rule.rule_code,
            "version": rule.version,
            "status": rule.status,
            "specificationHash": specification_hash(rule.specification),
            "sourceFactId": fact.pk,
            "sourceDetailId": fact.source_detail_id,
            "materialId": material.pk,
        })
    return {
        "serviceCode": SERVICE_CODE,
        "mappingRecordCreateCount": created_count,
        "mappingStateTransitionWriteCount": transition_count,
        "auditWriteCount": len(audit_ids),
        "businessWriteCount": created_count + transition_count + len(audit_ids),
        "auditIds": audit_ids,
        "mappings": results,
        "calculationReexecuted": False,
    }


def readback_authorized_mappings(*, user, approvals) -> dict:
    rows = []
    for approval in tuple(approvals):
        order, fact, material, saved_value, order_quantity = _resolve_authorized_fact(approval)
        if user.company_id != order.company_id:
            _fail("CROSS_COMPANY_READ_FORBIDDEN", "只能读取当前账户所属公司的正式事实。")
        expected_spec = _mapping_specification(approval, fact=fact, material=material)
        rule = EngineeringRuleDefinition.objects.filter(
            company_id=order.company_id,
            rule_code=approval.rule_code,
            version=approval.mapping_version,
        ).first()
        if not rule:
            _fail("MAPPING_READBACK_MISSING", "Mapping保存后Readback不存在。")
        _assert_existing_mapping(rule, approval, expected_spec)
        if rule.status != "released":
            _fail("MAPPING_READBACK_NOT_RELEASED", "Mapping保存后Readback未发布。")
        rows.append({
            "mappingNo": approval.mapping_no,
            "ruleId": rule.pk,
            "ruleCode": rule.rule_code,
            "mappingVersion": rule.version,
            "status": rule.status,
            "specificationHash": specification_hash(rule.specification),
            "auditIdentity": {
                "ruleId": rule.pk,
                "ruleCode": rule.rule_code,
                "ruleVersion": rule.version,
                "specificationHash": specification_hash(rule.specification),
                **rule.specification["auditIdentity"],
            },
            "sourceFactId": fact.pk,
            "sourceDetailId": fact.source_detail_id,
            "savedValue": str(saved_value),
            "salesOrderItemQuantity": str(order_quantity),
            "materialId": material.pk,
            "materialCode": material.code,
            "outputUom": material.base_uom.code,
        })
    return {"mappingCount": len(rows), "mappings": rows, "readbackMatch": True}


def _assert_existing_requirement(requirement, *, approval, fact, material, net_quantity, mapping):
    exact = (
        requirement.calculation_id == fact.calculation_id
        and requirement.source_detail_id == fact.source_detail_id
        and requirement.material_id == material.pk
        and requirement.quantity_basis == approval.quantity_basis
        and requirement.calculated_quantity == _fact_decimal(fact).quantize(Decimal("0.000001"))
        and requirement.order_quantity == Decimal(str(fact.calculation.sales_order_item.quantity)).quantize(Decimal("0.000001"))
        and requirement.net_quantity == net_quantity
        and requirement.gross_quantity is None
        and requirement.uom_id == material.base_uom_id
        and requirement.item_role == approval.item_role
        and requirement.requirement_type == approval.requirement_type
        and requirement.supply_type == approval.supply_type
        and requirement.scrap_rate_status == "not_maintained"
        and requirement.scrap_rate is None
        and (requirement.trace or {}).get("mappingSpecificationHash") == specification_hash(mapping.specification)
        and (requirement.trace or {}).get("authorizationReference") == AUTHORIZATION_REFERENCE
        and (requirement.trace or {}).get("calculationReexecuted") is False
    )
    if not exact:
        _fail(
            "EXISTING_REQUIREMENT_CONFLICT",
            "来源Detail已存在与本次授权不一致的正式Material Requirement，禁止覆盖。",
            requirementId=requirement.pk,
        )


@transaction.atomic
def create_authorized_requirements(*, user, approvals) -> dict:
    """Persist exactly the approved requirements after released Mapping readback."""
    approvals = tuple(approvals)
    mapping_readback = readback_authorized_mappings(user=user, approvals=approvals)
    if not mapping_readback["readbackMatch"] or mapping_readback["mappingCount"] != len(approvals):
        _fail("MAPPING_READBACK_REQUIRED", "两条Mapping未完整Readback，禁止创建Requirement。")
    created, audit_ids, rows = 0, [], []
    for approval in approvals:
        order, fact, material, saved_value, order_quantity = _resolve_authorized_fact(approval, lock=True)
        mapping = EngineeringRuleDefinition.objects.select_for_update().get(
            company_id=order.company_id,
            rule_code=approval.rule_code,
            version=approval.mapping_version,
            status="released",
        )
        execute_authorization = _authorize(
            user,
            "production.engineering.calculation.execute",
            order.company_id,
            {"calculationId": fact.calculation_id, "mode": "R1_NO_RECALC_HANDOFF"},
        )
        bom_authorization = _authorize(
            user,
            "production.master_data.bom.maintain",
            order.company_id,
            {"calculationId": fact.calculation_id, "mode": "MATERIAL_REQUIREMENT_ONLY"},
        )
        net_quantity = (saved_value * order_quantity).quantize(Decimal("0.000001"))
        if net_quantity != Decimal(approval.expected_saved_value).quantize(Decimal("0.000001")):
            _fail(
                "AUTHORIZED_NET_QUANTITY_MISMATCH",
                "只乘一次SalesOrderItem数量后的净需求与授权数量不一致。",
                mappingNo=approval.mapping_no,
                netQuantity=str(net_quantity),
            )
        requirement = EngineeringMaterialRequirement.objects.select_for_update().filter(
            source_detail_id=fact.source_detail_id,
        ).first()
        if requirement:
            _assert_existing_requirement(
                requirement,
                approval=approval,
                fact=fact,
                material=material,
                net_quantity=net_quantity,
                mapping=mapping,
            )
        else:
            requirement = EngineeringMaterialRequirement(
                calculation=fact.calculation,
                source_detail=fact.source_detail,
                sequence=fact.source_detail.sequence,
                material=material,
                quantity_basis=approval.quantity_basis,
                calculated_quantity=saved_value,
                order_quantity=order_quantity,
                net_quantity=net_quantity,
                gross_quantity=None,
                uom=material.base_uom,
                item_role=approval.item_role,
                requirement_type=approval.requirement_type,
                supply_type=approval.supply_type,
                order_specification={
                    "approvedMappingNo": approval.mapping_no,
                    "materialCode": material.code,
                    "materialSpecification": material.specification,
                    "designItemNo": approval.design_item_no,
                    "businessPurpose": "DEVELOPMENT_VALIDATION",
                },
                scrap_rate_status="not_maintained",
                scrap_rate=None,
                source_path=fact.source_path,
                trace={
                    "serviceCode": SERVICE_CODE,
                    "contractCode": MAPPING_CONTRACT_CODE,
                    "authorizationReference": AUTHORIZATION_REFERENCE,
                    "mappingNo": approval.mapping_no,
                    "mappingRuleId": mapping.pk,
                    "mappingRuleCode": mapping.rule_code,
                    "mappingVersion": mapping.version,
                    "mappingSpecificationHash": specification_hash(mapping.specification),
                    "sourceFactId": fact.pk,
                    "sourceDetailId": fact.source_detail_id,
                    "designItemNo": approval.design_item_no,
                    "quantitySource": "SAVED_DERIVED_FACT",
                    "salesItemMultiplier": "APPLY_ONCE",
                    "productDesignItemMultiplierApplied": False,
                    "scrapRateStatus": "not_maintained",
                    "grossQuantityStatus": "not_calculated_without_scrap_basis",
                    "calculationReexecuted": False,
                    "operatorId": user.pk,
                    "operator": user.username,
                },
            )
            try:
                requirement.full_clean()
                requirement.save()
            except ValidationError as exc:
                _fail("REQUIREMENT_VALIDATION_FAILED", "正式Material Requirement校验失败。", errors=exc.message_dict)
            created += 1
            audit = OrganizationOperatingAuditRecord.objects.create(
                action_code=REQUIREMENT_AUDIT_ACTION,
                actor=user,
                organization_id=order.company_id,
                target_type="EngineeringMaterialRequirement",
                target_id=requirement.pk,
                target_label=f"{approval.mapping_no} / {material.code}"[:200],
                reason=f"{AUTHORIZATION_REFERENCE}；R1不重算正式接续"[:300],
                before_snapshot={},
                after_snapshot={
                    "requirementId": requirement.pk,
                    "mappingNo": approval.mapping_no,
                    "mappingRuleId": mapping.pk,
                    "sourceFactId": fact.pk,
                    "sourceDetailId": fact.source_detail_id,
                    "materialId": material.pk,
                    "netQuantity": str(net_quantity),
                    "grossQuantity": None,
                    "scrapRate": None,
                    "scrapRateStatus": "not_maintained",
                    "uom": material.base_uom.code,
                    "calculationReexecuted": False,
                    "authorization": {
                        "calculationExecute": execute_authorization,
                        "bomMaintain": bom_authorization,
                    },
                    "factSource": "server",
                },
            )
            audit_ids.append(audit.pk)
        rows.append({
            "mappingNo": approval.mapping_no,
            "requirementId": requirement.pk,
            "calculationId": requirement.calculation_id,
            "sourceFactId": fact.pk,
            "sourceDetailId": requirement.source_detail_id,
            "materialId": requirement.material_id,
            "materialCode": material.code,
            "calculatedQuantity": str(requirement.calculated_quantity),
            "orderQuantity": str(requirement.order_quantity),
            "netQuantity": str(requirement.net_quantity),
            "grossQuantity": None,
            "scrapRate": None,
            "scrapRateStatus": requirement.scrap_rate_status,
            "uom": material.base_uom.code,
        })
    return {
        "serviceCode": SERVICE_CODE,
        "requirementCreateCount": created,
        "auditWriteCount": len(audit_ids),
        "businessWriteCount": created + len(audit_ids),
        "auditIds": audit_ids,
        "requirements": rows,
        "calculationReexecuted": False,
        "otherObjectAutoGeneratedCount": 0,
    }


def apply_authorized_so202609180003_representatives(*, user) -> dict:
    """Controlled entry point for the two representatives authorized on 2026-10-04."""
    approvals = AUTHORIZED_SO202609180003_REPRESENTATIVES
    mapping_result = confirm_authorized_mappings(user=user, approvals=approvals)
    mapping_readback = readback_authorized_mappings(user=user, approvals=approvals)
    requirement_result = create_authorized_requirements(user=user, approvals=approvals)
    return {
        "serviceCode": SERVICE_CODE,
        "authorizationReference": AUTHORIZATION_REFERENCE,
        "mappingResult": mapping_result,
        "mappingReadback": mapping_readback,
        "requirementResult": requirement_result,
        "businessWriteCount": (
            mapping_result["businessWriteCount"] + requirement_result["businessWriteCount"]
        ),
        "calculationReexecuted": False,
        "bomGenerated": False,
    }
