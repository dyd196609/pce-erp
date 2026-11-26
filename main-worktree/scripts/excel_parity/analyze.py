"""Inventory, provenance, dependency closure, family lowering and case preparation."""
from __future__ import annotations

import collections
import hashlib
import json
import re
from pathlib import Path

from workbook_source import SourceBook, TARGETS, OUT, SOURCE, ALTERNATE, EXPECTED_SHA, coord, address, dump, digest
from formula_ast import Parser, Unsupported, BrokenSource, functions, references, normalize, split_reference, generate_expression, walk

ROW_START = {"房门单": 11, "三合一生产单": 7}
HEADER = {"房门单": 10, "三合一生产单": 6, "木门单公式": 6, "木饰面": 6, "柜子单": 6, "隐形门模板 (2)": 6}
ENGLISH = {"洞高":"opening_height_mm", "洞宽":"opening_width_mm", "墙厚":"wall_thickness_mm", "门洞数量":"opening_quantity", "门套高":"frame_height_mm", "门套宽":"frame_width_mm", "门墙厚":"frame_wall_thickness_mm", "门套数量":"frame_quantity", "门高":"leaf_height_mm", "门宽":"leaf_width_or_pair_description", "门厚":"leaf_thickness_mm", "门数量":"leaf_quantity", "单位":"uom", "见光平方":"visible_area_m2", "套板平方":"frame_area_m2", "门面板张":"door_face_panel_count", "封边皮25":"edge_veneer_25_length_m", "封边皮50":"edge_veneer_50_length_m", "封边长度":"edge_length_m", "产品平方":"product_area_m2", "高":"height_mm", "宽":"width_mm", "厚":"thickness_mm", "数量":"quantity", "产品名称":"product_name", "油漆工艺(必填)":"paint_process", "单/双":"exposed_sides", "封边":"edge_selection", "颜色/版号":"finish_reference", "物料编码(必填)":"material_code", "工艺编码(必填)":"process_code", "线规格":"trim_specification", "开料长度":"cut_length_mm", "开料数":"cut_quantity", "序号":"row_number"}


def label(book, sheet, addr):
    row, col = coord(addr)
    header = HEADER.get(sheet, 1)
    if row > header:
        head = book.sheets[sheet].get(address(header, col), {})
        if head.get("value") is not None and not head.get("formula"):
            return str(head["value"]).replace("\n", " ")
    # Top summary labels usually sit immediately to the left, not in body headers.
    for offset in (1, 2):
        left = book.sheets[sheet].get(address(row, max(1, col-offset)), {})
        if isinstance(left.get("value"), str) and not left.get("formula"):
            return left["value"].replace("\n", " ")
    return "语义待核对_" + re.sub(r"\d", "", addr)


def semantic(book, sheet, addr):
    name = label(book, sheet, addr)
    return ENGLISH.get(name, re.sub(r"\W+", "_", name).strip("_") or "unresolved_output")


def safe_name(text):
    result = re.sub(r"\W", "_", text)
    return "field_" + result if not result or result[0].isdigit() else result


def is_real_row(book, sheet, row):
    start = ROW_START[sheet]
    cell = book.sheets[sheet].get(("H" if sheet == "房门单" else "G")+str(row), {})
    height = book.sheets[sheet].get("J"+str(row), {})
    return row >= start and bool(cell.get("value")) and not cell.get("formula") and isinstance(height.get("value"), (int,float))


def main():
    book = SourceBook()
    assert digest(SOURCE) == EXPECTED_SHA
    parsed, inventory, parse_errors = {}, [], []
    for sheet, cells in book.sheets.items():
        for addr, cell in cells.items():
            if not cell["formula"]:
                continue
            key = sheet+"!"+addr
            broken = "#REF!" in cell["formula"]
            try:
                tree = Parser().parse(cell["formula"], allow_broken=True)
                parsed[key] = tree
                funcs, refs = functions(tree), references(tree)
            except Unsupported as exc:
                funcs, refs = [], []
                parse_errors.append({"cell": key, "error": str(exc)})
            inventory.append({"cell": key, "sheet": sheet, "address": addr, "formula": cell["formula"], "functions": funcs, "references": refs, "broken": broken, "scope": "AUTHORITATIVE" if sheet in TARGETS else "INVENTORY_ONLY"})
    by_key = {x["cell"]:x for x in inventory}
    graph, pending, seen = {}, [x["cell"] for x in inventory if x["sheet"] in TARGETS], set()
    # Engineering identity/space/specification/UOM facts remain relevant even
    # when no formula consumes them. Do not lose such input provenance.
    pending.extend(s+"!"+a for s in TARGETS for a in book.sheets[s] if is_real_row(book,s,coord(a)[0]))
    roots = list(pending)
    # Cells and shared range nodes avoid expanding each lookup into a duplicate table.
    while pending:
        key = pending.pop()
        if key in seen:
            continue
        seen.add(key)
        sheet, addr = key.rsplit("!", 1)
        if sheet not in book.sheets:
            graph[key] = {"kind": "UNRESOLVED_REFERENCE", "dependencies": []}
            continue
        if ":" in addr:
            try:
                target, parts = split_reference(addr, sheet)
                full = not re.search(r"\d", addr)
                r1,c1 = coord(parts[0]+"1" if full else parts[0])
                r2,c2 = coord(parts[1]+"1048576" if full else parts[1])
                dependencies = [sheet+"!"+a for a in book.sheets[sheet] if r1<=coord(a)[0]<=r2 and c1<=coord(a)[1]<=c2]
                graph[key] = {"kind":"RANGE", "shape":[r2-r1+1,c2-c1+1], "blank_cells":"implicit BLANK; not zero", "dependencies":dependencies}
                pending.extend(dependencies)
            except (ValueError, Unsupported, BrokenSource):
                graph[key] = {"kind":"UNRESOLVED_REFERENCE", "dependencies":[]}
            continue
        cell = book.sheets[sheet].get(addr, {})
        dependencies = []
        for ref in references(parsed[key]) if key in parsed else []:
            try:
                target, parts = split_reference(ref, sheet)
                dep = target+"!"+":".join(p.replace("$", "") for p in parts)
                dependencies.append(dep)
                pending.append(dep)
            except (Unsupported, BrokenSource):
                matches = [n for n in book.names if n["name"].casefold() == ref.casefold()]
                dep = "NAME_OR_EXTERNAL:"+ref
                dependencies.append(dep)
                graph[dep] = {"kind":"LEGACY_EXTERNAL_REFERENCE" if "[" in ref or any("[" in (n["expression"] or "") for n in matches) else "UNRESOLVED_REFERENCE", "defined_names": matches, "dependencies":[]}
        graph[key] = {"kind":"FORMULA" if cell.get("formula") else "VALUE", "semantic_name":semantic(book,sheet,addr), "label":label(book,sheet,addr), "dependencies":dependencies}
    relevant = {key for key,v in graph.items() if v["kind"] != "RANGE"}
    families, mapping = {}, {}
    for item in inventory:
        key, sheet, addr = item["cell"], item["sheet"], item["address"]
        if key not in relevant:
            continue
        tree = parsed.get(key)
        normalized = normalize(tree, addr) if tree else {"unsupported":item["formula"]}
        # Do not merge differently named output columns just because structure matches.
        payload = [sheet, semantic(book,sheet,addr), normalized]
        family_id = "FF_"+hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:12]
        mapping[key] = family_id
        if family_id not in families:
            families[family_id] = {"family_id":family_id, "sheet":sheet, "semantic_output":label(book,sheet,addr), "semantic_name":semantic(book,sheet,addr), "normalized_formula":normalized,
                "source_formula":item["formula"], "source_cells":[], "input_dependencies":item["references"], "lookup_dependencies":[n["arguments"][1] if n["name"] in ("VLOOKUP","MATCH") else n["arguments"][0] for n in walk(tree) if n["kind"]=="call" and n["name"] in ("INDEX","VLOOKUP","MATCH")] if tree else [],
                "functions":item["functions"], "broken":item["broken"], "translation_status":"BROKEN_SOURCE" if item["broken"] else "PENDING_TRANSLATION", "ast":None if item["broken"] else tree}
        families[family_id]["source_cells"].append(key)
    code = ['"""AUTO-GENERATED from immutable Excel source AST. NON-PRODUCTION reference only.', 'Do not edit formulas here; regenerate with analyze.py. Golden parity pending.', '"""', '']
    function_map = []
    for family_id, f in families.items():
        f["cell_count"] = len(f["source_cells"])
        if f["broken"] or not f["ast"]:
            continue
        origin = f["source_cells"][0].rsplit("!",1)[1]
        function = safe_name(f["semantic_name"])+"__"+family_id.lower()
        aliases = {}
        declarations = []
        for idx,ref in enumerate(references(f["ast"])):
            try:
                sh, parts = split_reference(ref,f["sheet"])
                base_label = semantic(book,sh,parts[0].replace("$","")) if len(parts)==1 and re.search(r"\d",parts[0]) else "lookup_or_aggregate_range"
            except (KeyError,Unsupported,BrokenSource):
                base_label = "unresolved_reference"
            alias = safe_name(base_label)+"_"+str(idx+1)
            aliases[ref] = alias
            r,c = coord(origin)
            declarations.append(f"    {alias} = lambda: ctx.reference({ref!r}, {f['sheet']!r}, row - {r}, col - {c})")
        try:
            expression = generate_expression(f["ast"], origin, f["sheet"], aliases)
        except Unsupported as exc:
            f["translation_status"] = "UNSUPPORTED"
            f["translation_error"] = str(exc)
            continue
        f["translation_status"] = "TRANSLATED_NOT_GOLDEN_VERIFIED"
        f["generated_reference_function"] = function
        code += [f"# {family_id}: {f['sheet']} / {f['semantic_output']}", f"# Source: {f['source_cells'][0]} ({f['cell_count']} cells)", f"# Formula: {f['source_formula']}", f"def {function}(ctx, row, col):", *declarations, "    return "+expression, ""]
        function_map.append(f"    {family_id!r}: {function},")
    code += ["FUNCTIONS = {", *function_map, "}", ""]
    Path(__file__).with_name("generated_reference.py").write_text("\n".join(code),encoding="utf-8")
    reverse = collections.defaultdict(list)
    for k,v in graph.items():
        for dep in v["dependencies"]:
            reverse[dep].append(k)
    broken_register = []
    for item in inventory:
        if item["broken"] and item["cell"] in graph:
            affected, queue = set(), list(reverse[item["cell"]])
            while queue:
                downstream=queue.pop()
                if downstream in affected: continue
                affected.add(downstream)
                queue.extend(reverse[downstream])
            broken_register.append({**item,"family_id":mapping.get(item["cell"]), "upstream":graph[item["cell"]]["dependencies"], "downstream":sorted(affected), "business_outputs_affected":[{"cell":k,"label":graph[k].get("label")} for k in sorted(affected) if graph[k]["kind"]=="FORMULA" and k.split("!")[0] in TARGETS]})
    real_rows = {s:sorted({coord(a)[0] for a in book.sheets[s] if is_real_row(book,s,coord(a)[0])}) for s in TARGETS}
    provenance = []
    for key,node in graph.items():
        if node["kind"] == "RANGE" or "!" not in key or key.startswith("NAME_OR_EXTERNAL:"):
            continue
        sheet,addr=key.rsplit("!",1)
        if sheet not in book.sheets: continue
        cell=book.sheets[sheet].get(addr,{})
        formula=cell.get("formula")
        funcs=functions(parsed[key]) if key in parsed else []
        is_output = sheet in TARGETS and bool(formula) and coord(addr)[0]>=ROW_START[sheet]
        if formula:
            kind="BROKEN_FORMULA" if "#REF!" in formula else "LEGACY_EXTERNAL_REFERENCE" if "[" in formula else "AGGREGATION" if set(funcs)&{"SUM","SUMIF","SUMIFS"} else "MASTER_DATA_LOOKUP" if set(funcs)&{"INDEX","MATCH","VLOOKUP"} else "DERIVED_CALCULATION"
        elif sheet not in TARGETS:
            kind="MASTER_DATA_LOOKUP"
        elif coord(addr)[0] in real_rows[sheet] or addr in ({"I2","K2","N2","I3","V3","AB3"} if sheet=="房门单" else {"H2","J2","L2","H3"}):
            kind="MANUAL_ENGINEERING_INPUT"
        else:
            kind="UNRESOLVED"
        provenance.append({"cell":key,"label":node.get("label"),"semantic_name":node.get("semantic_name"),"classification":kind,"roles":[kind]+(["OUTPUT"] if is_output else []),"formula_present":bool(formula),"yellow_evidence":"FFFF00" in cell.get("fill", ""),"raw_value":cell.get("value") if not formula else None,"value_type":cell.get("type","blank"),"formula_family":mapping.get(key),"evidence":"formula/lookup/dependency/header/real-row; color not authoritative"})
    dump("FORMULA_INVENTORY.json", {"source_sha":EXPECTED_SHA,"formula_cells":len(inventory),"items":inventory,"parser_errors":parse_errors})
    dump("FORMULA_FAMILY_INVENTORY.json", {"families":list(families.values()),"cell_to_family":mapping})
    dump("CELL_PROVENANCE_MAP.json", {"scope":"target formula closure; static labels outside input boundary remain unresolved", "cells":provenance})
    dump("DEPENDENCY_GRAPH.json", {"direction":"output -> immediate precedents", "roots":roots,"nodes":graph})
    dump("BROKEN_FORMULA_REGISTER.json", broken_register)
    dump("SOURCE_REAL_ROWS.json",real_rows)
    semantic_sheet = book.sheets["木门单公式"]
    dump("SEMANTIC_CROSSCHECK.json", {"source_sha":EXPECTED_SHA,"sheet":"木门单公式","cells":semantic_sheet,
        "conflicts":[{"output":"子母门门宽", "source":"房门单!S11","crosscheck":"木门单公式!O10 / D4","difference":"权威房门单生成含大小扇的文本串；说明表输出数值总宽。不可用说明替换实际公式。"},
                    {"output":"见光/木皮面积", "source":"房门单!W11", "crosscheck":"木门单公式!W7 / D4","difference":"说明表有混油封闭排除；权威 W11 无排除分支。保留实际 Excel，不新增业务条件。"},
                    {"output":"封边皮25/50", "source":"房门单!Z11:AA11","crosscheck":"木门单公式!Z7:AA7","difference":"说明表引用 L(墙厚)，权威表引用 O(套宽)；不自动对齐。"}]})
    alt=SourceBook(ALTERNATE)
    dump("SOURCE_VARIANT_DIFFERENCE.json", {"sheet":"物料目录(设计)","cell":"V63","registered":book.sheets["物料目录(设计)"]["V63"],"alternate":alt.sheets["物料目录(设计)"]["V63"],"in_target_dependency_closure":"物料目录(设计)!V63" in graph})
    summary={"formula_cells_workbook":len(inventory),"formula_cells_authoritative":sum(x["sheet"] in TARGETS for x in inventory),"formula_cells_dependency_closure":len(mapping),"families_total":len(families),"families_by_sheet":dict(collections.Counter(f["sheet"] for f in families.values())),"translation_status":dict(collections.Counter(f["translation_status"] for f in families.values())),"real_rows":real_rows,"provenance_cells":dict(collections.Counter(x["classification"] for x in provenance)),"function_inventory":sorted({fn for item in inventory if item["sheet"] in TARGETS for fn in item["functions"]}),"parse_error_count":len(parse_errors),"broken_cells_closure":len(broken_register),"external_nodes":[k for k,v in graph.items() if v["kind"]=="LEGACY_EXTERNAL_REFERENCE"],"input_field_count":len({(x["cell"].split("!")[0],x["label"]) for x in provenance if x["classification"]=="MANUAL_ENGINEERING_INPUT"}),"lookup_field_count":len({(x["cell"].split("!")[0],x["label"]) for x in provenance if x["classification"]=="MASTER_DATA_LOOKUP"}),"derived_field_count":len({(x["cell"].split("!")[0],x["label"]) for x in provenance if "OUTPUT" in x["roles"]})}
    dump("ANALYSIS_SUMMARY.json",summary)
    fields=collections.defaultdict(list)
    for x in provenance:
        sh,a=x["cell"].rsplit("!",1)
        # Count physical source fields, not duplicate labels (e.g. two 线规格 columns).
        if sh in TARGETS and coord(a)[0] in real_rows[sh]:
            fields[(sh,coord(a)[1],x["classification"])].append(x)
    field_inventory=[{"sheet":sh,"column":address(1,col)[:-1],"classification":kind,"label":items[0]["label"],"semantic_name":items[0]["semantic_name"],"source_cells":[i["cell"] for i in items],"semantic_status":"SOURCE_HEADER_PROVISIONAL_NOT_DOMAIN_APPROVED"} for (sh,col,kind),items in sorted(fields.items())]
    dump("FIELD_INVENTORY.json",{"scope":"real source row fields only; same column with mixed formulas/constants yields separate provenance entries","fields":field_inventory,"counts":dict(collections.Counter(i["classification"] for i in field_inventory))})
    print(json.dumps(summary,ensure_ascii=False))


if __name__=="__main__":
    main()
