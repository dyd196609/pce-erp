"""Isolated contract tests; invalid examples are TEST_ONLY and always rolled back."""
import hashlib
import json
import shutil
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path
from semi_finished_model_closure_runtime import ROOT, OUT, ISO, bootstrap

mode = sys.argv[1] if len(sys.argv) > 1 else "tests"
db_name = {"tests": "isolated.sqlite3", "roundtrip": "roundtrip.sqlite3", "rollback": "rollback.sqlite3"}[mode]
if mode != "tests" and len(sys.argv) > 2:
    attempt = sys.argv[2]
    assert attempt.isalnum()
    db_name = f"{mode}-{attempt}.sqlite3"
if mode != "tests":
    target = (ISO / db_name).resolve()
    assert target.parent == ISO.resolve() and not target.exists()
    shutil.copy2(ISO / "isolated.sqlite3", target)
bootstrap(db_name)
from django.apps import apps
from django.core import serializers
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection, transaction, IntegrityError
from pde.models import *
from pde.material_configuration_service import MaterialConfigurationService
from pde.material_configuration_serializers import MaterialConfigurationSerializer

results = []


def check(name, value):
    assert value, name
    results.append({"check": name, "status": "PASS"})


def invalid(name, fn, exceptions=(ValidationError, IntegrityError)):
    try:
        with transaction.atomic():
            fn()
    except exceptions:
        results.append({"check": name, "status": "PASS", "fixtureClass": "TECHNICAL_NEGATIVE_ONLY_NOT_REAL"})
    else:
        raise AssertionError(name)


def business_hashes(db_path):
    with sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True) as con:
        con.execute("PRAGMA query_only=ON")
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                  if r[0] not in {"django_migrations", "sqlite_sequence"}]
        return {table: hashlib.sha256(json.dumps(sorted(con.execute(f'SELECT * FROM "{table}"').fetchall(), key=repr), default=str).encode()).hexdigest()
                for table in tables}


if mode == "tests":
    configs = list(MaterialConfiguration.objects.order_by("configuration_code"))
    btkf, qsfb = configs
    check("two validated config identities only", [c.configuration_code for c in configs] == ["BTKF2601001", "QSFB4601001"])
    check("63 plus 8 unique source inheritance", [c.source_bindings.count() for c in configs] == [63, 8])
    check("all real layer semantics remain unknown", MaterialConfigurationSourceBinding.objects.exclude(thickness_semantic="UNKNOWN").count() == 0)
    check("source thickness is null for door wall thickness", qsfb.source_bindings.exclude(thickness_value=None).count() == 0)
    check("16 typed attributes", MaterialConfigurationAttribute.objects.count() == 16)
    check("BTKF unknown booleans preserved", list(btkf.attributes.filter(attribute_kind__in=["splice", "skinFeel"]).values_list("knowledge_state", flat=True)) == ["UNKNOWN", "UNKNOWN"])
    check("QSFB false booleans preserved", set(qsfb.attributes.filter(attribute_kind__in=["splice", "skinFeel"]).values_list("knowledge_state", flat=True)) == {"KNOWN_FALSE"})
    process = btkf.attributes.get(attribute_kind="paintProcess")
    check("source canonical formal process kept separately", (process.source_value, process.canonical_value, process.process_type_id) == ("半透工艺", "半透开放工艺", 2))
    check("validated source is not procurement identity", all(c.attributes.filter(attribute_kind__in=["color", "veneer"], source_validated=True, resolution_status="UNRESOLVED", formal_material=None).count() == 2 for c in configs))
    check("explicit family without guessed membership", btkf.attributes.get(attribute_kind="substrate").material_family.name == "实木多层板" and MaterialFamilyAllowedMaterial.objects.count() == 0)
    invalid("duplicate configuration identity rejected", lambda: MaterialConfiguration.objects.create(company_id=1, material_id=btkf.material_id, source_identity_id=btkf.source_identity_id, configuration_code=btkf.configuration_code))
    invalid("cross-company configuration rejected", lambda: MaterialConfiguration(company_id=999, material_id=btkf.material_id, source_identity_id=btkf.source_identity_id, configuration_code="TECHNICAL_NEGATIVE").clean())
    invalid("invalid controlled boolean rejected by DB", lambda: MaterialConfigurationAttribute.objects.filter(configuration=btkf, attribute_kind="splice").update(knowledge_state="false"))
    attribute = btkf.attributes.get(attribute_kind="splice")
    attribute.canonical_value = "否"
    invalid("UNKNOWN cannot imply false", attribute.full_clean)
    color = btkf.attributes.get(attribute_kind="color")
    color.formal_material_id = btkf.material_id
    color.resolution_status = "RESOLVED"
    invalid("color constraint cannot masquerade as material", color.full_clean)
    invalid("source row cannot inherit second configuration", lambda: MaterialConfigurationSourceBinding.objects.create(source_record=btkf.source_bindings.first().source_record,
        source_sheet="三合一生产单", source_row=7, configuration=qsfb, source_lineage={"class": "TECHNICAL_NEGATIVE"}))
    for cfg in configs:
        rows = [MaterialConfigurationService.role_preview(s, cfg.source_bindings.first()) for s in cfg.composition_slots.all()]
        check(f"{cfg.configuration_code} five composition roles", len(rows) == 5)
        check(f"{cfg.configuration_code} blocked quantities are null", all(r["status"] == "BLOCKED" and r["quantity"] is None and not r["materialRequirementGenerated"] for r in rows))
        substrate = next(r for r in rows if r["roleCode"] == "SUBSTRATE")
        check(f"{cfg.configuration_code} geometry remains deferred", not substrate["resolver"]["geometryExecuted"] and "THICKNESS_SEMANTIC_UNKNOWN" in substrate["blockers"])
        check(f"{cfg.configuration_code} one formula engine entry", {r["ruleEntry"] for r in rows} == {"pde.EngineeringCalculationService.execute"})
        encoded = json.loads(json.dumps(MaterialConfigurationSerializer(cfg).data))
        check(f"{cfg.configuration_code} API serializer identity and attributes", encoded["configuration_code"] == cfg.configuration_code and len(encoded["attributes"]) == 8)
    bom = ProductBOM.objects.get(material_configuration=btkf)
    version = bom.versions.get()
    check("canonical BOM targets config without fake Product", bom.product_id is None and bom.product_category_id is None and version.product_id is None and version.product_version_id is None)
    invalid("BOM cannot mix material and configuration targets", lambda: ProductBOM.objects.filter(pk=bom.pk).update(material_id=btkf.material_id))
    invalid("BOM config owner company required", lambda: ProductBOM(applicability_scope="MATERIAL_CONFIGURATION", material_configuration=btkf).clean())
    check("three BOM quantity modes and nullable quantity", set(v for v, _ in BOMItem._meta.get_field("quantity_mode").choices) == {"FIXED", "CALCULATED", "MANUAL"} and BOMItem._meta.get_field("quantity").null)
    for quantity in (None, Decimal("0"), Decimal("-1")):
        invalid(f"FIXED rejects {quantity}", lambda q=quantity: BOMItem.objects.create(bom_version=version, line_no=999, material_id=btkf.material_id, uom_id=btkf.material.base_uom_id, quantity_mode="FIXED", quantity=q))
    invalid("CALCULATED rejects placeholder one", lambda: BOMItem.objects.create(bom_version=version, line_no=999, material_id=btkf.material_id, uom_id=btkf.material.base_uom_id, quantity_mode="CALCULATED", quantity=Decimal("1")))
    for quantity_mode in ("CALCULATED", "MANUAL"):
        with transaction.atomic():
            item = BOMItem(bom_version=version, line_no=999, material_id=btkf.material_id, uom_id=btkf.material.base_uom_id, quantity_mode=quantity_mode, quantity=None)
            item.full_clean()
            item.save()
            check(f"{quantity_mode} NULL persisted and roundtripped (TEST_ONLY rolled back)", BOMItem.objects.get(pk=item.pk).quantity is None)
            transaction.set_rollback(True)
    slot = btkf.composition_slots.get(slot_code="VENEER")
    original_rule = slot.engineering_rule_id
    slot.engineering_rule_id = 1
    check("old validation-only G1 rule not used as material rule", "VALIDATION_RULE_NOT_A_PRODUCTION_MATERIAL_RULE" in MaterialConfigurationService.role_preview(slot)["blockers"])
    slot.engineering_rule_id = original_rule
    slot.configuration_attribute = btkf.attributes.get(attribute_kind="paintProcess")
    invalid("paint process is not paint consumption", slot.full_clean)
    check("no fake material requirements or BOM items", all(m.objects.count() == 0 for m in (ComponentMaterialRequirement, MaterialSelectionCandidate, EngineeringMaterialCalculationResult, BOMItem)))
    check("frozen rules count", EngineeringRuleDefinition.objects.count() == 4)
    check("routing version step preserved", (Routing.objects.count(), RoutingVersion.objects.count(), RoutingStep.objects.count()) == (42, 42, 1137))
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM system_process")
        check("process count preserved", cur.fetchone()[0] == 33)
        cur.execute("PRAGMA foreign_key_check")
        check("foreign key integrity", not cur.fetchall())
    call_command("check", verbosity=0)
    check("Django system check", True)

elif mode == "roundtrip":
    objects = list(serializers.deserialize("json", (OUT / "REAL_CASE_ROUNDTRIP_FIXTURE.json").read_text(encoding="utf-8")))
    before = business_hashes(ISO / db_name)
    with transaction.atomic():
        for obj in objects:
            obj.save()
    after = business_hashes(ISO / db_name)
    check("serializer real-object full roundtrip", before == after)
    check("roundtrip object count", len(objects) == 106)
    check("roundtrip 71 inherited rows", MaterialConfigurationSourceBinding.objects.count() == 71)

elif mode == "rollback":
    # Only candidate-created PKs are removed, only in this explicit rehearsal copy.
    created = json.loads((OUT / "ISOLATED_CREATED_OBJECTS.json").read_text(encoding="utf-8"))
    assert Path(connection.settings_dict["NAME"]).resolve() == (ISO / db_name).resolve()
    assert db_name.startswith("rollback")
    check("rollback evidence archived", (OUT / "REAL_CASE_ROUNDTRIP_FIXTURE.json").stat().st_size > 0)
    with transaction.atomic():
        for item in reversed(created):
            model = apps.get_model(item["model"])
            # Explicit PK-only cleanup avoids unrelated undeployed Planning ORM
            # collectors. SQLite FK enforcement remains ON; no cascade guessing.
            model.objects.get(pk=item["pk"])
            with connection.cursor() as cursor:
                cursor.execute(f'DELETE FROM "{model._meta.db_table}" WHERE id=%s', [item["pk"]])
                assert cursor.rowcount == 1
    call_command("migrate", "pde", "0022_manufacturing_definition_applicability", interactive=False, verbosity=1)
    # Django intentionally leaves content types/default permissions after reversing
    # CreateModel. Remove only metadata created for our four candidate tables in
    # this rehearsal copy, after archiving the exact IDs and verifying ownership.
    candidate_models = {"materialconfiguration", "materialconfigurationattribute", "materialfamilyallowedmaterial", "materialconfigurationsourcebinding"}
    with sqlite3.connect((ROOT / "backend/db.sqlite3").as_uri() + "?mode=ro", uri=True) as original:
        original_content_ids = {r[0] for r in original.execute("SELECT id FROM django_content_type")}
        original_permission_ids = {r[0] for r in original.execute("SELECT id FROM auth_permission")}
    metadata = []
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute("SELECT id,model FROM django_content_type WHERE app_label='pde'")
        for content_id, model_name in cur.fetchall():
            if model_name not in candidate_models:
                continue
            assert content_id not in original_content_ids
            cur.execute("SELECT id FROM auth_permission WHERE content_type_id=%s", [content_id])
            permission_ids = [r[0] for r in cur.fetchall()]
            assert not (set(permission_ids) & original_permission_ids)
            metadata.append({"model": model_name, "contentTypeId": content_id, "permissionIds": permission_ids})
            cur.execute("DELETE FROM auth_permission WHERE content_type_id=%s", [content_id])
            cur.execute("DELETE FROM django_content_type WHERE id=%s", [content_id])
    (OUT / "ROLLBACK_METADATA_CLEANUP.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    check("rollback candidate metadata only", len(metadata) == 4)
    before, after = business_hashes(ROOT / "backend/db.sqlite3"), business_hashes(ISO / db_name)
    check("rollback preserves all original business table contents", before == after)
    with connection.cursor() as cur:
        cur.execute("PRAGMA foreign_key_check")
        check("rollback foreign key integrity", not cur.fetchall())

(OUT / f"{mode.upper()}_RESULTS.json").write_text(json.dumps({"status": "PASS", "database": str(connection.settings_dict["NAME"]), "checks": results,
    "productionBusinessWrite": 0, "fixturesAreNotBusinessFacts": True}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"mode": mode, "status": "PASS", "checks": len(results)}, ensure_ascii=False))
