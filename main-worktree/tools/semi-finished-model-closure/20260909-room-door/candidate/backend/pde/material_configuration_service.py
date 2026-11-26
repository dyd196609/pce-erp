"""Configuration/quantity readiness, not a formula engine or production writer."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from .models import MaterialFamilyAllowedMaterial


class MaterialConfigurationService:
    RULE_ENTRY = "pde.EngineeringCalculationService.execute"
    REQUIREMENT_CARRIER = "pde.ComponentMaterialRequirement"

    @staticmethod
    def resolve_substrate(configuration, source_binding):
        if source_binding.configuration_id != configuration.pk:
            raise ValidationError("工程行必须继承同一配置")
        attribute = configuration.attributes.get(attribute_kind="substrate")
        blockers = []
        if not configuration.source_validated:
            blockers.append("CONFIGURATION_NOT_USER_VALIDATED")
        if not attribute.material_family_id:
            blockers.append("SUBSTRATE_FAMILY_UNRESOLVED")
            allowed = []
        else:
            allowed = list(MaterialFamilyAllowedMaterial.objects.filter(
                family_id=attribute.material_family_id, source_validated=True,
                specification_validated=True, material__is_active=True,
                material__company_id=configuration.company_id,
            ).values("id", "material_id", "length_mm", "width_mm", "thickness_mm"))
            if not allowed:
                blockers.append("ALLOWED_MATERIAL_SPECIFICATION_SET_UNRESOLVED")
        if source_binding.thickness_semantic not in {"BOARD_MATCH_INPUT", "RAW_BOARD_THICKNESS"}:
            blockers.append("THICKNESS_SEMANTIC_UNKNOWN")
        if blockers:
            return {"status":"BLOCKED", "materialId":None,"allowedMaterials":allowed,"blockers":blockers,"geometryExecuted":False,"quantity":None}
        exact=[r for r in allowed if r["thickness_mm"] == source_binding.thickness_value]
        raw=source_binding.source_lineage.get("rawEngineeringRow", {})
        length,width=raw.get("length"),raw.get("width")
        if not exact:
            blockers.append("PROCUREMENT_MATERIAL_MASTER_DATA_GAP")
        if length is None or width is None:
            blockers.append("COMPONENT_GEOMETRY_MISSING")
        if blockers:
            return {"status":"BLOCKED","materialId":None,"allowedMaterials":allowed,"blockers":blockers,"geometryExecuted":False,"quantity":None}
        l,w=Decimal(str(length)),Decimal(str(width))
        if min(l,w)<=0:
            raise ValidationError("组件长宽必须为正数")
        direct=[r for r in exact if r["length_mm"]>=l and r["width_mm"]>=w]
        rotated=[r for r in exact if (r["length_mm"]>=w and r["width_mm"]>=l) or r in direct]
        # Dimensions form a partial order. Equal-size materials remain ambiguous.
        minimum=lambda rows:[r for r in rows if not any(z["length_mm"]<=r["length_mm"] and z["width_mm"]<=r["width_mm"] and
            (z["length_mm"]<r["length_mm"] or z["width_mm"]<r["width_mm"]) for z in rows)]
        direct,rotated=minimum(direct),minimum(rotated)
        if {r["material_id"] for r in direct}!={r["material_id"] for r in rotated}:
            blockers.append("ROTATION_PERMISSION_PENDING")
        if len(direct)!=1:
            blockers.append("NO_EXACT_GEOMETRY_SPEC" if not direct else "AMBIGUOUS_MINIMUM_SPEC")
        return {"status":"BLOCKED" if blockers else "MATCHED_PREVIEW", "materialId":None if blockers else direct[0]["material_id"],
            "allowedMaterials":allowed,"exactThicknessMaterialIds":[r["material_id"] for r in exact],
            "minimumSpecMaterialIds":[r["material_id"] for r in direct],"blockers":blockers,"geometryExecuted":True,"quantity":None}

    @classmethod
    def role_preview(cls, slot, source_binding=None):
        slot.full_clean()
        config = slot.material_configuration
        blockers = []
        attr = slot.configuration_attribute
        if not config.source_validated:
            blockers.append("CONFIGURATION_NOT_USER_VALIDATED")
        if not slot.fixed_material_id:
            blockers.append("PROCUREMENT_MATERIAL_IDENTITY_UNRESOLVED")
        if slot.quantity_mode == "CALCULATED":
            if not slot.engineering_rule_id:
                blockers.append("MATERIAL_QUANTITY_RULE_NOT_BOUND")
            elif slot.engineering_rule.status != "released":
                blockers.append("MATERIAL_QUANTITY_RULE_NOT_RELEASED")
            elif slot.engineering_rule.specification.get("applicability", {}).get("scope") == "validation":
                blockers.append("VALIDATION_RULE_NOT_A_PRODUCTION_MATERIAL_RULE")
        elif slot.quantity_mode == "MANUAL" and slot.fixed_quantity is None:
            blockers.append("MANUAL_QUANTITY_PENDING")
        elif slot.quantity_mode == "UNKNOWN":
            blockers.append("QUANTITY_MODE_UNKNOWN")
        resolver = None
        if slot.slot_code == "SUBSTRATE" and source_binding:
            resolver = cls.resolve_substrate(config, source_binding)
            blockers.extend(resolver["blockers"])
        return {"slotId": slot.pk, "roleCode": slot.slot_code, "roleLabel": slot.slot_name,
                "owner":"MATERIAL_CONFIGURATION", "roleStatus":"VALIDATED", "ruleReadiness":"PENDING" if not slot.engineering_rule_id else "BLOCKED",
                "configurationId": config.pk, "configurationCode": config.configuration_code,
                "sourceBusinessIdentity": attr.source_value if attr else None,
                "canonicalValue": attr.canonical_value if attr else None,
                "formalMaterialId": slot.fixed_material_id,
                "formalFamilyId": slot.material_category_id,
                "sourceValidated": bool(attr and attr.source_validated),
                "quantityMode": slot.quantity_mode, "quantityModeLabel": slot.get_quantity_mode_display(),
                "quantity": None if blockers or slot.quantity_mode == "CALCULATED" else str(slot.fixed_quantity),
                "ruleEntry": cls.RULE_ENTRY, "ruleId": slot.engineering_rule_id,
                "ruleVersion": slot.engineering_rule.version if slot.engineering_rule_id else None,
                "resolutionEntry": "MaterialConfigurationService.resolve_substrate" if slot.slot_code == "SUBSTRATE" else "ComponentMaterialRequirement → MaterialSelectionCandidate",
                "requirementCarrier": cls.REQUIREMENT_CARRIER, "resolver": resolver,
                "status": "BLOCKED" if blockers else "READY_FOR_EXISTING_REQUIREMENT_SERVICE",
                "blockers": sorted(set(blockers)), "materialRequirementGenerated": False,
                "scope": "ISOLATED_REPLAY_NOT_PRODUCTION"}

    @classmethod
    def component_edge_preview(cls, requirement):
        requirement.full_clean()
        if requirement.requirement_kind != "edge_banding" or not requirement.breakdown_item_id:
            raise ValidationError("该回放入口仅用于真实来源工程组件的封边需求")
        component=requirement.breakdown_item
        binding=component.source_binding
        edge=requirement.source_lineage.get('directNetEvidence') if requirement.requirement_source_mode=='DIRECT_CALCULATED' else component.attributes.get("edgePreview")
        if not edge:
            raise ValidationError("缺少来源净量与边段证据")
        from .material_loss_policy_service import MaterialLossPolicyService
        loss=MaterialLossPolicyService.preview(requirement)
        blockers=[]
        if requirement.material_id is None: blockers.append("EDGE_MATERIAL_IDENTITY_UNRESOLVED")
        if requirement.per_edge_allowance_mm is None: blockers.append("PER_EDGE_ALLOWANCE_PENDING")
        if not requirement.engineering_rule_id: blockers.append("RULE_NOT_RELEASED")
        return {**edge,"componentId":component.pk,"requirementId":requirement.pk,
            "requirementSourceMode":requirement.requirement_source_mode,
            "netLengthM":str(requirement.net_quantity),"grossLengthM":loss['grossLengthM'],
            "segments":requirement.edge_segment_trace,"edgeCount":loss['edgeCount'],
            "lossPolicyId":requirement.loss_policy_id,"lossMethod":requirement.loss_policy.method,
            "totalAllowanceM":loss['totalAllowanceM'],"grossStatus":loss['status'],
            "sourceBindingId":binding.pk,"configurationId":binding.configuration_id,
            "owner":"ENGINEERING_COMPONENT","carrier":"pde.ComponentMaterialRequirement",
            "quantityMode":requirement.quantity_mode,"materialId":requirement.material_id,
            "quantity":None if requirement.quantity is None else str(requirement.quantity),
            "perEdgeAllowanceMm":None if requirement.per_edge_allowance_mm is None else str(requirement.per_edge_allowance_mm),
            "uomId":requirement.uom_id,"baseUom":requirement.uom.code,
            "status":"BLOCKED" if blockers else "READY_FOR_EXISTING_RULE_ENGINE","blockers":blockers,
            "scope":"ISOLATED_REPLAY_NOT_PRODUCTION","formalProcurementRequirementGenerated":False}
