"""Re-read original Excel sources. No recalculation, workbook edit, or Native rerun."""
import json
import re
from collections import Counter
from pathlib import Path
from semi_finished_model_closure_audit import ROOT, OUT, save, sha
import sys
sys.path.insert(0, str(ROOT / "scripts/excel_parity"))
from workbook_source import SourceBook, coord

source = json.loads((ROOT / "backend/pde/semi_finished_configuration_source.json").read_text(encoding="utf-8"))
books = {}
for info in source["sourceFiles"]:
    assert sha(info["path"]) == info["sha256"]
    books[info["file"]] = SourceBook(info["path"])
main = books["工程拆单及订单排产数据核算方式.xlsx"]
rows = [r for r in source["realRows"] if r["sheet"] == "三合一生产单"]
analysis = []
for row in rows:
    n = row["row"]
    actual = main.sheets[row["sheet"]][f"L{n}"]
    assert actual["value"] == row["cells"][f"L{n}"]["value"]
    references = [{"cell": a, "formula": c["formula"]} for a, c in main.sheets[row["sheet"]].items()
                  if coord(a)[0] == n and c.get("formula") and re.search(rf"\$?L\$?{n}(?![0-9])", c["formula"])]
    analysis.append({"sheet": row["sheet"], "row": n, "thicknessCell": f"L{n}", "sourceValue": actual["value"],
        "sourceFormula": actual.get("formula"), "configurationCode": "BTKF2601001", "semantic": "UNKNOWN",
        "directFormulaConsumers": references, "sourceLayerDecomposition": None,
        "reason": "输入L列是工程部件的厚度值；被旧几何查表消费不证明是原板厚。05/12/13及层结构来源未提供可唯一闭合的原板厚、层数、层厚、胶层、加工余量组合。"})
trace = {}
for key in ("拆单基础数据", "坯板目录（设计）", "木皮目录（设计）", "表板目录（设计）"):
    trace[key] = source["dependencies"][key]
exact = []
for code in ("BTKF2601001", "QSFB4601001"):
    config = next(x for x in source["sourceRows"] if x["fields"]["半成品板材编码"]["value"] == code)
    facts = {}
    for attr, field, catalog, namefield in (
        ("veneer", "木皮种类", "12木皮.xlsx|木皮", "木皮目录"),
        ("color", "颜色/色板号", "04色板.xlsx|颜色板号目录", "颜色/板号名称"),
        ("substrate", "坯板材质", "13坯板.xlsx|坯板", "坯板目录")):
        raw = config["fields"][field]["value"]
        matches = [r for r in source["catalogs"][catalog] if r["fields"].get(namefield, {}).get("value") == raw]
        purchase = [r for r in source["catalogs"]["10采购物料.xlsx|采购物料"] if r["fields"].get("物料名称", {}).get("value") == raw]
        facts[attr] = {"sourceValue": raw, "sourceCell": config["fields"][field]["cell"], "sourceValidated": True,
            "exactCatalogRows": matches, "exactPurchaseRows": purchase,
            "procurementResolution": "UNRESOLVED", "method": "EXACT_OR_CONTROLLED_EXTERNAL_IDENTITY_ONLY"}
    exact.append({"configurationCode": code, "facts": facts})
rules = json.loads((OUT / "EXISTING_RULES.json").read_text(encoding="utf-8"))
rule_audit = [{"id": r["id"], "code": r["rule_code"], "status": r["status"],
               "specification": json.loads(r["specification"]),
               "materialQuantityApplicable": False, "reason": "既有4规则属于门套/门尺寸G1验证，不是本轮材料消耗规则；不绑定、不修改"} for r in rules]
save("THICKNESS_RECHECK.json", {"sourceHashesVerified": len(books), "rows": analysis,
    "distribution": dict(Counter(r["sourceValue"] for r in analysis)), "autoResolved": 0,
    "unknown": len(analysis), "layerSources": trace,
    "roughStructureReference": {"path": "backend/masterdata/group3_comparison_source.json", "sha256": sha(ROOT / "backend/masterdata/group3_comparison_source.json"),
        "scope": "engineeringBreakdown only; 08 excluded; structural roles are not layer thickness facts"},
    "ruleAudit": rule_audit, "nativeRerun": False})
save("CONTROLLED_IDENTITY_RECHECK.json", {"configs": exact, "businessFamily": "实木多层板",
    "allowedProcurementMembers": [], "allowedSpecifications": [],
    "reason": "正式MaterialCategory无该族，来源13给出族名但没有将10的具体编码列为允许成员；不以多层/OSB名称相似或尺寸近似建立正式关系。"})
print(json.dumps({"sourcesRead": len(books), "thicknessRows": len(analysis), "autoResolved": 0,
                  "unknown": len(analysis), "exactProcurementIdentities": 0, "rulesUnchanged": len(rules)}, ensure_ascii=False))
