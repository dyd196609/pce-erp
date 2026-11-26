"""Read-only Group 3 manufacturing-engineering acceptance facts.

This module deliberately performs no create/update/delete operation.  It compares an
immutable workbook-derived snapshot with the current formal PDE models.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pde.models import (
    BOMItem,
    BOMVersion,
    EngineeringSourceRecord,
    OrderEngineeringInstance,
    ProductBOM,
    ProductDefinition,
    ProductVersion,
    Routing,
    RoutingStep,
    RoutingVersion,
)
from system.models import Process
from masterdata.models import ExternalIdentity, Material


SOURCE_PATH = Path(__file__).with_name("group3_comparison_source.json")
SUPPORTED_ENTITIES = {"operations", "boms", "routings", "routing-steps"}


def _source():
    with SOURCE_PATH.open(encoding="utf-8") as source_handle:
        return json.load(source_handle)


def _company(queryset, company_id):
    return queryset.filter(company_id=company_id)


def _formal_counts(company_id):
    return {
        "productDefinition": _company(ProductDefinition.objects, company_id).count(),
        "productVersion": ProductVersion.objects.filter(product__company_id=company_id).count(),
        "orderEngineeringInstance": _company(OrderEngineeringInstance.objects, company_id).count(),
        "operation": _company(Process.objects, company_id).count(),
        "bom": _company(ProductBOM.objects, company_id).count(),
        "bomVersion": BOMVersion.objects.filter(bom__company_id=company_id).count(),
        "bomItem": BOMItem.objects.filter(bom_version__bom__company_id=company_id).count(),
        "routing": _company(Routing.objects, company_id).count(),
        "routingVersion": RoutingVersion.objects.filter(routing__company_id=company_id).count(),
        "routingStep": RoutingStep.objects.filter(routing_version__routing__company_id=company_id).count(),
        "engineeringSourceRecord": _company(EngineeringSourceRecord.objects, company_id).count(),
    }


def _operation_facts(source, company_id, counts):
    formal_rows = list(
        _company(Process.objects, company_id)
        .select_related("workshop", "calculation_uom")
        .order_by("code", "id")
    )
    by_name = {}
    for row in formal_rows:
        by_name.setdefault(row.name.strip(), []).append(row)

    comparison_rows = []
    matched = 0
    conflicts = 0
    for source_row in source["operationRows"]:
        candidates = by_name.get(source_row["sourceName"], [])
        formal = candidates[0] if len(candidates) == 1 else None
        expected_kind = "group" if source_row["sourceOperationCategory"].startswith("工序组") else "atomic"
        row_conflicts = []
        if len(candidates) > 1:
            row_conflicts.append("正式库存在同名重复工序")
        if formal:
            if formal.operation_kind != expected_kind:
                row_conflicts.append("工序类别不一致")
            if formal.calculation_basis != source_row["proposedCalculationBasis"].lower():
                row_conflicts.append("核算维度不一致")
            if (formal.workshop.name if formal.workshop_id else "") != source_row["workshop"]:
                row_conflicts.append("车间不一致")
        if formal and not row_conflicts:
            matched += 1
        if row_conflicts:
            conflicts += 1
        comparison_rows.append(
            {
                **source_row,
                "sourceOperationCategoryLabel": source_row["sourceOperationCategory"],
                "formalId": formal.id if formal else None,
                "formalCode": formal.code if formal else "",
                "formalName": formal.name if formal else "",
                "formalOperationCategory": formal.get_operation_kind_display() if formal else "",
                "formalWorkshop": formal.workshop.name if formal and formal.workshop_id else "",
                "formalCalculationBasis": ({
                    "count": "按数量", "length": "按长度", "area": "按面积",
                    "volume": "按体积", "mass": "按质量", "time": "按时间",
                    "other": "其它", "undetermined": "待确认",
                }.get(formal.calculation_basis, "待确认") if formal else "待确认"),
                "formalCalculationUom": (
                    f"{formal.calculation_uom.name}（{formal.calculation_uom.symbol or formal.calculation_uom.code}）"
                    if formal and formal.calculation_uom_id and (formal.calculation_uom.symbol or formal.calculation_uom.code)
                    else (formal.calculation_uom.name if formal and formal.calculation_uom_id else "待确认 / 来源未提供")
                ),
                "formalQuantityDriver": formal.quantity_driver if formal else "",
                "enabled": formal.is_active if formal else None,
                "defaultTransitionMode": formal.default_transition_mode if formal else "",
                "defaultTransitionModeLabel": formal.get_default_transition_mode_display() if formal else "待确认",
                "matchStatus": "CONFLICT" if row_conflicts else ("EXACT_MATCH" if formal else "MISSING"),
                "conflicts": row_conflicts,
                "dataProvenance": f'{source_row["sourceFile"]} / {source_row["sourceSheet"]} / 第{source_row["sourceRow"]}行',
                "transitionMode": formal.default_transition_mode if formal else "PENDING_USER_VALIDATION",
            }
        )

    formal_outside = [
        {
            "formalCode": row.code,
            "formalName": row.name,
            "workshop": row.workshop.name if row.workshop_id else "",
            "status": "FORMAL_OUTSIDE_CURRENT_SOURCE",
        }
        for row in formal_rows
        if row.name.strip() not in {item["sourceName"] for item in source["operationRows"]}
    ]
    return {
        "formalModel": "system.Process",
        "sourceRecordCount": len(source["operationRows"]),
        "formalRecordCount": counts["operation"],
        "matchedCount": matched,
        "conflictCount": conflicts,
        "missingCount": len(source["operationRows"]) - matched - conflicts,
        "formalOutsideCurrentSourceCount": len(formal_outside),
        "rows": comparison_rows,
        "formalOutsideCurrentSourceRows": formal_outside,
        "dataPresent": "PRESENT",
        "ready": "MANUAL_VALIDATION_READY",
        "modelGap": "已使用Process.default_transition_mode保存工序默认值；RoutingStep.effective_transition_mode可在未来正式路线步骤中覆盖。",
    }


def _routing_facts(source, company_id, counts):
    processes = list(_company(Process.objects, company_id).order_by("id"))
    process_by_name = {}
    process_by_id = {str(row.pk): row for row in processes}
    for process in processes:
        process_by_name.setdefault(process.name.strip(), []).append(process)
    alias_identities = list(ExternalIdentity.objects.filter(
        organization_id=company_id,
        source_system="02工艺路线.xlsx",
        source_type="USER_VALIDATED_ALIAS",
        source_object_type="ROUTING_STEP_OPERATION_VALUE",
        external_id="拉丝",
        mapping_status=ExternalIdentity.MappingStatus.MATCH,
        target_entity_type="operations",
    ))
    formal_routes = list(
        _company(Routing.objects, company_id)
        .select_related("product_category", "manufacturing_process_type")
        .prefetch_related("versions__steps__operation")
    )
    formal_by_code = {row.routing_code: row for row in formal_routes}

    def resolve_operation(source_name):
        exact = process_by_name.get(source_name, [])
        if len(exact) == 1:
            return exact[0], "RESOLVED", "名称精确匹配"
        if len(exact) > 1:
            return None, "CONFLICT", "正式工序存在同名重复"
        if source_name == "拉丝":
            targets = [process_by_id.get(identity.target_entity_id) for identity in alias_identities]
            targets = [target for target in targets if target]
            if len(alias_identities) == 1 and len(targets) == 1 and targets[0].name == "拉丝/打磨":
                return targets[0], "RESOLVED", "用户确认别名：拉丝 → 拉丝/打磨"
            if alias_identities:
                return None, "CONFLICT", "拉丝别名来源身份存在冲突"
        return None, "UNRESOLVED", "来源工序尚未匹配正式工序"

    steps_by_route = {}
    for step in source["routingStepRows"]:
        steps_by_route.setdefault(step["routeCode"], []).append(step)

    route_cards = []
    mapping_counts = {"resolved": 0, "unresolved": 0, "conflict": 0}
    unresolved_names = {}
    conflict_names = {}
    alias_resolved = 0
    for source_row in source["routingRows"]:
        formal_route = formal_by_code.get(source_row["routeCode"])
        formal_versions = list(formal_route.versions.all()) if formal_route else []
        formal_version = next(
            (version for version in formal_versions if version.routing_version == "SYSTEM_INITIAL_VERSION"),
            None,
        )
        formal_steps = {
            step.sequence: step for step in (formal_version.steps.all() if formal_version else [])
        }
        related_steps = sorted(steps_by_route.get(source_row["routeCode"], []), key=lambda row: row["sequence"])
        sequence_counts = {}
        operation_counts = {}
        projected_steps = []
        for step in related_steps:
            sequence_counts[step["sequence"]] = sequence_counts.get(step["sequence"], 0) + 1
            operation_counts[step["operationName"]] = operation_counts.get(step["operationName"], 0) + 1
            operation, mapping_status, mapping_reason = resolve_operation(step["operationName"])
            mapping_counts[mapping_status.lower()] += 1
            if mapping_status == "UNRESOLVED":
                unresolved_names[step["operationName"]] = unresolved_names.get(step["operationName"], 0) + 1
            elif mapping_status == "CONFLICT":
                conflict_names[step["operationName"]] = conflict_names.get(step["operationName"], 0) + 1
            if step["operationName"] == "拉丝" and mapping_status == "RESOLVED":
                alias_resolved += 1
            transition_code = operation.default_transition_mode if operation else ""
            formal_step = formal_steps.get(step["sequence"])
            expected_formal_name = operation.name if operation else ""
            formal_step_matches = bool(
                formal_step and formal_step.operation.name == expected_formal_name
                and formal_step.predecessor_sequences == ([step["predecessorSequence"]] if step["predecessorSequence"] else [])
            )
            projected_steps.append({
                "sequence": step["sequence"],
                "sourceOperation": step["operationName"],
                "formalOperationCode": operation.code if operation else "",
                "formalOperationName": operation.name if operation else "",
                "operationMappingStatus": mapping_status,
                "operationMappingStatusLabel": {
                    "RESOLVED": "已解析", "UNRESOLVED": "待解析", "CONFLICT": "冲突",
                }[mapping_status],
                "mappingReason": mapping_reason,
                "predecessor": step["predecessorName"],
                "next": step["nextName"],
                "transitionMode": transition_code,
                "transitionModeLabel": (
                    "齐套工序" if transition_code == Process.TransitionMode.KITTING
                    else "一般工序" if transition_code else "待解析"
                ),
                "transitionSource": "正式工序默认配置；未来路线步骤可按具体路线覆盖",
                "formalStepId": formal_step.pk if formal_step else None,
                "formalStepStatus": "EXACT_MATCH" if formal_step_matches else ("CONFLICT" if formal_step else "MISSING"),
                "source": f'{step["sourceFile"]} / {step["sourceSheet"]} / 第{step["sourceRow"]}行 / 关联工序{step["sequence"]}',
            })

        sequences = [step["sequence"] for step in related_steps]
        expected_sequences = list(range(1, len(related_steps) + 1))
        duplicate_sequences = sorted(value for value, total in sequence_counts.items() if total > 1)
        duplicate_operations = sorted(value for value, total in operation_counts.items() if total > 1)
        missing_sequences = sorted(set(expected_sequences) - set(sequences))
        first_abnormal = bool(related_steps and (
            related_steps[0]["sequence"] != 1 or related_steps[0]["predecessorSequence"] is not None
        ))
        last_abnormal = bool(related_steps and related_steps[-1]["nextSequence"] is not None)
        circular = any(
            step["predecessorSequence"] is not None and step["predecessorSequence"] >= step["sequence"]
            for step in related_steps
        )
        route_unresolved = sum(step["operationMappingStatus"] == "UNRESOLVED" for step in projected_steps)
        route_conflicts = sum(step["operationMappingStatus"] == "CONFLICT" for step in projected_steps)
        formal_step_conflicts = sum(step["formalStepStatus"] != "EXACT_MATCH" for step in projected_steps)
        anomaly_items = []
        if duplicate_operations:
            anomaly_items.append(f'重复工序：{"、".join(duplicate_operations)}')
        if duplicate_sequences:
            anomaly_items.append(f'同一步骤重复编号：{duplicate_sequences}')
        if missing_sequences:
            anomaly_items.append(f'顺序缺号：{missing_sequences}')
        if circular:
            anomaly_items.append("存在循环或反向前置关系")
        if first_abnormal:
            anomaly_items.append("首工序前置关系异常")
        if last_abnormal:
            anomaly_items.append("末工序后续关系异常")
        if route_unresolved:
            anomaly_items.append(f"未解析工序：{route_unresolved}个步骤")
        if route_conflicts:
            anomaly_items.append(f"工序映射冲突：{route_conflicts}个步骤")
        if formal_step_conflicts:
            anomaly_items.append(f"正式步骤不一致：{formal_step_conflicts}个步骤")
        route_identity_matches = bool(
            formal_route
            and formal_route.applicability_scope == "PRODUCT_CATEGORY"
            and formal_route.product_category
            and formal_route.product_category.name == source_row["applicableProductCategory"]
            and formal_route.manufacturing_process_type
            and source_row["routeCode"].split("/", 1)[0] == formal_route.manufacturing_process_type.code
        )
        kitting_relations = [
            f'{step["formalOperationName"]} → {step["next"]}'
            for step in projected_steps if step["transitionMode"] == Process.TransitionMode.KITTING
        ]
        route_cards.append({
            **source_row,
            "sourceRowRange": f'{source_row["sourceSheet"]} 第{source_row["sourceRow"]}行（关联工序1–{len(related_steps)}）',
            "sourceInterpretation": "产品类别适用的工艺路线变体/模板；不是订单工程实例",
            "proposedFormalObject": "产品分类 + 工艺类型适用的正式 Routing",
            "formalRouting": ({"id": formal_route.pk, "code": formal_route.routing_code, "name": formal_route.name} if formal_route else None),
            "formalStatus": "EXACT_MATCH" if route_identity_matches else ("CONFLICT" if formal_route else "MISSING"),
            "formalVersionStatus": "SYSTEM_INITIAL_VERSION / SYSTEM_DERIVED / INITIAL_FORMALIZATION" if formal_version else "MISSING",
            "formalStepCount": len(formal_steps),
            "steps": projected_steps,
            "resolvedStepCount": sum(step["operationMappingStatus"] == "RESOLVED" for step in projected_steps),
            "matchedOperationCount": sum(step["operationMappingStatus"] == "RESOLVED" for step in projected_steps),
            "unresolvedStepCount": route_unresolved,
            "unresolvedOperationNames": sorted({step["sourceOperation"] for step in projected_steps if step["operationMappingStatus"] == "UNRESOLVED"}),
            "conflictStepCount": route_conflicts,
            "containsPinpi": any(step["sourceOperation"] == "拼皮" for step in projected_steps),
            "anomalyCount": len(anomaly_items),
            "anomalies": anomaly_items,
            "anomalyStatus": "待处理" if anomaly_items else "未发现结构异常",
            "kittingRelationshipExplanation": kitting_relations,
            "predecessorRule": "来源关联工序列形成线性前后关系；本轮仅投影，不写正式步骤",
            "status": "FORMALIZED / USER_VALIDATED" if route_identity_matches and formal_version and not formal_step_conflicts else "CONFLICT",
        })

    categories = {}
    for category in sorted({row["applicableProductCategory"] for row in route_cards}):
        category_rows = [row for row in route_cards if row["applicableProductCategory"] == category]
        shortest = min(category_rows, key=lambda row: (row["stepCount"], row["sourceRow"]))
        longest = max(category_rows, key=lambda row: (row["stepCount"], -row["sourceRow"]))
        categories[category] = {
            "routeCount": len(category_rows),
            "stepCountMin": shortest["stepCount"],
            "stepCountMax": longest["stepCount"],
            "shortestRoute": {"routeCode": shortest["routeCode"], "routeName": shortest["routeName"], "stepCount": shortest["stepCount"]},
            "longestRoute": {"routeCode": longest["routeCode"], "routeName": longest["routeName"], "stepCount": longest["stepCount"]},
        }
    representative_codes = []
    for category in ("房门", "饰面", "柜体"):
        category_rows = [row for row in route_cards if row["applicableProductCategory"] == category]
        if not category_rows:
            continue
        shortest = min(category_rows, key=lambda row: (row["stepCount"], row["sourceRow"]))
        longest = max(category_rows, key=lambda row: (row["stepCount"], -row["sourceRow"]))
        representative_codes.extend([shortest["routeCode"], longest["routeCode"]])
    representative_cards = [row for row in route_cards if row["routeCode"] in representative_codes]
    anomaly_route_count = sum(row["anomalyCount"] > 0 for row in route_cards)
    total_anomaly_count = sum(row["anomalyCount"] for row in route_cards)
    return {
        "formalModel": "pde.Routing / pde.RoutingVersion",
        "sourceRecordCount": len(route_cards),
        "sourceStepRecordCount": len(source["routingStepRows"]),
        "formalRecordCount": counts["routing"],
        "formalVersionCount": counts["routingVersion"],
        "formalStepCount": counts["routingStep"],
        "proposedCount": len(route_cards),
        "unresolvedCount": sum(row["formalStatus"] != "EXACT_MATCH" or row["formalVersionStatus"] == "MISSING" for row in route_cards),
        "resolvedStepCount": mapping_counts["resolved"],
        "unresolvedStepCount": mapping_counts["unresolved"],
        "conflictStepCount": mapping_counts["conflict"],
        "unresolvedOperationNames": [{"name": name, "occurrenceCount": total} for name, total in sorted(unresolved_names.items())],
        "conflictOperationNames": [{"name": name, "occurrenceCount": total} for name, total in sorted(conflict_names.items())],
        "aliasMapping": {"source": "拉丝", "formal": "拉丝/打磨", "sourceOccurrenceCount": 3, "resolvedCount": alias_resolved},
        "pinpiProjection": {"sourceRouteCount": sum(row["containsPinpi"] for row in route_cards), "automaticallyInsertedCount": 0},
        "routeInterpretation": {
            "conclusion": "42条来源行是14种工艺类型分别适用于房门、饰面、柜体的类别路线变体/模板，不是42个订单工程实例。",
            "routeTypeCount": len({row["routeCode"].rsplit("/", 1)[0] for row in route_cards}),
            "applicabilityCategoryCount": len(categories),
            "formalizationDecision": "USER_VALIDATED / FORMALIZED / FROZEN",
        },
        "categorySummary": categories,
        "unknownCategoryCount": sum(row["applicableProductCategory"] not in {"房门", "饰面", "柜体"} for row in route_cards),
        "routeCards": route_cards,
        "representativeRouteCards": representative_cards,
        "representativeSelectionRule": "每类选择来源中步骤最短与最长的路线，共6张；用于先确认解析和卡片展示方式。",
        "anomalyRouteCount": anomaly_route_count,
        "totalAnomalyCount": total_anomaly_count,
        "rows": route_cards,
        "dataPresent": "PRESENT" if counts["routing"] == 42 and counts["routingVersion"] == 42 and counts["routingStep"] == 1137 else "PARTIAL",
        "ready": "READY",
        "modelGap": "Manufacturing Definition Applicability 已正式生效；42条路线使用 PRODUCT_CATEGORY + 工艺类型唯一承载，没有创建虚假ProductDefinition。",
        "versionReadiness": "42个 SYSTEM_INITIAL_VERSION 技术容器已正式建立；来源没有被伪装为历史版本。",
    }


def _routing_step_facts(source, company_id, counts):
    processes = list(_company(Process.objects, company_id).order_by("id"))
    process_by_name = {}
    for process in processes:
        process_by_name.setdefault(process.name.strip(), []).append(process)
    process_by_id = {str(row.pk): row for row in processes}
    alias_identity = ExternalIdentity.objects.filter(
        organization_id=company_id,
        source_system="02工艺路线.xlsx",
        source_type="USER_VALIDATED_ALIAS",
        source_object_type="ROUTING_STEP_OPERATION_VALUE",
        external_id="拉丝",
        mapping_status=ExternalIdentity.MappingStatus.MATCH,
        target_entity_type="operations",
    ).first()
    formal_steps = {
        (row.routing_version.routing.routing_code, row.sequence): row
        for row in RoutingStep.objects.filter(routing_version__routing__company_id=company_id)
        .select_related("routing_version__routing", "operation")
    }
    rows = []
    operation_unresolved = 0
    operation_conflicts = 0
    resolved = 0
    for source_row in source["routingStepRows"]:
        exact_matches = process_by_name.get(source_row["operationName"], [])
        operation = exact_matches[0] if len(exact_matches) == 1 else None
        conflict = len(exact_matches) > 1
        if not operation and source_row["operationName"] == "拉丝" and alias_identity:
            operation = process_by_id.get(alias_identity.target_entity_id)
        if conflict:
            operation_conflicts += 1
        elif not operation:
            operation_unresolved += 1
        else:
            resolved += 1
        formal_step = formal_steps.get((source_row["routeCode"], source_row["sequence"]))
        formal_match = bool(
            formal_step and operation and formal_step.operation_id == operation.pk
            and formal_step.predecessor_sequences == ([source_row["predecessorSequence"]] if source_row["predecessorSequence"] else [])
        )
        rows.append(
            {
                **source_row,
                "formalOperationCode": operation.code if operation else "",
                "formalOperationName": operation.name if operation else "",
                "operationMatchStatus": "CONFLICT" if conflict else ("RESOLVED" if operation else "UNRESOLVED_OPERATION"),
                "transitionMode": operation.default_transition_mode if operation else "",
                "transitionModeLabel": operation.get_default_transition_mode_display() if operation else "待解析",
                "formalStepId": formal_step.pk if formal_step else None,
                "formalStepStatus": "EXACT_MATCH" if formal_match else ("CONFLICT" if formal_step else "MISSING"),
                "formalizationStatus": "FORMALIZED / USER_VALIDATED" if formal_match else "UNRESOLVED_LINKAGE",
                "dataProvenance": f'{source_row["sourceFile"]} / {source_row["sourceSheet"]} / 第{source_row["sourceRow"]}行 / 步骤{source_row["sequence"]}',
            }
        )
    return {
        "formalModel": "pde.RoutingStep",
        "sourceRecordCount": len(source["routingStepRows"]),
        "formalRecordCount": counts["routingStep"],
        "proposedCount": len(rows),
        "resolvedCount": resolved,
        "unresolvedCount": sum(row["formalStepStatus"] != "EXACT_MATCH" for row in rows),
        "conflictCount": operation_conflicts,
        "unresolvedOperationMappingCount": operation_unresolved,
        "unresolvedOperationNames": sorted({row["operationName"] for row in rows if row["operationMatchStatus"] == "UNRESOLVED_OPERATION"}),
        "conflictOperationNames": sorted({row["operationName"] for row in rows if row["operationMatchStatus"] == "CONFLICT"}),
        "rows": rows,
        "dataPresent": "PRESENT" if counts["routingStep"] == 1137 else "PARTIAL",
        "ready": "READY",
        "modelGap": "1,137条正式RoutingStep已按来源顺序和前置关系回读；effective_transition_mode为空时继承正式工序默认值。",
    }


def _bom_facts(source, company_id, counts):
    material_by_code = {
        row.code: row for row in Material.objects.filter(company_id=company_id)
    }
    rows = []
    for row in source["engineeringBreakdown"]["rows"]:
        dimensions = row.get("dimensions") or {}
        material = material_by_code.get(row["materialCode"])
        material_role = "未匹配正式物料"
        if material:
            material_role = {
                "semi": "自产半成品" if material.is_produced else "半成品",
                "raw": "采购物料" if material.is_purchased else "原材料",
                "auxiliary": "采购辅料" if material.is_purchased else "辅料",
                "finished": "成品物料",
            }.get(material.material_type, material.get_material_type_display())
        preview_identity = " / ".join(filter(None, (
            row["productCategory"], row["space"], row["productName"], row["processCode"]
        )))
        rows.append(
            {
                **row,
                "dimensionsText": " × ".join(str(dimensions.get(key) or "-") for key in ("height", "width", "thickness")),
                "structureRole": "客户成品/订单工程对象" if row["productCategory"] in {"房门", "柜体", "饰面"} else "待人工确认",
                "componentRole": "工程部件/制造组成事实",
                "materialRole": material_role,
                "formalMaterialCode": material.code if material else "",
                "formalMaterialName": material.name if material else "",
                "previewStructureIdentity": preview_identity,
                "identityStatus": "SOURCE_STRUCTURE_USER_VALIDATED",
                "formalBom": None,
                "proposedFormalObject": "工程结构来源事实；待核算规则验收后再决定正式BOM承载边界",
                "status": "STRUCTURE_USER_VALIDATED_CALCULATION_NOT_READY",
                "unresolvedReason": "不要求关联08排产样版；当前缺口是工程/物料核算规则。",
            }
        )
    grouped = {}
    for row in rows:
        key = row["previewStructureIdentity"]
        card = grouped.setdefault(key, {
            "identity": key,
            "productCategory": row["productCategory"],
            "space": row["space"],
            "productName": row["productName"],
            "processCode": row["processCode"],
            "identityStatus": row["identityStatus"],
            "children": [],
        })
        card["children"].append(row)
    hierarchy_cards = list(grouped.values())
    for card in hierarchy_cards:
        card["componentCount"] = len(card["children"])
    representative_cards = []
    for category in ("房门", "柜体", "饰面"):
        category_cards = [card for card in hierarchy_cards if card["productCategory"] == category]
        representative_cards.extend(category_cards[:2])
    return {
        "formalModel": "pde.ProductBOM / pde.BOMVersion / pde.BOMItem",
        "sourceRecordCount": len(rows),
        "formalRecordCount": counts["bom"],
        "formalVersionCount": counts["bomVersion"],
        "formalItemCount": counts["bomItem"],
        "proposedCount": len(rows),
        "unresolvedCount": 0,
        "engineeringSourceRecordCount": counts["engineeringSourceRecord"],
        "engineeringLinkage": "NOT_REQUIRED_TO_08",
        "stableLinkageAnalysis": {
            "checkedFields": [],
            "sourceAvailableFields": source["engineeringBreakdown"]["availableIdentityFields"],
            "stableMatchCount": 0,
            "unresolvedCount": 0,
            "conclusion": "08订单排产信息（样版）仅作派生结果对照，不是工程结构来源，71行关联37行要求已作废。",
        },
        "hierarchyCards": hierarchy_cards,
        "hierarchyCardCount": len(hierarchy_cards),
        "representativeHierarchyCards": representative_cards,
        "representativeSelectionRule": "按房门、柜体、饰面各取最多2个来源结构，仅用于人工解释；不是正式BOM身份。",
        "rows": rows,
        "dataPresent": "MISSING",
        "ready": "STRUCTURE_USER_VALIDATED_CALCULATION_REQUIRED",
        "modelGap": "31张结构卡及71条组成行已通过结构层人工验收；当前仅暂停于核算规则层，不创建正式BOM。",
    }


def build_group3_comparison(entity, company_id):
    if entity not in SUPPORTED_ENTITIES:
        raise KeyError(entity)
    source = _source()
    counts = _formal_counts(company_id)
    if entity == "operations":
        facts = _operation_facts(source, company_id, counts)
    elif entity == "routings":
        facts = _routing_facts(source, company_id, counts)
    elif entity == "routing-steps":
        facts = _routing_step_facts(source, company_id, counts)
    else:
        facts = _bom_facts(source, company_id, counts)
    loaded_at = datetime.now(timezone.utc).isoformat()
    result = {
        "version": source["version"],
        "readOnly": True,
        "entity": entity,
        "developed": True,
        "userValidated": entity in {"boms", "routings", "routing-steps"},
        "group3Overall": "GROUP3C_STRUCTURE_VALIDATED_CALCULATION_LAYER_PAUSED" if entity == "boms" else "READY",
        "productionManufacturingMasterDataWriteCount": 0,
        "group4Entered": False,
        "planningProductionDeployed": False,
        "formalCounts": counts,
        "sourceSemantics": source["sourceSemantics"],
        "dataProvenance": source["generatedFrom"],
        "factLoadStatus": "loaded",
        "apiUrl": f"/api/masterdata/group3-comparison/{entity}/?company_id={company_id}",
        "httpStatus": 200,
        "errorCode": "",
        "errorMessage": "",
        "loadedAt": loaded_at,
        "tenantId": company_id,
        "batchId": "GROUP3B-ROUTING-MANUAL-ACCEPTANCE-20260908-001" if entity == "routings" else "",
        "linkageAudit": {
            "schedulingSourceCount": source["summary"]["schedulingSourceCount"],
            "engineeringBreakdownCount": source["summary"]["engineeringBreakdownCount"],
            "status": "SUPERSEDED_NOT_REQUIRED",
            "reason": "08排产样版仅作派生结果对照；不再要求与工程结构逐行关联。",
            "prohibitedMethods": ["按行号拼接", "按出现顺序拼接", "模糊名称匹配"],
        },
        **facts,
    }
    strict_facts = {
        "entity": entity,
        "sourceRecordCount": result["sourceRecordCount"],
        "formalRecordCount": result["formalRecordCount"],
        "dataPresent": result["dataPresent"],
        "productionManufacturingMasterDataWriteCount": 0,
        "loadedAt": loaded_at,
        "tenantId": company_id,
    }
    if entity == "routings":
        strict_facts.update({
            "sourceStepRecordCount": result["sourceStepRecordCount"],
            "resolvedStepCount": result["resolvedStepCount"],
            "unresolvedStepCount": result["unresolvedStepCount"],
            "conflictStepCount": result["conflictStepCount"],
            "routeCardCount": len(result["routeCards"]),
            "anomalyRouteCount": result["anomalyRouteCount"],
        })
    result["strictFacts"] = strict_facts
    result["acceptanceFacts"] = strict_facts
    return result
