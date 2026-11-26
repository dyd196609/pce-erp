"""A1.8 DO-3 formal engineering-calculation persistence boundary."""

from __future__ import annotations
from .formal_manufacturing_eligibility_service import FormalManufacturingEligibilityService

import hashlib
import os
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from masterdata.models import CodeRule, ExternalIdentity, Material, UnitOfMeasure
from sales.models import SalesOrder, SalesOrderItem, SalesOrderItemEngineeringAttribute
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord, Process

from .engineering_rule_foundation import (
    EngineeringRuleError,
    canonical_json,
    evaluate_specification,
    specification_hash,
    stable_topological_order,
)
from .crm_order_admission import (
    CRMOrderAdmissionError,
    require_current_order_admission,
)
from .models import (
    BOMItem,
    BOMItemSourceRequirement,
    BOMVersion,
    EngineeringCalculationDetail,
    EngineeringCalculationRecord,
    EngineeringDerivedFact,
    EngineeringMaterialRequirement,
    EngineeringOperationRequirement,
    EngineeringRuleDefinition,
    EngineeringSourceRecord,
    ManufacturingApplicabilityScope,
    OrderEngineeringInstance,
    ProductBOM,
    ProductDesignItem,
    RoutingStep,
    StandardCapacity,
)
from .production_foundation_service import (
    ProductionFoundationError,
    _actor_chain,
    _audit,
    _snapshot,
)
from .engineering_work_context import (
    build_engineering_input_options,
    build_production_plan_projection,
)
from .material_role_applicability import (
    APPLICABLE,
    NOT_APPLICABLE,
    UNRESOLVED,
    resolve_material_role_applicability,
)
from .manufacturing_structure_service import (
    ManufacturingStructureError,
    ManufacturingStructureService,
)
from .paint_process_applicability import (
    BLOCKED,
    DEFERRED,
    INCOMPLETE,
    MATERIAL_BOM_GENERATION_STAGE,
    READY,
    PAINT_MATERIAL_ROLE_CODES,
    resolve_capacity_readiness,
    resolve_capacity_stage_gate,
    resolve_paint_material_applicability,
    resolve_process_applicability,
    resolve_routing_readiness,
)
from .routing_step_applicability_service import (
    CONTRACT_VERSION as ROUTING_STEP_APPLICABILITY_CONTRACT_VERSION,
    NOT_APPLICABLE as ROUTING_STEP_NOT_APPLICABLE,
    PENDING as ROUTING_STEP_PENDING,
    REQUIRED as ROUTING_STEP_REQUIRED,
    RoutingStepApplicabilityResolver,
)


class EngineeringCalculationError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


# EngineeringMaterialRequirement preserves the upstream business vocabulary,
# while BOMItem uses the canonical manufacturing vocabulary. Keep this bridge
# explicit and fail closed: unknown values must never be guessed while a
# manufacturing structure is created.
BOM_ITEM_ROLE_BY_REQUIREMENT = {
    "MAIN_MATERIAL": "material",
    "MAIN_PANEL_WITH_TRIM": "material",
    "material": "material",
    "assembly": "assembly",
    "component": "component",
    "part": "part",
}
BOM_REQUIREMENT_TYPE_BY_REQUIREMENT = {
    "MANUFACTURING": "manufacturing",
    "manufacturing": "manufacturing",
    "packaging": "packaging",
    "installation": "installation",
    "process_consumable": "process_consumable",
    "indirect": "indirect",
}
BOM_SUPPLY_TYPE_BY_REQUIREMENT = {
    "PRODUCTION": "MAKE",
    "MAKE": "MAKE",
    "BUY": "BUY",
    "SUBCONTRACT": "SUBCONTRACT",
    "MAKE_OR_BUY": "MAKE_OR_BUY",
}


def _bom_contract_value(mapping, value, *, code, label):
    normalized = mapping.get(str(value or "").strip())
    if normalized is None:
        raise EngineeringCalculationError(
            code,
            f"工程物料需求的{label}无法映射为受治理BOM合同；系统拒绝猜测。",
            {"sourceValue": value},
        )
    return normalized


def _bom_item_role(value):
    return _bom_contract_value(
        BOM_ITEM_ROLE_BY_REQUIREMENT, value,
        code="UNSUPPORTED_BOM_ITEM_ROLE_MAPPING", label="结构角色",
    )


def _bom_requirement_type(value):
    return _bom_contract_value(
        BOM_REQUIREMENT_TYPE_BY_REQUIREMENT, value,
        code="UNSUPPORTED_BOM_REQUIREMENT_TYPE_MAPPING", label="需求类型",
    )


def _bom_supply_type(value):
    return _bom_contract_value(
        BOM_SUPPLY_TYPE_BY_REQUIREMENT, value,
        code="UNSUPPORTED_BOM_SUPPLY_TYPE_MAPPING", label="供给方式",
    )


CANONICAL_FIELD_LABELS = {
    "opening_height": "门洞高度",
    "opening_width": "门洞宽度",
    "casing_height": "门套高度",
    "casing_width": "门套宽度",
    "door_height": "门扇高度",
    "door_width": "门扇宽度",
    "order_quantity": "订单数量",
    "edge_band_25_net_length": "封边皮25净长度",
    "edge_band_50_net_length": "封边皮50净长度",
}


def _hash(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _classification(error_code):
    if error_code in {"UNKNOWN_VARIABLE"}:
        return "input_incomplete"
    if error_code in {"DIVISION_BY_ZERO", "UNIT_MISMATCH", "INVALID_DECIMAL"}:
        return "rule_recoverable"
    return "irrecoverable"


def _rule_set_identity(ordered_rules):
    package = ordered_rules[0].specification["rulePackage"]
    return f"{package['code']}@{package['version']}"


def _graph_snapshot(ordered_rules):
    return [{
        "sequence": sequence,
        "ruleId": rule.pk,
        "ruleCode": rule.rule_code,
        "ruleVersion": rule.version,
        "specificationHash": specification_hash(rule.specification),
        "dependencies": list(rule.specification.get("dependencies", [])),
        "expression": rule.specification["expression"],
        "precision": rule.specification["decimalPrecision"],
        "rounding": rule.specification["roundingMode"],
        "output": rule.specification["outputs"][0]["canonicalName"],
    } for sequence, rule in enumerate(ordered_rules, 1)]


def _golden_validation(source, canonical_snapshot, result_snapshot):
    """Build an exact comparison without ever exposing expected values as inputs."""
    payload = source.source_payload if isinstance(source.source_payload, dict) else {}
    golden = payload.get("goldenValidation")
    if not isinstance(golden, dict):
        return None
    if str(payload.get("validationClass") or "").upper() != "GOLDEN":
        raise EngineeringCalculationError(
            "GOLDEN_SOURCE_CLASS_INVALID",
            "Golden预期结果只能附着于明确标记为GOLDEN的验证来源。",
        )
    expected_rows = golden.get("expectedResults")
    if not isinstance(expected_rows, list) or not expected_rows:
        raise EngineeringCalculationError(
            "GOLDEN_EXPECTED_RESULT_REQUIRED", "Golden验证来源缺少受控预期结果。"
        )
    expected_fields = {
        str(row.get("canonicalField") or "").strip()
        for row in expected_rows if isinstance(row, dict)
    }
    leaked = sorted(field for field in expected_fields if field and field in canonical_snapshot)
    if leaked:
        raise EngineeringCalculationError(
            "GOLDEN_RESULT_AS_INPUT",
            "Golden预期结果不得作为工程计算输入。",
            {"canonicalFields": leaked},
        )
    actual_by_field = {
        row["canonicalField"]: row for row in result_snapshot
    }
    comparisons = []
    for expected in expected_rows:
        if not isinstance(expected, dict):
            raise EngineeringCalculationError(
                "GOLDEN_EXPECTED_RESULT_INVALID", "Golden预期结果成员必须是对象。"
            )
        field = str(expected.get("canonicalField") or "").strip()
        if not field or expected.get("verificationStatus") != "VERIFIED_RESULT":
            raise EngineeringCalculationError(
                "GOLDEN_EXPECTED_RESULT_INVALID",
                "Golden预期结果必须具有canonicalField和VERIFIED_RESULT状态。",
                {"canonicalField": field},
            )
        actual = actual_by_field.get(field)
        expected_value = Decimal(str(expected.get("value")))
        actual_value = (
            Decimal(str(actual["value"]["decimal"])) if actual else None
        )
        expected_unit = expected.get("unit") or None
        actual_unit = actual.get("uomCode") if actual else None
        value_match = actual_value is not None and actual_value == expected_value
        unit_match = actual_unit == expected_unit
        comparisons.append({
            "canonicalField": field,
            "expectedValue": str(expected_value),
            "actualValue": str(actual_value) if actual_value is not None else None,
            "difference": str(actual_value - expected_value) if actual_value is not None else None,
            "expectedUnit": expected_unit,
            "actualUnit": actual_unit,
            "sourceCell": expected.get("cell"),
            "verificationStatus": "VERIFIED_RESULT",
            "valueMatch": value_match,
            "unitMatch": unit_match,
            "result": "PASS" if value_match and unit_match else "FAIL",
        })
    return {
        "caseCode": golden.get("caseCode"),
        "caseName": golden.get("caseName"),
        "sourceFile": golden.get("sourceFile"),
        "sourceWorkbookSha256": golden.get("sourceWorkbookSha256"),
        "sourceSheet": golden.get("sourceSheet"),
        "sourceRow": golden.get("sourceRow"),
        "comparisonMode": "EXACT_DECIMAL_AND_UOM",
        "expectedResultsUsedAsInputs": False,
        "rows": comparisons,
        "result": "PASS" if all(row["result"] == "PASS" for row in comparisons) else "FAIL",
    }


def _order_inputs(sales_order_item):
    rows = SalesOrderItemEngineeringAttribute.objects.select_related("unit").filter(
        sales_order_item=sales_order_item,
    ).order_by("canonical_field", "sequence", "pk")
    result = {}
    for row in rows:
        if row.canonical_field in result:
            raise EngineeringCalculationError(
                "AMBIGUOUS_CANONICAL_INPUT",
                "同一订单行存在多个同名规范工程输入，DO-3不得猜测聚合。",
                {"canonicalField": row.canonical_field},
            )
        if row.normalized_value is None:
            raise EngineeringCalculationError(
                "CANONICAL_INPUT_NOT_MAINTAINED",
                "订单工程原始事实尚未形成规范值。",
                {"canonicalField": row.canonical_field},
            )
        result[row.canonical_field] = {
            "value": _json_safe(row.normalized_value),
            "unit": row.unit.code if row.unit_id else None,
            "sourceType": row.source_type,
            "sourceAttributeId": row.pk,
        }
    return result


def serialize_calculation(calculation, *, include_trace=True):
    details = list(calculation.details.select_related("rule", "uom").order_by("sequence"))
    facts = list(calculation.derived_facts.select_related("rule", "source_detail", "uom").order_by("sequence", "pk"))
    material_requirements = list(
        calculation.material_requirements.select_related("material", "uom", "source_detail")
        .order_by("sequence", "pk")
    )
    operation_requirements = list(
        calculation.operation_requirements.select_related("operation", "uom", "source_detail")
        .order_by("sequence", "pk")
    )
    payload = {
        "id": calculation.pk,
        "calculationNo": calculation.calculation_no,
        "companyId": calculation.company_id,
        "scope": calculation.scope,
        "sourceRecordId": calculation.source_record_id,
        "salesOrderItemId": calculation.sales_order_item_id,
        "orderEngineeringInstanceId": calculation.engineering_instance_id,
        "ruleSetVersion": calculation.rule_set_version,
        "revision": calculation.revision,
        "supersedesId": calculation.supersedes_id,
        "status": calculation.status,
        "errorClassification": calculation.error_classification,
        "errorCode": calculation.error_code,
        "errorMessage": calculation.error_message,
        "inputHash": calculation.input_hash,
        "ruleGraphHash": calculation.rule_graph_hash,
        "resultHash": calculation.result_hash,
        "idempotencyKey": calculation.idempotency_key,
        "startedAt": calculation.started_at.isoformat() if calculation.started_at else None,
        "finishedAt": calculation.finished_at.isoformat() if calculation.finished_at else None,
        "details": [{
            "id": row.pk,
            "sequence": row.sequence,
            "ruleId": row.rule_id,
            "ruleCode": row.rule_code,
            "ruleVersion": row.rule_version,
            "expressionSnapshot": row.expression_snapshot,
            "inputSnapshot": row.input_snapshot,
            "dependencySnapshot": row.dependency_snapshot,
            "outputName": row.output_name,
            "outputLabel": CANONICAL_FIELD_LABELS.get(row.output_name, row.output_name),
            "outputValue": row.output_value,
            "uomId": row.uom_id,
            "uomCode": row.uom.code if row.uom_id else None,
            "precision": row.precision,
            "rounding": row.rounding,
            "status": row.status,
            "errorCode": row.error_code,
            "errorMessage": row.error_message,
            "startedAt": row.started_at.isoformat(),
            "finishedAt": row.finished_at.isoformat() if row.finished_at else None,
        } for row in details],
        "derivedFacts": [{
            "id": row.pk,
            "canonicalField": row.canonical_field or row.fact_code,
            "displayName": CANONICAL_FIELD_LABELS.get(row.canonical_field or row.fact_code, row.canonical_field or row.fact_code),
            "value": row.value,
            "valueType": row.value_type,
            "uomId": row.uom_id,
            "uomCode": row.uom.code if row.uom_id else None,
            "sourceType": row.source_type,
            "sourceDetailId": row.source_detail_id,
            "ruleId": row.rule_id,
            "status": row.status,
            "trace": row.trace,
        } for row in facts],
        "materialRequirements": [{
            "id": row.pk,
            "sequence": row.sequence,
            "materialId": row.material_id,
            "materialCode": row.material.code,
            "materialName": row.material.name,
            "quantityBasis": row.quantity_basis,
            "calculatedQuantity": str(row.calculated_quantity),
            "orderQuantity": str(row.order_quantity),
            "netQuantity": str(row.net_quantity),
            "grossQuantity": str(row.gross_quantity) if row.gross_quantity is not None else None,
            "uomId": row.uom_id,
            "uomCode": row.uom.code,
            "itemRole": row.item_role,
            "requirementType": row.requirement_type,
            "supplyType": row.supply_type,
            "orderSpecification": row.order_specification,
            "scrapRateStatus": row.scrap_rate_status,
            "scrapRate": str(row.scrap_rate) if row.scrap_rate is not None else None,
            "sourceDetailId": row.source_detail_id,
            "trace": row.trace,
        } for row in material_requirements],
        "operationRequirements": [{
            "id": row.pk,
            "sequence": row.sequence,
            "operationId": row.operation_id,
            "operationCode": row.operation.code,
            "operationName": row.operation.name,
            "workloadQuantity": str(row.workload_quantity),
            "uomId": row.uom_id,
            "uomCode": row.uom.code,
            "sourceDetailId": row.source_detail_id,
            "trace": row.trace,
        } for row in operation_requirements],
        "factSource": "server",
        "localStorageFormalFactCount": 0,
    }
    if include_trace:
        payload["trace"] = calculation.trace
        from .saved_calculation_context import saved_context_from_record
        payload["savedPageContext"] = saved_context_from_record(calculation, payload)
    return payload


class EngineeringCalculationReadinessService:
    """A1.9 DO-1 read-only gate projection; it never prepares or executes a calculation."""

    PAGE_VERSION = "PCE-MATERIAL-CALCULATION-RULE-DEFINITION-V1.0"
    SOURCE_GOVERNANCE_SCHEMA_VERSION = "PCE-SOURCE-GOVERNANCE-V1"
    MATERIAL_CANDIDATES = (
        ("QSFB4601001", "清水封闭实木多层板", "G1面板候选数量2张"),
        ("BTKF2601001", "半透工艺实木多层板", "G2/G3工程候选"),
        (None, "25规格封边", "G1 edge_band_25_length=9.976 m"),
        (None, "50规格封边", "G1 edge_band_50_length=5.906 m"),
        (None, "60×18线料", "来源规格及数量候选，正式身份未确认"),
        (None, "50×18线料", "来源切长2440mm、数量3候选，正式身份未确认"),
    )
    OPERATION_CANDIDATES = (
        ("房门数量候选", "门类构件进入后续工序的数量语义", "G1 door/opening quantity candidate", "个/扇，待规则复核"),
        ("木工数量候选", "木工作业投产输入", "G1结构/面积/数量派生候选", "未唯一确认"),
        ("油漆数量候选", "表面处理作业投产输入", "visible_surface_area 4.789284候选", "m²来源明确，正式UOM不存在"),
    )
    CALCULATION_READINESS = (
        ("board_area", "板材面积", "面积", "m²"),
        ("paint_area", "可见面 / 油漆面积", "面积", "m²"),
        ("veneer_area", "木皮面积", "面积", "m²"),
        ("edge_band_length", "封边长度", "长度", "m"),
        ("glass_requirement", "玻璃用量", "面积 / 数量", "待用户确认"),
        ("hardware_requirement", "五金用量", "数量", "待用户确认"),
        ("hinge_requirement", "铰链用量", "数量", "个"),
        ("lock_requirement", "锁具用量", "数量", "套 / 个，待用户确认"),
        ("butt_hinge_requirement", "合页用量", "数量", "个"),
        ("other_requirement", "其它物料用量", "按规则", "待用户确认"),
    )
    FIRST_BATCH_RULE_TEMPLATES = (
        {
            "sequence": "M01", "code": "board_area", "name": "板材面积",
            "outputFact": "BOARD_AREA", "targetUom": "m² / 平方米",
            "inputOptions": ("长度", "宽度", "厚度", "数量", "其它结构参数"),
            "definitionPrompts": ("哪些部件计入", "长宽取哪个结构尺寸", "数量如何取得", "是否增加损耗", "舍入规则"),
            "boundary": "系统不预选长×宽×数量；具体公式必须由用户确认。",
        },
        {
            "sequence": "M02", "code": "paint_area", "name": "见光面积 / 油漆面积",
            "outputFact": "VISIBLE_AREA / PAINT_AREA", "targetUom": "m² / 平方米",
            "inputOptions": ("长度", "宽度", "厚度", "数量", "计入面", "扣除项", "增加项"),
            "definitionPrompts": ("哪些面计入", "哪些面不计入", "扣除什么", "增加什么", "舍入规则"),
            "boundary": "系统不默认六面全部计入；不同结构角色分别确认。",
        },
        {
            "sequence": "M03", "code": "veneer_area", "name": "木皮面积",
            "outputFact": "VENEER_AREA", "targetUom": "m² / 平方米",
            "inputOptions": ("长度", "宽度", "数量", "贴皮面", "单面/双面", "损耗"),
            "definitionPrompts": ("哪些部件贴皮", "哪些面贴皮", "是否双面", "是否留损耗", "损耗如何处理"),
            "boundary": "木皮面积不继承板材面积；贴皮面与损耗必须单独确认。",
        },
        {
            "sequence": "M04", "code": "edge_band_length", "name": "封边长度",
            "outputFact": "EDGE_BANDING_LENGTH", "targetUom": "m / 米",
            "inputOptions": ("长度", "宽度", "数量", "需封长边数", "需封宽边数", "其它边"),
            "definitionPrompts": ("哪些边需要封", "长边计入几条", "宽边计入几条", "是否留损耗", "舍入规则"),
            "boundary": "系统不默认四边全部封边；封边边界必须由用户确认或由已确认结构规则决定。",
        },
    )

    @staticmethod
    def _gate(code, status, blocker_code, observed_fact):
        return {
            "code": code,
            "status": status,
            "blockerCode": blocker_code,
            "observedFact": observed_fact,
        }

    @staticmethod
    def source_decision(classification):
        classification = str(classification or "D").upper()
        if classification == "A":
            return {
                "status": "PASS",
                "executionEligibility": "ELIGIBLE FOR FORMAL REVIEW",
                "formalHashRegistrationPerformed": False,
            }
        return {
            "status": "BLOCKED",
            "executionEligibility": "BLOCKED",
            "formalHashRegistrationPerformed": False,
        }

    @classmethod
    def _source_reconciliation(cls, company_id):
        """Resolve source readiness from governed records, never from a hash embedded in code."""
        candidates = []
        confirmed = EngineeringSourceRecord.objects.filter(
            company_id=company_id,
            source_type="controlled_import",
            status="confirmed",
        ).order_by("-effective_date", "-created_at", "-pk")
        for source in confirmed:
            payload = source.source_payload if isinstance(source.source_payload, dict) else {}
            governance = payload.get("governance") if isinstance(payload.get("governance"), dict) else {}
            validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
            content_hash = str(source.content_hash or "").upper()
            required_metadata = {
                "fileName": payload.get("fileName"),
                "capturedAt": payload.get("capturedAt"),
                "sourceDate": payload.get("sourceDate"),
                "governanceStatus": governance.get("status"),
                "validationStatus": validation.get("status"),
            }
            eligible = (
                len(content_hash) == 64
                and all(ch in "0123456789ABCDEF" for ch in content_hash)
                and all(required_metadata.values())
                and governance.get("status") == "AUTHORITATIVE"
                and validation.get("status") == "PASS"
            )
            candidates.append({
                "sourceRecordId": source.pk,
                "sourceNo": source.source_no,
                "sourceVersion": source.source_version,
                "fileName": payload.get("fileName"),
                "sha256": content_hash,
                "capturedAt": payload.get("capturedAt"),
                "sourceDate": payload.get("sourceDate"),
                "supersedes": governance.get("supersedes"),
                "governanceStatus": governance.get("status"),
                "validationStatus": validation.get("status"),
                "eligible": eligible,
                "missingMetadata": [key for key, value in required_metadata.items() if not value],
            })

        eligible = [row for row in candidates if row["eligible"]]
        if len(eligible) == 1:
            classification = "A"
            reason = "ONE_CONFIRMED_AUTHORITATIVE_SOURCE_VERSION"
            authoritative = eligible[0]
        elif len(eligible) > 1:
            classification = "C"
            reason = "MULTIPLE_AUTHORITATIVE_SOURCE_VERSIONS_REQUIRE_SUPERSESSION_REVIEW"
            authoritative = None
        else:
            classification = "D"
            reason = "NO_CONFIRMED_AUTHORITATIVE_SOURCE_VERSION"
            authoritative = None
        decision = cls.source_decision(classification)
        return {
            "governanceSchemaVersion": cls.SOURCE_GOVERNANCE_SCHEMA_VERSION,
            "classification": classification,
            "reason": reason,
            "authoritativeSource": authoritative,
            "candidateCount": len(candidates),
            "eligibleCandidateCount": len(eligible),
            "candidates": candidates,
            "executionEligibility": decision["executionEligibility"],
            "formalHashRegistrationPerformed": decision["formalHashRegistrationPerformed"],
            "status": decision["status"],
        }

    @classmethod
    def _orders(cls, company_id):
        items = SalesOrderItem.objects.select_related(
            "sales_order", "material", "product_definition", "uom",
        ).filter(sales_order__company_id=company_id).order_by("sales_order_id", "line_no")
        instance_by_item = {
            row.sales_order_item_id: row
            for row in OrderEngineeringInstance.objects.filter(company_id=company_id).select_related(
                "source_record", "product", "baseline_product_version", "product_category",
                "selected_process_type",
            )
        }
        attribute_rows = SalesOrderItemEngineeringAttribute.objects.filter(
            sales_order_item__sales_order__company_id=company_id,
        ).select_related("unit").order_by("sales_order_item_id", "sequence", "pk")
        attributes = {}
        for row in attribute_rows:
            bucket = attributes.setdefault(row.sales_order_item_id, [])
            bucket.append(row)

        design_items = {}
        for design_item in ProductDesignItem.objects.filter(
            company_id=company_id,
        ).select_related(
            "source_attribute", "product_category", "product_definition", "physical_uom",
        ).prefetch_related(
            "design_revisions__material", "design_revisions__material_process_type",
            "design_revisions__paint_process_type", "design_revisions__edge_method",
            "design_revisions__design_uom",
        ).order_by("source_attribute_id"):
            design_items.setdefault(design_item.sales_order_item_id, []).append(design_item)

        result = []
        for item in items:
            values = attributes.get(item.pk, [])
            current_design_items = []
            for design_item in design_items.get(item.pk, []):
                revision = design_item.design_revisions.order_by("-revision").first()
                source_design = design_item.existing_design_data if isinstance(design_item.existing_design_data, dict) else {}
                design_data = revision.design_data if revision and isinstance(revision.design_data, dict) else {}
                current_design_items.append({
                    "designItemId": design_item.pk, "designItemNo": design_item.item_no,
                    "salesOrderItemId": item.pk, "orderLineNo": item.line_no,
                    "sourceAttributeId": design_item.source_attribute_id,
                    "sourceSheet": (source_design.get("provenance") or {}).get("sourceSheet"),
                    "sourceRow": (source_design.get("provenance") or {}).get("sourceRow"),
                    "revision": revision.revision if revision else None,
                    "designLength": str(revision.design_length) if revision and revision.design_length is not None else source_design.get("designLength"),
                    "designWidth": str(revision.design_width) if revision and revision.design_width is not None else source_design.get("designWidth"),
                    "designThickness": str(revision.design_thickness) if revision and revision.design_thickness is not None else source_design.get("designThickness"),
                    "designUom": revision.design_uom.code if revision and revision.design_uom_id else "mm",
                    "materialId": revision.material_id if revision else None,
                    "materialProcessTypeId": revision.material_process_type_id if revision else None,
                    "paintProcessTypeId": revision.paint_process_type_id if revision else None,
                    "edgeMethodId": revision.edge_method_id if revision else (design_item.match_results or {}).get("edgeMethod", {}).get("matchedId"),
                    "edgeMethod": revision.edge_method.name if revision and revision.edge_method_id else source_design.get("edgeMethod"),
                    "visibleConditionCode": design_data.get("visibleConditionCode"),
                    "visibleCondition": design_data.get("visibleCondition") if revision else source_design.get("visibleCondition"),
                    "colorVersion": design_data.get("finishOrColor") if revision else source_design.get("finishOrColor"),
                    "inputAuthority": "CURRENT_PRODUCT_DESIGN_REVISION" if revision else "EXISTING_DESIGN_SOURCE_SNAPSHOT",
                })
            attribute_status = "PASS" if values and all(value.normalized_value is not None for value in values) else "BLOCKED"
            instance = instance_by_item.get(item.pk)
            source_type = instance.source_record.source_type if instance else "NOT_BOUND"
            source_payload = (
                instance.source_record.source_payload
                if instance and isinstance(instance.source_record.source_payload, dict)
                else {}
            )
            golden = source_payload.get("goldenValidation") if isinstance(source_payload.get("goldenValidation"), dict) else {}
            blockers = []
            if item.engineering_mode != "ORDER_ENGINEERED":
                blockers.append("ORDER_LINE_NOT_ENGINEERED")
            if not item.uom_id:
                blockers.append("ORDER_UOM_REQUIRED")
            if attribute_status != "PASS":
                blockers.append("ORDER_ENGINEERING_ATTRIBUTES_NOT_READY")
            if not instance:
                blockers.append("ORDER_ENGINEERING_INSTANCE_NOT_CREATED")
            elif instance.source_record.status != "confirmed":
                blockers.append("ORDER_ENGINEERING_SOURCE_NOT_CONFIRMED")
            elif instance.status not in {"source_confirmed", "calculated"}:
                blockers.append("ORDER_ENGINEERING_INSTANCE_NOT_READY")
            result.append({
                "salesOrderId": item.sales_order_id,
                "salesOrderItemId": item.pk,
                "orderNo": item.sales_order.order_no,
                "lineNo": item.line_no,
                "orderQuantity": str(item.quantity),
                "orderUomCode": item.uom.code if item.uom_id else None,
                "salesOrderItem": f"{item.sales_order.order_no}/{item.line_no}",
                "sourceType": source_type,
                "materialCode": item.material.code,
                "materialName": item.material.name,
                "customerProductName": item.customer_product_name,
                "installationArea": item.installation_area or golden.get("installationArea") or golden.get("caseName") or "未登记",
                "engineeringAttributeStatus": attribute_status,
                "engineeringAttributeCount": len(values),
                "orderEngineeringInstanceId": instance.pk if instance else None,
                "orderEngineeringInstanceNo": instance.instance_no if instance else None,
                "orderEngineeringInstanceStatus": instance.status if instance else "NOT_CREATED",
                "sourceRecordId": instance.source_record_id if instance else None,
                "sourceNo": instance.source_record.source_no if instance else None,
                "sourceVersion": instance.source_record.source_version if instance else None,
                "productId": instance.product_id if instance else None,
                "productVersionId": instance.baseline_product_version_id if instance else None,
                "productCategoryId": instance.product_category_id if instance else None,
                "selectedProcessTypeId": instance.selected_process_type_id if instance else None,
                "sourceFile": golden.get("sourceFile") or source_payload.get("fileName") or "未登记",
                "sourceSheet": golden.get("sourceSheet") or "未登记",
                "sourceRow": golden.get("sourceRow"),
                "sourceCaseName": (golden.get("caseName") or instance.source_record.source_name) if instance else "未登记",
                "sourceUnit": source_payload.get("sourceUom") or "来源未填写",
                "sourceMaterialCode": source_payload.get("sourceMaterialCode"),
                "stableOrderLinkStatus": source_payload.get("stableOrderLinkStatus") or "NO_STABLE_KEY",
                "coverageStatement": source_payload.get("coverageStatement") or "当前订单行的工程尺寸核算；不代表完整房门或整单BOM。",
                "canonicalInputs": [{
                    "id": value.pk,
                    "rawField": value.raw_field,
                    "displayName": CANONICAL_FIELD_LABELS.get(value.canonical_field, value.raw_field or value.canonical_field),
                    "canonicalField": value.canonical_field,
                    "rawValue": value.raw_value,
                    "normalizedValue": value.normalized_value,
                    "uomCode": value.unit.code if value.unit_id else None,
                    "sourceType": value.source_type,
                    "rawSource": value.raw_source,
                    "rawSheet": value.raw_sheet,
                    "externalSource": value.external_source,
                } for value in values],
                "designItemCount": len(current_design_items),
                "currentDesignInputs": current_design_items,
                "calculationInputPolicy": "CURRENT_DESIGN_REVISION_BY_STABLE_SOURCE_ITEM" if current_design_items else "ORDER_ENGINEERING_ATTRIBUTES",
                "status": "PASS" if not blockers else "BLOCKED",
                "blockerReasons": blockers,
            })
        return sorted(result, key=lambda row: (0 if row["designItemCount"] else 1, row["salesOrderId"], row["lineNo"]))

    @classmethod
    def _materials(cls, company_id):
        codes = [code for code, _, _ in cls.MATERIAL_CANDIDATES if code]
        formal = {
            row.code: row
            for row in Material.objects.filter(company_id=company_id, is_active=True, code__in=codes)
            .select_related("base_uom", "purchase_uom")
        }
        identity_rows = []
        unit_rows = []
        for code, name, evidence in cls.MATERIAL_CANDIDATES:
            match = formal.get(code) if code else None
            identity = None
            if not match and code:
                identity = ExternalIdentity.objects.filter(
                    organization_id=company_id,
                    external_id__endswith=f"CODE:{code}",
                    target_entity_type="materials",
                    mapping_status=ExternalIdentity.MappingStatus.MATCH,
                ).order_by("pk").first()
                try:
                    target_id = int(identity.target_entity_id) if identity else None
                except (TypeError, ValueError):
                    target_id = None
                if target_id:
                    match = Material.objects.filter(pk=target_id, company_id=company_id, is_active=True).select_related("base_uom", "purchase_uom").first()
            identity_rows.append({
                "sourceMaterial": name,
                "sourceCode": code or "UNKNOWN",
                "sourceName": name,
                "formalMaterialMatch": match.name if match else "NONE",
                "formalMaterialId": match.pk if match else None,
                "matchStatus": "MATCHED" if match else "UNRESOLVED",
                "evidence": (
                    f"ExternalIdentity#{identity.pk}：{identity.external_id}"
                    if identity and match else evidence
                ),
            })
            unit_rows.append({
                "sourceMaterial": name,
                "formalMaterialId": match.pk if match else None,
                "unitStatus": match.unit_status.upper() if match else "UNKNOWN",
                "baseUom": match.base_uom.code if match and match.base_uom_id else "NULL",
                "purchaseUom": match.purchase_uom.code if match and match.purchase_uom_id else "NULL",
                "identityAffectedByUnknownUom": False,
            })
        explicit_matches = sum(1 for code in codes if code in formal)
        return identity_rows, unit_rows, explicit_matches, len(codes)

    @classmethod
    def _engineering_uoms(cls, company_id):
        required = set()
        rules = EngineeringRuleDefinition.objects.filter(company_id=company_id, status="released")
        for rule in rules:
            specification = rule.specification if isinstance(rule.specification, dict) else {}
            package = specification.get("rulePackage") or {}
            if package.get("code") != "A18_G1_DOOR_GOLDEN":
                continue
            for output in specification.get("outputs") or []:
                if isinstance(output, dict) and output.get("unit"):
                    required.add(str(output["unit"]))
        formal = {
            row.code.lower(): row
            for row in UnitOfMeasure.objects.filter(company_id=company_id, is_active=True)
        }
        rows = []
        for code in sorted(required):
            match = formal.get(code.lower())
            rows.append({
                "uom": code,
                "requirement": "REQUIRED NOW",
                "formalUomId": match.pk if match else None,
                "status": "PASS" if match else "BLOCKED",
                "evidence": "当前released G1规则输出",
            })
        rows.extend([
            {"uom": "m", "requirement": "CONDITIONAL / FUTURE DO-3", "formalUomId": formal.get("m").pk if formal.get("m") else None, "status": "PENDING", "evidence": "不影响当前G1"},
            {"uom": "m²", "requirement": "CONDITIONAL / FUTURE DO-3/DO-4", "formalUomId": formal.get("m²").pk if formal.get("m²") else None, "status": "PENDING", "evidence": "不影响当前G1"},
        ])
        current_rows = [row for row in rows if row["requirement"] == "REQUIRED NOW"]
        status = "PASS" if current_rows and all(row["status"] == "PASS" for row in current_rows) else "BLOCKED"
        return rows, status

    @classmethod
    def _operations(cls, company_id):
        processes = list(Process.objects.filter(company_id=company_id).select_related("workshop", "work_center"))
        rows = [{
            "sourceOperation": source,
            "canonicalMeaning": meaning,
            "formalOperationMatch": "NONE",
            "workshopEvidence": "NOT VERIFIED",
            "workCenterEvidence": "NULL / NOT_MAINTAINED",
            "inputQuantitySource": quantity,
            "inputUomSource": uom,
            "status": "PENDING / NOT VERIFIED",
        } for source, meaning, quantity, uom in cls.OPERATION_CANDIDATES]
        return rows, len(processes)

    @classmethod
    def _material_rule_definition_read_model(cls, company_id):
        """Build a read-only structure scan and blank rule-definition templates."""
        from masterdata.group3_comparison_runtime import build_group3_comparison

        structure_facts = build_group3_comparison("boms", company_id)
        cards = structure_facts.get("hierarchyCards") or []
        contexts = []
        grouped_roles = {}
        for card in cards:
            children = card.get("children") or []
            dimensions = [row.get("dimensions") or {} for row in children]
            source_rows = [row.get("sourceRow") for row in children if row.get("sourceRow") is not None]
            context = {
                "identity": card.get("identity"),
                "productCategory": card.get("productCategory") or "待确认",
                "structureRole": card.get("productName") or "待确认",
                "space": card.get("space") or "未登记",
                "model": next((row.get("model") for row in children if row.get("model")), "未登记"),
                "processCode": card.get("processCode") or "未登记",
                "componentCount": len(children),
                "sourceRows": source_rows,
                "sourceFile": next((row.get("sourceFile") for row in children if row.get("sourceFile")), "未登记"),
                "sourceSheet": next((row.get("sourceSheet") for row in children if row.get("sourceSheet")), "未登记"),
                "materialCodes": sorted({row.get("materialCode") for row in children if row.get("materialCode")}),
                "dimensions": dimensions,
                "availableInputs": {
                    key: any(value.get(key) not in (None, "") for value in dimensions)
                    for key in ("height", "width", "thickness")
                },
                "quantityPresent": any(row.get("quantity") not in (None, "") for row in children),
            }
            contexts.append(context)
            role_key = (context["productCategory"], context["structureRole"])
            role = grouped_roles.setdefault(role_key, {
                "productCategory": context["productCategory"],
                "structureRole": context["structureRole"],
                "structureCardCount": 0,
                "sourceRowCount": 0,
                "materialCodes": set(),
                "hasDimensions": False,
            })
            role["structureCardCount"] += 1
            role["sourceRowCount"] += len(children)
            role["materialCodes"].update(context["materialCodes"])
            role["hasDimensions"] = role["hasDimensions"] or all(context["availableInputs"].values())

        gap_rows = []
        for role in grouped_roles.values():
            role_name = role["structureRole"]
            explicit_items = ["板材面积"] if role["materialCodes"] and role["hasDimensions"] else []
            if "见光" in role_name:
                explicit_items.append("见光面积 / 油漆面积")
            if "玻璃" in role_name:
                explicit_items.append("玻璃面积 / 数量")
            review_items = ["木皮面积", "封边长度"]
            if any(marker in role_name for marker in ("门", "抽")):
                review_items.append("五金 / 铰链 / 锁 / 合页")
            gap_rows.append({
                **role,
                "materialCodes": sorted(role["materialCodes"]),
                "requiredCalculationItems": explicit_items,
                "itemsRequiringUserDecision": review_items,
                "currentRule": "未建立物料核算规则",
                "status": "待用户定义",
                "missingInputs": "数量、计入面/边、损耗、条件与舍入规则；来源未提供的字段不得猜测",
                "userAction": "选择结构上下文，在首批规则卡中用业务语言补充并生成拟规则 Preview",
            })

        templates = []
        for template in cls.FIRST_BATCH_RULE_TEMPLATES:
            templates.append({
                **template,
                "inputOptions": list(template["inputOptions"]),
                "definitionPrompts": list(template["definitionPrompts"]),
                "applicableProductCategory": "待用户选择",
                "applicableStructureRole": "待用户选择",
                "applicableCondition": "待用户定义",
                "calculationMethod": "待用户定义",
                "version": "系统技术标识将在规则获人工确认后生成",
                "enabled": False,
                "provenance": "UNKNOWN",
                "userValidationStatus": "PENDING",
                "formalWriteAllowed": False,
            })
        return {
            "structureCardCount": len(cards),
            "sourceRowCount": structure_facts.get("sourceRecordCount", 0),
            "contexts": contexts,
            "gapMatrix": gap_rows,
            "firstBatchTemplates": templates,
            "secondBatch": [
                {"sequence": "M05", "name": "玻璃面积 / 数量", "status": "PREPARED_NOT_VALIDATED", "requiredDefinition": "结构角色、尺寸、数量与规格"},
                {"sequence": "M06", "name": "五金数量", "status": "PREPARED_NOT_VALIDATED", "requiredDefinition": "产品类别、结构角色、尺寸、数量与配置条件"},
                {"sequence": "M07", "name": "铰链", "status": "PREPARED_NOT_VALIDATED", "requiredDefinition": "尺寸区间、数量关系与特殊条件"},
                {"sequence": "M08", "name": "锁", "status": "PREPARED_NOT_VALIDATED", "requiredDefinition": "适用对象、数量、单位与特殊条件"},
                {"sequence": "M09", "name": "合页", "status": "PREPARED_NOT_VALIDATED", "requiredDefinition": "尺寸区间、数量关系与特殊条件"},
                {"sequence": "M10+", "name": "其它五金", "status": "PREPARED_NOT_VALIDATED", "requiredDefinition": "用户新增名称、适用范围、条件与数量规则"},
            ],
            "productionRealRuleWrite": 0,
        }

    @classmethod
    def _recovery_audit(cls, company_id):
        rules = list(EngineeringRuleDefinition.objects.filter(company_id=company_id).order_by("rule_code", "version"))
        calculations = EngineeringCalculationRecord.objects.filter(company_id=company_id)
        details = EngineeringCalculationDetail.objects.filter(calculation__company_id=company_id)
        facts = EngineeringDerivedFact.objects.filter(calculation__company_id=company_id)
        counts = {
            "EngineeringRuleDefinition": len(rules),
            "EngineeringCalculationRecord": calculations.count(),
            "CalculationDetail": details.count(),
            "EngineeringDerivedFact": facts.count(),
        }
        model_statuses = [{
            "model": name,
            "developed": True,
            "dataPresent": count > 0,
            "recordCount": count,
            "apiPresent": True,
            "pagePresent": True,
            "userAccessible": True,
            "productionDeployed": True,
            "usageStatus": "CURRENTLY_USED" if count else "AVAILABLE_NOT_POPULATED",
        } for name, count in counts.items()]
        capability_audit = [
            {"capability": "正式模型与迁移", "status": "FOUND", "evidence": "pde.0012 + pde.0018；四类核算证据模型已部署"},
            {"capability": "安全表达式引擎", "status": "FOUND", "evidence": "AST白名单、Decimal、单位维度、DAG依赖与舍入策略"},
            {"capability": "核算服务与持久化", "status": "FOUND", "evidence": "EngineeringCalculationService；幂等、修订、明细、派生事实与审计边界"},
            {"capability": "只读就绪API", "status": "FOUND", "evidence": "/api/pde/a1-engineering/calculations/readiness/"},
            {"capability": "规则维护API", "status": "FOUND", "evidence": "正式基础资料API已存在；本轮未调用写接口"},
            {"capability": "企业基础资料正式入口", "status": "RECOVERED", "evidence": "产品工程 → 工程核算 / 物料核算"},
            {"capability": "真实规则覆盖", "status": "PARTIAL", "evidence": f"已发布尺寸Golden规则 {sum(rule.status == 'released' for rule in rules)} 条；九类物料核算规则尚未正式建立"},
            {"capability": "订单工程正式使用", "status": "NOT_READY", "evidence": "OrderEngineeringInstance当前为0；不把08排产样版反向当工程输入"},
        ]
        rule_rows = []
        for rule in rules:
            specification = rule.specification if isinstance(rule.specification, dict) else {}
            output = (specification.get("outputs") or [{}])[0]
            rule_rows.append({
                "id": rule.pk,
                "ruleCode": rule.rule_code,
                "ruleName": rule.rule_name,
                "version": rule.version,
                "status": rule.status,
                "expression": specification.get("expression") or "",
                "calculationItem": output.get("canonicalName") or "",
                "inputs": [row.get("canonicalName") for row in specification.get("inputs") or []],
                "output": output.get("canonicalName") or "",
                "outputUnit": output.get("unit") or "待确认",
                "resultDomain": output.get("resultDomain") or "待确认",
                "sourceEvidence": (specification.get("sourceEvidence") or {}).get("reference") or "未登记",
                "applicability": specification.get("applicability") or {},
                "applicableProductCategory": (specification.get("applicability") or {}).get("productCategory") or "待确认",
                "applicableStructureRole": (specification.get("applicability") or {}).get("structureRole") or "未限定 / 待确认",
                "rounding": specification.get("roundingMode") or "待确认",
                "userValidationStatus": "USER_REVIEW_REQUIRED",
            })
        latest = calculations.filter(status="completed").prefetch_related("details", "derived_facts").order_by("-finished_at", "-pk").first()
        preview = None
        if latest:
            serialized = serialize_calculation(latest)
            source_payload = latest.source_record.source_payload if latest.source_record_id and isinstance(latest.source_record.source_payload, dict) else {}
            golden = source_payload.get("goldenValidation") or {}
            preview = {
                "calculationNo": latest.calculation_no,
                "scope": latest.scope,
                "status": latest.status,
                "sourceFile": golden.get("sourceFile") or "工程来源记录",
                "sourceSheet": golden.get("sourceSheet") or "未登记",
                "sourceRow": golden.get("sourceRow"),
                "structureObject": golden.get("caseName") or "未登记",
                "canonicalInputs": source_payload.get("canonicalInputs") or {},
                "results": serialized["derivedFacts"],
                "comparison": (serialized.get("trace") or {}).get("goldenComparison") or {},
                "materialRequirementCreated": False,
                "operationWorkloadCreated": False,
                "businessWriteSideEffectCount": 0,
            }
        readiness = [{
            "code": code,
            "name": name,
            "calculationBasis": basis,
            "targetUom": uom,
            "sourceStructurePresent": True,
            "ruleSource": "未建立",
            "inputComplete": False,
            "formalRuleStatus": "MISSING",
            "previewStatus": "AWAITING_RULE_DEFINITION",
            "userValidated": False,
            "currentStatus": "USER_INPUT_REQUIRED",
            "note": "仅确认结构来源存在；公式、损耗、舍入、适用范围和输出单位需用户维护并验收。",
        } for code, name, basis, uom in cls.CALCULATION_READINESS]
        if rules:
            readiness.append({
                "code": "door_dimension_derivation",
                "name": "房门尺寸派生（现有）",
                "calculationBasis": "长度",
                "targetUom": "mm",
                "sourceStructurePresent": True,
                "ruleSource": "工程拆单及订单排产数据核算方式.xlsx / 房门单",
                "inputComplete": preview is not None,
                "formalRuleStatus": "READY",
                "previewStatus": "VALIDATED_GOLDEN" if preview else "NO_COMPLETED_PREVIEW",
                "userValidated": False,
                "currentStatus": "PARTIAL",
                "note": "4条Released规则已有精确Golden验证；仍等待本轮用户查看，不外推为板材/五金/玻璃规则。",
            })
        return {
            "existingEngineStatus": "PARTIAL",
            "modelStatuses": model_statuses,
            "capabilityAudit": capability_audit,
            "formalRules": rule_rows,
            "calculationReadinessMatrix": readiness,
            "materialRuleDefinition": cls._material_rule_definition_read_model(company_id),
            "realStructureCalculationPreview": preview,
            "sourceAuthority": {
                "authoritative": "工程拆单及订单排产数据核算方式.xlsx",
                "derivedReferenceOnly": "08订单排产信息（样版）.xlsx",
                "derivedReferenceRole": "仅用于对照工程核算派生结果，不作为BOM、工程结构、订单工程实例或生产输入来源。",
                "linkageTo08Required": False,
                "supersededRequirement": "71条结构行关联37条子订单",
            },
            "group3C": {"structureLayer": "USER_VALIDATED", "calculationLayer": "NOT_READY", "overall": "PAUSED"},
            "group4": {"capacityModelPage": "MAY_PREPARE", "realCapacityData": "NOT_VALIDATED"},
            "planning": "NOT_DEPLOYED",
            "productionBusinessWrite": 0,
        }

    @classmethod
    def build(cls, *, user, subview=None):
        decision = AuthorizationService.decide(
            user=user,
            action_code="production.engineering.calculation.view",
            organization_id=user.company_id,
            business_object={"organizationId": user.company_id},
        )
        if not decision.get("allowed"):
            raise EngineeringCalculationError(
                decision.get("decisionCode", "PERMISSION_DENIED"),
                decision.get("reason", "当前账户无权查看工程核算事实。"),
                {"authorization": decision},
            )
        if subview == "semi-finished-structure":
            from django.utils import timezone
            from .semi_finished_configuration_preview import build_for_user
            preview = build_for_user(user)
            facts = {
                **preview["summary"], "pageCode": "pde-order-engineering-calculation",
                "moduleId": "engineering-calculation", "businessObject": "EngineeringCalculationRecord",
                "subview": subview, "pageVersion": preview["version"], "factSource": "server",
                "factLoadStatus": "loaded", "httpStatus": 200, "errorCode": "", "errorMessage": "",
                "apiUrl": "/api/pde/a1-engineering/calculations/readiness/?subview=semi-finished-structure",
                "loadedAt": timezone.now().isoformat(), "tenantId": user.company_id,
                "batchId": preview["version"], "passed": True, "userValidated": False,
                "resultCount": len(preview["configurations"]), "businessWriteSideEffectCount": 0,
            }
            return {"semiFinishedConfiguration": preview, **facts,
                    "apiFacts": facts, "strictFacts": facts, "pageFacts": facts, "diagnosticFacts": facts}
        if subview:
            raise EngineeringCalculationError("UNKNOWN_CALCULATION_SUBVIEW", "未知工程核算子视图。")
        company_id = user.company_id
        orders = cls._orders(company_id)
        material_identity, material_units, matched, required = cls._materials(company_id)
        engineering_uoms, engineering_uom_status = cls._engineering_uoms(company_id)
        operations, process_count = cls._operations(company_id)
        order_status = "PASS" if any(row["status"] == "PASS" for row in orders) else "BLOCKED"
        material_status = "PASS" if matched == required else "BLOCKED"
        operation_status = "PASS" if process_count and all(row["status"] == "PASS" for row in operations) else "BLOCKED"
        source_reconciliation = cls._source_reconciliation(company_id)
        source_status = source_reconciliation["status"]
        gates = [
            cls._gate("ORDER", order_status, "" if order_status == "PASS" else "A1.9-ORDER-INPUT-01", f"eligible={sum(row['status'] == 'PASS' for row in orders)}/{len(orders)}"),
            cls._gate("MATERIAL", material_status, "" if material_status == "PASS" else "BLOCKER-DATA-MAT-01", f"explicitMatch={matched}/{required}"),
            cls._gate("ENGINEERING UOM", engineering_uom_status, "" if engineering_uom_status == "PASS" else "ENGINEERING_UOM_REQUIRED", "currentG1=mm"),
            cls._gate("OPERATION", operation_status, "" if operation_status == "PASS" else "BLOCKER-SEM-OP-01", f"system.Process={process_count}"),
            cls._gate(
                "SOURCE", source_status,
                "" if source_status == "PASS" else "SOURCE_VERSION_GOVERNANCE_REQUIRED",
                f"eligibleSourceVersions={source_reconciliation['eligibleCandidateCount']}",
            ),
        ]
        overall_status = "BLOCKED" if any(gate["status"] == "BLOCKED" for gate in gates) else "PENDING" if any(gate["status"] == "PENDING" for gate in gates) else "READY"
        blocker_codes = [gate["blockerCode"] for gate in gates if gate["blockerCode"]]
        try:
            candidate_methods = EngineeringMethodTrialService.list_methods(user=user)
            candidate_method_access = {
                "status": "LOADED",
                "statusLabel": "候选方法读取成功",
                "errorCode": "",
                "methodCount": len(candidate_methods),
            }
        except EngineeringCalculationError as exc:
            if exc.code not in {"PERMISSION_DENIED", "SCOPE_DENIED", "IDENTITY_INVALID"}:
                raise
            candidate_methods = []
            candidate_method_access = {
                "status": "READ_DENIED",
                "statusLabel": "当前身份无权读取工程核算候选方法",
                "errorCode": exc.code,
                "methodCount": None,
            }
            blocker_codes.append("CALCULATION_METHOD_READ_PERMISSION_REQUIRED")
        common = {
            "factSource": "server",
            "pageVersion": cls.PAGE_VERSION,
            "pageCode": "pde-order-engineering-calculation",
            "pageName": "工程核算 / 物料核算",
            "moduleCode": "PDE",
            "businessObject": "EngineeringCalculationRecord",
            "overallStatus": overall_status,
            "gateCount": len(gates),
            "businessWriteSideEffectCount": 0,
            "localStorageFormalFactCount": 0,
            "acceptanceStatus": "PENDING",
            "runtimeEnvironment": {
                "label": os.environ.get("PCE_ENVIRONMENT_LABEL", "运行环境尚未由服务启动参数声明"),
                "nonProduction": os.environ.get("PCE_NON_PRODUCTION_ACCEPTANCE", "0") == "1",
                "databaseIdentity": os.environ.get("PCE_DATABASE_IDENTITY", "未声明"),
                "codeIdentity": os.environ.get("PCE_CODE_IDENTITY", "working-tree"),
                "acceptanceIdentity": os.environ.get("PCE_ACCEPTANCE_IDENTITY", "未声明"),
            },
        }
        return {
            **common,
            **cls._recovery_audit(company_id),
            "gates": gates,
            "orders": orders,
            "engineeringInputOptions": build_engineering_input_options(user),
            "productionPlanByOrder": build_production_plan_projection(company_id, orders),
            "candidateMethods": candidate_methods,
            "candidateMethodAccess": candidate_method_access,
            "materialIdentity": material_identity,
            "materialBasePurchaseUom": material_units,
            "engineeringRequiredUoms": engineering_uoms,
            "requiredOperations": operations,
            "sourceReconciliation": {
                key: value for key, value in source_reconciliation.items() if key != "status"
            },
            "execution": {
                "label": "执行工程／物料核算",
                "enabled": not blocker_codes,
                "status": "BLOCKED" if blocker_codes else "READY",
                "authorization": "SERVER_AUTHORIZATION_REQUIRED_ON_EXECUTION",
                "blockerCodes": blocker_codes,
            },
            "apiFacts": dict(common),
            "pageFacts": dict(common),
            "diagnosticFacts": dict(common),
            "strictFacts": dict(common),
            "acceptanceFacts": dict(common),
        }


class EngineeringCalculationService:
    @staticmethod
    def _authorize(*, user, action_code, company_id, object_id=None):
        decision = AuthorizationService.decide(
            user=user,
            action_code=action_code,
            organization_id=company_id,
            business_object={
                "organizationId": company_id,
                "engineeringCalculationId": object_id,
            },
        )
        if not decision.get("allowed"):
            raise EngineeringCalculationError(
                decision.get("decisionCode", "PERMISSION_DENIED"),
                decision.get("reason", "当前账户无权执行工程计算动作。"),
                {"authorization": decision},
            )
        return decision

    @classmethod
    def list(cls, *, user, scope=None, status=None):
        company_id = user.company_id
        cls._authorize(
            user=user,
            action_code="production.engineering.calculation.view",
            company_id=company_id,
        )
        queryset = EngineeringCalculationRecord.objects.filter(company_id=company_id)
        if scope:
            queryset = queryset.filter(scope=scope)
        if status:
            queryset = queryset.filter(status=status)
        return [serialize_calculation(row, include_trace=False) for row in queryset.order_by("-pk")]

    @classmethod
    def get(cls, *, user, object_id):
        calculation = EngineeringCalculationRecord.objects.filter(
            pk=object_id, company_id=user.company_id,
        ).first()
        if not calculation:
            raise EngineeringCalculationError("CALCULATION_NOT_FOUND", "工程计算记录不存在。")
        cls._authorize(
            user=user,
            action_code="production.engineering.calculation.view",
            company_id=calculation.company_id,
            object_id=calculation.pk,
        )
        return serialize_calculation(calculation)

    @classmethod
    def execute(
        cls,
        *,
        user,
        scope,
        source_record_id,
        rule_ids,
        canonical_inputs=None,
        sales_order_item_id=None,
        engineering_instance_id=None,
        reason="",
    ):
        source = EngineeringSourceRecord.objects.filter(pk=source_record_id).first()
        if not source:
            raise EngineeringCalculationError("SOURCE_NOT_FOUND", "工程来源记录不存在。")
        try:
            decision = cls._authorize(
                user=user,
                action_code="production.engineering.calculation.execute",
                company_id=source.company_id,
            )
        except EngineeringCalculationError as exc:
            execution_chain = {"account": getattr(user, "username", "")}
            try:
                execution_chain = _actor_chain(user)
            except ProductionFoundationError:
                pass
            audit = OrganizationOperatingAuditRecord.objects.create(
                action_code="production.engineering.calculation.execute",
                actor=user,
                organization_id=source.company_id,
                target_type="EngineeringCalculationAttempt",
                target_id=source.pk,
                target_label=source.source_no[:200],
                reason=str(reason or "工程计算授权拒绝")[:300],
                before_snapshot={
                    "sourceRecordId": source.pk,
                    "scope": scope,
                    "ruleIds": list(rule_ids or []),
                    "factSource": "server",
                },
                after_snapshot={
                    "decision": "DENIED",
                    "errorCode": exc.code,
                    "errorMessage": exc.message,
                    "authorization": exc.details.get("authorization", {}),
                    "executionChain": execution_chain,
                    "factSource": "server",
                },
            )
            exc.details["auditId"] = audit.pk
            raise
        try:
            execution_chain = _actor_chain(user)
        except ProductionFoundationError as exc:
            raise EngineeringCalculationError(exc.code, exc.message, exc.details)
        return cls._execute_atomic(
            user=user,
            scope=scope,
            source_record_id=source_record_id,
            rule_ids=rule_ids,
            canonical_inputs=canonical_inputs,
            sales_order_item_id=sales_order_item_id,
            engineering_instance_id=engineering_instance_id,
            reason=reason,
            decision=decision,
            execution_chain=execution_chain,
        )

    @classmethod
    @transaction.atomic
    def _execute_atomic(
        cls,
        *,
        user,
        scope,
        source_record_id,
        rule_ids,
        decision,
        execution_chain,
        canonical_inputs=None,
        sales_order_item_id=None,
        engineering_instance_id=None,
        reason="",
    ):
        if scope not in {"validation", "order_engineering"}:
            raise EngineeringCalculationError("INVALID_SCOPE", "计算scope不受支持。")
        source = EngineeringSourceRecord.objects.select_for_update().filter(pk=source_record_id).first()
        if not source:
            raise EngineeringCalculationError("SOURCE_NOT_FOUND", "工程来源记录不存在。")
        company_id = source.company_id
        if source.status != "confirmed":
            raise EngineeringCalculationError(
                "SOURCE_NOT_CONFIRMED", "只有已确认的工程来源记录允许正式计算。"
            )

        sales_item = None
        engineering_instance = None
        if scope == "validation":
            if sales_order_item_id or engineering_instance_id:
                raise EngineeringCalculationError(
                    "VALIDATION_CONTEXT_INVALID",
                    "validation计算不得绑定正式订单工程上下文。",
                )
            canonical_snapshot = canonical_inputs
            if canonical_snapshot is None:
                canonical_snapshot = source.source_payload.get("canonicalInputs")
            if not isinstance(canonical_snapshot, dict) or not canonical_snapshot:
                raise EngineeringCalculationError(
                    "CANONICAL_INPUT_REQUIRED", "validation计算必须提供受控规范输入。"
                )
        else:
            if not sales_order_item_id or not engineering_instance_id:
                raise EngineeringCalculationError(
                    "ORDER_ENGINEERING_CONTEXT_REQUIRED",
                    "order_engineering必须绑定SalesOrderItem和OrderEngineeringInstance。",
                )
            sales_item = SalesOrderItem.objects.select_related("sales_order").filter(
                pk=sales_order_item_id,
            ).first()
            engineering_instance = OrderEngineeringInstance.objects.select_related(
                "sales_order_item__sales_order", "source_record",
            ).filter(pk=engineering_instance_id).first()
            if not sales_item or not engineering_instance:
                raise EngineeringCalculationError(
                    "ORDER_ENGINEERING_CONTEXT_NOT_FOUND", "订单工程上下文不存在。"
                )
            if (
                sales_item.sales_order.company_id != company_id
                or engineering_instance.company_id != company_id
                or engineering_instance.sales_order_item_id != sales_item.pk
                or engineering_instance.source_record_id != source.pk
            ):
                raise EngineeringCalculationError(
                    "ORDER_ENGINEERING_CONTEXT_MISMATCH", "订单、工程实例和来源记录不属于同一正式上下文。"
                )
            if (
                sales_item.sales_order.business_purpose
                == SalesOrder.BusinessPurpose.FORMAL_SALE
            ):
                try:
                    admission = require_current_order_admission(
                        order=sales_item.sales_order,
                        sales_order_item_id=sales_item.pk,
                        engineering_instance_id=engineering_instance.pk,
                        lock=True,
                    )
                    if (
                        admission.as_dict().get("admissionMode")
                        == "LEGACY_IN_FLIGHT_ADOPTION"
                    ):
                        raise EngineeringCalculationError(
                            "PDE_LEGACY_IN_FLIGHT_SCOPE_IMMUTABLE",
                            "历史在制承接只授权锁定的既有工程范围，不得创建新的工程核算事实。",
                        )
                except CRMOrderAdmissionError as exc:
                    raise EngineeringCalculationError(
                        exc.code, exc.message, {"orderAdmission": exc.details},
                    ) from exc
            if engineering_instance.status not in {"source_confirmed", "calculated"}:
                raise EngineeringCalculationError(
                    "ORDER_ENGINEERING_SOURCE_NOT_READY", "订单工程来源尚未确认。"
                )
            canonical_snapshot = _order_inputs(sales_item)
            if isinstance(source.source_payload, dict) and "sourceFormatReference" in source.source_payload:
                from .source_format_mapping_service import SourceFormatMappingError, mapped_order_inputs
                try:
                    canonical_snapshot = mapped_order_inputs(source, canonical_snapshot)
                except SourceFormatMappingError as exc:
                    raise EngineeringCalculationError(exc.code, exc.message, exc.details)
            if not canonical_snapshot:
                raise EngineeringCalculationError(
                    "CANONICAL_INPUT_REQUIRED", "订单行没有已标准化的工程输入。"
                )

        canonical_snapshot = _json_safe(canonical_snapshot)
        try:
            requested_ids = [int(value) for value in rule_ids or []]
        except (TypeError, ValueError):
            raise EngineeringCalculationError("RULE_SET_REQUIRED", "正式规则ID必须为整数。")
        if not requested_ids or len(requested_ids) != len(set(requested_ids)):
            raise EngineeringCalculationError("RULE_SET_REQUIRED", "必须提供不重复的正式规则ID。")
        rules = list(EngineeringRuleDefinition.objects.filter(
            company_id=company_id, pk__in=requested_ids,
        ))
        if len(rules) != len(requested_ids):
            raise EngineeringCalculationError("RULE_NOT_FOUND", "规则集包含不存在或跨公司的规则。")
        if any(rule.status != "released" for rule in rules):
            raise EngineeringCalculationError("RULE_NOT_RELEASED", "规则集只能包含已发布规则。")
        try:
            ordered_rules = stable_topological_order(rules)
        except EngineeringRuleError as exc:
            raise EngineeringCalculationError(exc.code, exc.message, exc.details)
        rule_set_version = _rule_set_identity(ordered_rules)
        graph_snapshot = _graph_snapshot(ordered_rules)
        input_hash = _hash(canonical_snapshot)
        rule_graph_hash = _hash(graph_snapshot)
        idempotency_payload = {
            "scope": scope,
            "sourceRecordId": source.pk,
            "salesOrderItemId": sales_item.pk if sales_item else None,
            "engineeringInstanceId": engineering_instance.pk if engineering_instance else None,
            "ruleSetVersion": rule_set_version,
            "inputHash": input_hash,
            "ruleGraphHash": rule_graph_hash,
        }
        idempotency_key = _hash(idempotency_payload)
        existing = EngineeringCalculationRecord.objects.filter(
            company_id=company_id, idempotency_key=idempotency_key,
        ).first()
        if existing:
            audit = OrganizationOperatingAuditRecord.objects.filter(
                action_code="production.engineering.calculation.execute",
                target_type="EngineeringCalculationRecord",
                target_id=existing.pk,
            ).order_by("-pk").first()
            return {
                "calculation": serialize_calculation(existing),
                "idempotent": True,
                "auditId": audit.pk if audit else None,
                "authorization": decision,
                "executionChain": execution_chain,
            }

        base_queryset = EngineeringCalculationRecord.objects.select_for_update().filter(
            company_id=company_id,
            scope=scope,
            source_record=source,
            sales_order_item=sales_item,
            engineering_instance=engineering_instance,
        )
        previous = base_queryset.order_by("-revision", "-pk").first()
        revision = previous.revision + 1 if previous else 1
        try:
            calculation_no = CodeRule.next_code(
                entity_type="production_engineering_calculation",
                company_id=company_id,
            )
        except CodeRule.DoesNotExist:
            raise EngineeringCalculationError(
                "CODE_RULE_REQUIRED", "缺少正式工程计算编码规则。"
            )
        started_at = timezone.now()
        calculation = EngineeringCalculationRecord(
            company_id=company_id,
            scope=scope,
            source_record=source,
            sales_order_item=sales_item,
            engineering_instance=engineering_instance,
            calculation_no=calculation_no,
            rule_set_version=rule_set_version,
            revision=revision,
            supersedes=previous,
            idempotency_key=idempotency_key,
            input_hash=input_hash,
            rule_graph_hash=rule_graph_hash,
            status="running",
            started_at=started_at,
            trace={
                "scope": scope,
                "sourceReference": {
                    "id": source.pk,
                    "sourceNo": source.source_no,
                    "sourceVersion": source.source_version,
                    "contentHash": source.content_hash,
                },
                "salesOrderItemId": sales_item.pk if sales_item else None,
                "orderEngineeringInstanceId": engineering_instance.pk if engineering_instance else None,
                "ruleSetVersion": rule_set_version,
                "ruleGraphSnapshot": graph_snapshot,
                "inputSnapshot": _json_safe(source.source_payload),
                "canonicalInputSnapshot": canonical_snapshot,
                "executionOrder": [rule.rule_code for rule in ordered_rules],
                "precisionPolicy": [rule.specification["decimalPrecision"] for rule in ordered_rules],
                "roundingPolicy": [rule.specification["roundingMode"] for rule in ordered_rules],
                "idempotencyPayload": idempotency_payload,
                "factSource": "server",
            },
        )
        try:
            calculation.full_clean()
        except ValidationError as exc:
            raise EngineeringCalculationError(
                "CALCULATION_CONTEXT_INVALID", "工程计算聚合校验失败。", exc.message_dict,
            )
        calculation.save()

        pool = dict(canonical_snapshot)
        pending_outputs = []
        failed = None
        for sequence, rule in enumerate(ordered_rules, 1):
            spec = rule.specification
            input_names = [row["canonicalName"] for row in spec["inputs"]]
            rule_inputs = {name: pool[name] for name in input_names if name in pool}
            detail_started = timezone.now()
            output_contract = spec["outputs"][0]
            try:
                result = evaluate_specification(spec, rule_inputs)
                if result["resultDomain"] != "DERIVED_FACT" and scope != "order_engineering":
                    raise EngineeringRuleError(
                        "OUTPUT_DOMAIN_NOT_AUTHORIZED",
                        "物料需求和工序需求只能在正式订单工程核算中生成。",
                    )
                uom = None
                if result.get("unit"):
                    uom = UnitOfMeasure.objects.filter(
                        company_id=company_id, code=result["unit"], is_active=True,
                    ).first()
                    if not uom:
                        raise EngineeringRuleError(
                            "UNIT_MISMATCH", "规则输出引用的正式UOM不存在或已停用。",
                            {"uom": result["unit"]},
                        )
                if result["resultDomain"] in {"MATERIAL_REQUIREMENT", "OPERATION_REQUIREMENT"} and not uom:
                    raise EngineeringRuleError(
                        "UNIT_REQUIRED", "物料需求和工序需求输出必须引用正式UOM。",
                    )
                output_metadata = {}
                if result["resultDomain"] == "MATERIAL_REQUIREMENT":
                    try:
                        material_id = int(output_contract.get("materialId"))
                    except (TypeError, ValueError):
                        raise EngineeringRuleError(
                            "MATERIAL_IDENTITY_REQUIRED", "物料需求规则必须声明正式materialId。",
                        )
                    material = Material.objects.filter(
                        pk=material_id, company_id=company_id, is_active=True,
                    ).first()
                    if not material:
                        raise EngineeringRuleError(
                            "MATERIAL_NOT_FOUND", "物料需求规则引用的正式物料不存在、跨公司或已停用。",
                            {"materialId": material_id},
                        )
                    if material.base_uom_id is None:
                        raise EngineeringRuleError(
                            "MATERIAL_BASE_UOM_REQUIRED", "正式物料尚未维护基本单位。",
                            {"materialId": material_id},
                        )
                    if material.base_uom_id != uom.pk:
                        raise EngineeringRuleError(
                            "MATERIAL_UOM_MISMATCH", "规则输出单位与物料正式基本单位不一致；系统不做隐式换算。",
                            {"materialId": material_id, "materialBaseUomId": material.base_uom_id, "outputUomId": uom.pk},
                        )
                    quantity_basis = str(output_contract.get("quantityBasis") or "").strip()
                    if quantity_basis not in {"PER_SALES_ITEM_UNIT", "ORDER_TOTAL"}:
                        raise EngineeringRuleError(
                            "QUANTITY_BASIS_REQUIRED", "物料需求规则必须明确PER_SALES_ITEM_UNIT或ORDER_TOTAL数量口径。",
                        )
                    calculated_quantity = Decimal(result["value"])
                    order_quantity = Decimal(sales_item.quantity)
                    net_quantity = (
                        calculated_quantity * order_quantity
                        if quantity_basis == "PER_SALES_ITEM_UNIT" else calculated_quantity
                    )
                    net_quantity = net_quantity.quantize(Decimal("0.000001"))
                    if calculated_quantity <= 0 or net_quantity <= 0:
                        raise EngineeringRuleError("INVALID_DECIMAL", "物料需求数量必须大于0。")
                    scrap_rate_raw = output_contract.get("scrapRate")
                    scrap_rate = None
                    gross_quantity = None
                    scrap_status = "not_maintained"
                    if scrap_rate_raw is not None:
                        scrap_rate = Decimal(str(scrap_rate_raw))
                        if scrap_rate < 0 or scrap_rate >= 1:
                            raise EngineeringRuleError("INVALID_SCRAP_RATE", "损耗率必须在0（含）到1（不含）之间。")
                        scrap_status = "maintained"
                        gross_quantity = net_quantity / (Decimal("1") - scrap_rate)
                        gross_quantity = gross_quantity.quantize(Decimal("0.000001"))
                    output_metadata = {
                        "material": material,
                        "quantityBasis": quantity_basis,
                        "calculatedQuantity": calculated_quantity,
                        "orderQuantity": order_quantity,
                        "netQuantity": net_quantity,
                        "grossQuantity": gross_quantity,
                        "itemRole": str(output_contract.get("itemRole") or "material"),
                        "requirementType": str(output_contract.get("requirementType") or "manufacturing"),
                        "supplyType": str(output_contract.get("supplyType") or "BUY"),
                        "orderSpecification": output_contract.get("orderSpecification") or {},
                        "scrapRateStatus": scrap_status,
                        "scrapRate": scrap_rate,
                    }
                    if output_metadata["itemRole"] not in dict(BOMItem.ITEM_ROLE_CHOICES):
                        raise EngineeringRuleError("INVALID_BOM_ITEM_ROLE", "规则声明的BOM结构角色无效。")
                    if output_metadata["requirementType"] not in dict(BOMItem.REQUIREMENT_TYPE_CHOICES):
                        raise EngineeringRuleError("INVALID_BOM_REQUIREMENT_TYPE", "规则声明的BOM需求类型无效。")
                    if output_metadata["supplyType"] not in dict(BOMItem.SUPPLY_TYPE_CHOICES):
                        raise EngineeringRuleError("INVALID_BOM_SUPPLY_TYPE", "规则声明的BOM供给方式无效。")
                elif result["resultDomain"] == "OPERATION_REQUIREMENT":
                    try:
                        operation_id = int(output_contract.get("operationId"))
                    except (TypeError, ValueError):
                        raise EngineeringRuleError(
                            "OPERATION_IDENTITY_REQUIRED", "工序需求规则必须声明正式operationId。",
                        )
                    operation = Process.objects.filter(
                        pk=operation_id, company_id=company_id,
                    ).first()
                    if not operation:
                        raise EngineeringRuleError(
                            "OPERATION_NOT_FOUND", "工序需求规则引用的正式工序不存在或跨公司。",
                            {"operationId": operation_id},
                        )
                    if operation.calculation_uom_id and operation.calculation_uom_id != uom.pk:
                        raise EngineeringRuleError(
                            "OPERATION_UOM_MISMATCH", "规则输出单位与工序正式核算单位不一致。",
                        )
                    workload = Decimal(result["value"])
                    if workload <= 0:
                        raise EngineeringRuleError("INVALID_DECIMAL", "工序作业量必须大于0。")
                    output_metadata = {"operation": operation, "workloadQuantity": workload}
                output_value = {"decimal": result["value"]}
                detail = EngineeringCalculationDetail.objects.create(
                    calculation=calculation,
                    sequence=sequence,
                    rule=rule,
                    rule_code=rule.rule_code,
                    rule_version=rule.version,
                    expression_snapshot=spec["expression"],
                    input_snapshot=_json_safe(rule_inputs),
                    dependency_snapshot=list(spec.get("dependencies", [])),
                    output_name=result["canonicalName"],
                    output_value=output_value,
                    uom=uom,
                    precision=spec["decimalPrecision"],
                    rounding=spec["roundingMode"],
                    status="succeeded",
                    started_at=detail_started,
                    finished_at=timezone.now(),
                )
                pool[result["canonicalName"]] = {
                    "value": result["value"],
                    "unit": result.get("unit"),
                    "unitDimension": result.get("unitDimension"),
                }
                pending_outputs.append((sequence, rule, detail, result, uom, output_value, output_metadata))
            except EngineeringRuleError as exc:
                EngineeringCalculationDetail.objects.create(
                    calculation=calculation,
                    sequence=sequence,
                    rule=rule,
                    rule_code=rule.rule_code,
                    rule_version=rule.version,
                    expression_snapshot=spec["expression"],
                    input_snapshot=_json_safe(rule_inputs),
                    dependency_snapshot=list(spec.get("dependencies", [])),
                    output_name=output_contract["canonicalName"],
                    output_value=None,
                    precision=spec["decimalPrecision"],
                    rounding=spec["roundingMode"],
                    status="failed",
                    error_code=exc.code,
                    error_message=exc.message,
                    started_at=detail_started,
                    finished_at=timezone.now(),
                )
                failed = exc
                break

        finished_at = timezone.now()
        if failed:
            calculation.status = "failed"
            calculation.error_classification = _classification(failed.code)
            calculation.error_code = failed.code
            calculation.error_message = failed.message
            calculation.finished_at = finished_at
            calculation.trace = {
                **calculation.trace,
                "errorSummary": {
                    "code": failed.code,
                    "message": failed.message,
                    "details": failed.details,
                },
                "completedDetailCount": calculation.details.filter(status="succeeded").count(),
            }
            calculation.save(update_fields=[
                "status", "error_classification", "error_code", "error_message",
                "finished_at", "trace", "updated_at",
            ])
        else:
            result_snapshot = []
            for sequence, rule, detail, result, uom, output_value, metadata in pending_outputs:
                trace = {
                    "ruleCode": rule.rule_code,
                    "ruleVersion": rule.version,
                    "detailId": detail.pk,
                    "specificationHash": result["specificationHash"],
                    "resultDomain": result["resultDomain"],
                }
                if result["resultDomain"] == "DERIVED_FACT":
                    fact = EngineeringDerivedFact(
                        calculation=calculation, source_detail=detail, rule=rule,
                        fact_code=result["canonicalName"], canonical_field=result["canonicalName"],
                        sequence=sequence, value=output_value, value_type=result["valueType"],
                        uom=uom, source_type="ENGINEERING_DERIVED", status="active",
                        source_path=f"calculation.details[{sequence}].output", trace=trace,
                    )
                    fact.full_clean()
                    fact.save()
                elif result["resultDomain"] == "MATERIAL_REQUIREMENT":
                    requirement = EngineeringMaterialRequirement(
                        calculation=calculation, source_detail=detail, sequence=sequence,
                        material=metadata["material"], quantity_basis=metadata["quantityBasis"],
                        calculated_quantity=metadata["calculatedQuantity"],
                        order_quantity=metadata["orderQuantity"], net_quantity=metadata["netQuantity"],
                        gross_quantity=metadata["grossQuantity"], uom=uom,
                        item_role=metadata["itemRole"], requirement_type=metadata["requirementType"],
                        supply_type=metadata["supplyType"], order_specification=metadata["orderSpecification"],
                        scrap_rate_status=metadata["scrapRateStatus"], scrap_rate=metadata["scrapRate"],
                        source_path=f"calculation.details[{sequence}].output", trace=trace,
                    )
                    requirement.full_clean()
                    requirement.save()
                else:
                    requirement = EngineeringOperationRequirement(
                        calculation=calculation, source_detail=detail, sequence=sequence,
                        operation=metadata["operation"], workload_quantity=metadata["workloadQuantity"],
                        uom=uom, source_path=f"calculation.details[{sequence}].output", trace=trace,
                    )
                    requirement.full_clean()
                    requirement.save()
                result_snapshot.append({
                    "canonicalField": result["canonicalName"],
                    "value": output_value,
                    "uomId": uom.pk if uom else None,
                    "uomCode": uom.code if uom else None,
                    "detailId": detail.pk,
                    "resultDomain": result["resultDomain"],
                })
            golden_comparison = _golden_validation(
                source, canonical_snapshot, result_snapshot,
            )
            calculation.result_hash = _hash(result_snapshot)
            calculation.status = "completed"
            calculation.error_classification = "none"
            calculation.finished_at = finished_at
            calculation.trace = {
                **calculation.trace,
                "resultSnapshot": result_snapshot,
                "resultHash": calculation.result_hash,
                "goldenComparison": golden_comparison,
            }
            calculation.save(update_fields=[
                "result_hash", "status", "error_classification",
                "finished_at", "trace", "updated_at",
            ])
            if previous and previous.status == "completed":
                EngineeringCalculationRecord.objects.filter(pk=previous.pk).update(status="superseded")
                EngineeringDerivedFact.objects.filter(
                    calculation=previous, status="active",
                ).update(status="superseded")
            if engineering_instance and engineering_instance.status == "source_confirmed":
                OrderEngineeringInstance.objects.filter(pk=engineering_instance.pk).update(
                    status="calculated", updated_at=timezone.now(),
                )

        after = _snapshot(calculation)
        after.update({
            "source_record_id": source.pk,
            "rule_set_version": rule_set_version,
            "input_hash": input_hash,
            "rule_graph_hash": rule_graph_hash,
            "result_hash": calculation.result_hash,
            "decision": "SUCCEEDED" if calculation.status == "completed" else "FAILED",
            "operator": execution_chain["account"],
        })
        audit = _audit(
            user=user,
            organization_id=company_id,
            action_code="production.engineering.calculation.execute",
            instance=calculation,
            before={},
            after=after,
            reason=reason or f"{scope}工程计算执行",
            authorization=decision,
            execution_chain=execution_chain,
        )
        return {
            "calculation": serialize_calculation(calculation),
            "idempotent": False,
            "auditId": audit.pk,
            "authorization": decision,
            "executionChain": execution_chain,
        }


class EngineeringMethodTrialService:
    """Non-production, zero-write evaluation of draft calculation methods.

    Candidate rules remain EngineeringRuleDefinition rows with ``draft`` status.
    The same safe Decimal expression engine used by formal calculations is used,
    while results are deliberately not persisted as calculation facts or demands.
    """

    CANDIDATE_EVIDENCE_STATUS = "CANDIDATE_METHOD"

    @classmethod
    def _candidate_rules(cls, *, company_id, rule_ids=None):
        queryset = EngineeringRuleDefinition.objects.filter(company_id=company_id, status="draft")
        if rule_ids is not None:
            try:
                requested = [int(value) for value in rule_ids]
            except (TypeError, ValueError):
                raise EngineeringCalculationError("CANDIDATE_RULE_SET_REQUIRED", "候选方法ID必须为整数。")
            if not requested or len(requested) != len(set(requested)):
                raise EngineeringCalculationError("CANDIDATE_RULE_SET_REQUIRED", "必须明确选择不重复的候选方法。")
            queryset = queryset.filter(pk__in=requested)
        rows = []
        for rule in queryset.order_by("rule_code", "version"):
            evidence = (rule.specification or {}).get("sourceEvidence") or {}
            if evidence.get("verificationStatus") == cls.CANDIDATE_EVIDENCE_STATUS:
                rows.append(rule)
        if rule_ids is not None and len(rows) != len(requested):
            raise EngineeringCalculationError(
                "CANDIDATE_RULE_NOT_AVAILABLE",
                "所选规则不是当前组织可试算的draft候选方法。",
            )
        return rows

    @classmethod
    def list_methods(cls, *, user):
        EngineeringCalculationService._authorize(
            user=user,
            action_code="production.engineering.calculation.view",
            company_id=user.company_id,
        )
        rows = []
        for rule in cls._candidate_rules(company_id=user.company_id):
            spec = rule.specification
            output = spec["outputs"][0]
            rows.append({
                "id": rule.pk,
                "ruleCode": rule.rule_code,
                "ruleName": rule.rule_name,
                "version": rule.version,
                "status": rule.status,
                "methodStatus": "试算，待业务确认",
                "expression": spec["expression"],
                "inputs": [row["canonicalName"] for row in spec["inputs"]],
                "output": output["canonicalName"],
                "outputLabel": CANONICAL_FIELD_LABELS.get(output["canonicalName"], output["canonicalName"]),
                "outputUnit": output.get("unit"),
                "applicability": spec.get("applicability") or {},
                "sourceEvidence": (spec.get("sourceEvidence") or {}).get("reference"),
                "rounding": spec.get("roundingMode"),
                "outputScale": spec.get("outputScale"),
            })
        return rows

    @classmethod
    def execute(cls, *, user, sales_order_item_id, engineering_instance_id, source_record_id, rule_ids):
        if os.environ.get("PCE_NON_PRODUCTION_ACCEPTANCE", "0") != "1":
            raise EngineeringCalculationError(
                "NON_PRODUCTION_TRIAL_REQUIRED",
                "候选方法只能在已声明的非生产验收环境试算。",
            )
        item = SalesOrderItem.objects.select_related("sales_order").filter(pk=sales_order_item_id).first()
        instance = OrderEngineeringInstance.objects.select_related("source_record", "product__category").filter(
            pk=engineering_instance_id,
        ).first()
        source = EngineeringSourceRecord.objects.filter(pk=source_record_id).first()
        if not item or not instance or not source:
            raise EngineeringCalculationError("TRIAL_CONTEXT_NOT_FOUND", "候选试算的订单行、工程实例或来源不存在。")
        if (
            item.sales_order.company_id != user.company_id
            or instance.company_id != user.company_id
            or source.company_id != user.company_id
            or instance.sales_order_item_id != item.pk
            or instance.source_record_id != source.pk
        ):
            raise EngineeringCalculationError("TRIAL_CONTEXT_MISMATCH", "候选试算上下文不属于同一组织和工程来源。")
        EngineeringCalculationService._authorize(
            user=user,
            action_code="production.engineering.calculation.view",
            company_id=user.company_id,
        )
        rules = cls._candidate_rules(company_id=user.company_id, rule_ids=rule_ids)
        try:
            ordered_rules = stable_topological_order(rules)
        except EngineeringRuleError as exc:
            raise EngineeringCalculationError(exc.code, exc.message, exc.details)

        latest = EngineeringCalculationRecord.objects.filter(
            company_id=user.company_id,
            sales_order_item=item,
            engineering_instance=instance,
            source_record=source,
            scope="order_engineering",
            status="completed",
        ).prefetch_related("derived_facts__uom").order_by("-revision", "-pk").first()
        if not latest:
            raise EngineeringCalculationError("COMPLETED_DIMENSION_CALCULATION_REQUIRED", "候选方法试算前须有已完成的尺寸核算。")

        payload = source.source_payload if isinstance(source.source_payload, dict) else {}
        validation = payload.get("methodTrialValidation")
        if not isinstance(validation, dict) or validation.get("status") != "INDEPENDENT_VERIFIED_SOURCE":
            raise EngineeringCalculationError("METHOD_TRIAL_REFERENCE_REQUIRED", "来源未提供独立核对结果，不能宣称试算对账通过。")
        applicability_context = {
            "sourceSheet": (payload.get("goldenValidation") or {}).get("sourceSheet"),
            "structureRole": validation.get("structureRole"),
        }
        for rule in ordered_rules:
            applicability = (rule.specification or {}).get("applicability") or {}
            for key, actual in applicability_context.items():
                expected = applicability.get(key)
                if expected and expected != actual:
                    raise EngineeringCalculationError(
                        "CANDIDATE_METHOD_NOT_APPLICABLE",
                        "候选方法不适用于当前来源结构。",
                        {"ruleCode": rule.rule_code, "field": key, "expected": expected, "actual": actual},
                    )

        pool = _order_inputs(item)
        pool["order_quantity"] = {"value": str(item.quantity), "unitDimension": "dimensionless", "sourceType": "SALES"}
        for fact in latest.derived_facts.filter(status="active"):
            pool[fact.canonical_field or fact.fact_code] = {
                "value": (fact.value or {}).get("decimal"),
                "unit": fact.uom.code if fact.uom_id else None,
                "unitDimension": fact.rule.specification["outputs"][0].get("unitDimension"),
                "sourceType": "ENGINEERING_DERIVED",
            }

        expected_by_field = {
            str(row.get("canonicalField")): row
            for row in validation.get("expectedResults") or []
            if isinstance(row, dict)
        }
        results = []
        for rule in ordered_rules:
            spec = rule.specification
            names = [row["canonicalName"] for row in spec["inputs"]]
            inputs = {name: pool[name] for name in names if name in pool}
            try:
                result = evaluate_specification(spec, inputs)
            except EngineeringRuleError as exc:
                raise EngineeringCalculationError(exc.code, exc.message, {**exc.details, "ruleCode": rule.rule_code})
            if result["resultDomain"] != "DERIVED_FACT":
                raise EngineeringCalculationError(
                    "TRIAL_OUTPUT_DOMAIN_NOT_ALLOWED",
                    "候选试算只允许输出工程派生事实，不得生成物料或工序需求。",
                )
            expected = expected_by_field.get(result["canonicalName"])
            if not expected or expected.get("verificationStatus") != "VERIFIED_RESULT":
                raise EngineeringCalculationError("METHOD_TRIAL_EXPECTED_RESULT_REQUIRED", "候选结果缺少独立核对值。")
            actual_value = Decimal(result["value"])
            expected_value = Decimal(str(expected.get("value")))
            actual_unit = result.get("unit")
            expected_unit = expected.get("unit")
            value_match = actual_value == expected_value
            unit_match = actual_unit == expected_unit
            results.append({
                "ruleId": rule.pk,
                "ruleCode": rule.rule_code,
                "ruleName": rule.rule_name,
                "ruleVersion": rule.version,
                "methodStatus": "试算，待业务确认",
                "outputName": result["canonicalName"],
                "outputLabel": CANONICAL_FIELD_LABELS.get(result["canonicalName"], result["canonicalName"]),
                "systemValue": result["value"],
                "systemUnit": actual_unit,
                "independentValue": str(expected_value),
                "independentUnit": expected_unit,
                "difference": str(actual_value - expected_value),
                "result": "PASS" if value_match and unit_match else "FAIL",
                "expression": spec["expression"],
                "substitution": {name: _json_safe(inputs[name]) for name in names},
                "sourceCell": expected.get("cell"),
                "sourceEvidence": (spec.get("sourceEvidence") or {}).get("reference"),
                "precision": spec["decimalPrecision"],
                "outputScale": spec["outputScale"],
                "rounding": spec["roundingMode"],
            })
            pool[result["canonicalName"]] = {
                "value": result["value"],
                "unit": actual_unit,
                "unitDimension": result.get("unitDimension"),
                "sourceType": "ENGINEERING_DERIVED",
            }
        return {
            "trialStatus": "PASS" if results and all(row["result"] == "PASS" for row in results) else "FAIL",
            "methodStatus": "试算，待业务确认",
            "sourceRecordId": source.pk,
            "sourceCalculationId": latest.pk,
            "sourceCalculationNo": latest.calculation_no,
            "salesOrderItemId": item.pk,
            "orderQuantity": str(item.quantity),
            "comparisonMode": "EXACT_DECIMAL_AND_UOM",
            "expectedResultsUsedAsInputs": False,
            "rows": results,
            "businessWriteSideEffectCount": 0,
            "formalCalculationRecordCreated": False,
            "materialRequirementCreated": False,
            "operationRequirementCreated": False,
            "bomCreated": False,
            "downstreamInterface": {
                "requiredFacts": ["product/component", "operation", "workload quantity and UOM", "process/rule version", "source", "calculation batch"],
                "boundary": "工序工程量不是工时；本次试算不形成产能占用、计划或排程。",
            },
        }


CURRENT_VERSION_NOT_APPLICABLE_MATERIAL_CATEGORIES = (
    "CORE_MATERIAL",
    "FILLER",
    "HIDDEN_INTERNAL_COMPOSITE_LAYER",
    "HIDDEN_INTERNAL_FRAME",
    "INTERNAL_SHAPING_STRUCTURE",
)


def _requirement_design_item_id(requirement, design_item_id_by_no):
    """Resolve immutable requirement provenance without borrowing another object."""
    trace = requirement.trace if isinstance(requirement.trace, dict) else {}
    value = trace.get("designItemId")
    if value is None:
        snapshot = requirement.source_detail.input_snapshot if requirement.source_detail_id else {}
        value = (snapshot.get("object") or {}).get("designItemId") if isinstance(snapshot, dict) else None
    if value is None:
        specification = requirement.order_specification if isinstance(requirement.order_specification, dict) else {}
        value = design_item_id_by_no.get(specification.get("designItemNo"))
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _requirement_structure_role(requirement):
    specification = requirement.order_specification if isinstance(requirement.order_specification, dict) else {}
    trace = requirement.trace if isinstance(requirement.trace, dict) else {}
    return str(specification.get("structureRole") or trace.get("structureRole") or "").strip().upper()


def _saved_result_is_positive(row):
    """Treat a saved dimensional fact as applicable only when its value is positive.

    Older isolated fixtures only declared fact positions, so an omitted value keeps
    the legacy presence-only contract. Persisted result snapshots always carry a
    value and therefore cannot make a zero dimension look like an applicable part.
    """
    if "value" not in row:
        return True
    value = row.get("value")
    if isinstance(value, dict):
        value = value.get("decimal")
    try:
        return Decimal(str(value)) > 0
    except (ArithmeticError, TypeError, ValueError):
        return False


VENEER_FINISH_ROLE_CODES = {"VENEER", "VENEER_FINISH", "FINISH_MATERIAL"}


def _saved_role_evidence(snapshot, role_code):
    """Read an explicit role-evidence envelope from an immutable object snapshot."""
    if not isinstance(snapshot, dict):
        return {}
    envelope = snapshot.get("materialRoleApplicability")
    if isinstance(envelope, dict):
        candidate = envelope.get(role_code)
        if isinstance(candidate, dict):
            return candidate
        if str(envelope.get("roleCode") or "").strip().upper() == role_code:
            return envelope
    if isinstance(envelope, list):
        for candidate in envelope:
            if (
                isinstance(candidate, dict)
                and str(candidate.get("roleCode") or "").strip().upper() == role_code
            ):
                return candidate
    return {}


def _veneer_finish_applicability(target_object, object_requirements):
    """Resolve VENEER_FINISH from saved facts without interpreting display text."""
    inputs = target_object.get("input") if isinstance(target_object, dict) else {}
    inputs = inputs if isinstance(inputs, dict) else {}
    saved = _saved_role_evidence(inputs, "VENEER_FINISH")

    material_evidence = list(saved.get("materialEvidence") or [])
    quantity_evidence = list(saved.get("quantityEvidence") or [])
    requirement_evidence = []
    for requirement in object_requirements:
        if _requirement_structure_role(requirement) not in VENEER_FINISH_ROLE_CODES:
            continue
        requirement_id = getattr(requirement, "pk", None)
        material_evidence.append({
            "status": "CONFIRMED",
            "source": "EngineeringMaterialRequirement",
            "requirementId": requirement_id,
            "materialId": getattr(requirement, "material_id", None),
        })
        quantity_evidence.append({
            "status": "CONFIRMED",
            "source": "EngineeringMaterialRequirement",
            "requirementId": requirement_id,
            "quantity": str(
                getattr(requirement, "net_quantity", None)
                or getattr(requirement, "calculated_quantity", None)
                or ""
            ),
            "uomId": getattr(requirement, "uom_id", None),
        })
        requirement_evidence.append(requirement_id)

    appearance_evidence = list(saved.get("appearanceEvidence") or [])
    finish_or_color = str(inputs.get("finishOrColor") or "").strip()
    if finish_or_color:
        appearance_evidence.append({
            "status": "PRESENT",
            "source": "ProductDesignRevision.design_data.finishOrColor",
            "value": finish_or_color,
        })

    process_evidence = list(saved.get("processEvidence") or [])
    for field in ("paintProcess", "processConfigurationCode", "routingProcessCode"):
        value = str(inputs.get(field) or "").strip()
        if value:
            process_evidence.append({
                "status": "PRESENT",
                "source": f"ProductDesignRevision.{field}",
                "value": value,
            })

    resolution = resolve_material_role_applicability(
        role_code="VENEER_FINISH",
        material_evidence=material_evidence,
        template_evidence=saved.get("templateEvidence"),
        configuration_evidence=saved.get("configurationEvidence"),
        appearance_evidence=appearance_evidence,
        process_evidence=process_evidence,
        quantity_evidence=quantity_evidence,
        rule_evidence=saved.get("ruleEvidence"),
    )
    resolution["designItemId"] = int(target_object["designItemId"])
    resolution["requirementIds"] = [value for value in requirement_evidence if value is not None]
    return resolution


def _paint_process_formal_context(calculation):
    """Read one shared server-side process/routing/capacity fact envelope.

    Unit tests may supply the same contract in the immutable calculation trace.
    Production resolution always comes from the canonical routing/capacity
    models and never from a display label.
    """
    trace = calculation.trace if isinstance(calculation.trace, dict) else {}
    saved = trace.get("paintProcessClosureFacts")
    if (
        isinstance(saved, dict)
        and saved.get("routingStepApplicabilityContractVersion")
        == ROUTING_STEP_APPLICABILITY_CONTRACT_VERSION
    ):
        return saved

    instance_id = getattr(calculation, "engineering_instance_id", None)
    if not instance_id:
        return {
            "process": {"status": "NOT_FOUND"},
            "routing": {"status": "NOT_FOUND", "operationCount": 0},
            "capacity": {"status": INCOMPLETE, "complete": False},
            "operations": [],
            "sourceByObject": {},
        }

    instance = calculation.engineering_instance
    selected_process = getattr(instance, "selected_process_type", None)
    process_fact = {
        "status": "CONFIRMED" if selected_process else "NOT_FOUND",
        "processTypeId": getattr(selected_process, "pk", None),
        "code": getattr(selected_process, "code", None),
        "name": getattr(selected_process, "name", None),
        "source": "OrderEngineeringInstance.selected_process_type",
    }
    source_by_object = {}
    for item in ProductDesignItem.objects.filter(
        sales_order_item_id=calculation.sales_order_item_id,
        source_record_id=calculation.source_record_id,
    ).only("pk", "existing_design_data"):
        values = item.existing_design_data if isinstance(item.existing_design_data, dict) else {}
        source_by_object[item.pk] = {
            "materialProcessCode": values.get("materialProcessCode"),
            "routingProcessCode": values.get("routingProcessCode"),
            "paintProcess": values.get("paintProcess"),
        }

    try:
        resolved = ManufacturingStructureService.resolve_effective_routing(instance)
    except ManufacturingStructureError as exc:
        return {
            "process": process_fact,
            "routing": {
                "status": UNRESOLVED,
                "reasonCode": exc.code,
                "details": exc.details,
                "operationCount": 0,
            },
            "capacity": {"status": INCOMPLETE, "complete": False},
            "operations": [],
            "sourceByObject": source_by_object,
        }

    routing = resolved["routing"]
    version = resolved["routing_version"]
    steps = list(RoutingStep.objects.select_related(
        "operation__workshop", "operation__work_center", "workshop", "work_center",
        "routing_version__routing",
    ).filter(routing_version=version, is_active=True).order_by("sequence", "pk"))
    from .models import CapacityProductType
    from .manufacturing_rule_configuration import _active
    from .operation_workload_source_service import project_operation_sources, restrict_operation_projection
    source_types = [row for row in CapacityProductType.objects.filter(
        company_id=calculation.company_id, code=routing.routing_code,
        product_category_id=routing.product_category_id,
        manufacturing_process_type_id=routing.manufacturing_process_type_id,
    ) if _active(row)]
    source_type_id = source_types[0].pk if len(source_types) == 1 else None
    workload_sources = project_operation_sources(
        [step.operation for step in steps], company_id=calculation.company_id,
        product_type_id=source_type_id,
    )
    workload_sources_by_step = {
        step.pk: restrict_operation_projection(workload_sources[step.operation_id], {
            "routingId": routing.pk, "routingVersionId": version.pk, "routingStepId": step.pk,
        }) for step in steps
    }
    applicability_by_step = {
        row.pk: RoutingStepApplicabilityResolver.resolve(
            row,
            engineering_calculation=calculation,
            order_engineering_instance=instance,
        )
        for row in steps
    }
    required_steps = [
        row for row in steps
        if applicability_by_step[row.pk]["result"] == ROUTING_STEP_REQUIRED
    ]
    operation_ids = {row.operation_id for row in required_steps}
    work_center_ids = {
        value for row in required_steps
        for value in (row.work_center_id, row.operation.work_center_id)
        if value is not None
    }
    capacities = []
    if operation_ids or work_center_ids:
        capacities = list(StandardCapacity.objects.filter(
            company_id=calculation.company_id, is_active=True,
        ).filter(
            models.Q(operation_id__in=operation_ids)
            | models.Q(work_center_id__in=work_center_ids)
            | models.Q(equipment__work_center_id__in=work_center_ids)
        ).select_related("equipment"))
    capacities_by_operation = {}
    capacities_by_work_center = {}
    for row in capacities:
        if row.operation_id:
            capacities_by_operation.setdefault(row.operation_id, []).append(row)
        if row.work_center_id:
            capacities_by_work_center.setdefault(row.work_center_id, []).append(row)
        if row.equipment_id:
            capacities_by_work_center.setdefault(row.equipment.work_center_id, []).append(row)

    operations = []
    for step in steps:
        applicability = applicability_by_step[step.pk]
        workload_source = workload_sources_by_step[step.pk]
        if source_type_id is None:
            workload_source = {**workload_source, "hasValidSourceConfiguration": False,
                "statusCode": "PRODUCT_TYPE_SCOPE_UNPROVEN",
                "statusLabel": "当前路线的产能产品类型尚未唯一确认"}
        workshop = step.workshop or step.operation.workshop
        work_center = step.work_center or step.operation.work_center
        capacity_rows = []
        if applicability["result"] == ROUTING_STEP_REQUIRED:
            capacity_rows = list(capacities_by_operation.get(step.operation_id, []))
        if work_center and applicability["result"] == ROUTING_STEP_REQUIRED:
            capacity_rows.extend(capacities_by_work_center.get(work_center.pk, []))
        capacity_rows = list({row.pk: row for row in capacity_rows}.values())
        ready_capacity_rows = [
            row for row in capacity_rows
            if row.measurement_status == StandardCapacity.MeasurementStatus.MEASURED
            and row.quantity is not None
            and (
                row.standard_hours is not None
                or (
                    row.time_basis != StandardCapacity.TimeBasis.NOT_MAINTAINED
                    and row.time_basis_quantity is not None
                )
            )
        ]
        operations.append({
            "stepId": step.pk,
            "sequence": step.sequence,
            "operationId": step.operation_id,
            "operationCode": step.operation.code,
            "operationName": step.operation.name,
            "applicability": applicability,
            "capacityDemandEvaluated": applicability["result"] == ROUTING_STEP_REQUIRED,
            "workshopId": workshop.pk if workshop else None,
            "workshopCode": workshop.code if workshop else None,
            "workshopName": workshop.name if workshop else None,
            "workCenterId": work_center.pk if work_center else None,
            "workCenterCode": work_center.code if work_center else None,
            "workCenterName": work_center.name if work_center else None,
            "standardHours": str(
                step.standard_hours
                if step.standard_hours is not None
                else step.operation.standard_hours
            ) if (
                step.standard_hours is not None or step.operation.standard_hours is not None
            ) else None,
            "calculationBasis": step.operation.calculation_basis,
            "calculationUomId": step.operation.calculation_uom_id,
            "quantityDriver": step.operation.quantity_driver,
            "workloadSource": workload_source,
            "capacityFactIds": [row.pk for row in capacity_rows],
            "readyCapacityFactIds": [row.pk for row in ready_capacity_rows],
        })

    step_count = len(operations)
    required_operations = [
        row for row in operations
        if row["applicability"]["result"] == ROUTING_STEP_REQUIRED
    ]
    not_applicable_operations = [
        row for row in operations
        if row["applicability"]["result"] == ROUTING_STEP_NOT_APPLICABLE
    ]
    pending_operations = [
        row for row in operations
        if row["applicability"]["result"] == ROUTING_STEP_PENDING
    ]
    required_step_count = len(required_operations)
    steps_with_workshop = sum(row["workshopId"] is not None for row in required_operations)
    steps_with_work_center = sum(row["workCenterId"] is not None for row in required_operations)
    steps_with_standard_time = sum(row["standardHours"] is not None for row in required_operations)
    steps_with_workload_driver = sum(
        row["workloadSource"]["hasValidSourceConfiguration"] for row in required_operations
    )
    steps_with_capacity = sum(bool(row["capacityFactIds"]) for row in required_operations)
    steps_with_ready_capacity = sum(bool(row["readyCapacityFactIds"]) for row in required_operations)
    operation_requirement_count = calculation.operation_requirements.count()
    capacity_complete = bool(required_step_count) and not pending_operations and all((
        steps_with_workshop == required_step_count,
        steps_with_work_center == required_step_count,
        steps_with_workload_driver == required_step_count,
        steps_with_standard_time == required_step_count,
        steps_with_ready_capacity == required_step_count,
        len(capacities) > 0,
        operation_requirement_count > 0,
    ))
    capacity_fact = {
        "status": READY if capacity_complete else INCOMPLETE,
        "complete": capacity_complete,
        "stepCount": step_count,
        "requiredStepCount": required_step_count,
        "notApplicableStepCount": len(not_applicable_operations),
        "pendingApplicabilityStepCount": len(pending_operations),
        "stepsWithWorkshop": steps_with_workshop,
        "stepsWithWorkCenter": steps_with_work_center,
        "stepsWithWorkloadDriver": steps_with_workload_driver,
        "stepsWithStandardTime": steps_with_standard_time,
        "stepsWithCapacityFact": steps_with_capacity,
        "stepsWithReadyCapacityFact": steps_with_ready_capacity,
        "standardCapacityFactCount": len(capacities),
        "operationRequirementCount": operation_requirement_count,
        "pendingApplicabilitySequences": [row["sequence"] for row in pending_operations],
        "missingWorkshopSequences": [row["sequence"] for row in required_operations if not row["workshopId"]],
        "missingWorkCenterSequences": [
            row["sequence"] for row in required_operations
            if not row["workCenterId"]
        ],
        "missingWorkloadDriverSequences": [
            row["sequence"] for row in required_operations
            if not row["workloadSource"]["hasValidSourceConfiguration"]
        ],
        "missingStandardTimeSequences": [
            row["sequence"] for row in required_operations
            if not row["standardHours"]
        ],
        "missingStandardCapacitySequences": [
            row["sequence"] for row in required_operations
            if not row["readyCapacityFactIds"]
        ],
    }
    return {
        "process": process_fact,
        "routing": {
            "status": READY,
            "routingId": routing.pk,
            "routingCode": routing.routing_code,
            "routingName": routing.name,
            "routingVersionId": version.pk,
            "routingVersion": version.routing_version,
            "resolvedScope": resolved["resolved_scope"],
            "operationCount": step_count,
        },
        "capacity": capacity_fact,
        "operations": operations,
        "routingStepApplicabilityContractVersion": ROUTING_STEP_APPLICABILITY_CONTRACT_VERSION,
        "sourceByObject": source_by_object,
    }


def _paint_process_applicability(target_object, object_requirements, formal_context):
    inputs = target_object.get("input") if isinstance(target_object, dict) else {}
    inputs = inputs if isinstance(inputs, dict) else {}
    design_item_id = int(target_object["designItemId"])
    source = (formal_context.get("sourceByObject") or {}).get(design_item_id, {})
    routing_fact = dict(formal_context.get("routing") or {})
    saved_routing_code = str(
        inputs.get("routingProcessCode")
        or inputs.get("processConfigurationCode")
        or source.get("routingProcessCode")
        or ""
    ).strip()
    formal_routing_code = str(routing_fact.get("routingCode") or "").strip()
    if saved_routing_code and formal_routing_code and saved_routing_code != formal_routing_code:
        routing_fact["status"] = "CONFLICT"
        routing_fact["savedRoutingCode"] = saved_routing_code

    process = resolve_process_applicability(
        process_fact=formal_context.get("process"), routing_fact=routing_fact,
    )
    routing = resolve_routing_readiness(
        process_status=process["status"], routing_fact=routing_fact,
    )
    capacity = resolve_capacity_readiness(
        process_status=process["status"], routing_status=routing["status"],
        capacity_fact=formal_context.get("capacity"),
    )

    saved_material = _saved_role_evidence(inputs, "PAINT_PROCESS_MATERIAL")
    material_evidence = list(saved_material.get("materialEvidence") or [])
    recipe_evidence = list(saved_material.get("recipeEvidence") or [])
    consumption_evidence = list(saved_material.get("consumptionEvidence") or [])
    requirement_ids = []
    for requirement in object_requirements:
        if _requirement_structure_role(requirement) not in PAINT_MATERIAL_ROLE_CODES:
            continue
        requirement_id = getattr(requirement, "pk", None)
        trace = requirement.trace if isinstance(requirement.trace, dict) else {}
        requirement_ids.append(requirement_id)
        material_evidence.append({
            "status": "CONFIRMED",
            "source": "EngineeringMaterialRequirement",
            "requirementId": requirement_id,
            "materialId": getattr(requirement, "material_id", None),
        })
        recipe_evidence.append({
            "status": "CONFIRMED",
            "source": "EngineeringMaterialRequirement.trace",
            "requirementId": requirement_id,
            "ruleId": trace.get("mappingRuleId") or trace.get("ruleId") or requirement_id,
        })
        consumption_evidence.append({
            "status": "CONFIRMED",
            "source": "EngineeringMaterialRequirement",
            "requirementId": requirement_id,
            "quantity": str(
                getattr(requirement, "net_quantity", None)
                or getattr(requirement, "calculated_quantity", None)
                or ""
            ),
            "formula": trace.get("quantityExpression") or trace.get("formula"),
            "uomId": getattr(requirement, "uom_id", None),
        })
    material = resolve_paint_material_applicability(
        material_evidence=material_evidence,
        recipe_evidence=recipe_evidence,
        consumption_evidence=consumption_evidence,
    )
    return {
        "designItemId": design_item_id,
        "designItemNo": target_object.get("designItemNo"),
        "paintProcess": inputs.get("paintProcess") or source.get("paintProcess"),
        "materialProcessCode": inputs.get("materialProcessCode") or source.get("materialProcessCode"),
        "routingProcessCode": saved_routing_code or None,
        "process": process,
        "routing": routing,
        "capacity": capacity,
        "material": material,
        "operations": list(formal_context.get("operations") or []),
        "materialRequirementIds": [value for value in requirement_ids if value is not None],
    }


def _current_version_material_completeness(
    calculation, requirements, *, workflow_stage=MATERIAL_BOM_GENERATION_STAGE,
):
    """Fail-closed, evidence-led completeness for object-aware BOM calculations.

    Calculations created before object snapshots existed keep their original service
    contract. Object-aware calculations must prove every applicable current-version
    material category from saved facts; order coverage and admission mode are not
    inputs to this resolver.
    """
    trace = calculation.trace if isinstance(calculation.trace, dict) else {}
    snapshots = trace.get("objectInputSnapshot")
    results = trace.get("resultSnapshot")
    if not isinstance(snapshots, list) or not isinstance(results, list):
        return {
            "contractCode": "PCE-CURRENT-VERSION-MATERIAL-COMPLETENESS-V1",
            "applicable": False,
            "complete": True,
            "status": "OBJECT_AWARE_SCOPE_NOT_APPLICABLE",
            "workflowStage": workflow_stage,
            "evaluatedCategories": [],
            "notApplicableCategories": list(CURRENT_VERSION_NOT_APPLICABLE_MATERIAL_CATEGORIES),
            "firstRealBlocker": None,
        }

    target_objects = [row for row in snapshots if row.get("designItemId") is not None]
    if not target_objects:
        return {
            "contractCode": "PCE-CURRENT-VERSION-MATERIAL-COMPLETENESS-V1",
            "applicable": False,
            "complete": True,
            "status": "OBJECT_AWARE_SCOPE_NOT_APPLICABLE",
            "workflowStage": workflow_stage,
            "evaluatedCategories": [],
            "notApplicableCategories": list(CURRENT_VERSION_NOT_APPLICABLE_MATERIAL_CATEGORIES),
            "firstRealBlocker": None,
        }

    target_ids = {int(row["designItemId"]) for row in target_objects}
    design_item_id_by_no = {
        row.get("designItemNo"): int(row["designItemId"])
        for row in target_objects if row.get("designItemNo")
    }
    facts_by_object = {object_id: set() for object_id in target_ids}
    positive_facts_by_object = {object_id: set() for object_id in target_ids}
    for row in results:
        try:
            object_id = int(row.get("designItemId"))
        except (TypeError, ValueError):
            continue
        if object_id in facts_by_object:
            fact_code = str(row.get("canonicalField") or "").upper()
            facts_by_object[object_id].add(fact_code)
            if _saved_result_is_positive(row):
                positive_facts_by_object[object_id].add(fact_code)

    roles_by_object = {object_id: set() for object_id in target_ids}
    requirements_by_object = {object_id: [] for object_id in target_ids}
    covered_object_ids = set()
    for requirement in requirements:
        object_id = _requirement_design_item_id(requirement, design_item_id_by_no)
        if object_id not in target_ids:
            continue
        covered_object_ids.add(object_id)
        requirements_by_object[object_id].append(requirement)
        role = _requirement_structure_role(requirement)
        if role:
            roles_by_object[object_id].add(role)

    independent_edge_not_required_ids = {
        object_id
        for object_id, object_requirements in requirements_by_object.items()
        if any(
            _requirement_structure_role(requirement) == "MAIN_PANEL_WITH_TRIM"
            and isinstance(requirement.order_specification, dict)
            and requirement.order_specification.get("separateEdgeMaterial") is False
            for requirement in object_requirements
        )
    }

    categories = (
        {
            "code": "DOOR_LEAF_SURFACE_PANEL",
            "statusLabel": "门扇表面板材",
            "applicableObjects": {
                object_id for object_id, facts in positive_facts_by_object.items()
                if {"R", "S", "U"}.issubset(facts)
            },
            "roles": {"DOOR_LEAF_SURFACE_PANEL"},
            "evidenceFactCodes": ["R", "S", "U"],
            "missingCode": "DOOR_LEAF_SURFACE_PANEL_REQUIREMENT_MISSING",
        },
        {
            "code": "CASING_MATERIAL",
            "statusLabel": "门套材料",
            "applicableObjects": {
                object_id for object_id, facts in facts_by_object.items()
                if {"N", "O", "P", "Q"}.issubset(facts) or "X" in facts
            },
            "roles": {
                "CASING_MATERIAL", "DOOR_CASING_MATERIAL",
                "DOOR_CASING_FRAME_MATERIAL", "MAIN_PANEL_WITH_TRIM",
            },
            "evidenceFactCodes": ["N", "O", "P", "Q", "X"],
            "missingCode": "CASING_MATERIAL_REQUIREMENT_MISSING",
        },
        {
            "code": "CASING_TRIM",
            "statusLabel": "门套线条材料",
            "applicableObjects": {
                object_id for object_id, facts in facts_by_object.items()
                if facts.intersection({"AT", "AU", "AV", "AW", "AX", "AY"})
            },
            "roles": {
                "CASING_TRIM", "DOOR_CASING_TRIM", "TRIM_MATERIAL",
                "MAIN_PANEL_WITH_TRIM",
            },
            "evidenceFactCodes": ["AT", "AU", "AV", "AW", "AX", "AY"],
            "missingCode": "CASING_TRIM_REQUIREMENT_MISSING",
        },
        {
            "code": "EDGE_BANDING",
            "statusLabel": "封边材料",
            "applicableObjects": {
                object_id for object_id, facts in facts_by_object.items()
                if (
                    facts.intersection({"Z", "AA"})
                    and object_id not in independent_edge_not_required_ids
                )
            },
            "roles": {"EDGE_BANDING", "EDGE_BANDING_MATERIAL"},
            "evidenceFactCodes": ["Z", "AA"],
            "missingCode": "EDGE_BANDING_REQUIREMENT_MISSING",
        },
        {
            "code": "VENEER_FINISH",
            "statusLabel": "木皮/饰面材料",
            "applicabilityByObject": {
                int(row["designItemId"]): _veneer_finish_applicability(
                    row, requirements_by_object[int(row["designItemId"])],
                )
                for row in target_objects
            },
            "roles": VENEER_FINISH_ROLE_CODES,
            "evidenceFactCodes": ["materialRoleApplicability"],
            "missingCode": "VENEER_FINISH_REQUIREMENT_MISSING",
        },
    )

    paint_formal_context = _paint_process_formal_context(calculation)
    paint_by_object = {
        int(row["designItemId"]): _paint_process_applicability(
            row,
            requirements_by_object[int(row["designItemId"])],
            paint_formal_context,
        )
        for row in target_objects
    }

    evaluated = []
    not_applicable_categories = list(CURRENT_VERSION_NOT_APPLICABLE_MATERIAL_CATEGORIES)
    first_blocker = None
    if covered_object_ids != target_ids:
        missing_ids = sorted(target_ids - covered_object_ids)
        first_blocker = {
            "code": "TARGET_BOM_REQUIREMENT_COVERAGE_INCOMPLETE",
            "statusLabel": "目标BOM对象Requirement覆盖不完整",
            "message": f"目标主体仍有{len(missing_ids)}个Design Item没有任何正式材料需求。",
            "missingDesignItemIds": missing_ids,
        }
    else:
        for category in categories:
            applicability_by_object = category.get("applicabilityByObject")
            if applicability_by_object is not None:
                applicable_ids = {
                    object_id for object_id, row in applicability_by_object.items()
                    if row["status"] == APPLICABLE
                }
                not_applicable_ids = {
                    object_id for object_id, row in applicability_by_object.items()
                    if row["status"] == NOT_APPLICABLE
                }
                unresolved_ids = sorted(
                    object_id for object_id, row in applicability_by_object.items()
                    if row["status"] == UNRESOLVED
                )
                covered_ids = {
                    object_id for object_id in applicable_ids
                    if roles_by_object[object_id].intersection(category["roles"])
                }
                category_result = {
                    "code": category["code"],
                    "roleCode": category["code"],
                    "statusLabel": category["statusLabel"],
                    "applicableDesignItemCount": len(applicable_ids),
                    "notApplicableDesignItemCount": len(not_applicable_ids),
                    "unresolvedDesignItemCount": len(unresolved_ids),
                    "requirementDesignItemCount": len(covered_ids),
                    "coveredDesignItemCount": len(covered_ids),
                    "evidenceFactCodes": category["evidenceFactCodes"],
                    "applicabilityByObject": [
                        applicability_by_object[object_id]
                        for object_id in sorted(applicability_by_object)
                    ],
                }
                if unresolved_ids:
                    category_result["status"] = "APPLICABILITY_UNRESOLVED"
                    evaluated.append(category_result)
                    if first_blocker is None:
                        first_blocker = {
                            "code": "APPLICABILITY_UNRESOLVED",
                            "statusLabel": f"{category['statusLabel']}适用性尚未解析",
                            "message": (
                                f"{category['statusLabel']}存在不完整、冲突或歧义的正式适用性证据；"
                                "系统拒绝猜测Material Requirement。"
                            ),
                            "category": category["code"],
                            "unresolvedDesignItemIds": unresolved_ids,
                            "applicabilityByObject": category_result["applicabilityByObject"],
                        }
                    continue
                if not applicable_ids:
                    category_result["status"] = "NOT_APPLICABLE"
                    evaluated.append(category_result)
                    not_applicable_categories.append(category["code"])
                    continue
            else:
                applicable_ids = category["applicableObjects"]
            if not applicable_ids:
                continue
            covered_ids = {
                object_id for object_id in applicable_ids
                if roles_by_object[object_id].intersection(category["roles"])
            }
            missing_ids = sorted(applicable_ids - covered_ids)
            if applicability_by_object is not None:
                category_result.update({
                    "requirementDesignItemCount": len(covered_ids),
                    "coveredDesignItemCount": len(covered_ids),
                    "status": "COMPLETE" if not missing_ids else "MISSING_REQUIREMENT",
                })
                evaluated.append(category_result)
            else:
                evaluated.append({
                    "code": category["code"],
                    "statusLabel": category["statusLabel"],
                    "applicableDesignItemCount": len(applicable_ids),
                    "coveredDesignItemCount": len(covered_ids),
                    "evidenceFactCodes": category["evidenceFactCodes"],
                    "status": "COMPLETE" if not missing_ids else "MISSING_REQUIREMENT",
                })
            if missing_ids:
                if first_blocker is None:
                    first_blocker = {
                        "code": category["missingCode"],
                        "statusLabel": f"{category['statusLabel']}Requirement尚未形成",
                        "message": (
                            f"保存的当前版本事实已证明{category['statusLabel']}适用，"
                            "但目标对象没有对应结构角色的正式Material Requirement；不猜定物料或规格。"
                        ),
                        "category": category["code"],
                        "missingDesignItemIds": missing_ids,
                        "evidenceFactCodes": category["evidenceFactCodes"],
                    }

    process_applicable_ids = {
        object_id for object_id, row in paint_by_object.items()
        if row["process"]["status"] == APPLICABLE
    }
    process_not_applicable_ids = {
        object_id for object_id, row in paint_by_object.items()
        if row["process"]["status"] == NOT_APPLICABLE
    }
    process_unresolved_ids = sorted(
        object_id for object_id, row in paint_by_object.items()
        if row["process"]["status"] == UNRESOLVED
    )
    routing_incomplete_ids = sorted(
        object_id for object_id in process_applicable_ids
        if paint_by_object[object_id]["routing"]["status"] != READY
    )
    process_status = (
        "APPLICABILITY_UNRESOLVED" if process_unresolved_ids else
        "NOT_APPLICABLE" if not process_applicable_ids else
        "APPLICABLE"
    )
    process_result = {
        "code": "PAINT_PROCESS",
        "statusLabel": "油漆/表面工艺适用性",
        "applicableDesignItemCount": len(process_applicable_ids),
        "notApplicableDesignItemCount": len(process_not_applicable_ids),
        "unresolvedDesignItemCount": len(process_unresolved_ids),
        "coveredDesignItemCount": len(process_applicable_ids),
        "status": process_status,
        "evidenceFactCodes": ["selectedProcessType", "formalRouting"],
        "applicabilityByObject": [{
            "designItemId": object_id,
            "designItemNo": paint_by_object[object_id]["designItemNo"],
            "paintProcess": paint_by_object[object_id]["paintProcess"],
            "materialProcessCode": paint_by_object[object_id]["materialProcessCode"],
            "routingProcessCode": paint_by_object[object_id]["routingProcessCode"],
            "process": paint_by_object[object_id]["process"],
        } for object_id in sorted(paint_by_object)],
    }
    evaluated.append(process_result)
    if process_status == "NOT_APPLICABLE":
        not_applicable_categories.append("PAINT_PROCESS")
    elif process_unresolved_ids and first_blocker is None:
        first_blocker = {
            "code": "PAINT_PROCESS_APPLICABILITY_UNRESOLVED",
            "statusLabel": "油漆/表面工艺适用性尚未解析",
            "message": "正式Process或Routing事实存在冲突/歧义；系统拒绝猜测工艺适用性。",
            "category": "PAINT_PROCESS",
            "unresolvedDesignItemIds": process_unresolved_ids,
        }

    routing_status = (
        UNRESOLVED if process_unresolved_ids else
        NOT_APPLICABLE if not process_applicable_ids else
        INCOMPLETE if routing_incomplete_ids else
        READY
    )
    routing_result = {
        "code": "PAINT_PROCESS_ROUTING",
        "statusLabel": "油漆/表面工艺Routing",
        "applicableDesignItemCount": len(process_applicable_ids),
        "notApplicableDesignItemCount": len(process_not_applicable_ids),
        "unresolvedDesignItemCount": len(process_unresolved_ids),
        "coveredDesignItemCount": len(process_applicable_ids) - len(routing_incomplete_ids),
        "status": routing_status,
        "evidenceFactCodes": ["formalRouting", "routingOperations"],
        "readinessByObject": [{
            "designItemId": object_id,
            "designItemNo": paint_by_object[object_id]["designItemNo"],
            "routing": paint_by_object[object_id]["routing"],
            "operations": paint_by_object[object_id]["operations"],
        } for object_id in sorted(paint_by_object)],
    }
    evaluated.append(routing_result)
    if routing_status == NOT_APPLICABLE:
        not_applicable_categories.append("PAINT_PROCESS_ROUTING")
    elif routing_incomplete_ids and first_blocker is None:
        first_blocker = {
            "code": "PAINT_PROCESS_ROUTING_FACT_MISSING",
            "statusLabel": "油漆/表面工艺Routing事实不完整",
            "message": "工艺适用，但未形成唯一有效Routing及正式Operation清单。",
            "category": "PAINT_PROCESS_ROUTING",
            "missingDesignItemIds": routing_incomplete_ids,
        }

    capacity_gate_by_object = {
        object_id: resolve_capacity_stage_gate(
            process_status=paint_by_object[object_id]["process"]["status"],
            routing_status=paint_by_object[object_id]["routing"]["status"],
            capacity_readiness=paint_by_object[object_id]["capacity"],
            workflow_stage=workflow_stage,
        )
        for object_id in paint_by_object
    }
    capacity_incomplete_ids = sorted(
        object_id for object_id in process_applicable_ids
        if paint_by_object[object_id]["capacity"]["status"] != READY
    )
    capacity_deferred_ids = sorted(
        object_id for object_id, row in capacity_gate_by_object.items()
        if row["status"] == DEFERRED
    )
    capacity_blocked_ids = sorted(
        object_id for object_id, row in capacity_gate_by_object.items()
        if row["status"] == BLOCKED
    )
    capacity_status = (
        "NOT_APPLICABLE" if not process_applicable_ids else
        BLOCKED if capacity_blocked_ids else
        DEFERRED if capacity_deferred_ids else
        "READY"
    )
    capacity_result = {
        "code": "PAINT_PROCESS_CAPACITY",
        "statusLabel": "油漆/表面工艺产能",
        "applicableDesignItemCount": len(process_applicable_ids),
        "notApplicableDesignItemCount": len(process_not_applicable_ids),
        "coveredDesignItemCount": len(process_applicable_ids) - len(capacity_incomplete_ids),
        "status": capacity_status,
        "actualCapacityReadiness": (
            INCOMPLETE if capacity_incomplete_ids else
            NOT_APPLICABLE if not process_applicable_ids else
            READY
        ),
        "workflowStage": workflow_stage,
        "capacityRequiredForCurrentStage": any(
            row["capacityRequiredForCurrentStage"]
            for row in capacity_gate_by_object.values()
        ),
        "capacityRequiredForLaterManufacturingStage": any(
            row["capacityRequiredForLaterManufacturingStage"]
            for row in capacity_gate_by_object.values()
        ),
        "evidenceFactCodes": [
            "operation", "workshop", "workCenter", "workloadDriver", "standardTime",
            "standardCapacity", "operationRequirement",
        ],
        "readinessByObject": [{
            "designItemId": object_id,
            "designItemNo": paint_by_object[object_id]["designItemNo"],
            "capacity": paint_by_object[object_id]["capacity"],
            "stageGate": capacity_gate_by_object[object_id],
        } for object_id in sorted(paint_by_object)],
    }
    evaluated.append(capacity_result)
    if capacity_status == "NOT_APPLICABLE":
        not_applicable_categories.append("PAINT_PROCESS_CAPACITY")
    elif capacity_blocked_ids and first_blocker is None:
        first_blocker = {
            "code": "PAINT_PROCESS_CAPACITY_FACT_MISSING",
            "statusLabel": "油漆/表面工艺产能事实不完整",
            "message": (
                f"当前流程阶段{workflow_stage}要求产能事实，但Workshop/Work Center/"
                "Workload Driver/Standard Time/Capacity/Operation Requirement事实不足；"
                "系统Fail Closed且不得猜建。"
            ),
            "category": "PAINT_PROCESS_CAPACITY",
            "missingDesignItemIds": capacity_blocked_ids,
            "capacityByObject": capacity_result["readinessByObject"],
        }

    material_applicable_ids = {
        object_id for object_id, row in paint_by_object.items()
        if row["material"]["status"] == APPLICABLE
    }
    material_not_applicable_ids = {
        object_id for object_id, row in paint_by_object.items()
        if row["material"]["status"] == NOT_APPLICABLE
    }
    material_unresolved_ids = sorted(
        object_id for object_id, row in paint_by_object.items()
        if row["material"]["status"] == UNRESOLVED
    )
    material_covered_ids = {
        object_id for object_id in material_applicable_ids
        if roles_by_object[object_id].intersection(PAINT_MATERIAL_ROLE_CODES)
    }
    material_missing_requirement_ids = sorted(material_applicable_ids - material_covered_ids)
    material_status = (
        "APPLICABILITY_UNRESOLVED" if material_unresolved_ids else
        "NOT_APPLICABLE" if not material_applicable_ids else
        "MISSING_REQUIREMENT" if material_missing_requirement_ids else
        "COMPLETE"
    )
    material_result = {
        "code": "PAINT_PROCESS_MATERIAL",
        "statusLabel": "油漆/表面工艺物理耗用材料",
        "applicableDesignItemCount": len(material_applicable_ids),
        "notApplicableDesignItemCount": len(material_not_applicable_ids),
        "unresolvedDesignItemCount": len(material_unresolved_ids),
        "requirementDesignItemCount": len(material_covered_ids),
        "coveredDesignItemCount": len(material_covered_ids),
        "status": material_status,
        "evidenceFactCodes": ["materialIdentity", "recipeRule", "consumptionFormula", "uom"],
        "applicabilityByObject": [{
            "designItemId": object_id,
            "designItemNo": paint_by_object[object_id]["designItemNo"],
            "material": paint_by_object[object_id]["material"],
            "materialRequirementIds": paint_by_object[object_id]["materialRequirementIds"],
        } for object_id in sorted(paint_by_object)],
    }
    evaluated.append(material_result)
    if material_status == "NOT_APPLICABLE":
        not_applicable_categories.append("PAINT_PROCESS_MATERIAL")
    elif material_unresolved_ids and first_blocker is None:
        first_blocker = {
            "code": "PAINT_PROCESS_MATERIAL_APPLICABILITY_UNRESOLVED",
            "statusLabel": "油漆/表面工艺材料适用性尚未解析",
            "message": "存在部分或冲突的Material/Recipe/UOM/Consumption正式证据；不得猜定。",
            "category": "PAINT_PROCESS_MATERIAL",
            "unresolvedDesignItemIds": material_unresolved_ids,
        }
    elif material_missing_requirement_ids and first_blocker is None:
        first_blocker = {
            "code": "PAINT_PROCESS_MATERIAL_REQUIREMENT_MISSING",
            "statusLabel": "油漆/表面工艺Material Requirement尚未形成",
            "message": "正式配方与耗用事实已证明物理材料适用，但Material Requirement缺失。",
            "category": "PAINT_PROCESS_MATERIAL",
            "missingDesignItemIds": material_missing_requirement_ids,
        }

    blocker_by_category = {
        (first_blocker or {}).get("category"): (first_blocker or {}).get("code")
    }
    full_readiness_scan = [{
        "roleOrRequirementType": row["code"],
        "applicability": row.get("status"),
        "coverage": {
            "applicableDesignItemCount": row.get("applicableDesignItemCount", 0),
            "coveredDesignItemCount": row.get("coveredDesignItemCount", 0),
            "requirementDesignItemCount": row.get("requirementDesignItemCount"),
        },
        "status": row.get("status"),
        "workflowStage": row.get("workflowStage", workflow_stage),
        "actualCapacityReadiness": row.get("actualCapacityReadiness"),
        "capacityRequiredForCurrentStage": row.get("capacityRequiredForCurrentStage"),
        "capacityRequiredForLaterManufacturingStage": row.get(
            "capacityRequiredForLaterManufacturingStage"
        ),
        "evidence": row.get("evidenceFactCodes", []),
        "potentialBlocker": blocker_by_category.get(row["code"]),
        "needsHumanFact": row.get("status") in {
            "APPLICABILITY_UNRESOLVED", "MISSING_REQUIREMENT",
            INCOMPLETE, BLOCKED,
        },
        "currentStageSatisfied": row.get("status") in {
            "COMPLETE", "APPLICABLE", READY, NOT_APPLICABLE, DEFERRED,
        },
        "canExistingFormalDataAutoResolve": row.get("status") in {
            "COMPLETE", "APPLICABLE", READY, NOT_APPLICABLE,
        },
    } for row in evaluated]

    return {
        "contractCode": "PCE-CURRENT-VERSION-MATERIAL-COMPLETENESS-V1",
        "applicable": True,
        "complete": first_blocker is None,
        "status": "COMPLETE" if first_blocker is None else "BLOCKED",
        "workflowStage": workflow_stage,
        "targetDesignItemCount": len(target_ids),
        "coveredDesignItemCount": len(covered_object_ids),
        "evaluatedCategories": evaluated,
        "fullBomReadinessScan": full_readiness_scan,
        "notApplicableCategories": not_applicable_categories,
        "firstRealBlocker": first_blocker,
    }


class OrderEngineeringClosureService:
    """Read validation, BOM draft preview, and explicit idempotent draft generation."""

    @staticmethod
    def _calculation(*, user, calculation_id, lock=False):
        queryset = EngineeringCalculationRecord.objects.select_related(
            "engineering_instance__sales_order_item__sales_order", "source_record",
        )
        if lock:
            queryset = queryset.select_for_update()
        calculation = queryset.filter(pk=calculation_id).first()
        if not calculation:
            test_query = EngineeringCalculationRecord.all_records.select_related("engineering_instance__sales_order_item__sales_order", "source_record").filter(scope='test_business',pk=calculation_id)
            calculation = (test_query.select_for_update() if lock else test_query).first()
        if not calculation:
            raise EngineeringCalculationError("CALCULATION_NOT_FOUND", "工程核算记录不存在。")
        EngineeringCalculationService._authorize(
            user=user,
            action_code="production.engineering.calculation.view",
            company_id=calculation.company_id,
            object_id=calculation.pk,
        )
        if calculation.scope == 'test_business':
            from .test_business_bom_service import validate_source,authorize
            authorize(user,'production.engineering.calculation.view',calculation.company_id)
            validate_source(calculation,user)
        return calculation

    @staticmethod
    def validate(*, user, sales_order_item_id, engineering_instance_id, source_record_id, rule_ids):
        blockers = []
        item = SalesOrderItem.objects.select_related("sales_order", "material", "uom").filter(
            pk=sales_order_item_id,
        ).first()
        instance = OrderEngineeringInstance.objects.select_related(
            "sales_order_item__sales_order", "source_record", "product", "baseline_product_version",
            "product_category", "selected_process_type",
        ).filter(pk=engineering_instance_id).first()
        company_id = getattr(getattr(item, "sales_order", None), "company_id", None)
        if not item:
            blockers.append({"code": "SALES_ORDER_ITEM_NOT_FOUND", "subject": "订单行", "impact": "无法核算", "maintenancePath": "销售订单 → 订单明细"})
        if not instance:
            blockers.append({"code": "ORDER_ENGINEERING_INSTANCE_NOT_FOUND", "subject": "订单工程实例", "impact": "无法绑定来源和版本", "maintenancePath": "产品工程 → 订单工程实例"})
        if item and item.engineering_mode != "ORDER_ENGINEERED":
            blockers.append({"code": "ORDER_LINE_NOT_ENGINEERED", "subject": f"{item.sales_order.order_no}/{item.line_no}", "impact": "不是按单工程行", "maintenancePath": "销售订单 → 工程模式"})
        if item and not item.uom_id:
            blockers.append({"code": "ORDER_UOM_REQUIRED", "subject": f"{item.sales_order.order_no}/{item.line_no}", "impact": "订单数量口径不完整", "maintenancePath": "销售订单 → 订单明细单位"})
        if item and instance and (
            instance.company_id != item.sales_order.company_id
            or instance.sales_order_item_id != item.pk
            or instance.source_record_id != source_record_id
        ):
            blockers.append({"code": "ORDER_ENGINEERING_CONTEXT_MISMATCH", "subject": "订单／实例／来源", "impact": "上下文不一致", "maintenancePath": "产品工程 → 订单工程实例"})
        if instance and instance.status not in {"source_confirmed", "calculated"}:
            blockers.append({"code": "ORDER_ENGINEERING_SOURCE_NOT_READY", "subject": instance.instance_no, "impact": "来源未确认", "maintenancePath": "产品工程 → 工程来源确认"})
        try:
            canonical_inputs = _order_inputs(item) if item else {}
        except EngineeringCalculationError as exc:
            canonical_inputs = {}
            blockers.append({"code": exc.code, "subject": "规范工程输入", "impact": exc.message, "maintenancePath": "销售订单 → 工程属性"})
        requested_ids = []
        try:
            requested_ids = [int(value) for value in rule_ids or []]
        except (TypeError, ValueError):
            pass
        rules = list(EngineeringRuleDefinition.objects.filter(
            company_id=company_id, pk__in=requested_ids,
        )) if company_id else []
        if not requested_ids or len(requested_ids) != len(set(requested_ids)):
            blockers.append({"code": "RULE_SET_REQUIRED", "subject": "规则包", "impact": "必须明确选择不重复规则", "maintenancePath": "产品工程 → 工程核算规则"})
        elif len(rules) != len(requested_ids):
            blockers.append({"code": "RULE_NOT_FOUND", "subject": "规则包", "impact": "规则不存在或跨公司", "maintenancePath": "产品工程 → 工程核算规则"})
        elif any(rule.status != "released" for rule in rules):
            blockers.append({"code": "RULE_NOT_RELEASED", "subject": "规则包", "impact": "只允许已发布规则", "maintenancePath": "产品工程 → 工程核算规则"})
        if company_id:
            EngineeringCalculationService._authorize(
                user=user, action_code="production.engineering.calculation.view", company_id=company_id,
            )
        return {
            "ready": not blockers,
            "blockers": blockers,
            "selection": {
                "salesOrderItemId": getattr(item, "pk", None),
                "orderNo": item.sales_order.order_no if item else None,
                "lineNo": item.line_no if item else None,
                "orderEngineeringInstanceId": getattr(instance, "pk", None),
                "instanceNo": instance.instance_no if instance else None,
                "sourceRecordId": source_record_id,
                "sourceNo": instance.source_record.source_no if instance else None,
                "sourceVersion": instance.source_record.source_version if instance else None,
                "productId": instance.product_id if instance else None,
                "productVersionId": instance.baseline_product_version_id if instance else None,
                "canonicalInputCount": len(canonical_inputs),
                "ruleIds": requested_ids,
            },
            "factSource": "server",
            "businessWriteSideEffectCount": 0,
        }

    @staticmethod
    def _preview_payload(calculation):
        if calculation.scope not in {"order_engineering", "test_business"} or calculation.status != "completed":
            raise EngineeringCalculationError(
                "COMPLETED_ORDER_CALCULATION_REQUIRED", "只有已完成的正式订单工程核算可以生成BOM草稿。",
            )
        requirements = list(calculation.material_requirements.select_related(
            "material", "uom", "source_detail",
        ).order_by("sequence", "pk"))
        test_completeness = None
        if calculation.scope == 'test_business':
            from .test_business_bom_service import validate_requirements
            test_completeness = validate_requirements(calculation, requirements)
        if not requirements and test_completeness is not None:
            return {"calculationId":calculation.pk,"calculationNo":calculation.calculation_no,
                    "previewHash":_hash({"resultHash":calculation.result_hash,"materialCount":0}),
                    "rows":[],"rowCount":0,"sourceRequirementCount":0,"canGenerate":False,"targetScope":{"calculationId":calculation.pk,"salesOrderItemId":calculation.sales_order_item_id},
                    "alreadyGenerated":False,"firstRealBlocker":test_completeness['firstRealBlocker'],
                    "currentVersionMaterialCompleteness":test_completeness,"businessPurposeLabel":"测试业务",
                    "sourceRecordId":calculation.source_record_id,"sourceVersion":calculation.source_record.source_version,
                    "businessWriteSideEffectCount":0,"factSource":"server"}
        if not requirements:
            raise EngineeringCalculationError(
                "MATERIAL_REQUIREMENT_REQUIRED", "该核算没有形成物料需求，不能生成空BOM草稿。",
            )
        groups = {}
        material_contracts = {}
        role_contracts = {}
        material_roles = {}
        for row in requirements:
            bom_item_role = _bom_item_role(row.item_role)
            bom_requirement_type = _bom_requirement_type(row.requirement_type)
            bom_supply_type = _bom_supply_type(row.supply_type)
            # ``designItemNo`` is immutable requirement provenance, not a BOM
            # aggregation semantic.  Two exact-compatible requirements for
            # the same material may originate from different design objects;
            # retain every object identity in the aggregated specification
            # instead of treating that provenance difference as a material
            # contract conflict.
            aggregation_specification = dict(row.order_specification or {})
            source_design_item_no = aggregation_specification.pop("designItemNo", None)
            structure_role = str(aggregation_specification.get("structureRole")
                                 or (getattr(row, "trace", {}) or {}).get("structureRole") or "").strip().upper()
            semantic_specification = dict(aggregation_specification)
            if structure_role:
                semantic_specification["structureRole"] = structure_role
            for provenance_key in ("developmentValidation", "sourceExternalIdentity", "classification",
                                   "notForPurchaseOrManufacture", "quantityBasisExplanation", "thicknessStatus"):
                semantic_specification.pop(provenance_key, None)
            contract = (
                row.uom_id, bom_item_role, bom_requirement_type, bom_supply_type,
                canonical_json(semantic_specification), row.scrap_rate_status,
                str(row.scrap_rate) if row.scrap_rate is not None else None,
            )
            material_contract = (row.uom_id, bom_item_role, bom_requirement_type, bom_supply_type,
                                 row.scrap_rate_status, str(row.scrap_rate) if row.scrap_rate is not None else None,
                                 aggregation_specification.get("materialCode", row.material.code),
                                 aggregation_specification.get("materialSpecification"))
            material_contracts.setdefault(row.material_id, set()).add(material_contract)
            role_contracts.setdefault((row.material_id, structure_role), set()).add(contract)
            material_roles.setdefault(row.material_id, set()).add(structure_role)
            if (len(material_contracts[row.material_id]) > 1
                    or len(role_contracts[(row.material_id, structure_role)]) > 1):
                raise EngineeringCalculationError(
                    "INCOMPATIBLE_MATERIAL_REQUIREMENTS",
                    "同一物料存在不兼容的单位、角色、需求类型、供给方式、规格或损耗语义；系统拒绝猜测聚合。",
                    {"materialId": row.material_id},
                )
            quantity = row.gross_quantity if row.scrap_rate_status == "maintained" else row.net_quantity
            bucket = groups.setdefault((row.material_id, structure_role, contract), {
                "materialId": row.material_id, "materialCode": row.material.code,
                "materialName": row.material.name, "uomId": row.uom_id, "uomCode": row.uom.code,
                "itemRole": bom_item_role, "requirementType": bom_requirement_type,
                "supplyType": bom_supply_type, "orderSpecification": {
                    **row.order_specification, **({"structureRole": structure_role} if structure_role else {})},
                "scrapRateStatus": row.scrap_rate_status,
                "scrapRate": str(row.scrap_rate) if row.scrap_rate is not None else None,
                "quantity": Decimal("0"), "sourceRequirementIds": [],
                "_aggregationSpecification": {
                    **aggregation_specification, **({"structureRole": structure_role} if structure_role else {})},
                "_sourceDesignItemNos": [],
                "_sourceRequirementContracts": [],
            })
            bucket["quantity"] += quantity
            bucket["sourceRequirementIds"].append(row.pk)
            bucket["_sourceRequirementContracts"].append({"requirementId": row.pk,
                                                        "orderSpecification": row.order_specification})
            if (
                source_design_item_no
                and source_design_item_no not in bucket["_sourceDesignItemNos"]
            ):
                bucket["_sourceDesignItemNos"].append(source_design_item_no)
        rows = []
        for line_no, bucket in enumerate(groups.values(), 1):
            source_design_item_nos = bucket.pop("_sourceDesignItemNos")
            aggregation_specification = bucket.pop("_aggregationSpecification")
            source_contracts = bucket.pop("_sourceRequirementContracts")
            if len(bucket["sourceRequirementIds"]) > 1:
                bucket["orderSpecification"] = {
                    **aggregation_specification,
                    "sourceDesignItemNos": source_design_item_nos,
                    "aggregationMode": "EXACT_COMPATIBLE_REQUIREMENTS",
                    "sourceRequirementContracts": source_contracts,
                }
            rows.append({
                **bucket,
                "lineNo": line_no,
                "quantity": str(bucket["quantity"]),
                "sourceDesignItemNos": source_design_item_nos,
            })
        instance = calculation.engineering_instance
        item = instance.sales_order_item
        hash_payload = {
            "calculationId": calculation.pk, "resultHash": calculation.result_hash,
            "instanceId": instance.pk, "rows": rows,
        }
        preview_hash = _hash(hash_payload)
        existing = BOMVersion.objects.filter(source_calculation=calculation).select_related("bom").first()
        completeness = test_completeness if test_completeness is not None else _current_version_material_completeness(
            calculation,
            requirements,
            workflow_stage=MATERIAL_BOM_GENERATION_STAGE,
        )
        first_real_blocker = completeness["firstRealBlocker"]
        if any(len(roles) > 1 for roles in material_roles.values()):
            # Never claim a generatable split while the deployed schema still
            # has the old one-material-per-parent uniqueness contract.
            from django.db import connection
            with connection.cursor() as cursor:
                constraints = connection.introspection.get_constraints(cursor, BOMItem._meta.db_table)
            if not {"pde_bom_item_parent_material_role_unique", "pde_bom_item_root_material_role_unique"}.issubset(constraints):
                first_real_blocker = {"code": "BOM_ROLE_LINE_STORAGE_CONTRACT_REQUIRED",
                                      "statusLabel": "同材分行存储契约待迁移",
                                      "message": "独立行已解析，但当前数据库唯一约束尚未支持结构角色；禁止生成。"}
        can_generate = completeness["complete"] and not existing and not first_real_blocker
        return {
            "calculationId": calculation.pk,
            "calculationNo": calculation.calculation_no,
            "orderNo": item.sales_order.order_no,
            "lineNo": item.line_no,
            "salesOrderItemId": item.pk,
            "orderEngineeringInstanceId": instance.pk,
            "orderEngineeringInstanceNo": instance.instance_no,
            "sourceRecordId": calculation.source_record_id,
            "sourceNo": calculation.source_record.source_no,
            "sourceVersion": calculation.source_record.source_version,
            "previewHash": preview_hash,
            "rows": rows,
            "rowCount": len(rows),
            "sourceRequirementCount": len(requirements),
            "targetScope": {
                "salesOrderItemId": item.pk,
                "lineNo": item.line_no,
                "orderEngineeringInstanceId": instance.pk,
                "calculationId": calculation.pk,
                "designItemCount": completeness.get("targetDesignItemCount"),
                "coveredDesignItemCount": completeness.get("coveredDesignItemCount"),
                "coverageGate": "PASS" if completeness["complete"] or (
                    first_real_blocker and first_real_blocker.get("code") != "TARGET_BOM_REQUIREMENT_COVERAGE_INCOMPLETE"
                ) else "FAIL",
            },
            "currentVersionMaterialCompleteness": completeness,
            "firstRealBlocker": first_real_blocker,
            "canGenerate": can_generate,
            "alreadyGenerated": bool(existing),
            "bomId": existing.bom_id if existing else None,
            "bomVersionId": existing.pk if existing else None,
            "bomVersion": existing.bom_version if existing else None,
            "status": (
                "DRAFT_ALREADY_GENERATED" if existing else
                "BOM_INPUT_BLOCKED" if first_real_blocker else
                "PREVIEW_ONLY"
            ),
            "factSource": "server",
            "businessWriteSideEffectCount": 0,
        }

    @classmethod
    def preview_bom(cls, *, user, calculation_id):
        calculation = cls._calculation(user=user, calculation_id=calculation_id)
        return cls._preview_payload(calculation)

    @classmethod
    @transaction.atomic
    def generate_bom(cls, *, user, calculation_id, preview_hash, reason="", _development_admission=None):
        calculation = cls._calculation(user=user, calculation_id=calculation_id, lock=True)
        decision = EngineeringCalculationService._authorize(
            user=user, action_code="production.master_data.bom.maintain",
            company_id=calculation.company_id, object_id=calculation.engineering_instance_id,
        )
        execution_chain = _actor_chain(user)
        controlled_test = calculation.scope == 'test_business'
        order = calculation.engineering_instance.sales_order_item.sales_order
        development_proof = None
        if _development_admission is not None:
            from .system_test_bom_draft import validate_admission
            development_proof = validate_admission(_development_admission, user=user,
                calculation_id=calculation.pk, preview_hash=preview_hash)
        if not controlled_test and development_proof is None and order.business_purpose in {
                SalesOrder.BusinessPurpose.FORMAL_SALE, SalesOrder.BusinessPurpose.SYSTEM_TEST}:
            try:
                require_current_order_admission(
                    order=order,
                    sales_order_item_id=calculation.sales_order_item_id,
                    engineering_instance_id=calculation.engineering_instance_id,
                    calculation_id=calculation.pk,
                    lock=True,
                )
            except CRMOrderAdmissionError as exc:
                raise EngineeringCalculationError(
                    exc.code, exc.message, {"orderAdmission": exc.details},
                ) from exc
        preview = cls._preview_payload(calculation)
        if not preview_hash or preview_hash != preview["previewHash"]:
            raise EngineeringCalculationError(
                "STALE_BOM_PREVIEW", "BOM预览已变化或未提供；请重新预览后再生成。",
                {"currentPreviewHash": preview["previewHash"]},
            )
        if not preview["canGenerate"] and not preview["alreadyGenerated"]:
            blocker = preview["firstRealBlocker"] or {
                "code": "BOM_INPUT_READINESS_BLOCKED",
                "message": "当前BOM输入完整性未通过。",
            }
            raise EngineeringCalculationError(
                blocker["code"], blocker["message"],
                {"firstRealBlocker": blocker, "targetScope": preview["targetScope"]},
            )
        existing = BOMVersion.objects.select_for_update().filter(source_calculation=calculation).first()
        if existing:
            return {**preview, "idempotent": True, "authorization": decision, "executionChain": execution_chain}
        instance = calculation.engineering_instance
        base_code = f"OBOM-{instance.instance_no}"
        bom_code = base_code[:55] + "-" + _hash({"instanceId": instance.pk})[:8] if len(base_code) > 64 else base_code
        bom_fields = dict(
            company_id=calculation.company_id,
            order_engineering_instance=instance,
            bom_type="manufacturing",
            is_active=True,
            **({"source_calculation":calculation,"usage_purpose":"TEST_BUSINESS"} if controlled_test else
               {"usage_purpose":"PRODUCTION_USE"} if FormalManufacturingEligibilityService.resolve(calculation)['formalManufacturingEligible'] else {}),
        )
        defaults = {"applicability_scope": ManufacturingApplicabilityScope.ORDER_ENGINEERING,
                    "bom_code": bom_code,
                    "name": f"{instance.sales_order_item.sales_order.order_no}/{instance.sales_order_item.line_no} 订单BOM",
                    "status": "draft"}
        if development_proof or controlled_test:
            from workflow_runtime.state_transitions import create_business_object_with_initial_state
            defaults['name'] += '（受控开发测试）'
            ProductBOM(**bom_fields, **defaults).full_clean()
            defaults.pop('status')
            bom = create_business_object_with_initial_state(model=ProductBOM, initial_state='draft',
                                                            **bom_fields, **defaults)
        else:
            bom, _ = ProductBOM.objects.select_for_update().get_or_create(**bom_fields, defaults=defaults)
        bom.full_clean()
        generation_key = _hash({"calculationId": calculation.pk, "previewHash": preview_hash})
        version = BOMVersion(
            bom=bom, bom_version=f"CALC-{calculation.pk}", revision=calculation.revision,
            bom_scope="order_specific", order_engineering_instance=instance,
            source_calculation=calculation, preview_hash=preview_hash,
            generation_key=generation_key, status="draft",
            applicability={
                "salesOrderItemId": calculation.sales_order_item_id,
                "sourceRecordId": calculation.source_record_id,
                "calculationId": calculation.pk,
                **({"developmentValidation": development_proof} if development_proof else {}),
            },
        )
        version.full_clean()
        if development_proof or controlled_test:
            version = create_business_object_with_initial_state(model=BOMVersion, initial_state='draft',
                **{field.attname: getattr(version, field.attname) for field in version._meta.concrete_fields
                   if field.name not in {'id', 'status', 'created_at', 'updated_at'}})
        else:
            version.save()
        requirement_by_id = {
            row.pk: row for row in calculation.material_requirements.all()
        }
        for row in preview["rows"]:
            item = BOMItem(
                bom_version=version, line_no=row["lineNo"], material_id=row["materialId"],
                quantity=Decimal(row["quantity"]), item_role=row["itemRole"],
                requirement_type=row["requirementType"], supply_type=row["supplyType"],
                order_specification=row["orderSpecification"], uom_id=row["uomId"],
                scrap_rate_status=row["scrapRateStatus"],
                scrap_rate=Decimal(row["scrapRate"]) if row["scrapRate"] is not None else None,
                substitute_status=BOMItem.SubstituteStatus.NOT_MAINTAINED,
                **({"quantity_rule": {"basis": "ORDER_TOTAL_NET", "source": "SAVED_REQUIREMENTS",
                    "orderQuantityMultiplierApplied": False,
                    "netQuantity": row['quantity'], "grossQuantity": None}} if development_proof else {}),
            )
            item.full_clean()
            item.save()
            for requirement_id in row["sourceRequirementIds"]:
                link = BOMItemSourceRequirement(
                    bom_item=item, material_requirement=requirement_by_id[requirement_id],
                    contributed_quantity=(
                        requirement_by_id[requirement_id].gross_quantity
                        if requirement_by_id[requirement_id].scrap_rate_status == "maintained"
                        else requirement_by_id[requirement_id].net_quantity
                    ),
                )
                link.full_clean()
                link.save()
        header_audit = None
        if development_proof or controlled_test:
            header_audit = _audit(user=user, organization_id=calculation.company_id,
                action_code="production.master_data.bom.maintain", instance=bom, before={},
                after={"status": "draft", "sourceCalculationId": calculation.pk,
                       "developmentValidation": development_proof}, reason=reason,
                authorization=decision, execution_chain=execution_chain)
        audit = _audit(
            user=user, organization_id=calculation.company_id,
            action_code="production.master_data.bom.maintain", instance=version,
            before={}, after={
                "decision": "DRAFT_CREATED", "bomId": bom.pk, "bomVersionId": version.pk,
                "sourceCalculationId": calculation.pk, "previewHash": preview_hash,
                "itemCount": len(preview["rows"]), "downstreamWriteCount": 0,
                **({"developmentValidation": development_proof} if development_proof else {}),
            },
            reason=reason or "从订单工程核算结果生成BOM草稿",
            authorization=decision, execution_chain=execution_chain,
        )
        transitions = []
        if development_proof or controlled_test:
            from workflow_runtime.state_transitions import record_projected_business_transition
            for obj, event_audit in ((bom, header_audit), (version, audit)):
                transitions.append(record_projected_business_transition(
                    object_type=type(obj).__name__, object_id=obj.pk, source_state='', target_state='draft',
                    action_code="production.master_data.bom.maintain", operator=user, reason=reason,
                    audit_reference=f'OrganizationOperatingAuditRecord:{event_audit.pk}',
                    allowed_transitions={('', 'draft')}).pk)
        return {
            **cls._preview_payload(calculation), "idempotent": False,
            "auditId": audit.pk, "authorization": decision, "executionChain": execution_chain,
            **({"headerAuditId": header_audit.pk, "transitionIds": transitions,
                "developmentValidation": development_proof} if development_proof else {}),
        }


