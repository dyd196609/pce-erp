"""Package-only adapter over the frozen reference code. Never a Golden engine.

No ORM, ERP services, network, workbook authoring, inventory generation or recovery.
Native captures are retained for later code-only re-comparison with the same inputs.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib
import json
import math
import shutil
import sys
import traceback
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
EXPECTED_SHA = "7ED132C13F6F7B13F5805F3872EC06528D9342A8E821A4D6F3D8B571243FB122"
PYTHON = Path(r"C:\Users\DAODA\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
PACKAGE_FILES = (
    "RUN_EXCEL_GOLDEN_VALIDATION.cmd", "run_excel_golden_validation.ps1",
    "runner_common.ps1", "native_excel_runner.ps1", "package_support.py",
    "test_package.py", "test_native_contract.ps1", "README_FOR_USER.txt", "OUTPUT_SCHEMA.json",
)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".pending")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_hashes(entries, root=None):
    for name, expected in entries.items():
        path = Path(root) / name if root else Path(name)
        require(path.is_file() and digest(path) == expected, f"HASH MISMATCH: {path}")


def load_manifest():
    m = read(ROOT / "RUNNER_MANIFEST.json")
    require(m["source_sha"] == EXPECTED_SHA, "SOURCE AUTHORITY MISMATCH")
    require(set(m["files"]) == set(PACKAGE_FILES), "PACKAGE FILE SET MISMATCH")
    verify_hashes(m["files"], ROOT)
    verify_hashes(m["frozen_files"])
    require(Path(m["python"]).resolve() == Path(sys.executable).resolve(), "WRONG PYTHON RUNTIME")
    require(digest(m["python"]) == m["python_sha"], "PYTHON RUNTIME DRIFT")
    return m


def reference(m):
    sys.path.insert(0, m["reference_directory"])
    modules = {name: importlib.import_module(name) for name in (
        "workbook_source", "formula_ast", "reference_runtime", "generated_reference", "differential"
    )}
    for name, module in modules.items():
        require(Path(module.__file__).resolve() == Path(m["reference_directory"]) / (name + ".py"), "WRONG REFERENCE IMPORT")
    return modules


def assets(m):
    evidence = Path(m["evidence_directory"])
    family = read(evidence / "FORMULA_FAMILY_INVENTORY.json")
    cases = read(evidence / "EXCEL_GOLDEN_CASES.json")
    broken = read(evidence / "BROKEN_FORMULA_REGISTER.json")
    require(len(family["families"]) == 163 and len(broken) == 1144, "FROZEN INVENTORY COUNT MISMATCH")
    require(sum(f["broken"] for f in family["families"]) == 51, "BROKEN FAMILY COUNT MISMATCH")
    require(len(cases["cases"]) == 722, "FROZEN CASE COUNT MISMATCH")
    return family, cases


def select_cases(family, cases, functions):
    intact = {f["family_id"] for f in family["families"] if not f["broken"]}
    require(intact == set(functions) and len(intact) == 112, "INTACT/GENERATED FUNCTION SET MISMATCH")
    selected = [c for c in cases["cases"] if c["level"] == 1 and c["derived_outputs"] and all(o["formula_family"] in intact for o in c["derived_outputs"])]
    covered = {o["formula_family"] for c in selected for o in c["derived_outputs"]}
    require(covered == intact, "INTACT FAMILY COVERAGE INCOMPLETE")
    require(len({c["case_id"] for c in cases["cases"]}) == 722, "DUPLICATE CASE ID")
    require(len(selected) == 280 and sum(len(c["derived_outputs"]) for c in selected) == 280, "FROZEN SELECTION COUNT DRIFT")
    return selected


def inspect_workbook(path):
    """Read only, no evaluation. Refuse automatic data refresh before Excel opens."""
    with zipfile.ZipFile(path) as z:
        require(z.testzip() is None, "CORRUPT SOURCE ZIP")
        connections = []
        for name in z.namelist():
            if not name.endswith(".xml"):
                continue
            if name == "xl/connections.xml" or name.startswith(("xl/queryTables/", "xl/pivotCache/")):
                root = ET.fromstring(z.read(name))
                for node in root.iter():
                    require(node.get("refreshOnLoad", "0").lower() not in ("1", "true"), "AUTO REFRESH BLOCKED: " + name)
                connections.append(name)
        require(not any("vbaProject" in n for n in z.namelist()), "MACRO PROJECT NOT ALLOWED IN FROZEN XLSX")
        return {"zip_readable": True, "automatic_refresh_on_load": False, "connection_metadata_checked": connections}


def prepare(run_dir):
    report = {"status": "FAIL", "started_at": now(), "checks": {}, "native_excel_executed": False}
    try:
        m = load_manifest()
        report["checks"]["manifest_and_frozen_hashes"] = "PASS"
        source = Path(m["source"])
        require(source.is_file() and digest(source) == EXPECTED_SHA, "SOURCE PATH/SHA MISMATCH")
        report["checks"]["source_path_sha_readability"] = "PASS"
        report["workbook_safety"] = inspect_workbook(source)
        copy = run_dir / "source-readonly-copy.xlsx"
        require(not copy.exists(), "RUN COPY ALREADY EXISTS; REUSE IS FORBIDDEN")
        shutil.copyfile(source, copy)
        require(digest(copy) == EXPECTED_SHA and digest(source) == EXPECTED_SHA, "COPY/SOURCE HASH MISMATCH")
        report["checks"]["isolated_copy_and_run_directory"] = "PASS"
        modules = reference(m)
        family, cases = assets(m)
        selected = select_cases(family, cases, modules["generated_reference"].FUNCTIONS)
        book = modules["workbook_source"].SourceBook(copy)
        for c in selected:
            require(c["source_sha"] == EXPECTED_SHA, "CASE SOURCE MISMATCH")
            seen = set()
            for change in c["overrides"]:
                key = (change["sheet"], change["cell"])
                require(key not in seen, "DUPLICATE OVERRIDE")
                seen.add(key)
                require(change["sheet"] in book.sheets, "OVERRIDE SHEET MISSING")
                modules["workbook_source"].coord(change["cell"])
                require(change["type"] in ("number", "text", "boolean", "blank"), "UNKNOWN OVERRIDE TYPE")
                require(type_matches(change["value"], {"number": "number", "text": "string", "boolean": "boolean", "blank": "null"}[change["type"]]), "OVERRIDE TYPE MISMATCH")
            for o in c["derived_outputs"]:
                s, a = o["cell"].rsplit("!", 1)
                require(book.sheets[s][a]["formula"] == o["formula"], "OUTPUT FORMULA != FROZEN SOURCE")
                require(family["cell_to_family"][o["cell"]] == o["formula_family"], "OUTPUT FAMILY MISMATCH")
                require("comparison" in o["contract"], "COMPARISON CONTRACT MISSING")
        plan = {
            "run_id": run_dir.name, "source_sha": EXPECTED_SHA, "workbook_copy": str(copy),
            "case_manifest_sha": digest(Path(m["evidence_directory"]) / "EXCEL_GOLDEN_CASES.json"),
            "family_inventory_sha": digest(Path(m["evidence_directory"]) / "FORMULA_FAMILY_INVENTORY.json"),
            "level": 1, "cohort": "INTACT_FORMULA_FAMILY_NATIVE_PARITY", "family_count": 112,
            "frozen_case_count": 722, "selected_case_count": len(selected), "excluded_case_count": 722-len(selected),
            "excluded_direct_broken_family_count": 51, "cases": selected,
            "cached_values_are_oracle": False, "formula_recovery_applied": False, "production_write": 0,
        }
        write(run_dir / "RUN_CASE_PLAN.json", plan)
        report["checks"]["case_definitions_families_imports_source_mapping"] = "PASS"
        report["selected_cases"] = len(selected)
        report["selected_families"] = 112
        report["status"] = "PREPARATION_PASS"
    except Exception as exc:
        report["error"] = repr(exc)
        raise
    finally:
        write(run_dir / "PACKAGE_PRECHECK.json", report)


def evaluate_reference(m, plan):
    modules = reference(m)
    family, _ = assets(m)
    rt = modules["reference_runtime"]
    book = modules["workbook_source"].SourceBook(plan["workbook_copy"])
    base = rt.Context(book, family["cell_to_family"], modules["generated_reference"].FUNCTIONS)
    rows = []
    for c in plan["cases"]:
        overrides = {(o["sheet"], o["cell"]): rt.BLANK if o["type"] == "blank" else o["value"] for o in c["overrides"]}
        ctx = rt.Context(book, family["cell_to_family"], modules["generated_reference"].FUNCTIONS, overrides) if overrides else base
        for output in c["derived_outputs"]:
            row = {"case_id": c["case_id"], "cell": output["cell"], "formula_family": output["formula_family"], "semantic_name": output["semantic_name"], "contract": output["contract"], "code_result": None, "reference_status": "EVALUATED_NOT_NATIVE_VERIFIED"}
            try:
                try:
                    value = ctx.cell(*output["cell"].rsplit("!", 1))
                except rt.ExcelError as exc:
                    value = exc
                row["code_result"] = rt.serialized(value)
            except modules["formula_ast"].BrokenSource as exc:
                row.update(reference_status="BROKEN_DEPENDENCY", reason=str(exc))
            except modules["formula_ast"].Unsupported as exc:
                row.update(reference_status="TECHNICAL_TRANSLATOR_DEFECT", reason=str(exc))
            rows.append(row)
    return rows


def type_matches(value, expected):
    if expected.startswith("nullable_"):
        return value is None or type_matches(value, expected.removeprefix("nullable_"))
    return {
        "string": lambda: type(value) is str,
        "integer": lambda: type(value) is int,
        "number": lambda: type(value) in (int, float) and math.isfinite(value),
        "boolean": lambda: type(value) is bool,
        "array": lambda: type(value) is list,
        "object": lambda: type(value) is dict,
        "null": lambda: value is None,
    }[expected]()


def validate_output_files(run_dir):
    schema = read(ROOT / "OUTPUT_SCHEMA.json")
    for name, fields in schema["required_files"].items():
        obj = read(run_dir / name)
        for field, typ in fields.items():
            require(field in obj and type_matches(obj[field], typ), f"OUTPUT SCHEMA: {name}.{field} must be {typ}")
        require(obj["run_id"] == run_dir.name, "OUTPUT RUN ID MISMATCH")
    require((run_dir / "RUN_LOG.txt").is_file(), "RUN LOG MISSING")


def precheck(run_dir):
    import unittest
    m = load_manifest()
    report = read(run_dir / "PACKAGE_PRECHECK.json")
    try:
        for path in [ROOT / f for f in PACKAGE_FILES if f.endswith(".py")] + list(Path(m["reference_directory"]).glob("*.py")):
            compile(path.read_text("utf-8-sig"), str(path), "exec")
        report["checks"]["python_and_modules_compile"] = "PASS"
        modules = reference(m)
        family, _ = assets(m)
        for f in family["families"]:
            if not f["broken"]:
                modules["formula_ast"].Parser().parse(f["source_formula"])
        report["checks"]["all_112_intact_formulas_parse"] = "PASS"
        tests = unittest.defaultTestLoader.loadTestsFromName("test_package")
        result = unittest.TextTestRunner(verbosity=2).run(tests)
        require(result.wasSuccessful(), "PACKAGE UNIT TEST FAILURE")
        report["unit_test_count"] = result.testsRun
        report["checks"]["comparator_and_contract_tests"] = "PASS"
        plan = read(run_dir / "RUN_CASE_PLAN.json")
        rows = evaluate_reference(m, plan)
        write(run_dir / "REFERENCE_PRECHECK.json", {"oracle": False, "native_executed": False, "results": rows})
        report["reference_precheck_counts"] = dict(collections.Counter(r["reference_status"] for r in rows))
        report["checks"]["all_selected_cases_reference_exercised"] = "PASS"
        validate_output_files(run_dir)
        report["checks"]["output_schema"] = "PASS"
        diagnostic = read(run_dir / "SESSION_DIAGNOSTIC.json")
        require(diagnostic["excel_paths"], "EXCEL DISCOVERY MISSING")
        report["checks"]["excel_installation_discovery"] = "PASS"
        syntax = read(run_dir / "POWERSHELL_PRECHECK.json")
        require(syntax["status"] == "PASS" and len(syntax["files"]) == 4, "POWERSHELL PARSE EVIDENCE MISSING")
        report["checks"]["powershell_syntax"] = "PASS"
        report["powershell_version"] = syntax["version"]
        ps_contract = read(run_dir / "POWERSHELL_CONTRACT_TEST.json")
        require(ps_contract["status"] == "PASS" and ps_contract["native_excel_executed"] is False, "POWERSHELL CONTRACT TEST FAILED")
        report["checks"]["powershell_serialization_control_pid_interop"] = "PASS"
        report["powershell_contract_test_count"] = ps_contract["count"]
        verify_hashes(m["files"], ROOT)
        verify_hashes(m["frozen_files"])
        report["checks"]["tested_code_equals_packaged_code"] = "PASS"
        report["tested_files"] = m["files"]
        report["package_manifest_sha"] = digest(ROOT / "RUNNER_MANIFEST.json")
        report["status"] = "PASS"
        report["native_excel_status"] = "NOT_EXECUTED"
    except Exception as exc:
        report.update(status="FAIL", error=repr(exc))
        raise
    finally:
        report["finished_at"] = now()
        write(run_dir / "PACKAGE_PRECHECK.json", report)


def validate_native(run, golden, plan, plan_sha):
    require(run["run_id"] == golden["run_id"] == plan["run_id"], "NATIVE RUN ID MISMATCH")
    require(run["mode"] == "USER_SESSION_NATIVE" and run["execution_status"] == "PASS", "NATIVE EXECUTION NOT PASS")
    require(golden["engine"] == "Microsoft Excel Calculation Engine" and golden["status"] == "CAPTURED", "MICROSOFT EXCEL ORACLE REQUIRED")
    require(run["original_unchanged"] is True and run["source_sha_after"] == EXPECTED_SHA and run["run_copy_sha_after"] == EXPECTED_SHA, "SOURCE/COPY PROTECTION NOT VERIFIED")
    require(golden["source_sha"] == EXPECTED_SHA and golden["plan_sha"] == plan_sha and run["plan_sha"] == plan_sha, "ORACLE IDENTITY MISMATCH")
    require(run["excel_pid"] and run["excel_version"] and run["calculation_start"] and run["calculation_end"], "NATIVE ENGINE METADATA MISSING")
    cases = {c["case_id"]: c for c in plan["cases"]}
    require(len(golden["results"]) == len(cases) == run["result_count"], "ORACLE COVERAGE INCOMPLETE")
    require({c["case_id"] for c in golden["results"]} == set(cases), "ORACLE CASE SET MISMATCH")
    indexed = {}
    for capture in golden["results"]:
        case = cases[capture["case_id"]]
        expected = {o["cell"]: o for o in case["derived_outputs"]}
        require(capture["restored"] is True and capture["calculation_start"] and capture["calculation_end"], "CASE RESTORE/CALCULATION NOT PROVEN")
        require(len(capture["outputs"]) == len(expected) and {o["cell"] for o in capture["outputs"]} == set(expected), "ORACLE OUTPUT SET MISMATCH")
        changes = {(o["sheet"], o["cell"]): o for o in case["overrides"]}
        require(len(capture["overrides"]) == len(changes), "OVERRIDE COUNT MISMATCH")
        require({(o["sheet"], o["cell"]) for o in capture["overrides"]} == set(changes), "OVERRIDE CELL SET MISMATCH")
        for applied in capture["overrides"]:
            change = changes[(applied["sheet"], applied["cell"])]
            require(type_matches(applied["actual"]["value"], {"number":"number","text":"string","boolean":"boolean","blank":"null"}[change["type"]]), "NATIVE OVERRIDE VALUE TYPE INVALID")
            require(applied["actual"] == {"type": change["type"], "value": change["value"]}, "NATIVE INPUT != REFERENCE INPUT")
        for output in capture["outputs"]:
            definition = expected[output["cell"]]
            require(output["formula_family"] == definition["formula_family"], "NATIVE FAMILY MISMATCH")
            require(output["has_formula"] is True, "NATIVE OUTPUT FORMULA MISSING")
            # Excel may remove the stored compatibility prefix; no other rewriting accepted.
            require(output["formula"].replace("_xlfn.", "") == definition["formula"].replace("_xlfn.", ""), "NATIVE FORMULA DRIFT")
            typed = output["excel_raw_value"]
            typ = {"blank": "null", "error": "string", "text": "string", "number": "number", "boolean": "boolean"}.get(typed["type"])
            require(typ is not None and type_matches(typed["value"], typ), "INVALID NATIVE VALUE TYPE")
            indexed[(capture["case_id"], output["cell"])] = output
    return indexed


def compare(run_dir):
    m = load_manifest()
    plan = read(run_dir / "RUN_CASE_PLAN.json")
    family, frozen_cases = assets(m)
    require(plan["cases"] == select_cases(family, frozen_cases, reference(m)["generated_reference"].FUNCTIONS), "PLAN != FROZEN INTACT CASE SELECTION")
    run = read(run_dir / "NATIVE_EXCEL_RUN.json")
    golden = read(run_dir / "EXCEL_NATIVE_GOLDEN.json")
    indexed = validate_native(run, golden, plan, digest(run_dir / "RUN_CASE_PLAN.json"))
    require(digest(plan["workbook_copy"]) == EXPECTED_SHA, "RECOMPARISON COPY DRIFT")
    rows = evaluate_reference(m, plan)
    comparator = reference(m)["differential"].compare_result
    for row in rows:
        capture = indexed[(row["case_id"], row["cell"])]
        row["excel_raw_value"] = capture["excel_raw_value"]
        row["excel_displayed_value"] = capture["excel_displayed_value"]
        if row["reference_status"] in ("BROKEN_DEPENDENCY", "TECHNICAL_TRANSLATOR_DEFECT"):
            row["classification"] = row["reference_status"]
        else:
            row["comparison"] = comparator(row["code_result"], row["excel_raw_value"], row["contract"])
            row["classification"] = "PARITY_PASS" if row["comparison"]["status"] == "PASS" else "UNCLASSIFIED_DIFFERENCE"
        row["next_action"] = "NONE" if row["classification"] == "PARITY_PASS" else "CODEX_TECHNICAL_INVESTIGATION_FIRST"
        row["user_decision_requested"] = False
    counts = dict(collections.Counter(r["classification"] for r in rows))
    families = []
    for family_id in sorted({r["formula_family"] for r in rows}):
        members = [r for r in rows if r["formula_family"] == family_id]
        families.append({"family_id": family_id, "case_count": len(members), "counts": dict(collections.Counter(r["classification"] for r in members)), "status": "PARITY_PASS" if all(r["classification"] == "PARITY_PASS" for r in members) else "REQUIRES_CODEX_ANALYSIS"})
    status = "PASS" if rows and all(r["classification"] == "PARITY_PASS" for r in rows) else "REVIEW_REQUIRED"
    write(run_dir / "DIFFERENTIAL_RESULTS.json", {"run_id": run_dir.name, "status": status, "engine": golden["engine"], "level": 1, "source_sha": EXPECTED_SHA, "plan_sha": golden["plan_sha"], "reference_hashes": {k:v for k,v in m["frozen_files"].items() if k.endswith(".py")}, "counts": counts, "results": rows, "families": families, "production_write": 0, "levels_2_to_5": "NOT_STARTED"})
    return 0 if status == "PASS" else 3


def finalize(run_dir):
    validate_output_files(run_dir)
    run = read(run_dir / "NATIVE_EXCEL_RUN.json")
    manifest = {"run_id": run_dir.name, "mode": run["mode"], "package_manifest_sha": run["package_manifest_sha"], "source_sha": run["source_sha"], "run_copy_sha": run["run_copy_sha"], "finished_at": now(), "files": {p.name: digest(p) for p in sorted(run_dir.iterdir()) if p.is_file() and p.name != "RUN_MANIFEST.json"}, "self_hash_excluded": True}
    write(run_dir / "RUN_MANIFEST.json", manifest)
    validate_output_files(run_dir)
    return 0


def seal():
    """Maintainer packaging step only. Does not regenerate any formula asset."""
    evidence = REPO / "docs/evidence/excel_formula_parity"
    previous_path = evidence / "PACKAGE_MANIFEST.json"
    previous = read(previous_path)
    frozen = {str(REPO / path): sha for path, sha in previous["source_files"].items()}
    frozen.update({str(evidence / name): sha for name, sha in previous["evidence_files"].items()})
    verify_hashes(frozen)
    frozen[str(previous_path)] = digest(previous_path)
    source = read(evidence / "SOURCE_WORKBOOK_FREEZE.json")["source"]
    require(digest(source) == EXPECTED_SHA, "SOURCE SHA MISMATCH")
    # Formatting only: Windows PowerShell 5.1 needs UTF-8 BOM for Chinese messages;
    # batch files use ASCII CRLF. These are the bytes subsequently tested/delivered.
    for name in PACKAGE_FILES:
        p = ROOT / name
        if p.suffix == ".ps1":
            p.write_bytes(p.read_text("utf-8-sig").encode("utf-8-sig"))
        elif p.suffix == ".cmd":
            p.write_bytes(p.read_text("ascii").replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii"))
    m = {"package_version": "1.0", "created_at": now(), "entry_point": "RUN_EXCEL_GOLDEN_VALIDATION.cmd", "source": source, "source_sha": EXPECTED_SHA, "python": str(PYTHON), "python_sha": digest(PYTHON), "reference_directory": str(REPO / "scripts/excel_parity"), "evidence_directory": str(evidence), "files": {name: digest(ROOT / name) for name in PACKAGE_FILES}, "frozen_files": frozen, "scope": "USER_SESSION_NATIVE_LEVEL_1_ONLY", "frozen_inventory": {"families":163,"generated":112,"broken_families":51,"broken_cells":1144,"cases":722}, "native_execution": "NOT_EXECUTED", "production_write": 0, "migration": 0}
    write(ROOT / "RUNNER_MANIFEST.json", m)
    print(json.dumps({"sealed": len(m["files"]), "frozen_dependencies": len(frozen), "native_executed": False}))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("seal", "prepare", "precheck", "compare", "finalize"))
    parser.add_argument("--run-directory", type=Path)
    args = parser.parse_args()
    if args.action == "seal":
        seal()
        return 0
    require(args.run_directory is not None, "RUN DIRECTORY REQUIRED")
    run_dir = args.run_directory.resolve()
    require(run_dir.parent in (ROOT / "runs", ROOT / "prechecks"), "RUN DIRECTORY MUST BE ISOLATED WITHIN PACKAGE")
    require(run_dir.is_dir(), "RUN DIRECTORY NOT FOUND")
    return globals()[args.action](run_dir) or 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        if "--run-directory" in sys.argv:
            directory = Path(sys.argv[sys.argv.index("--run-directory")+1]).resolve()
            if directory.is_dir() and directory.parent in (ROOT / "prechecks", ROOT / "runs"):
                detail = {"time": now(), "action": sys.argv[1], "traceback": traceback.format_exc(), "native_result_not_invented": True}
                write(directory / "PYTHON_FAILURE.json", detail)
                with (directory / "RUN_LOG.txt").open("a", encoding="utf-8") as log:
                    log.write(now() + " PYTHON FAILURE\n" + detail["traceback"] + "\n")
        raise SystemExit(2)
