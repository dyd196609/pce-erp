from types import MappingProxyType


SCM_CANARY_OBJECT_MAPPING = MappingProxyType({
    "HAPPY_PATH": MappingProxyType({"businessNo": "PRQ-CAN-001", "sourceScenarioCode": "HAPPY_PATH", "name": "正常采购闭环"}),
    "PRICE_EXCEPTION": MappingProxyType({"businessNo": "PRQ-CAN-007", "sourceScenarioCode": "PRICE_EXCEPTION", "name": "价格异常"}),
    "QUALITY_FAIL": MappingProxyType({"businessNo": "PRQ-CAN-003", "sourceScenarioCode": "QUALITY_FAIL", "name": "质量不合格"}),
    "QUANTITY_DIFFERENCE": MappingProxyType({"businessNo": "PRQ-CAN-004", "sourceScenarioCode": "INBOUND_SHORTAGE", "name": "数量差异"}),
    "SOURCE_MISSING": MappingProxyType({"businessNo": "PRQ-CAN-005", "sourceScenarioCode": "RECONCILIATION_DIFF", "name": "来源缺失"}),
    "INVOICE_VALIDATION_FAILED": MappingProxyType({"businessNo": "PRQ-CAN-006", "sourceScenarioCode": "SUPPLIER_MISSING", "name": "发票校验失败"}),
    "DUPLICATE_INVOICE": MappingProxyType({"businessNo": "PRQ-CAN-002", "sourceScenarioCode": "QUANTITY_DIFFERENCE", "name": "重复发票"}),
    "SOURCE_STALE": MappingProxyType({"businessNo": "PRQ-CAN-008", "sourceScenarioCode": "EXISTING_TARGET", "name": "来源过期"}),
})


def resolve_scm_canary_mapping(batch_id, scenario_code):
    if batch_id != "SCM-CANARY-FLOW-V1":
        return None
    mapping = SCM_CANARY_OBJECT_MAPPING.get(scenario_code)
    if mapping is None:
        raise LookupError(f"Frozen SCM canary scenario not found: {scenario_code}")
    return mapping


def scm_canary_scenario_catalog():
    return [
        {"code": code, "name": item["name"], "businessNo": item["businessNo"]}
        for code, item in SCM_CANARY_OBJECT_MAPPING.items()
    ]
