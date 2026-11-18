"""Read-only Group 2 source-to-formal comparison runtime.

This module has no mutation branch.  It compares the immutable workbook
snapshot with the current canonical Material and PDE product tables.
"""

from collections import Counter, defaultdict, deque
from functools import lru_cache
import json
from pathlib import Path

from django.db import DatabaseError, connection
from django.db.models import Count

from .models import ExternalIdentity, Material
from planning.models import (
    Demand,
    MasterProductionScheduleLine,
    MaterialRequirementProposal,
    PlanningRequirement,
    ProductionPlan,
    PurchasePlan,
)
from sales.models import SalesOrderItem
from pde.models import (
    BOMItem,
    ConfiguredProduct,
    OrderEngineeringInstance,
    ProductCategory,
    ProductConfiguration,
    ProductDefinition,
    ProductTemplate,
    ProductVersion,
)


SOURCE_PATH = Path(__file__).with_name("group2_comparison_source.json")
SUPPORTED_ENTITIES = {"materials", "products", "product-versions-configurations"}


def _text(value):
    return str(value or "").strip()


def _norm(value):
    return "".join(_text(value).casefold().split())


def _supply(row):
    if row.is_purchased and not row.is_produced:
        return "BUY"
    if row.is_produced and not row.is_purchased:
        return "MAKE"
    return "UNDETERMINED"


def _material_key(name, specification, make_buy):
    return (_norm(name), _norm(specification), make_buy)


def _norm_uom(value):
    normalized = _norm(value)
    return {
        "平方": "平方米", "m2": "平方米", "m²": "平方米", "㎡": "平方米",
        "kg": "千克", "公斤": "千克",
    }.get(normalized, normalized)


@lru_cache(maxsize=1)
def _snapshot():
    return json.loads(SOURCE_PATH.read_text(encoding="utf-8"))


def _formal_materials(company_id):
    return list(
        Material.objects.filter(company_id=company_id)
        .select_related("base_uom", "purchase_uom", "category")
        .order_by("id")
    )


def _serialize_material(row):
    return {
        "id": row.pk,
        "formalCode": row.code,
        "formalName": row.name,
        "specification": row.specification or "",
        "materialType": row.material_type,
        "uom": row.base_uom.name if row.base_uom_id else row.unit,
        "uomCode": row.base_uom.code if row.base_uom_id else "",
        "makeBuy": _supply(row),
        "enabled": row.is_active,
        "category": row.category.name if row.category_id else "",
        "dataOrigin": "masterdata.Material",
    }


def _material_reference_counts(material_ids):
    """Return server-owned usage evidence without mutating planning/order facts."""
    model_fields = (
        ("salesOrderItems", SalesOrderItem),
        ("bomItems", BOMItem),
        ("demands", Demand),
        ("mpsLines", MasterProductionScheduleLine),
        ("mrpProposals", MaterialRequirementProposal),
        ("planningRequirements", PlanningRequirement),
        ("purchasePlans", PurchasePlan),
        ("productionPlans", ProductionPlan),
    )
    result = {material_id: {name: 0 for name, _ in model_fields} for material_id in material_ids}
    available_tables = set(connection.introspection.table_names())
    for name, model in model_fields:
        if model._meta.db_table not in available_tables:
            continue
        try:
            rows = model.objects.filter(material_id__in=material_ids).values("material_id").annotate(total=Count("id"))
            for row in rows:
                result[row["material_id"]][name] = row["total"]
        except DatabaseError:
            # The production database can temporarily lag optional planning
            # migrations.  A missing optional evidence table must not take
            # down the authoritative material comparison.
            continue
    return result


def _build_materials(company_id, snapshot):
    source_rows = snapshot["materialRows"]
    source_hashes = {item["fileName"]: item["sha256"] for item in snapshot["generatedFrom"]}
    formal_objects = _formal_materials(company_id)
    reference_counts = _material_reference_counts([row.pk for row in formal_objects])
    queues = defaultdict(deque)
    for row in formal_objects:
        queues[_material_key(row.name, row.specification, _supply(row))].append(row)

    exclusion_by_code = {
        row.audit_metadata.get("sourceCode"): row.audit_metadata
        for row in ExternalIdentity.objects.filter(
            organization_id=company_id,
            source_system="PCE_GROUP2_ACCEPTANCE",
            source_type="USER_VALIDATED_XLSX",
            source_object_type="SEMI_FINISHED_MATERIAL_SOURCE",
            mapping_status=ExternalIdentity.MappingStatus.BLOCK,
        )
    }
    matched_ids = set()
    compared = []
    conflict_count = 0
    for source in source_rows:
        if source["sourceValidity"] != "VALID":
            decision = exclusion_by_code.get(source["sourceCode"], {})
            compared.append({
                **source,
                "dataProvenance": f"{source['sourceFile']} / {source['sourceSheet']} / row {source['sourceRow']} / sha256 {source_hashes.get(source['sourceFile'], '')}",
                "matchStatus": "USER_EXCLUDED_INCOMPLETE_SOURCE" if decision else "INVALID_SOURCE",
                "formalMatch": None,
                "conflicts": ["来源名称或工艺规格仍为‘待定’，不得形成正式主数据。"],
                "sourceDecisionStatus": decision.get("decisionStatus", ""),
                "importEligible": decision.get("importEligible"),
                "planningEligible": decision.get("planningEligible"),
                "formalMaterialCreate": decision.get("formalMaterialCreate", 0),
            })
            continue
        key = _material_key(source["sourceName"], source["specification"], source["makeBuy"])
        match = queues[key].popleft() if queues[key] else None
        conflicts = []
        if match:
            matched_ids.add(match.pk)
            expected_type = "semi" if source["sourceKind"] == "SEMI_FINISHED_MATERIAL" else None
            if expected_type and match.material_type != expected_type:
                conflicts.append(f"Material Type: 来源={expected_type} / 正式={match.material_type}")
            if _supply(match) != source["makeBuy"]:
                conflicts.append(f"MAKE/BUY: 来源={source['makeBuy']} / 正式={_supply(match)}")
            formal_uom = match.base_uom.name if match.base_uom_id else match.unit
            if source["sourceUom"] and _norm_uom(source["sourceUom"]) != _norm_uom(formal_uom):
                conflicts.append(f"UOM: 来源={source['sourceUom']} / 正式={formal_uom or '未维护'}")
        code_exact = bool(match and _norm(source["sourceCode"]) == _norm(match.code))
        status = "CONFLICT" if conflicts else (
            "EXACT_MATCH" if match and code_exact else ("ATTRIBUTE_MATCH" if match else "NO_MATCH")
        )
        if conflicts:
            conflict_count += 1
        compared.append({
            **source,
            "dataProvenance": f"{source['sourceFile']} / {source['sourceSheet']} / row {source['sourceRow']} / sha256 {source_hashes.get(source['sourceFile'], '')}",
            "matchStatus": status,
            "formalMatch": _serialize_material(match) if match else None,
            "conflicts": conflicts,
            "codeComparison": "EXACT" if code_exact else ("SYSTEM_CODE_DIFFERS_FROM_SOURCE" if match else "NO_FORMAL_MATCH"),
            "matchBasis": "名称 + 规格 + MAKE/BUY + UOM（按用户UOM裁决归一）" if match else "无",
            "proposedAction": "REUSE_EXISTING" if status in {"EXACT_MATCH", "ATTRIBUTE_MATCH"} else (
                "MANUAL_CONFLICT_REVIEW" if status == "CONFLICT" else "MANUAL_MATCH_OR_MAINTENANCE_PREVIEW"
            ),
            "supplyEvidence": (
                "10采购物料：来源明确为采购对象；正式记录is_purchased=True。"
                if source["sourceFile"].startswith("10") else
                "05半成品板材：来源明确为半成品板材；正式记录is_produced=True。"
            ),
            "supplyValidationStatus": "PENDING USER VALIDATION",
        })

    formal_rows = []
    for row in formal_objects:
        serialized = _serialize_material(row)
        counts = reference_counts[row.pk]
        reference_total = sum(counts.values())
        if row.pk in matched_ids:
            classification = "REAL_WHOLE_HOUSE_MATERIAL"
            evidence = "与05半成品板材或10采购物料的有效来源行完成业务属性匹配；来源编码另列"
        elif row.code.upper() in {f"MT{index:03d}" for index in range(1, 81)}:
            classification = "TEST_HISTORICAL"
            evidence = "明确命中backend/generate_orders_standalone.py开发样例批次MT001–MT080；不是仅因未出现在Excel而判定"
        else:
            classification = "POSSIBLE_REAL_OUTSIDE_SOURCE" if reference_total else "UNKNOWN_OUTSIDE_SOURCE"
            evidence = "未命中当前整木来源，但存在业务引用，需核查是否为其它真实来源" if reference_total else "未命中当前来源且无明确测试证据；保持未知，待人工核查"
        formal_rows.append({
            **serialized,
            "classification": classification,
            "classificationEvidence": evidence,
            "productionReferenceCounts": counts,
            "productionReferenceTotal": reference_total,
            "productionReferenceStatus": "REFERENCE_EXISTS_REVIEW_REQUIRED" if reference_total else "NO_EXPLICIT_PRODUCTION_REFERENCE",
        })

    exact_count = sum(row["matchStatus"] == "EXACT_MATCH" for row in compared)
    match_count = sum(row["matchStatus"] in {"EXACT_MATCH", "ATTRIBUTE_MATCH"} for row in compared)
    unmatched_count = sum(row["matchStatus"] in {"NO_MATCH", "INVALID_SOURCE", "USER_EXCLUDED_INCOMPLETE_SOURCE"} for row in compared)
    historical_count = sum(row["classification"] == "TEST_HISTORICAL" for row in formal_rows)
    historical_rows = [row for row in formal_rows if row["classification"] == "TEST_HISTORICAL"]
    historical_types = Counter(row["materialType"] for row in historical_rows)
    mouse = next((row for row in historical_rows if row["formalCode"] == "MT004"), None)
    historical_examples = ([mouse] if mouse else []) + [
        row for row in historical_rows if not mouse or row["id"] != mouse["id"]
    ][:11]

    def representative_group(source):
        name = source["sourceName"]
        category = source.get("attributes", {}).get("物料品类", "")
        if any(token in name for token in ("长虹", "磨砂", "钢化", "银镜")):
            return "玻璃 / 镜面类"
        if any(token in name for token in ("铝条", "拉丝", "青古铜", "黑钛金")):
            return "五金 / 型材类"
        if source["sourceKind"] == "SEMI_FINISHED_MATERIAL":
            return "板材（自制半成品）"
        if category == "板材":
            return "板材（采购）"
        if category == "木皮":
            return "木皮"
        return "其它采购件"

    representative_rows = []
    group_counts = Counter()
    for row in compared:
        if row["matchStatus"] not in {"EXACT_MATCH", "ATTRIBUTE_MATCH"}:
            continue
        group = representative_group(row)
        if group_counts[group] >= 3:
            continue
        group_counts[group] += 1
        representative_rows.append({**row, "representativeGroup": group})
    targeted_rows = [
        {
            "sourceRow": row["sourceRow"], "sourceCode": row["sourceCode"],
            "materialId": row["formalMatch"]["id"],
            "formalCode": row["formalMatch"]["formalCode"],
            "formalName": row["formalMatch"]["formalName"],
            "currentUom": row["formalMatch"]["uom"], "proposedUom": "平方米",
            "makeBuy": row["formalMatch"]["makeBuy"], "materialType": row["formalMatch"]["materialType"],
            "result": "PASS" if row["formalMatch"]["uomCode"] == "m2" else "待整改",
            "dataProvenance": row["dataProvenance"],
        }
        for row in compared
        if row.get("sourceFile") == "05半成品板材.xlsx"
        and row.get("sourceKind") == "SEMI_FINISHED_MATERIAL"
        and row.get("sourceValidity") == "VALID"
        and row.get("formalMatch")
    ]
    return {
        "entity": "materials",
        "title": "物料",
        "formalModel": "masterdata.Material",
        "sourceRecordCount": len(source_rows),
        "validSourceCount": sum(row["sourceValidity"] == "VALID" for row in source_rows),
        "formalRecordCount": len(formal_rows),
        "exactMatchCount": exact_count,
        "matchCount": match_count,
        "businessFingerprintMatchCount": match_count,
        "sourceCodeExactMatchCount": exact_count,
        "rekeyedCodeMatchCount": match_count - exact_count,
        "proposedMappingCount": match_count,
        "missingSourceCount": unmatched_count,
        "conflictCount": conflict_count,
        "testHistoricalCount": historical_count,
        "possibleRealOutsideSourceCount": sum(row["classification"] == "POSSIBLE_REAL_OUTSIDE_SOURCE" for row in formal_rows),
        "unknownOutsideSourceCount": sum(row["classification"] == "UNKNOWN_OUTSIDE_SOURCE" for row in formal_rows),
        "formalOutsideCurrentSourceCount": len(formal_rows) - match_count,
        "developed": True,
        "dataPresent": "PARTIAL" if match_count else "MISSING",
        "userValidated": False,
        "ready": "PARTIAL",
        "manualValidationReady": True,
        "sourceRows": compared,
        "formalRows": formal_rows,
        "referenceCatalogRows": snapshot["materialReferenceCatalogs"],
        "missingSourceRows": [row for row in compared if row["matchStatus"] in {"NO_MATCH", "INVALID_SOURCE", "USER_EXCLUDED_INCOMPLETE_SOURCE"}],
        "targetedRemediation": {
            "targetCount": len(targeted_rows),
            "passCount": sum(row["result"] == "PASS" for row in targeted_rows),
            "rows": targeted_rows,
            "excludedRows": [row for row in compared if row["matchStatus"] == "USER_EXCLUDED_INCOMPLETE_SOURCE"],
            "userValidated": "AWAITING_TARGETED_RECHECK",
            "productionBusinessWrite": 0,
        },
        "historicalSummary": [{"materialType": name, "count": count} for name, count in sorted(historical_types.items())],
        "historicalExamples": historical_examples,
        "representativeRows": representative_rows,
        "sourceFileGroups": [
            {"sourceFile": name, "rowCount": count}
            for name, count in sorted(Counter(row["sourceFile"] for row in compared).items())
        ],
    }


def _serialize_product(row):
    return {
        "id": row.pk,
        "formalCode": row.product_code,
        "formalName": row.product_name,
        "category": row.category.name if row.category_id else "",
        "definitionMode": row.manufacturing_definition_mode,
        "emdMaterialCode": row.emd_material_code,
        "status": row.status,
        "enabled": row.is_active,
    }


def _build_products(company_id, snapshot):
    categories = list(ProductCategory.objects.filter(company_id=company_id).order_by("code"))
    formal = list(
        ProductDefinition.objects.filter(company_id=company_id)
        .select_related("category")
        .order_by("product_code")
    )
    category_by_name = defaultdict(list)
    for row in categories:
        category_by_name[_norm(row.name)].append(row)

    category_rows = []
    normalization_groups = []
    for source in snapshot["productCandidates"]:
        source_lines = [
            row for row in snapshot["productOrderRows"]
            if row["sourceProductType"] == source["sourceProductName"]
        ]
        matches = category_by_name[_norm(source["sourceProductName"])]
        category_rows.append({
            "sourceCategory": source["sourceProductName"],
            "sourceRowCount": len(source_lines),
            "sourceRowNumbers": [row["sourceRow"] for row in source_lines],
            "proposedCategoryName": source["sourceProductName"],
            "formalMatch": {
                "id": matches[0].pk, "code": matches[0].code, "name": matches[0].name,
            } if len(matches) == 1 else None,
            "formalStatus": "PRESENT" if len(matches) == 1 else "MISSING",
            "semanticEvidence": "08列名为“产品类型”；工程拆单来源把“产品类别”与“产品名称”分列。",
            "needsUserConfirmation": "YES",
            "decisionNote": "用户已确认正式分类名称；饰面不得改名为木饰面。" if source["sourceProductName"] == "饰面" else "用户已确认正式分类名称。",
        })
        normalization_groups.append({
            "sourceCategory": source["sourceProductName"],
            "sourceRowCount": len(source_lines),
            "uniqueOrderCount": len({row["salesOrderNo"] for row in source_lines}),
            "uniqueSubOrderCount": len({row["salesOrderItemNo"] for row in source_lines}),
            "proposedCategoryCount": 1,
            "proposedProductDefinitionCount": 0,
            "proposedOrderEngineeredInstanceCount": len(source_lines),
            "unableToDetermineCount": len(source_lines),
        })

    order_engineered_rows = []
    for row in snapshot["productOrderRows"]:
        production_measures = [
            f"{name}={value}" for name, value in row.get("productionMeasureEvidence", {}).items()
            if _text(value) not in {"", "0", "0.0"}
        ]
        order_engineered_rows.append({
            **row,
            "rawProductName": row.get("sourceProductName") or "未提供",
            "productCategory": row["sourceProductType"],
            "specification": row.get("sourceSpecification") or "未提供",
            "dimensionsText": "未提供",
            "space": row.get("sourceSpace") or "未提供",
            "distinguishingFields": "；".join([
                f"子订单={row['salesOrderItemNo']}",
                f"半成品板材编码={row['sourceEngineeredMaterialCode']}",
                f"半成品编码={row['sourceEngineeredMaterialName']}",
                *production_measures,
            ]),
            "proposedFormalIdentity": f"OrderEngineeringInstance候选 / {row['salesOrderItemNo']}",
            "isUnique": "来源子订单号唯一；长期产品身份无法判定",
            "needsUserConfirmation": "YES",
            "boundaryDecision": "订单工程来源实例候选；不创建长期ProductDefinition",
            "formalWriteStatus": "PREVIEW ONLY / WRITE 0",
        })

    unable_to_determine_summary = []
    for group in normalization_groups:
        unable_to_determine_summary.append({
            "sourceCategory": group["sourceCategory"],
            "affectedRowCount": group["unableToDetermineCount"],
            "sourceRowNumbers": [
                row["sourceRow"] for row in snapshot["productOrderRows"]
                if row["sourceProductType"] == group["sourceCategory"]
            ],
            "missingIdentityFields": ["具体产品名称", "型号/规格", "高/宽/厚", "安装空间"],
            "reason": "08排产样例只提供产品类型与订单/生产数量上下文，不能据此确认长期产品身份。",
        })

    engineering_evidence = snapshot["engineeringIdentityEvidence"]

    formal_rows = [_serialize_product(row) for row in formal]
    version_count = ProductVersion.objects.filter(product__company_id=company_id).count()
    configuration_count = ProductConfiguration.objects.filter(template__company_id=company_id).count()
    configured_product_count = ConfiguredProduct.objects.filter(
        configuration__template__company_id=company_id
    ).count()
    order_engineering_count = OrderEngineeringInstance.objects.filter(company_id=company_id).count()
    return {
        "entity": "products",
        "title": "产品身份人工验收 Preview",
        "formalModel": "pde.ProductCategory + pde.ProductDefinition + pde.OrderEngineeringInstance",
        "sourceRecordCount": len(snapshot["productOrderRows"]),
        "distinctSourceCandidateCount": len(category_rows),
        "formalRecordCount": len(formal_rows),
        "exactMatchCount": 0,
        "proposedMappingCount": 0,
        "missingSourceCount": len(order_engineered_rows),
        "conflictCount": 0,
        "testHistoricalCount": 0,
        "formalOutsideCurrentSourceCount": len(formal_rows),
        "developed": True,
        "dataPresent": "PRESENT" if formal_rows else "MISSING",
        "userValidated": False,
        "ready": "MISSING",
        "manualValidationReady": True,
        "sourceRows": order_engineered_rows,
        "candidateRows": category_rows,
        "formalRows": formal_rows,
        "normalizationGroups": normalization_groups,
        "categoryPreviewRows": category_rows,
        "productDefinitionPreviewRows": [],
        "orderEngineeredPreviewRows": order_engineered_rows,
        "unableToDetermineRows": order_engineered_rows,
        "unableToDetermineSummaryRows": unable_to_determine_summary,
        "engineeringIdentityEvidence": {
            **engineering_evidence,
            "recordCount": len(engineering_evidence["rows"]),
            "exampleRows": engineering_evidence["rows"][:12],
        },
        "formalRealityRows": [
            {"object": "Product Category / Product Family", "formalModel": "pde.ProductCategory", "formalCount": len(categories), "status": "MISSING" if not categories else "PRESENT"},
            {"object": "ProductDefinition", "formalModel": "pde.ProductDefinition", "formalCount": len(formal_rows), "status": "MISSING" if not formal_rows else "PRESENT"},
            {"object": "Product Version", "formalModel": "pde.ProductVersion", "formalCount": version_count, "status": "MISSING" if not version_count else "PRESENT"},
            {"object": "Product Configuration", "formalModel": "pde.ProductConfiguration", "formalCount": configuration_count, "status": "MISSING" if not configuration_count else "PRESENT"},
            {"object": "ConfiguredProduct", "formalModel": "pde.ConfiguredProduct", "formalCount": configured_product_count, "status": "MISSING" if not configured_product_count else "PRESENT"},
            {"object": "OrderEngineeringInstance", "formalModel": "pde.OrderEngineeringInstance", "formalCount": order_engineering_count, "status": "MISSING" if not order_engineering_count else "PRESENT"},
        ],
        "productIdentityConclusion": "37条来源行归并为3个产品分类候选、0个可确认长期ProductDefinition、37个订单工程来源实例候选。",
        "identityGate": "PENDING USER CONFIRMATION",
    }


def _build_versions_configurations(company_id, snapshot):
    versions = list(ProductVersion.objects.filter(product__company_id=company_id).select_related("product"))
    configurations = list(ProductConfiguration.objects.filter(template__company_id=company_id).select_related("template"))
    templates = ProductTemplate.objects.filter(company_id=company_id).count()
    engineered_codes = sorted({
        row["sourceEngineeredMaterialCode"]
        for row in snapshot["productOrderRows"]
        if row["sourceEngineeredMaterialCode"]
    })
    version_readiness = []
    configuration_readiness = []
    for candidate in snapshot["productCandidates"]:
        name = candidate["sourceProductName"]
        source_lines = [row for row in snapshot["productOrderRows"] if row["sourceProductType"] == name]
        version_readiness.append({
            "productCandidate": name,
            "sourceRowCount": len(source_lines),
            "sourceRowNumbers": [row["sourceRow"] for row in source_lines],
            "sourceVersionFactPresent": False,
            "formalVersionRecordCount": 0,
            "initialVersionContainerRecommendation": "YES_AFTER_PRODUCT_ACCEPTANCE",
            "recommendation": "产品确认后建立受控初始版本容器；本轮不写入。",
            "realManufacturingFields": ["生效日期", "版本状态/发布状态", "变更原因或制造基线说明", "已批准BOM/工艺路线关联"],
            "systemGeneratedFields": ["内部ID", "创建/更新时间", "内容哈希/幂等标识", "按受控规则生成的初始版本号"],
        })
        configuration_readiness.append({
            "productCandidate": name,
            "sourceRowCount": len(source_lines),
            "currentSelection": "PENDING USER DECISION",
            "options": [],
            "blockedReason": "Product identity尚未通过人工确认，暂不选择配置方式。",
        })
    return {
        "entity": "product-versions-configurations",
        "title": "产品版本 / 产品配置",
        "formalModel": "pde.ProductVersion + pde.ProductConfiguration",
        "sourceRecordCount": len(snapshot["productOrderRows"]),
        "distinctSourceCandidateCount": len(snapshot["productCandidates"]),
        "engineeredMaterialCodeCount": len(engineered_codes),
        "engineeredMaterialCodes": engineered_codes,
        "productVersion": {
            "developed": True,
            "formalModel": "pde.ProductVersion",
            "formalRecordCount": len(versions),
            "dataPresent": "PRESENT" if versions else "MISSING",
            "userValidated": False,
            "ready": "MISSING",
            "status": "MISSING — 等待产品定义与版本来源人工确认",
        },
        "productConfiguration": {
            "developed": True,
            "formalModel": "pde.ProductTemplate + pde.ProductConfiguration",
            "templateRecordCount": templates,
            "formalRecordCount": len(configurations),
            "dataPresent": "PRESENT" if configurations else "MISSING",
            "userValidated": False,
            "ready": "MISSING",
            "status": "MISSING — Product identity确认前保持PENDING USER DECISION",
        },
        "sourceRows": snapshot["productCandidates"],
        "versionReadinessRows": version_readiness,
        "configurationReadinessRows": configuration_readiness,
        "manualValidationReady": True,
    }


def build_group2_comparison(entity, company_id):
    if entity not in SUPPORTED_ENTITIES:
        raise KeyError(entity)
    snapshot = _snapshot()
    if entity == "materials":
        payload = _build_materials(company_id, snapshot)
    elif entity == "products":
        payload = _build_products(company_id, snapshot)
    else:
        payload = _build_versions_configurations(company_id, snapshot)
    return {
        "factLoadStatus": "success",
        "comparisonVersion": snapshot["version"],
        "readOnly": True,
        "productionBusinessWriteCount": 0,
        "dataProvenance": snapshot["generatedFrom"],
        "sourceSummary": snapshot["summary"],
        **payload,
    }
