"""Read-only audit and immutable baseline for the isolated configuration closure."""
from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/evidence/semi_finished_model_closure_20260909"
HISTORY = "wave27-formal-readback-remediation-20260903"
sys.path.insert(0, str(ROOT / "scripts"))
from engineering_material_configuration_audit import snapshot, sha


def save(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def git(*args):
    return subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}", *args], cwd=ROOT).decode("utf-8")


def classes(text):
    lines = text.splitlines(keepends=True)
    return {n.name: "".join(lines[n.lineno - 1:n.end_lineno]) for n in ast.parse(text).body if isinstance(n, ast.ClassDef)}


def main():
    if (OUT / "BASELINE.json").exists():
        raise SystemExit("Baseline exists: refusing to replace frozen evidence")
    previous = json.loads((ROOT / "docs/evidence/semi_finished_configuration_20260909/BASELINE.json").read_text(encoding="utf-8"))
    source = json.loads((ROOT / "backend/pde/semi_finished_configuration_source.json").read_text(encoding="utf-8"))
    files = {Path(p) for p in previous["files"]}
    files.update(Path(x["path"]) for x in source["sourceFiles"])
    files.update(ROOT / p for p in (
        "backend/pde/semi_finished_configuration_source.json", "backend/pde/semi_finished_configuration_preview.py",
        "frontend/src/meta/components/SemiFinishedConfigurationPreview.vue", "scripts/test_semi_finished_configuration.py",
        "docs/evidence/SEMI_FINISHED_CONFIGURATION_FINAL_CONSOLIDATED_20260909.md"))
    save("BASELINE.json", {"files": {str(p): sha(p) for p in sorted(files)}, "gitHead": git("rev-parse", "HEAD").strip()})
    current = snapshot()
    save("FORMAL_BEFORE.json", current)
    with sqlite3.connect((ROOT / "backend/db.sqlite3").as_uri() + "?mode=ro", uri=True) as con:
        con.execute("PRAGMA query_only=ON")
        migrations = list(con.execute("SELECT app,name FROM django_migrations ORDER BY app,name"))
        all_ddl = list(con.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"))
        rules = [dict(zip([c[0] for c in cursor.description], row)) for cursor in [con.execute("SELECT * FROM pde_engineering_rule_definition")] for row in cursor]
    save("MIGRATION_LEDGER.json", migrations)
    save("ALL_TABLE_DDL.json", dict(all_ddl))
    save("EXISTING_RULES.json", rules)
    old_text = git("show", f"{HISTORY}:backend/pde/models.py")
    old, now = classes(old_text), classes((ROOT / "backend/pde/models.py").read_text(encoding="utf-8"))
    # Historical source is preserved verbatim as audit evidence, never loaded by production.
    historical_dir = OUT / "historical"
    historical_dir.mkdir(exist_ok=True)
    selected = ["backend/pde/models.py", "backend/pde/order_engineered_product_service.py",
                "backend/pde/tests_order_engineered_product_structure_wave26.py",
                "backend/pde/tests_structure_template_rule_binding_wave27.py"]
    tree = git("ls-tree", "-r", "--name-only", HISTORY, "backend/pde").splitlines()
    selected += [p for p in tree if "/migrations/002" in p]
    for path in selected:
        (historical_dir / Path(path).name).write_text(git("show", f"{HISTORY}:{path}"), encoding="utf-8")
    result = []
    for name in ("ComponentMaterialRequirement", "MaterialSelectionCandidate", "EngineeringMaterialCalculationResult", "TemplateMaterialRequirementSlot"):
        table = next(line.split('"')[1] for line in old[name].splitlines() if "db_table =" in line)
        result.append({"model": name, "table": table, "currentRuntimeModel": name in now,
                       "productionCount": current["tables"][table]["count"],
                       "classification": "RECOVERABLE_IMPLEMENTATION", "currentState": "ORPHANED_CONTRACT",
                       "historyRef": HISTORY, "historyCommit": git("rev-parse", HISTORY).strip(),
                       "introduced": git("log", "--all", "--oneline", "-S", f"class {name}", "--", "backend/pde/models.py").splitlines(),
                       "reason": "Production retains schema applied from a later wave26/27 branch; current runtime HEAD is the earlier workcenter closure branch. Current models do not contain these classes. No evidence of intentional business deprecation.",
                       "schema": current["tables"][table],
                       "modelSha256": hashlib.sha256(old[name].encode()).hexdigest().upper()})
    save("ORPHAN_CONTRACT_AUDIT.json", {"contracts": result, "missingHistoricalClasses": sorted(set(old) - set(now)),
         "currentBranch": git("branch", "--show-current").strip(), "historicalFiles": selected,
         "recoveryPolicy": "Recover original names/db_table in isolated canonical candidate; no second requirement/formula engine. Do not restore unrelated WorkCenter, route or production data."})
    print(json.dumps({"baselineFiles": len(files), "databaseSha": current["sha256"], "missing": sorted(set(old)-set(now)),
                      "pdeMigrations": [m for m in migrations if m[0] == "pde"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
