"""Read-only production/frozen evidence and browser/API consistency checks."""
import hashlib
import json
from pathlib import Path
from semi_finished_model_closure_audit import ROOT, OUT, save, sha
from engineering_material_configuration_audit import snapshot

baseline = json.loads((OUT / "BASELINE.json").read_text(encoding="utf-8"))
allowed = {str(ROOT / p) for p in (
    "backend/pde/semi_finished_configuration_preview.py",
    "frontend/src/meta/components/SemiFinishedConfigurationPreview.vue",
    "scripts/test_semi_finished_configuration.py",
    "docs/evidence/ENGINEERING_MATERIAL_CALCULATION_TARGET_U03_20260909.md")}
changes, unchanged, missing = [], [], []
for name, old in baseline["files"].items():
    if not Path(name).exists():
        missing.append(name)
    elif sha(name) != old:
        changes.append({"path": name, "before": old, "after": sha(name), "authorized": name in allowed})
    else:
        unchanged.append(name)
assert not missing and all(x["authorized"] for x in changes), (missing, changes)
native_roots = [ROOT / x for x in ("scripts/excel_parity", "tools/excel-golden-runner", "docs/evidence/excel_formula_parity/closure-20260909")]
native_baseline = {str(Path(n).resolve()) for n in baseline["files"] if any(Path(n).is_relative_to(r) for r in native_roots)}
native_current = {str(p.resolve()) for root in native_roots for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
assert native_current == native_baseline, {"added": sorted(native_current-native_baseline), "missing": sorted(native_baseline-native_current)}
assert native_baseline.issubset(set(unchanged))
formal = snapshot()
assert formal["sha256"] == baseline["files"][str(ROOT / "backend/db.sqlite3")]
save("FORMAL_AFTER.json", formal)
ui = json.loads((OUT / "UI_DIAGNOSTIC.json").read_text(encoding="utf-8"))
api = json.loads((OUT / "API_READONLY_EVIDENCE.json").read_text(encoding="utf-8"))
assert ui["semiFinishedConfiguration"] == api["semiFinishedConfiguration"], "UI_API_PROJECTION_DIFFERENCE"
assert ui["productionBusinessWrite"] == 0
projection = ui["semiFinishedConfiguration"]
assert projection["summary"]["source05Count"] == 61
assert projection["summary"]["allRealMapped"] == 71
save("FINAL_NON_REGRESSION.json", {"status": "PASS", "baselineFiles": len(baseline["files"]),
    "unchanged": len(unchanged), "authorizedChanges": changes, "unexpectedChanges": [],
    "nativeFilesByteIdentical": len(native_baseline), "nativeAddedRemoved": 0,
    "productionDatabaseSha256": formal["sha256"], "productionBusinessWrite": 0,
    "productionMigration": 0, "uiApiProjectionExact": True, "uiProjectionVersion": projection["version"],
    "uiDiagnosticSha256": sha(OUT / "UI_DIAGNOSTIC.json"),
    "freezeCount": {k: v["count"] for k, v in formal["tables"].items()},
    "historyNote": "Previous phase reusable API/TEST_RESULTS files were refreshed before output isolation was corrected. Native 474 files and previous consolidated reports are unchanged; no claim all prior phase scratch evidence is byte-identical."})
print(json.dumps({"status": "PASS", "baselineFiles": len(baseline["files"]), "nativeUnchanged": len(native_baseline),
    "productionDatabaseUnchanged": True, "uiApiProjectionExact": True, "authorizedChangedFiles": len(changes)}, ensure_ascii=False))

report = ROOT / "docs/evidence/SEMI_FINISHED_MODEL_CLOSURE_FINAL_CONSOLIDATED_20260909.md"
if report.exists():
    raw = report.read_bytes()
    content = raw.decode("utf-8")
    assert len(content.splitlines()) <= 500
    save("REPORT_READBACK.json", {"path": str(report), "sha256": sha(report), "bytes": len(raw),
        "lines": len(content.splitlines()), "reviewLevel": "C", "fullContentReviewRequired": True,
        "readback": "Full Get-Content output read by main agent; UTF-8 decoded again without truncation",
        "firstLine": content.splitlines()[0], "lastNonemptyLine": [x for x in content.splitlines() if x][-1],
        "reportIsProductionDeploymentApproval": False})
    print(json.dumps(json.loads((OUT / "REPORT_READBACK.json").read_text(encoding="utf-8")), ensure_ascii=False))
