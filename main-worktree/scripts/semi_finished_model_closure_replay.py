"""Replay only the two user-validated real configurations in an isolated SQLite."""
import json
from decimal import Decimal
from pathlib import Path
from semi_finished_model_closure_runtime import bootstrap, ROOT, OUT, ISO

bootstrap()
from django.core import serializers
from django.db import transaction, connection
from masterdata.models import Material, MaterialCategory, ExternalIdentity
from pde.models import (MaterialConfiguration, MaterialConfigurationAttribute, MaterialConfigurationSourceBinding,
    MaterialFamilyAllowedMaterial, EngineeringSourceRecord, ProductBOM, BOMVersion, BOMItem,
    TemplateMaterialRequirementSlot, ComponentMaterialRequirement, MaterialSelectionCandidate,
    EngineeringMaterialCalculationResult)
from pde.material_configuration_service import MaterialConfigurationService
from pde.material_configuration_serializers import MaterialConfigurationSerializer, MaterialCompositionSlotSerializer
from pde.semi_finished_configuration_preview import build_projection

DECISION = "USER_ATTACHMENT_59b3cc64_SHA256_802C9E1CA211D4802D19107607BB0AB67F2E9165649589624E4D2779E2825E48"
source = json.loads((ROOT / "backend/pde/semi_finished_configuration_source.json").read_text(encoding="utf-8"))
formal = json.loads((OUT / "FORMAL_BEFORE.json").read_text(encoding="utf-8"))["formal"]
preview = build_projection(source, formal, 1)
accepted = [r for r in preview["configurations"] if r["sourceCode"] in {"BTKF2601001", "QSFB4601001"}]
assert len(accepted) == 2
source_sha = source["sourceFiles"][0]["sha256"]
five = [("SUBSTRATE", "坯板", "substrate", "CALCULATED"), ("VENEER", "木皮", "veneer", "CALCULATED"),
        ("EDGE", "封边材料", None, "CALCULATED"), ("SURFACE_PAINT", "表面 / 油漆材料", "paintKind", "UNKNOWN"),
        ("OTHER_FIXED", "其它固定组成（待明确）", None, "UNKNOWN")]
created = []


def keep(obj):
    obj.full_clean()
    obj.save()
    created.append(obj)
    return obj


with transaction.atomic():
    assert MaterialConfiguration.objects.count() == 0, "Replay already exists; do not duplicate it"
    family = keep(MaterialCategory(code="SUBSTRATE-SOURCE13-R2", name="实木多层板", company_id=1, is_active=True))
    family_identity = keep(ExternalIdentity(organization_id=1, source_system="USER_SOURCE_EXCEL",
        source_type="EXCEL", source_object_type="SUBSTRATE_MATERIAL_FAMILY", external_id="13坯板.xlsx|坯板|ROW:2",
        target_entity_type="material-categories", target_entity_id=str(family.pk), mapping_status="MATCH",
        source_fingerprint=next(r["sha256"] for r in source["sourceFiles"] if r["file"] == "13坯板.xlsx"),
        audit_metadata={"scope": "ISOLATED_REPLAY", "userDecision": DECISION, "sourceName": "实木多层板", "generatedTechnicalCode": family.code}))
    source_record = keep(EngineeringSourceRecord(company_id=1, source_no="SF-CONFIG-REAL71-ISOLATED",
        source_name="工程拆单及订单排产数据核算方式.xlsx", source_type="controlled_import",
        source_version="SOURCE_SHA256", source_payload={"scope": "ISOLATED_REPLAY", "sourceSha256": source_sha,
            "sheets": ["三合一生产单", "房门单"], "userDecision": DECISION}, content_hash=source_sha, status="confirmed"))
    cases = []
    for previous in accepted:
        code = previous["sourceCode"]
        material_id = previous["identity"]["formal"]["id"]
        identity_id = previous["identity"]["evidence"][0]["id"]
        config = keep(MaterialConfiguration(company_id=1, material_id=material_id, source_identity_id=identity_id,
            configuration_code=code, source_validated=True, validation_reference=DECISION))
        attrs = {}
        for item in previous["attributes"]:
            key, raw = item["key"], item["sourceValue"]
            kwargs = {"configuration": config, "attribute_kind": key, "source_value": raw,
                "canonical_value": raw, "knowledge_state": "NOT_APPLICABLE", "resolution_status": "UNRESOLVED",
                "source_file": item["sourceFile"], "source_sha256": next(x["sha256"] for x in source["sourceFiles"] if x["file"] == item["sourceFile"]),
                "source_sheet": item["sourceSheet"], "source_cell": item["sourceCell"], "source_validated": True,
                "validation_reference": DECISION, "provenance": {"sourceTrace": item.get("sourceTrace", []),
                    "dependencyTrace": item.get("dependencyTrace", []), "scope": "ISOLATED_REPLAY", "businessValidationIsNotProcurementResolution": True}}
            if key == "paintProcess":
                assert len(item["formalTargets"]) == 1
                kwargs.update(process_type_id=item["formalTargets"][0]["id"], resolution_status="RESOLVED")
                if code == "BTKF2601001":
                    kwargs["canonical_value"] = "半透开放工艺"
                    kwargs["provenance"]["canonicalMappingAuthority"] = DECISION
            elif key == "substrate":
                kwargs.update(material_family=family, resolution_status="RESOLVED")
            elif key in {"splice", "skinFeel"}:
                kwargs.update(knowledge_state={"是": "KNOWN_TRUE", "否": "KNOWN_FALSE"}.get(raw, "UNKNOWN"), resolution_status="NOT_APPLICABLE")
            elif key == "uom":
                assert len(item["formalTargets"]) == 1
                kwargs.update(uom_id=item["formalTargets"][0]["id"], resolution_status="RESOLVED",
                    canonical_value=item["formalTargets"][0]["name"])
                kwargs["provenance"]["canonicalSource"] = "EXISTING_FORMAL_MATERIAL_BASE_UOM"
            attrs[key] = keep(MaterialConfigurationAttribute(**kwargs))
        bindings = []
        for row in previous["engineeringRows"]:
            bindings.append(keep(MaterialConfigurationSourceBinding(source_record=source_record,
                source_sheet=row["sheet"], source_row=row["row"], configuration=config,
                thickness_value=None if row["thickness"] is None else Decimal(str(row["thickness"])),
                thickness_semantic="UNKNOWN", source_lineage={"scope": "ISOLATED_REPLAY", "sourceSha256": source_sha,
                    "sourceCodeCell": f"B{row['row']}", "rawEngineeringRow": row, "userDecision": DECISION})))
        roles = []
        for role, label, attrkey, quantity_mode in five:
            attr = attrs.get(attrkey)
            slot = keep(TemplateMaterialRequirementSlot(material_configuration=config, configuration_attribute=attr,
                slot_code=role, slot_name=label, material_category=family if role == "SUBSTRATE" else None,
                quantity_mode=quantity_mode, composition_channel="FIXED_COMPOSITION",
                selection_constraints={"scope": "ISOLATED_REPLAY", "sourceBusinessIdentity": attr.source_value if attr else None,
                    "roleApplicability": "SOURCE_RELATION_VALIDATED" if role in {"SUBSTRATE", "VENEER"} else "UNDETERMINED_REQUIREMENT_ROLE",
                    "lossRate": None, "perEdgeAllowance": None, "provenance": DECISION}))
            roles.append(MaterialConfigurationService.role_preview(slot, bindings[0]))
        header = keep(ProductBOM(company_id=1, applicability_scope="MATERIAL_CONFIGURATION", material_configuration=config,
            bom_code=f"ISOLATED-SF-{code}", name=f"{code} 组成载体隔离验证", status="draft", is_active=False))
        version = keep(BOMVersion(bom=header, bom_version="SYSTEM_INITIAL_VERSION", status="draft",
            applicability={"scope": "ISOLATED_REPLAY", "versionProvenance": "SYSTEM_INITIAL_VERSION", "manufacturingApproved": False}))
        cases.append({"configurationCode": code, "configurationId": config.pk, "formalMaterialId": material_id,
            "sourceIdentityId": identity_id, "sourceValidated": True, "inheritedRows": len(bindings),
            "canonicalConfiguration": MaterialConfigurationSerializer(config).data,
            "roles": roles, "bomHeaderId": header.pk, "bomVersionId": version.pk,
            "bomItemCount": 0, "materialRequirementGenerated": 0,
            "replayStatus": "PASS", "businessCalculationStatus": "BLOCKED"})
    assert MaterialConfiguration.objects.count() == 2
    assert MaterialConfigurationSourceBinding.objects.count() == 71
    assert MaterialConfigurationAttribute.objects.count() == 16
    assert TemplateMaterialRequirementSlot.objects.count() == 10
    assert MaterialFamilyAllowedMaterial.objects.count() == 0
    assert not ComponentMaterialRequirement.objects.exists()
    assert not MaterialSelectionCandidate.objects.exists()
    assert not EngineeringMaterialCalculationResult.objects.exists()
    assert not BOMItem.objects.exists()
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA foreign_key_check")
        assert not cursor.fetchall()

from semi_finished_model_closure_serialization import encoder
fixture = serializers.serialize("json", created, indent=2, cls=encoder())
(OUT / "REAL_CASE_ROUNDTRIP_FIXTURE.json").write_text(fixture + "\n", encoding="utf-8")
(OUT / "ISOLATED_CREATED_OBJECTS.json").write_text(json.dumps([{ "model": x._meta.label, "pk": x.pk} for x in created], indent=2) + "\n", encoding="utf-8")
report = {"schemaVersion": "PCE-MATERIAL-CONFIGURATION-ISOLATED-1", "status": "PASS", "scope": "ISOLATED_REPLAY_NOT_PRODUCTION",
    "sourceBundleSha256": "6A2D7A5D8E2DAA04E212DEFFD1C37F771D7CDDA806DFCF8105E373D9C72985E6",
    "userDecision": DECISION, "cases": cases, "sourceBusinessFamily": "实木多层板", "isolatedFamilyId": family.pk,
    "allowedMaterialCount": 0, "allowedSpecificationCount": 0, "userValidatedConfigurations": 2,
    "otherValidConfigurationsUserValidated": False, "instanceInheritance": {"BTKF2601001": 63, "QSFB4601001": 8},
    "unknownThicknessRows": 63, "unknownFactsPreserved": True, "materialRequirementsGenerated": 0,
    "productionBusinessWrite": 0, "productionMigrationApplied": False, "domainRuleFormalization": "NOT_ENTERED"}
(OUT / "ISOLATED_REPLAY.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"replay": "PASS", "configs": 2, "attributes": 16, "sourceBindings": 71,
                  "roles": 10, "bomHeaders": 2, "bomVersions": 2, "bomItems": 0, "generatedRequirements": 0}, ensure_ascii=False))
