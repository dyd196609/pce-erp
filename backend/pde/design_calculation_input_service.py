"""Explicit neutral formal cabinet contract; original TEST adapter stays sealed."""
def normalize_contract(value,*,frozen=False):
    if isinstance(value,dict) and value.get('contractVersion')=='CABINET-PARTS-V1':
        from .formal_cabinet_calculation_adapter import normalize
        return normalize(value,frozen=frozen)
    from .native_design_calculation_adapter import normalize_contract as original
    return original(value,frozen=frozen)

def freeze_contract_units(value,*,company_id,design_uom_id=None,physical_uom_id=None):
    if isinstance(value,dict) and value.get('contractVersion')=='CABINET-PARTS-V1':
        from .formal_cabinet_calculation_adapter import freeze
        return freeze(value,company_id)
    from .native_design_calculation_adapter import freeze_contract_units as original
    return original(value,company_id=company_id,design_uom_id=design_uom_id,physical_uom_id=physical_uom_id)
