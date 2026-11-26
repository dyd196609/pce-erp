"""Controlled wood-category and CASING_TRIM continuation workflow.

The reusable business services remain category-, order-, and material-neutral.
This command only binds the explicit 2026-10-06 user decision to those
services.  It can inspect or read back any database, but ``--apply`` is
restricted to the known formal acceptance database unless an isolated copy is
explicitly selected with ``--allow-isolated``.  It never generates a BOM.
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
MATERIAL_ID = 249
MATERIAL_CODE = "MAT202608000167"
MATERIAL_NAME = "门套线6*1.8"
MATERIAL_SPECIFICATION = "60×18 mm"
MATERIAL_PURPOSE = "门套线"
MATERIAL_UOM_CODE = "支"
STRUCTURE_ROLE = "CASING_TRIM"
FORMULA_CODE = "CASING_TRIM_PIECE_COUNT"
FORMULA_EXPRESSION = "AW+AY"
DESIGN_SUFFIXES = (3, 4, 5, 6, 7)
REFERENCE_FACTS = {
    suffix: (Decimal("4"), Decimal("1"), Decimal("5"))
    for suffix in DESIGN_SUFFIXES
}

CATEGORY_SPECS = {
    "wood": {
        "code": "MATCAT-WOOD-MATERIAL",
        "name": "木质材料",
        "parent": None,
    },
    "solid": {
        "code": "MATCAT-SOLID-WOOD",
        "name": "实木",
        "parent": "wood",
        "required_id": 11,
    },
    "wood_based": {
        "code": "MATCAT-WOOD-BASED-PANEL",
        "name": "人造板（木基板材）",
        "parent": "wood",
    },
    "multilayer": {
        "code": "MATCAT-MULTILAYER-BOARD",
        "name": "多层板",
        "parent": "wood_based",
    },
}

SEMANTIC_CATEGORY_TERMS = (
    "木材", "木质材料", "木基材料", "人造板", "木基板材", "工程木",
    "复合木板", "多层板", "胶合板", "plywood", "wood-based panel", "multilayer",
)

AUTHORIZATION_REFERENCE = (
    "USER_INSTRUCTION:SO202609180003:LINE1:WOOD-MATERIAL-HIERARCHY:"
    "MATERIAL-249:CASING-TRIM:2026-10-06"
)


class WoodCasingTrimWorkflowError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def fail(code: str, message: str, **details):
    raise WoodCasingTrimWorkflowError(code, message, details)


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
        raise WoodCasingTrimWorkflowError(
            "SAVED_FACT_DECIMAL_REQUIRED",
            "AW/AY事实不是合法十进制数值。",
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
        fail(
            "FORMAL_ACTOR_INVALID",
            "正式执行账号不存在、已停用或为超级管理员。",
            username=username,
        )
    employee = getattr(user, "employee_profile", None)
    department = getattr(employee, "department_ref", None) if employee else None
    position = getattr(employee, "position_ref", None) if employee else None
    if (
        not employee or employee.status != "active"
        or not department or not department.is_active
        or not position or not position.is_active
    ):
        fail(
            "FORMAL_EMPLOYMENT_CONTEXT_REQUIRED",
            "正式执行账号必须关联在职员工、有效部门和有效岗位。",
            username=username,
        )
    action_codes = (
        ("production.master_data.material.maintain",)
        if material_actor
        else (
            "production.engineering.calculation.view",
            "production.engineering.calculation.execute",
            "production.engineering.rule.maintain",
            "production.engineering.rule.release",
            "production.master_data.bom.maintain",
        )
    )
    decisions = {}
    for action_code in action_codes:
        decision = AuthorizationService.decide(
            user=user,
            action_code=action_code,
            organization_id=user.company_id,
            business_object={
                "organizationId": user.company_id,
                "calculationId": CALCULATION_ID,
            },
        )
        if not decision.get("allowed"):
            fail(
                decision.get("decisionCode", "PERMISSION_DENIED"),
                decision.get("reason", "正式执行账号无权执行本轮动作。"),
                username=username,
                actionCode=action_code,
                authorization=decision,
            )
        decisions[action_code] = decision
    role_rows = list(
        user.role_scope_assignments.filter(active=True)
        .select_related("role", "organization", "department")
        .order_by("role__code", "pk")
    )
    return {
        "user": user,
        "readback": {
            "user": {
                "id": user.pk,
                "username": user.username,
                "realName": user.real_name,
                "companyId": user.company_id,
                "active": user.is_active,
                "superuser": user.is_superuser,
            },
            "employee": {
                "id": employee.pk,
                "employeeNo": employee.employee_no,
                "name": employee.full_name,
                "status": employee.status,
            },
            "company": {"id": company.pk, "code": company.code, "name": company.name},
            "department": {
                "id": department.pk, "code": department.code, "name": department.name,
                "active": department.is_active,
            },
            "position": {
                "id": position.pk, "code": position.code, "name": position.name,
                "active": position.is_active,
            },
            "roles": [{
                "assignmentId": row.pk,
                "roleId": row.role_id,
                "roleCode": row.role.code,
                "roleName": row.role.name,
                "scope": row.scope_code,
                "organizationId": row.organization_id,
                "departmentId": row.department_id,
            } for row in role_rows],
            "authorization": decisions,
        },
    }


def serialize_category(category) -> dict:
    return {
        "id": category.pk,
        "code": category.code,
        "name": category.name,
        "parentId": category.parent_id,
        "parentCode": category.parent.code if category.parent_id else None,
        "parentName": category.parent.name if category.parent_id else None,
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
    from masterdata.material_identity import normalize_identity_text
    from masterdata.models import MaterialCategory
    from system.models import Company

    company = Company.objects.get(code=COMPANY_CODE, is_active=True)
    rows = list(
        MaterialCategory.objects.select_related("parent")
        .filter(company_id=company.pk).order_by("pk")
    )
    expected_by_code = {spec["code"]: spec for spec in CATEGORY_SPECS.values()}
    exact = {}
    conflicts = []
    for key, spec in CATEGORY_SPECS.items():
        code_rows = list(MaterialCategory.objects.select_related("parent").filter(code=spec["code"]))
        name_rows = [
            row for row in rows
            if normalize_identity_text(row.name) == normalize_identity_text(spec["name"])
        ]
        if len(code_rows) > 1 or len(name_rows) > 1:
            conflicts.append({
                "key": key,
                "reason": "DUPLICATE_CODE_OR_NAME",
                "codeRows": [serialize_category(row) for row in code_rows],
                "nameRows": [serialize_category(row) for row in name_rows],
            })
            continue
        code_row = code_rows[0] if code_rows else None
        name_row = name_rows[0] if name_rows else None
        if code_row and (
            code_row.company_id != company.pk
            or normalize_identity_text(code_row.name) != normalize_identity_text(spec["name"])
        ):
            conflicts.append({
                "key": key, "reason": "CODE_IDENTITY_CONFLICT",
                "row": serialize_category(code_row),
            })
            continue
        if name_row and name_row.code != spec["code"]:
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
        if row and spec.get("required_id") and row.pk != spec["required_id"]:
            conflicts.append({
                "key": key, "reason": "REQUIRED_ID_CONFLICT",
                "requiredId": spec["required_id"], "row": serialize_category(row),
            })
            continue
        exact[key] = row
    semantic_candidates = []
    normalized_terms = [normalize_identity_text(term) for term in SEMANTIC_CATEGORY_TERMS]
    for row in rows:
        normalized_name = normalize_identity_text(row.name)
        normalized_code = normalize_identity_text(row.code)
        if row.code in expected_by_code and (
            normalized_name == normalize_identity_text(expected_by_code[row.code]["name"])
        ):
            continue
        matched = [
            term for term in normalized_terms
            if term and (term in normalized_name or term in normalized_code)
        ]
        if matched:
            semantic_candidates.append({
                "row": serialize_category(row), "matchedTerms": matched,
            })
    if conflicts:
        fail(
            "MATERIAL_CATEGORY_CANONICAL_CONFLICT",
            "木质材料Category Code/Name/active身份存在冲突。",
            conflicts=conflicts,
        )
    if semantic_candidates:
        fail(
            "MATERIAL_CATEGORY_SEMANTIC_CANDIDATE_REQUIRES_DECISION",
            "发现语义近似Category候选；禁止自动合并或另建。",
            candidates=semantic_candidates,
        )
    if exact.get("solid") is None:
        fail(
            "SOLID_WOOD_CATEGORY_MISSING",
            "既有MATCAT-SOLID-WOOD / 实木Category不存在。",
        )
    return {
        "company": company,
        "rows": rows,
        "exact": exact,
        "semanticCandidates": semantic_candidates,
        "canonicalConflictCount": 0,
    }


def category_write_evidence(*, result: dict, reused: bool) -> dict:
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
    from masterdata.models import MaterialCategory, MasterDataWriteRequest
    from pde.production_foundation_service import ProductionFoundationError, ProductionFoundationService
    from system.models import OrganizationOperatingAuditRecord

    spec = CATEGORY_SPECS[key]
    row = MaterialCategory.objects.select_related("parent").filter(code=spec["code"]).first()
    expected_parent_id = parent.pk if parent else None
    if row:
        if (
            row.name != spec["name"] or not row.is_active
            or row.parent_id != expected_parent_id
        ):
            fail(
                "MATERIAL_CATEGORY_PARENT_OR_IDENTITY_CONFLICT",
                "既有Category与本轮正式身份或Parent冲突。",
                expected={
                    "code": spec["code"], "name": spec["name"],
                    "parentId": expected_parent_id, "active": True,
                },
                actual=serialize_category(row),
            )
        return {
            "category": row,
            "readback": serialize_category(row),
            "evidence": category_write_evidence(result={}, reused=True),
        }
    if not apply:
        return {
            "category": None,
            "readback": None,
            "evidence": {"decision": "CREATE_REQUIRED", "businessWriteCount": 0},
        }
    idempotency_key = f"WOOD-CATEGORY-HIERARCHY:{COMPANY_CODE}:{spec['code']}:20261006:V1"
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
                "reason": f"{AUTHORIZATION_REFERENCE}；建立行业通用木质材料分类骨架",
            },
            idempotency_key=idempotency_key,
            source_identity={
                "sourceSystem": "PCE",
                "sourceType": "USER_CONFIRMED_BUSINESS_DECISION",
                "sourceObjectType": "MATERIAL_CATEGORY",
                "externalId": f"{COMPANY_CODE}:{spec['code']}",
                "auditMetadata": {
                    "authorizationReference": AUTHORIZATION_REFERENCE,
                    "categoryHierarchy": "WOOD_MATERIAL_INDUSTRY_GENERIC_V1",
                },
            },
        )
    except ProductionFoundationError as exc:
        raise WoodCasingTrimWorkflowError(exc.code, exc.message, exc.details) from exc
    row = MaterialCategory.objects.select_related("parent").get(pk=result["row"]["id"])
    if row.parent_id != expected_parent_id or row.name != spec["name"] or not row.is_active:
        fail("CATEGORY_READBACK_FAILED", "Category保存后Readback不匹配。", row=serialize_category(row))
    ledger = MasterDataWriteRequest.objects.filter(
        organization_id=user.company_id,
        action_code="production.master_data.create",
        entity_type="material-categories",
        idempotency_key=idempotency_key,
        target_entity_id=str(row.pk),
    ).first()
    audit = OrganizationOperatingAuditRecord.objects.filter(
        pk=result.get("auditId"), target_type="MaterialCategory", target_id=row.pk,
    ).first()
    if not ledger or not audit:
        fail("CATEGORY_AUDIT_IDEMPOTENCY_EVIDENCE_MISSING", "Category缺少审计或幂等账本。")
    result["actionRequestId"] = ledger.pk
    return {
        "category": row,
        "readback": serialize_category(row),
        "evidence": category_write_evidence(result=result, reused=False),
    }


def ensure_solid_parent(*, wood, user, apply: bool) -> dict:
    from masterdata.models import MaterialCategory, MasterDataWriteRequest
    from pde.production_foundation_service import ProductionFoundationError, ProductionFoundationService
    from system.models import OrganizationOperatingAuditRecord

    row = MaterialCategory.objects.select_related("parent").get(
        pk=CATEGORY_SPECS["solid"]["required_id"],
        code=CATEGORY_SPECS["solid"]["code"],
        name=CATEGORY_SPECS["solid"]["name"],
        company_id=user.company_id,
        is_active=True,
    )
    if row.parent_id == wood.pk:
        return {
            "category": row,
            "readback": serialize_category(row),
            "evidence": category_write_evidence(result={}, reused=True),
        }
    if row.parent_id is not None:
        fail(
            "SOLID_WOOD_PARENT_CONFLICT",
            "既有实木Category已绑定其他Parent，禁止覆盖。",
            row=serialize_category(row), expectedParent=serialize_category(wood),
        )
    if not apply:
        return {
            "category": row,
            "readback": serialize_category(row),
            "evidence": {"decision": "PARENT_UPDATE_REQUIRED", "businessWriteCount": 0},
        }
    key = "WOOD-CATEGORY-HIERARCHY:COMP001:MATCAT-SOLID-WOOD:PARENT:20261006:V1"
    try:
        result = ProductionFoundationService.write(
            "material-categories",
            user=user,
            payload={
                "parent_id": wood.pk,
                "reason": f"{AUTHORIZATION_REFERENCE}；将既有实木归入木质材料",
            },
            idempotency_key=key,
            source_identity={},
            object_id=row.pk,
        )
    except ProductionFoundationError as exc:
        raise WoodCasingTrimWorkflowError(exc.code, exc.message, exc.details) from exc
    row.refresh_from_db()
    row = MaterialCategory.objects.select_related("parent").get(pk=row.pk)
    if row.parent_id != wood.pk:
        fail("SOLID_WOOD_PARENT_READBACK_FAILED", "实木Parent更新后Readback不匹配。")
    ledger = MasterDataWriteRequest.objects.filter(
        organization_id=user.company_id,
        action_code="production.master_data.material.maintain",
        entity_type="material-categories",
        idempotency_key=key,
        target_entity_id=str(row.pk),
    ).first()
    audit = OrganizationOperatingAuditRecord.objects.filter(
        pk=result.get("auditId"), target_type="MaterialCategory", target_id=row.pk,
    ).first()
    if not ledger or not audit:
        fail("SOLID_WOOD_PARENT_EVIDENCE_MISSING", "实木Parent更新缺少审计或幂等账本。")
    result["actionRequestId"] = ledger.pk
    return {
        "category": row,
        "readback": serialize_category(row),
        "evidence": category_write_evidence(result=result, reused=False),
    }


def ensure_category_hierarchy(*, user, apply: bool) -> dict:
    gate_before = category_canonical_gate()
    wood = ensure_category(key="wood", parent=None, user=user, apply=apply)
    if not wood["category"]:
        return {"gateBefore": gate_before, "steps": {"wood": wood}, "complete": False}
    solid = ensure_solid_parent(
        wood=wood["category"], user=user, apply=apply,
    )
    wood_based = ensure_category(
        key="wood_based", parent=wood["category"], user=user, apply=apply,
    )
    if not wood_based["category"]:
        return {
            "gateBefore": gate_before,
            "steps": {"wood": wood, "solid": solid, "woodBased": wood_based},
            "complete": False,
        }
    multilayer = ensure_category(
        key="multilayer", parent=wood_based["category"], user=user, apply=apply,
    )
    steps = {
        "wood": wood,
        "solid": solid,
        "woodBased": wood_based,
        "multilayer": multilayer,
    }
    if not multilayer["category"]:
        return {"gateBefore": gate_before, "steps": steps, "complete": False}
    gate_after = category_canonical_gate()
    for key, expected_parent_key in (
        ("wood", None), ("solid", "wood"),
        ("wood_based", "wood"), ("multilayer", "wood_based"),
    ):
        row = gate_after["exact"][key]
        parent_id = gate_after["exact"][expected_parent_key].pk if expected_parent_key else None
        if not row or row.parent_id != parent_id or not row.is_active:
            fail("CATEGORY_TREE_READBACK_FAILED", "最终Category树Readback不匹配。", key=key)
    return {
        "gateBefore": gate_before,
        "gateAfter": gate_after,
        "steps": steps,
        "complete": True,
        "tree": {
            "root": serialize_category(gate_after["exact"]["wood"]),
            "children": [
                serialize_category(gate_after["exact"]["solid"]),
                {
                    **serialize_category(gate_after["exact"]["wood_based"]),
                    "children": [serialize_category(gate_after["exact"]["multilayer"])],
                },
            ],
        },
        "businessWriteCount": sum(
            step["evidence"]["businessWriteCount"] for step in steps.values()
        ),
    }


def material_state(*, multilayer) -> dict:
    from masterdata.material_identity import canonical_identity, matching_materials
    from masterdata.models import Material

    material = Material.objects.select_related("category", "base_uom").filter(pk=MATERIAL_ID).first()
    if not material:
        fail("MATERIAL_249_MISSING", "Material 249不存在。")
    baseline_ok = (
        material.code == MATERIAL_CODE
        and material.name == MATERIAL_NAME
        and material.company_id == multilayer.company_id
        and material.base_uom_id is not None
        and material.base_uom.code == MATERIAL_UOM_CODE
        and material.base_uom.name == MATERIAL_UOM_CODE
        and material.base_uom.dimension == "count"
        and material.unit_status == "confirmed"
        and material.is_active
        and material.is_purchased
        and not material.is_produced
    )
    if not baseline_ok:
        fail(
            "MATERIAL_249_BASELINE_CONFLICT",
            "Material 249基础身份与用户裁决冲突。",
            material=serialize_material(material),
        )
    original_identity = (
        material.category_id is None
        and not (material.specification or "").strip()
        and not (material.purpose or "").strip()
    )
    target_identity = (
        material.category_id == multilayer.pk
        and material.specification == MATERIAL_SPECIFICATION
        and material.purpose == MATERIAL_PURPOSE
    )
    if not original_identity and not target_identity:
        fail(
            "MATERIAL_249_PARTIAL_OR_CONFLICTING_IDENTITY",
            "Material 249处于非原始、非目标的冲突状态。",
            material=serialize_material(material),
        )
    identity = canonical_identity(values={
        "name": MATERIAL_NAME,
        "category_id": multilayer.pk,
        "purpose": MATERIAL_PURPOSE,
        "specification": MATERIAL_SPECIFICATION,
        "base_uom_id": material.base_uom_id,
    })
    matches = matching_materials(
        company_id=material.company_id, identity=identity, exclude_id=material.pk,
    )
    if matches:
        fail(
            "MATERIAL_249_CANONICAL_CONFLICT",
            "全公司active/inactive范围存在与Material 249目标身份完全相同的Material。",
            candidates=[serialize_material(row) for row in matches],
        )
    peers = list(
        Material.objects.select_related("category", "base_uom")
        .filter(pk__in=(247, 249, 250)).order_by("pk")
    )
    return {
        "material": material,
        "originalIdentity": original_identity,
        "targetIdentity": target_identity,
        "canonicalMatchCountExcluding249": 0,
        "peers": [serialize_material(row) for row in peers],
    }


def ensure_material_249(*, multilayer, user, apply: bool) -> dict:
    from masterdata.models import MasterDataWriteRequest, Material
    from pde.production_foundation_service import ProductionFoundationError, ProductionFoundationService
    from system.models import OrganizationOperatingAuditRecord

    state = material_state(multilayer=multilayer)
    before = serialize_material(state["material"])
    if state["targetIdentity"]:
        return {
            "material": state["material"], "before": before, "after": before,
            "canonicalGate": state,
            "evidence": {"decision": "REUSED_TARGET", "businessWriteCount": 0},
        }
    if not apply:
        return {
            "material": None, "before": before, "after": None,
            "canonicalGate": state,
            "evidence": {"decision": "UPDATE_REQUIRED", "businessWriteCount": 0},
        }
    key = "MATERIAL-249:MULTILAYER:CATEGORY-SPEC-PURPOSE:20261006:V1"
    try:
        result = ProductionFoundationService.write(
            "materials",
            user=user,
            payload={
                "category_id": multilayer.pk,
                "specification": MATERIAL_SPECIFICATION,
                "purpose": MATERIAL_PURPOSE,
                "reason": f"{AUTHORIZATION_REFERENCE}；补齐门套线多层板分类、规格和用途",
            },
            idempotency_key=key,
            source_identity={},
            object_id=MATERIAL_ID,
        )
    except ProductionFoundationError as exc:
        raise WoodCasingTrimWorkflowError(exc.code, exc.message, exc.details) from exc
    final_state = material_state(multilayer=multilayer)
    material = final_state["material"]
    after = serialize_material(material)
    immutable_fields = (
        "id", "code", "name", "applicationNotes", "baseUom", "unit",
        "unitStatus", "materialType", "isPurchased", "isProduced", "supplyType", "active",
    )
    if any(before[field] != after[field] for field in immutable_fields):
        fail(
            "MATERIAL_249_UNAUTHORIZED_FIELD_CHANGE",
            "Material 249更新改变了未授权字段。",
            before=before, after=after,
        )
    ledger = MasterDataWriteRequest.objects.filter(
        organization_id=user.company_id,
        action_code="production.master_data.material.maintain",
        entity_type="materials",
        idempotency_key=key,
        target_entity_id=str(material.pk),
    ).first()
    audit = OrganizationOperatingAuditRecord.objects.filter(
        pk=result.get("auditId"), target_type="Material", target_id=material.pk,
    ).first()
    if not ledger or not audit:
        fail("MATERIAL_249_EVIDENCE_MISSING", "Material 249缺少审计或幂等账本。")
    return {
        "material": material,
        "before": before,
        "after": after,
        "canonicalGate": final_state,
        "evidence": {
            "decision": "IDEMPOTENT_REPLAY" if result.get("idempotentReplay") else "UPDATED",
            "businessWriteCount": 0 if result.get("idempotentReplay") else 4,
            "auditId": audit.pk,
            "actionRequestId": ledger.pk,
            "externalIdentityId": result.get("sourceIdentityId"),
            "authorization": result.get("authorization"),
            "executionChain": result.get("executionChain"),
        },
    }


def fact_bundle(suffix: int) -> dict:
    from pde.models import EngineeringDerivedFact, ProductDesignItem

    item_no = f"{ORDER_NO}-DES-01-SRC-{suffix:04d}"
    item = ProductDesignItem.objects.select_related(
        "sales_order_item__sales_order", "source_record",
    ).filter(item_no=item_no).first()
    if not item:
        fail("DESIGN_ITEM_NOT_FOUND", "CASING_TRIM目标设计对象不存在。", designItemNo=item_no)
    if item.sales_order_item.sales_order.order_no != ORDER_NO or item.sales_order_item.line_no != 1:
        fail("DESIGN_ITEM_ORDER_SCOPE_MISMATCH", "目标设计对象不属于授权订单行1。")
    facts = {}
    for code in ("AW", "AY"):
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
                "AW/AY必须分别精确对应一个当前已保存事实。",
                designItemNo=item_no, factCode=code, matchCount=len(rows),
            )
        facts[code] = rows[0]
    aw, ay = (decimal_fact_value(facts[code]) for code in ("AW", "AY"))
    quantity = aw + ay
    if (aw, ay, quantity) != REFERENCE_FACTS[suffix]:
        fail(
            "CURRENT_CASING_TRIM_FACT_CONFLICT",
            "数据库当前AW/AY与用户裁决事实冲突。",
            designItemNo=item_no,
            expected=[str(value) for value in REFERENCE_FACTS[suffix]],
            actual=[str(aw), str(ay), str(quantity)],
        )
    for code, value in (("AW", aw), ("AY", ay)):
        if value <= 0 or value != value.to_integral_value():
            fail("CASING_TRIM_FACT_INVALID", "AW/AY必须为大于0的整数。", factCode=code)
        if not facts[code].source_detail_id or not facts[code].source_path:
            fail("CASING_TRIM_FACT_LINEAGE_MISSING", "AW/AY缺少Detail或Source Path。")
    return {
        "suffix": suffix,
        "item": item,
        "itemNo": item_no,
        "facts": facts,
        "AW": aw,
        "AY": ay,
        "quantity": quantity,
    }


def serialize_fact_bundle(bundle: dict) -> dict:
    return {
        "designItemId": bundle["item"].pk,
        "designItemNo": bundle["itemNo"],
        "AW": str(bundle["AW"]),
        "AY": str(bundle["AY"]),
        "quantity": str(bundle["quantity"]),
        "facts": [{
            "code": code,
            "factId": bundle["facts"][code].pk,
            "detailId": bundle["facts"][code].source_detail_id,
            "value": str(decimal_fact_value(bundle["facts"][code])),
            "uom": (
                bundle["facts"][code].uom.code
                if bundle["facts"][code].uom_id else None
            ),
            "sourcePath": bundle["facts"][code].source_path,
        } for code in ("AW", "AY")],
    }


def build_contract(*, material, category, bundle):
    from pde.saved_fact_material_requirement_service import (
        SavedFactInputBinding,
        SavedFactMaterialRequirementContract,
    )

    suffix = bundle["suffix"]
    return SavedFactMaterialRequirementContract(
        mapping_no=f"MRC-CASING-TRIM-{suffix:04d}",
        mapping_rule_code=f"MRM.{ORDER_NO}.CASING-TRIM-{suffix:04d}",
        mapping_version="V1",
        rule_name=f"{FORMULA_CODE} / DES-01-SRC-{suffix:04d}",
        order_no=ORDER_NO,
        calculation_id=CALCULATION_ID,
        design_item_no=bundle["itemNo"],
        material_id=material.pk,
        material_code=material.code,
        output_uom_code=MATERIAL_UOM_CODE,
        output_name="casing_trim_piece_quantity",
        expression=FORMULA_EXPRESSION,
        inputs=(
            SavedFactInputBinding(
                "AW", "AW", None, "count",
                unit_required=False, integer_required=True,
            ),
            SavedFactInputBinding(
                "AY", "AY", None, "count",
                unit_required=False, integer_required=True,
            ),
        ),
        primary_source_fact_code="AW",
        expected_quantity=bundle["quantity"],
        authorization_reference=f"{AUTHORIZATION_REFERENCE}:DES01-{suffix:04d}",
        idempotency_key=f"{ORDER_NO}:LINE1:{FORMULA_CODE}:{suffix:04d}:V1",
        purpose_code=STRUCTURE_ROLE,
        quantity_basis="ORDER_TOTAL",
        item_role="material",
        requirement_type="manufacturing",
        supply_type="BUY",
        scrap_rate=Decimal("0"),
        order_specification={
            "businessPurpose": "FORMAL_SALE",
            "businessMeaning": "当前设计对象门套线AW与AY条数合计形成的支数需求",
            "materialPurpose": MATERIAL_PURPOSE,
            "materialCategoryId": category.pk,
            "materialCategoryCode": category.code,
            "materialCategoryName": category.name,
            "materialSpecification": MATERIAL_SPECIFICATION,
            "structureRole": STRUCTURE_ROLE,
            "formulaCode": FORMULA_CODE,
            "formula": FORMULA_EXPRESSION,
            "lossPolicy": "ZERO_LOSS_ENGINEERING_NET_REQUIREMENT",
            "sourceQuantityUnit": "条",
            "targetMaterialUom": MATERIAL_UOM_CODE,
            "currentRequirementUnitMapping": "1条=1支",
            "globalUomConversionCreated": False,
            "qAlreadyAppliedInSourceFacts": True,
            "salesOrderItemQuantityMultiplierApplied": False,
            "excludedLengthFactCodes": ["AV", "AX"],
        },
        provenance={
            "decisionDate": "2026-10-06",
            "decisionSource": "USER_EXPLICIT_BUSINESS_DECISION",
            "materialId": material.pk,
            "materialCode": material.code,
            "materialCategory": {
                "id": category.pk, "code": category.code, "name": category.name,
            },
            "materialSpecification": MATERIAL_SPECIFICATION,
            "materialPurpose": MATERIAL_PURPOSE,
            "structuralRole": STRUCTURE_ROLE,
            "sourceFactCodes": ["AW", "AY"],
            "formulaCode": FORMULA_CODE,
            "formula": FORMULA_EXPRESSION,
            "AW": str(bundle["AW"]),
            "AY": str(bundle["AY"]),
            "quantity": str(bundle["quantity"]),
            "uom": MATERIAL_UOM_CODE,
            "sourceQuantityUnit": "条",
            "currentRequirementUnitMapping": "1条=1支",
            "globalUomConversionCreated": False,
            "qAlreadyApplied": True,
            "salesOrderItemQuantityMultiplierApplied": False,
            "loss": 0,
            "AV": "PRESERVED_NOT_USED_AS_SECOND_CASING_TRIM_REQUIREMENT",
            "AX": "PRESERVED_NOT_USED_AS_SECOND_CASING_TRIM_REQUIREMENT",
            "designMaterialReferencePolicy": (
                "STRUCTURE_REQUIREMENT_DOES_NOT_REPLACE_DESIGN_PRIMARY_MATERIAL"
            ),
        },
        output_scale=6,
        output_unit_dimension="count",
        require_design_material_reference=False,
    )


def build_contracts(*, material, category) -> tuple[list, list]:
    bundles = [fact_bundle(suffix) for suffix in DESIGN_SUFFIXES]
    return bundles, [
        build_contract(material=material, category=category, bundle=bundle)
        for bundle in bundles
    ]


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
                    "actors": {
                        "categoryAndMaterial": material_actor["readback"],
                        "requirement": requirement_actor["readback"],
                    },
                    "businessWriteCount": 0,
                    "bomGenerated": False,
                }
            multilayer = hierarchy["steps"]["multilayer"]["category"]
            material_result = ensure_material_249(
                multilayer=multilayer, user=material_actor["user"], apply=apply,
            )
            if material_result["material"] is None:
                bundles = [fact_bundle(suffix) for suffix in DESIGN_SUFFIXES]
                return {
                    "mode": "INSPECT",
                    "categoryHierarchy": hierarchy,
                    "material": {
                        key: value for key, value in material_result.items()
                        if key != "material"
                    },
                    "facts": [serialize_fact_bundle(row) for row in bundles],
                    "actors": {
                        "categoryAndMaterial": material_actor["readback"],
                        "requirement": requirement_actor["readback"],
                    },
                    "businessWriteCount": 0,
                    "bomGenerated": False,
                }
            bundles, contracts = build_contracts(
                material=material_result["material"], category=multilayer,
            )
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
                    "material": {
                        key: value for key, value in material_result.items()
                        if key != "material"
                    },
                    "facts": [serialize_fact_bundle(row) for row in bundles],
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
                "material": {
                    key: value for key, value in material_result.items()
                    if key != "material"
                },
                "facts": [serialize_fact_bundle(row) for row in bundles],
                "contracts": [asdict(contract) for contract in contracts],
                "previews": previews,
                "applies": applies,
                "readbacks": readbacks,
                "bomPreview": bom_preview,
                "actors": {
                    "categoryAndMaterial": material_actor["readback"],
                    "requirement": requirement_actor["readback"],
                },
                "businessWriteCount": (
                    hierarchy["businessWriteCount"]
                    + material_result["evidence"]["businessWriteCount"]
                    + sum(row["businessWriteCount"] for row in applies)
                ),
                "bomGenerated": False,
            }
    except SavedFactMaterialRequirementError as exc:
        raise WoodCasingTrimWorkflowError(exc.code, exc.message, exc.details) from exc


def readback() -> dict:
    from pde.engineering_calculation_service import OrderEngineeringClosureService
    from pde.saved_fact_material_requirement_service import (
        SavedFactMaterialRequirementError,
        readback_saved_fact_material_requirement,
    )

    material_actor = actor_preflight(MATERIAL_ACTOR, material_actor=True)
    requirement_actor = actor_preflight(REQUIREMENT_ACTOR, material_actor=False)
    hierarchy = ensure_category_hierarchy(user=material_actor["user"], apply=False)
    if not hierarchy["complete"]:
        fail("WOOD_CATEGORY_HIERARCHY_MISSING", "木质材料Category层级尚未完整建立。")
    multilayer = hierarchy["steps"]["multilayer"]["category"]
    material_result = ensure_material_249(
        multilayer=multilayer, user=material_actor["user"], apply=False,
    )
    if material_result["material"] is None:
        fail("MATERIAL_249_NOT_FORMALLY_CLASSIFIED", "Material 249尚未完成正式归类。")
    bundles, contracts = build_contracts(
        material=material_result["material"], category=multilayer,
    )
    try:
        requirement_rows = [
            readback_saved_fact_material_requirement(
                user=requirement_actor["user"], contract=contract,
            )
            for contract in contracts
        ]
    except SavedFactMaterialRequirementError as exc:
        raise WoodCasingTrimWorkflowError(exc.code, exc.message, exc.details) from exc
    return {
        "mode": "READBACK",
        "categoryHierarchy": hierarchy,
        "material": {
            key: value for key, value in material_result.items()
            if key != "material"
        },
        "facts": [serialize_fact_bundle(row) for row in bundles],
        "requirements": requirement_rows,
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
    def compact_authorization(value):
        if not isinstance(value, dict):
            return value
        if "allowed" in value:
            return {
                "allowed": value.get("allowed"),
                "actionCode": value.get("actionCode"),
                "decisionCode": value.get("decisionCode"),
                "roleCodes": value.get("roleCodes"),
                "authoritySource": value.get("authoritySource"),
            }
        return {key: compact_authorization(row) for key, row in value.items()}

    def compact_actor(value):
        if not isinstance(value, dict):
            return value
        return {
            "user": value.get("user"),
            "employee": value.get("employee"),
            "company": value.get("company"),
            "department": value.get("department"),
            "position": value.get("position"),
            "roles": value.get("roles"),
            "authorization": compact_authorization(value.get("authorization")),
        }

    def compact_write_evidence(value):
        if not isinstance(value, dict):
            return value
        return {
            key: (
                compact_authorization(row) if key == "authorization" else row
            )
            for key, row in value.items()
        }

    hierarchy = result.get("categoryHierarchy") or {}
    steps = hierarchy.get("steps") or {}
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
        "categoryHierarchy": {
            "complete": hierarchy.get("complete"),
            "tree": hierarchy.get("tree"),
            "canonicalConflictCount": (
                (hierarchy.get("gateAfter") or hierarchy.get("gateBefore") or {})
                .get("canonicalConflictCount")
            ),
            "steps": {
                key: {
                    "readback": value.get("readback"),
                    "evidence": compact_write_evidence(value.get("evidence")),
                }
                for key, value in steps.items()
            },
            "businessWriteCount": hierarchy.get("businessWriteCount", 0),
        },
        "material": ({
            **(result.get("material") or {}),
            "evidence": compact_write_evidence(
                (result.get("material") or {}).get("evidence")
            ),
        } if result.get("material") else None),
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
            "businessWriteSideEffectCount": preview.get("businessWriteSideEffectCount"),
        },
        "actors": {
            key: compact_actor(value)
            for key, value in (result.get("actors") or {}).items()
        },
        "businessWriteCount": result.get("businessWriteCount", 0),
        "bomGenerated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--readback", action="store_true")
    parser.add_argument("--allow-isolated", action="store_true")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    database = args.database.resolve()
    if args.apply and database != FORMAL_DATABASE and not args.allow_isolated:
        raise RuntimeError("FORMAL_DATABASE_TARGET_MISMATCH")
    configure(database)
    try:
        result = readback() if args.readback else execute(apply=args.apply)
    except WoodCasingTrimWorkflowError as exc:
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
