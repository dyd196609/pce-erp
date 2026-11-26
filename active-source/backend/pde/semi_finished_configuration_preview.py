"""Read-only projection of source configuration evidence onto canonical PCE facts.

This is a subview of EngineeringCalculationReadinessService, not a Material model,
resolver, rule engine, or persistence service. Identity matches do not approve a
composition relationship or make a business calculation executable.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

SOURCE_PATH = Path(__file__).with_name("semi_finished_configuration_source.json")
SOURCE_SHA = "6A2D7A5D8E2DAA04E212DEFFD1C37F771D7CDDA806DFCF8105E373D9C72985E6"
VERSION = "PCE-SEMI-FINISHED-CONFIGURATION-PREVIEW-1"
ATTRIBUTES = (
    ("paintProcess", "油漆工艺名称", "油漆工艺"), ("color", "颜色/色板号", "颜色 / 色板"),
    ("veneer", "木皮种类", "木皮"), ("substrate", "坯板材质", "坯板材质"),
    ("splice", "是否拼皮", "是否拼皮"), ("skinFeel", "是否肤感", "是否肤感"),
    ("paintKind", "油漆种类", "油漆种类"), ("uom", "单位", "半成品基本单位"),
)
UNKNOWN_VALUES = (None, "", "待定", "待确认色版", "客供色版", "无色版1")


def value(row, field):
    return row.get("fields", {}).get(field, {}).get("value")


def cell_value(row, col):
    return row["cells"].get(f"{col}{row['row']}", {}).get("value")


def material_identity(material):
    return {k: material.get(k) for k in ("id", "code", "name", "material_type", "specification", "unit", "unit_status", "base_uom_id", "is_active", "company_id")}


def resolve_code(code, file, sheet, source_sha, formal):
    """No fuzzy, ordinal, name, or dimension matching. Reject ambiguous targets."""
    materials = {str(r["id"]): r for r in formal["materials"] if r["is_active"]}
    direct = [r for r in materials.values() if r["code"] == str(code)]
    expected = f"{file}|{sheet}|CODE:{code}"
    mapped, evidence = [], []
    for identity in formal["identities"]:
        if identity["target_entity_type"] != "materials":
            continue
        meta = identity.get("audit_metadata") or {}
        if isinstance(meta, str):
            meta = json.loads(meta)
        if identity["external_id"] != expected:
            continue
        if identity["mapping_status"] == "BLOCK" and meta.get("decisionStatus") == "USER_EXCLUDED_INCOMPLETE_SOURCE":
            return {"status": "UNRESOLVED", "method": "USER_EXCLUDED", "formal": None, "excludedByUser": True,
                    "evidence": [{"id": identity["id"], "externalId": expected, "decisionStatus": meta["decisionStatus"]}],
                    "reason": "既有人工作废/排除的不完整来源；保留证据，不重开导入、不作为新缺失物料要求补建"}
        if identity["mapping_status"] != "MATCH":
            continue
        if str(meta.get("sourceCode")) != str(code) or str(meta.get("sourceSha256", "")).upper() != source_sha:
            continue
        evidence.append({"id": identity["id"], "externalId": expected, "sourceSha256": source_sha, "targetId": identity["target_entity_id"]})
        if str(identity["target_entity_id"]) in materials:
            mapped.append(materials[str(identity["target_entity_id"])])
    unique = {r["id"]: r for r in direct + mapped}
    if len(unique) != 1:
        return {"status": "UNRESOLVED", "method": "UNRESOLVED", "formal": None, "evidence": evidence,
                "reason": "正式身份冲突" if len(unique) > 1 else "未找到有效正式编码或同SHA的已登记来源身份；未使用模糊名称/序号匹配"}
    matched = next(iter(unique.values()))
    return {"status": "MATCHED", "method": "EXACT" if direct else "EXTERNAL_IDENTITY", "formal": material_identity(matched),
            "evidence": evidence, "reason": "正式编码精确匹配" if direct else "来源编码通过已登记ExternalIdentity关联现有Material；没有创建新物料"}


def source_matches(source, key, field, source_value):
    if source_value in UNKNOWN_VALUES:
        return []
    return [{"fileSheet": key, "row": r["row"], "cell": r["fields"][field]["cell"], "value": source_value}
            for r in source["catalogs"].get(key, []) if value(r, field) == source_value]


def attribute_projection(source, formal, row, kind, field, label, source_shas):
    raw = value(row, field)
    result = {"key": kind, "label": label, "sourceValue": raw, "sourceFile": row["file"], "sourceSheet": row["sheet"],
              "sourceCell": row["fields"][field]["cell"], "sourceStatus": "MISSING" if raw in UNKNOWN_VALUES else "PRESENT",
              "formalStatus": "UNRESOLVED", "formalTargets": [], "sourceTrace": [], "relationshipStatus": "NOT_FORMALIZED",
              "provenance": "SOURCE → PREVIEW; formal targets are live reads", "note": "缺少来源值或正式关联；不填默认值"}
    if kind == "paintProcess" and raw not in UNKNOWN_VALUES:
        dep = [r for r in source["dependencies"]["油漆工艺及编码"] if value(r, "油漆工艺") == raw]
        codes = {value(r, "工艺编码") for r in dep if value(r, "工艺编码")}
        result["sourceTrace"] = [{"fileSheet": "工程拆单及订单排产数据核算方式.xlsx|油漆工艺及编码", "row": r["row"], "code": value(r, "工艺编码"), "value": raw} for r in dep]
        target = [r for r in formal["processTypes"] if r["code"] in codes and r["is_active"]]
        if len(codes) == 1 and len(target) == 1:
            result.update(formalStatus="MATCHED", formalTargets=[{"model": "pde.ManufacturingProcessType", **{k: target[0][k] for k in ("id", "code", "name")}}],
                          note="依来源工艺目录明确代码关联正式工艺类型；名称差异保留。不是system.Process，不推导执行路线")
    elif kind in ("color", "veneer", "substrate"):
        catalog, column, dependency, dep_column = {
            "color": ("04色板.xlsx|颜色板号目录", "颜色/板号名称", "颜色板号目录", "颜色/板号名称(必填)"),
            "veneer": ("12木皮.xlsx|木皮", "木皮目录", "木皮目录（设计）", "木皮目录"),
            "substrate": ("13坯板.xlsx|坯板", "坯板目录", "坯板目录（设计）", "坯板目录"),
        }[kind]
        result["sourceTrace"] = source_matches(source, catalog, column, raw)
        result["dependencyTrace"] = [{"sheet": dependency, "row": r["row"], "cell": r["fields"][dep_column]["cell"], "value": raw}
                                     for r in source["dependencies"][dependency] if raw not in UNKNOWN_VALUES and value(r, dep_column) == raw]
        if (kind == "veneer" and raw == "无木皮") or (kind == "color" and raw == "无色版"):
            result.update(formalStatus="NOT_APPLICABLE", relationshipStatus="SOURCE_EXPLICIT_NONE", note="来源明确为无；不创建虚拟物料/色板。此项不等于整套配置完整")
        elif kind == "substrate":
            family = [r for r in formal["categories"] if r["name"] == raw and r["is_active"]]
            if len(family) == 1:
                result.update(formalStatus="MATCHED", formalTargets=[{"model": "masterdata.MaterialCategory", **family[0]}])
            result["note"] = "来源坯板目录明确材质家族，但不等于采购规格；未按板材品类或几何跨材质选板" if result["sourceTrace"] else "来源材质未填写或待定；没有可确认的材料家族，不按几何推断"
        elif kind == "veneer" and raw not in UNKNOWN_VALUES:
            # Attribute values are explicit catalogue names, unlike material-code identity.
            # Only exact names in the purchase source are admissible, followed by formal code identity.
            purchased = [r for r in source["catalogs"]["10采购物料.xlsx|采购物料"] if value(r, "物料名称") == raw]
            resolutions = [resolve_code(value(p, "物料编码"), "10采购物料.xlsx", "采购物料", source_shas["10采购物料.xlsx"], formal) for p in purchased]
            result["purchaseSourceTrace"] = [{"row": p["row"], "code": value(p, "物料编码"), "name": value(p, "物料名称")} for p in purchased]
            result["formalTargets"] = [{"model": "masterdata.Material", **r["formal"]} for r in resolutions if r["status"] == "MATCHED"]
            if len(purchased) == 1 and len(result["formalTargets"]) == 1:
                result["formalStatus"] = "MATCHED"
            result["note"] = "仅按显式木皮名称精确追采购来源，再经正式来源编码关联；相似黑胡桃名称不互换。已匹配目标也尚未建立半成品组成关系"
        elif kind == "color":
            result["note"] = "来源色板目录与正式颜色身份分开；当前无正式色板身份/Material颜色关联，不从色号推断漆料"
        else:
            result["note"] = "来源木皮未填写或待定；没有可确认的采购木皮身份，不补默认值"
    elif kind in ("splice", "skinFeel"):
        result["note"] = "来源值原样保留；当前Material无对应受控属性。不得根据木皮名称猜是/否或自动改变Routing/产能"
    elif kind == "paintKind":
        result["note"] = "05全部未填；设计目录底漆/色漆/面漆/色精须逐项追溯，不由色号或工艺名反推漆料"
    elif kind == "uom":
        result["note"] = "半成品基本单位不是工程行计数单位；块/支/m²不能自动回填Material基本单位"
    return result


def build_projection(source, formal, company_id):
    if source["organizationId"] != company_id:
        raise ValueError("SOURCE_ORGANIZATION_MISMATCH")
    formal = {k: [r for r in rows if r.get("organization_id" if k == "identities" else "company_id") == company_id] for k, rows in formal.items()}
    source_shas = {r["file"]: r["sha256"] for r in source["sourceFiles"]}
    configs, attrs, compositions, identity_map = [], [], [], []
    referenced = Counter(cell_value(r, "B") for r in source["realRows"])
    for row in source["sourceRows"]:
        code = value(row, "半成品板材编码")
        result = resolve_code(code, row["file"], row["sheet"], row["sha256"], formal)
        raw_attrs = {field: value(row, field) for _, field, _ in ATTRIBUTES}
        group = hashlib.sha256(json.dumps([code, raw_attrs], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        engineering = [r for r in source["realRows"] if cell_value(r, "B") == code]
        roles = sorted({str(cell_value(r, "G" if r["sheet"] == "三合一生产单" else "H") or "来源未提供") for r in engineering})
        categories = sorted({str(cell_value(r, "E")) for r in engineering if cell_value(r, "E")})
        fields = [attribute_projection(source, formal, row, *item, source_shas) for item in ATTRIBUTES]
        if result["formal"]:
            formal_uom = [u for u in formal["uoms"] if u["id"] == result["formal"]["base_uom_id"] and u["is_active"]]
            if len(formal_uom) == 1:
                u = formal_uom[0]
                unit_field = next(a for a in fields if a["key"] == "uom")
                unit_field.update(formalStatus="MATCHED", formalTargets=[{"model": "masterdata.UnitOfMeasure", **{k: u[k] for k in ("id", "code", "name", "symbol")}}],
                                  relationshipStatus="EXISTING_FORMAL_LINK", note="05来源单位为空，但现有Material.base_uom正式关联已存在；保留既有人工作业结果，不用工程行单位覆盖，不重新要求单位裁决")
        for a in fields:
            a.update(sourceCode=code, groupId=group)
        attrs.extend(fields)
        design = [r for r in source["dependencies"]["物料目录(设计)"] if value(r, "物料编码(必填)") == code]
        attribute_conflicts = []
        if len(design) == 1:
            keys = {"油漆工艺名称": "油漆工艺(必填)", "颜色/色板号": "颜色/色板号(必填)", "木皮种类": "木皮种类", "坯板材质": "坯板材质", "是否拼皮": "是否拼皮", "是否肤感": "是否肤感"}
            for lhs, rhs in keys.items():
                if value(row, lhs) != value(design[0], rhs):
                    attribute_conflicts.append({"field": lhs, "source05": value(row, lhs), "engineeringCatalog": value(design[0], rhs), "policy": "DO_NOT_OVERWRITE_SOURCE05"})
        config = {"groupId": group, "sourceCode": code, "name": value(row, "半成品板材名称"), "sourceRow": row["row"], "sourceFile": row["file"],
                  "identity": result, "attributes": fields, "sourceState": "PLACEHOLDER" if value(row, "坯板材质") in UNKNOWN_VALUES else "PRESENT",
                  "structureRoles": roles, "productCategories": categories, "realRowCount": len(engineering), "sourceReferenceCount": referenced[code],
                  "engineeringRows": [{"sheet": r["sheet"], "row": r["row"], "role": cell_value(r, "G" if r["sheet"] == "三合一生产单" else "H"),
                                       "productCategory": cell_value(r, "E"), "space": cell_value(r, "F"), "model": cell_value(r, "H") if r["sheet"] == "三合一生产单" else None,
                                       "dimensionText": " / ".join(f"{label} {cell_value(r, col)}" for label, col in (("高", "J"), ("宽", "K"), ("厚", "L"))) if r["sheet"] == "三合一生产单" else " / ".join(f"{label} {cell_value(r, col)}" for label, col in (("洞高", "J"), ("洞宽", "K"), ("墙厚", "L"))),
                                       "quantityLabel": "数量" if r["sheet"] == "三合一生产单" else "门洞数量",
                                       "length": cell_value(r, "J"), "width": cell_value(r, "K"), "thickness": cell_value(r, "L") if r["sheet"] == "三合一生产单" else None,
                                       "quantity": cell_value(r, "M"), "rowUom": cell_value(r, "N") if r["sheet"] == "三合一生产单" else cell_value(r, "V"),
                                       "visibleSides": cell_value(r, "O") if r["sheet"] == "三合一生产单" else None,
                                       "edgeMode": cell_value(r, "P") if r["sheet"] == "三合一生产单" else None} for r in engineering],
                  "designCatalogRows": [r["row"] for r in design], "attributeConflicts": attribute_conflicts,
                  "paintInputs": [{"field": f, "value": value(d, f), "sourceCell": d["fields"][f]["cell"]} for d in design for f in ("底漆名称", "色漆名称", "面漆名称", "色精名称") if f in d["fields"]],
                  "businessCalculable": False, "compositionFormalized": False, "userValidated": False,
                  "missingRelations": [f["label"] for f in fields if f["formalStatus"] == "UNRESOLVED"],
                  "dataProvenance": ["SOURCE", "FORMAL_IDENTITY_LOOKUP", "PREVIEW"], "composition": []}
        for key, label, basis in (("substrate", "坯板", "产品平方＋已确认的层结构"), ("veneer", "木皮", "共享见光面积"),
                                  ("edge", "封边材料", "净边长＋每边余量（m）"), ("paintKind", "油漆 / 表面材料", "共享见光面积；本轮不计算漆量"),
                                  ("color", "色板 / 特殊饰面身份", "配置约束；不是自动消耗物料")):
            a = next((f for f in fields if f["key"] == key), None)
            component = {"sourceCode": code, "role": label, "sourceValue": a["sourceValue"] if a else None,
                         "formalTargets": a["formalTargets"] if a else [], "status": a["formalStatus"] if a else "UNRESOLVED",
                         "compositionKind": "CONFIGURATION_CONSTRAINT" if key == "color" else "FIXED_COMPOSITION_CANDIDATE",
                         "quantityKind": "CALCULATED_REQUIREMENT_PENDING" if key != "color" else "NOT_APPLICABLE",
                         "quantity": None, "basis": basis, "formalRelationship": False,
                         "note": "固定材料身份与计算数量分开；人工、临时和客户特殊需求保留独立通道"}
            config["composition"].append(component)
            compositions.append(component)
        configs.append(config)
    by_code = {}
    for c in configs:
        by_code.setdefault(c["sourceCode"], []).append(c)
    for r in source["realRows"]:
        code = cell_value(r, "B")
        matches = by_code.get(code, [])
        color_col = "V" if r["sheet"] == "三合一生产单" else "AD"
        color = cell_value(r, color_col)
        dependency = [d for d in source["dependencies"]["物料目录(设计)"] if value(d, "颜色/色板号(必填)") == color]
        proof = len(dependency) == 1 and value(dependency[0], "物料编码(必填)") == code
        identity_map.append({"sheet": r["sheet"], "row": r["row"], "sourceCode": code, "sourceCell": f"B{r['row']}",
                             "sourceFormula": r["cells"][f"B{r['row']}"]["formula"], "lookupColorValue": color,
                             "dependencyRows": [d["row"] for d in dependency], "lookupConsistency": "EXACT" if proof else "UNRESOLVED",
                             "source05Method": "EXACT" if len(matches) == 1 and proof else "UNRESOLVED",
                             "source05Rows": [c["sourceRow"] for c in matches], "aliasHistoricalEvidence": [],
                             "formal": matches[0]["identity"] if len(matches) == 1 and proof else None,
                             "status": "MATCHED" if len(matches) == 1 and proof else "UNRESOLVED"})
    thickness = []
    for r in source["realRows"]:
        if r["sheet"] != "三合一生产单":
            continue
        thickness.append({"sheet": r["sheet"], "row": r["row"], "cell": f"L{r['row']}", "sourceCode": cell_value(r, "B"),
                          "sourceThickness": cell_value(r, "L"), "sourceHeader": "厚", "structuralRole": cell_value(r, "G") or cell_value(r, "H"),
                          "context": "ENGINEERING_COMPONENT_INSTANCE", "semantic": "UNKNOWN", "rawBoardExactMatchAllowed": False,
                          "reason": "原表仅标厚；05/设计物料目录给出材质与木皮，未给层数、原板厚、加工余量或完成厚度定义，不能证明RAW/FINISHED/COMPOSITE",
                          "layerReconciliation": "UNRESOLVED", "nearestThicknessUsed": False})
    active = [c for c in configs if c["realRowCount"]]
    gaps = []
    for c in active:
        issues = ["确认坯板层结构、厚度语义及材料家族→采购材料的正式约束", "确认木皮采购身份（不得按相似名称替换）",
                  "确认封边材料/规格及每边余量；未知边和见光条件仍需工程输入", "确认缺失油漆材料/基本单位及适用损耗政策"]
        issues[-1] = "确认缺失油漆材料及适用损耗政策；既有正式基本单位保持不变"
        if any(a["sourceValue"] is None for a in c["attributes"] if a["key"] in ("splice", "skinFeel")):
            issues.append("是否拼皮/肤感为空，需一次性配置确认；不得从名称推定")
        color = next(a for a in c["attributes"] if a["key"] == "color")
        if not color["sourceTrace"]:
            issues.append("色板未在04精确命中，需确认受控色板身份")
        gaps.append({"id": f"U03-CONFIG-{c['sourceCode']}", "kind": "U03", "scope": "ONE_CONFIGURATION_NOT_EACH_ROW",
                     "sourceCode": c["sourceCode"], "affectedRows": c["realRowCount"], "issues": issues,
                     "sourceExhaustion": [r["file"] for r in source["sourceFiles"]] + list(source["dependencies"]),
                     "status": "USER_DECISION_REQUIRED", "note": "先确认配置事实，再授权正式关联；本轮不自动写入"})
    trace_counts = {kind: {"sourcePresent": sum(a["sourceStatus"] == "PRESENT" for a in attrs if a["key"] == kind),
                           "sourceCatalogExact": sum(bool(a["sourceTrace"]) for a in attrs if a["key"] == kind),
                           "formalMatched": sum(a["formalStatus"] == "MATCHED" for a in attrs if a["key"] == kind),
                           "notApplicable": sum(a["formalStatus"] == "NOT_APPLICABLE" for a in attrs if a["key"] == kind)} for kind, _, _ in ATTRIBUTES}
    summary = {"source05Count": len(configs), "formal05Matched": sum(c["identity"]["status"] == "MATCHED" for c in configs),
               "realRowCount": len(identity_map), "threeInOneCount": sum(r["sheet"] == "三合一生产单" for r in identity_map),
               "threeInOneMapped": sum(r["sheet"] == "三合一生产单" and r["status"] == "MATCHED" for r in identity_map),
               "allRealMapped": sum(r["status"] == "MATCHED" for r in identity_map), "sourceConfigurationCount": len({c["groupId"] for c in configs}),
               "activeConfigurationCount": len(active), "threeInOneConfigurationCount": len({r["sourceCode"] for r in identity_map if r["sheet"] == "三合一生产单"}),
               "userExcludedSourceCount": sum(bool(c["identity"].get("excludedByUser")) for c in configs),
               "attributeConflictCount": sum(len(c["attributeConflicts"]) for c in configs),
               "previewFormalizedCompositionCount": sum(c["compositionFormalized"] for c in configs),
               "userDecisionGroupCount": len(gaps), "thicknessSemantics": "UNKNOWN", "thicknessCounts": dict(Counter(str(r["sourceThickness"]) for r in thickness)),
               "traceCounts": trace_counts, "businessCalculableCount": 0, "productionBusinessWrite": 0,
               "nativeGap": 0, "technicalFormulaDifference": 0, "nativeStatusSource": "USER_FROZEN_NATIVE_R5_NOT_RERUN"}
    return {"version": VERSION, "runtimeModelType": "EngineeringCalculationReadinessPreview", "runtimeAdapterCode": "EngineeringCalculationReadinessService",
            "moduleId": "engineering-calculation", "subview": "semi-finished-structure", "summary": summary, "sourceFiles": source["sourceFiles"],
            "configurations": configs, "identityMap": identity_map, "attributeTrace": attrs, "compositionTrace": compositions,
            "thicknessAnalysis": thickness, "gaps": gaps, "outsideFrozenScope": deepcopy(source["outsideFrozenScope"]),
            "boundaries": {"domainRuleFormalization": "NOT_ENTERED", "stockResolver": "DEFERRED_UNTIL_CONFIG_IDENTITY", "legacy36": "TECHNICAL_REFERENCE_ONLY",
                           "source08": "DERIVED_REFERENCE_ONLY_NOT_USED", "bomStructuralReference": True, "bomNumericAuthority": False,
                           "bomFormulaAuthority": False, "userValidated": False, "productionBusinessWrite": 0}}


def load_frozen_source_snapshot():
    """Read the registered immutable snapshot for explicit historical display.

    This proves the snapshot bytes, not that the original files are currently
    available or that a new calculation may execute against them.
    """
    raw = SOURCE_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest().upper() != SOURCE_SHA:
        raise ValueError("CONFIGURATION_SOURCE_INTEGRITY_FAILED")
    source = json.loads(raw)
    if source.get("schemaVersion") != "PCE-SEMI-FINISHED-CONFIGURATION-SOURCE-1":
        raise ValueError("CONFIGURATION_SOURCE_SCHEMA_MISMATCH")
    return source


def load_source():
    """New use of the original source still requires every registered file."""
    source = load_frozen_source_snapshot()
    for item in source["sourceFiles"]:
        if hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest().upper() != item["sha256"]:
            raise ValueError("CONFIGURATION_ORIGINAL_SOURCE_CHANGED")
    return source


def build_for_user(user):
    from django.db import connection
    from masterdata.models import Material, MaterialCategory, ExternalIdentity, UnitOfMeasure
    from .models import ManufacturingProcessType
    from .engineering_calculation_service import EngineeringCalculationService
    EngineeringCalculationService._authorize(user=user, action_code="production.engineering.calculation.view", company_id=user.company_id)
    # This read-only preview must be re-bound after any future production schema
    # deployment; never keep reporting the current zero as a permanent constant.
    if "pde_material_configuration" in connection.introspection.table_names():
        raise ValueError("PRODUCTION_CONFIGURATION_SCHEMA_CHANGED_RECHECK_REQUIRED")
    formal = {
        "materials": list(Material.objects.filter(company_id=user.company_id).values()),
        "categories": list(MaterialCategory.objects.filter(company_id=user.company_id).values()),
        "identities": list(ExternalIdentity.objects.filter(organization_id=user.company_id).values()),
        "processTypes": list(ManufacturingProcessType.objects.filter(company_id=user.company_id).values("id", "code", "name", "company_id", "is_active")),
        "uoms": list(UnitOfMeasure.objects.filter(company_id=user.company_id).values()),
    }
    from .semi_finished_configuration_validation import apply_validation
    from .room_door_edge_preview import apply_room_door
    return apply_room_door(apply_validation(build_projection(load_source(), formal, user.company_id), formal=formal))
