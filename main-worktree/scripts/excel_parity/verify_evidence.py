"""Package/build checks, private technical tests, SQLite read-only protection."""
from __future__ import annotations

import collections
import contextlib
import io
import json
import py_compile
import sqlite3
import unittest
from pathlib import Path
from workbook_source import SOURCE, ALTERNATE, OUT, EXPECTED_SHA, digest, dump
from test_reference import ReferenceTests

DB=Path(__file__).resolve().parents[2]/"backend/db.sqlite3"
BASELINE_DB_SHA="9DADFB55D446DF052A4DCF6CF2EE552906939FD1B65D7D899C5FD8C1AC368F5C"


def main():
    compiled=[]
    for path in Path(__file__).parent.glob("*.py"):
        py_compile.compile(str(path),doraise=True)
        compiled.append(path.name)
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReferenceTests))
    dump("TECHNICAL_TEST_RESULTS.json",{"test_role":"candidate adapter technical checks, never Excel oracle/parity", "run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"success":result.wasSuccessful(),"log":stream.getvalue(),"compiled_files":compiled})
    connection=sqlite3.connect(DB.as_uri()+"?mode=ro",uri=True)
    connection.execute("PRAGMA query_only = ON")
    tables={r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    wanted={"Operation":"system_process","Routing":"pde_routing","RoutingVersion":"pde_routing_version","RoutingStep":"pde_routing_step","EngineeringRuleDefinition":"pde_engineering_rule_definition","EngineeringCalculation":"pde_engineering_calculation_record","CalculationDetail":"pde_engineering_calculation_detail","EngineeringDerivedFact":"pde_engineering_derived_fact","ProductBOM":"pde_product_bom","BOMItem":"pde_bom_item","StandardCapacity":"pde_standard_capacity"}
    counts={name:connection.execute('SELECT COUNT(*) FROM "'+table+'"').fetchone()[0] if table in tables else "TABLE_NAME_NOT_FOUND" for name,table in wanted.items()}
    journal=connection.execute("PRAGMA journal_mode").fetchone()[0]
    connection.close()
    functions=json.loads((OUT/"FORMULA_FAMILY_INVENTORY.json").read_text(encoding="utf-8"))["families"]
    results=json.loads((OUT/"DIFFERENTIAL_RESULTS.json").read_text(encoding="utf-8"))["results"]
    source_inventory=json.loads((OUT/"FORMULA_INVENTORY.json").read_text(encoding="utf-8"))
    coverage={"actual_functions_authoritative":sorted({n for x in source_inventory["items"] if x["scope"]=="AUTHORITATIVE" for n in x["functions"]}),"actual_functions_closure":sorted({n for f in functions for n in f["functions"]}),"implemented_dispatch_count":21,"native_verified_function_count":0,"limitations":["Exact lookup mode only; approximate sorted lookup is explicitly unsupported","TEXT supports only inventoried 00/000 numeric formats","CHAR supports ASCII; non-ASCII locale-sensitive values unsupported","INDEX array results and implicit intersection unsupported","Microsoft Excel session required to validate coercion, IFS evaluation and numeric edge semantics"]}
    dump("TRANSLATOR_FUNCTION_COVERAGE.json",coverage)
    protection={"source_sha_before":EXPECTED_SHA,"source_sha_after":digest(SOURCE),"source_unchanged":digest(SOURCE)==EXPECTED_SHA,"alternate_sha_after":digest(ALTERNATE),"database_sha_before":BASELINE_DB_SHA,"database_sha_after":digest(DB),"database_unchanged":digest(DB)==BASELINE_DB_SHA,"database_read_mode":"SQLite mode=ro + PRAGMA query_only=ON", "formal_counts":counts,"production_real_rule_write":0,"bom_write":0,"capacity_real_write":0,"planning_write":0,"production_batch_write":0,"ui_navigation_api_migration_changes":False,"frozen_groups":"1/2/3A/3B preserved by unchanged complete DB hash; no replay"}
    protection.update(database_journal_mode=journal,wal_file_exists=Path(str(DB)+"-wal").exists())
    dump("PROTECTION_EVIDENCE.json",protection)
    assert protection["source_unchanged"] and protection["database_unchanged"]
    assert result.wasSuccessful()
    assert counts["Operation"]==33 and counts["Routing"]==42 and counts["RoutingVersion"]==42 and counts["RoutingStep"]==1137
    assert len(results)==sum(len(c["derived_outputs"]) for c in json.loads((OUT/"EXCEL_GOLDEN_CASES.json").read_text(encoding="utf-8"))["cases"])
    manifest={"scope":"isolated non-production reference source and evidence, no web/backend deploy", "source_files":{str(p.relative_to(Path(__file__).resolve().parents[2])):digest(p) for p in sorted(Path(__file__).parent.glob("*")) if p.is_file()},"evidence_files":{p.name:digest(p) for p in sorted(OUT.glob("*.json")) if p.name!="PACKAGE_MANIFEST.json"}}
    dump("PACKAGE_MANIFEST.json",manifest)
    print(json.dumps({"technical_tests":result.testsRun,"technical_pass":result.wasSuccessful(),"source_unchanged":protection["source_unchanged"],"db_unchanged":protection["database_unchanged"],"counts":counts,"generated_functions":sum(f["translation_status"]=="TRANSLATED_NOT_GOLDEN_VERIFIED" for f in functions),"parity_pass":sum(r["status"]=="PASS" for r in results),"coverage":coverage},ensure_ascii=False))


if __name__=="__main__":main()
