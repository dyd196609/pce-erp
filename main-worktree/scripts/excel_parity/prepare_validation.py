"""Prepare typed cases and source exception evidence; never fabricate Golden values."""
from __future__ import annotations

import collections
import copy
import json
import re
from pathlib import Path
from workbook_source import *
from formula_ast import Parser, walk, normalize
from analyze import label, semantic, ROW_START


def load(name):
    return json.loads((OUT/name).read_text(encoding="utf-8"))


def contract(book, sheet, addr):
    name=label(book,sheet,addr)
    fmt=book.sheets[sheet].get(addr,{}).get("number_format","General")
    # Source formatting is evidence, not authority to invent ERP business precision.
    integer=any(x in name for x in ("数量","张","开料数")) or name in ("门套高","门套宽","门墙厚","门高","门厚")
    unit="m²" if "平方" in name else "m" if name in ("封边长度","封边皮25","封边皮50") else "mm" if name in ("门套高","门套宽","门墙厚","门高","门宽","门厚") else "SOURCE_UOM_OR_UNRESOLVED"
    fmtbase=fmt.split(";")[0]
    fixed=re.fullmatch(r"(?:#,##)?0(?:\.(0+))?",fmtbase)
    precision=0 if integer else len(fixed[1] or "") if fixed else None
    return {"source_number_format":fmt,"uom":unit,"precision":precision,"rounding":"ROUND_HALF_UP" if precision is not None else None,
            "comparison":"TYPED_INTEGER_EXACT" if integer else "TYPED_SOURCE_DISPLAY_EXACT_WITH_RAW_DELTA" if precision is not None else "TYPED_RAW_EXACT_NO_TOLERANCE",
            "precision_authority":"integer field label" if integer else "Excel explicit number format; domain precision not approved" if precision is not None else "not defined; raw equality only, mismatch cannot be waived"}


def main():
    b=SourceBook()
    families=load("FORMULA_FAMILY_INVENTORY.json")
    graph=load("DEPENDENCY_GRAPH.json")["nodes"]
    real_rows=load("SOURCE_REAL_ROWS.json")
    cells_map=families["cell_to_family"]
    fs=families["families"]
    cases=[]
    def case(case_id,level,sheet,row,outputs,overrides=None,why=None):
        constants={sheet+"!"+a:{"value":c["value"],"type":c["type"],"label":label(b,sheet,a)} for a,c in b.sheets[sheet].items() if coord(a)[0]==row and not c["formula"]}
        return {"case_id":case_id,"level":level,"source_sheet":sheet,"source_row":row,"source_sha":EXPECTED_SHA,"input_facts":constants,
            "lookup_facts_reference":"MASTER_DATA_SNAPSHOT.json","overrides":overrides or [],"case_provenance":"SOURCE_REAL_ROW" if level in (2,3) else "FORMULA_UNIT_PRECEDENT_OVERRIDE" if overrides else "SOURCE_FORMULA_OR_AGGREGATE",
            "branch_evidence":why,"derived_outputs":[{"cell":sheet+"!"+a,"formula_family":cells_map.get(sheet+"!"+a),"semantic_name":semantic(b,sheet,a),"label":label(b,sheet,a),"formula":b.sheets[sheet].get(a,{}).get("formula"),"contract":contract(b,sheet,a),
                "excel_displayed_value":None,"excel_raw_value":None,"golden_status":"NOT_EXECUTED","source_cached_value":b.sheets[sheet].get(a,{}).get("value"),"source_cached_type":b.sheets[sheet].get(a,{}).get("type")} for a in outputs]}
    boundaries=[]
    for f in fs:
        sheet,addr=f["source_cells"][0].rsplit("!",1)
        row,_=coord(addr)
        cases.append(case("UNIT_"+f["family_id"],1,sheet,row,[addr]))
        tree=Parser().parse(f["source_formula"],allow_broken=True)
        unique={}
        for node in walk(tree):
            if node["kind"]!="binary" or node["operator"] not in ("=","<>","<",">","<=",">="):
                continue
            left,right=node["left"],node["right"]
            if left["kind"]=="reference" and right["kind"] in ("number","text","boolean"):
                ref=left["value"]
                if "!" in ref or ":" in ref: continue
                literal=right["value"]
                samples=[literal]
                if right["kind"]=="number": samples=[literal-1,literal,literal+1]
                for sample in samples:
                    unique[(ref,str(type(sample)),str(sample))]=(sample,node)
        if sheet not in TARGETS or row<ROW_START[sheet]: continue
        for (ref,typ,value),(sample,node) in unique.items():
            cid=f"BOUNDARY_{f['family_id']}_{len(boundaries)+1:04}"
            overrides=[{"sheet":sheet,"cell":ref.replace("$",""),"value":sample,"type":"boolean" if isinstance(sample,bool) else "number" if isinstance(sample,(int,float)) else "text"}]
            item=case(cid,1,sheet,row,[addr],overrides,node)
            cases.append(item)
            boundaries.append({"case_id":cid,"family_id":f["family_id"],"source_formula":f["source_formula"],"predicate":node,"overrides":overrides,"broken_source":f["broken"]})
    for sheet,rows in real_rows.items():
        for row in rows:
            outputs=[a for a,c in b.sheets[sheet].items() if coord(a)[0]==row and c["formula"]]
            cases.append(case("ROW_"+sheet+"_"+str(row),2 if row==rows[0] else 3,sheet,row,outputs))
        aggregates=[a for a,c in b.sheets[sheet].items() if c["formula"] and any(n["kind"]=="call" and n["name"] in ("SUM","SUMIF","SUMIFS") for n in walk(Parser().parse(c["formula"],allow_broken=True)))]
        for a in aggregates:
            cases.append(case("AGGREGATE_"+sheet+"_"+a,4,sheet,coord(a)[0],[a]))
    for a,c in b.sheets["材料清单"].items():
        if c["formula"]:
            cases.append(case("MATERIAL_SUMMARY_"+a,5,"材料清单",coord(a)[0],[a]))
    dump("EXCEL_GOLDEN_CASES.json",{"oracle":"Microsoft Excel required; cached values are not Golden", "source_sha":EXPECTED_SHA,"execution_status":"NOT_EXECUTED","cases":cases})
    dump("BRANCH_BOUNDARY_CASES.json",boundaries)
    master={}
    for key,node in graph.items():
        if node["kind"] not in ("VALUE","FORMULA"):continue
        s,a=key.rsplit("!",1)
        if s not in TARGETS and s in b.sheets and a in b.sheets[s]:
            master[key]=b.sheets[s][a]
    dump("MASTER_DATA_SNAPSHOT.json",{"source_sha":EXPECTED_SHA,"role":"Excel parity lookup snapshot only; not PCE formal master data", "cells":master})
    candidates=[]
    for f in fs:
        if not f["broken"] or f["sheet"]!="三合一生产单":continue
        tree=Parser().parse(f["source_formula"],allow_broken=True)
        if tree.get("name")!="IF" or len(tree["arguments"])<2 or tree["arguments"][1].get("value")!="#REF!":continue
        origin=f["source_cells"][0].rsplit("!",1)[1]
        predicate=copy.deepcopy(tree["arguments"][0])
        for n in walk(predicate):
            if n["kind"]=="reference":
                n["value"]=re.sub(r"\d+","7",n["value"]).replace("J","E").replace("L","G")
        matches=[]
        for sh in ("木饰面","柜子单","隐形门模板 (2)"):
            for a,c in b.sheets[sh].items():
                if coord(a)[0]!=7 or not c["formula"] or "#REF!" in c["formula"]:continue
                other=Parser().parse(c["formula"])
                if other.get("name")=="IF" and other["arguments"][0]==predicate and other["arguments"][1]=={"kind":"reference","value":"T7"}:
                    matches.append({"sheet":sh,"cell":a,"formula":c["formula"],"output_precedent":"T7","precedent_formula":b.sheets[sh]["T7"]["formula"],"cached_value":c["value"]})
        if matches:
            row=coord(origin)[0]
            candidates.append({"family_id":f["family_id"],"status":"CANDIDATE","source_cells":f["source_cells"],"broken_formula":f["source_formula"],"candidate_formula":f["source_formula"].replace("#REF!", "S"+str(row)),
                "mapping":{"E_height":"J_height","F_width":"K_width","G_thickness":"L_thickness","H_quantity":"M_quantity","T_area_formula":"S_product_area_formula"},"evidence":matches,"candidate_applied":False,"verified":False,
                "remaining_evidence":"Native Excel candidate execution, zero/blank/guard differences of T vs S, business approval; no original replacement"})
    dump("CANDIDATE_FORMULA_RECONSTRUCTION.json",candidates)
    external=[{**n,"status":"LEGACY_OUT_OF_SCOPE","used_by_target_formula":False} for n in b.names if "[" in (n["expression"] or "") or "#REF!" in (n["expression"] or "")]
    dump("LEGACY_EXTERNAL_DEPENDENCIES.json",{"names":external,"external_links":b.external_links,"target_external_dependencies":[k for k,v in graph.items() if v["kind"]=="LEGACY_EXTERNAL_REFERENCE"],"note":"No target named references found; validation dropdown external ranges retained as source metadata, not executed."})
    material=[]
    for a,c in b.sheets["材料清单"].items():
        if c["formula"]:
            material.append({"cell":a,"formula":c["formula"],"status":"BROKEN_SOURCE" if "#REF!" in c["formula"] else "BROKEN_DEPENDENCY_D25" if "D25" in c["formula"] else "UNVERIFIED"})
    absent=[]
    for term in ("玻璃","铰链","锁","合页"):
        occurrences=[{"sheet":s,"cell":a,"value":c["value"],"formula":c["formula"]} for s,cells in b.sheets.items() if s in TARGETS or s=="材料清单" for a,c in cells.items() if term in str(c["value"]) or term in (c["formula"] or "")]
        status="BROKEN_SOURCE" if term in ("锁","合页") else "NOT_IN_EXCEL / USER_RULE_REQUIRED"
        absent.append({"business_output":term,"status":status,"scope":"executable dedicated material-quantity rule in authoritative closure + material summary", "occurrences":occurrences,
            "explanation":"材料清单 D33=D25 / D35=3*D25 exists, but D25=SUM(房门单!#REF!); not absent, do not invent a replacement" if term in ("锁","合页") else "Product names/input labels do not establish an executable dedicated procurement/consumption rule; no full rule found in inspected closure"})
    dump("MATERIAL_SUMMARY_SOURCE_AUDIT.json",{"formulas":material,"absent_or_broken_rules":absent})
    drift=[]
    for f in fs:
        if f["sheet"]!="房门单":continue
        addresses=[k.rsplit("!",1)[1] for k in f["source_cells"]]
        if not any(coord(a)[0] in real_rows["房门单"] for a in addresses):
            drift.append({"family_id":f["family_id"],"cells":f["source_cells"],"header_label":f["semantic_output"],"status":"UNUSED_TEMPLATE_OR_SUMMARY_REQUIRES_SEMANTIC_REVIEW","formula":f["source_formula"]})
    dump("SOURCE_TEMPLATE_DRIFT.json",{"warning":"Row 19+ / later template formulas have shifted-column variants. Header-derived names are provisional, not ERP semantics.","families":drift})
    print(json.dumps({"cases":len(cases),"by_level":dict(collections.Counter(c["level"] for c in cases)),"boundary_cases":len(boundaries),"reconstruction_candidates":len(candidates),"external_or_broken_names":len(external),"material_summary_formulas":len(material),"master_snapshot_cells":len(master)},ensure_ascii=False))


if __name__=="__main__":main()
