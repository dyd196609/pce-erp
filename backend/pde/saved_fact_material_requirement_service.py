"""Formal handoff from persisted engineering facts to one material requirement.

The service is deliberately industry-neutral.  A caller supplies an explicit,
audited formula contract whose variables bind to saved ``EngineeringDerivedFact``
rows.  The service validates and releases that contract through the existing
``EngineeringRuleDefinition`` lifecycle, then creates exactly one traceable
``EngineeringMaterialRequirement``.  It never recalculates an engineering
calculation and never creates a BOM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from masterdata.models import ExternalIdentity, MasterDataWriteRequest, Material
from sales.models import SalesOrder
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord, PositionWorkflowResponsibility

from .crm_order_admission import CRMOrderAdmissionError, require_current_order_admission
from .engineering_rule_foundation import (
    EngineeringRuleError,
    canonical_json,
    evaluate_specification,
    specification_hash,
    validate_specification,
)
from .models import (
    EngineeringCalculationRecord,
    EngineeringDerivedFact,
    EngineeringMaterialRequirement,
    EngineeringRuleDefinition,
    ProductDesignItem,
)
from .production_foundation_service import (
    EngineeringLifecycleService,
    ProductionFoundationError,
    ProductionFoundationService,
)


SERVICE_CODE = "PCE-SAVED-FACT-MATERIAL-REQUIREMENT-HANDOFF-V1"
MAPPING_CONTRACT_CODE = "PCE-MATERIAL-REQUIREMENT-FORMULA-MAPPING-V1"
REQUIREMENT_ACTION_CODE = "production.engineering.material_requirement.create"
MAPPING_SOURCE_SYSTEM = "PCE_ENGINEERING_FACT_HANDOFF"
MAPPING_SOURCE_TYPE = "USER_AUTHORIZED_FORMULA_MAPPING"
REQUIREMENT_SOURCE_SYSTEM = "PCE_ENGINEERING_FACT_HANDOFF"
REQUIREMENT_SOURCE_TYPE = "USER_AUTHORIZED_REQUIREMENT"


class SavedFactMaterialRequirementError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class SavedFactInputBinding:
    variable: str
    fact_code: str
    expected_uom_code: str | None
    unit_dimension: str | dict | None
    unit_required: bool = True
    positive_required: bool = True
    integer_required: bool = False


@dataclass(frozen=True)
class SavedFactMaterialRequirementContract:
    mapping_no: str
    mapping_rule_code: str
    mapping_version: str
    rule_name: str
    order_no: str
    calculation_id: int
    design_item_no: str
    material_id: int
    material_code: str
    output_uom_code: str
    output_name: str
    expression: str
    inputs: tuple[SavedFactInputBinding, ...]
    primary_source_fact_code: str
    expected_quantity: Decimal
    authorization_reference: str
    idempotency_key: str
    purpose_code: str
    quantity_basis: str = "ORDER_TOTAL"
    item_role: str = "material"
    requirement_type: str = "manufacturing"
    supply_type: str = "MAKE"
    scrap_rate: Decimal | None = Decimal("0")
    order_specification: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    output_scale: int = 6
    output_unit_dimension: str | dict | None = "area"
    require_design_material_reference: bool = True
    source_external_identity_id: int | None = None
    allow_missing_design_revision_when_source_identity_confirmed: bool = False

    @property
    def mapping_idempotency_key(self) -> str:
        return f"{self.idempotency_key}:MAPPING"

    @property
    def requirement_idempotency_key(self) -> str:
        return f"{self.idempotency_key}:REQUIREMENT"


def _fail(code: str, message: str, **details):
    raise SavedFactMaterialRequirementError(code, message, details)


def _hash(value) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _current_local_date():
    """Return today's date under both USE_TZ modes used by PCE runtimes."""
    current = timezone.now()
    return current.date() if timezone.is_naive(current) else timezone.localtime(current).date()


def _decimal(value, *, code: str, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        _fail(code, f"{label}不是合法十进制数值。", value=value)
    return result


def _fact_decimal(fact: EngineeringDerivedFact) -> Decimal:
    raw = fact.value.get("decimal") if isinstance(fact.value, dict) else fact.value
    return _decimal(raw, code="SAVED_FACT_DECIMAL_REQUIRED", label="已保存工程事实")


def _authorize(*, user, action_code: str, organization_id: int, business_object: dict) -> dict:
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


def _actor_context(*, user, order) -> dict:
    if not user or not user.is_authenticated or not user.is_active:
        _fail("FORMAL_ACTOR_REQUIRED", "正式材料需求必须由有效登录账户执行。")
    if user.is_superuser:
        _fail("ADMIN_BYPASS_FORBIDDEN", "正式材料需求禁止使用超级管理员绕过业务身份。")
    employee = getattr(user, "employee_profile", None)
    position = getattr(employee, "position_ref", None) if employee else None
    department = getattr(employee, "department_ref", None) if employee else None
    if (
        not employee
        or employee.status != "active"
        or not position
        or not position.is_active
        or not department
        or not department.is_active
    ):
        _fail(
            "FORMAL_EMPLOYMENT_CONTEXT_REQUIRED",
            "执行账户必须关联在职员工、有效岗位和有效部门。",
        )
    if user.company_id != order.company_id or department.company_id != order.company_id:
        _fail("FORMAL_ACTOR_COMPANY_MISMATCH", "执行账户、部门与订单必须属于同一公司。")
    today = _current_local_date()
    responsibility = PositionWorkflowResponsibility.objects.select_related(
        "responsibility", "workflow_node__process_definition",
    ).filter(
        position=position,
        active=True,
        responsibility__is_active=True,
        ownership_type__in=("OWNER", "EXECUTOR"),
    ).filter(
        Q(effective_from__isnull=True) | Q(effective_from__lte=today),
        Q(effective_to__isnull=True) | Q(effective_to__gte=today),
    ).order_by("pk").first()
    if not responsibility:
        _fail(
            "WORKFLOW_RESPONSIBILITY_REQUIRED",
            "执行岗位没有生效的正式流程负责/执行责任。",
        )
    return {
        "accountId": user.pk,
        "account": user.username,
        "employeeId": employee.pk,
        "employeeNo": employee.employee_no,
        "positionId": position.pk,
        "positionCode": position.code,
        "departmentId": department.pk,
        "departmentCode": department.code,
        "companyId": user.company_id,
        "workflowResponsibility": {
            "mappingId": responsibility.pk,
            "workflowCode": responsibility.workflow_code,
            "nodeCode": responsibility.node_code,
            "ownershipType": responsibility.ownership_type,
            "responsibilityCode": responsibility.responsibility.code,
        },
    }


def _validate_contract(contract: SavedFactMaterialRequirementContract) -> None:
    if not contract.mapping_no.strip() or not contract.mapping_rule_code.strip():
        _fail("MAPPING_IDENTITY_REQUIRED", "Mapping编号和正式规则编码不能为空。")
    if not contract.authorization_reference.strip() or not contract.idempotency_key.strip():
        _fail("FORMAL_AUTHORIZATION_REFERENCE_REQUIRED", "正式授权依据和幂等键不能为空。")
    if len(contract.mapping_idempotency_key) > 160 or len(contract.requirement_idempotency_key) > 160:
        _fail("IDEMPOTENCY_KEY_TOO_LONG", "幂等键超过正式账本长度限制。")
    if contract.quantity_basis not in {"PER_SALES_ITEM_UNIT", "ORDER_TOTAL"}:
        _fail("QUANTITY_BASIS_REQUIRED", "数量口径必须明确为PER_SALES_ITEM_UNIT或ORDER_TOTAL。")
    if contract.output_scale != 6:
        _fail("OUTPUT_SCALE_UNSUPPORTED", "当前正式Requirement模型要求六位小数输出。")
    if not isinstance(contract.require_design_material_reference, bool):
        _fail(
            "DESIGN_MATERIAL_REFERENCE_POLICY_INVALID",
            "是否要求当前设计主材引用必须是明确布尔值。",
        )
    if (
        contract.source_external_identity_id is not None
        and contract.source_external_identity_id <= 0
    ):
        _fail(
            "SOURCE_EXTERNAL_IDENTITY_INVALID",
            "来源ExternalIdentity必须是有效正整数身份。",
        )
    if not isinstance(
        contract.allow_missing_design_revision_when_source_identity_confirmed, bool
    ):
        _fail(
            "MISSING_DESIGN_REVISION_POLICY_INVALID",
            "缺少设计修订时的承接策略必须是明确布尔值。",
        )
    if contract.allow_missing_design_revision_when_source_identity_confirmed and (
        contract.require_design_material_reference
        or contract.source_external_identity_id is None
    ):
        _fail(
            "MISSING_DESIGN_REVISION_POLICY_UNSAFE",
            "仅在不改写设计Material引用且显式校验来源ExternalIdentity时，才可承接无修订的既有DesignItem。",
        )
    if not contract.inputs:
        _fail("SAVED_FACT_INPUT_REQUIRED", "至少需要一个已保存工程事实输入。")
    variables = [row.variable for row in contract.inputs]
    fact_codes = [row.fact_code for row in contract.inputs]
    if len(variables) != len(set(variables)) or len(fact_codes) != len(set(fact_codes)):
        _fail("DUPLICATE_SAVED_FACT_INPUT", "公式变量或来源Fact编码重复。")
    if contract.primary_source_fact_code not in fact_codes:
        _fail("PRIMARY_SOURCE_FACT_REQUIRED", "Requirement主来源Fact必须属于公式输入集合。")
    expected = _decimal(
        contract.expected_quantity,
        code="EXPECTED_QUANTITY_REQUIRED",
        label="业务确认数量",
    )
    if expected <= 0:
        _fail("EXPECTED_QUANTITY_MUST_BE_POSITIVE", "业务确认数量必须大于0。")
    if contract.scrap_rate is not None:
        rate = _decimal(contract.scrap_rate, code="INVALID_SCRAP_RATE", label="损耗率")
        if rate < 0 or rate >= 1:
            _fail("INVALID_SCRAP_RATE", "损耗率必须在0（含）到1（不含）之间。")


def _validate_input_values(
    contract: SavedFactMaterialRequirementContract,
    values: dict[str, dict],
) -> None:
    for binding in contract.inputs:
        if binding.variable not in values:
            _fail(
                "SAVED_FACT_INPUT_MISSING",
                "公式缺少必需的已保存工程事实输入。",
                variable=binding.variable,
                factCode=binding.fact_code,
            )
        value = _decimal(
            values[binding.variable].get("value"),
            code="SAVED_FACT_DECIMAL_REQUIRED",
            label=f"公式输入{binding.variable}",
        )
        if binding.positive_required and value <= 0:
            _fail(
                "SAVED_FACT_INPUT_MUST_BE_POSITIVE",
                "公式输入必须大于0。",
                variable=binding.variable,
                value=str(value),
            )

        if binding.integer_required and value != value.to_integral_value():
            _fail("SAVED_FACT_INPUT_MUST_BE_INTEGER", "公式输入必须是整数。",
                  variable=binding.variable, value=str(value))

    # Optional explicit input assertions are part of a versioned mapping, not
    # defaults inferred from a unit name or another order's stock length.
    for assertion in contract.order_specification.get("inputAssertions", []):
        variable = assertion.get("variable")
        if variable not in values or variable not in {b.variable for b in contract.inputs}:
            _fail("SAVED_FACT_ASSERTION_MISSING", "数量换算缺少合同要求的冻结输入。")
        if (_decimal(values[variable].get("value"), code="SAVED_FACT_DECIMAL_REQUIRED", label=variable)
                != _decimal(assertion.get("equals"), code="SAVED_FACT_ASSERTION_INVALID", label=variable)
                or values[variable].get("unit") != assertion.get("uom")):
            _fail("SAVED_FACT_ASSERTION_MISMATCH", "冻结开料长度或单位不满足显式换算合同。", variable=variable)


def build_mapping_specification(
    contract: SavedFactMaterialRequirementContract,
    *,
    resolved_facts: dict[str, EngineeringDerivedFact],
    material: Material,
    order_specification: dict,
) -> dict:
    fact_evidence = []
    source_rule_versions = []
    for binding in contract.inputs:
        fact = resolved_facts[binding.variable]
        source_rule = f"{fact.rule.rule_code}@{fact.rule.version}" if fact.rule_id else None
        if source_rule and source_rule not in source_rule_versions:
            source_rule_versions.append(source_rule)
        fact_evidence.append({
            "variable": binding.variable,
            "sourceFactCode": binding.fact_code,
            "sourceFactId": fact.pk,
            "sourceDetailId": fact.source_detail_id,
            "sourcePath": fact.source_path,
            "value": str(_fact_decimal(fact)),
            "uom": fact.uom.code if fact.uom_id else None,
        })
    spec = {
        "contractCode": MAPPING_CONTRACT_CODE,
        "rulePackage": {
            "code": "PCE-MATERIAL-REQUIREMENT-FORMULA-MAPPING",
            "version": contract.mapping_version,
        },
        "inputs": [{
            "canonicalName": binding.variable,
            "valueType": "decimal",
            "unit": binding.expected_uom_code,
            "unitDimension": binding.unit_dimension,
            "sourceType": "ENGINEERING_DERIVED",
            "required": True,
            "unitRequired": binding.unit_required,
        } for binding in contract.inputs],
        "outputs": [{
            "canonicalName": contract.output_name,
            "valueType": "decimal",
            "unit": contract.output_uom_code,
            "unitDimension": contract.output_unit_dimension,
            "resultDomain": "MATERIAL_REQUIREMENT",
            "sourceFactCode": contract.primary_source_fact_code,
            "sourceFactCodes": [row.fact_code for row in contract.inputs],
            "materialId": material.pk,
            "materialCode": material.code,
            "outputUom": contract.output_uom_code,
            "quantityBasis": contract.quantity_basis,
            "quantityScope": "PRODUCT_DESIGN_ITEM",
            "quantityExpression": contract.expression,
            "quantitySource": {
                "type": "SAVED_DERIVED_FACT_SET",
                "sourceFactCodes": [row.fact_code for row in contract.inputs],
                "sourceFacts": fact_evidence,
            },
            "salesItemMultiplier": "NONE",
            "scrapRate": (
                str(contract.scrap_rate.quantize(Decimal("0.000001")))
                if contract.scrap_rate is not None else None
            ),
            "itemRole": contract.item_role,
            "requirementType": contract.requirement_type,
            "supplyType": contract.supply_type,
            "structureRole": contract.purpose_code,
            "orderSpecification": order_specification,
            "sourceRuleVersion": "+".join(source_rule_versions),
            "mappingVersion": contract.mapping_version,
        }],
        "expression": contract.expression,
        "dependencies": [],
        "decimalPrecision": 24,
        "outputScale": contract.output_scale,
        "roundingMode": "ROUND_HALF_UP",
        "priority": 100,
        "sourceEvidence": {
            "reference": contract.authorization_reference,
            "calculationId": next(iter(resolved_facts.values())).calculation_id,
            "calculationResultHash": next(iter(resolved_facts.values())).calculation.result_hash,
            "sourceFacts": fact_evidence,
        },
        "applicability": {
            "orderNo": contract.order_no,
            "designItemNo": contract.design_item_no,
            "salesOrderItemId": next(iter(resolved_facts.values())).calculation.sales_order_item_id,
        },
        "auditIdentity": {
            "authorizationReference": contract.authorization_reference,
            "idempotencyKey": contract.idempotency_key,
            "mappingNo": contract.mapping_no,
            "approvedScope": "PRODUCT_DESIGN_ITEM_FORMAL_REQUIREMENT",
        },
        "provenance": contract.provenance,
    }
    source_external_identity = order_specification.get("sourceExternalIdentity")
    if source_external_identity:
        spec["sourceEvidence"]["materialSourceExternalIdentity"] = source_external_identity
    try:
        validate_specification(spec)
    except EngineeringRuleError as exc:
        raise SavedFactMaterialRequirementError(exc.code, exc.message, exc.details) from exc
    return spec


def evaluate_contract_formula(
    contract: SavedFactMaterialRequirementContract,
    *,
    mapping_specification: dict,
    input_values: dict[str, dict],
) -> Decimal:
    _validate_contract(contract)
    _validate_input_values(contract, input_values)
    try:
        evaluated = evaluate_specification(mapping_specification, input_values)
    except EngineeringRuleError as exc:
        raise SavedFactMaterialRequirementError(exc.code, exc.message, exc.details) from exc
    quantity = _decimal(
        evaluated["value"], code="FORMULA_RESULT_INVALID", label="公式结果",
    ).quantize(Decimal("0.000001"))
    expected = Decimal(str(contract.expected_quantity)).quantize(Decimal("0.000001"))
    if quantity != expected:
        _fail(
            "AUTHORIZED_QUANTITY_MISMATCH",
            "已保存事实公式结果与业务确认数量不一致。",
            calculatedQuantity=str(quantity),
            expectedQuantity=str(expected),
        )
    if quantity <= 0:
        _fail("FORMULA_RESULT_MUST_BE_POSITIVE", "正式材料需求数量必须大于0。")
    return quantity


def _resolve_context(
    *,
    user,
    contract: SavedFactMaterialRequirementContract,
    lock: bool,
    _development_context=None,
) -> dict:
    _validate_contract(contract)
    order_query = SalesOrder.objects.select_related("company", "department")
    calculation_query = EngineeringCalculationRecord.objects.select_related(
        "sales_order_item__sales_order", "engineering_instance", "source_record",
    )
    design_query = ProductDesignItem.objects.select_related(
        "sales_order_item__sales_order", "source_record",
    )
    material_query = Material.objects.select_related("base_uom")
    if lock:
        order_query = order_query.select_for_update()
        calculation_query = calculation_query.select_for_update()
        design_query = design_query.select_for_update()
        material_query = material_query.select_for_update()
    order = order_query.filter(order_no=contract.order_no, company_id=user.company_id).first()
    if not order:
        _fail("ORDER_NOT_FOUND", "目标销售订单不存在、跨公司或编号已变化。")
    actor = _actor_context(user=user, order=order)
    calculation = calculation_query.filter(
        pk=contract.calculation_id,
        company_id=order.company_id,
    ).first()
    if not calculation:
        _fail("CALCULATION_NOT_FOUND", "目标工程核算不存在或跨公司。")
    try:
        if _development_context is not None:
            from .system_test_material_handoff import verify_admission
            admission = verify_admission(_development_context, user=user, contract=contract)
        else:
            admission = require_current_order_admission(
                order=order,
                sales_order_item_id=calculation.sales_order_item_id,
                engineering_instance_id=calculation.engineering_instance_id,
                calculation_id=calculation.pk,
                lock=lock,
            )
    except CRMOrderAdmissionError as exc:
        raise SavedFactMaterialRequirementError(exc.code, exc.message, exc.details) from exc
    if (
        calculation.scope != "order_engineering"
        or calculation.status != "completed"
        or not calculation.sales_order_item_id
        or not calculation.engineering_instance_id
        or calculation.sales_order_item.sales_order_id != order.pk
    ):
        _fail(
            "COMPLETED_ORDER_CALCULATION_REQUIRED",
            "Requirement只能承接目标订单中已完成的正式订单工程核算。",
        )
    design_item = design_query.filter(
        item_no=contract.design_item_no,
        company_id=order.company_id,
    ).first()
    if not design_item:
        _fail("DESIGN_ITEM_NOT_FOUND", "目标ProductDesignItem不存在或跨公司。")
    if (
        design_item.sales_order_item_id != calculation.sales_order_item_id
        or design_item.source_record_id != calculation.source_record_id
    ):
        _fail(
            "DESIGN_ITEM_CALCULATION_CONTEXT_MISMATCH",
            "ProductDesignItem与Calculation的订单行或正式来源不一致。",
        )
    latest_revision = design_item.design_revisions.select_related(
        "material__base_uom",
    ).order_by("-revision", "-pk").first()
    if _development_context is not None:
        # The controlled contract consumes the exact frozen revision, even if
        # another revision exists. It never writes the old material reference.
        latest_revision = design_item.design_revisions.select_related("material__base_uom").get(
            pk=admission.proof["sourceIdentity"]["designRevisionId"],
        )
    if (
        not latest_revision
        and not contract.allow_missing_design_revision_when_source_identity_confirmed
    ):
        _fail(
            "CURRENT_DESIGN_REVISION_REQUIRED",
            "目标ProductDesignItem缺少当前正式设计修订。",
        )
    if (
        latest_revision
        and
        contract.require_design_material_reference
        and latest_revision.material_id != contract.material_id
    ):
        _fail(
            "DESIGN_MATERIAL_REFERENCE_MISMATCH",
            "当前正式设计修订没有引用本次Mapping指定的Material。",
            currentMaterialId=getattr(latest_revision, "material_id", None),
            requestedMaterialId=contract.material_id,
        )
    material = material_query.filter(
        pk=contract.material_id,
        code=contract.material_code,
        company_id=order.company_id,
        is_active=True,
    ).first()
    if not material:
        _fail("MATERIAL_NOT_FOUND", "正式Material不存在、编码不一致、跨公司或已停用。")
    if not material.base_uom_id or not material.base_uom.is_active:
        _fail("MATERIAL_BASE_UOM_REQUIRED", "正式Material缺少有效基本单位。")
    if material.base_uom.code != contract.output_uom_code:
        _fail(
            "MATERIAL_UOM_MISMATCH",
            "公式输出单位必须等于Material正式基本单位；系统不做隐式换算。",
            materialBaseUom=material.base_uom.code,
            outputUom=contract.output_uom_code,
        )
    source_external_identity = None
    if contract.source_external_identity_id is not None:
        identity_query = ExternalIdentity.objects
        if lock:
            identity_query = identity_query.select_for_update()
        source_external_identity = identity_query.filter(
            pk=contract.source_external_identity_id,
            organization_id=order.company_id,
            target_entity_type="materials",
            target_entity_id=str(material.pk),
            mapping_status=ExternalIdentity.MappingStatus.MATCH,
        ).first()
        if not source_external_identity:
            _fail(
                "MATERIAL_SOURCE_EXTERNAL_IDENTITY_MISMATCH",
                "来源ExternalIdentity不存在、跨组织、未MATCH或未指向本次Material。",
                sourceExternalIdentityId=contract.source_external_identity_id,
                materialId=material.pk,
            )

    fact_query = EngineeringDerivedFact.objects.select_related(
        "calculation", "source_detail", "rule", "uom",
    ).filter(calculation=calculation, status="active")
    if lock:
        fact_query = fact_query.select_for_update()
    resolved_facts: dict[str, EngineeringDerivedFact] = {}
    input_values: dict[str, dict] = {}
    for binding in contract.inputs:
        rows = list(fact_query.filter(
            fact_code=f"{design_item.item_no}:{binding.fact_code}",
            canonical_field=binding.fact_code,
        ))
        if len(rows) != 1:
            _fail(
                "SAVED_FACT_INPUT_NOT_UNIQUE",
                "公式输入必须精确对应一个已保存DerivedFact。",
                variable=binding.variable,
                factCode=binding.fact_code,
                matchCount=len(rows),
            )
        fact = rows[0]
        if (
            fact.trace.get("designItemId") != design_item.pk
            or fact.trace.get("designItemNo") != design_item.item_no
            or not fact.source_detail_id
            or fact.source_detail.calculation_id != calculation.pk
        ):
            _fail("SAVED_FACT_LINEAGE_MISMATCH", "已保存DerivedFact追溯不属于目标设计对象。")
        actual_uom = fact.uom.code if fact.uom_id else None
        if binding.expected_uom_code is not None and actual_uom != binding.expected_uom_code:
            _fail(
                "SAVED_FACT_UOM_MISMATCH",
                "已保存DerivedFact单位与Mapping输入合同不一致。",
                variable=binding.variable,
                actualUom=actual_uom,
                expectedUom=binding.expected_uom_code,
            )
        resolved_facts[binding.variable] = fact
        input_values[binding.variable] = {
            "value": str(_fact_decimal(fact)),
            "unit": actual_uom,
            "unitDimension": binding.unit_dimension,
        }

    order_specification = {
        **contract.order_specification,
        "materialCode": material.code,
        "materialSpecification": material.specification,
        "designItemNo": design_item.item_no,
        "quantityScope": "PRODUCT_DESIGN_ITEM",
        "structureRole": contract.purpose_code,
        "salesOrderItemQuantity": str(calculation.sales_order_item.quantity),
        "salesOrderItemQuantityMultiplierApplied": False,
    }
    if _development_context is not None:
        order_specification["developmentValidation"] = admission.as_dict()
    if contract.allow_missing_design_revision_when_source_identity_confirmed:
        order_specification["designRevisionReference"] = {
            "required": False,
            "reason": "LEGACY_DESIGN_ITEM_WITH_CONFIRMED_EXTERNAL_MATERIAL_IDENTITY",
            "designItemPreserved": True,
        }
    if source_external_identity:
        order_specification["sourceExternalIdentity"] = {
            "id": source_external_identity.pk,
            "sourceSystem": source_external_identity.source_system,
            "sourceType": source_external_identity.source_type,
            "sourceObjectType": source_external_identity.source_object_type,
            "externalId": source_external_identity.external_id,
            "targetEntityType": source_external_identity.target_entity_type,
            "targetEntityId": source_external_identity.target_entity_id,
            "mappingStatus": source_external_identity.mapping_status,
            "sourceFingerprint": source_external_identity.source_fingerprint,
        }
    mapping_specification = build_mapping_specification(
        contract,
        resolved_facts=resolved_facts,
        material=material,
        order_specification=order_specification,
    )
    quantity = evaluate_contract_formula(
        contract,
        mapping_specification=mapping_specification,
        input_values=input_values,
    )
    primary_fact = next(
        fact for variable, fact in resolved_facts.items()
        if next(row.fact_code for row in contract.inputs if row.variable == variable)
        == contract.primary_source_fact_code
    )
    adoption = getattr(admission, "adoption", None)
    return {
        "order": order,
        "actor": actor,
        "calculation": calculation,
        "designItem": design_item,
        "designRevision": latest_revision,
        "material": material,
        "sourceExternalIdentity": source_external_identity,
        "resolvedFacts": resolved_facts,
        "inputValues": input_values,
        "primaryFact": primary_fact,
        "mappingSpecification": mapping_specification,
        "orderSpecification": order_specification,
        "quantity": quantity,
        "admission": admission,
        "legacyAdoption": adoption,
    }


def _serialize_preview(contract, context, *, authorizations=None) -> dict:
    from .material_supply_authority import material_supply_fact

    calculation = context["calculation"]
    material = context["material"]
    facts = [{
        "variable": binding.variable,
        "factCode": binding.fact_code,
        "factId": context["resolvedFacts"][binding.variable].pk,
        "detailId": context["resolvedFacts"][binding.variable].source_detail_id,
        "value": str(_fact_decimal(context["resolvedFacts"][binding.variable])),
        "uom": (
            context["resolvedFacts"][binding.variable].uom.code
            if context["resolvedFacts"][binding.variable].uom_id else None
        ),
        "sourcePath": context["resolvedFacts"][binding.variable].source_path,
    } for binding in contract.inputs]
    return {
        "serviceCode": SERVICE_CODE,
        "mappingNo": contract.mapping_no,
        "mappingRuleCode": contract.mapping_rule_code,
        "mappingVersion": contract.mapping_version,
        "mappingSpecificationHash": specification_hash(context["mappingSpecification"]),
        "order": {"id": context["order"].pk, "orderNo": context["order"].order_no},
        "salesOrderItem": {
            "id": calculation.sales_order_item_id,
            "lineNo": calculation.sales_order_item.line_no,
            "quantity": str(calculation.sales_order_item.quantity),
            "quantityMultiplierApplied": False,
        },
        "oei": {
            "id": calculation.engineering_instance_id,
            "instanceNo": calculation.engineering_instance.instance_no,
        },
        "calculation": {
            "id": calculation.pk,
            "calculationNo": calculation.calculation_no,
            "resultHash": calculation.result_hash,
            "reexecuted": False,
        },
        "designItem": {
            "id": context["designItem"].pk,
            "itemNo": context["designItem"].item_no,
            "physicalQuantity": str(context["designItem"].physical_quantity),
        },
        "material": {
            "id": material.pk,
            "code": material.code,
            "name": material.name,
            "uom": material.base_uom.code,
        },
        "sourceExternalIdentity": (
            context["orderSpecification"].get("sourceExternalIdentity")
        ),
        "materialSupplyFact": material_supply_fact(material, contract.supply_type),
        "purpose": contract.purpose_code,
        "quantityBasis": contract.quantity_basis,
        "quantityScope": "PRODUCT_DESIGN_ITEM",
        "expression": contract.expression,
        "quantity": str(context["quantity"]),
        "scrapRate": (
            str(contract.scrap_rate.quantize(Decimal("0.000001")))
            if contract.scrap_rate is not None else None
        ),
        "facts": facts,
        "factCodesUsed": [row["factCode"] for row in facts],
        "authorizationReference": contract.authorization_reference,
        "legacyAdoption": ({
            "id": context["legacyAdoption"].pk,
            "adoptionNo": context["legacyAdoption"].adoption_no,
            "lockedScope": context["legacyAdoption"].evidence_snapshot.get("scope"),
        } if context["legacyAdoption"] else None),
        "actor": context["actor"],
        "authorizations": authorizations or {},
        "databaseBusinessWriteCount": 0,
        "bomGenerated": False,
    }


def _preview_saved_fact_material_requirement(*, user, contract, _development_context=None) -> dict:
    context = _resolve_context(user=user, contract=contract, lock=False, _development_context=_development_context)
    view = _authorize(
        user=user,
        action_code="production.engineering.calculation.view",
        organization_id=context["order"].company_id,
        business_object={"calculationId": context["calculation"].pk},
    )
    return _serialize_preview(contract, context, authorizations={"calculationView": view})


def _mapping_identity(contract, context) -> dict:
    return {
        "sourceSystem": MAPPING_SOURCE_SYSTEM,
        "sourceType": MAPPING_SOURCE_TYPE,
        "sourceObjectType": "EngineeringMaterialRequirementMapping",
        "externalId": f"{contract.mapping_rule_code}:{contract.mapping_version}",
        "sourceFingerprint": specification_hash(context["mappingSpecification"]),
        "auditMetadata": {
            "serviceCode": SERVICE_CODE,
            "mappingNo": contract.mapping_no,
            "authorizationReference": contract.authorization_reference,
            "designItemNo": contract.design_item_no,
            "operatorId": context["actor"]["accountId"],
        },
    }


def _assert_mapping(rule, *, contract, context) -> None:
    expected = {
        "companyId": context["order"].company_id,
        "ruleCode": contract.mapping_rule_code,
        "ruleName": contract.rule_name,
        "version": contract.mapping_version,
        "ruleKind": "mapping",
        "specification": context["mappingSpecification"],
    }
    actual = {
        "companyId": rule.company_id,
        "ruleCode": rule.rule_code,
        "ruleName": rule.rule_name,
        "version": rule.version,
        "ruleKind": rule.rule_kind,
        "specification": rule.specification,
    }
    if canonical_json(actual) != canonical_json(expected):
        _fail(
            "EXISTING_MAPPING_CONFLICT",
            "同一Mapping编码/版本已存在不同正式内容，禁止覆盖。",
            ruleId=rule.pk,
        )


def _ensure_released_mapping(*, user, contract, context) -> dict:
    rule = EngineeringRuleDefinition.objects.select_for_update().filter(
        company_id=context["order"].company_id,
        rule_code=contract.mapping_rule_code,
        version=contract.mapping_version,
    ).first()
    mapping_created = 0
    mapping_audits = []
    mapping_transitions = []
    mapping_action_request_id = None
    mapping_external_identity_id = None
    if rule:
        _assert_mapping(rule, contract=contract, context=context)
    else:
        try:
            written = ProductionFoundationService.write(
                "engineering-rule-definitions",
                user=user,
                payload={
                    "company_id": context["order"].company_id,
                    "rule_code": contract.mapping_rule_code,
                    "rule_name": contract.rule_name,
                    "version": contract.mapping_version,
                    "rule_kind": "mapping",
                    "specification": context["mappingSpecification"],
                    "status": "draft",
                    "effective_from": _current_local_date(),
                    "effective_to": None,
                    "reason": f"{contract.authorization_reference}；{contract.mapping_no}正式Mapping",
                },
                idempotency_key=contract.mapping_idempotency_key,
                source_identity=_mapping_identity(contract, context),
            )
        except ProductionFoundationError as exc:
            raise SavedFactMaterialRequirementError(exc.code, exc.message, exc.details) from exc
        rule = EngineeringRuleDefinition.objects.select_for_update().get(pk=written["row"]["id"])
        mapping_created = int(not written.get("idempotentReplay", False))
        mapping_external_identity_id = written.get("sourceIdentityId")
        if written.get("auditId"):
            mapping_audits.append(written["auditId"])
        if written.get("transitionId"):
            mapping_transitions.append(written["transitionId"])
        ledger = MasterDataWriteRequest.objects.filter(
            organization_id=context["order"].company_id,
            action_code="production.master_data.create",
            idempotency_key=contract.mapping_idempotency_key,
        ).first()
        mapping_action_request_id = ledger.pk if ledger else None
    for target_status in ("reviewed", "released"):
        if rule.status == "released":
            break
        try:
            transitioned = EngineeringLifecycleService.transition(
                "engineering-rule-definitions",
                object_id=rule.pk,
                target_status=target_status,
                user=user,
                reason=f"{contract.authorization_reference}；{contract.mapping_no}正式确认",
            )
        except ProductionFoundationError as exc:
            raise SavedFactMaterialRequirementError(exc.code, exc.message, exc.details) from exc
        if transitioned.get("auditId"):
            mapping_audits.append(transitioned["auditId"])
        if transitioned.get("transitionId"):
            mapping_transitions.append(transitioned["transitionId"])
        rule.refresh_from_db()
    if rule.status != "released":
        _fail("MAPPING_RELEASE_REQUIRED", "Mapping未到达released，禁止创建Requirement。")
    _assert_mapping(rule, contract=contract, context=context)
    mapping_identity = ExternalIdentity.objects.filter(
        organization_id=context["order"].company_id,
        source_system=MAPPING_SOURCE_SYSTEM,
        source_type=MAPPING_SOURCE_TYPE,
        source_object_type="EngineeringMaterialRequirementMapping",
        external_id=f"{contract.mapping_rule_code}:{contract.mapping_version}",
        target_entity_type="engineering-rule-definitions",
        target_entity_id=str(rule.pk),
        mapping_status=ExternalIdentity.MappingStatus.MATCH,
    ).first()
    mapping_ledger = MasterDataWriteRequest.objects.filter(
        organization_id=context["order"].company_id,
        action_code="production.master_data.create",
        entity_type="engineering-rule-definitions",
        idempotency_key=contract.mapping_idempotency_key,
        status=MasterDataWriteRequest.Status.COMMITTED,
        target_entity_id=str(rule.pk),
    ).first()
    if not mapping_identity or not mapping_ledger:
        _fail("MAPPING_IDEMPOTENCY_EVIDENCE_REQUIRED", "Mapping缺少完整来源身份或幂等账本。")
    return {
        "rule": rule,
        "created": mapping_created,
        "auditIds": mapping_audits,
        "transitionIds": mapping_transitions,
        "actionRequestId": mapping_action_request_id or mapping_ledger.pk,
        "externalIdentityId": mapping_external_identity_id or mapping_identity.pk,
    }


def _requirement_source_identity(*, contract, context, lock: bool):
    lookup = {
        "organization_id": context["order"].company_id,
        "source_system": REQUIREMENT_SOURCE_SYSTEM,
        "source_type": REQUIREMENT_SOURCE_TYPE,
        "source_object_type": "ProductDesignItem",
        "external_id": f"{contract.design_item_no}:{contract.mapping_no}:{contract.mapping_version}",
    }
    query = ExternalIdentity.objects
    if lock:
        query = query.select_for_update()
    identity = query.filter(**lookup).first()
    fingerprint = _hash({
        "mappingSpecificationHash": specification_hash(context["mappingSpecification"]),
        "calculationResultHash": context["calculation"].result_hash,
        "quantity": str(context["quantity"]),
        "materialId": context["material"].pk,
    })
    if identity:
        if identity.target_entity_type != "engineering-material-requirements":
            _fail("SOURCE_IDENTITY_TARGET_CONFLICT", "Requirement来源身份已绑定其它实体类型。")
        if identity.source_fingerprint and identity.source_fingerprint != fingerprint:
            _fail("SOURCE_IDENTITY_FINGERPRINT_CONFLICT", "Requirement来源身份内容Hash已变化。")
        return identity, False, fingerprint
    identity = ExternalIdentity(
        **lookup,
        target_entity_type="engineering-material-requirements",
        mapping_status=ExternalIdentity.MappingStatus.CREATE,
        source_fingerprint=fingerprint,
        audit_metadata={
            "serviceCode": SERVICE_CODE,
            "mappingNo": contract.mapping_no,
            "authorizationReference": contract.authorization_reference,
            "calculationId": context["calculation"].pk,
            "designItemId": context["designItem"].pk,
        },
    )
    identity.full_clean()
    identity.save()
    return identity, True, fingerprint


def _requirement_payload(*, contract, context, mapping) -> dict:
    facts = [{
        "variable": binding.variable,
        "factCode": binding.fact_code,
        "factId": context["resolvedFacts"][binding.variable].pk,
        "sourceDetailId": context["resolvedFacts"][binding.variable].source_detail_id,
        "value": str(_fact_decimal(context["resolvedFacts"][binding.variable])),
        "uom": (
            context["resolvedFacts"][binding.variable].uom.code
            if context["resolvedFacts"][binding.variable].uom_id else None
        ),
        "sourcePath": context["resolvedFacts"][binding.variable].source_path,
    } for binding in contract.inputs]
    quantity = context["quantity"]
    rate = contract.scrap_rate
    gross_quantity = None
    scrap_rate_status = "not_maintained"
    if rate is not None:
        scrap_rate_status = "maintained"
        gross_quantity = (quantity / (Decimal("1") - rate)).quantize(Decimal("0.000001"))
    legacy = context["legacyAdoption"]
    trace = {
        "serviceCode": SERVICE_CODE,
        "contractCode": MAPPING_CONTRACT_CODE,
        "authorizationReference": contract.authorization_reference,
        "mappingNo": contract.mapping_no,
        "mappingRuleId": mapping.pk,
        "mappingRuleCode": mapping.rule_code,
        "mappingVersion": mapping.version,
        "mappingSpecificationHash": specification_hash(mapping.specification),
        "sourceFactId": context["primaryFact"].pk,
        "sourceDetailId": context["primaryFact"].source_detail_id,
        "sourceFacts": facts,
        "sourceFactCodes": [row["factCode"] for row in facts],
        "designItemId": context["designItem"].pk,
        "designItemNo": context["designItem"].item_no,
        "salesOrderId": context["order"].pk,
        "salesOrderItemId": context["calculation"].sales_order_item_id,
        "salesOrderItemQuantity": str(context["calculation"].sales_order_item.quantity),
        "orderEngineeringInstanceId": context["calculation"].engineering_instance_id,
        "orderEngineeringInstanceNo": context["calculation"].engineering_instance.instance_no,
        "calculationId": context["calculation"].pk,
        "calculationNo": context["calculation"].calculation_no,
        "calculationResultHash": context["calculation"].result_hash,
        "sourceRecordId": context["calculation"].source_record_id,
        "quantitySource": "SAVED_DERIVED_FACT_FORMULA",
        "quantityExpression": contract.expression,
        "quantityScope": "PRODUCT_DESIGN_ITEM",
        "salesItemMultiplier": "NOT_APPLIED",
        "orderQuantityMultiplierApplied": False,
        "productDesignItemQuantityApplied": True,
        "structureRole": contract.purpose_code,
        "scrapRate": str(rate.quantize(Decimal("0.000001"))) if rate is not None else None,
        "calculationReexecuted": False,
        "wUsedAsQuantityBasis": (
            any(row.fact_code == "W" for row in contract.inputs)
            if contract.source_external_identity_id is not None else False
        ),
        "xUsedAsMaterialQuantityBasis": (
            any(row.fact_code == "X" for row in contract.inputs)
            if contract.source_external_identity_id is not None else False
        ),
        "legacyAdoptionId": legacy.pk if legacy else None,
        "legacyAdoptionNo": legacy.adoption_no if legacy else None,
        "legacyScope": legacy.evidence_snapshot.get("scope") if legacy else None,
        "operatorId": context["actor"]["accountId"],
        "operator": context["actor"]["account"],
        "workflowResponsibility": context["actor"]["workflowResponsibility"],
        "provenance": contract.provenance,
    }
    if context["sourceExternalIdentity"]:
        trace["sourceMaterialExternalIdentity"] = context["orderSpecification"][
            "sourceExternalIdentity"
        ]
    return {
        "calculation": context["calculation"],
        "source_detail": context["primaryFact"].source_detail,
        "sequence": context["primaryFact"].source_detail.sequence,
        "material": context["material"],
        "quantity_basis": contract.quantity_basis,
        "calculated_quantity": quantity,
        "order_quantity": Decimal(str(context["calculation"].sales_order_item.quantity)),
        "net_quantity": quantity,
        "gross_quantity": gross_quantity,
        "uom": context["material"].base_uom,
        "item_role": contract.item_role,
        "requirement_type": contract.requirement_type,
        "supply_type": contract.supply_type,
        "order_specification": context["orderSpecification"],
        "scrap_rate_status": scrap_rate_status,
        "scrap_rate": rate,
        "source_path": (
            f"calculation[{context['calculation'].pk}].derivedFacts"
            f"[{','.join(row['factCode'] for row in facts)}]"
        ),
        "trace": trace,
    }


def _assert_requirement(requirement, *, contract, context, mapping) -> None:
    payload = _requirement_payload(
        contract=contract, context=context, mapping=mapping,
    )
    exact_fields = (
        "calculation_id", "source_detail_id", "sequence", "material_id",
        "quantity_basis", "calculated_quantity", "order_quantity", "net_quantity",
        "gross_quantity", "uom_id", "item_role", "requirement_type", "supply_type",
        "order_specification", "scrap_rate_status", "scrap_rate", "source_path", "trace",
    )
    expected = EngineeringMaterialRequirement(**payload)
    mismatch = [field for field in exact_fields if getattr(requirement, field) != getattr(expected, field)]
    if mismatch:
        _fail(
            "EXISTING_REQUIREMENT_CONFLICT",
            "既有正式Requirement与本次授权合同不一致，禁止覆盖。",
            requirementId=requirement.pk,
            mismatchedFields=mismatch,
        )


def _serialize_requirement(requirement, *, mapping, action_request, audit) -> dict:
    return {
        "requirementId": requirement.pk,
        "calculationId": requirement.calculation_id,
        "sourceDetailId": requirement.source_detail_id,
        "materialId": requirement.material_id,
        "materialCode": requirement.material.code,
        "materialName": requirement.material.name,
        "calculatedQuantity": str(requirement.calculated_quantity),
        "orderQuantity": str(requirement.order_quantity),
        "netQuantity": str(requirement.net_quantity),
        "grossQuantity": (
            str(requirement.gross_quantity) if requirement.gross_quantity is not None else None
        ),
        "uom": requirement.uom.code,
        "quantityBasis": requirement.quantity_basis,
        "itemRole": requirement.item_role,
        "requirementType": requirement.requirement_type,
        "supplyType": requirement.supply_type,
        "scrapRate": str(requirement.scrap_rate) if requirement.scrap_rate is not None else None,
        "scrapRateStatus": requirement.scrap_rate_status,
        "purpose": (requirement.trace or {}).get("structureRole"),
        "quantityExpression": (requirement.trace or {}).get("quantityExpression"),
        "sourceFacts": (requirement.trace or {}).get("sourceFacts"),
        "salesItemMultiplier": (requirement.trace or {}).get("salesItemMultiplier"),
        "orderQuantityMultiplierApplied": (requirement.trace or {}).get("orderQuantityMultiplierApplied"),
        "wUsedAsQuantityBasis": (requirement.trace or {}).get("wUsedAsQuantityBasis"),
        "xUsedAsMaterialQuantityBasis": (requirement.trace or {}).get("xUsedAsMaterialQuantityBasis"),
        "mapping": {
            "id": mapping.pk,
            "ruleCode": mapping.rule_code,
            "version": mapping.version,
            "status": mapping.status,
            "specificationHash": specification_hash(mapping.specification),
        },
        "actionRequest": {
            "id": action_request.pk,
            "status": action_request.status,
            "idempotencyKey": action_request.idempotency_key,
            "requestHash": action_request.request_hash,
        },
        "audit": {
            "id": audit.pk,
            "actionCode": audit.action_code,
            "actor": audit.actor.username,
        },
        "trace": requirement.trace,
    }


@transaction.atomic
def _apply_saved_fact_material_requirement(*, user, contract, _development_context=None) -> dict:
    context = _resolve_context(user=user, contract=contract, lock=True, _development_context=_development_context)
    business_object = {
        "calculationId": context["calculation"].pk,
        "salesOrderItemId": context["calculation"].sales_order_item_id,
        "designItemId": context["designItem"].pk,
    }
    authorizations = {
        "calculationView": _authorize(
            user=user,
            action_code="production.engineering.calculation.view",
            organization_id=context["order"].company_id,
            business_object=business_object,
        ),
        "calculationExecute": _authorize(
            user=user,
            action_code="production.engineering.calculation.execute",
            organization_id=context["order"].company_id,
            business_object=business_object,
        ),
        "ruleMaintain": _authorize(
            user=user,
            action_code="production.engineering.rule.maintain",
            organization_id=context["order"].company_id,
            business_object=business_object,
        ),
        "ruleRelease": _authorize(
            user=user,
            action_code="production.engineering.rule.release",
            organization_id=context["order"].company_id,
            business_object=business_object,
        ),
        "bomMaintain": _authorize(
            user=user,
            action_code="production.master_data.bom.maintain",
            organization_id=context["order"].company_id,
            business_object=business_object,
        ),
    }
    historical = MasterDataWriteRequest.objects.filter(
        organization_id=context["order"].company_id,
        entity_type="EngineeringMaterialRequirement",
        action_code=REQUIREMENT_ACTION_CODE,
        idempotency_key=contract.requirement_idempotency_key,
        status=MasterDataWriteRequest.Status.COMMITTED,
    ).exists()
    if not historical:
        from .material_supply_authority import material_supply_fact
        supply = material_supply_fact(context["material"], contract.supply_type)
        if not supply["allowed"]:
            _fail(supply["code"], supply["message"], materialSupplyFact=supply)
    mapping_result = _ensure_released_mapping(
        user=user, contract=contract, context=context,
    )
    mapping = mapping_result["rule"]
    identity, identity_created, fingerprint = _requirement_source_identity(
        contract=contract, context=context, lock=True,
    )
    request_payload = {
        "serviceCode": SERVICE_CODE,
        "mappingRuleId": mapping.pk,
        "mappingSpecificationHash": specification_hash(mapping.specification),
        "calculationId": context["calculation"].pk,
        "calculationResultHash": context["calculation"].result_hash,
        "designItemId": context["designItem"].pk,
        "designItemNo": context["designItem"].item_no,
        "materialId": context["material"].pk,
        "quantity": str(context["quantity"]),
        "uom": context["material"].base_uom.code,
        "purpose": contract.purpose_code,
        "authorizationReference": contract.authorization_reference,
    }
    if context["sourceExternalIdentity"]:
        request_payload["sourceExternalIdentityId"] = context["sourceExternalIdentity"].pk
    request_hash = _hash(request_payload)
    ledger = MasterDataWriteRequest.objects.select_for_update().filter(
        organization_id=context["order"].company_id,
        action_code=REQUIREMENT_ACTION_CODE,
        entity_type="EngineeringMaterialRequirement",
        idempotency_key=contract.requirement_idempotency_key,
    ).first()
    if ledger:
        if ledger.request_hash != request_hash or ledger.source_identity_id != identity.pk:
            _fail("IDEMPOTENCY_PAYLOAD_CONFLICT", "同一Requirement幂等键不得提交不同内容。")
        requirement = EngineeringMaterialRequirement.objects.select_for_update().filter(
            pk=ledger.target_entity_id,
        ).select_related("material", "uom").first()
        if ledger.status != MasterDataWriteRequest.Status.COMMITTED or not requirement:
            _fail("IDEMPOTENT_RESULT_INCOMPLETE", "Requirement幂等账本没有完整提交结果。")
        _assert_requirement(requirement, contract=contract, context=context, mapping=mapping)
        audit = OrganizationOperatingAuditRecord.objects.filter(
            pk=(ledger.result or {}).get("auditId"),
            action_code=REQUIREMENT_ACTION_CODE,
            target_type="EngineeringMaterialRequirement",
            target_id=requirement.pk,
            actor=user,
        ).select_related("actor").defer("actor__password").first()
        if not audit:
            _fail("REQUIREMENT_AUDIT_REQUIRED", "Requirement幂等结果缺少正式审计。")
        return {
            "serviceCode": SERVICE_CODE,
            "idempotent": True,
            "businessWriteCount": 0,
            "mappingWriteCount": 0,
            "mappingActionRequestWriteCount": 0,
            "mappingExternalIdentityWriteCount": 0,
            "mappingTransitionWriteCount": 0,
            "requirementWriteCount": 0,
            "auditWriteCount": 0,
            "actionRequestWriteCount": 0,
            "externalIdentityWriteCount": 0,
            "calculationReexecuted": False,
            "bomGenerated": False,
            "preview": _serialize_preview(contract, context, authorizations=authorizations),
            "requirement": _serialize_requirement(
                requirement, mapping=mapping, action_request=ledger, audit=audit,
            ),
        }

    existing_requirement = EngineeringMaterialRequirement.objects.select_for_update().filter(
        Q(source_detail_id=context["primaryFact"].source_detail_id)
        | Q(
            calculation_id=context["calculation"].pk,
            sequence=context["primaryFact"].source_detail.sequence,
        )
    ).first()
    if existing_requirement:
        _fail(
            "EXISTING_REQUIREMENT_WITHOUT_IDEMPOTENCY_LEDGER",
            "来源Detail或序号已有Requirement但缺本次幂等账本，禁止静默接管。",
            requirementId=existing_requirement.pk,
        )
    ledger = MasterDataWriteRequest.objects.create(
        organization_id=context["order"].company_id,
        action_code=REQUIREMENT_ACTION_CODE,
        entity_type="EngineeringMaterialRequirement",
        idempotency_key=contract.requirement_idempotency_key,
        request_hash=request_hash,
        source_identity=identity,
        status=MasterDataWriteRequest.Status.RESERVED,
        audit_metadata={
            "serviceCode": SERVICE_CODE,
            "authorizationReference": contract.authorization_reference,
            "actor": context["actor"],
            "authorizationDecisionCodes": {
                key: value.get("decisionCode") for key, value in authorizations.items()
            },
        },
    )
    requirement = EngineeringMaterialRequirement(**_requirement_payload(
        contract=contract, context=context, mapping=mapping,
    ))
    try:
        requirement.full_clean()
        requirement.save()
    except ValidationError as exc:
        _fail(
            "REQUIREMENT_VALIDATION_FAILED",
            "正式Material Requirement校验失败。",
            errors=getattr(exc, "message_dict", {"all": exc.messages}),
        )
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=REQUIREMENT_ACTION_CODE,
        actor=user,
        organization_id=context["order"].company_id,
        target_type="EngineeringMaterialRequirement",
        target_id=requirement.pk,
        target_label=f"{contract.mapping_no} / {context['material'].code}"[:200],
        reason=f"{contract.authorization_reference}；已保存事实公式承接"[:300],
        before_snapshot={},
        after_snapshot={
            "request": request_payload,
            "requirementId": requirement.pk,
            "sourceDetailId": requirement.source_detail_id,
            "sourceFacts": requirement.trace["sourceFacts"],
            "orderQuantityMultiplierApplied": False,
            "calculationReexecuted": False,
            "bomGenerated": False,
            "authorizations": authorizations,
            "factSource": "server",
        },
    )
    identity.target_entity_id = str(requirement.pk)
    identity.target_entity_type = "engineering-material-requirements"
    identity.mapping_status = ExternalIdentity.MappingStatus.MATCH
    identity.source_fingerprint = fingerprint
    identity.full_clean()
    identity.save(update_fields=(
        "target_entity_id", "target_entity_type", "mapping_status",
        "source_fingerprint", "last_seen",
    ))
    ledger.status = MasterDataWriteRequest.Status.COMMITTED
    ledger.target_entity_id = str(requirement.pk)
    ledger.result = {
        "requirementId": requirement.pk,
        "mappingRuleId": mapping.pk,
        "auditId": audit.pk,
        "externalIdentityId": identity.pk,
        "quantity": str(requirement.net_quantity),
        "uom": requirement.uom.code,
    }
    ledger.save(update_fields=("status", "target_entity_id", "result", "updated_at"))
    direct_writes = (
        mapping_result["created"]
        + mapping_result["created"]  # Mapping action request
        + mapping_result["created"]  # Mapping external identity
        + len(mapping_result["auditIds"])
        + len(mapping_result["transitionIds"])
        + 1  # Requirement
        + 1  # Requirement audit
        + 1  # Requirement action request
        + int(identity_created)
    )
    return {
        "serviceCode": SERVICE_CODE,
        "idempotent": False,
        "businessWriteCount": direct_writes,
        "mappingWriteCount": mapping_result["created"],
        "mappingActionRequestWriteCount": mapping_result["created"],
        "mappingExternalIdentityWriteCount": mapping_result["created"],
        "mappingAuditWriteCount": len(mapping_result["auditIds"]),
        "mappingTransitionWriteCount": len(mapping_result["transitionIds"]),
        "requirementWriteCount": 1,
        "auditWriteCount": 1,
        "actionRequestWriteCount": 1,
        "externalIdentityWriteCount": int(identity_created),
        "mappingActionRequestId": mapping_result["actionRequestId"],
        "mappingExternalIdentityId": mapping_result["externalIdentityId"],
        "calculationReexecuted": False,
        "bomGenerated": False,
        "preview": _serialize_preview(contract, context, authorizations=authorizations),
        "requirement": _serialize_requirement(
            requirement, mapping=mapping, action_request=ledger, audit=audit,
        ),
    }


def _readback_saved_fact_material_requirement(*, user, contract, _development_context=None) -> dict:
    context = _resolve_context(user=user, contract=contract, lock=False, _development_context=_development_context)
    _authorize(
        user=user,
        action_code="production.engineering.calculation.view",
        organization_id=context["order"].company_id,
        business_object={"calculationId": context["calculation"].pk},
    )
    mapping = EngineeringRuleDefinition.objects.filter(
        company_id=context["order"].company_id,
        rule_code=contract.mapping_rule_code,
        version=contract.mapping_version,
        status="released",
    ).first()
    if not mapping:
        _fail("MAPPING_READBACK_MISSING", "正式Mapping Readback不存在或未发布。")
    _assert_mapping(mapping, contract=contract, context=context)
    ledger = MasterDataWriteRequest.objects.filter(
        organization_id=context["order"].company_id,
        action_code=REQUIREMENT_ACTION_CODE,
        entity_type="EngineeringMaterialRequirement",
        idempotency_key=contract.requirement_idempotency_key,
        status=MasterDataWriteRequest.Status.COMMITTED,
    ).first()
    if not ledger:
        _fail("REQUIREMENT_ACTION_REQUEST_MISSING", "Requirement缺少已提交幂等账本。")
    requirement = EngineeringMaterialRequirement.objects.filter(
        pk=ledger.target_entity_id,
    ).select_related("material", "uom").first()
    if not requirement:
        _fail("REQUIREMENT_READBACK_MISSING", "正式Requirement Readback不存在。")
    _assert_requirement(requirement, contract=contract, context=context, mapping=mapping)
    audit = OrganizationOperatingAuditRecord.objects.filter(
        pk=(ledger.result or {}).get("auditId"),
        action_code=REQUIREMENT_ACTION_CODE,
        target_type="EngineeringMaterialRequirement",
        target_id=requirement.pk,
        actor=user,
    ).select_related("actor").defer("actor__password").first()
    if not audit:
        _fail("REQUIREMENT_AUDIT_REQUIRED", "正式Requirement缺少匹配审计。")
    return {
        "serviceCode": SERVICE_CODE,
        "readbackMatch": True,
        "calculationReexecuted": False,
        "bomGenerated": False,
        "requirement": _serialize_requirement(
            requirement, mapping=mapping, action_request=ledger, audit=audit,
        ),
    }


def preview_saved_fact_material_requirement(*, user, contract) -> dict:
    """Ordinary entry: always retain the original current CRM admission."""
    return _preview_saved_fact_material_requirement(user=user, contract=contract)


def apply_saved_fact_material_requirement(*, user, contract) -> dict:
    return _apply_saved_fact_material_requirement(user=user, contract=contract)


def readback_saved_fact_material_requirement(*, user, contract) -> dict:
    return _readback_saved_fact_material_requirement(user=user, contract=contract)
