"""Build the immutable Group 2 source snapshot from approved XLSX evidence."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from openpyxl import load_workbook


SOURCE_ROOT = Path(
    r"C:\Users\DAODA\Documents\Codex\2026-09-01\files-pasted-by-the-user-pce"
    r"\outputs\PCE_WAVE2_SOURCE_DISCOVERY_READINESS_V1.0\sources"
)
OUTPUT = Path(__file__).resolve().parents[1] / "masterdata" / "group2_comparison_source.json"


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def read_rows(file_name, sheet_name=None):
    path = SOURCE_ROOT / file_name
    book = load_workbook(path, read_only=True, data_only=True)
    sheet = book[sheet_name] if sheet_name else book.worksheets[0]
    rows = list(sheet.iter_rows(values_only=True))
    book.close()
    return path, sheet.title, rows


def material_rows():
    output = []
    path, sheet, rows = read_rows("05半成品板材.xlsx")
    headers = [clean(value) for value in rows[0]]
    for row_no, values in enumerate(rows[1:], 2):
        row = dict(zip(headers, values))
        if not clean(row.get("半成品板材编码")) or not clean(row.get("半成品板材名称")):
            continue
        is_placeholder = (
            clean(row.get("半成品板材名称")) == "待定待定"
            or clean(row.get("油漆工艺名称")) == "待定"
        )
        output.append({
            "sourceFile": path.name, "sourceSheet": sheet, "sourceRow": row_no,
            "sourceKind": "SEMI_FINISHED_MATERIAL",
            "sourceCode": clean(row.get("半成品板材编码")),
            "sourceName": clean(row.get("半成品板材名称")),
            "specification": clean(row.get("油漆工艺名称")),
            "sourceUom": clean(row.get("单位")),
            "materialType": "semi", "makeBuy": "MAKE",
            "sourceValidity": "INVALID_PLACEHOLDER" if is_placeholder else "VALID",
            "proposedAction": "SOURCE_CORRECTION_REQUIRED" if is_placeholder else "MATCH_FORMAL_MATERIAL",
            "attributes": {
                "拼皮": clean(row.get("是否拼皮")), "肤感": clean(row.get("是否肤感")),
                "颜色/色板号": clean(row.get("颜色/色板号")), "木皮种类": clean(row.get("木皮种类")),
                "坯板材质": clean(row.get("坯板材质")), "油漆种类": clean(row.get("油漆种类")),
            },
        })
    path, sheet, rows = read_rows("10采购物料.xlsx")
    headers = [clean(value) for value in rows[0]]
    for row_no, values in enumerate(rows[1:], 2):
        row = dict(zip(headers, values))
        if not clean(row.get("物料名称")) or not clean(row.get("物料编码")):
            continue
        output.append({
            "sourceFile": path.name, "sourceSheet": sheet, "sourceRow": row_no,
            "sourceKind": "PURCHASE_COMPONENT_MATERIAL",
            "sourceCode": clean(row.get("物料编码")), "sourceName": clean(row.get("物料名称")),
            "specification": clean(row.get("规格/型号")), "sourceUom": clean(row.get("单位")),
            "materialType": clean(row.get("物料分类")) or "UNKNOWN", "makeBuy": "BUY",
            "sourceValidity": "VALID", "proposedAction": "MATCH_FORMAL_MATERIAL",
            "purchaseLeadTimeMin": clean(row.get("最短采购周期")),
            "purchaseLeadTimeMax": clean(row.get("最长采购周期")),
            "attributes": {"物料品类": clean(row.get("物料品类")), "备注": clean(row.get("备注"))},
        })
    return output


def catalog_rows(file_name, semantic):
    path, sheet, rows = read_rows(file_name)
    result = []
    for row_no, values in enumerate(rows[1:], 2):
        name = clean(values[1] if len(values) > 1 else "")
        if name:
            result.append({
                "sourceFile": path.name, "sourceSheet": sheet, "sourceRow": row_no,
                "catalogSemantic": semantic, "sourceName": name,
                "classification": "MATERIAL_ATTRIBUTE_REFERENCE_NOT_SALES_PRODUCT",
            })
    return result


def product_rows():
    path, sheet, rows = read_rows("08订单排产信息（样版）.xlsx")
    headers = [clean(value) for value in rows[0]]
    output = []
    for row_no, values in enumerate(rows[1:], 2):
        row = dict(zip(headers, values))
        order_no = clean(row.get("主订单号"))
        product_type = clean(row.get("产品类型"))
        if order_no in {"", "0"} or product_type in {"", "0"}:
            continue
        output.append({
            "sourceFile": path.name, "sourceSheet": sheet, "sourceRow": row_no,
            "salesOrderNo": clean(row.get("主订单号")), "salesOrderItemNo": clean(row.get("子订单号")),
            "customer": clean(row.get("客户")), "projectName": clean(row.get("项目名称")),
            "sourceProductType": clean(row.get("产品类型")),
            "sourceEngineeredMaterialCode": clean(row.get("半成品板材编码")),
            "sourceEngineeredMaterialName": clean(row.get("半成品编码")),
            "orderType": clean(row.get("订单类型")),
            # The scheduling source calls this field "产品类型".  It does not
            # provide a concrete product name, model, dimensions or space, so
            # these facts must remain visibly missing in the identity preview.
            "sourceProductField": "产品类型",
            "sourceProductName": "",
            "sourceProductModel": "",
            "sourceSpecification": "",
            "sourceDimensions": {"height": "", "width": "", "thickness": ""},
            "sourceSpace": "",
            "identityCompleteness": "CATEGORY_AND_ORDER_CONTEXT_ONLY",
            "quantityEvidence": {
                "柜门数量": clean(row.get("柜门数量")), "柜体数量": clean(row.get("柜体数量")),
                "房门数量": clean(row.get("房门数量")), "饰面数量": clean(row.get("饰面数量")),
            },
            "productionMeasureEvidence": {
                name: clean(row.get(name)) for name in (
                    "油漆数量", "木工数量", "贴皮数量", "拼皮数量", "UV数量",
                    "防潮数量", "饰面数量", "柜门数量", "柜体数量", "房门数量",
                    "免漆数量", "开放数量", "混油数量", "封闭数量", "肤感数量",
                )
            },
        })
    return output


def engineering_identity_evidence():
    """Read identity-capable engineering fields without joining unrelated samples."""
    evidence = []
    workbook = SOURCE_ROOT / "工程拆单及订单排产数据核算方式.xlsx"
    book = load_workbook(workbook, read_only=True, data_only=True)
    sheet_specs = (
        ("房门单提取数据", {
            "materialCode": "物料编码(必填)", "processCode": "工艺编码(必填)",
            "productCategory": "产品类别(必填)", "space": "安装区域",
            "productName": "产品名称", "model": "",
            "height": "洞高", "width": "洞宽", "thickness": "墙厚",
        }),
        ("三合一提取数据", {
            "materialCode": "物料编码(必填)", "processCode": "工艺编码(必填)",
            "productCategory": "产品类别(必填)", "space": "安装区域",
            "productName": "产品名称", "model": "型号",
            "height": "高", "width": "宽", "thickness": "厚",
        }),
    )
    for sheet_name, mapping in sheet_specs:
        sheet = book[sheet_name]
        rows = list(sheet.iter_rows(values_only=True))
        headers = [clean(value) for value in rows[0]]
        for row_no, values in enumerate(rows[1:], 2):
            row = dict(zip(headers, values))
            category = clean(row.get(mapping["productCategory"]))
            product_name = clean(row.get(mapping["productName"]))
            material_code = clean(row.get(mapping["materialCode"]))
            # These sheets contain cached formula tails whose displayed value is
            # the string "0".  They are not source facts and must never inflate
            # the engineering identity evidence count.
            if category in {"", "0"} or product_name in {"", "0"} or material_code in {"", "0"}:
                continue
            evidence.append({
                "sourceFile": workbook.name,
                "sourceSheet": sheet_name,
                "sourceRow": row_no,
                "materialCode": material_code,
                "processCode": clean(row.get(mapping["processCode"])),
                "productCategory": category,
                "space": clean(row.get(mapping["space"])),
                "productName": product_name,
                "model": clean(row.get(mapping["model"])) if mapping["model"] else "",
                "dimensions": {
                    "height": clean(row.get(mapping["height"])),
                    "width": clean(row.get(mapping["width"])),
                    "thickness": clean(row.get(mapping["thickness"])),
                },
                "linkageToSchedulingSource": "NO_STABLE_KEY",
            })
    book.close()
    return evidence


materials = material_rows()
valid_materials = [row for row in materials if row["sourceValidity"] == "VALID"]
products = product_rows()
engineering_evidence = engineering_identity_evidence()
veneers = catalog_rows("12木皮.xlsx", "VENEER_CATALOG")
boards = catalog_rows("13坯板.xlsx", "BLANK_BOARD_CATALOG")
files = [
    "05半成品板材.xlsx", "08订单排产信息（样版）.xlsx", "10采购物料.xlsx",
    "12木皮.xlsx", "13坯板.xlsx", "工程拆单及订单排产数据核算方式.xlsx",
]
product_counts = Counter(row["sourceProductType"] for row in products)
product_codes = {}
for row in products:
    product_codes.setdefault(row["sourceProductType"], set()).add(row["sourceEngineeredMaterialCode"])

snapshot = {
    "version": "GROUP2-PRODUCT-IDENTITY-PREVIEW-V2",
    "readOnly": True,
    "generatedFrom": [{"fileName": name, "sha256": digest(SOURCE_ROOT / name)} for name in files],
    "materialRows": materials,
    "materialReferenceCatalogs": veneers + boards,
    "productOrderRows": products,
    "engineeringIdentityEvidence": {
        "sourceFile": "工程拆单及订单排产数据核算方式.xlsx",
        "linkageTo08": "NO_STABLE_KEY",
        "reason": "工程拆单样例含安装区域、产品名称、型号和尺寸，但订单号与08排产样例不同，不能反向拼接到37行。",
        "availableIdentityFields": ["安装区域", "产品名称", "型号", "高", "宽", "厚"],
        "rows": engineering_evidence,
    },
    "productCandidates": [{
        "sourceProductName": name,
        "sourceOrderLineCount": count,
        "sourceEngineeredMaterialCodes": sorted(product_codes[name]),
        "proposedFormalObject": "pde.ProductCategory (PREVIEW ONLY)",
        "proposedAction": "USER_CONFIRM_PRODUCT_CATEGORY",
        "configurationMode": "PENDING USER DECISION",
        "configurationModeOptions": [],
        "decisionNote": (
            "来源原值“饰面”是否应确认为“木饰面”需用户裁决。"
            if name == "饰面" else "客户购买产品候选；不把其组成板材/五金作为销售产品。"
        ),
    } for name, count in sorted(product_counts.items())],
    "summary": {
        "materialSourceRecordCount": len(materials),
        "materialCandidateCount": len(valid_materials),
        "invalidMaterialSourceCount": len(materials) - len(valid_materials),
        "semiFinishedMaterialCount": sum(row["sourceKind"] == "SEMI_FINISHED_MATERIAL" for row in valid_materials),
        "purchaseMaterialCount": sum(row["sourceKind"] == "PURCHASE_COMPONENT_MATERIAL" for row in valid_materials),
        "materialReferenceCatalogCount": len(veneers) + len(boards),
        "veneerReferenceCount": len(veneers), "blankBoardReferenceCount": len(boards),
        "productOrderLineCount": len(products),
        "distinctProductCandidateCount": len(product_counts),
        "distinctEngineeredMaterialCodeCount": len({row["sourceEngineeredMaterialCode"] for row in products}),
    },
    "group1Decision": {
        "userValidated": True,
        "uomDecisions": {
            "平方": "MAP_TO_M2_SQUARE_METER",
            "面积": "NOT_A_UOM_CALCULATION_BASIS_AREA",
        },
        "simulatedAuxiliaryFieldsAllowed": True,
        "productionBusinessWriteCount": 0,
    },
}
OUTPUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(snapshot["summary"], ensure_ascii=False, indent=2))
print(OUTPUT)
