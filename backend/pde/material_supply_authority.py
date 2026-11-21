"""Use governed material facts for an explicit engineering MAKE/BUY choice.

This validates supply facts only; it grants no role, action or object scope.
Historic documents and material attributes are never changed here.
"""


def material_supply_fact(material, supply_type):
    requested = str(supply_type or "").strip().upper()
    canonical = {"PURCHASE": "BUY", "PRODUCTION": "MAKE"}.get(requested, requested)
    purchased = bool(material.is_purchased)
    produced = bool(material.is_produced)
    code = None
    message = None
    if canonical == "BUY" and not purchased:
        code = "MATERIAL_PURCHASE_NOT_ALLOWED"
        message = f"物料{material.code}未获准采购，不能按外购生成工程材料需求或发布BOM；请沿正式物料维护及来源核定处理。"
    elif canonical == "MAKE" and not produced:
        code = "MATERIAL_PRODUCTION_NOT_ALLOWED"
        message = f"物料{material.code}未获准自制，不能按自制生成工程材料需求或发布BOM；请沿正式物料维护及来源核定处理。"
    elif canonical in {"BUY", "MAKE"} and purchased and produced:
        code = "MATERIAL_SUPPLY_FACT_CONFLICT"
        message = f"物料{material.code}的采购与自制事实相互冲突，须先核定正式来源。"
    return {
        "materialId": material.pk, "materialCode": material.code,
        "requestedSupplyType": requested, "canonicalSupplyType": canonical,
        "isPurchased": purchased, "isProduced": produced,
        "allowed": code is None, "code": code, "message": message,
        "authority": "masterdata.Material.is_purchased/is_produced",
        "qualificationMeaning": "仅核对明确MAKE/BUY与现有供给事实，不授办理资格；委外及双源枚举仍沿各自原合同。",
    }
