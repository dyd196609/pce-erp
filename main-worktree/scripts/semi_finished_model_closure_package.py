"""Package the tested canonical candidate without applying it to production."""
import ast
import difflib
import json
import shutil
import sqlite3
import subprocess
from collections import Counter
from pathlib import Path
from semi_finished_model_closure_audit import ROOT, OUT, save, sha, git, classes, HISTORY

PACKAGE = ROOT / "tools/semi-finished-model-closure/20260909"
CANDIDATE = ROOT / ".runtime/semi-finished-model-closure-20260909/backend"
BASELINE = json.loads((OUT / "BASELINE.json").read_text(encoding="utf-8"))


def main():
    PACKAGE.mkdir(parents=True, exist_ok=True)
    paths = ["pde/models.py", "pde/material_configuration_models.py",
             "pde/material_configuration_service.py", "pde/material_configuration_serializers.py",
             "pde/order_engineered_product_service.py",
             "pde/migrations/0024_restore_material_contract_state.py",
             "pde/migrations/0025_material_configuration_applicability_quantity.py"]
    baseline_model = ROOT / "backend/pde/models.py"
    assert sha(baseline_model) == BASELINE["files"][str(baseline_model)]
    manifest = {"status": "ISOLATED_TESTED_NOT_PRODUCTION_APPLIED", "productionApplied": False,
                "sourceHead": BASELINE["gitHead"], "target": "canonical pde models and original db_table names",
                "baselineProductionModelsSha256": sha(baseline_model),
                "baselineDatabaseSha256": BASELINE["files"][str(ROOT / "backend/db.sqlite3")],
                "files": [], "rules": "No production apply runner. Separate authorization and schema preflight required."}
    for relative in paths:
        src = CANDIDATE / relative
        dest = PACKAGE / "candidate/backend" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        assert sha(src) == sha(dest)
        manifest["files"].append({"canonicalPath": "backend/" + relative,
                                  "packagePath": str(dest.relative_to(PACKAGE)), "sha256": sha(dest)})
    # A reviewable delta is generated mechanically from the frozen production model.
    patch = "".join(difflib.unified_diff(
        baseline_model.read_bytes().decode("utf-8").splitlines(keepends=True),
        (CANDIDATE / "pde/models.py").read_bytes().decode("utf-8").splitlines(keepends=True),
        fromfile="a/backend/pde/models.py", tofile="b/backend/pde/models.py"))
    patch_path = PACKAGE / "canonical-models.patch"
    patch_path.write_bytes(patch.encode("utf-8"))
    result = subprocess.run(["git", "-c", f"safe.directory={ROOT.as_posix()}", "apply", "--check", str(patch_path)],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    manifest["patchCheck"] = {"status": "PASS", "readOnly": True, "sha256": sha(patch_path)}
    (PACKAGE / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save("PACKAGE_VERIFICATION.json", manifest)

    # Preserve API/serializer evidence from the same historical branch as the models.
    history_files = ["production_foundation_service.py", "views.py", "urls.py", "formal_structure_readback.py"]
    trace = {}
    names = ["ComponentMaterialRequirement", "MaterialSelectionCandidate", "EngineeringMaterialCalculationResult", "TemplateMaterialRequirementSlot"]
    for name in history_files:
        content = git("show", f"{HISTORY}:backend/pde/{name}")
        (OUT / "historical" / name).write_text(content, encoding="utf-8")
        trace[name] = {"sha256": sha(OUT / "historical" / name),
                       "references": {key: [i for i, line in enumerate(content.splitlines(), 1) if key in line] for key in names}}
    save("HISTORICAL_API_TRACE.json", {"historyRef": HISTORY, "files": trace,
        "componentRequirement": "Historical ENTITY_CONFIG -> shared a1-foundation/<entity> view -> generic model-field serialization; production current ENTITY_CONFIG does not register this orphan model.",
        "remainingThree": "Historical ORM/service/model tests exist; not separately registered as generic CRUD entities or dedicated serializers in inspected historical files. Do not claim full deployed API recovery.",
        "candidateScope": "Original four models plus seven FK dependency models, original structure read service and new typed serializers, isolated only. No production write API."})

    formal = json.loads((OUT / "FORMAL_BEFORE.json").read_text(encoding="utf-8"))
    source = json.loads((ROOT / "backend/pde/semi_finished_configuration_source.json").read_text(encoding="utf-8"))
    with sqlite3.connect((ROOT / "backend/db.sqlite3").as_uri()+"?mode=ro", uri=True) as con:
        con.execute("PRAGMA query_only=ON")
        con.row_factory = sqlite3.Row
        identities = [dict(row) for row in con.execute("SELECT * FROM masterdata_external_identity")]
        materials = [dict(row) for row in con.execute("SELECT * FROM material")]
        categories = [dict(row) for row in con.execute("SELECT * FROM material_category")]
    wanted = ["展厅样品无把手门", "45丝半透黑胡桃花纹实木拼", "柚木直纹，封闭/LC-M045", "柚木", "实木多层板"]
    save("FORMAL_CONTROLLED_IDENTITY_AUDIT.json", {
        "externalIdentityCount": len(identities),
        "externalIdentityObjectTypes": dict(Counter(x["source_object_type"] for x in identities)),
        "exactMaterialMatches": {name: [{"id": m["id"], "code": m["code"], "name": m["name"]} for m in materials if m["name"] == name] for name in wanted},
        "controlledCatalogIdentities": [x for x in identities if any(x["external_id"].startswith(prefix) for prefix in ("04色板.xlsx|", "12木皮.xlsx|", "13坯板.xlsx|"))],
        "existingConfigurationMaterialIdentities": [x for x in identities if x["id"] in (51, 61)],
        "materialCategoryCount": len(categories), "exactFamilyCategory": [x for x in categories if x["name"] == "实木多层板"],
        "method": "Inspect actual external_id/target_entity_type/target_entity_id/mapping_status/source_fingerprint/audit_metadata, not invented source_name columns. Exact Material names and source catalogue identity prefixes; source metadata is evidence, not a separate controlled procurement mapping. No substring/fuzzy/geometry promotion."})
    rough_path = ROOT / "backend/masterdata/group3_comparison_source.json"
    rough = json.loads(rough_path.read_text(encoding="utf-8"))["engineeringBreakdown"]
    rows = [r for r in rough["rows"] if r["materialCode"] in ("BTKF2601001", "QSFB4601001")]
    save("ROUGH_STRUCTURE_RECHECK.json", {"source": str(rough_path), "sha256": sha(rough_path),
        "scope": "engineeringBreakdown only; no 08 joining", "rows": rows,
        "countByConfiguration": dict(Counter(r["materialCode"] for r in rows)),
        "fields": sorted({key for r in rows for key in r}),
        "layerDecompositionPresent": False, "thicknessAutomaticallyResolved": 0,
        "reason": "Source contains category/space/product/model/dimensions, not constituent board/veneer/glue/allowance thickness equations. Door wall thickness is not substrate thickness."})
    models = classes((ROOT / "backend/pde/models.py").read_text(encoding="utf-8"))
    models.update(classes((ROOT / "backend/masterdata/models.py").read_text(encoding="utf-8")))
    carrier_names = ["Material", "ExternalIdentity", "ProductBOM", "BOMVersion", "BOMItem",
        "EngineeringSourceRecord", "EngineeringBreakdownItem", "EngineeringRuleDefinition",
        "EngineeringCalculationRecord", "EngineeringCalculationDetail", "EngineeringDerivedFact"]
    carriers = []
    for name in carrier_names:
        body = models[name]
        tree = ast.parse(body).body[0]
        fields = [n.targets[0].id for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Call)]
        table = next(line.split('"')[1] for line in body.splitlines() if "db_table =" in line)
        carriers.append({"name": name, "table": table, "currentFields": fields,
                         "productionCount": formal["tables"].get(table, {}).get("count"), "developed": True})
    save("CURRENT_CARRIER_AUDIT.json", {"carriers": carriers, "orphanAudit": "ORPHAN_CONTRACT_AUDIT.json",
        "design": "Use existing Material identity, ExternalIdentity provenance, EngineeringRuleDefinition engine and original BOM/requirement tables. Four new typed relationship carriers only; not JSON-only and not a second ERP."})
    print(json.dumps({"packageFiles": len(paths), "patchCheck": "PASS", "carriers": len(carriers),
                      "roughRows": len(rows), "identities": len(identities)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
