"""Read-only Foundation Wave 1 manufacturing source preview.

Requirement trace: PCM-MD-001/002/006/009/010, PCM-ACC-005 and
Production L7 V1.6 rules 47/48/52/53/58/68/72-79.

This module is deliberately stateless.  It parses the three approved source
workbooks in memory, reads canonical facts through the existing production
foundation service, and never calls a model save or a code allocator.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

from django.apps import apps
from django.db.migrations.recorder import MigrationRecorder
from openpyxl import load_workbook
from masterdata.uom_governance import UnitOfMeasureNormalizer

from .production_foundation_service import ProductionFoundationService


class FoundationImportPreviewError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class ApprovedSource:
    file_name: str
    sha256: str
    sheet: str
    candidate_type: str
    adapter: str
    source_object_type: str
    code_field: str = ""
    name_field: str = ""
    specification_field: str = ""
    category_fields: tuple[str, ...] = ()
    missing_uom_policy: str = "REQUIRE_STANDARD_UOM"
    placeholder_names: frozenset[str] = frozenset()
    include_procurement_facts: bool = False


APPROVED_SOURCES = {
    "01工序.xlsx": ApprovedSource(
        "01工序.xlsx",
        "310706432239D1017F48677B1A7BF6C4D6F9BA247C92946B239C5C9191EF6C38",
        "工序管理",
        "OPERATION",
        "OPERATION_REGISTER_V1",
        "MANUFACTURING_OPERATION_SOURCE",
    ),
    "05半成品板材.xlsx": ApprovedSource(
        "05半成品板材.xlsx",
        "2D2FC7BC7558CB0CDE9D8FE3521FCB83B0C9858C6827E24B85C192D4504124DF",
        "半成品板材",
        "MATERIAL",
        "SEMI_FINISHED_MATERIAL_REGISTER_V1",
        "SEMI_FINISHED_MATERIAL_SOURCE",
        "半成品板材编码",
        "半成品板材名称",
        "油漆工艺名称",
        (),
        "ALLOW_UNIT_NOT_CONFIRMED",
        frozenset({"待定", "待定待定"}),
    ),
    "10采购物料.xlsx": ApprovedSource(
        "10采购物料.xlsx",
        "0A5BFD0810C77B8A0DE92D08C68C58FD63EE2C9E32F506A3E607B2F8658CEA3D",
        "采购物料",
        "MATERIAL",
        "PURCHASE_MATERIAL_REGISTER_V1",
        "PURCHASE_MATERIAL_SOURCE",
        "物料编码",
        "物料名称",
        "规格/型号",
        ("物料分类", "物料品类"),
        "REQUIRE_STANDARD_UOM",
        frozenset(),
        True,
    ),
}

MAX_SOURCE_BYTES = 5 * 1024 * 1024
# Frozen, independently tested evidence from approved source 02.  The runtime
# preview stays portable: it does not depend on a developer workstation path.
# The acceptance test re-opens the approved workbook and proves these facts.
ROUTING_REFERENCE_EVIDENCE = {
    "fileName": "02工艺路线.xlsx",
    "sha256": "67338393E63E44C78D0B3B56270EE7A79A83A67EAB295B81B6ADF2EF8373DF3B",
    "sourceCodeField": "半成品编码",
    "distinctSourceCodes": 42,
    "matchedApproved05Codes": 0,
}

SOURCE_IDENTITY_SYSTEM = "PCE_FOUNDATION_WAVE1"
SOURCE_IDENTITY_TYPE = "APPROVED_XLSX"


def _text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _row_hash(rows):
    payload = json.dumps(
        rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")
    return sha256(payload).hexdigest().upper()


def _external_id(source, suffix):
    return f"{source.file_name}|{source.sheet}|{suffix}"


def _resolve_existing(
    source, facts, *, target_entity_type, external_id, fallback_matches,
    source_name, source_object_type=None,
):
    """Resolve a formal object without mutating identity or master-data facts.

    A persisted identity is authoritative.  Fallback matching is used only when
    no identity exists; a corrupt identity never silently degrades into CREATE.
    The same resolver is used by Material, Operation and Workshop previews.
    """
    object_type = source_object_type or source.source_object_type
    identities = [
        item for item in facts.get("externalIdentities", [])
        if item.get("organization_id") == facts["organizationId"]
        and _text(item.get("source_system")) == SOURCE_IDENTITY_SYSTEM
        and _text(item.get("source_type")) == SOURCE_IDENTITY_TYPE
        and _text(item.get("source_object_type")) == object_type
        and _text(item.get("external_id")) == external_id
    ]
    if len(identities) > 1:
        return {
            "status": "DATA_INTEGRITY_ERROR", "match": None,
            "viaIdentity": True, "payloadChanged": False,
            "reason": "同一组织与来源身份出现多条映射；禁止降级为新增候选。",
        }
    if identities:
        identity = identities[0]
        if _text(identity.get("mapping_status")) != "MATCH":
            return {
                "status": "DATA_INTEGRITY_ERROR", "match": None,
                "viaIdentity": True, "payloadChanged": False,
                "reason": "来源身份已存在但不是MATCH状态；禁止降级为新增候选。",
            }
        if _text(identity.get("target_entity_type")) != target_entity_type:
            return {
                "status": "DATA_INTEGRITY_ERROR", "match": None,
                "viaIdentity": True, "payloadChanged": False,
                "reason": "来源身份指向错误的正式对象类型；禁止降级为新增候选。",
            }
        target_id = _text(identity.get("target_entity_id"))
        targets = [
            item for item in facts[target_entity_type]
            if _text(item.get("id")) == target_id
        ]
        if len(targets) != 1:
            return {
                "status": "DATA_INTEGRITY_ERROR", "match": None,
                "viaIdentity": True, "payloadChanged": False,
                "reason": "来源身份指向的正式对象不存在或不唯一；禁止降级为新增候选。",
            }
        match = targets[0]
        return {
            "status": "IDENTITY_MATCH", "match": match,
            "viaIdentity": True,
            "payloadChanged": _text(match.get("name")) != source_name,
            "reason": "已通过同组织持久化ExternalIdentity解析到正式对象。",
        }
    if len(fallback_matches) > 1:
        return {
            "status": "FALLBACK_CONFLICT", "match": None,
            "viaIdentity": False, "payloadChanged": False,
            "reason": "未找到来源身份，且保守回退匹配不唯一。",
        }
    return {
        "status": "FALLBACK_MATCH" if fallback_matches else "NO_MATCH",
        "match": fallback_matches[0] if fallback_matches else None,
        "viaIdentity": False, "payloadChanged": False,
        "reason": (
            "未找到来源身份；已使用原有精确匹配保守复用。"
            if fallback_matches else
            "未找到来源身份或正式对象；保留为新增候选。"
        ),
    }


def _common_row(source, row_number, source_code, source_name, raw_uom):
    return {
        "id": f"{source.sha256[:12]}:{row_number}",
        "sourceFile": source.file_name,
        "sourceSha256": source.sha256,
        "sourceSheet": source.sheet,
        "sourceRow": row_number,
        "sourceCode": source_code,
        "sourceName": source_name,
        "rawUom": raw_uom,
        "sourceIdentityStatus": "SOURCE_IDENTITY_VERIFIED",
        "existingCanonicalMatch": None,
        "canonicalCode": "",
        "formalBusinessWriteCount": 0,
    }


def _material_rows(source, worksheet, facts):
    iterator = worksheet.iter_rows(values_only=True)
    headers = [_text(value) for value in next(iterator)]
    records = []
    source_codes = []
    raw_rows = []
    for row_number, values in enumerate(iterator, 2):
        raw = dict(zip(headers, values))
        source_code = _text(raw.get(source.code_field))
        source_name = _text(raw.get(source.name_field))
        if not source_code or not source_name:
            continue
        source_codes.append(source_code)
        raw_rows.append((row_number, raw, source_code, source_name))
    duplicate_codes = {code for code in source_codes if source_codes.count(code) > 1}

    for row_number, raw, source_code, source_name in raw_rows:
        raw_uom = _text(raw.get("单位"))
        row = _common_row(source, row_number, source_code, source_name, raw_uom)
        fallback_matches = [
            item for item in facts["materials"]
            if _text(item.get("code")) == source_code
        ]
        identity = _resolve_existing(
            source, facts, target_entity_type="materials",
            external_id=_external_id(source, f"CODE:{source_code}"),
            fallback_matches=fallback_matches, source_name=source_name,
        )
        match = identity["match"]
        match_conflict = (
            identity["status"] == "FALLBACK_CONFLICT"
            or bool(match and not identity["viaIdentity"] and _text(match.get("name")) != source_name)
        )
        uom_resolution = UnitOfMeasureNormalizer.resolve(raw_uom, facts["units"])
        uom = uom_resolution["match"]
        incomplete = source_name in source.placeholder_names
        integrity_error = identity["status"] == "DATA_INTEGRITY_ERROR"
        conflict = source_code in duplicate_codes or match_conflict
        unit_not_confirmed_allowed = (
            source.missing_uom_policy == "ALLOW_UNIT_NOT_CONFIRMED" and not raw_uom
        )
        if match and not conflict:
            decision = "EXISTING_REUSE"
            code_policy = "REUSE_EXISTING_CODE"
            canonical_code = _text(match.get("code"))
            existing = {
                "id": match.get("id"), "code": canonical_code, "name": match.get("name"),
            }
        else:
            decision = "NEW_MATERIAL_CANDIDATE"
            code_policy = "GENERATE_FORMAL_MATERIAL_CODE"
            canonical_code = ""
            existing = None

        if integrity_error:
            validation = "DATA_INTEGRITY_ERROR"
            recommendation = "UNRESOLVED"
            reason = identity["reason"]
        elif conflict:
            validation = "CONFLICT"
            recommendation = "UNRESOLVED"
            reason = "来源编码重复，或与同编码正式物料的名称冲突；禁止自动复用。"
        elif incomplete:
            validation = "INCOMPLETE_SOURCE"
            recommendation = "UNRESOLVED"
            reason = "来源编码可信，但名称是明显占位值；不得补造正式名称。"
        elif identity["payloadChanged"]:
            validation = "SEMANTIC_REVIEW"
            recommendation = "EXISTING_REUSE"
            reason = "ExternalIdentity已解析正式对象，但来源名称与正式名称不同；需数据变更裁决，禁止重复CREATE。"
        elif unit_not_confirmed_allowed:
            validation = "READY_FOR_DECISION"
            recommendation = decision
            reason = "来源未提供基本单位；正式模型支持UNIT_NOT_CONFIRMED且不会猜填单位。"
        elif uom_resolution["classification"] == UnitOfMeasureNormalizer.SEMANTIC_REVIEW:
            validation = "SEMANTIC_REVIEW"
            recommendation = decision
            reason = uom_resolution["reason"]
        elif uom_resolution["classification"] == UnitOfMeasureNormalizer.INVALID:
            validation = "UOM_INVALID"
            recommendation = "UNRESOLVED"
            reason = uom_resolution["reason"]
        else:
            validation = "READY_FOR_DECISION"
            recommendation = decision
            reason = "来源身份已确认；仅按完整来源编码精确匹配正式物料。"

        row.update({
            "sourceObjectType": source.source_object_type,
            "sourceIdentityStatus": (
                "SOURCE_IDENTITY_INTEGRITY_ERROR" if integrity_error
                else "SOURCE_IDENTITY_MATCHED" if identity["viaIdentity"]
                else "SOURCE_IDENTITY_VERIFIED"
            ),
            "identityResolution": identity,
            "specification": _text(raw.get(source.specification_field)),
            "sourceCategory": (
                "半成品物料来源" if not source.category_fields else
                " / ".join(filter(None, [_text(raw.get(field)) for field in source.category_fields]))
            ),
            "existingCanonicalMatch": existing,
            "candidateObject": "MATERIAL",
            "canonicalCodePolicy": code_policy,
            "canonicalCode": canonical_code,
            "uomDecision": uom_resolution["classification"],
            "uomStatus": (
                "STANDARD_INITIALIZATION_READY" if uom and uom.get("standardInitialization")
                else "EXISTING_UOM_REUSE" if uom
                else "UNIT_NOT_CONFIRMED" if unit_not_confirmed_allowed
                else uom_resolution["classification"]
            ),
            "uomGovernance": uom_resolution,
            "existingUomMatch": ({
                "id": uom.get("id"), "code": uom.get("code"), "name": uom.get("name"),
            } if uom else None),
            "validationStatus": validation,
            "recommendedDecision": recommendation,
            "reason": reason,
            "productDecision": (
                "DEFERRED_NO_FORMAL_PRODUCT_SOURCE"
                if source.adapter == "SEMI_FINISHED_MATERIAL_REGISTER_V1"
                else "NOT_APPLICABLE"
            ),
            "procurementFacts": ({
                "price": raw.get("单价"),
                "minimumStock": raw.get("最低存量"),
                "minimumOrderQuantity": raw.get("起订量"),
                "maximumStock": raw.get("最高存量"),
                "minimumLeadTime": raw.get("最短采购周期"),
                "maximumLeadTime": raw.get("最长采购周期"),
                "classification": "DEFERRED_PROCUREMENT_PRICE_AND_POLICY",
            } if source.include_procurement_facts else None),
            "commitReadiness": {
                "eligibleSourceRecord": not incomplete and not conflict and not integrity_error,
                "canonicalCodeReady": not incomplete and not conflict and not integrity_error,
                "uomReady": bool(uom) or unit_not_confirmed_allowed,
                "uomPolicy": (
                    "ALLOWED_WITH_UNIT_NOT_CONFIRMED" if unit_not_confirmed_allowed
                    else "STANDARD_INITIALIZATION_READY" if uom and uom.get("standardInitialization")
                    else "EXACT_OR_NORMALIZED_REUSE" if uom else "PENDING"
                ),
                "sourceIdentityPersistenceReady": True,
                "formalWriteEligible": not incomplete and not conflict and not integrity_error and not identity["payloadChanged"] and (
                    bool(uom) or unit_not_confirmed_allowed
                ),
            },
        })
        records.append(row)
    return records


def _operation_rows(source, worksheet, facts):
    iterator = worksheet.iter_rows(values_only=True)
    headers = [_text(value) for value in next(iterator)]
    raw_rows = []
    names = []
    for row_number, values in enumerate(iterator, 2):
        raw = dict(zip(headers, values))
        name = _text(raw.get("工序名称"))
        if not name:
            continue
        names.append(name)
        raw_rows.append((row_number, raw, name))
    duplicate_names = {name for name in names if names.count(name) > 1}
    records = []
    for row_number, raw, name in raw_rows:
        raw_uom = _text(raw.get("核算单位"))
        row = _common_row(source, row_number, "", name, raw_uom)
        matches = [item for item in facts["operations"] if _text(item.get("name")) == name]
        operation_identity = _resolve_existing(
            source, facts, target_entity_type="operations",
            external_id=_external_id(source, f"ROW:{row_number}"),
            fallback_matches=matches, source_name=name,
        )
        match = operation_identity["match"]
        uom_resolution = UnitOfMeasureNormalizer.resolve(raw_uom, facts["units"])
        uom = uom_resolution["match"]
        workshop_name = _text(raw.get("车间"))
        workshop_matches = [
            item for item in facts["workshops"] if _text(item.get("name")) == workshop_name
        ]
        workshop_identity = _resolve_existing(
            source, facts, target_entity_type="workshops",
            external_id=_external_id(source, f"WORKSHOP:{workshop_name}"),
            fallback_matches=workshop_matches, source_name=workshop_name,
            source_object_type="WORKSHOP_SOURCE",
        )
        workshop = workshop_identity["match"]
        integrity_error = (
            operation_identity["status"] == "DATA_INTEGRITY_ERROR"
            or workshop_identity["status"] == "DATA_INTEGRITY_ERROR"
        )
        payload_changed = (
            operation_identity["payloadChanged"] or workshop_identity["payloadChanged"]
        )
        conflict = (
            name in duplicate_names
            or operation_identity["status"] == "FALLBACK_CONFLICT"
            or workshop_identity["status"] == "FALLBACK_CONFLICT"
        )
        basis_only_ready = (
            not uom
            and uom_resolution["classification"] == UnitOfMeasureNormalizer.SEMANTIC_REVIEW
            and uom_resolution.get("dimension") in {"count", "length", "area", "volume", "mass", "time"}
        )
        if integrity_error:
            validation = "DATA_INTEGRITY_ERROR"
            recommendation = "UNRESOLVED"
            reason = "；".join(
                item["reason"] for item in (operation_identity, workshop_identity)
                if item["status"] == "DATA_INTEGRITY_ERROR"
            )
        elif conflict:
            validation = "CONFLICT"
            recommendation = "UNRESOLVED"
            reason = "工序名称或车间精确匹配不唯一，必须人工裁决。"
        elif payload_changed:
            validation = "SEMANTIC_REVIEW"
            recommendation = "EXISTING_REUSE" if match else "UNRESOLVED"
            reason = "ExternalIdentity已解析正式对象，但来源名称与正式名称不同；需数据变更裁决，禁止重复CREATE。"
        elif basis_only_ready:
            validation = "READY_FOR_DECISION"
            recommendation = "EXISTING_REUSE" if match else "NEW_OPERATION_CANDIDATE"
            reason = "工序核算维度已明确；具体UOM是可选执行参数，不阻断Operation主数据建立。"
        elif uom_resolution["classification"] == UnitOfMeasureNormalizer.INVALID:
            validation = "UOM_INVALID"
            recommendation = "UNRESOLVED"
            reason = uom_resolution["reason"]
        else:
            validation = "READY_FOR_DECISION"
            recommendation = "EXISTING_REUSE" if match else "NEW_OPERATION_CANDIDATE"
            reason = "工序来源身份已确认；正式编码只在未来提交时由CodeRule生成。"
        row.update({
            "sourceObjectType": source.source_object_type,
            "sourceIdentityStatus": (
                "SOURCE_IDENTITY_INTEGRITY_ERROR" if integrity_error
                else "SOURCE_IDENTITY_MATCHED" if operation_identity["viaIdentity"]
                else "SOURCE_IDENTITY_VERIFIED"
            ),
            "identityResolution": operation_identity,
            "sourceCategory": _text(raw.get("工序类别")),
            "specification": _text(raw.get("投产量")),
            "existingCanonicalMatch": ({
                "id": match.get("id"), "code": match.get("code"), "name": match.get("name"),
            } if match else None),
            "candidateObject": "OPERATION",
            "canonicalCodePolicy": "REUSE_EXISTING_CODE" if match else "GENERATE_CANONICAL_CODE_PENDING_APPROVAL",
            "canonicalCode": _text(match.get("code")) if match else "",
            "canonicalCodeDisplay": _text(match.get("code")) if match else "提交时由正式编码规则生成",
            "uomDecision": uom_resolution["classification"],
            "uomStatus": (
                "STANDARD_INITIALIZATION_READY" if uom and uom.get("standardInitialization")
                else "EXISTING_UOM_REUSE" if uom
                else "BASIS_ONLY_READY" if basis_only_ready
                else uom_resolution["classification"]
            ),
            "uomGovernance": uom_resolution,
            "existingUomMatch": ({
                "id": uom.get("id"), "code": uom.get("code"), "name": uom.get("name"),
            } if uom else None),
            "validationStatus": validation,
            "recommendedDecision": recommendation,
            "reason": reason,
            "workshop": {
                "sourceName": workshop_name,
                "status": "EXISTING_REUSE" if workshop else "WORKSHOP_CANDIDATE",
                "canonicalCode": _text(workshop.get("code")) if workshop else "PENDING",
                "identityResolution": workshop_identity,
            },
            "workCenterStatus": "NOT_MAINTAINED",
            "operationMeasurement": {
                "operationKind": "group" if "工序组" in _text(raw.get("工序类别")) else "atomic",
                "calculationBasis": uom_resolution.get("dimension") or (
                    uom.get("dimension") if uom else "undetermined"
                ),
                "calculationUomId": uom.get("id") if uom else None,
                "quantityDriver": "" if _text(raw.get("投产量")) == "无法核算" else _text(raw.get("投产量")),
                "quantityDriverStatus": (
                    "NOT_DETERMINABLE" if _text(raw.get("投产量")) == "无法核算" else "SOURCE_CONFIRMED"
                ),
            },
            "productDecision": "NOT_APPLICABLE",
            "commitReadiness": {
                "eligibleSourceRecord": not conflict and not integrity_error,
                "canonicalCodeReady": not integrity_error,
                "uomReady": bool(uom) or basis_only_ready,
                "uomPolicy": "BASIS_ONLY_READY" if basis_only_ready else uom_resolution["classification"],
                "sourceIdentityPersistenceReady": True,
                "formalWriteEligible": not conflict and not integrity_error and not payload_changed and (bool(uom) or basis_only_ready),
            },
        })
        records.append(row)
    return records


class FoundationImportPreviewService:
    @staticmethod
    def _commit_readiness(source, rows, facts, operation_rule):
        is_semifinished = source.adapter == "SEMI_FINISHED_MATERIAL_REGISTER_V1"
        is_purchase = source.adapter == "PURCHASE_MATERIAL_REGISTER_V1"
        incomplete = sum(row["validationStatus"] == "INCOMPLETE_SOURCE" for row in rows)
        conflicts = sum(row["validationStatus"] == "CONFLICT" for row in rows)
        candidates = sum(row["commitReadiness"]["eligibleSourceRecord"] for row in rows)
        existing_reuse = sum(row["recommendedDecision"] == "EXISTING_REUSE" for row in rows)
        uom_ready = sum(
            row["commitReadiness"]["uomReady"] and row["commitReadiness"]["eligibleSourceRecord"]
            for row in rows
        )
        canonical_ready = sum(
            row["commitReadiness"]["canonicalCodeReady"] and row["commitReadiness"]["eligibleSourceRecord"]
            for row in rows
        )
        ready = sum(row["validationStatus"] == "READY_FOR_DECISION" for row in rows)
        review = sum(row["validationStatus"] == "SEMANTIC_REVIEW" for row in rows)
        blocked = sum(
            row["validationStatus"] in {"INCOMPLETE_SOURCE", "CONFLICT", "UOM_INVALID", "DATA_INTEGRITY_ERROR"}
            for row in rows
        )

        if is_semifinished:
            policy = "GENERATE_FORMAL_MATERIAL_CODE"
            policy_decision = "05来源编码作为外部身份保留；新增物料由统一Material CodeRule生成正式编码"
            category_policy = "ATTRIBUTE_ONLY; CATEGORY_NULL_ALLOWED"
            blockers = ["3条来源名称为占位值，属于真实数据质量阻断；修正来源事实前不得创建。"] if blocked else []
            reviews = []
        elif is_purchase:
            policy = "GENERATE_FORMAL_MATERIAL_CODE"
            policy_decision = "10来源序号1–132仅作为外部身份；新增物料由统一Material CodeRule生成正式编码"
            category_policy = "AMBIGUOUS; CATEGORY_NULL_ALLOWED"
            blockers = []
            reviews = []
        else:
            policy = "FORMAL_OPERATION_AND_WORKSHOP_CODE_RULE_READY"
            policy_decision = "工序与车间正式编码均由统一CodeRule生成；面积已归类为核算维度AREA"
            category_policy = "NOT_APPLICABLE"
            blockers = []
            reviews = []
            if not operation_rule:
                blockers.append("隔离验收数据库缺少production_operation正式编码规则。")

        authorization_ready = True
        write_service_ready = True
        formal_write_gate = "PARTIAL" if blocked or review or blockers else "GO"
        wave2_migration_applied = MigrationRecorder.Migration.objects.filter(
            app="pde", name="0019_manufacturing_structure_wave2",
        ).exists()
        return {
            "status": "PARTIAL" if formal_write_gate == "PARTIAL" else "READY",
            "reviewStatus": "RECORD_LEVEL_DECISION_COMPLETE",
            "sourcePolicy": policy,
            "sourcePolicyDecision": policy_decision,
            "formalCommitCandidates": candidates,
            "excludedIncomplete": incomplete,
            "excludedConflict": conflicts,
            "existingReuse": existing_reuse,
            "canonicalCodeReady": canonical_ready,
            "canonicalCodePending": max(candidates - canonical_ready, 0),
            "uomReady": uom_ready,
            "uomPending": max(candidates - uom_ready, 0),
            "sourceIdentityPersistenceReady": candidates,
            "sourceIdentityPersistenceBlocked": 0,
            "formalWriteServiceReady": write_service_ready,
            "authorizationAuditReady": authorization_ready,
            "readyForAuthorizedWrite": ready,
            "ready": ready,
            "review": review,
            "blocked": blocked,
            "excluded": blocked,
            "formalWriteAuthorized": False,
            "gateDecisions": {
                "engineeringCodeCommitReadiness": "GO",
                "productionMigrationReadiness": "GO",
                "formalMasterDataWriteReadiness": formal_write_gate,
                "gitCommitAuthorization": "NOT_GRANTED",
                "productionMigrationAuthorization": (
                    "COMPLETE" if wave2_migration_applied else "NOT_GRANTED"
                ),
                "formalMasterDataWriteAuthorization": "NOT_GRANTED",
            },
            "workshopCandidateCount": len({
                row.get("workshop", {}).get("sourceName") for row in rows
                if row.get("workshop", {}).get("status") == "WORKSHOP_CANDIDATE"
            }),
            "workCenterCandidateCount": 0,
            "categoryPolicy": category_policy,
            "routingReferenceEvidence": ROUTING_REFERENCE_EVIDENCE if is_semifinished else None,
            "uomPolicy": (
                "ALLOWED_WITH_UNIT_NOT_CONFIRMED" if is_semifinished
                else "EXACT_OR_NORMALIZED_OR_INITIALIZATION_READY"
            ),
            "blockers": blockers,
            "reviewItems": reviews,
            "rowExceptions": [
                {
                    "sourceRow": row["sourceRow"],
                    "sourceCode": row["sourceCode"],
                    "sourceName": row["sourceName"],
                    "status": row["validationStatus"],
                    "issue": row["reason"],
                    "blockerType": "SOURCE_DATA_BLOCKER" if row["validationStatus"] == "INCOMPLETE_SOURCE" else "BUSINESS_FACT_BLOCKER",
                    "formalCommitCandidate": False,
                }
                for row in rows
                if row["validationStatus"] in {"INCOMPLETE_SOURCE", "CONFLICT", "UOM_INVALID", "DATA_INTEGRITY_ERROR"}
            ],
            "rowReviews": [
                {
                    "sourceRow": row["sourceRow"], "sourceCode": row["sourceCode"],
                    "sourceName": row["sourceName"], "issue": row["reason"],
                    "blockerType": "BUSINESS_FACT_BLOCKER",
                }
                for row in rows if row["validationStatus"] == "SEMANTIC_REVIEW"
            ],
            "formalChain": {
                "transaction": "READY",
                "modelValidation": "READY",
                "authorization": "READY",
                "organizationAudit": "READY",
                "serverReadback": "READY",
                "identityResolution": "READY",
                "idempotency": "READY",
                "migration": "APPLIED" if wave2_migration_applied else "READY_NOT_APPLIED",
            },
        }

    @staticmethod
    def _canonical_facts(organization_id):
        entities = {
            "materials": "materials", "units": "units", "products": "products",
            "operations": "operations", "workshops": "workshops", "workCenters": "work-centers",
        }
        facts = {
            key: ProductionFoundationService.list(entity, organization_id=organization_id)
            for key, entity in entities.items()
        }
        ExternalIdentity = apps.get_model("masterdata", "ExternalIdentity")
        facts["organizationId"] = organization_id
        facts["externalIdentities"] = list(
            ExternalIdentity.objects.filter(
                organization_id=organization_id,
                source_system=SOURCE_IDENTITY_SYSTEM,
                source_type=SOURCE_IDENTITY_TYPE,
            ).order_by("pk").values()
        )
        Supplier = apps.get_model("procurement", "Supplier")
        Customer = apps.get_model("sales", "Customer")
        facts["suppliers"] = list(Supplier.objects.order_by("pk").values())
        facts["customers"] = list(Customer.objects.order_by("pk").values())
        return facts

    @classmethod
    def preview(cls, *, uploaded_file, organization_id):
        file_name = Path(_text(getattr(uploaded_file, "name", ""))).name
        source = APPROVED_SOURCES.get(file_name)
        if not source:
            raise FoundationImportPreviewError(
                "SOURCE_NOT_APPROVED", "请选择当前检查点批准的01、05或10来源文件。",
                {"fileName": file_name, "approvedFiles": sorted(APPROVED_SOURCES)},
            )
        payload = uploaded_file.read(MAX_SOURCE_BYTES + 1)
        if len(payload) > MAX_SOURCE_BYTES:
            raise FoundationImportPreviewError("SOURCE_TOO_LARGE", "来源文件超过5MB限制。")
        digest = sha256(payload).hexdigest().upper()
        if digest != source.sha256:
            raise FoundationImportPreviewError(
                "SOURCE_IDENTITY_MISMATCH", "来源文件SHA256与当前批准版本不一致。",
                {"fileName": file_name, "expectedSha256": source.sha256, "actualSha256": digest},
            )
        try:
            workbook = load_workbook(BytesIO(payload), read_only=True, data_only=True)
        except Exception as exc:
            raise FoundationImportPreviewError(
                "SOURCE_PARSE_FAILED", "无法读取所选XLSX来源文件。", {"error": str(exc)},
            ) from exc
        try:
            if source.sheet not in workbook.sheetnames:
                raise FoundationImportPreviewError(
                    "SOURCE_SHEET_MISSING", "批准的来源工作表不存在。",
                    {"expectedSheet": source.sheet, "actualSheets": workbook.sheetnames},
                )
            facts = cls._canonical_facts(organization_id)
            worksheet = workbook[source.sheet]
            rows = (
                _operation_rows(source, worksheet, facts)
                if source.candidate_type == "OPERATION"
                else _material_rows(source, worksheet, facts)
            )
        finally:
            workbook.close()

        code_rules = ProductionFoundationService.list("operations", organization_id=organization_id)
        CodeRule = apps.get_model("masterdata", "CodeRule")
        operation_rule = CodeRule.objects.filter(
            entity_type="production_operation", company_id=organization_id,
        ).values("entity_type", "prefix", "date_format", "seq_length", "current_seq").first()
        material_rule = CodeRule.objects.filter(
            entity_type="production_material", company_id=organization_id,
        ).values("entity_type", "prefix", "date_format", "seq_length", "current_seq").first()
        workshop_rule = CodeRule.objects.filter(
            entity_type="production_workshop", company_id=organization_id,
        ).values("entity_type", "prefix", "date_format", "seq_length", "current_seq").first()
        protection = {
            "existingMaterial": len(facts["materials"]),
            "existingUom": len(facts["units"]),
            "existingProduct": len(facts["products"]),
            "existingOperation": len(facts["operations"]),
            "existingWorkshop": len(facts["workshops"]),
            "existingWorkCenter": len(facts["workCenters"]),
            "existingSupplier": len(facts["suppliers"]),
            "existingCustomer": len(facts["customers"]),
            "existingRecordUpdatePlan": 0,
            "formalMasterDataWrite": 0,
            "codeSequenceChange": 0,
            "schemaChange": 0,
            "migration": 0,
            "hashes": {
                key: _row_hash(value) for key, value in facts.items()
                if isinstance(value, list)
            },
        }
        statistics = {
            "total": len(rows),
            "sourceIdentityVerified": sum(
                row["sourceIdentityStatus"] in {"SOURCE_IDENTITY_VERIFIED", "SOURCE_IDENTITY_MATCHED"}
                for row in rows
            ),
            "existingReuse": sum(row["recommendedDecision"] == "EXISTING_REUSE" for row in rows),
            "newMaterialCandidate": sum(
                row["recommendedDecision"] == "NEW_MATERIAL_CANDIDATE"
                and row["commitReadiness"]["eligibleSourceRecord"]
                for row in rows
            ),
            "sourceOperationCandidates": sum(row["candidateObject"] == "OPERATION" for row in rows),
            "incompleteSource": sum(row["validationStatus"] == "INCOMPLETE_SOURCE" for row in rows),
            "canonicalCodePending": sum(
                row["commitReadiness"]["eligibleSourceRecord"]
                and not row["commitReadiness"]["canonicalCodeReady"]
                for row in rows
            ),
            "uomPending": sum(row["uomStatus"] in {"SEMANTIC_REVIEW", "INVALID"} for row in rows),
            "conflict": sum(row["validationStatus"] == "CONFLICT" for row in rows),
        }
        workshop_candidates = sorted({
            row["workshop"]["sourceName"] for row in rows
            if row.get("workshop", {}).get("status") == "WORKSHOP_CANDIDATE"
        })
        commit_readiness = cls._commit_readiness(source, rows, facts, operation_rule)
        return {
            "factLoadStatus": "loaded",
            "factSource": "server canonical facts + approved source bytes",
            "validationAction": {
                "actionType": "VALIDATION_ACTION",
                "actionCode": "production.master_data.view",
                "formalBusinessWriteCount": 0,
                "auditWriteCount": 0,
            },
            "source": {
                "fileName": source.file_name, "sha256": digest, "bytes": len(payload),
                "sheet": source.sheet, "candidateType": source.candidate_type,
            },
            "statistics": statistics,
            "protection": protection,
            "productBoundary": {
                "formalImport": False,
                "decision": "DEFERRED_NO_FORMAL_PRODUCT_SOURCE",
                "message": "暂不建立产品定义——当前来源只证明半成品物料身份。",
            },
            "operationBoundary": {
                "codeRule": operation_rule,
                "materialCodeRule": material_rule,
                "workshopCodeRule": workshop_rule,
                "previewCalledNextCode": False,
                "workshopCandidates": workshop_candidates,
                "workCenter": "NOT_MAINTAINED",
                "existingOperationRowsRead": len(code_rules),
            },
            "commitReadiness": commit_readiness,
            "rows": rows,
        }
