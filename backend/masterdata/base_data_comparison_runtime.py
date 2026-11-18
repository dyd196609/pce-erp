"""Read-only Batch 1 source-to-formal comparison runtime.

The source snapshot is generated from the user-approved whole-house XLSX files
and carries workbook hashes and source row numbers. Runtime comparison always
queries the current canonical tables and has no write branch.
"""

from functools import lru_cache
import json
from pathlib import Path

from .models import UnitOfMeasure
from procurement.models import Supplier
from sales.models import Customer


SOURCE_PATH = Path(__file__).with_name("base_data_comparison_source.json")
SUPPORTED_ENTITIES = {"customers", "suppliers", "uoms"}


def _text(value):
    return str(value or "").strip()


def _key(value):
    return _text(value).casefold()


@lru_cache(maxsize=1)
def _source_snapshot():
    return json.loads(SOURCE_PATH.read_text(encoding="utf-8"))


def _is_explicit_test_customer(row):
    marker = " ".join((row.code, row.name, row.acceptance_marker)).casefold()
    return any(token in marker for token in ("test", "accept", "验收", "测试"))


def _customer_formal(company_id):
    return [{
        "id": row.pk,
        "formalCode": row.code,
        "formalName": row.name,
        "enabled": row.is_active,
        "dataOrigin": "sales.Customer",
        "testHistorical": _is_explicit_test_customer(row),
    } for row in Customer.objects.filter(company_id=company_id).order_by("code", "id")]


def _supplier_formal(company_id):
    return [{
        "id": row.pk,
        "formalCode": row.code,
        "formalName": row.name,
        "enabled": row.is_active,
        "dataOrigin": row.data_origin,
        "testHistorical": False,
    } for row in Supplier.objects.filter(company_id=company_id).order_by("code", "id")]


def _uom_formal(company_id):
    return [{
        "id": row.pk,
        "formalCode": row.code,
        "formalName": row.name,
        "symbol": row.symbol,
        "dimension": row.dimension,
        "enabled": row.is_active,
        "dataOrigin": "masterdata.UnitOfMeasure",
        "testHistorical": False,
    } for row in UnitOfMeasure.objects.filter(company_id=company_id).order_by("code", "id")]


def _formal_tokens(row):
    return {_key(row.get(field)) for field in ("formalCode", "formalName", "symbol") if row.get(field)}


def _serialize_match(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "formalCode": row["formalCode"],
        "formalName": row["formalName"],
        "enabled": row["enabled"],
        "dataOrigin": row["dataOrigin"],
    }


def build_batch1_comparison(entity, company_id):
    if entity not in SUPPORTED_ENTITIES:
        raise KeyError(entity)

    snapshot = _source_snapshot()
    source = snapshot["sources"][entity]
    if entity == "customers":
        formal = _customer_formal(company_id)
    elif entity == "suppliers":
        formal = _supplier_formal(company_id)
    else:
        formal = _uom_formal(company_id)

    rows = []
    matched_formal_ids = set()
    conflict_count = 0
    invalid_count = 0
    for source_row in source["rows"]:
        source_value = _text(source_row.get("sourceValue") or source_row.get("sourceName"))
        if not source_value:
            invalid_count += 1
            rows.append({
                **source_row,
                "matchStatus": "INCOMPLETE_SOURCE",
                "formalMatch": None,
                "proposedAction": "SOURCE_CORRECTION_REQUIRED",
                "decisionReason": "来源必填名称为空，不生成正式候选。",
            })
            continue

        if entity == "uoms":
            candidates = [item for item in formal if _key(source_value) in _formal_tokens(item)]
        else:
            candidates = [item for item in formal if _key(item["formalName"]) == _key(source_value)]

        if len(candidates) > 1:
            conflict_count += 1
            status = "CONFLICT"
            proposed = "MANUAL_MATCH_REQUIRED"
            reason = "精确匹配命中多个正式对象，禁止自动选择。"
            match = None
        elif candidates:
            match = candidates[0]
            matched_formal_ids.add(match["id"])
            status = "EXACT_MATCH"
            proposed = "REUSE_EXISTING"
            reason = "来源值与正式编码、名称或符号精确匹配。"
        elif entity == "uoms" and source_value == "平方":
            match = next((item for item in formal if item["formalCode"] == "m2"), None)
            if match:
                matched_formal_ids.add(match["id"])
            status = "USER_DECISION_MAPPED"
            proposed = "REUSE_EXISTING"
            reason = "用户已裁决：平方 → m² / 平方米。"
        elif entity == "uoms" and source_value == "面积":
            match = None
            status = "USER_DECISION_NOT_UOM"
            proposed = "CALCULATION_BASIS_AREA"
            reason = "用户已裁决：面积不是UOM；标记calculation_basis=AREA，不创建面积UOM。"
        else:
            match = None
            status = "NO_MATCH"
            proposed = "CREATE_OR_MANUAL_MATCH_REVIEW"
            reason = "未找到精确正式匹配；未执行模糊匹配或自动新增。"

        rows.append({
            **source_row,
            "matchStatus": status,
            "formalMatch": _serialize_match(match),
            "candidateFormal": (
                next((_serialize_match(item) for item in formal if item["formalCode"] == "m2"), None)
                if entity == "uoms" and source_value in {"平方", "面积"} else None
            ),
            "proposedAction": proposed,
            "decisionReason": reason,
        })

    formal_only = [item for item in formal if item["id"] not in matched_formal_ids]
    formal_duplicate_groups = 0
    if entity == "suppliers":
        names = [_key(item["formalName"]) for item in formal]
        formal_duplicate_groups = len({name for name in names if names.count(name) > 1})

    exact_count = sum(row["matchStatus"] == "EXACT_MATCH" for row in rows)
    unmatched_count = sum(row["matchStatus"] == "NO_MATCH" for row in rows)
    return {
        "factLoadStatus": "success",
        "comparisonVersion": snapshot["version"],
        "entity": entity,
        "readOnly": True,
        "productionBusinessMasterDataWriteCount": 0,
        "source": {key: value for key, value in source.items() if key != "rows"},
        "summary": {
            "sourceRecordCount": len(rows),
            "validSourceCount": len(rows) - invalid_count,
            "formalRecordCount": len(formal),
            "exactMatchCount": exact_count,
            "unmatchedSourceCount": unmatched_count,
            "formalOutsideCurrentSourceCount": len(formal_only),
            "conflictCount": conflict_count,
            "invalidSourceCount": invalid_count,
            "formalDuplicateGroupCount": formal_duplicate_groups,
            "explicitTestHistoricalCount": sum(item["testHistorical"] for item in formal),
            "readiness": "VALIDATED",
            "userValidated": True,
        },
        "rows": rows,
        "formalOutsideCurrentSourceRows": formal_only,
    }
