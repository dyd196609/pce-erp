"""Read-only evidence build. Never executes Excel or writes any business database."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/excel_parity"))
sys.path.insert(0, str(ROOT / "backend"))
from workbook_source import SourceBook, SOURCE, EXPECTED_SHA, coord

OUT = ROOT / "docs/evidence/semi_finished_configuration_20260909"
SOURCE_BUNDLE = ROOT / "backend/pde/semi_finished_configuration_source.json"
DB = ROOT / "backend/db.sqlite3"
NATIVE = ROOT / "docs/evidence/excel_formula_parity/closure-20260909"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def records(book, sheet, header=1):
    cells = book.sheets[sheet]
    headers = {coord(a)[1]: (a.rstrip("0123456789"), str(v["value"]))
               for a, v in cells.items() if coord(a)[0] == header and v["value"] is not None}
    output = []
    for r in sorted({coord(a)[0] for a in cells if coord(a)[0] > header}):
        fields = {}
        for _, (col, name) in headers.items():
            c = cells.get(f"{col}{r}", {})
            fields[name] = {"cell": f"{col}{r}", "value": c.get("value"), "formula": c.get("formula")}
        if any(v["value"] is not None or v["formula"] for v in fields.values()):
            output.append({"row": r, "sheet": sheet, "fields": fields})
    return output


def snapshot():
    with sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        tables = [n for n in names if n in ("material", "material_category", "masterdata_external_identity", "system_process", "unit_of_measure")
                  or n.startswith(("pde_bom", "pde_engineering", "pde_component_material", "pde_material_selection", "pde_template_material", "pde_manufacturing", "pde_product_bom", "pde_routing", "pde_order_engineering"))]
        schema = {t: {"count": db.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0],
                      "columns": [dict(r) for r in db.execute(f'PRAGMA table_info("{t}")')],
                      "ddl": db.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()[0]} for t in tables}
        selected = {"materials": "material", "identities": "masterdata_external_identity", "categories": "material_category", "processTypes": "pde_manufacturing_process_type", "uoms": "unit_of_measure"}
        formal = {k: [dict(r) for r in db.execute(f'SELECT * FROM "{t}" ORDER BY id')] for k, t in selected.items()}
    return {"database": str(DB), "sha256": sha(DB), "queryOnly": True, "tables": schema, "formal": formal, "allTableNames": names}


def freeze():
    # Freeze before touching target code. Existing dirty worktree is deliberately preserved.
    files = [DB, SOURCE, ROOT / "frontend/src/meta/pages/PdeOrderEngineeringCalculationPage.vue",
             ROOT / "frontend/src/meta/master-data/foundationEntryUnificationRegistry.js",
             ROOT / "frontend/src/router/index.js", ROOT / "frontend/src/meta/runtime/pcePageAcceptanceRegistry.js",
             ROOT / "backend/pde/models.py", ROOT / "backend/masterdata/models.py",
             ROOT / "backend/pde/engineering_calculation_service.py", ROOT / "backend/pde/views.py",
             ROOT / "docs/evidence/ENGINEERING_MATERIAL_CALCULATION_TARGET_U03_20260909.md"]
    for folder in (ROOT / "scripts/excel_parity", ROOT / "tools/excel-golden-runner", NATIVE):
        files.extend(p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    baseline = {"capturedAt": datetime.now(timezone.utc).isoformat(), "files": {str(p): sha(p) for p in sorted(set(files))}}
    save(OUT / "BASELINE.json", baseline)
    save(OUT / "FORMAL_READONLY_SNAPSHOT.json", snapshot())
    return len(files)


def extract():
    assert sha(SOURCE) == EXPECTED_SHA
    filenames = [SOURCE.name, "05半成品板材.xlsx", "04色板.xlsx", "12木皮.xlsx", "13坯板.xlsx", "10采购物料.xlsx"]
    sources, books = [], {}
    for filename in filenames:
        path = SOURCE.parent / filename
        book = books[filename] = SourceBook(path)
        sources.append({"file": filename, "path": str(path), "sha256": sha(path), "sheets": [s["sheet"] for s in book.inventory],
                        "role": "SOURCE_AUTHORITY", "recordCounts": {s: len(records(book, s)) for s in book.sheets}})
    engineering = books[SOURCE.name]
    frozen = json.loads((NATIVE / "recovery-u03/REAL_ROW_SOURCE_FACTS.json").read_text(encoding="utf-8"))
    real = []
    for row in frozen:
        sheet, r = row["sheet"], row["row"]
        cells = {a: {k: v[k] for k in ("value", "formula", "type")} for a, v in engineering.sheets[sheet].items() if coord(a)[0] == r}
        # The frozen scope is used only as a scope reference, not as a value source.
        for address, previous in row["source_cells"].items():
            if address in cells:
                assert all(cells[address].get(k) == previous.get(k) for k in ("value", "formula", "type")), (sheet, address)
        real.append({"caseId": row["case_id"], "sheet": sheet, "row": r, "cells": cells})
    sf = records(books["05半成品板材.xlsx"], "半成品板材")
    sf = [r for r in sf if r["fields"]["半成品板材编码"]["value"]]
    for r in sf:
        r.update(file="05半成品板材.xlsx", sha256=sources[1]["sha256"])
    catalogs = {}
    for filename in filenames[2:]:
        for sheet in books[filename].sheets:
            catalogs[f"{filename}|{sheet}"] = records(books[filename], sheet)
    dependencies = {n: records(engineering, n) for n in ("物料目录(设计)", "油漆工艺及编码", "颜色板号目录", "木皮目录（设计）", "坯板目录（设计）", "表板目录（设计）", "油漆目录", "拆单基础数据")}
    real_keys = {(r["sheet"], r["row"]) for r in real}
    outside = [{"row": r, "sheet": "三合一生产单", "scope": "OUTSIDE_FROZEN_71_REAL_ROW_SCOPE", "cells": {a: {"value": v["value"], "formula": v["formula"]} for a, v in engineering.sheets["三合一生产单"].items() if coord(a)[0] == r and coord(a)[1] <= 22}}
               for r in range(7, 74) if ("三合一生产单", r) not in real_keys and engineering.sheets["三合一生产单"].get(f"B{r}", {}).get("value")]
    result = {"schemaVersion": "PCE-SEMI-FINISHED-CONFIGURATION-SOURCE-1", "organizationId": 1, "sourceFiles": sources,
              "excludedSourceAuthority": "08订单排产信息（样版）.xlsx", "nativeRerun": False, "sourceRows": sf,
              "catalogs": catalogs, "dependencies": dependencies, "realRows": real, "outsideFrozenScope": outside,
              "sourceScope": "61 coded rows from 05; frozen 71 real engineering rows only; dependent catalogs are evidence, not formal master data"}
    save(SOURCE_BUNDLE, result)
    save(OUT / "SOURCE_MANIFEST.json", {"bundle": str(SOURCE_BUNDLE), "bundleSha256": sha(SOURCE_BUNDLE), "sources": sources, "source05Count": len(sf), "realCount": len(real), "threeInOneCount": sum(r["sheet"] == "三合一生产单" for r in real), "outsideFrozenScope": outside})
    print(json.dumps({"source05Count": len(sf), "realCount": len(real), "bundleSha256": sha(SOURCE_BUNDLE)}, ensure_ascii=False))


def project():
    from pde.semi_finished_configuration_preview import build_projection
    source = json.loads(SOURCE_BUNDLE.read_text(encoding="utf-8"))
    current = snapshot()
    projected = build_projection(source, current["formal"], 1)
    save(OUT / "CONFIGURATION_PREVIEW.json", projected)
    save(OUT / "FORMAL_READONLY_SNAPSHOT.json", current)
    for name, key in (("SEMI_FINISHED_CODE_IDENTITY_MAP", "identityMap"),
                      ("SEMI_FINISHED_MATERIAL_CONFIGURATION_MATRIX", "configurations"),
                      ("MATERIAL_COMPOSITION_TRACE_MATRIX", "compositionTrace"),
                      ("SOURCE_TO_FORMAL_ATTRIBUTE_MATRIX", "attributeTrace"),
                      ("THICKNESS_SEMANTIC_ANALYSIS", "thicknessAnalysis"),
                      ("MATERIAL_CONFIGURATION_GAP_MATRIX", "gaps")):
        save(OUT / f"{name}.json", projected[key])
    print(json.dumps(projected["summary"], ensure_ascii=False))


def verify_preservation():
    baseline = json.loads((OUT / "BASELINE.json").read_text(encoding="utf-8"))
    allowed = {str(ROOT / p) for p in (
        "backend/pde/engineering_calculation_service.py", "backend/pde/views.py",
        "frontend/src/meta/pages/PdeOrderEngineeringCalculationPage.vue",
        "frontend/src/meta/master-data/foundationEntryUnificationRegistry.js",
        "docs/evidence/ENGINEERING_MATERIAL_CALCULATION_TARGET_U03_20260909.md")}
    changes = [{"path": p, "before": old, "after": sha(p) if Path(p).exists() else None}
               for p, old in baseline["files"].items() if not Path(p).exists() or sha(p) != old]
    unexpected = [r for r in changes if r["path"] not in allowed]
    frozen_roots = (ROOT / "scripts/excel_parity", ROOT / "tools/excel-golden-runner", NATIVE)
    current_frozen = {str(p) for folder in frozen_roots for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    baseline_frozen = {p for p in baseline["files"] if any(Path(p).is_relative_to(folder) for folder in frozen_roots)}
    from pde.semi_finished_configuration_preview import load_source
    source = load_source()
    report = {"baselineFiles": len(baseline["files"]), "unchangedFiles": len(baseline["files"]) - len(changes),
              "allowedExistingFileChanges": changes, "unexpectedChanges": unexpected,
              "frozenNativeFileCount": len(baseline_frozen), "frozenNativeFilesAdded": sorted(current_frozen - baseline_frozen),
              "frozenNativeFilesRemoved": sorted(baseline_frozen - current_frozen),
              "sourceFilesUnchanged": len(source["sourceFiles"]), "databaseSha256": sha(DB),
              "productionBusinessWrite": 0, "migrationExecuted": False, "nativeRerun": False}
    assert not unexpected and current_frozen == baseline_frozen
    assert sha(DB) == baseline["files"][str(DB)]
    preview = json.loads((OUT / "CONFIGURATION_PREVIEW.json").read_text(encoding="utf-8"))
    api = json.loads((OUT / "API_READONLY_EVIDENCE.json").read_text(encoding="utf-8"))
    ui = json.loads((OUT / "UI_COPIED_DIAGNOSTIC.json").read_text(encoding="utf-8"))
    assert preview == api["semiFinishedConfiguration"] == ui["semiFinishedConfiguration"]
    report["sourceSnapshotApiUiProjectionIdentical"] = True
    current = snapshot()
    audit = json.loads((OUT / "BOM_CARRIER_CAPABILITY_AUDIT.json").read_text(encoding="utf-8"))
    for row in audit["rows"]:
        if row.get("table"):
            assert current["tables"][row["table"]]["count"] == row["recordCount"], row["table"]
    report["bomCarrierCountsVerified"] = len(audit["rows"]) - 1
    report["matrixCounts"] = {name: len(json.loads((OUT / f"{name}.json").read_text(encoding="utf-8"))) for name in (
        "SEMI_FINISHED_CODE_IDENTITY_MAP", "SEMI_FINISHED_MATERIAL_CONFIGURATION_MATRIX", "MATERIAL_COMPOSITION_TRACE_MATRIX",
        "SOURCE_TO_FORMAL_ATTRIBUTE_MATRIX", "THICKNESS_SEMANTIC_ANALYSIS", "MATERIAL_CONFIGURATION_GAP_MATRIX")}
    report["result"] = "PASS"
    save(OUT / "PRESERVATION_RESULTS.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "extract", "project", "verify"))
    action = parser.parse_args().action
    if action == "freeze":
        if (OUT / "BASELINE.json").exists():
            raise SystemExit("Baseline exists; refuse overwrite")
        print("Frozen files:", freeze())
    elif action == "extract":
        extract()
    elif action == "verify":
        verify_preservation()
    else:
        project()
