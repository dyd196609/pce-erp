from pde.baseline_usage_service import production_baselines
"""Read-only bridge from immutable calculation evidence to the existing BOM chain.

No evaluation, default quantity, write service or numbering API is used here.
Current master data are candidates, never amendments to a saved R1 snapshot.
"""
import re
from datetime import datetime
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.utils import timezone
from masterdata.models import Material, UnitOfMeasure
from sales.models import SalesOrder
from system.authorization import AuthorizationService

from .engineering_calculation_service import EngineeringCalculationError, EngineeringCalculationService, OrderEngineeringClosureService
from .engineering_rule_foundation import ROUNDING_MODES, specification_hash
from .formal_manufacturing_eligibility_service import FormalManufacturingEligibilityService
from .models import (BOMItem, BOMVersion, EngineeringCalculationRecord, EngineeringRuleDefinition,
                     OrderEngineeringBaselineItem, ProductBOM, ProductManufacturingOutput, Routing)


class HandoffReadError(Exception):
    def __init__(self, code, message, http_status=409):
        self.code, self.message, self.http_status = code, message, http_status


BOM_MATERIAL_REQUIREMENT_GATE_CODE = "MATERIAL_REQUIREMENT_REQUIRED"
BOM_MATERIAL_REQUIREMENT_GATE_MESSAGE = "该核算没有形成物料需求，不能生成空BOM草稿。"
BOM_PARTIAL_PREVIEW_GATE_CODE = "BOM_PARTIAL_PREVIEW_AVAILABLE"


def order_business_purpose(order):
    """Compatibility projection backed by the shared fail-closed service."""
    eligibility = FormalManufacturingEligibilityService.resolve(order)
    return {
        "code": eligibility["businessPurposeCode"],
        "statusLabel": eligibility["businessPurposeLabel"],
        "boundary": eligibility["message"],
        "formalManufacturingEligible": eligibility["formalManufacturingEligible"],
        "decisionCode": eligibility["decisionCode"],
        "orderTraceUnique": eligibility["orderTraceUnique"],
        "evidence": eligibility["evidence"],
    }


def bom_handoff_gate(*, records, selected_order, company_id, target_calculation_id=None):
    """Resolve a target BOM subject while retaining order-wide progress as information."""
    order_requirement_count = sum(row["materialRequirementCount"] for row in records)
    order_object_count = sum(row["objectCount"] for row in records)
    order_covered_object_count = sum(
        bool(obj.get("formalMaterialRequirementCount"))
        for row in records for obj in row.get("objects", [])
    )
    order_preview_ready_count = sum(bool(row.get("formalRequirementPreview")) for row in records)
    target_record = next((
        row for row in records if row.get("calculationId") == target_calculation_id
    ), None) if target_calculation_id else None
    target_records = [target_record] if target_record else []
    target_requirement_count = sum(row["materialRequirementCount"] for row in target_records)
    target_object_count = sum(row["objectCount"] for row in target_records)
    target_covered_object_count = sum(
        bool(obj.get("formalMaterialRequirementCount"))
        for row in target_records for obj in row.get("objects", [])
    )
    if not selected_order:
        return {
            "code": "ORDER_SELECTION_REQUIRED",
            "statusLabel": "请选择订单后检查BOM承接条件",
            "message": "尚未选择包含已完成正式核算的订单。",
            "canPreview": False,
            "canGenerate": False,
            "missingConditions": [{
                "code": "ORDER_SELECTION_REQUIRED",
                "statusLabel": "缺少订单范围",
                "message": "请选择订单后再执行只读BOM条件预览。",
            }],
            "formalEngineeringMaterialRequirementCount": 0,
            "formalRequirementObjectCount": 0,
            "remainingObjectCount": 0,
            "previewReadyCalculationCount": 0,
            "blockedCalculationCount": 0,
            "orderCoverageComplete": False,
            "productBomCount": 0,
            "bomVersionCount": 0,
            "bomItemCount": 0,
            "businessWriteSideEffectCount": 0,
            "targetScope": None,
            "orderScope": {
                "totalDesignItemCount": 0,
                "totalCoveredCount": 0,
                "coverageStatus": "NOT_SELECTED",
                "gateRole": "INFORMATIONAL",
            },
        }
    product_boms = ProductBOM.objects.filter(
        company_id=company_id,
        order_engineering_instance__sales_order_item__sales_order_id=selected_order.pk,
    )
    bom_versions = BOMVersion.objects.filter(
        Q(source_calculation__sales_order_item__sales_order_id=selected_order.pk)
        | Q(order_engineering_instance__sales_order_item__sales_order_id=selected_order.pk)
    ).distinct()
    bom_items = BOMItem.objects.filter(bom_version__in=bom_versions)
    target_selected = target_calculation_id is not None
    target_found = target_record is not None
    target_blocked = target_found and target_requirement_count == 0
    target_partial = target_found and not target_blocked and target_covered_object_count < target_object_count
    preview = target_record.get("formalRequirementPreview") if target_record else None
    preview_blocker = (preview or {}).get("firstRealBlocker")
    preview_error = (target_record or {}).get("formalRequirementPreviewError")
    if not preview_blocker and preview_error:
        # Preserve the authoritative preview refusal. Object coverage alone
        # cannot claim readiness when aggregation/completeness did not finish.
        preview_blocker = {
            "code": preview_error["code"],
            "statusLabel": "目标BOM预览受阻",
            "message": preview_error["message"],
        }
    already_generated = bool((preview or {}).get("alreadyGenerated"))
    cancelled = str(getattr(selected_order, "status", "")).lower() in {"cancelled", "canceled"}
    missing_conditions = []
    if not target_selected:
        missing_conditions = [{
            "code": "TARGET_BOM_SUBJECT_REQUIRED",
            "statusLabel": "请选择目标Calculation",
            "message": "整单覆盖仅作进度展示；生成门禁必须定位到SalesOrderItem/OEI/Calculation。",
        }]
    elif not target_found:
        missing_conditions = [{
            "code": "TARGET_BOM_SUBJECT_NOT_FOUND",
            "statusLabel": "目标Calculation不在当前订单范围",
            "message": "拒绝从其他订单行、OEI或Calculation借用Requirement。",
        }]
    elif cancelled:
        missing_conditions = [{
            "code": "CANCELLED_ORDER_BOM_ISOLATED",
            "statusLabel": "取消订单保持隔离",
            "message": "取消订单不得形成BOM候选或推进BOM生成。",
        }]
    elif target_blocked:
        missing_conditions = [{
            "code": "FORMAL_ENGINEERING_MATERIAL_REQUIREMENT_REQUIRED",
            "statusLabel": "目标主体正式工程材料需求尚未形成",
            "message": "当前只读候选和Mapping确认卡不属于正式EngineeringMaterialRequirement。",
        }]
    elif target_partial:
        missing_conditions = [{
            "code": "TARGET_BOM_REQUIREMENT_COVERAGE_INCOMPLETE",
            "statusLabel": "目标BOM对象Requirement覆盖不完整",
            "message": f"目标主体仅{target_covered_object_count}/{target_object_count}个对象形成正式材料需求。",
        }]
    elif already_generated:
        missing_conditions = [{
            "code": "BOM_ALREADY_GENERATED",
            "statusLabel": "目标Calculation已生成BOM草稿",
            "message": "保持原幂等链，不创建重复ProductBOM或BOMVersion。",
        }]
    elif preview_blocker:
        missing_conditions = [preview_blocker]
    purpose = order_business_purpose(selected_order)
    if not missing_conditions:
        generation_reason = (
            "目标主体已通过只读Readiness；实际生成仍必须由既有generate_bom服务校验"
            "Preview Hash、权限、Admission与幂等约束。"
        )
    elif purpose["code"] == "DEVELOPMENT_VALIDATION":
        generation_reason = (
            "开发验证draft由统一正式制造资格门禁隔离：允许创建和只读查看，"
            "禁止进入评审、发布及正式制造下游；本页保持只读，不提供生成动作。"
        )
    else:
        generation_reason = (
            "本轮只获准执行只读Preview；生成BOM仍需独立授权、匹配Preview Hash和原正式生命周期校验。"
        )
    target_coverage_complete = bool(target_object_count) and target_covered_object_count == target_object_count
    can_generate = bool(
        target_found and target_coverage_complete and preview and preview.get("canGenerate")
        and not missing_conditions
    )
    gate_code = missing_conditions[0]["code"] if missing_conditions else "BOM_TARGET_READY"
    return {
        "code": gate_code,
        "statusLabel": (
            missing_conditions[0]["statusLabel"] if missing_conditions else
            "目标BOM输入已通过完整性门禁"
        ),
        "message": (
            missing_conditions[0]["message"] if missing_conditions else
            "目标SalesOrderItem/OEI/Calculation已通过覆盖和当前版本材料完整性检查；整单进度不参与该Hard Gate。"
        ),
        "canPreview": bool(target_record or (records and not target_selected)),
        "canGenerate": can_generate,
        "generationDisabledReason": generation_reason,
        "developmentValidationDraftSupported": purpose["code"] == "DEVELOPMENT_VALIDATION",
        "businessPurposeCode": purpose["code"],
        "businessPurposeLabel": purpose["statusLabel"],
        "formalManufacturingEligible": purpose["formalManufacturingEligible"],
        "formalManufacturingDecisionCode": purpose["decisionCode"],
        "formalManufacturingMessage": purpose["boundary"],
        "missingConditions": missing_conditions,
        "formalEngineeringMaterialRequirementCount": target_requirement_count if target_found else order_requirement_count,
        "formalRequirementObjectCount": order_covered_object_count,
        "remainingObjectCount": order_object_count - order_covered_object_count,
        "previewReadyCalculationCount": order_preview_ready_count,
        "blockedCalculationCount": len(records) - order_preview_ready_count,
        "orderCoverageComplete": bool(order_object_count) and order_covered_object_count == order_object_count,
        "coverageStatus": (
            "NOT_SELECTED" if not target_selected else
            "BLOCKED" if missing_conditions else
            "COMPLETE"
        ),
        "targetCoverageGate": "PASS" if target_coverage_complete else "FAIL",
        "targetScope": ({
            "salesOrderItemId": target_record.get("lineId"),
            "lineNo": target_record.get("lineNo"),
            "orderEngineeringInstanceId": target_record.get("instanceId"),
            "orderEngineeringInstanceNo": target_record.get("instanceNo"),
            "calculationId": target_record.get("calculationId"),
            "calculationNo": target_record.get("calculationNo"),
            "designItemCount": target_object_count,
            "coveredDesignItemCount": target_covered_object_count,
            "formalRequirementCount": target_requirement_count,
            "coverageGate": "PASS" if target_coverage_complete else "FAIL",
        } if target_record else None),
        "orderScope": {
            "salesOrderId": selected_order.pk,
            "orderNo": selected_order.order_no,
            "totalDesignItemCount": order_object_count,
            "totalCoveredCount": order_covered_object_count,
            "formalRequirementCount": order_requirement_count,
            "coverageStatus": (
                "COMPLETE" if order_object_count and order_covered_object_count == order_object_count else
                "PARTIAL" if order_covered_object_count else "BLOCKED"
            ),
            "gateRole": "INFORMATIONAL",
            "hardBlocker": False,
        },
        "currentVersionMaterialCompleteness": (preview or {}).get("currentVersionMaterialCompleteness"),
        "firstRealBlocker": missing_conditions[0] if missing_conditions else None,
        "productBomCount": product_boms.count(),
        "bomVersionCount": bom_versions.count(),
        "bomItemCount": bom_items.count(),
        "previewService": {
            "service": "OrderEngineeringClosureService.preview_bom",
            "api": "/api/pde/a1-engineering/calculations/{calculationId}/bom-preview/",
            "method": "GET",
            "businessWriteSideEffectCount": 0,
        },
        "businessWriteSideEffectCount": 0,
    }


def require(condition, message):
    if not condition:
        raise HandoffReadError("HANDOFF_EVIDENCE_MISMATCH", message)


def positive_id(value):
    if value in (None, ""):
        return None
    if not str(value).isdigit() or int(value) <= 0:
        raise HandoffReadError("HANDOFF_CONTEXT_INVALID", "订单或正式核算定位参数无效。", 400)
    return int(value)


def gap(code, field, evidence, stage, location, owner, kind="业务资料待确认"):
    return dict(code=code, field=field, evidence=evidence, stage=stage,
                location=location, owner=owner, kind=kind)


MATERIAL_REQUIREMENT_MAPPING_CONTRACT = {
    "contractCode": "PCE-MATERIAL-REQUIREMENT-MAPPING-V1",
    "storageDecision": "REUSE_ENGINEERING_RULE_DEFINITION_JSON",
    "schemaChangeRequired": False,
    "cardinality": "每个DesignItem允许0、1或多条Material Requirement；DesignItem不等于单一Material Requirement。",
    "requiredFields": [
        "applicabilityScope", "sourceFactCode", "materialId", "outputUom",
        "quantityBasis", "quantityExpression", "quantitySource", "salesItemMultiplier",
        "scrapRate", "itemRole", "requirementType", "supplyType", "orderSpecification",
        "rounding", "precision", "sourceRuleVersion", "effectiveScope",
        "mappingVersion", "auditIdentity",
    ],
    "quantityBasisValues": ["PER_SALES_ITEM_UNIT", "ORDER_TOTAL"],
    "quantityBoundary": {
        "savedDerivedFact": "只读取已保存DerivedFact值；不重新执行工程核算公式。",
        "designObjectQuantity": "不得默认再乘设计对象数量；如它已进入已保存事实，保持已保存口径。",
        "salesItemQuantity": "仅PER_SALES_ITEM_UNIT且salesItemMultiplier=APPLY_ONCE时乘SalesOrderItem.quantity一次；ORDER_TOTAL必须为NONE。",
    },
    "uomPolicy": "输出UOM必须是正式Material基础UOM；不做mm→m、块→m2、扇→m2或组→件等隐式换算。",
    "jsonPlacement": {
        "applicabilityScope": "specification.applicability",
        "sourceFactCode": "specification.outputs[0].sourceFactCode",
        "materialAndQuantity": "specification.outputs[0]",
        "roundingAndPrecision": "specification.roundingMode/decimalPrecision/outputScale",
        "sourceRuleVersion": "specification.outputs[0].sourceRuleVersion",
        "effectiveScope": "EngineeringRuleDefinition.effective_from/effective_to + specification.applicability",
        "mappingVersionAndAuditIdentity": "EngineeringRuleDefinition.id/rule_code/version + specificationHash",
    },
}

MATERIAL_PREVIEW_STATUSES = (
    "CONFIRMED", "READY_FOR_REQUIREMENT", "MISSING_MATERIAL", "MISSING_MAPPING",
    "MISSING_UOM", "AMBIGUOUS_MATERIAL", "MISSING_QUANTITY_CONTRACT",
    "NOT_APPLICABLE",
)

BUSINESS_CONFIRMATION_STATUSES = (
    "CONFIRMED", "READY_FOR_BUSINESS_CONFIRMATION", "MATERIAL_IDENTITY_REQUIRED",
    "QUANTITY_RULE_REQUIRED", "UOM_DEFINITION_REQUIRED", "BUSINESS_FACT_REQUIRED",
)


def _mapping_contract(rule):
    """Project one released rule into the stricter R1 no-recalc mapping contract."""
    spec = rule.specification if isinstance(rule.specification, dict) else {}
    outputs = spec.get("outputs") if isinstance(spec.get("outputs"), list) else []
    output = outputs[0] if len(outputs) == 1 and isinstance(outputs[0], dict) else {}
    if output.get("resultDomain") != "MATERIAL_REQUIREMENT":
        return None
    source = output.get("quantitySource") if isinstance(output.get("quantitySource"), dict) else {}
    source_fact_code = str(output.get("sourceFactCode") or source.get("sourceFactCode") or "").strip()
    output_uom = output.get("outputUom") or output.get("unit")
    quantity_basis = str(output.get("quantityBasis") or "").strip()
    expression = str(output.get("quantityExpression") or "").strip()
    multiplier = str(output.get("salesItemMultiplier") or "").strip()
    required_text = {
        "sourceFactCode": source_fact_code,
        "outputUom": output_uom,
        "quantityBasis": quantity_basis,
        "quantityExpression": expression,
        "quantitySource.type": source.get("type"),
        "salesItemMultiplier": multiplier,
        "itemRole": output.get("itemRole"),
        "requirementType": output.get("requirementType"),
        "supplyType": output.get("supplyType"),
        "sourceRuleVersion": output.get("sourceRuleVersion"),
    }
    missing = [key for key, value in required_text.items() if value in (None, "")]
    if rule.rule_kind != "mapping":
        missing.append("ruleKind=mapping")
    try:
        material_id = int(output.get("materialId"))
    except (TypeError, ValueError):
        material_id = None
        missing.append("materialId")
    source_type = source.get("type")
    if source_type == "SAVED_DERIVED_FACT":
        if expression != "SOURCE_FACT_VALUE":
            missing.append("quantityExpression=SOURCE_FACT_VALUE")
    elif source_type == "SAVED_DERIVED_FACT_SET":
        source_fact_codes = source.get("sourceFactCodes")
        source_facts = source.get("sourceFacts")
        if (
            not isinstance(source_fact_codes, list)
            or not source_fact_codes
            or source_fact_code not in source_fact_codes
        ):
            missing.append("quantitySource.sourceFactCodes")
        if not isinstance(source_facts, list) or len(source_facts) != len(source_fact_codes or []):
            missing.append("quantitySource.sourceFacts")
        if not expression or expression == "SOURCE_FACT_VALUE":
            missing.append("quantityExpression=formula")
    else:
        missing.append("quantitySource.type=SAVED_DERIVED_FACT[_SET]")
    if quantity_basis not in MATERIAL_REQUIREMENT_MAPPING_CONTRACT["quantityBasisValues"]:
        missing.append("quantityBasis")
    expected_multiplier = "APPLY_ONCE" if quantity_basis == "PER_SALES_ITEM_UNIT" else "NONE"
    if multiplier != expected_multiplier:
        missing.append(f"salesItemMultiplier={expected_multiplier}")
    if not isinstance(spec.get("applicability"), dict):
        missing.append("applicabilityScope")
    specification_audit_identity = spec.get("auditIdentity")
    if (
        not isinstance(specification_audit_identity, dict)
        or not str(specification_audit_identity.get("authorizationReference") or "").strip()
    ):
        missing.append("auditIdentity.authorizationReference")
    if not isinstance(output.get("orderSpecification"), dict):
        missing.append("orderSpecification")
    if not isinstance(spec.get("decimalPrecision"), int) or not isinstance(spec.get("outputScale"), int):
        missing.append("rounding/precision")
    if not str(spec.get("roundingMode") or "").strip():
        missing.append("rounding")
    scrap_rate = output.get("scrapRate")
    if scrap_rate is not None:
        try:
            rate = Decimal(str(scrap_rate))
            if rate < 0 or rate >= 1:
                missing.append("scrapRate[0,1)")
        except InvalidOperation:
            missing.append("scrapRate")
    today = datetime.now().date()
    current_effective = (
        (not rule.effective_from or rule.effective_from <= today)
        and (not rule.effective_to or rule.effective_to >= today)
    )
    order_specification = output.get("orderSpecification") or {}
    source_evidence = spec.get("sourceEvidence") or {}
    audit_identity = spec.get("auditIdentity") or {}
    return {
        "id": rule.pk, "code": rule.rule_code, "version": rule.version,
        "mappingVersion": rule.version,
        "mappingNo": audit_identity.get("mappingNo"),
        "auditIdentity": {
            "ruleId": rule.pk, "ruleCode": rule.rule_code, "ruleVersion": rule.version,
            "specificationHash": specification_hash(spec),
            "authorization": specification_audit_identity,
        },
        "applicabilityScope": spec.get("applicability", {}),
        "effectiveScope": {
            "effectiveFrom": str(rule.effective_from) if rule.effective_from else None,
            "effectiveTo": str(rule.effective_to) if rule.effective_to else None,
            "currentEffective": current_effective,
        },
        "sourceFactCode": source_fact_code, "materialId": material_id,
        "outputUom": output_uom, "quantityBasis": quantity_basis,
        "quantityExpression": expression, "quantitySource": source,
        "salesItemMultiplier": multiplier, "scrapRate": scrap_rate,
        "itemRole": output.get("itemRole"), "requirementType": output.get("requirementType"),
        "supplyType": output.get("supplyType"), "orderSpecification": order_specification,
        "sourceExternalIdentity": (
            order_specification.get("sourceExternalIdentity")
            or source_evidence.get("materialSourceExternalIdentity")
        ),
        "provenance": spec.get("provenance") or {},
        "rounding": spec.get("roundingMode"), "precision": {
            "decimalPrecision": spec.get("decimalPrecision"), "outputScale": spec.get("outputScale"),
        },
        "sourceRuleVersion": output.get("sourceRuleVersion"),
        "contractStatus": "READY" if not missing else "INCOMPLETE",
        "missingConditions": sorted(set(missing)),
    }


def _applicable(mapping, context):
    """Exact-only applicability. Unknown fields fail closed instead of approximate matching."""
    for key, expected in (mapping.get("applicabilityScope") or {}).items():
        actual = context.get(key)
        allowed = expected if isinstance(expected, list) else [expected]
        if str(actual) not in {str(value) for value in allowed}:
            return False
    return True


def saved_quantity_basis(detail):
    """Describe dependency evidence; do not evaluate or multiply the saved value."""
    keys = set(re.findall(r"\b[A-Za-z_][A-Za-z_0-9]*\b", detail.expression_snapshot or ""))
    inputs = (detail.input_snapshot or {}).get("ruleInputs", [])
    used = [i for i in inputs if i.get("key") in keys]
    quantities = [i for i in used if "数量" in str(i.get("name", ""))]
    return {
        "expression": detail.expression_snapshot,
        "inputs": used,
        "label": "按下列已保存表达式及输入读取；不再次乘对象或订单数量。批量/订单用量口径须由材料或工序规则明确。",
        "quantityDependencyLabel": ("表达式已使用数量输入：" + "、".join(f"{i['name']}={i.get('value')}" for i in quantities)) if quantities else "本表达式的直接输入未引用数量字段；保留保存值，不自行扩展为整单量",
        "batchBasisLabel": "保存表达式未声明独立基准批量/订单行乘数合同；不能默认乘订单数量或再乘对象数量",
    }


def validate_record_scope(record, company_id):
    item, instance = record.sales_order_item, record.engineering_instance
    require(record.company_id == company_id and item and instance and record.source_record_id,
            "正式核算缺少合法公司、订单行、实例或来源关系。")
    require(item.sales_order.company_id == company_id == instance.company_id == record.source_record.company_id,
            "正式核算引用跨公司，停止承接读取。")
    require(instance.sales_order_item_id == item.pk and instance.source_record_id == record.source_record_id,
            "核算与实例的订单行/来源不一致，停止承接读取。")
    trace = record.trace or {}
    require(trace.get("salesOrderItemId") == item.pk
            and trace.get("orderEngineeringInstanceId") == instance.pk
            and (trace.get("sourceReference") or {}).get("id") == record.source_record_id,
            "已保存追溯与正式核算归属不一致。")
    require((trace.get("baselineReference") or {}).get("orderId") == item.sales_order_id,
            "已保存基线不属于当前订单。")


def _unit(unit):
    if not unit:
        return None
    return dict(id=unit.pk, code=unit.code, name=unit.name, dimension=unit.dimension,
                active=unit.is_active, conversionBaseId=unit.conversion_base_id,
                conversionFactor=str(unit.conversion_factor))


def _material(material):
    if not material:
        return None
    return dict(id=material.pk, code=material.code, name=material.name,
                specification=material.specification, active=material.is_active,
                unitStatus=material.unit_status, baseUnit=_unit(material.base_uom),
                materialType=material.get_material_type_display(),
                supplyLabel=material.supply_type_display,
                produced=material.is_produced, purchased=material.is_purchased,
                updatedAt=material.updated_at.isoformat(),
                versionLabel="该物料模型无独立版本/发布状态字段；显示当前启用状态与更新时间，不代表保存时确认")


def _routing(routing, today):
    versions = []
    for version in routing.versions.all():
        for step in version.steps.all():
            require(step.operation.company_id == routing.company_id, "路线工序引用跨公司，停止承接读取。")
            if step.operation.calculation_uom:
                require(step.operation.calculation_uom.company_id == routing.company_id, "工序核算单位跨公司，停止承接读取。")
        steps = [dict(id=s.pk, sequence=s.sequence, operationId=s.operation_id,
                      operationCode=s.operation.code, operationName=s.operation.name,
                      active=s.is_active and s.operation.is_active,
                      unit=_unit(s.operation.calculation_uom),
                      quantityDriver=s.operation.quantity_driver,
                      calculationBasis=s.operation.calculation_basis)
                 for s in version.steps.all()]
        versions.append(dict(id=version.pk, version=version.routing_version,
                             statusLabel=version.get_status_display(),
                             currentEffective=routing.is_active and routing.status == "released"
                             and (not routing.effective_from or routing.effective_from <= today)
                             and (not routing.effective_to or routing.effective_to >= today)
                             and version.status == "released"
                             and (not version.effective_date or version.effective_date <= today)
                             and (not version.expire_date or version.expire_date >= today),
                             effectiveFrom=str(version.effective_date or "未设置"),
                             effectiveTo=str(version.expire_date or "未设置"),
                             applicability=version.applicability, steps=steps, stepCount=len(steps),
                             missingOperationUnitCount=sum(not s["unit"] for s in steps)))
    return dict(id=routing.pk, code=routing.routing_code, name=routing.name,
                categoryId=routing.product_category_id, instanceId=routing.order_engineering_instance_id,
                scopeLabel=routing.get_applicability_scope_display(), statusLabel=routing.get_status_display(),
                versions=versions, identityLabel="仅按保存的工艺编码精确关联当前路线；尚非已确认的对象工序需求")


def record_handoff(record, company_id, *, include_bom_preview=True):
    validate_record_scope(record, company_id)
    trace, instance, item = record.trace, record.engineering_instance, record.sales_order_item
    eligibility = FormalManufacturingEligibilityService.resolve(record)
    snapshots, results = trace.get("objectInputSnapshot"), trace.get("resultSnapshot")
    require(isinstance(snapshots, list) and snapshots and isinstance(results, list),
            "该核算没有可独立承接的完整对象/结果快照；不以实时设计或重算补齐。")
    details = {d.pk: d for d in record.details.all()}
    facts = {f.pk: f for f in record.derived_facts.all()}
    require(len(results) == len(details) == len(facts), "已保存结果、明细和派生事实数量不一致。")
    baseline_id = trace["baselineReference"]["id"]
    baseline_items = {b.pk: b for b in OrderEngineeringBaselineItem.objects.filter(baseline__in=production_baselines(),
        baseline_id=baseline_id, baseline__company_id=company_id,
        pk__in=[s.get("baselineItemId") for s in snapshots]).select_related(
            "design_item__source_attribute")}
    require(len(baseline_items) == len(snapshots), "基线对象缺失或重复，无法安全定位。")
    material_ids = [s["input"].get("materialId") for s in snapshots]
    materials = {m.pk: m for m in Material.objects.filter(company_id=company_id, pk__in=material_ids).select_related("base_uom")}
    unit_ids = [s["input"].get("physicalUomId") for s in snapshots]
    units = {u.pk: u for u in UnitOfMeasure.objects.filter(company_id=company_id, pk__in=unit_ids)}
    route_codes = {s["input"].get("routingProcessCode") for s in snapshots}
    routes = defaultdict(list)
    for routing in Routing.objects.filter(company_id=company_id, routing_code__in=route_codes).prefetch_related(
            "versions__steps__operation__calculation_uom"):
        routes[routing.routing_code].append(_routing(routing, timezone.now().date()))
    by_object, seen_details, seen_facts, seen_positions = defaultdict(list), set(), set(), set()
    object_ids = [s.get("designItemId") for s in snapshots]
    require(len(set(object_ids)) == len(object_ids), "核算对象身份重复。")
    for result in results:
        detail, fact = details.get(result.get("detailId")), facts.get(result.get("factId"))
        object_id = result.get("designItemId")
        require(detail and fact and object_id in object_ids, "结果没有对应正式明细/派生事实/对象。")
        position = (object_id, result.get("canonicalField"))
        require(detail.pk not in seen_details and fact.pk not in seen_facts and position not in seen_positions,
                "结果位置或正式来源重复。")
        seen_details.add(detail.pk); seen_facts.add(fact.pk); seen_positions.add(position)
        require(fact.source_detail_id == detail.pk and fact.value == detail.output_value == result.get("value")
                and fact.canonical_field == result.get("canonicalField")
                and fact.trace.get("designItemId") == object_id
                and detail.input_snapshot.get("object", {}).get("designItemId") == object_id,
                "结果位置、值或对象链不一致。")
        value = result.get("value")
        by_object[object_id].append(dict(
            **result, valueText=str(value.get("decimal")) if isinstance(value, dict) else str(value),
            quantityBasis=saved_quantity_basis(detail), sourcePath=fact.source_path,
            downstreamUseLabel="已保存工程量依据；未确认材料/工序映射，不作为采购量或BOM用量"))
    material_requirements = list(record.material_requirements.select_related("material", "uom", "source_detail").all())
    operation_requirements = list(record.operation_requirements.all())
    existing_versions = list(BOMVersion.objects.filter(
        Q(source_calculation=record) | Q(order_engineering_instance=instance),
        bom__company_id=company_id).select_related("bom").distinct())
    objects = []
    for snapshot in snapshots:
        saved, object_id = snapshot["input"], snapshot["designItemId"]
        baseline = baseline_items[snapshot["baselineItemId"]]
        require(baseline.design_item_id == object_id and baseline.source_record_id == record.source_record_id
                and baseline.design_item.sales_order_item_id == item.pk
                and baseline.content_hash == snapshot.get("contentHash"), "基线对象跨行或指纹不一致。")
        require(saved.get("sourceRecordId") == record.source_record_id
                and saved.get("designItemId") == object_id and by_object[object_id], "对象输入与结果断链。")
        require(saved.get("sourceVersion") == trace["sourceReference"].get("sourceVersion")
                and saved.get("sourceContentHash") == trace["sourceReference"].get("contentHash"), "对象来源版本与核算快照不一致。")
        for result in by_object[object_id]:
            fact, detail = facts[result["factId"]], details[result["detailId"]]
            require(detail.input_snapshot.get("object") == saved
                    and fact.trace.get("baselineItemId") == baseline.pk
                    and result.get("sourceKey") == snapshot["sourceKey"], "结果明细与稳定基线对象不一致。")
        material, unit = materials.get(saved.get("materialId")), units.get(saved.get("physicalUomId"))
        source_design = baseline.design_item.existing_design_data if isinstance(
            baseline.design_item.existing_design_data, dict) else {}
        source_raw = baseline.design_item.source_attribute.raw_value if isinstance(
            baseline.design_item.source_attribute.raw_value, dict) else {}
        source_material_code = str(
            source_design.get("materialProcessCode") or source_raw.get("materialProcessCode") or ""
        ).strip()
        source_material_match = (baseline.design_item.match_results or {}).get("material")
        business_context = {
            "product": source_raw.get("product") or "",
            "component": source_raw.get("component") or baseline.item_name_snapshot or "",
            "materialText": source_raw.get("materialName") or "",
            "sourceSpecification": source_raw.get("specification") or "",
            "finishOrColor": saved.get("finishOrColor") or source_design.get("finishOrColor") or "",
            "processConfiguration": saved.get("processConfigurationCode") or "",
            "paintProcess": saved.get("paintProcess") or source_design.get("paintProcess") or "",
            "edgeMethod": saved.get("edgeMethod") or source_design.get("edgeMethod") or "",
            "visibleCondition": saved.get("visibleCondition") or source_design.get("visibleCondition") or "",
            "hardware": source_design.get("hardware") or "",
            "glass": source_design.get("glass") or "",
            "processingNote": source_design.get("processingNote") or source_raw.get("processingNote") or "",
        }
        if material and material.base_uom:
            require(material.base_uom.company_id == company_id, "物料基本单位跨公司，停止承接读取。")
        object_requirements = [r for r in material_requirements if r.source_detail_id in {f["detailId"] for f in by_object[object_id]}]
        requirement_materials = {r.material_id: r.material for r in object_requirements}
        readback_material = material or (
            next(iter(requirement_materials.values())) if len(requirement_materials) == 1 else None
        )
        if readback_material and readback_material.base_uom:
            require(readback_material.base_uom.company_id == company_id, "正式材料需求引用的物料基本单位跨公司，停止承接读取。")
        serialized_object_requirements = [{
            "id": requirement.pk,
            "mappingNo": (requirement.trace or {}).get("mappingNo"),
            "mappingRuleId": (requirement.trace or {}).get("mappingRuleId"),
            "mappingRuleCode": (requirement.trace or {}).get("mappingRuleCode"),
            "mappingVersion": (requirement.trace or {}).get("mappingVersion"),
            "sourceFactId": (requirement.trace or {}).get("sourceFactId"),
            "sourceDetailId": requirement.source_detail_id,
            "materialId": requirement.material_id,
            "materialCode": requirement.material.code,
            "materialName": requirement.material.name,
            "material": _material(requirement.material),
            "calculatedQuantity": str(requirement.calculated_quantity),
            "orderQuantity": str(requirement.order_quantity),
            "netQuantity": str(requirement.net_quantity),
            "grossQuantity": str(requirement.gross_quantity) if requirement.gross_quantity is not None else None,
            "uom": requirement.uom.code,
            "quantityBasis": requirement.quantity_basis,
            "salesItemMultiplier": (requirement.trace or {}).get("salesItemMultiplier"),
            "itemRole": requirement.item_role,
            "requirementType": requirement.requirement_type,
            "supplyType": requirement.supply_type,
            "scrapRate": str(requirement.scrap_rate) if requirement.scrap_rate is not None else None,
            "scrapRateStatus": requirement.scrap_rate_status,
            "scrapStatusLabel": (
                "损耗率尚未维护；grossQuantity保持空值，不冒充0%损耗"
                if requirement.scrap_rate_status != "maintained" else
                "已维护正式损耗率"
            ),
            "calculationReexecuted": (requirement.trace or {}).get("calculationReexecuted"),
            "authorizationReference": (requirement.trace or {}).get("authorizationReference"),
            "sourceExternalIdentity": (
                (requirement.trace or {}).get("sourceMaterialExternalIdentity")
                or ((requirement.trace or {}).get("provenance") or {}).get("sourceExternalIdentity")
            ),
            "provenance": (requirement.trace or {}).get("provenance") or {},
            "responsibilitySource": (
                ((requirement.trace or {}).get("provenance") or {}).get("responsibilitySource")
            ),
            "orderSpecification": requirement.order_specification,
        } for requirement in object_requirements]
        gaps = []
        if not readback_material:
            gaps.append(gap("MATERIAL", "正式物料引用", f"保存输入materialId={saved.get('materialId')}；未按名称猜配", "材料需求/BOM草稿", "产品设计（工程数据录入）→物料引用；EMD物料管理", "工程设计＋物料主数据维护"))
        elif not readback_material.is_active or readback_material.unit_status != "confirmed" or not readback_material.base_uom_id or not readback_material.base_uom.is_active:
            gaps.append(gap("MATERIAL_STATE", "物料启用/基础单位", "当前物料或单位未满足有效合同", "材料需求/BOM草稿", "EMD物料管理／计量单位", "物料主数据维护"))
        if not unit or not unit.is_active:
            gaps.append(gap("PHYSICAL_UNIT", "对象正式数量单位", f"保存文字单位：{saved.get('physicalUom')}，正式ID：{saved.get('physicalUomId')}", "材料/工序数量依据", "产品设计（工程数据录入）→数量单位；EMD计量单位", "工程设计＋计量单位维护"))
        if not object_requirements:
            gaps.extend([
                gap("MAPPING", "结果→物料/标准净用量/单位/批量口径规则", "派生事实不是材料需求；面积/封边/见光等仅保留原值，不乘数量、不换算", "材料需求/BOM草稿", "工程核算规则管理＋BOM结构维护", "工程/BOM设计＋规则管理"),
                gap("STRUCTURE", "父子结构与物料角色/供应方式适用依据", "来源行与分类不是正式父子关系；本对象未形成带来源的材料需求", "BOM草稿/发布", "BOM管理→BOM版本管理（获批后维护）", "BOM工程设计"),
            ])
        if not operation_requirements:
            gaps.append(gap("OPERATION_MAPPING", "对象→路线版本/工序投入量及单位依据", "保存了工艺编码，不等于保存了工序或路线版本；当前路线仅为可复用候选", "工序需求/制造发布", "工艺路线管理→工艺路线版本管理；工序管理；工程核算规则管理", "工艺工程＋规则管理"))
            current_routes = routes.get(saved.get("routingProcessCode"), [])
            missing_units = [f"{r['code']}/{v['version']}：{v['missingOperationUnitCount']}/{v['stepCount']}步骤未声明工序核算单位"
                             for r in current_routes for v in r["versions"] if v["missingOperationUnitCount"]]
            if missing_units:
                gaps.append(gap("OPERATION_UNIT", "候选路线工序的核算单位", "；".join(missing_units) + "。并非要求每一步都生成需求，先由工艺负责人确认适用步骤，再明确输出单位合同", "适用工序需求", "工序管理→核算依据/单位；工程核算规则管理", "工艺工程＋计量单位维护"))
        objects.append(dict(
            id=object_id, objectNo=snapshot["designItemNo"], objectName=baseline.item_name_snapshot, lineNo=item.line_no,
            sourceKey=snapshot["sourceKey"], baselineItemId=baseline.pk, savedInput=saved,
            sourceMaterialCode=source_material_code, sourceMaterialMasterMatch=source_material_match,
            businessContext=business_context,
            physicalQuantity=saved.get("physicalQuantity"), physicalUnit=saved.get("physicalUom") or "未确认",
            currentUnit=_unit(unit), material=_material(readback_material),
            materialLabel=(
                f"Material{readback_material.pk} · {readback_material.code} {readback_material.name}"
                if readback_material else "未确认正式物料"
            ),
            routingCandidateIds=[r["id"] for r in routes.get(saved.get("routingProcessCode"), [])],
            facts=by_object[object_id], factCount=len(by_object[object_id]), gaps=gaps, gapCount=len(gaps),
            formalMaterialRequirements=serialized_object_requirements,
            formalMaterialRequirementCount=len(serialized_object_requirements),
            statusLabel=(
                "已形成受控正式材料需求；其余承接条件仍待完成"
                if serialized_object_requirements else
                "待补承接依据"
            ),
            candidateQuantity=None, parentObjectId=None, scrapRate=None,
            scrapExplanation="未知损耗保持空值。现模型允许草稿/版本保留未维护；不等于已有完整发布资格。无损耗依据不能得出毛量/采购量。",
            applicabilityLabel=(
                "正式材料需求已保存；具体Mapping确认状态以服务端Readback为准"
                if object_requirements else
                "物料当前身份可核对，规格/供应方式对本对象及用量适用性仍待工程确认"
                if readback_material else
                "待明确物料后核对规格及供应方式"
            ),
            unitContractLabel="已有工程结果单位只作原量纲展示；同为面积也不代表材料用量映射成立。计数单位与面积不能仅凭换算因子互转。现材料需求服务要求输出单位等于物料基础单位；本次不做任何换算。",
        ))
    preview, preview_error = None, None
    if material_requirements and include_bom_preview:
        try:
            preview = OrderEngineeringClosureService._preview_payload(record)
        except EngineeringCalculationError as error:
            preview_error = dict(code=error.code, message=error.message)
    return dict(
        calculationId=record.pk, calculationNo=record.calculation_no, revision=record.revision,
        lineId=item.pk, lineNo=item.line_no, instanceId=instance.pk, instanceNo=instance.instance_no,
        orderId=item.sales_order_id, orderNo=item.sales_order.order_no,
        orderQuantity=str(item.quantity), orderUomCode=item.uom.code if item.uom_id else None,
        baseline=trace["baselineReference"], source=trace["sourceReference"], rules=trace.get("ruleGraphSnapshot", []),
        currentRoutings=[r for group in routes.values() for r in group],
        finishedAt=record.finished_at.isoformat() if record.finished_at else None,
        inputHash=record.input_hash, resultHash=record.result_hash, ruleGraphHash=record.rule_graph_hash,
        objects=objects, objectCount=len(objects), factCount=len(results),
        materialReferencedCount=sum(o["material"] is not None for o in objects),
        materialRequirementCount=len(material_requirements), operationRequirementCount=len(operation_requirements),
        existingVersions=[dict(id=v.pk, bomCode=v.bom.bom_code, version=v.bom_version,
                               sourceCalculationId=v.source_calculation_id, statusLabel=v.get_status_display()) for v in existing_versions],
        existingManufacturingOutputCount=ProductManufacturingOutput.objects.filter(order_engineering_instance=instance).count(),
        formalRequirementPreview=preview, formalRequirementPreviewError=preview_error,
        candidateCount=(preview or {}).get("rowCount", 0),
        statusLabel=(
            f"已形成{len(material_requirements)}条受控正式材料需求；本次页面读取0写入"
            if material_requirements else
            "待补承接依据；本次页面读取0写入"
        ),
        stages=[
            dict(name="标准材料需求", statusLabel="已有正式需求，需按来源复核" if material_requirements else "未就绪：缺物料/用量/结构映射及R1接续服务"),
            dict(name="工序需求", statusLabel="已有正式需求，需按来源复核" if operation_requirements else "未就绪：需路线版本、工序数量/单位映射及R1接续服务"),
            dict(name="订单BOM草稿", statusLabel=(
                f"已生成{len(existing_versions)}个独立OEI草稿版本；保持只读验证"
                if existing_versions else
                "可复用正式需求预览；保存仍需独立授权"
            ) if preview else "未就绪：现有草稿服务须消费正式材料需求"),
            dict(name="BOM发布", statusLabel=(
                eligibility["message"]
                if not eligibility["formalManufacturingEligible"] else
                "仍须先有合法版本并通过原生命周期、权限及完整性门禁"
            )),
            dict(name="制造定义发布", statusLabel="未就绪：现PMO模型仍要求产品/产品版本、已发布BOM/路线/工程文档；无产品订单的后续边界需单独裁决" if not instance.product_id else "未就绪：须独立核对产品/BOM/路线/文档及发布权"),
        ],
    )


def _source_material_analysis(obj, materials_by_code):
    code = str(obj.get("sourceMaterialCode") or "").strip()
    exact = materials_by_code.get(code, []) if code else []
    if obj.get("material"):
        category = "FORMAL_MATERIAL_BOUND"
    elif len(exact) == 1:
        category = "UNIQUE_EXISTING_REQUIRES_CONFIRMATION"
    elif len(exact) > 1:
        category = "AMBIGUOUS_MATERIAL"
    elif code:
        category = "NON_PURE_MATERIAL_CODE"
    else:
        category = "NO_FORMAL_MATERIAL"
    return {
        "category": category, "sourceCode": code or None,
        "exactFormalMaterialCandidates": [_material(row) for row in exact],
        "matchingPolicy": "仅正式Material.code精确匹配；不做名称或字符串相似绑定。",
        "sourceMatchEvidence": obj.get("sourceMaterialMasterMatch"),
    }


def _fact_family(obj):
    return tuple(sorted(
        (str(row.get("canonicalField") or ""), str(row.get("unit") or ""))
        for row in obj.get("facts", [])
    ))


def _material_group_signature(obj):
    """Exact business grouping key; never a Material binding decision by itself."""
    context = obj.get("businessContext") or {}
    return tuple(str(value or "").strip() for value in (
        obj.get("sourceMaterialCode"), context.get("product"), context.get("component"),
        context.get("materialText"), context.get("sourceSpecification"),
        context.get("finishOrColor"), context.get("processConfiguration"),
        context.get("paintProcess"), context.get("edgeMethod"),
        context.get("visibleCondition"), context.get("hardware"), context.get("glass"),
    )) + (_fact_family(obj),)


def _source_range(source_keys):
    by_sheet = defaultdict(list)
    for source_key in source_keys:
        sheet, _, row = str(source_key or "").rpartition(":")
        by_sheet[sheet or "未标明来源"].append(row or "-")
    labels = []
    for sheet, rows in sorted(by_sheet.items()):
        numeric = sorted(int(row) for row in rows if row.isdigit())
        if len(numeric) == len(rows) and numeric:
            labels.append(f"{sheet}:{numeric[0]}" if len(numeric) == 1 else f"{sheet}:{numeric[0]}–{numeric[-1]}（{len(numeric)}项，非连续行按明细）")
        else:
            labels.append(f"{sheet}:{'、'.join(rows)}")
    return "；".join(labels)


def _fact_options(obj):
    return [{
        "sourceFactCode": row.get("canonicalField"), "name": row.get("displayName"),
        "value": row.get("valueText"), "uom": row.get("unit"),
        "expression": (row.get("quantityBasis") or {}).get("expression"),
        "sourceFactId": row.get("factId"), "sourceDetailId": row.get("detailId"),
        "sourcePath": row.get("sourcePath"),
    } for row in obj.get("facts", [])]


def _recommended_material_fact(obj):
    context = obj.get("businessContext") or {}
    facts = obj.get("facts", [])
    if context.get("product") == "房门":
        fact = next((row for row in facts if row.get("canonicalField") == "W" and row.get("unit") == "m2"), None)
        return fact, (
            "条件推荐：W见光面积与当前按饰面命名的半成品Material同为m2；但W包含见光面/门套表面积，"
            "若Material代表板材实体净面积而非饰面等价面积，必须拆分角色并另定板材Fact。"
        )
    fact = next((row for row in facts if row.get("canonicalField") == "S" and row.get("unit") == "m2"), None)
    return fact, "推荐S部件工程净面积作为板材净用量；Q见光面积保留给油漆/饰面工序，R保留给封边材料。"


def _business_confirmation_package(records, company_id):
    """Compress 71 technical rows into business decisions without approving or writing mappings."""
    scoped = [(record, obj) for record in records for obj in record.get("objects", [])]
    bound_by_signature = defaultdict(dict)
    for _record, obj in scoped:
        material = obj.get("material")
        if material:
            bound_by_signature[_material_group_signature(obj)][material["id"]] = material

    missing_groups = defaultdict(list)
    for record, obj in scoped:
        if not obj.get("material"):
            missing_groups[_material_group_signature(obj)].append((record, obj))

    groups = []
    for index, (signature, rows) in enumerate(sorted(
            missing_groups.items(), key=lambda item: (item[0], item[1][0][1].get("sourceKey", ""))), 1):
        record, first = rows[0]
        context = first.get("businessContext") or {}
        candidates = list(bound_by_signature.get(signature, {}).values())
        if len(candidates) == 1:
            decision = "EXACT_EXISTING_MATERIAL_CANDIDATE"
        elif len(candidates) > 1:
            decision = "MULTIPLE_EXISTING_CANDIDATES"
        else:
            decision = "INSUFFICIENT_BUSINESS_FACTS"
        contains_group_uom = any((obj.get("savedInput") or {}).get("physicalUom") == "组" for _, obj in rows)
        status = (
            "UOM_DEFINITION_REQUIRED" if contains_group_uom else
            "MATERIAL_IDENTITY_REQUIRED" if decision == "MULTIPLE_EXISTING_CANDIDATES" else
            "BUSINESS_FACT_REQUIRED"
        )
        source_keys = [obj.get("sourceKey") for _, obj in rows]
        fact_codes = sorted({
            f"{fact.get('canonicalField')}:{fact.get('unit') or '-'}"
            for _, obj in rows for fact in obj.get("facts", [])
        })
        potential_roles = ["板材Material"]
        if any(any(fact.get("unit") == "m" for fact in obj.get("facts", [])) for _, obj in rows):
            potential_roles.append("封边Material")
        if any("玻璃" in str(obj.get("objectName") or "") for _, obj in rows):
            potential_roles.append("玻璃Material（规格/数量/UOM待补）")
        if any((obj.get("businessContext") or {}).get("hardware") for _, obj in rows):
            potential_roles.append("五金Material（结构关系待核）")
        groups.append({
            "groupNo": f"MRG-{index:03d}", "objectCount": len(rows),
            "objectNos": [obj.get("objectNo") for _, obj in rows], "sourceKeys": source_keys,
            "sourceKeyRange": _source_range(source_keys),
            "sourceCode": first.get("sourceMaterialCode"),
            "product": context.get("product"), "component": context.get("component"),
            "materialText": context.get("materialText"), "sourceSpecification": context.get("sourceSpecification"),
            "finishOrColor": context.get("finishOrColor"),
            "processConfiguration": context.get("processConfiguration"), "paintProcess": context.get("paintProcess"),
            "edgeMethod": context.get("edgeMethod"), "visibleCondition": context.get("visibleCondition"),
            "hardware": context.get("hardware"), "glass": context.get("glass"),
            "quantityFactFamily": fact_codes, "materialDecision": decision,
            "existingMaterialCandidates": candidates,
            "decisionBasis": (
                "同一完整业务签名已有多个正式Material引用，必须由业务人员选择；不按名称或编码前缀自动绑定。"
                if decision == "MULTIPLE_EXISTING_CANDIDATES" else
                "来源码是材料＋工艺组合，且来源没有材料名称/规格等足够身份事实；既不能唯一匹配，也不能证明企业无此Material。"
            ),
            "currentStatus": status, "requiredConfirmers": ["工程/BOM负责人", "物料数据治理"],
            "potentialRequirementRoles": potential_roles,
            "sourceFactCodeCandidate": "S" if any(code == "S:m2" for code in fact_codes) else None,
            "quantityBasisCandidate": "PER_SALES_ITEM_UNIT", "salesItemMultiplierCandidate": "APPLY_ONCE",
            "scrapRateCandidate": None,
            "question": (
                "请在列出的正式Material中选择本组实际使用者，并确认板材、饰面、封边是否拆成多条需求。"
                if candidates else
                "请补充本组实际材料名称、规格/厚度、板材/饰面/封边角色及供给方式；现有工艺码不能代替Material身份。"
            ),
        })

    cards = []
    for index, (record, obj) in enumerate(sorted(
            ((record, obj) for record, obj in scoped if obj.get("material")),
            key=lambda item: item[1].get("objectNo", "")), 1):
        material = obj["material"]
        recommended, reason = _recommended_material_fact(obj)
        is_door = (obj.get("businessContext") or {}).get("product") == "房门"
        multiplier = Decimal(str(record.get("orderQuantity") or "0"))
        projected = None
        if recommended:
            try:
                projected = Decimal(str(recommended.get("valueText"))) * multiplier
            except InvalidOperation:
                projected = None
        cards.append({
            "mappingNo": f"MRC-{index:03d}", "designItem": {
                "id": obj.get("id"), "objectNo": obj.get("objectNo"), "name": obj.get("objectName"),
                "sourceKey": obj.get("sourceKey"),
            },
            "productComponent": obj.get("businessContext"), "material": material,
            "salesOrderItem": {"lineId": record.get("lineId"), "lineNo": record.get("lineNo"),
                               "quantity": record.get("orderQuantity"), "uom": record.get("orderUomCode")},
            "savedDerivedFacts": _fact_options(obj),
            "recommendedQuantitySource": ({
                "type": "SAVED_DERIVED_FACT", "sourceFactCode": recommended.get("canonicalField"),
                "name": recommended.get("displayName"), "savedValue": recommended.get("valueText"),
                "uom": recommended.get("unit"), "sourceFactId": recommended.get("factId"),
                "sourceDetailId": recommended.get("detailId"), "sourcePath": recommended.get("sourcePath"),
            } if recommended else None),
            "recommendedQuantityBasis": "PER_SALES_ITEM_UNIT", "salesItemMultiplier": "APPLY_ONCE",
            "multiplicationPath": (
                f"已保存Fact {recommended.get('valueText')} {recommended.get('unit')}（表达式已含对象数量一次）"
                f" × SalesOrderItem.quantity {record.get('orderQuantity')}（只乘一次）"
                f" = {projected} {recommended.get('unit')}" if recommended and projected is not None else
                "缺少可推荐的同UOM已保存Fact；不得默认乘对象数量或订单数量。"
            ),
            "recommendedReason": reason, "scrapRate": None,
            "scrapDecision": "待业务确认；净量、损耗率和含损耗量必须分开，当前不代填0。",
            "itemRole": "MAIN_MATERIAL", "requirementType": "MANUFACTURING",
            "supplyType": "PRODUCTION" if material.get("produced") else "PURCHASE" if material.get("purchased") else "PENDING_CONFIRMATION",
            "specification": material.get("specification"), "outputUom": (material.get("baseUnit") or {}).get("code"),
            "mappingVersionSuggestion": "V1-CANDIDATE", "currentStatus": "QUANTITY_RULE_REQUIRED" if is_door else "READY_FOR_BUSINESS_CONFIRMATION",
            "requiredConfirmers": ["工程/BOM负责人", "物料数据治理"],
            "question": (
                "该Material代表板材实体净面积，还是包含双面/门套的饰面等价面积？若是板材实体，W不能直接作为唯一数量源，需拆分并补板材净面积Fact。"
                if is_door else
                "确认以S部件工程净面积作为板材净量，Q只用于油漆/饰面工序、R另行形成封边材料需求；并确认损耗率。"
            ),
        })

    checklist = [{
        "mappingNo": group["groupNo"], "appliesTo": f"{group['product']}/{group['component']}（{group['objectCount']}项）",
        "sourceFactCode": group["sourceFactCodeCandidate"], "material": None, "outputUom": None,
        "quantityBasis": group["quantityBasisCandidate"], "quantitySource": "SAVED_DERIVED_FACT_CANDIDATE",
        "salesItemMultiplier": group["salesItemMultiplierCandidate"], "scrapRate": None,
        "itemRole": None, "requirementType": None, "supplyType": None,
        "specification": group["sourceSpecification"] or None, "mappingVersionSuggestion": "V1-CANDIDATE",
        "currentStatus": group["currentStatus"], "requiredConfirmers": group["requiredConfirmers"],
        "question": group["question"],
    } for group in groups] + [{
        "mappingNo": card["mappingNo"], "appliesTo": card["designItem"]["objectNo"],
        "sourceFactCode": (card.get("recommendedQuantitySource") or {}).get("sourceFactCode"),
        "material": card["material"], "outputUom": card["outputUom"],
        "quantityBasis": card["recommendedQuantityBasis"], "quantitySource": "SAVED_DERIVED_FACT",
        "salesItemMultiplier": card["salesItemMultiplier"], "scrapRate": card["scrapRate"],
        "itemRole": card["itemRole"], "requirementType": card["requirementType"], "supplyType": card["supplyType"],
        "specification": card["specification"], "mappingVersionSuggestion": card["mappingVersionSuggestion"],
        "currentStatus": card["currentStatus"], "requiredConfirmers": card["requiredConfirmers"],
        "question": card["question"],
    } for card in cards]
    status_counts = {status: sum(row["currentStatus"] == status for row in checklist)
                     for status in BUSINESS_CONFIRMATION_STATUSES}
    decision_counts = {status: sum(group["materialDecision"] == status for group in groups) for status in (
        "EXACT_EXISTING_MATERIAL_CANDIDATE", "MULTIPLE_EXISTING_CANDIDATES",
        "NO_EXISTING_MATERIAL_CONFIRMED", "INSUFFICIENT_BUSINESS_FACTS",
    )}
    group_uom_objects = [obj for _record, obj in scoped if (obj.get("savedInput") or {}).get("physicalUom") == "组"]
    glass_named = [obj for _record, obj in scoped if "玻璃" in str(obj.get("objectName") or "")]
    active_materials = Material.objects.filter(company_id=company_id, is_active=True)
    return {
        "packageCode": "PCE-SO202609180003-MATERIAL-MAPPING-BUSINESS-CONFIRMATION-PACK-V1",
        "modeLabel": "业务确认准备；不是批准、不是Mapping、不是Material Requirement",
        "objectCount": len(scoped), "missingMaterialObjectCount": sum(len(rows) for rows in missing_groups.values()),
        "missingMaterialBusinessGroupCount": len(groups), "formalMaterialMappingCardCount": len(cards),
        "decisionUnitCount": len(checklist), "coverageClosed": sum(len(rows) for rows in missing_groups.values()) + len(cards) == len(scoped),
        "groups": groups, "mappingCards": cards, "mappingChecklist": checklist,
        "confirmationStatusCounts": status_counts, "materialDecisionCounts": decision_counts,
        "materialMasterSearch": {
            "companyId": company_id, "activeMaterialCount": active_materials.count(),
            "activeConfirmedMaterialCount": active_materials.filter(unit_status="confirmed").count(),
            "searchFields": ["正式工程引用", "Material.code", "Material.name", "specification", "category", "baseUom", "materialType", "produced/purchased"],
            "bindingPolicy": "只有完整业务签名下既有正式工程引用可列为候选；名称、包含关系、编码前缀和工艺词不得自动形成Material绑定。",
        },
        "quantityBoundary": {
            "recommendedBasis": "PER_SALES_ITEM_UNIT", "salesItemMultiplier": "APPLY_ONCE",
            "proof": "已保存DerivedFact表达式已经使用ProductDesignItem对象数量；Mapping层不再乘对象数量，只按SalesOrderItem.quantity乘一次。",
        },
        "uomQuestion": {
            "objectNo": group_uom_objects[0].get("objectNo") if len(group_uom_objects) == 1 else None,
            "sourceKey": group_uom_objects[0].get("sourceKey") if len(group_uom_objects) == 1 else None,
            "sourceTextUom": "组", "formalUomExists": UnitOfMeasure.objects.filter(
                company_id=company_id, is_active=True,
            ).filter(Q(code="组") | Q(name="组")).exists(),
            "question": "这里的‘1组’在企业业务中具体表示什么？",
            "boundary": "‘组’是设计对象物理单位，不等于材料需求单位；即使以后建立‘组’，材料需求仍按Material自身正式UOM计算。",
        },
        "hardwareAndGlass": {
            "structuredHardwareObjectCount": sum(bool((obj.get("businessContext") or {}).get("hardware")) for _record, obj in scoped),
            "structuredGlassObjectCount": sum(bool((obj.get("businessContext") or {}).get("glass")) for _record, obj in scoped),
            "glassNamedObjectCount": len(glass_named), "glassNamedObjectNos": [obj.get("objectNo") for obj in glass_named],
            "formalMaterialReferenceCount": 0, "structuredQuantityCount": 0, "structuredUomCount": 0,
            "decision": "当前没有可直接复用的结构化五金/玻璃Material关系、数量和UOM；玻璃柜门名称不能自动生成玻璃需求，须补规格与构成关系。",
        },
        "processBoundary": {
            "sourceCodes": sorted({obj.get("sourceMaterialCode") for _record, obj in scoped if obj.get("sourceMaterialCode")}),
            "material": "企业正式Material主数据；不能由QSFB/BTKF/GT/SM或油漆词替代。",
            "paintingProcess": "清水封闭、清水开放、半透等是表面工艺/饰面条件。",
            "operation": "Q见光面积可作为油漆/饰面工序候选工程量，不自动成为板材需求。",
            "routing": "QSFB/FM、BTKF/GT、BTKF/SM是工艺路线/配置候选，不是Material身份。",
        },
        "automaticMaterialBindingCount": 0, "mappingWriteCount": 0, "requirementWriteCount": 0,
        "databaseBusinessWriteCount": 0,
    }


def _candidate_from_mapping(*, record, obj, mapping, materials_by_id):
    missing = list(mapping.get("missingConditions") or [])
    material = materials_by_id.get(mapping.get("materialId"))
    facts = [row for row in obj["facts"] if row.get("canonicalField") == mapping.get("sourceFactCode")]
    if not material or not material.is_active:
        missing.append("FORMAL_MATERIAL_REQUIRED")
    elif not material.base_uom_id or not material.base_uom or not material.base_uom.is_active:
        missing.append("MATERIAL_BASE_UOM_REQUIRED")
    elif str(mapping.get("outputUom") or "") != material.base_uom.code:
        missing.append("OUTPUT_UOM_MUST_EQUAL_MATERIAL_BASE_UOM")
    if len(facts) != 1:
        missing.append("SAVED_SOURCE_FACT_MUST_BE_UNIQUE")
    elif str(facts[0].get("unit") or "") != str(mapping.get("outputUom") or ""):
        missing.append("SOURCE_FACT_UOM_CONVERSION_NOT_ALLOWED")
    net, gross = None, None
    if not missing:
        try:
            value = Decimal(facts[0]["valueText"])
            if mapping["quantityBasis"] == "PER_SALES_ITEM_UNIT":
                value *= Decimal(record["orderQuantity"])
            scale = int(mapping["precision"]["outputScale"])
            quantum = Decimal("1").scaleb(-scale)
            rounding = ROUNDING_MODES.get(mapping["rounding"])
            if rounding is None:
                missing.append("ROUNDING_MODE_NOT_SUPPORTED")
            else:
                net = value.quantize(quantum, rounding=rounding)
                if net <= 0:
                    missing.append("NET_QUANTITY_MUST_BE_POSITIVE")
                elif mapping.get("scrapRate") is not None:
                    gross = (net / (Decimal("1") - Decimal(str(mapping["scrapRate"])))).quantize(
                        quantum, rounding=rounding)
        except (InvalidOperation, TypeError, ValueError, KeyError):
            missing.append("SAVED_SOURCE_FACT_DECIMAL_REQUIRED")
    evidence = {
        "calculationResultHash": record["resultHash"],
        "calculationRuleGraphHash": record["ruleGraphHash"],
        "baselineItemId": obj["baselineItemId"],
        "sourceFactId": facts[0].get("factId") if len(facts) == 1 else None,
        "sourceDetailId": facts[0].get("detailId") if len(facts) == 1 else None,
        "sourcePath": facts[0].get("sourcePath") if len(facts) == 1 else None,
        "mappingAuditIdentity": mapping["auditIdentity"],
        "readPolicy": "读取已保存事实；不重新执行核算公式。",
    }
    return {
        "salesOrder": {"id": record["orderId"], "orderNo": record["orderNo"]},
        "salesOrderItem": {"id": record["lineId"], "lineNo": record["lineNo"]},
        "oei": {"id": record["instanceId"], "instanceNo": record["instanceNo"]},
        "calculation": {"id": record["calculationId"], "calculationNo": record["calculationNo"]},
        "designItem": {"id": obj["id"], "objectNo": obj["objectNo"], "name": obj["objectName"]},
        "sourceFact": facts[0] if len(facts) == 1 else None,
        "material": _material(material), "materialCode": material.code if material else None,
        "specification": mapping.get("orderSpecification"),
        "netQuantity": str(net) if net is not None else None,
        "uom": mapping.get("outputUom"), "quantityBasis": mapping.get("quantityBasis"),
        "scrapRate": str(mapping["scrapRate"]) if mapping.get("scrapRate") is not None else None,
        "grossQuantity": str(gross) if gross is not None else None,
        "itemRole": mapping.get("itemRole"), "requirementType": mapping.get("requirementType"),
        "supplyType": mapping.get("supplyType"), "mappingRule": mapping.get("code"),
        "mappingVersion": mapping.get("version"), "evidence": evidence,
        "status": "READY_FOR_REQUIREMENT" if not missing else "MISSING_QUANTITY_CONTRACT",
        "missingConditions": sorted(set(missing)),
    }


def _apply_formal_confirmation_readback(package, records, mappings):
    """Mark only exact released Mapping + formal Requirement pairs as confirmed."""
    requirements_by_object = {
        obj.get("objectNo"): list(obj.get("formalMaterialRequirements") or [])
        for record in records for obj in record.get("objects", [])
    }
    mappings_by_object = defaultdict(list)
    for mapping in mappings:
        object_no = (mapping.get("applicabilityScope") or {}).get("designItemNo")
        if object_no:
            mappings_by_object[str(object_no)].append(mapping)
    cards = package.setdefault("mappingCards", [])
    scoped_objects = {
        str(obj.get("objectNo") or ""): (record, obj)
        for record in records for obj in record.get("objects", [])
    }
    confirmed_pairs = []
    for object_no, requirements in requirements_by_object.items():
        exact_pairs = [
            (mapping, requirement)
            for mapping in mappings_by_object.get(object_no, [])
            for requirement in requirements
            if mapping.get("contractStatus") == "READY"
            and requirement.get("mappingRuleId") == mapping.get("id")
            and requirement.get("materialId") == mapping.get("materialId")
        ]
        if len(exact_pairs) != 1 or object_no not in scoped_objects:
            continue
        mapping, requirement = exact_pairs[0]
        record, obj = scoped_objects[object_no]
        source_fact = next((
            row for row in obj.get("facts", [])
            if row.get("factId") == requirement.get("sourceFactId")
        ), None)
        material = requirement.get("material") or {
            "id": requirement.get("materialId"),
            "code": requirement.get("materialCode"),
            "name": requirement.get("materialName"),
        }
        card = next((row for row in cards if str((row.get("designItem") or {}).get("objectNo") or "") == object_no), None)
        if card is None:
            card = {
                "mappingNo": requirement.get("mappingNo") or mapping.get("mappingNo") or mapping.get("code"),
                "designItem": {
                    "id": obj.get("id"), "objectNo": obj.get("objectNo"),
                    "name": obj.get("objectName"), "sourceKey": obj.get("sourceKey"),
                },
                "productComponent": obj.get("businessContext"),
                "material": material,
                "salesOrderItem": {
                    "lineId": record.get("lineId"), "lineNo": record.get("lineNo"),
                    "quantity": record.get("orderQuantity"), "uom": record.get("orderUomCode"),
                },
                "savedDerivedFacts": _fact_options(obj),
                "recommendedQuantitySource": ({
                    "type": "SAVED_DERIVED_FACT", "sourceFactCode": source_fact.get("canonicalField"),
                    "name": source_fact.get("displayName"), "savedValue": source_fact.get("valueText"),
                    "uom": source_fact.get("unit"), "sourceFactId": source_fact.get("factId"),
                    "sourceDetailId": source_fact.get("detailId"), "sourcePath": source_fact.get("sourcePath"),
                } if source_fact else None),
                "recommendedQuantityBasis": requirement.get("quantityBasis"),
                "salesItemMultiplier": requirement.get("salesItemMultiplier"),
                "multiplicationPath": (
                    f"正式Requirement #{requirement.get('id')}读取已保存净需求"
                    f" {requirement.get('netQuantity')} {requirement.get('uom')}；本页不重新计算。"
                ),
                "scrapRate": requirement.get("scrapRate"),
                "itemRole": requirement.get("itemRole"),
                "requirementType": requirement.get("requirementType"),
                "supplyType": requirement.get("supplyType"),
                "specification": material.get("specification"),
                "outputUom": requirement.get("uom"),
                "requiredConfirmers": [requirement.get("responsibilitySource") or "工程/BOM承接确认"],
            }
            cards.append(card)
        card["mappingNo"] = requirement.get("mappingNo") or mapping.get("mappingNo") or card.get("mappingNo")
        card["material"] = material
        card["savedDerivedFacts"] = _fact_options(obj)
        card["recommendedQuantitySource"] = ({
            "type": "SAVED_DERIVED_FACT", "sourceFactCode": source_fact.get("canonicalField"),
            "name": source_fact.get("displayName"), "savedValue": source_fact.get("valueText"),
            "uom": source_fact.get("unit"), "sourceFactId": source_fact.get("factId"),
            "sourceDetailId": source_fact.get("detailId"), "sourcePath": source_fact.get("sourcePath"),
        } if source_fact else None)
        card["recommendedQuantityBasis"] = requirement.get("quantityBasis")
        card["salesItemMultiplier"] = requirement.get("salesItemMultiplier")
        card["multiplicationPath"] = (
            f"正式Requirement #{requirement.get('id')}读取已保存净需求"
            f" {requirement.get('netQuantity')} {requirement.get('uom')}；本页不重新计算。"
        )
        card["scrapRate"] = requirement.get("scrapRate")
        card["itemRole"] = requirement.get("itemRole")
        card["requirementType"] = requirement.get("requirementType")
        card["supplyType"] = requirement.get("supplyType")
        card["specification"] = material.get("specification")
        card["outputUom"] = requirement.get("uom")
        card["requiredConfirmers"] = [requirement.get("responsibilitySource") or "工程/BOM承接确认"]
        card["currentStatus"] = "CONFIRMED"
        card["acceptanceStatus"] = "CONFIRMED"
        card["acceptanceStatusLabel"] = "CONFIRMED（已确认）"
        card["mappingVersionSuggestion"] = mapping.get("mappingVersion")
        card["confirmedMapping"] = mapping
        card["formalRequirement"] = requirement
        card["sourceExternalIdentity"] = (
            requirement.get("sourceExternalIdentity") or mapping.get("sourceExternalIdentity")
        )
        card["question"] = "已按正式Mapping与Requirement的服务端绑定确认；不得扩展到其他对象或其他材料角色。"
        confirmed_pairs.append((object_no, mapping, requirement))

    group_checklist = [
        row for row in package.get("mappingChecklist", [])
        if str(row.get("mappingNo") or "").startswith("MRG-")
    ]
    card_checklist = [{
        "mappingNo": card.get("mappingNo"),
        "appliesTo": (card.get("designItem") or {}).get("objectNo"),
        "sourceFactCode": (card.get("recommendedQuantitySource") or {}).get("sourceFactCode"),
        "material": card.get("material"), "outputUom": card.get("outputUom"),
        "quantityBasis": card.get("recommendedQuantityBasis"), "quantitySource": "SAVED_DERIVED_FACT",
        "salesItemMultiplier": card.get("salesItemMultiplier"), "scrapRate": card.get("scrapRate"),
        "itemRole": card.get("itemRole"), "requirementType": card.get("requirementType"),
        "supplyType": card.get("supplyType"), "specification": card.get("specification"),
        "mappingVersionSuggestion": card.get("mappingVersionSuggestion"),
        "currentStatus": card.get("currentStatus"), "requiredConfirmers": card.get("requiredConfirmers"),
        "question": card.get("question"), "formalRequirement": card.get("formalRequirement"),
        "confirmedMapping": card.get("confirmedMapping"),
        "sourceExternalIdentity": card.get("sourceExternalIdentity"),
        "acceptanceStatus": card.get("acceptanceStatus"),
        "acceptanceStatusLabel": card.get("acceptanceStatusLabel"),
    } for card in cards]
    checklist = group_checklist + card_checklist
    package["mappingChecklist"] = checklist
    confirmed_count = len(confirmed_pairs)
    package["confirmationStatusCounts"] = {
        status: sum(row.get("currentStatus") == status for row in checklist)
        for status in BUSINESS_CONFIRMATION_STATUSES
    }
    package["confirmedMappingCount"] = confirmed_count
    package["confirmedRequirementCount"] = confirmed_count
    package["pendingDecisionUnitCount"] = len(checklist) - confirmed_count
    package["decisionUnitCount"] = len(checklist)
    package["formalMaterialMappingCardCount"] = len(cards)
    package["coverageClosed"] = (
        sum(group.get("objectCount", 0) for group in package.get("groups", [])) + len(cards)
        == package.get("objectCount")
    )
    package["modeLabel"] = (
        f"原{len(checklist)}个业务确认单元中{confirmed_count}个已按明确授权确认；"
        f"其余{len(checklist) - confirmed_count}个继续待确认，不批量批准。"
    )
    package["mappingReadbackCount"] = confirmed_count
    package["requirementReadbackCount"] = package["confirmedRequirementCount"]
    package["mappingWriteCount"] = 0
    package["requirementWriteCount"] = 0
    package["databaseBusinessWriteCount"] = 0
    return package


def material_requirement_preview(*, records, mapping_rules, company_id):
    """Build a read-only R1 preview from saved facts and exact approved mappings."""
    formal_requirement_rows = [
        {
            **requirement,
            "designItemNo": obj.get("objectNo"),
            "designItemName": obj.get("objectName"),
            "calculationId": record.get("calculationId"),
            "calculationNo": record.get("calculationNo"),
            "lineNo": record.get("lineNo"),
        }
        for record in records for obj in record.get("objects", [])
        for requirement in obj.get("formalMaterialRequirements", [])
    ]
    mapping_candidates = [contract for contract in (_mapping_contract(rule) for rule in mapping_rules) if contract]
    mappings = [row for row in mapping_candidates if row["effectiveScope"]["currentEffective"]]
    source_codes = {
        obj.get("sourceMaterialCode") for record in records for obj in record["objects"]
        if obj.get("sourceMaterialCode")
    }
    materials_by_code = defaultdict(list)
    for material in Material.objects.filter(company_id=company_id, is_active=True, code__in=source_codes).select_related("base_uom"):
        materials_by_code[material.code].append(material)
    mapping_material_ids = {row.get("materialId") for row in mappings if row.get("materialId")}
    materials_by_id = {
        row.pk: row for row in Material.objects.filter(
            company_id=company_id, pk__in=mapping_material_ids,
        ).select_related("base_uom")
    }
    classifications, candidates = [], []
    for record in records:
        for obj in record["objects"]:
            context = {
                **(obj.get("savedInput") or {}),
                "orderId": record["orderId"], "orderNo": record["orderNo"],
                "salesOrderItemId": record["lineId"], "designItemId": obj["id"],
                "designItemNo": obj["objectNo"], "sourceMaterialCode": obj.get("sourceMaterialCode"),
            }
            source_analysis = _source_material_analysis(obj, materials_by_code)
            applicable = [row for row in mappings if _applicable(row, context)]
            object_candidates = [
                _candidate_from_mapping(record=record, obj=obj, mapping=row, materials_by_id=materials_by_id)
                for row in applicable
            ]
            exact_confirmations = [
                (mapping, requirement)
                for mapping in applicable
                for requirement in obj.get("formalMaterialRequirements", [])
                if mapping.get("contractStatus") == "READY"
                and requirement.get("mappingRuleId") == mapping.get("id")
                and requirement.get("materialId") == mapping.get("materialId")
            ]
            if len(exact_confirmations) == 1:
                status = "CONFIRMED"
                missing = []
            elif obj.get("formalMaterialRequirementCount"):
                status = "READY_FOR_REQUIREMENT"
                missing = []
            elif source_analysis["category"] == "AMBIGUOUS_MATERIAL":
                status = "AMBIGUOUS_MATERIAL"
                missing = ["MULTIPLE_EXACT_FORMAL_MATERIAL_CANDIDATES_REQUIRE_CONFIRMATION"]
            elif not obj.get("material") and not applicable:
                status = "MISSING_MATERIAL"
                missing = ["FORMAL_MATERIAL_REFERENCE_OR_APPROVED_MAPPING_REQUIRED"]
            elif not applicable:
                status = "MISSING_MAPPING"
                missing = ["RELEASED_MATERIAL_REQUIREMENT_MAPPING_REQUIRED"]
            elif any(row["status"] != "READY_FOR_REQUIREMENT" for row in object_candidates):
                flat = {condition for row in object_candidates for condition in row["missingConditions"]}
                status = "MISSING_UOM" if flat & {
                    "MATERIAL_BASE_UOM_REQUIRED", "OUTPUT_UOM_MUST_EQUAL_MATERIAL_BASE_UOM",
                    "SOURCE_FACT_UOM_CONVERSION_NOT_ALLOWED",
                } else "MISSING_QUANTITY_CONTRACT"
                missing = sorted(flat)
            else:
                status = "READY_FOR_REQUIREMENT"
                missing = []
            if status != "CONFIRMED":
                candidates.extend(row for row in object_candidates if row["status"] == "READY_FOR_REQUIREMENT")
            confirmed_mapping = exact_confirmations[0][0] if len(exact_confirmations) == 1 else None
            confirmed_requirement = exact_confirmations[0][1] if len(exact_confirmations) == 1 else None
            classifications.append({
                "designItemId": obj["id"], "objectNo": obj["objectNo"], "objectName": obj["objectName"],
                "sourceKey": obj["sourceKey"], "status": status, "statusLabel": {
                    "CONFIRMED": "CONFIRMED（已确认）",
                    "READY_FOR_REQUIREMENT": "可形成材料需求候选（仍未保存）",
                    "MISSING_MATERIAL": "缺正式Material",
                    "MISSING_MAPPING": "已有Material，缺正式Mapping",
                    "MISSING_UOM": "缺正式或同量纲输出UOM",
                    "AMBIGUOUS_MATERIAL": "多个正式Material候选，需人工确认",
                    "MISSING_QUANTITY_CONTRACT": "Mapping数量合同不完整",
                    "NOT_APPLICABLE": "经正式规则确认不适用材料需求",
                }[status],
                "material": (
                    (confirmed_requirement or {}).get("material")
                    or obj.get("material")
                ),
                "acceptanceStatus": "CONFIRMED" if confirmed_requirement else None,
                "acceptanceStatusLabel": "CONFIRMED（已确认）" if confirmed_requirement else None,
                "formalRequirementIds": [
                    row.get("id") for row in obj.get("formalMaterialRequirements", [])
                ],
                "confirmedMappingIds": [confirmed_mapping.get("id")] if confirmed_mapping else [],
                "sourceExternalIdentity": (
                    (confirmed_requirement or {}).get("sourceExternalIdentity")
                    or (confirmed_mapping or {}).get("sourceExternalIdentity")
                ),
                "physicalUnit": obj.get("currentUnit"),
                "sourceMaterialAnalysis": source_analysis,
                "applicableMappingIds": [row["id"] for row in applicable],
                "candidateCount": (
                    0 if confirmed_requirement else
                    sum(row["status"] == "READY_FOR_REQUIREMENT" for row in object_candidates)
                ),
                "missingConditions": missing,
            })
    counts = {status: sum(row["status"] == status for row in classifications) for status in MATERIAL_PREVIEW_STATUSES}
    source_counts = {
        key: sum(row["sourceMaterialAnalysis"]["category"] == key for row in classifications)
        for key in (
            "UNIQUE_EXISTING_REQUIRES_CONFIRMATION", "AMBIGUOUS_MATERIAL",
            "NO_FORMAL_MATERIAL", "NON_PURE_MATERIAL_CODE", "FORMAL_MATERIAL_BOUND",
        )
    }
    object_count = len(classifications)
    business_confirmation_package = _apply_formal_confirmation_readback(
        _business_confirmation_package(records, company_id), records, mappings,
    )
    confirmed_requirements = {
        (card.get("formalRequirement") or {}).get("id"): card
        for card in business_confirmation_package.get("mappingCards", [])
        if card.get("currentStatus") == "CONFIRMED" and (card.get("formalRequirement") or {}).get("id")
    }
    for requirement in formal_requirement_rows:
        card = confirmed_requirements.get(requirement.get("id"))
        if card:
            requirement["acceptanceStatus"] = card.get("acceptanceStatus")
            requirement["acceptanceStatusLabel"] = card.get("acceptanceStatusLabel")
            requirement["confirmedMappingId"] = (card.get("confirmedMapping") or {}).get("id")
            requirement["sourceExternalIdentity"] = card.get("sourceExternalIdentity")
    return {
        "previewCode": "PCE-R1-MATERIAL-REQUIREMENT-NO-RECALC-PREVIEW-V1",
        "modeLabel": "R1已保存事实＋已发布Mapping的只读候选；不是正式材料清单",
        "mappingContract": MATERIAL_REQUIREMENT_MAPPING_CONTRACT,
        "mappingCandidates": mapping_candidates,
        "approvedMappings": mappings, "approvedMappingCount": len(mappings),
        "classifications": classifications, "classificationCounts": counts,
        "classificationClosed": sum(counts.values()) == object_count,
        "objectCount": object_count, "candidateRows": candidates, "candidateCount": len(candidates),
        "formalRequirementRows": formal_requirement_rows,
        "formalRequirementObjectCount": sum(
            bool(obj.get("formalMaterialRequirementCount"))
            for record in records for obj in record.get("objects", [])
        ),
        "metrics": {
            "formalMaterialReferencedCount": sum(bool(row.get("material")) for row in classifications),
            "missingMaterialCount": sum(not row.get("material") for row in classifications),
            "physicalUomCompleteCount": sum(bool(row.get("physicalUnit")) for row in classifications),
            "physicalUomMissingCount": sum(not row.get("physicalUnit") for row in classifications),
            "sourceMaterialAnalysisCounts": source_counts,
        },
        "businessConfirmationPackage": business_confirmation_package,
        "calculationReexecuted": False, "implicitUomConversionCount": 0,
        "databaseBusinessWriteCount": 0,
    }


def order_bom_handoff(*, user, order_id=None, calculation_id=None, include_bom_preview=True):
    company_id = user.company_id
    EngineeringCalculationService._authorize(user=user, action_code="production.engineering.calculation.view", company_id=company_id)
    order_id, calculation_id = positive_id(order_id), positive_id(calculation_id)
    query = EngineeringCalculationRecord.objects.filter(company_id=company_id, scope="order_engineering", status="completed").select_related(
        "sales_order_item__sales_order", "engineering_instance", "source_record")
    catalog = {}
    for record in query:
        decision = AuthorizationService.decide(user=user, action_code="production.engineering.calculation.view", organization_id=company_id,
                                               business_object={"organizationId": company_id, "engineeringCalculationId": record.pk})
        if decision.get("allowed") and record.sales_order_item_id:
            order = record.sales_order_item.sales_order
            if order.company_id == company_id:
                catalog[order.pk] = dict(
                    id=order.pk,
                    orderNo=order.order_no,
                    businessPurpose=order_business_purpose(order),
                )
    if calculation_id:
        record = query.filter(pk=calculation_id).first()
        if not record or not record.sales_order_item_id:
            raise HandoffReadError("HANDOFF_NOT_FOUND", "当前范围没有该已完成正式核算。", 404)
        if order_id and order_id != record.sales_order_item.sales_order_id:
            raise HandoffReadError("HANDOFF_CONTEXT_MISMATCH", "核算不属于请求的订单，不自动改换订单。", 409)
        order_id = record.sales_order_item.sales_order_id
    if order_id and order_id not in catalog:
        raise HandoffReadError("HANDOFF_NOT_FOUND", "当前授权范围没有该订单的已完成正式核算。", 404)
    released_rules = list(EngineeringRuleDefinition.objects.filter(
        company_id=company_id, status="released",
    ).order_by("rule_code", "version", "pk"))
    order_records = []
    if order_id:
        for record in query.filter(sales_order_item__sales_order_id=order_id).order_by("sales_order_item__line_no", "revision", "pk"):
            EngineeringCalculationService._authorize(user=user, action_code="production.engineering.calculation.view", company_id=company_id, object_id=record.pk)
            order_records.append(record_handoff(record, company_id, include_bom_preview=include_bom_preview))
    records = (
        [row for row in order_records if row["calculationId"] == calculation_id]
        if calculation_id else order_records
    )
    permissions = []
    for label, action in [("查看核算承接", "production.engineering.calculation.view"), ("维护BOM", "production.master_data.bom.maintain"),
                          ("正式发布BOM版本", "pde.bom_version.release"), ("发布制造定义", "production.engineering.release")]:
        decision = AuthorizationService.decide(user=user, action_code=action, organization_id=company_id, business_object={"organizationId": company_id})
        permissions.append(dict(name=label, allowed=decision.get("allowed", False),
                                statusLabel="权限校验允许（不代表本轮获准执行）" if decision.get("allowed") else "当前身份无此动作权限",
                                reason=decision.get("reason")))
    rules = []
    for rule in released_rules:
        domains = sorted({o.get("resultDomain", "DERIVED_FACT") for o in rule.specification.get("outputs", [])})
        if any(d in {"MATERIAL_REQUIREMENT", "OPERATION_REQUIREMENT"} for d in domains):
            rules.append(dict(id=rule.pk, code=rule.rule_code, version=rule.version, domains=domains,
                              applicability=rule.specification.get("applicability", {})))
    material_preview = material_requirement_preview(
        records=records, mapping_rules=released_rules, company_id=company_id,
    )
    selected_order = SalesOrder.objects.filter(pk=order_id, company_id=company_id).first() if order_id else None
    gate = bom_handoff_gate(
        records=order_records, selected_order=selected_order, company_id=company_id,
        target_calculation_id=calculation_id,
    )
    formal_requirement_count = gate["formalEngineeringMaterialRequirementCount"]
    material_preview["formalEngineeringMaterialRequirementCount"] = formal_requirement_count
    material_preview["bomGate"] = {
        **gate,
        "blocked": bool(gate["missingConditions"]),
        "evidence": "Preview候选不作为正式EngineeringMaterialRequirement；原BOM服务只消费正式需求。",
    }
    selected_order_projection = catalog.get(order_id) if order_id else None
    return dict(factSource="server", modeLabel="承接预览，未保存BOM或正式需求", checkedAt=datetime.now().astimezone().isoformat(),
                companyId=company_id, account=user.username, orders=list(catalog.values()), selectedOrderId=order_id,
                selectedOrderNo=catalog.get(order_id, {}).get("orderNo"), selectedOrder=selected_order_projection,
                requestedCalculationId=calculation_id,
                records=records, permissions=permissions, currentRequirementRuleCandidates=rules,
                materialRequirementPreview=material_preview, bomHandoffStatus=gate,
                objectCount=sum(r["objectCount"] for r in records), factCount=sum(r["factCount"] for r in records),
                candidateCount=sum(r["candidateCount"] for r in records),
                authority="已保存CalculationRecord/Detail/DerivedFact＋原正式需求/BOM关系；物料/路线标明当前核对", businessWriteCount=0)
