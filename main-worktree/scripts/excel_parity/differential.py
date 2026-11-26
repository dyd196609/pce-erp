"""Strict, level-gated native Excel / generated-code differential harness."""
from __future__ import annotations

import collections
import json
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from workbook_source import SourceBook, SOURCE, EXPECTED_SHA, OUT, digest, dump
from formula_ast import Unsupported, BrokenSource
from reference_runtime import Context, ExcelError, BLANK, serialized
from generated_reference import FUNCTIONS


def load(name):
    return json.loads((OUT/name).read_text(encoding="utf-8-sig"))


def compare_result(code, excel, contract):
    if code["type"]!=excel["type"]:
        return {"status":"FAIL","reason":"TYPE_MISMATCH","raw_numeric_delta":None}
    a,b=code["value"],excel["value"]
    if code["type"]!="number":
        return {"status":"PASS" if a==b else "FAIL","reason":"TYPED_EXACT","raw_numeric_delta":None}
    aa,bb=Decimal(str(a)),Decimal(str(b))
    delta=aa-bb
    mode=contract["comparison"]
    if mode=="TYPED_INTEGER_EXACT":
        equal=aa==bb and aa==aa.to_integral_value() and bb==bb.to_integral_value()
    elif mode=="TYPED_SOURCE_DISPLAY_EXACT_WITH_RAW_DELTA":
        quantum=Decimal(1).scaleb(-contract["precision"])
        equal=aa.quantize(quantum,rounding=ROUND_HALF_UP)==bb.quantize(quantum,rounding=ROUND_HALF_UP)
    else:
        equal=aa==bb
    return {"status":"PASS" if equal else "FAIL","reason":mode,"raw_numeric_delta":str(delta)}


def main():
    assert digest(SOURCE)==EXPECTED_SHA
    book=SourceBook()
    manifest=load("EXCEL_GOLDEN_CASES.json")
    families=load("FORMULA_FAMILY_INVENTORY.json")
    rows,levels=[],[]
    previous_pass=True
    base_context=Context(book,families["cell_to_family"],FUNCTIONS)
    for level in range(1,6):
        native_path=OUT/f"EXCEL_NATIVE_LEVEL_{level}.json"
        native=load(native_path.name) if native_path.exists() else {}
        native_valid=(native.get("status")=="PASS" and native.get("engine")=="Microsoft Excel" and native.get("source_sha")==EXPECTED_SHA and native.get("case_manifest_sha")==digest(OUT/"EXCEL_GOLDEN_CASES.json") and native.get("original_unchanged") is True)
        golden={r["case_id"]:{o["cell"]:o for o in r["outputs"]} for r in native.get("results",[])} if native_valid else {}
        level_rows=[]
        for case in [c for c in manifest["cases"] if c["level"]==level]:
            overrides={(o["sheet"],o["cell"]):BLANK if o["type"]=="blank" else o["value"] for o in case["overrides"]}
            ctx=Context(book,families["cell_to_family"],FUNCTIONS,overrides) if overrides else base_context
            for output in case["derived_outputs"]:
                row={"case_id":case["case_id"],"level":level,"cell":output["cell"],"formula_family":output["formula_family"],"semantic_name":output["semantic_name"],"contract":output["contract"],"code_result":None,"excel_raw_value":None,"excel_displayed_value":None,"raw_numeric_delta":None}
                if "#REF!" in (output["formula"] or ""):
                    row.update(status="BROKEN_SOURCE",reason="FORMULA_TEXT_CONTAINS_REF; not translated or accepted")
                elif not previous_pass:
                    row.update(status="UNSUPPORTED",reason="PREVIOUS_LEVEL_NOT_PASS; calculation not executed")
                else:
                    sheet,addr=output["cell"].rsplit("!",1)
                    try:
                        try: value=ctx.cell(sheet,addr)
                        except ExcelError as exc: value=exc
                        row["code_result"]=serialized(value)
                        oracle=golden.get(case["case_id"],{}).get(output["cell"])
                        if not oracle:
                            row.update(status="UNSUPPORTED",reason="EXCEL_GOLDEN_NOT_EXECUTED_OR_UNVERIFIED; code result not proof")
                        else:
                            row.update(excel_raw_value=oracle["excel_raw_value"],excel_displayed_value=oracle["excel_displayed_value"])
                            row.update(compare_result(row["code_result"],row["excel_raw_value"],row["contract"]))
                    except BrokenSource as exc:
                        row.update(status="BROKEN_SOURCE",reason=str(exc))
                    except Unsupported as exc:
                        row.update(status="UNSUPPORTED",reason=str(exc))
                level_rows.append(row)
        counts=dict(collections.Counter(r["status"] for r in level_rows))
        passed=bool(level_rows) and all(r["status"]=="PASS" for r in level_rows)
        levels.append({"level":level,"status":"PASS" if passed else "BLOCKED","executed_as_parity":native_valid and previous_pass,"output_count":len(level_rows),"results":counts,"native_status":native.get("status","NOT_EXECUTED"),"native_error":native.get("error"),"prior_gate_pass":previous_pass})
        previous_pass=passed
        rows.extend(level_rows)
    dump("DIFFERENTIAL_RESULTS.json",{"source_sha":EXPECTED_SHA,"case_manifest_sha":digest(OUT/"EXCEL_GOLDEN_CASES.json"),"generated_code_sha":digest(__file__.replace("differential.py","generated_reference.py")),"timestamp":datetime.now(timezone.utc).isoformat(),"results":rows})
    dump("PARITY_GATES.json",{"source_sha":EXPECTED_SHA,"levels":levels,"domain_formalization_allowed":all(l["status"]=="PASS" for l in levels),"production_business_write":0})
    candidate_ids={f["family_id"] for f in load("CANDIDATE_FORMULA_RECONSTRUCTION.json")}
    matrix=[]
    for f in families["families"]:
        actual=[r for r in rows if r["formula_family"]==f["family_id"] and r["level"]==1]
        results=dict(collections.Counter(r["status"] for r in actual))
        state="NEEDS_RECONSTRUCTION" if f["family_id"] in candidate_ids else "BROKEN_SOURCE" if f["broken"] else "PARITY_PASS" if actual and all(r["status"]=="PASS" for r in actual) else "PARITY_FAIL" if any(r["status"]=="FAIL" for r in actual) else None
        matrix.append({"Excel Source":f["source_cells"],"Formula Family":f["family_id"],"Business Meaning":f["semantic_output"],"Current Status":state,"Execution Readiness":"BLOCKED_ORACLE_OR_SOURCE" if state is None else state,"Code Function":f.get("generated_reference_function"),"Golden Cases":[r["case_id"] for r in actual],"Parity Result":results,"Final ERP Rule Target":"existing EngineeringRuleDefinition -> CalculationDetail -> EngineeringDerivedFact after explicit domain authorization; not written","status_note":"Null is intentionally unadjudicated; no native result is neither PARITY_PASS nor PARITY_FAIL" if state is None else ""})
    dump("FORMULA_MIGRATION_MATRIX.json",matrix)
    print(json.dumps({"levels":levels,"result_count":len(rows),"passed":sum(r["status"]=="PASS" for r in rows)},ensure_ascii=False))


if __name__=="__main__":main()
