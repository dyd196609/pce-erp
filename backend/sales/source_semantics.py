"""DO4 source evidence: archived strings, never an inferred sales quantity."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path

RULE_VERSION = "PCM-SALES-017/DO4-1"
ARCHIVE = Path(__file__).resolve().parents[1] / "masterdata/group3_comparison_source.json"


def source_evidence():
    content = ARCHIVE.read_bytes()
    archive = json.loads(content)
    rows = []
    groups = {}
    operations = archive["operationRows"]
    for raw in archive["schedulingRows"]:
        category = raw["sourceProductType"]
        field = f"{category}数量"
        value = raw["quantityEvidence"].get(field)
        group = groups.setdefault(category, {"productName": category, "quantity": Decimal(0), "sourceRows": [], "sourceQuantityField": field})
        group["quantity"] += Decimal(value) if value is not None else Decimal(0)
        group["sourceRows"].append(raw["sourceRow"])
        rows.append({
            "sourceRow": raw["sourceRow"], "salesOrderItemNo": raw["salesOrderItemNo"],
            "productType": category, "engineeringSourceCode": raw["sourceEngineeredMaterialCode"],
            "rawFields": raw, "quantityField": field, "rawQuantity": value,
            "exactQuantity": value, "businessQuantity": None, "uomId": None,
            "businessTypeLabel": "工程／排产来源记录（非已确认销售明细）",
            "quantityRoleLabel": "工程装配／工序驱动量，销售用途未证明",
            "identityCompleteness": raw["identityCompleteness"],
            "proposedSalesLine": None,
            "mergeRule": "不能按类别合并；需逐行产品、配置、空间、单位、交付职责及商业数量证据。重复工程展开仅引用一次，不累加销售数量。",
            "unknowns": ["商业产品身份", "配置", "空间", "交付职责", "销售数量及单位"],
        })
    summaries = [{**v, "quantity": str(v["quantity"]), "uom": "工程维度待核实；不是销售单位", "statusLabel": "分类汇总，不等于销售明细"} for v in groups.values()]
    return {
        "rows": rows, "groups": summaries,
        "archiveSha256": hashlib.sha256(content).hexdigest().upper(),
        "archivePath": "backend/masterdata/group3_comparison_source.json",
        "evidenceType": "已归档规范化证据；本轮未重新打开 Excel 原件",
        "operationEvidence": [r for r in operations if r.get("quantityDriver") in ("饰面数量", "柜体数量", "房门数量")],
        "precision": {
            "rawFinishValues": [r["rawQuantity"] for r in rows if r["productType"] == "饰面"],
            "exactFinishTotal": str(groups["饰面"]["quantity"]),
            "meaning": "8 条饰面工程来源的饰面数量合计；01工序归档将该字段作为装配面积驱动，但未给出正式单位。不是已确认销售数量。",
            "salesQuantity": None, "rounding": "无舍入；保留原字符串，Decimal 精确求和",
            "salesStorageDecimalPlaces": 4,
        },
    }
