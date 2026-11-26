"""Controlled pine Material and casing-frame Requirement workflow.

The production services stay order- and material-neutral.  This module only
binds the user-authorized SO202609180003 execution scope to those services.
Default mode is read-only inspection; ``--apply`` is restricted to the known
formal acceptance database unless ``--allow-isolated`` is explicitly used by
the isolated verification harness.
"""

from __future__ import annotations

import argparse
import json
import os
import site
import sys
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FORMAL_DATABASE = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
).resolve()
COMPANY_CODE = "COMP001"
ORDER_NO = "SO202609180003"
CALCULATION_ID = 3
MATERIAL_ACTOR = "emd_emp047"
REQUIREMENT_ACTOR = "pce_plan_r12"
CATEGORY_CODE = "MATCAT-SOLID-WOOD"
CATEGORY_NAME = "实木"
MATERIAL_NAME = "松木"
MATERIAL_PURPOSE = "木方 / 骨架材料"
MATERIAL_SPECIFICATION = "30×40 mm"
MATERIAL_APPLICATION_NOTES = "门框、门套等外部结构骨架"
MATERIAL_IDEMPOTENCY_KEY = "PINE-30X40-MATERIAL:COMP001:20261006:V1"
AUTHORIZATION_REFERENCE = (
    "USER_INSTRUCTION:SO202609180003:LINE1:PINE-30X40-CASING-FRAME:2026-10-06"
)
FORMULA_CODE = "CASING_FRAME_LENGTH"
FORMULA_EXPRESSION = "(2*N+O)*Q/1000"
STRUCTURE_ROLE = "DOOR_CASING_MATERIAL"
STRUCTURE_ROLE_DETAIL = "DOOR_CASING_STRUCTURAL_FRAME"
DESIGN_SUFFIXES = (3, 4, 5, 6, 7)
REFERENCE_FACTS = {
    3: (Decimal("2035"), Decimal("920"), Decimal("1"), Decimal("4.990000")),
    4: (Decimal("2035"), Decimal("840"), Decimal("1"), Decimal("4.910000")),
    5: (Decimal("2035"), Decimal("865"), Decimal("1"), Decimal("4.935000")),
    6: (Decimal("2035"), Decimal("800"), Decimal("1"), Decimal("4.870000")),
    7: (Decimal("2040"), Decimal("817"), Decimal("1"), Decimal("4.897000")),
}


class PineCasingWorkflowError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def fail(code: str, message: str, **details):
    raise PineCasingWorkflowError(code, message, details)


def configure(database: Path) -> None:
    database = database.resolve()
    if not database.is_file():
        raise RuntimeError("DATABASE_NOT_FOUND")
    site.addsitedir(str(BACKEND / "venv/Lib/site-packages"))
    sys.path.insert(0, str(BACKEND))
    os.environ["PCE_DATABASE_PATH"] = str(database)
    if database == FORMAL_DATABASE:
        os.environ["PCE_DATABASE_IDENTITY"] = "PDE-OPERABLE-ACCEPTANCE-20260912"
        os.environ["PCE_NON_PRODUCTION_ACCEPTANCE"] = "1"
        os.environ["PCE_RUNTIME_PROFILE"] = "PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE"
    else:
        for key in (
            "PCE_DATABASE_IDENTITY",
            "PCE_NON_PRODUCTION_ACCEPTANCE",
            "PCE_RUNTIME_PROFILE",
            "PCE_RUNTIME_LAUNCHER_VERIFIED",
        ):
            os.environ.pop(key, None)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")
    import django

    django.setup()


def decimal_fact_value(fact) -> Decimal:
    raw = fact.value.get("decimal") if isinstance(fact.value, dict) else fact.value
    try:
        return Decimal(str(raw))
    except Exception as exc:  # pragma: no cover - guarded by formal fact service
        raise PineCasingWorkflowError(
            "SAVED_FACT_DECIMAL_REQUIRED", "N/O/Q事实不是合法十进制数值。",
            {"factId": fact.pk, "value": raw},
        ) from exc


def actor_preflight(username: str, *, material_actor: bool) -> dict:
    from system.authorization import AuthorizationService
    from system.models import Company, User

    company = Company.objects.get(code=COMPANY_CODE, is_active=True)
    user = User.objects.filter(
        username=username, company_id=company.pk, is_active=True,
    ).first()
    if not user or user.is_superuser:
        fail("FORMAL_ACTOR_INVALID", "正式执行账号不存在、已停用或为管理员。", username=username)
    action_code = (
        "production.master_data.material.maintain"
        if material_actor else "production.engineering.calculation.view"
    )
    decision = AuthorizationService.decide(
        user=user,
        action_code=action_code,
        organization_id=user.company_id,
        business_object={"organizationId": user.company_id, "calculationId": CALCULATION_ID},
    )
    if not decision.get("allowed"):
        fail(
            decision.get("decisionCode", "PERMISSION_DENIED"),
            decision.get("reason", "正式执行账号无权执行本轮动作。"),
            username=username,
            authorization=decision,
        )
    return {
        "user": user,
        "readback": {
            "id": user.pk,
            "username": user.username,
            "companyId": user.company_id,
            "isActive": user.is_active,
            "isSuperuser": user.is_superuser,
            "authorization": decision,
        },
    }


def canonical_material_state() -> dict:
    from masterdata.material_identity import canonical_identity, matching_materials
    from masterdata.models import MaterialCategory, UnitOfMeasure
    from system.models import Company

    company = Company.objects.get(code=COMPANY_CODE, is_active=True)
    category = MaterialCategory.objects.filter(
        company_id=company.pk, code=CATEGORY_CODE, is_active=True,
    ).first()
    if not category or category.name != CATEGORY_NAME:
        fail(
            "MATERIAL_CATEGORY_IDENTITY_MISMATCH",
            "正式实木MaterialCategory不存在、已停用或业务名称不一致。",
        )
    meter = UnitOfMeasure.objects.filter(
        company_id=company.pk, code="m", is_active=True,
    ).first()
    if not meter or meter.name != "米" or meter.dimension != "length":
        fail("METER_UOM_IDENTITY_MISMATCH", "正式m/米长度单位不存在或身份不一致。")
    identity_values = {
        "name": MATERIAL_NAME,
        "category_id": category.pk,
        "purpose": MATERIAL_PURPOSE,
        "specification": MATERIAL_SPECIFICATION,
        "base_uom_id": meter.pk,
    }
    matches = matching_materials(
        company_id=company.pk,
        identity=canonical_identity(values=identity_values),
    )
    active = [row for row in matches if row.is_active]
    inactive = [row for row in matches if not row.is_active]
    if len(active) > 1:
        fail(
            "DUPLICATE_ACTIVE_MATERIAL",
            "公司范围内存在多条完全相同active松木Material。",
            materialIds=[row.pk for row in active],
        )
    return {
        "company": company,
        "category": category,
        "meter": meter,
        "identityValues": identity_values,
        "active": active,
        "inactive": inactive,
    }


def serialize_material(material) -> dict:
    return {
        "id": material.pk,
        "code": material.code,
        "name": material.name,
        "category": {
            "id": material.category_id,
            "code": material.category.code,
            "name": material.category.name,
        },
        "purpose": material.purpose,
        "specification": material.specification,
        "applicationNotes": material.application_notes,
        "baseUom": {
            "id": material.base_uom_id,
            "code": material.base_uom.code,
            "name": material.base_uom.name,
        },
        "isPurchased": material.is_purchased,
        "isProduced": material.is_produced,
        "supplyType": material.supply_type,
        "isActive": material.is_active,
    }


def ensure_canonical_material(*, user, create: bool) -> dict:
    from masterdata.models import MasterDataWriteRequest, Material
    from pde.production_foundation_service import ProductionFoundationError, ProductionFoundationService

    state = canonical_material_state()
    if state["active"]:
        material = Material.objects.select_related("category", "base_uom").get(
            pk=state["active"][0].pk,
        )
        if material.application_notes != MATERIAL_APPLICATION_NOTES:
            fail(
                "ACTIVE_CANONICAL_MATERIAL_DETAIL_CONFLICT",
                "完全相同active Material的应用说明与本轮正式事实冲突。",
                material=serialize_material(material),
            )
        if material.is_purchased or material.is_produced:
            fail(
                "ACTIVE_CANONICAL_MATERIAL_SUPPLY_CONFLICT",
                "完全相同active Material已带采购或自产事实，与本轮待确认边界冲突。",
                material=serialize_material(material),
            )
        return {
            "decision": "REUSE_ACTIVE_CANONICAL",
            "material": material,
            "readback": serialize_material(material),
            "canonicalActiveCount": 1,
            "canonicalInactiveCount": len(state["inactive"]),
            "businessWriteCount": 0,
            "idempotentReplay": True,
        }
    if state["inactive"]:
        fail(
            "INACTIVE_MATERIAL_CANDIDATE_REQUIRES_DECISION",
            "存在完全相同inactive松木Material；禁止自动重启或另建。",
            inactiveCandidates=[serialize_material(row) for row in state["inactive"]],
        )
    if not create:
        return {
            "decision": "CREATE_REQUIRED",
            "material": None,
            "readback": None,
            "canonicalActiveCount": 0,
            "canonicalInactiveCount": 0,
            "businessWriteCount": 0,
            "idempotentReplay": False,
        }
    try:
        result = ProductionFoundationService.write(
            "materials",
            user=user,
            payload={
                "company_id": state["company"].pk,
                "name": MATERIAL_NAME,
                "category_id": state["category"].pk,
                "purpose": MATERIAL_PURPOSE,
                "specification": MATERIAL_SPECIFICATION,
                "application_notes": MATERIAL_APPLICATION_NOTES,
                "unit": "",
                "unit_status": "confirmed",
                "base_uom_id": state["meter"].pk,
                "purchase_uom_id": None,
                "material_type": "raw",
                "is_purchased": False,
                "is_produced": False,
                "is_active": True,
                "reason": "用户正式确认门套/门框主体松木规格30×40 mm；供应属性保持待确认。",
            },
            idempotency_key=MATERIAL_IDEMPOTENCY_KEY,
            source_identity={
                "sourceSystem": "PCE",
                "sourceType": "USER_CONFIRMED_BUSINESS_DECISION",
                "sourceObjectType": "MATERIAL",
                "externalId": "COMP001:PINE:30X40-MM:CASING-FRAME",
                "auditMetadata": {
                    "authorizationReference": AUTHORIZATION_REFERENCE,
                    "businessFact": "PINE_30X40_MM",
                    "supplyStatus": "PENDING_CONFIRMATION",
                },
            },
        )
    except ProductionFoundationError as exc:
        raise PineCasingWorkflowError(exc.code, exc.message, exc.details) from exc
    material = Material.objects.select_related("category", "base_uom").get(
        pk=result["row"]["id"],
    )
    final_state = canonical_material_state()
    if len(final_state["active"]) != 1 or final_state["active"][0].pk != material.pk:
        fail("CANONICAL_MATERIAL_READBACK_FAILED", "松木Material保存后canonical readback不唯一。")
    ledger = MasterDataWriteRequest.objects.filter(
        organization_id=material.company_id,
        action_code="production.master_data.create",
        entity_type="materials",
        idempotency_key=MATERIAL_IDEMPOTENCY_KEY,
    ).first()
    return {
        "decision": "CREATED" if not result.get("idempotentReplay") else "IDEMPOTENT_REPLAY",
        "material": material,
        "readback": serialize_material(material),
        "canonicalActiveCount": len(final_state["active"]),
        "canonicalInactiveCount": len(final_state["inactive"]),
        "businessWriteCount": 0 if result.get("idempotentReplay") else 4,
        "idempotentReplay": bool(result.get("idempotentReplay")),
        "auditId": result.get("auditId"),
        "actionRequestId": result.get("actionRequestId") or (ledger.pk if ledger else None),
        "externalIdentityId": result.get("sourceIdentityId"),
        "executionChain": result.get("executionChain"),
        "authorization": result.get("authorization"),
    }


def fact_bundle(suffix: int) -> dict:
    from pde.models import EngineeringDerivedFact, ProductDesignItem

    item_no = f"{ORDER_NO}-DES-01-SRC-{suffix:04d}"
    item = ProductDesignItem.objects.select_related(
        "sales_order_item__sales_order", "source_record",
    ).filter(item_no=item_no).first()
    if not item:
        fail("DESIGN_ITEM_NOT_FOUND", "门套Requirement目标设计对象不存在。", designItemNo=item_no)
    if item.sales_order_item.sales_order.order_no != ORDER_NO or item.sales_order_item.line_no != 1:
        fail("DESIGN_ITEM_ORDER_SCOPE_MISMATCH", "目标设计对象不属于授权订单行1。", designItemNo=item_no)
    facts = {}
    for code in ("N", "O", "Q"):
        rows = list(EngineeringDerivedFact.objects.select_related(
            "uom", "source_detail", "calculation__engineering_instance",
        ).filter(
            calculation_id=CALCULATION_ID,
            fact_code=f"{item_no}:{code}",
            canonical_field=code,
            status="active",
        ))
        if len(rows) != 1:
            fail(
                "SAVED_FACT_INPUT_NOT_UNIQUE",
                "门套N/O/Q必须分别精确对应一个当前已保存事实。",
                designItemNo=item_no,
                factCode=code,
                matchCount=len(rows),
            )
        facts[code] = rows[0]
    n, o, q = (decimal_fact_value(facts[code]) for code in ("N", "O", "Q"))
    if facts["N"].uom.code != "mm" or facts["O"].uom.code != "mm" or facts["Q"].uom_id:
        fail("CASING_FACT_UOM_MISMATCH", "N/O必须为mm且Q必须为无量纲计数。", designItemNo=item_no)
    if q <= 0 or q != q.to_integral_value():
        fail("CASING_QUANTITY_FACT_INVALID", "Q必须是大于0的整数。", designItemNo=item_no, value=str(q))
    quantity = ((Decimal("2") * n + o) * q / Decimal("1000")).quantize(Decimal("0.000001"))
    reference = REFERENCE_FACTS[suffix]
    if (n, o, q, quantity) != reference:
        fail(
            "CURRENT_CASING_FACT_CONFLICT",
            "数据库当前N/O/Q或计算结果与本轮已知Readback事实冲突。",
            designItemNo=item_no,
            expected=[str(value) for value in reference],
            actual=[str(n), str(o), str(q), str(quantity)],
        )
    return {
        "suffix": suffix,
        "item": item,
        "itemNo": item_no,
        "facts": facts,
        "N": n,
        "O": o,
        "Q": q,
        "quantity": quantity,
    }


def build_contract(*, material, bundle):
    from pde.saved_fact_material_requirement_service import (
        SavedFactInputBinding,
        SavedFactMaterialRequirementContract,
    )

    suffix = bundle["suffix"]
    return SavedFactMaterialRequirementContract(
        mapping_no=f"MRC-CASING-{suffix:04d}",
        mapping_rule_code=f"MRM.{ORDER_NO}.CASING-{suffix:04d}",
        mapping_version="V1",
        rule_name=f"{FORMULA_CODE} / DES-01-SRC-{suffix:04d}",
        order_no=ORDER_NO,
        calculation_id=CALCULATION_ID,
        design_item_no=bundle["itemNo"],
        material_id=material.pk,
        material_code=material.code,
        output_uom_code="m",
        output_name="casing_frame_net_length",
        expression=FORMULA_EXPRESSION,
        inputs=(
            SavedFactInputBinding("N", "N", "mm", "length"),
            SavedFactInputBinding("O", "O", "mm", "length"),
            SavedFactInputBinding(
                "Q", "Q", None, None, unit_required=False, integer_required=True,
            ),
        ),
        primary_source_fact_code="N",
        expected_quantity=bundle["quantity"],
        authorization_reference=f"{AUTHORIZATION_REFERENCE}:DES01-{suffix:04d}",
        idempotency_key=f"{ORDER_NO}:LINE1:{FORMULA_CODE}:{suffix:04d}:V1",
        purpose_code=STRUCTURE_ROLE,
        quantity_basis="ORDER_TOTAL",
        item_role="material",
        requirement_type="manufacturing",
        supply_type="MAKE_OR_BUY",
        scrap_rate=Decimal("0"),
        order_specification={
            "businessPurpose": "FORMAL_SALE",
            "businessMeaning": "当前设计对象门套主体左竖边、右竖边与上横边的结构骨架净长度",
            "materialPurpose": MATERIAL_PURPOSE,
            "structureRoleDetail": STRUCTURE_ROLE_DETAIL,
            "formulaCode": FORMULA_CODE,
            "formula": FORMULA_EXPRESSION,
            "lossPolicy": "ZERO_LOSS_ENGINEERING_NET_REQUIREMENT",
            "supplyStatus": "PENDING_CONFIRMATION",
            "excludedFactCodes": ["P", "X"],
            "excludedMaterialCategories": ["CASING_TRIM", "EDGE_BANDING"],
        },
        provenance={
            "decisionDate": "2026-10-06",
            "decisionSource": "USER_EXPLICIT_BUSINESS_DECISION",
            "materialSpecification": MATERIAL_SPECIFICATION,
            "sourceFactCodes": ["N", "O", "Q"],
            "formulaCode": FORMULA_CODE,
            "formula": FORMULA_EXPRESSION,
            "loss": 0,
            "salesOrderItemQuantityMultiplierApplied": False,
            "P": "PRESERVED_NOT_USED_AS_MATERIAL_SECTION_OR_QUANTITY",
            "X": "PRESERVED_NOT_USED_AS_PINE_QUANTITY",
            "casingTrim": "OUT_OF_SCOPE_NOT_USED",
            "edgeBanding": "OUT_OF_SCOPE_NOT_USED",
            "designMaterialReferencePolicy": "STRUCTURE_REQUIREMENT_DOES_NOT_REPLACE_DESIGN_PRIMARY_MATERIAL",
        },
        output_scale=6,
        output_unit_dimension="length",
        require_design_material_reference=False,
    )


def build_contracts(material) -> tuple[list, list]:
    bundles = [fact_bundle(suffix) for suffix in DESIGN_SUFFIXES]
    return bundles, [build_contract(material=material, bundle=row) for row in bundles]


def execute(*, create: bool, apply: bool, allow_generate_if_ready: bool) -> dict:
    from django.db import transaction
    from pde.engineering_calculation_service import OrderEngineeringClosureService
    from pde.saved_fact_material_requirement_service import (
        apply_saved_fact_material_requirement,
        preview_saved_fact_material_requirement,
        readback_saved_fact_material_requirement,
    )

    material_actor = actor_preflight(MATERIAL_ACTOR, material_actor=True)
    requirement_actor = actor_preflight(REQUIREMENT_ACTOR, material_actor=False)
    with transaction.atomic():
        material_result = ensure_canonical_material(
            user=material_actor["user"], create=create,
        )
        material = material_result["material"]
        if material is None:
            bundles = [fact_bundle(suffix) for suffix in DESIGN_SUFFIXES]
            return {
                "mode": "INSPECT",
                "material": {key: value for key, value in material_result.items() if key != "material"},
                "facts": [{
                    "object": row["itemNo"], "N": str(row["N"]), "O": str(row["O"]),
                    "Q": str(row["Q"]), "quantity": str(row["quantity"]),
                } for row in bundles],
                "actors": {
                    "material": material_actor["readback"],
                    "requirement": requirement_actor["readback"],
                },
                "businessWriteCount": 0,
            }
        bundles, contracts = build_contracts(material)
        previews = [
            preview_saved_fact_material_requirement(
                user=requirement_actor["user"], contract=contract,
            )
            for contract in contracts
        ]
        if not apply:
            return {
                "mode": "PREVIEW",
                "material": {key: value for key, value in material_result.items() if key != "material"},
                "facts": [{
                    "object": row["itemNo"], "N": str(row["N"]), "O": str(row["O"]),
                    "Q": str(row["Q"]), "quantity": str(row["quantity"]),
                } for row in bundles],
                "contracts": [asdict(contract) for contract in contracts],
                "previews": previews,
                "actors": {
                    "material": material_actor["readback"],
                    "requirement": requirement_actor["readback"],
                },
                "businessWriteCount": material_result["businessWriteCount"],
            }
        applies = [
            apply_saved_fact_material_requirement(
                user=requirement_actor["user"], contract=contract,
            )
            for contract in contracts
        ]
        readbacks = [
            readback_saved_fact_material_requirement(
                user=requirement_actor["user"], contract=contract,
            )
            for contract in contracts
        ]
        preview = OrderEngineeringClosureService.preview_bom(
            user=requirement_actor["user"], calculation_id=CALCULATION_ID,
        )
        pre_generate_receipt = None
        generated = None
        if preview["canGenerate"] and not preview["alreadyGenerated"]:
            completeness = preview["currentVersionMaterialCompleteness"]
            pre_generate_receipt = {
                "targetCoverage": preview["targetScope"],
                "currentVersionMaterialCompleteness": completeness,
                "firstRealBlocker": preview["firstRealBlocker"],
                "previewHash": preview["previewHash"],
                "allApplicableMaterialCategoriesComplete": bool(completeness.get("complete")),
                "noCasingTrimEdgeOrOtherGap": preview["firstRealBlocker"] is None,
            }
            if not (
                allow_generate_if_ready
                and pre_generate_receipt["allApplicableMaterialCategoriesComplete"]
                and pre_generate_receipt["noCasingTrimEdgeOrOtherGap"]
            ):
                fail(
                    "BOM_READY_REQUIRES_CONTROLLED_GENERATION",
                    "BOM Preview已READY，但当前调用未授权执行条件式generate_bom。",
                    receipt=pre_generate_receipt,
                )
            generated = OrderEngineeringClosureService.generate_bom(
                user=requirement_actor["user"],
                calculation_id=CALCULATION_ID,
                preview_hash=preview["previewHash"],
                reason=f"{AUTHORIZATION_REFERENCE}；完整Preview意外READY后的条件式草稿生成",
            )
        return {
            "mode": "APPLY",
            "material": {key: value for key, value in material_result.items() if key != "material"},
            "facts": [{
                "object": row["itemNo"], "N": str(row["N"]), "O": str(row["O"]),
                "Q": str(row["Q"]), "quantity": str(row["quantity"]),
            } for row in bundles],
            "previews": previews,
            "applies": applies,
            "readbacks": readbacks,
            "bomPreview": preview,
            "preGenerateReadinessReceipt": pre_generate_receipt,
            "bomGeneration": generated,
            "bomGenerated": generated is not None,
            "actors": {
                "material": material_actor["readback"],
                "requirement": requirement_actor["readback"],
            },
            "businessWriteCount": material_result["businessWriteCount"] + sum(
                row["businessWriteCount"] for row in applies
            ) + (0 if generated is None else generated.get("businessWriteSideEffectCount", 0)),
        }


def readback() -> dict:
    from pde.engineering_calculation_service import OrderEngineeringClosureService
    from pde.saved_fact_material_requirement_service import readback_saved_fact_material_requirement

    material_actor = actor_preflight(MATERIAL_ACTOR, material_actor=True)
    requirement_actor = actor_preflight(REQUIREMENT_ACTOR, material_actor=False)
    material_result = ensure_canonical_material(user=material_actor["user"], create=False)
    if material_result["material"] is None:
        fail("CANONICAL_MATERIAL_MISSING", "正式松木30×40 Material尚未建立。")
    bundles, contracts = build_contracts(material_result["material"])
    requirement_rows = [
        readback_saved_fact_material_requirement(
            user=requirement_actor["user"], contract=contract,
        )
        for contract in contracts
    ]
    return {
        "mode": "READBACK",
        "material": {key: value for key, value in material_result.items() if key != "material"},
        "facts": [{
            "object": row["itemNo"], "N": str(row["N"]), "O": str(row["O"]),
            "Q": str(row["Q"]), "quantity": str(row["quantity"]),
        } for row in bundles],
        "requirements": requirement_rows,
        "bomPreview": OrderEngineeringClosureService.preview_bom(
            user=requirement_actor["user"], calculation_id=CALCULATION_ID,
        ),
        "actors": {
            "material": material_actor["readback"],
            "requirement": requirement_actor["readback"],
        },
        "businessWriteCount": 0,
    }


def compact_result(result: dict) -> dict:
    requirement_results = result.get("readbacks") or result.get("requirements") or []
    requirements = []
    for row in requirement_results:
        requirement = row["requirement"]
        requirements.append({
            "designItemNo": requirement["trace"]["designItemNo"],
            "requirementId": requirement["requirementId"],
            "mappingId": requirement["mapping"]["id"],
            "mappingRuleCode": requirement["mapping"]["ruleCode"],
            "mappingSpecificationHash": requirement["mapping"]["specificationHash"],
            "sourceDetailId": requirement["sourceDetailId"],
            "sourceFacts": requirement["sourceFacts"],
            "materialId": requirement["materialId"],
            "materialCode": requirement["materialCode"],
            "calculatedQuantity": requirement["calculatedQuantity"],
            "netQuantity": requirement["netQuantity"],
            "grossQuantity": requirement["grossQuantity"],
            "uom": requirement["uom"],
            "scrapRate": requirement["scrapRate"],
            "structureRole": requirement["purpose"],
            "quantityExpression": requirement["quantityExpression"],
            "orderQuantityMultiplierApplied": requirement["orderQuantityMultiplierApplied"],
            "actionRequest": requirement["actionRequest"],
            "audit": requirement["audit"],
            "operator": requirement["trace"]["operator"],
            "oeiId": requirement["trace"]["orderEngineeringInstanceId"],
            "calculationId": requirement["trace"]["calculationId"],
            "legacyAdoptionId": requirement["trace"]["legacyAdoptionId"],
            "provenance": requirement["trace"]["provenance"],
        })
    preview = result.get("bomPreview") or {}
    return {
        "mode": result.get("mode"),
        "material": result.get("material"),
        "facts": result.get("facts"),
        "requirements": requirements,
        "bomPreview": {
            "previewHash": preview.get("previewHash"),
            "rows": preview.get("rows"),
            "rowCount": preview.get("rowCount"),
            "sourceRequirementCount": preview.get("sourceRequirementCount"),
            "targetScope": preview.get("targetScope"),
            "currentVersionMaterialCompleteness": preview.get("currentVersionMaterialCompleteness"),
            "firstRealBlocker": preview.get("firstRealBlocker"),
            "canGenerate": preview.get("canGenerate"),
            "alreadyGenerated": preview.get("alreadyGenerated"),
            "bomId": preview.get("bomId"),
            "bomVersionId": preview.get("bomVersionId"),
            "status": preview.get("status"),
        },
        "preGenerateReadinessReceipt": result.get("preGenerateReadinessReceipt"),
        "bomGeneration": result.get("bomGeneration"),
        "bomGenerated": result.get("bomGenerated", False),
        "actors": result.get("actors"),
        "businessWriteCount": result.get("businessWriteCount", 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--readback", action="store_true")
    parser.add_argument("--allow-isolated", action="store_true")
    parser.add_argument("--allow-generate-if-ready", action="store_true")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    database = args.database.resolve()
    if args.apply and database != FORMAL_DATABASE and not args.allow_isolated:
        raise RuntimeError("FORMAL_DATABASE_TARGET_MISMATCH")
    configure(database)
    try:
        result = (
            readback()
            if args.readback
            else execute(
                create=args.apply,
                apply=args.apply,
                allow_generate_if_ready=args.allow_generate_if_ready,
            )
        )
    except PineCasingWorkflowError as exc:
        print(json.dumps({
            "status": "BLOCKED", "code": exc.code,
            "message": exc.message, "details": exc.details,
        }, ensure_ascii=False, indent=2, default=str))
        return 2
    if args.compact:
        result = compact_result(result)
    print(json.dumps({"status": "PASS", **result}, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
