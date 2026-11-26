"""Read-only user adjudication and sealed isolated evidence. No ORM writes.

This projection is not a production configuration carrier. The canonical schema
candidate is isolated and has not been applied to the production database.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

EVIDENCE_PATH = Path(__file__).resolve().parents[2] / "docs/evidence/semi_finished_role_layer_20260909/ISOLATED_REPLAY.json"
EVIDENCE_SHA = "22C97C1D68267A53304050A927673C486D7006179D5F7B9FBA6636E2E352AD80"
DECISION_SHA = "894230DC5BB2D05BFB28E99C731CEC9FD877EFA985E275FEBED7B483052B32FA"
BLOCKER_LABELS = {
    "PROCUREMENT_MATERIAL_IDENTITY_UNRESOLVED": "采购物料身份未唯一确定",
    "MATERIAL_QUANTITY_RULE_NOT_BOUND": "材料数量规则尚未绑定",
    "ALLOWED_MATERIAL_SPECIFICATION_SET_UNRESOLVED": "材料族允许采购物料及规格尚未确认",
    "THICKNESS_SEMANTIC_UNKNOWN": "厚度语义未知",
    "QUANTITY_MODE_UNKNOWN": "数量方式尚未确定",
    "MANUAL_QUANTITY_PENDING": "工程人工数量待提供",
    "ALLOWED_FAMILY_MEMBERS_UNRESOLVED": "实木多层板的允许采购成员尚未确定",
    "PROCUREMENT_MATERIAL_MASTER_DATA_GAP": "当前采购来源及正式规格缺少该精确厚度",
    "EDGE_MATERIAL_IDENTITY_UNRESOLVED": "封边条材质、宽厚、颜色与正式物料尚未确定",
    "PER_EDGE_ALLOWANCE_PENDING": "每边预留长度尚未提供（不是0）",
    "RULE_NOT_RELEASED": "数量规则尚未发布",
}


def formal_fingerprint(formal):
    """Hash only read-authoritative fields, normalized across SQLite and Django."""
    fields={
        "materials":("id","code","name","specification","company_id","category_id","base_uom_id","is_active","is_purchased","material_type"),
        "categories":("id","code","name","company_id","is_active"),
        "identities":("id","organization_id","external_id","target_entity_type","target_entity_id","mapping_status","source_object_type","source_fingerprint"),
        "processTypes":("id","code","name","company_id","is_active"),
        "uoms":("id","code","name","company_id","dimension","is_active"),
    }
    data={k:[{f:bool(row.get(f)) if f in {"is_active","is_purchased"} else row.get(f) for f in keys}
        for row in sorted(formal[k],key=lambda r:r["id"])] for k,keys in fields.items()}
    return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest().upper()


def load_evidence():
    raw = EVIDENCE_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest().upper() != EVIDENCE_SHA:
        raise ValueError("ISOLATED_CONFIGURATION_EVIDENCE_INTEGRITY_FAILED")
    data = json.loads(raw)
    if data.get("scope") != "ISOLATED_REPLAY_NOT_PRODUCTION" or data.get("schemaVersion") != "PCE-MATERIAL-ROLE-LAYER-ISOLATED-1":
        raise ValueError("ISOLATED_CONFIGURATION_EVIDENCE_SCHEMA_FAILED")
    if not data.get("userDecision", "").endswith(DECISION_SHA):
        raise ValueError("USER_CONFIGURATION_DECISION_IDENTITY_FAILED")
    return data


def apply_validation(projection, evidence=None, formal=None):
    data = deepcopy(projection)
    evidence = load_evidence() if evidence is None else deepcopy(evidence)
    if formal is not None and formal_fingerprint(formal) != evidence.get("formalInputFingerprint"):
        raise ValueError("MATERIAL_ROLE_PREVIEW_FORMAL_INPUT_DRIFT")
    cases = {r["configurationCode"]: r for r in evidence["cases"]}
    if set(cases) != {"BTKF2601001", "QSFB4601001"}:
        raise ValueError("ISOLATED_CONFIGURATION_SCOPE_FAILED")
    for config in data["configurations"]:
        case = cases.get(config["sourceCode"])
        config["userValidated"] = case is not None
        config["userValidationLabel"] = "来源配置已人工确认（冻结）" if case else "尚未人工验收"
        config["layerUserValidationLabel"] = "新层级页面待人工验收"
        config["roleLayerUserValidated"] = False
        # Historical pure source projection remains audit-compatible, while the
        # current live projection never places edge requirements inside a config.
        config["composition"] = [r for r in config["composition"] if r["role"] in {"坯板","木皮","油漆 / 表面材料"}]
        for role in config["composition"]:
            role["owner"]="MATERIAL_CONFIGURATION"
            role["quantityMode"]="CALCULATED"
            role["ruleReadiness"]="PENDING"
            if role["role"]=="坯板":role["basis"]="三合一L列厚度精确匹配＋工程几何；不近似替换"
        for field in config["attributes"]:
            field["formalStatusLabel"] = {"MATCHED": "生产身份已匹配", "UNRESOLVED": "生产身份待解析", "NOT_APPLICABLE": "不适用"}[field["formalStatus"]]
            field["sourceValidated"] = case is not None
            field["sourceValidationLabel"] = "来源已确认" if case else "未人工确认"
            field["canonicalValue"] = field["sourceValue"]
            field["knowledgeLabel"] = None
        if not case:
            continue
        formal = config["identity"].get("formal") or {}
        if config["identity"]["status"] != "MATCHED" or formal.get("id") != case["formalMaterialId"] or config["realRowCount"] != case["inheritedRows"]:
            raise ValueError("ISOLATED_CONFIGURATION_LIVE_IDENTITY_DRIFT")
        attributes = {a["attribute_kind"]: a for a in case["canonicalConfiguration"]["attributes"]}
        for field in config["attributes"]:
            isolated = attributes[field["key"]]
            if isolated["source_value"] != field["sourceValue"]:
                raise ValueError("ISOLATED_CONFIGURATION_SOURCE_ATTRIBUTE_DRIFT")
            field["canonicalValue"] = isolated["canonical_value"]
            if field["key"] in {"splice", "skinFeel"}:
                field["knowledgeLabel"] = {"UNKNOWN": "未知（保持来源）", "KNOWN_FALSE": "否（来源已确认）", "KNOWN_TRUE": "是（来源已确认）", "NOT_APPLICABLE": "不适用"}[isolated["knowledge_state"]]
                field["note"] = "此状态已获用户确认；不根据名称或相似产品推断，不改变工艺路线。"
            elif field["key"] == "paintProcess" and config["sourceCode"] == "BTKF2601001":
                field["note"] = "用户已确认标准语义为半透开放工艺；保留来源半透工艺，复用现有正式工艺类型半透开放。"
            elif field["key"] in {"color", "veneer", "substrate"}:
                field["note"] = "来源业务关系已人工确认；不等于生产采购Material身份或允许采购规格已确定。"
        config["isolatedReplay"] = deepcopy(case)
        for role in config["isolatedReplay"]["roles"]:
            role["statusLabel"] = "用量生成已阻断"
            role["blockerLabels"] = [BLOCKER_LABELS.get(k, "前置业务事实尚未满足") for k in role["blockers"]]
            role["roleStatusLabel"]="角色已人工确认"
            role["ruleReadinessLabel"]="规则待定义/发布"
        code=config["sourceCode"]
        config["layerPreview"]={"components":[r for r in evidence["components"] if r["configurationCode"]==code],
            "boardRows":[r for r in evidence["boardPreview"]["rows"] if r["configurationCode"]==code],
            "veneerRows":[r for r in evidence["veneerPreview"]["rows"] if r["configurationCode"]==code],
            "veneerSummary":evidence["veneerPreview"]["summary"]["byConfiguration"][code],
            "edgeRows":[r for r in evidence["edgeRequirements"] if r["configurationCode"]==code]}
        for row in config["layerPreview"]["boardRows"]+config["layerPreview"]["edgeRows"]:
            row["blockerLabels"]=[BLOCKER_LABELS.get(k,"前置业务事实尚未满足") for k in row["blockers"]]
        for row in config["layerPreview"]["veneerRows"]:
            row["netStatusLabel"]="净面积可计算" if row["netStatus"]=="PASS" else "缺少见光条件；净面积未知"
        config["productionConfigurationLabel"] = "生产配置关系尚未部署；隔离回放已完成"
    for gap in data["gaps"]:
        if gap["sourceCode"] in cases:
            gap.update(status="KNOWN_BUSINESS_GAPS_PRESERVED", decisionRequiredNow=False,
                issues=["来源配置关系已人工确认，不重新要求逐行选料或确认拼皮/肤感。",
                        "木皮采购身份、受控色板身份及材料族允许采购成员仍未唯一解析。",
                        "三合一L列厚度已确认；32行在当前采购目录没有精确厚度，材料族允许成员关系仍未确定。不近似替换。",
                        "材料数量规则、油漆材料、损耗参数未发布；本轮不生成用量。"],
                note="既有U03来源身份裁决已完成；余下业务缺口显式保留，不为隔离技术验证补造事实。")
    data["summary"].update(userValidatedConfigurationCount=sum(c["userValidated"] for c in data["configurations"]),
        otherValidNotUserValidatedCount=56, isolatedConfigurationCount=2, isolatedRoleCount=6,
        isolatedInheritedRowCount=71, currentSampleUserValidation=True,
        isolatedMigrationStatus="PASS", isolatedBusinessCalculationStatus="BLOCKED",
        productionConfigurationCount=0, productionMigrationApplied=False, userDecisionGroupCount=0,
        thicknessSemantics="BOARD_MATCH_INPUT_COLUMN_L",layerUserManualValidation="PENDING")
    data["compositionTrace"]=[r for c in data["configurations"] for r in c["composition"]]
    data["attributeTrace"]=[r for c in data["configurations"] for r in c["attributes"]]
    for row in data["thicknessAnalysis"]:
        row.update(semantic="BOARD_MATCH_INPUT",rawBoardExactMatchAllowed=True,
            reason="用户明确裁决：三合一L列作为板材匹配厚度输入；禁止最近厚度替换",userDecisionSha256=DECISION_SHA,
            layerReconciliation="NOT_REQUIRED_FOR_CURRENT_EXACT_THICKNESS_INPUT")
    data["roleLayerSummary"]={"configurationRoleCount":6,"sourceComponentCount":len(evidence["components"]),
        "pendingEdgeRequirementCount":len(evidence["edgeRequirements"]),"board":evidence["boardPreview"]["summary"],
        "veneer":evidence["veneerPreview"]["summary"],"edge":evidence["edgeSummary"],
        "userManualValidation":"PENDING","userManualValidationLabel":"新层级待您人工验收", "actualConsumptionGenerated":0}
    data["structureAuthority"]=evidence["structureAuthority"]
    # Existing service publishes summary unchanged to API/page/strict/diagnostic facts.
    # Keep the new layer counts in that same server-owned contract.
    data["summary"].update(sourceComponentCount=len(evidence["components"]),
        pendingEdgeRequirementCount=len(evidence["edgeRequirements"]),
        boardExactThicknessMatch=evidence["boardPreview"]["summary"]["exactThicknessMatch"],
        boardExactMatch=evidence["boardPreview"]["summary"]["boardExactMatch"],
        boardBlocked=evidence["boardPreview"]["summary"]["blocked"],
        veneerNetPass=evidence["veneerPreview"]["summary"]["netPass"],
        veneerNetBlocked=evidence["veneerPreview"]["summary"]["netBlocked"],
        actualConsumptionGenerated=0)
    data["version"] = "PCE-SEMI-FINISHED-CONFIGURATION-PREVIEW-3"
    data["boundaries"].update(currentSampleUserValidated=True, all05UserValidated=False,
        stockResolver="CONFIGURATION_FAMILY_COLUMN_L_ALLOWED_MATERIAL_EXACT_SPEC_GEOMETRY_MINIMUM", productionMigrationApplied=False,
        edgeOwner="ENGINEERING_COMPONENT",otherFixedOwner="ENGINEERING_STRUCTURE_BOM",roleLayerUserValidated=False,
        veneerThicknessCalculationInput=False)
    data["isolationEvidence"] = {"scope": evidence["scope"], "sha256": EVIDENCE_SHA,
        "decisionSha256": DECISION_SHA, "schemaVersion": evidence["schemaVersion"],
        "statusLabel": "三层角色整改及隔离回放完成；新层级待人工验收，生产尚未应用", "productionBusinessWrite": 0}
    return data
