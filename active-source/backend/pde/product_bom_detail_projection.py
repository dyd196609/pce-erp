"""Read-only Product BOM material and requirement provenance projection."""

from decimal import Decimal

from django.db.models import Prefetch

from .models import BOMItem, BOMItemSourceRequirement


class ProductBomDetailProjectionError(RuntimeError):
    """Raised when persisted BOM provenance crosses its formal identity scope."""


def _require(condition, message):
    if not condition:
        raise ProductBomDetailProjectionError(message)


def _uom_display(uom):
    symbol = str(uom.symbol or "").strip()
    name = str(uom.name or "").strip()
    if symbol and name and symbol != name:
        return f"{symbol} / {name}"
    return symbol or name or uom.code


def project_bom_draft_context(version):
    """Project the persisted draft contract; never reclassify the order purpose."""
    if version is None:
        return {}
    if version.usage_purpose == 'TEST_BUSINESS':
        return {'controlledDraftLabel':'测试业务草稿；禁止正式评审、发布及制造','usagePurposeLabel':'测试业务','sourceCalculationId':version.source_calculation_id or version.bom.source_calculation_id}
    proof = (version.applicability or {}).get('developmentValidation')
    if not proof:
        return {}
    from .models import OrderEngineeringBaselineItem
    scope = proof.get('objectScope', {})
    _require(proof.get('scope') == 'SYSTEM_TEST_BOM_DRAFT_ONCE_V1'
             and proof.get('developmentOnly') is True
             and proof.get('formalManufacturingEligible') is False
             and proof.get('quantityBasis') == 'ORDER_TOTAL_NET'
             and proof.get('orderQuantityMultiplierApplied') is False
             and version.source_calculation_id == scope.get('calculationId')
             and version.order_engineering_instance_id == scope.get('oeiId')
             and version.bom.company_id == scope.get('companyId'), '受控草稿用途或对象合同不一致。')
    baseline_item = OrderEngineeringBaselineItem.objects.select_related('baseline').filter(
        pk=scope.get('baselineItemId'), baseline_id=scope.get('baselineId'),
        design_item_id=scope.get('designItemId'), design_revision_id=scope.get('designRevisionId'),
        baseline__company_id=scope.get('companyId'), baseline__status='confirmed',
    ).first()
    _require(baseline_item is not None, '受控草稿缺少精确冻结设计修订及基线。')
    from .baseline_usage_service import production_status
    _require(production_status(baseline_item.baseline)=='confirmed','该旧草稿契约未开放TEST_BUSINESS用途消费，或批准依据已失效。')
    return {'controlledDraftLabel': '受控开发测试草稿；仅限本订单，禁止评审、发布及制造',
            'quantityBasisLabel': '订单总净量（已含订单数量，不再乘数量）',
            'frozenDesignRevisionLabel': f'设计修订R{baseline_item.design_revision_no}',
            'frozenBaselineNo': baseline_item.baseline.baseline_no}


def project_product_bom_material_detail(*, bom, bom_version, order_item):
    """Project persisted BOM items and their exact source-requirement links.

    This function is deliberately query-only.  It neither derives missing facts nor
    groups requirements again; BOMItemSourceRequirement remains the relationship
    authority created by the formal BOM generation transaction.
    """

    if bom_version is None:
        return []

    link_queryset = BOMItemSourceRequirement.objects.select_related(
        "material_requirement__calculation__sales_order_item__sales_order",
        "material_requirement__source_detail",
        "material_requirement__material",
        "material_requirement__uom",
    ).order_by("material_requirement__sequence", "pk")
    item_queryset = BOMItem.objects.filter(bom_version=bom_version).select_related(
        "material", "uom",
    ).prefetch_related(
        Prefetch("source_requirements", queryset=link_queryset),
    ).order_by("line_no", "pk")

    rows = []
    seen_requirement_ids = set()
    for item in item_queryset:
        _require(item.material.company_id == bom.company_id, "BOM明细物料跨公司，停止来源投影。")
        _require(item.uom.company_id == bom.company_id, "BOM明细单位跨公司，停止来源投影。")
        source_rows = []
        contributed_total = Decimal("0")
        links = item.source_requirements.all()
        if bom_version.usage_purpose == 'TEST_BUSINESS' and bom_version.origin_version_id:
            origin = bom_version.origin_version
            visited = {bom_version.pk}
            while origin.origin_version_id:
                _require(origin.pk not in visited, '测试派生沿革循环。')
                visited.add(origin.pk)
                origin = origin.origin_version
            original_item = origin.items.get(line_no=item.line_no)
            _require(original_item.material_id == item.material_id and original_item.uom_id == item.uom_id and original_item.quantity == item.quantity, '派生测试行与来源材料需求不一致。')
            links = original_item.source_requirements.all()
        for link in links:
            requirement = link.material_requirement
            calculation = requirement.calculation
            requirement_order_item = calculation.sales_order_item
            trace = requirement.trace or {}

            _require(requirement.pk not in seen_requirement_ids, "同一Requirement重复关联BOM明细，停止来源投影。")
            seen_requirement_ids.add(requirement.pk)
            _require(calculation.pk == (bom.source_calculation_id if bom_version.usage_purpose == 'TEST_BUSINESS' else bom_version.source_calculation_id), "Requirement来源核算与BOM版本不一致。")
            _require(calculation.company_id == bom.company_id, "Requirement来源核算跨公司。")
            _require(requirement.material_id == item.material_id, "Requirement物料与BOM明细物料不一致。")
            _require(requirement.uom_id == item.uom_id, "Requirement单位与BOM明细单位不一致。")
            if order_item is not None:
                _require(requirement_order_item is not None, "Requirement缺少正式销售订单行。")
                _require(requirement_order_item.pk == order_item.pk, "Requirement来源订单行与BOM适用订单行不一致。")

            contributed_total += link.contributed_quantity
            source_rows.append({
                "sourceLinkId": link.pk,
                "requirementId": requirement.pk,
                "requirementSequence": requirement.sequence,
                "designItemId": trace.get("designItemId"),
                "designItemNo": trace.get("designItemNo") or "未提供",
                "materialId": requirement.material_id,
                "materialCode": requirement.material.code,
                "materialName": requirement.material.name,
                "quantity": str(requirement.net_quantity),
                "contributedQuantity": str(link.contributed_quantity),
                "uomId": requirement.uom_id,
                "uomCode": requirement.uom.code,
                "uomName": requirement.uom.name,
                "uomSymbol": requirement.uom.symbol,
                "uomDisplay": _uom_display(requirement.uom),
                "structuralRole": trace.get("structureRole") or requirement.item_role,
                "structuralRoleLabel": {'DOOR_LEAF_SURFACE_PANEL':'门扇面层', 'CASING_MATERIAL':'门套',
                    'CASING_TRIM':'门套线', 'EDGE_BANDING':'封边'}.get(
                        trace.get('structureRole') or requirement.item_role, '其他结构角色'),
                "itemRole": requirement.item_role,
                "requirementType": requirement.requirement_type,
                "supplyType": requirement.supply_type,
                "calculationId": calculation.pk,
                "calculationNo": calculation.calculation_no,
                "sourceDetailId": requirement.source_detail_id,
                "sourceDetailName": requirement.source_detail.output_name,
                "sourceFactId": trace.get("sourceFactId"),
                "mappingRuleId": trace.get("mappingRuleId"),
                "mappingRuleCode": trace.get("mappingRuleCode") or trace.get("ruleCode") or "未提供",
                "sourcePath": requirement.source_path,
                "relationStatusCode": "LINKED",
                "relationStatusLabel": "已建立正式来源关系",
                "companyId": calculation.company_id,
                "orderId": requirement_order_item.sales_order_id if requirement_order_item else None,
                "orderNo": requirement_order_item.sales_order.order_no if requirement_order_item else "",
                "salesOrderItemId": requirement_order_item.pk if requirement_order_item else None,
                "orderLineNo": requirement_order_item.line_no if requirement_order_item else None,
                "bomItemId": item.pk,
            })

        if source_rows:
            _require(contributed_total == item.quantity, "BOM明细数量与来源Requirement贡献量合计不一致。")
        quantity_rule = item.quantity_rule or {}
        order_total_net = quantity_rule.get('basis') == 'ORDER_TOTAL_NET'
        if order_total_net:
            _require(quantity_rule.get('orderQuantityMultiplierApplied') is False
                     and quantity_rule.get('grossQuantity') is None
                     and Decimal(quantity_rule.get('netQuantity')) == item.quantity
                     and item.scrap_rate is None and item.scrap_rate_status == 'not_maintained',
                     '订单总净量草稿的数量或损耗合同不一致。')
        rows.append({
            "bomItemId": item.pk,
            "lineNo": item.line_no,
            "materialId": item.material_id,
            "materialCode": item.material.code,
            "materialName": item.material.name,
            "materialSpecification": item.material.specification or "",
            "materialSpecificationLabel": item.material.specification or "未维护",
            "quantity": str(item.quantity),
            "quantityBasisLabel": '订单总净量' if order_total_net else '原BOM数量口径',
            "scrapRateLabel": '未维护' if item.scrap_rate is None else f'{item.scrap_rate * 100}%',
            "grossQuantityLabel": '未维护（净量草稿）' if order_total_net else '未由本投影核定',
            "structuralRoleLabel": '、'.join(dict.fromkeys(s['structuralRoleLabel'] for s in source_rows)) or '未提供',
            "uomId": item.uom_id,
            "uomCode": item.uom.code,
            "uomName": item.uom.name,
            "uomSymbol": item.uom.symbol,
            "uomDisplay": _uom_display(item.uom),
            "sourceRequirementCount": len(source_rows),
            "sourceRequirements": source_rows,
        })
    return rows
