"""Controlled EDGE_BANDING Material and Requirement continuation workflow.

This task binder applies the explicit 2026-10-06 business decision for
SO202609180003 line 1 through the existing production services.  It creates no
schema and never calls ``generate_bom``.  Default execution is read-only;
``--apply`` is restricted to the formal acceptance database or an explicitly
approved isolated copy.
"""

from __future__ import annotations

import argparse
import json
import os
import site
import sys
import unicodedata
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
AUTHORIZATION_REFERENCE = (
    "USER_INSTRUCTION:SO202609180003:LINE1:EDGE-BANDING:25MM:50MM:2026-10-06"
)

CATEGORY_SPECS = {
    "surface_edge": {
        "code": "MATCAT-SURFACE-EDGE-MATERIAL",
        "name": "贴面及封边材料",
        "parent": None,
    },
    "edge": {
        "code": "MATCAT-EDGE-BANDING",
        "name": "封边材料",
        "parent": "surface_edge",
    },
}

CATEGORY_QUERY_TERMS = (
    "贴面及封边材料", "封边材料", "封边条", "EDGE", "EDGE BANDING",
    "SURFACE", "SURFACE EDGE",
)

MATERIAL_SPECS = {
    25: {
        "name": "封边条25mm",
        "sourceAlias": "封边皮25",
        "specification": "宽25 mm",
        "factCode": "Z",
        "outputName": "edge_banding_25_net_length",
        "sourceOutputName": "封边皮25净长度",
        "fullFormula": "(N*4+O*2)*Q/1000",
        "quantities": {
            3: Decimal("9.980000"), 4: Decimal("9.820000"),
            5: Decimal("9.870000"), 6: Decimal("9.740000"),
            7: Decimal("9.794000"),
        },
    },
    50: {
        "name": "封边条50mm",
        "sourceAlias": "封边皮50",
        "specification": "宽50 mm",
        "factCode": "AA",
        "outputName": "edge_banding_50_net_length",
        "sourceOutputName": "封边皮50净长度",
        "fullFormula": "(N*2+O*2)*Q/1000",
        "quantities": {
            3: Decimal("5.910000"), 4: Decimal("5.750000"),
            5: Decimal("5.800000"), 6: Decimal("5.670000"),
            7: Decimal("5.714000"),
        },
    },
}

DESIGN_SUFFIXES = (3, 4, 5, 6, 7)
STRUCTURE_ROLE = "EDGE_BANDING"
MATERIAL_PURPOSE = "封边"
MATERIAL_UOM_CODE = "m"
APPEARANCE_REFERENCE = "LC-M045"


class EdgeBandingWorkflowError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def fail(code: str, message: str, **details):
    raise EdgeBandingWorkflowError(code, message, details)


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
            "PCE_DATABASE_IDENTITY", "PCE_NON_PRODUCTION_ACCEPTANCE",
            "PCE_RUNTIME_PROFILE", "PCE_RUNTIME_LAUNCHER_VERIFIED",
        ):
            os.environ.pop(key, None)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")
    import django

    django.setup()


def normalize(value) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).split()).casefold()


def decimal_fact_value(fact) -> Decimal:
    raw = fact.value.get("decimal") if isinstance(fact.value, dict) else fact.value
    try:
        return Decimal(str(raw))
    except Exception as exc:  # pragma: no cover - service also validates this
        raise EdgeBandingWorkflowError(
            "SAVED_FACT_DECIMAL_REQUIRED", "工程事实不是合法十进制数值。",
            {"factId": fact.pk, "value": raw},
        ) from exc


def actor_preflight(username: str, *, material_actor: bool) -> dict:
    from system.authorization import AuthorizationService
    from system.models import Company, User

    company = Company.objects.get(code=COMPANY_CODE, is_active=True)
    user = User.objects.select_related(
        "employee_profile__department_ref", "employee_profile__position_ref",
    ).filter(username=username, company_id=company.pk, is_active=True).first()
    if not user or user.is_superuser:
        fail("FORMAL_ACTOR_INVALID", "正式执行账号不存在、已停用或为管理员。", username=username)
    action_codes = (
        ["production.master_data.material.maintain"] if material_actor else [
            "production.engineering.calculation.view",
            "production.engineering.calculation.execute",
            "production.engineering.rule.maintain",
            "production.engineering.rule.release",
            "production.master_data.bom.maintain",
        ]
    )
    decisions = {}
    for action_code in action_codes:
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
                username=username, actionCode=action_code, authorization=decision,
            )
        decisions[action_code] = decision
    employee = user.employee_profile
    return {
        "user": user,
        "readback": {
            "id": user.pk,
            "username": user.username,
            "companyId": user.company_id,
            "isActive": user.is_active,
            "isSuperuser": user.is_superuser,
            "employeeId": employee.pk,
            "employeeNo": employee.employee_no,
            "employeeName": employee.full_name,
            "departmentCode": employee.department_ref.code,
            "positionCode": employee.position_ref.code,
            "authorizations": decisions,
        },
    }


def serialize_category(category) -> dict:
    return {
        "id": category.pk,
        "code": category.code,
        "name": category.name,
        "parentId": category.parent_id,
        "parentCode": category.parent.code if category.parent_id else None,
        "companyId": category.company_id,
        "active": category.is_active,
    }


def serialize_material(material) -> dict:
    return {
        "id": material.pk,
        "code": material.code,
        "name": material.name,
        "category": ({
            "id": material.category_id,
            "code": material.category.code,
            "name": material.category.name,
        } if material.category_id else None),
        "purpose": material.purpose,
        "specification": material.specification,
        "applicationNotes": material.application_notes,
        "baseUom": ({
            "id": material.base_uom_id,
            "code": material.base_uom.code,
            "name": material.base_uom.name,
            "dimension": material.base_uom.dimension,
        } if material.base_uom_id else None),
        "unit": material.unit,
        "unitStatus": material.unit_status,
        "materialType": material.material_type,
        "isPurchased": material.is_purchased,
        "isProduced": material.is_produced,
        "supplyType": material.supply_type,
        "active": material.is_active,
    }


def category_canonical_gate() -> dict:
    from masterdata.models import MaterialCategory
    from system.models import Company

    company = Company.objects.get(code=COMPANY_CODE, is_active=True)
    company_rows = list(
        MaterialCategory.objects.select_related("parent")
        .filter(company_id=company.pk).order_by("pk")
    )
    exact = {}
    conflicts = []
    for key, spec in CATEGORY_SPECS.items():
        code_rows = list(
            MaterialCategory.objects.select_related("parent")
            .filter(code__iexact=spec["code"]).order_by("pk")
        )
        name_rows = [row for row in company_rows if normalize(row.name) == normalize(spec["name"])]
        if len(code_rows) > 1 or len(name_rows) > 1:
            conflicts.append({
                "key": key, "reason": "DUPLICATE_CODE_OR_NAME",
                "codeRows": [serialize_category(row) for row in code_rows],
                "nameRows": [serialize_category(row) for row in name_rows],
            })
            continue
        code_row = code_rows[0] if code_rows else None
        name_row = name_rows[0] if name_rows else None
        if code_row and (
            code_row.company_id != company.pk
            or normalize(code_row.name) != normalize(spec["name"])
        ):
            conflicts.append({
                "key": key, "reason": "CODE_IDENTITY_CONFLICT",
                "row": serialize_category(code_row),
            })
            continue
        if name_row and normalize(name_row.code) != normalize(spec["code"]):
            conflicts.append({
                "key": key, "reason": "NAME_IDENTITY_CONFLICT",
                "row": serialize_category(name_row),
            })
            continue
        row = code_row or name_row
        if row and not row.is_active:
            conflicts.append({
                "key": key, "reason": "INACTIVE_CANONICAL_CONFLICT",
                "row": serialize_category(row),
            })
            continue
        exact[key] = row

    target_codes = {spec["code"] for spec in CATEGORY_SPECS.values()}
    target_names = {normalize(spec["name"]) for spec in CATEGORY_SPECS.values()}
    normalized_terms = [normalize(term) for term in CATEGORY_QUERY_TERMS]
    semantic_candidates = []
    for row in company_rows:
        if row.code in target_codes and normalize(row.name) in target_names:
            continue
        haystacks = (normalize(row.code), normalize(row.name))
        matches = sorted({
            term for term in normalized_terms
            if term and any(term in haystack for haystack in haystacks)
        })
        if matches:
            semantic_candidates.append({
                "row": serialize_category(row), "matchedTerms": matches,
            })
    if conflicts:
        fail(
            "EDGE_CATEGORY_CANONICAL_CONFLICT",
            "封边材料Category Code/Name/active身份存在冲突。",
            conflicts=conflicts,
        )
    if semantic_candidates:
        fail(
            "EDGE_CATEGORY_SEMANTIC_CANDIDATE_REQUIRES_DECISION",
            "发现封边/贴面语义Category候选；禁止自动合并或另建。",
            candidates=semantic_candidates,
        )
    if exact.get("surface_edge") and exact["surface_edge"].parent_id is not None:
        fail(
            "EDGE_CATEGORY_ROOT_PARENT_CONFLICT",
            "贴面及封边材料必须为根Category。",
            row=serialize_category(exact["surface_edge"]),
        )
    if exact.get("edge"):
        expected_parent = exact.get("surface_edge")
        if not expected_parent or exact["edge"].parent_id != expected_parent.pk:
            fail(
                "EDGE_CATEGORY_PARENT_CONFLICT",
                "封边材料Category的Parent与正式裁决不一致。",
                row=serialize_category(exact["edge"]),
            )
    return {
        "company": company,
        "exact": exact,
        "semanticCandidates": semantic_candidates,
        "queryTerms": list(CATEGORY_QUERY_TERMS),
        "canonicalConflictCount": 0,
    }


def write_evidence(*, result: dict, reused: bool) -> dict:
    return {
        "decision": "REUSED" if reused else (
            "IDEMPOTENT_REPLAY" if result.get("idempotentReplay") else "WRITTEN"
        ),
        "businessWriteCount": 0 if reused or result.get("idempotentReplay") else 4,
        "auditId": result.get("auditId"),
        "actionRequestId": result.get("actionRequestId"),
        "externalIdentityId": result.get("sourceIdentityId"),
        "authorization": result.get("authorization"),
        "executionChain": result.get("executionChain"),
    }


def ensure_category(*, key: str, parent, user, apply: bool) -> dict:
    from masterdata.models import MasterDataWriteRequest, MaterialCategory
    from pde.production_foundation_service import ProductionFoundationError, ProductionFoundationService
    from system.models import OrganizationOperatingAuditRecord

    spec = CATEGORY_SPECS[key]
    row = MaterialCategory.objects.select_related("parent").filter(
        company_id=user.company_id, code=spec["code"],
    ).first()
    expected_parent_id = parent.pk if parent else None
    if row:
        if (
            row.name != spec["name"] or not row.is_active
            or row.parent_id != expected_parent_id
        ):
            fail(
                "EDGE_CATEGORY_IDENTITY_CONFLICT",
                "既有Category与正式Code/Name/Parent/active合同冲突。",
                expected={**spec, "parentId": expected_parent_id, "active": True},
                actual=serialize_category(row),
            )
        return {
            "category": row,
            "readback": serialize_category(row),
            "evidence": write_evidence(result={}, reused=True),
        }
    if not apply:
        return {
            "category": None, "readback": None,
            "evidence": {"decision": "CREATE_REQUIRED", "businessWriteCount": 0},
        }
    key_value = f"EDGE-CATEGORY:{COMPANY_CODE}:{spec['code']}:20261006:V1"
    try:
        result = ProductionFoundationService.write(
            "material-categories",
            user=user,
            payload={
                "company_id": user.company_id,
                "code": spec["code"],
                "name": spec["name"],
                "parent_id": expected_parent_id,
                "is_active": True,
                "reason": f"{AUTHORIZATION_REFERENCE}；建立行业通用贴面及封边材料分类",
            },
            idempotency_key=key_value,
            source_identity={
                "sourceSystem": "PCE",
                "sourceType": "USER_CONFIRMED_BUSINESS_DECISION",
                "sourceObjectType": "MATERIAL_CATEGORY",
                "externalId": f"{COMPANY_CODE}:{spec['code']}",
                "auditMetadata": {
                    "authorizationReference": AUTHORIZATION_REFERENCE,
                    "categoryHierarchy": "SURFACE_EDGE_MATERIAL_INDUSTRY_GENERIC_V1",
                },
            },
        )
    except ProductionFoundationError as exc:
        raise EdgeBandingWorkflowError(exc.code, exc.message, exc.details) from exc
    row = MaterialCategory.objects.select_related("parent").get(pk=result["row"]["id"])
    ledger = MasterDataWriteRequest.objects.filter(
        organization_id=user.company_id,
        action_code="production.master_data.create",
        entity_type="material-categories",
        idempotency_key=key_value,
        target_entity_id=str(row.pk),
    ).first()
    audit = OrganizationOperatingAuditRecord.objects.filter(
        pk=result.get("auditId"), target_type="MaterialCategory", target_id=row.pk,
    ).first()
    if not ledger or not audit:
        fail("CATEGORY_EVIDENCE_MISSING", "Category缺少正式审计或幂等账本。")
    result["actionRequestId"] = ledger.pk
    if row.name != spec["name"] or row.parent_id != expected_parent_id or not row.is_active:
        fail("CATEGORY_READBACK_FAILED", "Category保存后Readback不匹配。")
    return {
        "category": row,
        "readback": serialize_category(row),
        "evidence": write_evidence(result=result, reused=False),
    }


def ensure_category_hierarchy(*, user, apply: bool) -> dict:
    gate_before = category_canonical_gate()
    root = ensure_category(key="surface_edge", parent=None, user=user, apply=apply)
    if not root["category"]:
        return {"gateBefore": gate_before, "steps": {"surfaceEdge": root}, "complete": False}
    edge = ensure_category(key="edge", parent=root["category"], user=user, apply=apply)
    steps = {"surfaceEdge": root, "edge": edge}
    if not edge["category"]:
        return {"gateBefore": gate_before, "steps": steps, "complete": False}
    gate_after = category_canonical_gate()
    root_row = gate_after["exact"].get("surface_edge")
    edge_row = gate_after["exact"].get("edge")
    if not root_row or not edge_row or edge_row.parent_id != root_row.pk:
        fail("EDGE_CATEGORY_TREE_READBACK_FAILED", "封边材料Category树最终Readback失败。")
    return {
        "gateBefore": gate_before,
        "gateAfter": gate_after,
        "steps": steps,
        "complete": True,
        "tree": {
            "root": serialize_category(root_row),
            "children": [serialize_category(edge_row)],
        },
        "businessWriteCount": sum(
            step["evidence"]["businessWriteCount"] for step in steps.values()
        ),
    }


def material_canonical_state(*, category, width: int) -> dict:
    from masterdata.material_identity import canonical_identity, matching_materials
    from masterdata.models import Material, UnitOfMeasure
    from system.models import Company

    company = Company.objects.get(code=COMPANY_CODE, is_active=True)
    meter = UnitOfMeasure.objects.filter(
        company_id=company.pk, code=MATERIAL_UOM_CODE, is_active=True,
    ).first()
    if not meter or meter.name != "米" or meter.dimension != "length":
        fail("METER_UOM_IDENTITY_MISMATCH", "正式m/米长度单位不存在或身份不一致。")
    spec = MATERIAL_SPECS[width]
    identity_values = {
        "name": spec["name"],
        "category_id": category.pk,
        "purpose": MATERIAL_PURPOSE,
        "specification": spec["specification"],
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
            "DUPLICATE_ACTIVE_EDGE_MATERIAL",
            "公司范围内存在多条完全相同active封边Material。",
            width=width, materialIds=[row.pk for row in active],
        )
    return {
        "company": company,
        "category": category,
        "meter": meter,
        "identityValues": identity_values,
        "active": active,
        "inactive": inactive,
        "nameCandidates": [serialize_material(row) for row in Material.objects.select_related(
            "category", "base_uom",
        ).filter(company_id=company.pk, name__iexact=spec["name"]).order_by("pk")],
    }


def ensure_material(*, category, width: int, user, apply: bool) -> dict:
    from masterdata.models import MasterDataWriteRequest, Material
    from pde.production_foundation_service import ProductionFoundationError, ProductionFoundationService
    from system.models import OrganizationOperatingAuditRecord

    state = material_canonical_state(category=category, width=width)
    if state["active"]:
        material = Material.objects.select_related("category", "base_uom").get(
            pk=state["active"][0].pk,
        )
        return {
            "material": material,
            "readback": serialize_material(material),
            "canonicalActiveCount": 1,
            "canonicalInactiveCount": len(state["inactive"]),
            "evidence": write_evidence(result={}, reused=True),
        }
    if state["inactive"]:
        fail(
            "INACTIVE_EDGE_MATERIAL_CANDIDATE_REQUIRES_DECISION",
            "存在完全相同inactive封边Material；禁止自动恢复或另建。",
            width=width,
            candidates=[serialize_material(row) for row in state["inactive"]],
        )
    if not apply:
        return {
            "material": None, "readback": None,
            "canonicalActiveCount": 0, "canonicalInactiveCount": 0,
            "evidence": {"decision": "CREATE_REQUIRED", "businessWriteCount": 0},
        }
    spec = MATERIAL_SPECS[width]
    key_value = f"EDGE-BANDING-MATERIAL:{COMPANY_CODE}:WIDTH-{width}-MM:20261006:V1"
    try:
        result = ProductionFoundationService.write(
            "materials",
            user=user,
            payload={
                "company_id": state["company"].pk,
                "name": spec["name"],
                "category_id": category.pk,
                "purpose": MATERIAL_PURPOSE,
                "specification": spec["specification"],
                "application_notes": "",
                "unit": "",
                "unit_status": "confirmed",
                "base_uom_id": state["meter"].pk,
                "purchase_uom_id": None,
                "material_type": "raw",
                "is_purchased": False,
                "is_produced": False,
                "is_active": True,
                "reason": (
                    f"{AUTHORIZATION_REFERENCE}；建立名义宽度{width} mm封边条；"
                    "具体材质和供应属性保持未猜测"
                ),
            },
            idempotency_key=key_value,
            source_identity={
                "sourceSystem": "PCE",
                "sourceType": "USER_CONFIRMED_BUSINESS_DECISION",
                "sourceObjectType": "MATERIAL",
                "externalId": f"{COMPANY_CODE}:EDGE-BANDING:WIDTH-{width}-MM",
                "auditMetadata": {
                    "authorizationReference": AUTHORIZATION_REFERENCE,
                    "sourceAlias": spec["sourceAlias"],
                    "nominalWidth": width,
                    "nominalWidthUom": "mm",
                    "specificComposition": "NOT_PROVEN",
                    "supplyStatus": "PENDING_CONFIRMATION",
                },
            },
        )
    except ProductionFoundationError as exc:
        raise EdgeBandingWorkflowError(exc.code, exc.message, exc.details) from exc
    material = Material.objects.select_related("category", "base_uom").get(
        pk=result["row"]["id"],
    )
    final_state = material_canonical_state(category=category, width=width)
    if len(final_state["active"]) != 1 or final_state["active"][0].pk != material.pk:
        fail("EDGE_MATERIAL_READBACK_FAILED", "封边Material保存后Canonical Readback不唯一。")
    ledger = MasterDataWriteRequest.objects.filter(
        organization_id=user.company_id,
        action_code="production.master_data.create",
        entity_type="materials",
        idempotency_key=key_value,
        target_entity_id=str(material.pk),
    ).first()
    audit = OrganizationOperatingAuditRecord.objects.filter(
        pk=result.get("auditId"), target_type="Material", target_id=material.pk,
    ).first()
    if not ledger or not audit:
        fail("EDGE_MATERIAL_EVIDENCE_MISSING", "封边Material缺少正式审计或幂等账本。")
    result["actionRequestId"] = ledger.pk
    return {
        "material": material,
        "readback": serialize_material(material),
        "canonicalActiveCount": 1,
        "canonicalInactiveCount": len(final_state["inactive"]),
        "evidence": write_evidence(result=result, reused=False),
    }


def target_candidate_readback() -> dict:
    from masterdata.models import Material

    rows = Material.objects.select_related("category", "base_uom").filter(
        company_id=1,
    ).order_by("pk")
    return {
        str(width): [
            serialize_material(row) for row in rows
            if normalize(row.name) == normalize(spec["name"])
        ]
        for width, spec in MATERIAL_SPECS.items()
    }


def fact_bundle(suffix: int) -> dict:
    from pde.models import EngineeringCalculationRecord, EngineeringDerivedFact, ProductDesignItem

    item_no = f"{ORDER_NO}-DES-01-SRC-{suffix:04d}"
    item = ProductDesignItem.objects.select_related(
        "sales_order_item__sales_order", "source_record",
    ).filter(item_no=item_no).first()
    if not item:
        fail("DESIGN_ITEM_NOT_FOUND", "EDGE_BANDING目标设计对象不存在。", designItemNo=item_no)
    if item.sales_order_item.sales_order.order_no != ORDER_NO or item.sales_order_item.line_no != 1:
        fail("DESIGN_ITEM_ORDER_SCOPE_MISMATCH", "目标设计对象不属于授权订单行1。")
    facts = {}
    for code in ("N", "O", "Q", "Z", "AA"):
        rows = list(EngineeringDerivedFact.objects.select_related(
            "uom", "source_detail", "calculation__engineering_instance", "rule",
        ).filter(
            calculation_id=CALCULATION_ID,
            fact_code=f"{item_no}:{code}",
            canonical_field=code,
            status="active",
        ))
        if len(rows) != 1:
            fail(
                "SAVED_FACT_INPUT_NOT_UNIQUE",
                "N/O/Q/Z/AA必须分别精确对应一个当前已保存事实。",
                designItemNo=item_no, factCode=code, matchCount=len(rows),
            )
        facts[code] = rows[0]
    values = {code: decimal_fact_value(fact) for code, fact in facts.items()}
    if facts["N"].uom.code != "mm" or facts["O"].uom.code != "mm" or facts["Q"].uom_id:
        fail("EDGE_FACT_UOM_MISMATCH", "N/O必须为mm且Q必须为无量纲计数。")
    if facts["Z"].uom.code != "m" or facts["AA"].uom.code != "m":
        fail("EDGE_OUTPUT_UOM_MISMATCH", "Z/AA必须为m。")
    q = values["Q"]
    if q <= 0 or q != q.to_integral_value():
        fail("EDGE_QUANTITY_FACT_INVALID", "Q必须是大于0的整数。")
    calculated = {
        25: ((values["N"] * 4 + values["O"] * 2) * q / 1000).quantize(Decimal("0.000001")),
        50: ((values["N"] * 2 + values["O"] * 2) * q / 1000).quantize(Decimal("0.000001")),
    }
    for width, code in ((25, "Z"), (50, "AA")):
        expected = MATERIAL_SPECS[width]["quantities"][suffix]
        actual = values[code].quantize(Decimal("0.000001"))
        if actual != expected or calculated[width] != expected:
            fail(
                "CURRENT_EDGE_FACT_CONFLICT",
                "当前Z/AA或N/O/Q公式结果与正式裁决数量冲突。",
                designItemNo=item_no, width=width,
                expected=str(expected), saved=str(actual), calculated=str(calculated[width]),
            )
        if not facts[code].source_detail_id or not facts[code].source_path:
            fail("EDGE_FACT_LINEAGE_MISSING", "Z/AA缺少Detail或Source Path。")
    calculation = EngineeringCalculationRecord.objects.get(pk=CALCULATION_ID)
    snapshot = next((
        row for row in (calculation.trace or {}).get("objectInputSnapshot", [])
        if row.get("designItemId") == item.pk
    ), None)
    finish = str(((snapshot or {}).get("input") or {}).get("finishOrColor") or "")
    appearance_reference = APPEARANCE_REFERENCE if APPEARANCE_REFERENCE in finish else None
    return {
        "suffix": suffix,
        "item": item,
        "itemNo": item_no,
        "facts": facts,
        "values": values,
        "appearanceReference": appearance_reference,
        "appearanceSource": finish if appearance_reference else None,
    }


def serialize_fact_bundle(bundle: dict) -> dict:
    return {
        "designItemId": bundle["item"].pk,
        "designItemNo": bundle["itemNo"],
        "appearanceReference": bundle["appearanceReference"],
        "appearanceSource": bundle["appearanceSource"],
        "facts": [{
            "code": code,
            "factId": bundle["facts"][code].pk,
            "detailId": bundle["facts"][code].source_detail_id,
            "value": str(bundle["values"][code]),
            "uom": bundle["facts"][code].uom.code if bundle["facts"][code].uom_id else None,
            "sourcePath": bundle["facts"][code].source_path,
        } for code in ("N", "O", "Q", "Z", "AA")],
    }


def requirement_supply_type(material) -> str:
    if material.supply_type == "purchase":
        return "BUY"
    if material.supply_type == "production":
        return "MAKE"
    return "MAKE_OR_BUY"


def build_contract(*, material, category, width: int, bundle):
    from pde.saved_fact_material_requirement_service import (
        SavedFactInputBinding,
        SavedFactMaterialRequirementContract,
    )

    spec = MATERIAL_SPECS[width]
    suffix = bundle["suffix"]
    fact_code = spec["factCode"]
    primary = bundle["facts"][fact_code]
    value = bundle["values"][fact_code].quantize(Decimal("0.000001"))
    provenance_facts = [{
        "code": code,
        "factId": bundle["facts"][code].pk,
        "detailId": bundle["facts"][code].source_detail_id,
        "value": str(bundle["values"][code]),
        "uom": bundle["facts"][code].uom.code if bundle["facts"][code].uom_id else None,
        "sourcePath": bundle["facts"][code].source_path,
    } for code in ("N", "O", "Q", fact_code)]
    order_specification = {
        "businessPurpose": "FORMAL_SALE",
        "businessMeaning": f"当前设计对象{width}mm封边条工程净长度需求",
        "materialPurpose": MATERIAL_PURPOSE,
        "materialCategoryId": category.pk,
        "materialCategoryCode": category.code,
        "materialCategoryName": category.name,
        "materialSpecification": spec["specification"],
        "nominalWidth": width,
        "nominalWidthUom": "mm",
        "structureRole": STRUCTURE_ROLE,
        "formulaCode": fact_code,
        "formula": fact_code,
        "sourceFormula": spec["fullFormula"],
        "quantityBasis": "NET_LENGTH",
        "lossPolicy": "ZERO_LOSS_ENGINEERING_NET_REQUIREMENT",
        "lossRate": 0,
        "allowanceApplied": False,
        "qAlreadyApplied": True,
        "salesOrderItemQuantityMultiplierApplied": False,
        "sourceAlias": spec["sourceAlias"],
        "specificComposition": "NOT_PROVEN",
        "supplyStatus": material.supply_type.upper(),
    }
    if bundle["appearanceReference"]:
        order_specification["appearanceReference"] = bundle["appearanceReference"]
        order_specification["appearanceReferenceMeaning"] = "颜色/样板/外观协调参考"
    return SavedFactMaterialRequirementContract(
        mapping_no=f"MRC-EDGE-{width}-{suffix:04d}",
        mapping_rule_code=f"MRM.{ORDER_NO}.EDGE-{width}-{suffix:04d}",
        mapping_version="V1",
        rule_name=f"EDGE_BANDING_{width}_NET_LENGTH / DES-01-SRC-{suffix:04d}",
        order_no=ORDER_NO,
        calculation_id=CALCULATION_ID,
        design_item_no=bundle["itemNo"],
        material_id=material.pk,
        material_code=material.code,
        output_uom_code=MATERIAL_UOM_CODE,
        output_name=spec["outputName"],
        expression=fact_code,
        inputs=(SavedFactInputBinding(fact_code, fact_code, "m", "length"),),
        primary_source_fact_code=fact_code,
        expected_quantity=value,
        authorization_reference=f"{AUTHORIZATION_REFERENCE}:WIDTH-{width}:DES01-{suffix:04d}",
        idempotency_key=f"{ORDER_NO}:LINE1:EDGE-BANDING:{width}:{suffix:04d}:V1",
        purpose_code=STRUCTURE_ROLE,
        quantity_basis="ORDER_TOTAL",
        item_role="material",
        requirement_type="manufacturing",
        supply_type=requirement_supply_type(material),
        scrap_rate=Decimal("0"),
        order_specification=order_specification,
        provenance={
            "decisionDate": "2026-10-06",
            "decisionSource": "USER_EXPLICIT_BUSINESS_DECISION",
            "sourceAlias": spec["sourceAlias"],
            "sourceOutputName": spec["sourceOutputName"],
            "materialId": material.pk,
            "materialCode": material.code,
            "materialCategory": {
                "id": category.pk, "code": category.code, "name": category.name,
            },
            "materialSpecification": spec["specification"],
            "materialPurpose": MATERIAL_PURPOSE,
            "nominalWidth": width,
            "nominalWidthUom": "mm",
            "specificComposition": "NOT_PROVEN",
            "formulaCode": fact_code,
            "formula": fact_code,
            "sourceFormula": spec["fullFormula"],
            "sourceFacts": provenance_facts,
            "primarySourceFactId": primary.pk,
            "primarySourceDetailId": primary.source_detail_id,
            "primarySourcePath": primary.source_path,
            "quantity": str(value),
            "uom": "m",
            "quantityBasis": "NET_LENGTH",
            "lossRate": 0,
            "allowanceApplied": False,
            "qAlreadyApplied": True,
            "salesOrderItemQuantityMultiplierApplied": False,
            "appearanceReference": bundle["appearanceReference"],
            "appearanceSource": bundle["appearanceSource"],
            "designMaterialReferencePolicy": (
                "EDGE_REQUIREMENT_DOES_NOT_REPLACE_DESIGN_PRIMARY_MATERIAL"
            ),
        },
        output_scale=6,
        output_unit_dimension="length",
        require_design_material_reference=False,
    )


def build_contracts(*, materials: dict, category) -> tuple[list, list]:
    bundles = [fact_bundle(suffix) for suffix in DESIGN_SUFFIXES]
    contracts = []
    for bundle in bundles:
        for width in (25, 50):
            contracts.append(build_contract(
                material=materials[width], category=category,
                width=width, bundle=bundle,
            ))
    return bundles, contracts


def execute(*, apply: bool) -> dict:
    from django.db import transaction
    from pde.engineering_calculation_service import OrderEngineeringClosureService
    from pde.saved_fact_material_requirement_service import (
        SavedFactMaterialRequirementError,
        apply_saved_fact_material_requirement,
        preview_saved_fact_material_requirement,
        readback_saved_fact_material_requirement,
    )

    material_actor = actor_preflight(MATERIAL_ACTOR, material_actor=True)
    requirement_actor = actor_preflight(REQUIREMENT_ACTOR, material_actor=False)
    try:
        with transaction.atomic():
            hierarchy = ensure_category_hierarchy(
                user=material_actor["user"], apply=apply,
            )
            if not hierarchy["complete"]:
                return {
                    "mode": "INSPECT",
                    "categoryHierarchy": hierarchy,
                    "materialNameCandidates": target_candidate_readback(),
                    "actors": {
                        "categoryAndMaterial": material_actor["readback"],
                        "requirement": requirement_actor["readback"],
                    },
                    "businessWriteCount": 0,
                    "bomGenerated": False,
                }
            category = hierarchy["steps"]["edge"]["category"]
            material_results = {
                width: ensure_material(
                    category=category, width=width,
                    user=material_actor["user"], apply=apply,
                )
                for width in (25, 50)
            }
            if any(not row["material"] for row in material_results.values()):
                return {
                    "mode": "INSPECT",
                    "categoryHierarchy": hierarchy,
                    "materials": {
                        str(width): {k: v for k, v in row.items() if k != "material"}
                        for width, row in material_results.items()
                    },
                    "actors": {
                        "categoryAndMaterial": material_actor["readback"],
                        "requirement": requirement_actor["readback"],
                    },
                    "businessWriteCount": hierarchy.get("businessWriteCount", 0),
                    "bomGenerated": False,
                }
            materials = {width: row["material"] for width, row in material_results.items()}
            bundles, contracts = build_contracts(materials=materials, category=category)
            previews = [
                preview_saved_fact_material_requirement(
                    user=requirement_actor["user"], contract=contract,
                )
                for contract in contracts
            ]
            if not apply:
                return {
                    "mode": "PREVIEW",
                    "categoryHierarchy": hierarchy,
                    "materials": {
                        str(width): {k: v for k, v in row.items() if k != "material"}
                        for width, row in material_results.items()
                    },
                    "facts": [serialize_fact_bundle(bundle) for bundle in bundles],
                    "contracts": [asdict(contract) for contract in contracts],
                    "previews": previews,
                    "actors": {
                        "categoryAndMaterial": material_actor["readback"],
                        "requirement": requirement_actor["readback"],
                    },
                    "businessWriteCount": 0,
                    "bomGenerated": False,
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
            bom_preview = OrderEngineeringClosureService.preview_bom(
                user=requirement_actor["user"], calculation_id=CALCULATION_ID,
            )
            return {
                "mode": "APPLY",
                "categoryHierarchy": hierarchy,
                "materials": {
                    str(width): {k: v for k, v in row.items() if k != "material"}
                    for width, row in material_results.items()
                },
                "facts": [serialize_fact_bundle(bundle) for bundle in bundles],
                "previews": previews,
                "applies": applies,
                "readbacks": readbacks,
                "bomPreview": bom_preview,
                "bomGeneration": None,
                "bomGenerated": False,
                "actors": {
                    "categoryAndMaterial": material_actor["readback"],
                    "requirement": requirement_actor["readback"],
                },
                "businessWriteCount": (
                    hierarchy.get("businessWriteCount", 0)
                    + sum(row["evidence"]["businessWriteCount"] for row in material_results.values())
                    + sum(row["businessWriteCount"] for row in applies)
                ),
            }
    except SavedFactMaterialRequirementError as exc:
        raise EdgeBandingWorkflowError(exc.code, exc.message, exc.details) from exc


def readback() -> dict:
    from pde.engineering_calculation_service import OrderEngineeringClosureService
    from pde.saved_fact_material_requirement_service import readback_saved_fact_material_requirement

    material_actor = actor_preflight(MATERIAL_ACTOR, material_actor=True)
    requirement_actor = actor_preflight(REQUIREMENT_ACTOR, material_actor=False)
    hierarchy = ensure_category_hierarchy(user=material_actor["user"], apply=False)
    if not hierarchy["complete"]:
        fail("EDGE_CATEGORY_MISSING", "封边材料Category尚未完整建立。")
    category = hierarchy["steps"]["edge"]["category"]
    material_results = {
        width: ensure_material(
            category=category, width=width, user=material_actor["user"], apply=False,
        )
        for width in (25, 50)
    }
    if any(not row["material"] for row in material_results.values()):
        fail("EDGE_MATERIAL_MISSING", "25mm或50mm封边Material尚未建立。")
    materials = {width: row["material"] for width, row in material_results.items()}
    bundles, contracts = build_contracts(materials=materials, category=category)
    requirements = [
        readback_saved_fact_material_requirement(
            user=requirement_actor["user"], contract=contract,
        )
        for contract in contracts
    ]
    return {
        "mode": "READBACK",
        "categoryHierarchy": hierarchy,
        "materials": {
            str(width): {k: v for k, v in row.items() if k != "material"}
            for width, row in material_results.items()
        },
        "facts": [serialize_fact_bundle(bundle) for bundle in bundles],
        "requirements": requirements,
        "bomPreview": OrderEngineeringClosureService.preview_bom(
            user=requirement_actor["user"], calculation_id=CALCULATION_ID,
        ),
        "actors": {
            "categoryAndMaterial": material_actor["readback"],
            "requirement": requirement_actor["readback"],
        },
        "businessWriteCount": 0,
        "bomGenerated": False,
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
            "materialName": requirement["materialName"],
            "calculatedQuantity": requirement["calculatedQuantity"],
            "netQuantity": requirement["netQuantity"],
            "grossQuantity": requirement["grossQuantity"],
            "uom": requirement["uom"],
            "scrapRate": requirement["scrapRate"],
            "scrapRateStatus": requirement["scrapRateStatus"],
            "purpose": requirement["purpose"],
            "quantityExpression": requirement["quantityExpression"],
            "trace": requirement["trace"],
            "actionRequest": requirement["actionRequest"],
            "audit": requirement["audit"],
        })
    return {
        "mode": result.get("mode"),
        "categoryHierarchy": result.get("categoryHierarchy"),
        "materialNameCandidates": result.get("materialNameCandidates"),
        "materials": result.get("materials"),
        "facts": result.get("facts"),
        "requirements": requirements,
        "bomPreview": result.get("bomPreview"),
        "bomGenerated": result.get("bomGenerated", False),
        "businessWriteCount": result.get("businessWriteCount", 0),
        "actors": result.get("actors"),
    }


def summary_result(result: dict) -> dict:
    compact = compact_result(result)
    hierarchy = compact.get("categoryHierarchy") or {}
    material_summaries = {}
    for width, row in (compact.get("materials") or {}).items():
        evidence = row.get("evidence") or {}
        material_summaries[width] = {
            "readback": row.get("readback"),
            "canonicalActiveCount": row.get("canonicalActiveCount"),
            "canonicalInactiveCount": row.get("canonicalInactiveCount"),
            "evidence": {
                key: evidence.get(key) for key in (
                    "decision", "businessWriteCount", "auditId",
                    "actionRequestId", "externalIdentityId",
                )
            },
        }
    requirements = [{
        key: row.get(key) for key in (
            "designItemNo", "requirementId", "mappingId", "mappingRuleCode",
            "mappingSpecificationHash", "sourceDetailId", "materialId",
            "materialCode", "materialName", "calculatedQuantity", "netQuantity",
            "grossQuantity", "uom", "scrapRate", "scrapRateStatus", "purpose",
            "quantityExpression", "actionRequest", "audit",
        )
    } for row in compact.get("requirements") or []]
    actors = {}
    for key, row in (compact.get("actors") or {}).items():
        actors[key] = {
            field: row.get(field) for field in (
                "id", "username", "companyId", "isActive", "isSuperuser",
                "employeeId", "employeeNo", "employeeName",
                "departmentCode", "positionCode",
            )
        }
        actors[key]["authorizationDecisionCodes"] = {
            action: decision.get("decisionCode")
            for action, decision in (row.get("authorizations") or {}).items()
        }
    facts = []
    for bundle in compact.get("facts") or []:
        facts.append({
            "designItemId": bundle.get("designItemId"),
            "designItemNo": bundle.get("designItemNo"),
            "appearanceReference": bundle.get("appearanceReference"),
            "facts": bundle.get("facts"),
        })
    return {
        "mode": compact.get("mode"),
        "categoryCanonicalGate": {
            "beforeConflictCount": (hierarchy.get("gateBefore") or {}).get("canonicalConflictCount"),
            "beforeSemanticCandidates": (hierarchy.get("gateBefore") or {}).get("semanticCandidates"),
            "complete": hierarchy.get("complete"),
            "tree": hierarchy.get("tree"),
            "steps": {
                key: {
                    "readback": row.get("readback"),
                    "evidence": {
                        field: (row.get("evidence") or {}).get(field)
                        for field in (
                            "decision", "businessWriteCount", "auditId",
                            "actionRequestId", "externalIdentityId",
                        )
                    },
                }
                for key, row in (hierarchy.get("steps") or {}).items()
            },
        },
        "materialNameCandidates": compact.get("materialNameCandidates"),
        "materials": material_summaries,
        "facts": facts,
        "requirements": requirements,
        "bomPreview": compact.get("bomPreview"),
        "bomGenerated": compact.get("bomGenerated"),
        "businessWriteCount": compact.get("businessWriteCount"),
        "actors": actors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--readback", action="store_true")
    parser.add_argument("--allow-isolated", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    database = args.database.resolve()
    if args.apply and database != FORMAL_DATABASE and not args.allow_isolated:
        raise RuntimeError("ISOLATED_APPLY_REQUIRES_EXPLICIT_FLAG")
    if args.apply and args.readback:
        raise RuntimeError("APPLY_AND_READBACK_ARE_MUTUALLY_EXCLUSIVE")
    configure(database)
    try:
        result = readback() if args.readback else execute(apply=args.apply)
        payload = summary_result(result) if args.summary else compact_result(result)
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 0
    except EdgeBandingWorkflowError as exc:
        print(json.dumps({
            "status": "BLOCKED", "code": exc.code,
            "message": exc.message, "details": exc.details,
        }, ensure_ascii=False, indent=2, default=str))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
