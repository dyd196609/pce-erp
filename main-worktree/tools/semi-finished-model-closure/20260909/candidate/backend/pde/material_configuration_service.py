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
        if source_binding.thickness_semantic == "UNKNOWN":
            blockers.append("THICKNESS_SEMANTIC_UNKNOWN")
        # No geometry implementation here: former 3 x 12 lookup is never invoked.
        return {"status": "BLOCKED" if blockers else "DEFERRED_GEOMETRY_NOT_AUTHORIZED",
                "materialId": None, "allowedMaterials": allowed, "blockers": blockers,
                "geometryExecuted": False, "quantity": None}

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

