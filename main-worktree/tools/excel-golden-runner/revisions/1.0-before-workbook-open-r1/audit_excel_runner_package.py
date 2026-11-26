"""Read-only delivery audit; writes only its own evidence JSON and a temp probe."""
from __future__ import annotations
import json
import io
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "tools/excel-golden-runner"
sys.path.insert(0, str(PACKAGE))
import package_support as p


def main():
    manifest = p.load_manifest()
    p.reference(manifest)
    test_log = io.StringIO()
    legacy_tests = unittest.TextTestRunner(stream=test_log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_reference'))
    p.require(legacy_tests.wasSuccessful() and legacy_tests.testsRun == 40, 'FROZEN REFERENCE REGRESSION')
    precheck = sorted((PACKAGE / "prechecks").iterdir())[-1]
    report = p.read(precheck / "PACKAGE_PRECHECK.json")
    native = p.read(precheck / "NATIVE_EXCEL_RUN.json")
    run_manifest = p.read(precheck / "RUN_MANIFEST.json")
    p.require(report["status"] == "PASS" and native["exit_code"] == 0, "LATEST PRECHECK NOT PASS")
    p.require(report["tested_files"] == manifest["files"], "TESTED CODE != PACKAGED CODE")
    p.require(report["package_manifest_sha"] == p.digest(PACKAGE / "RUNNER_MANIFEST.json"), "TESTED MANIFEST != DELIVERED MANIFEST")
    p.verify_hashes(run_manifest["files"], precheck)
    p.validate_output_files(precheck)
    p.require(native["execution_status"] == "NOT_EXECUTED" and native["result_count"] == 0, "PRECHECK MISREPRESENTED AS GOLDEN")
    p.require(native["original_unchanged"] and p.digest(manifest["source"]) == p.EXPECTED_SHA, "SOURCE PROTECTION FAILED")
    runs = PACKAGE / "runs"
    runs.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="package-write-probe-", dir=runs) as directory:
        probe = Path(directory) / "isolated-probe.txt"
        probe.write_text("PACKAGE PREFLIGHT ONLY", encoding="utf-8")
        p.require(probe.read_text("utf-8") == "PACKAGE PREFLIGHT ONLY", "RUN DIRECTORY NOT WRITABLE")
    db_path = REPO / "backend/db.sqlite3"
    baseline = "9DADFB55D446DF052A4DCF6CF2EE552906939FD1B65D7D899C5FD8C1AC368F5C"
    p.require(p.digest(db_path) == baseline, "BUSINESS DB HASH CHANGED")
    connection = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    expected = {"system_process":33,"pde_routing":42,"pde_routing_version":42,"pde_routing_step":1137,"pde_engineering_rule_definition":4,"pde_product_bom":0,"pde_bom_item":0,"pde_standard_capacity":0}
    try:
        actual = {name: connection.execute("SELECT COUNT(*) FROM " + name).fetchone()[0] for name in expected}
    finally:
        connection.close()
    p.require(actual == expected and p.digest(db_path) == baseline, "FROZEN BUSINESS FACTS CHANGED")
    p.require(not list(runs.iterdir()), "NATIVE RUN UNEXPECTEDLY STARTED")
    source_inputs = list(manifest["frozen_files"]) + [
        r"D:\Dev-PCE\AGENTS.md", str(REPO / "AGENTS.md"),
        str(REPO / "docs/governance/PCE CODEX开发指令规范管理V1.2.md"),
        r"C:\Users\DAODA\.codex\attachments\3a258f4d-dac7-4066-a45c-a31c5abcdf74\pasted-text.txt",
        manifest["source"], str(db_path),
    ]
    output = {
        "status":"PASS", "time":datetime.now(timezone.utc).isoformat(), "package":str(PACKAGE),
        "precheck":str(precheck), "package_manifest_sha":p.digest(PACKAGE / "RUNNER_MANIFEST.json"),
        "package_file_count":len(manifest["files"]), "frozen_dependency_count":len(manifest["frozen_files"]),
        "frozen_dependency_drift_count":0, "tested_code_equals_packaged_code":True,
        "cmd_execution":"PASS; actual delivered CMD, -PrecheckOnly -NoDelay, Windows PowerShell 5.1",
        "package_tests":report["unit_test_count"], "powershell_contract_tests":report["powershell_contract_test_count"], "legacy_reference_tests":legacy_tests.testsRun,
        "legacy_reference_test_output":test_log.getvalue(),
        "source_sha_before":p.EXPECTED_SHA,"source_sha_after":p.digest(manifest["source"]),
        "source_workbook_mutation":0,"db_sha_before":baseline,"db_sha_after":p.digest(db_path),
        "business_counts":actual,"run_directory_writable":True,"native_excel_execution":"NOT_EXECUTED",
        "native_result_count":0,"user_action":"DOUBLE_CLICK_ONLY","production_write":0,"migration":0,
        "input_files":len(source_inputs), "inputs":{name:p.digest(name) for name in source_inputs},
        "checks":report["checks"],"precheck_reference_counts":report["reference_precheck_counts"],
        "audit_script_sha":p.digest(__file__),"user_manual_validation":"PENDING",
    }
    p.write(REPO / "docs/evidence/NATIVE_EXCEL_RUNNER_PACKAGE_VALIDATION.json", output)
    print(json.dumps({k:v for k,v in output.items() if k not in ("inputs","checks","legacy_reference_test_output")}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
