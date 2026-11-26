"""Read-only OOXML evidence reader. No formula evaluation or workbook writes."""
from __future__ import annotations

import hashlib
import json
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from openpyxl.formula.translate import Translator
from openpyxl.styles.numbers import BUILTIN_FORMATS

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
SOURCE = Path(r"C:\Users\DAODA\Documents\Codex\2026-09-01\files-pasted-by-the-user-pce\outputs\PCE_WAVE2_BUSINESS_FACT_RECONSTRUCTION_SOURCE_GOVERNANCE_V1.0\sources\工程拆单及订单排产数据核算方式.xlsx")
ALTERNATE = Path(r"C:\Users\DAODA\Documents\Codex\2026-09-01\files-pasted-by-the-user-pce\outputs\PCE_WAVE2_SOURCE_DISCOVERY_READINESS_V1.0\sources\工程拆单及订单排产数据核算方式.xlsx")
EXPECTED_SHA = "7ED132C13F6F7B13F5805F3872EC06528D9342A8E821A4D6F3D8B571243FB122"
OUT = Path(__file__).resolve().parents[2] / "docs/evidence/excel_formula_parity"
TARGETS = ("房门单", "三合一生产单")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def dump(name, data):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def coord(address):
    m = re.fullmatch(r"\$?([A-Z]+)\$?(\d+)", address)
    if not m:
        raise ValueError(address)
    col = 0
    for x in m[1]:
        col = col * 26 + ord(x) - 64
    return int(m[2]), col


def address(row, col):
    result = ""
    while col:
        col, x = divmod(col - 1, 26)
        result = chr(65 + x) + result
    return result + str(row)


class SourceBook:
    def __init__(self, path=SOURCE):
        self.path = Path(path)
        self.sheets = {}
        self.inventory = []
        self.names = []
        self.external_links = []
        with zipfile.ZipFile(path) as z:
            root = ET.fromstring(z.read("xl/workbook.xml"))
            rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
            strings = []
            if "xl/sharedStrings.xml" in z.namelist():
                strings = ["".join(si.itertext()) for si in ET.fromstring(z.read("xl/sharedStrings.xml"))]
            styles = ET.fromstring(z.read("xl/styles.xml"))
            formats = dict(BUILTIN_FORMATS)
            for e in styles.findall("s:numFmts/s:numFmt", NS):
                formats[int(e.get("numFmtId"))] = e.get("formatCode")
            xfs = list(styles.find("s:cellXfs", NS))
            fills = [ET.tostring(e, encoding="unicode") for e in styles.find("s:fills", NS)]
            self.names = [dict(e.attrib, expression=e.text) for e in root.findall("s:definedNames/s:definedName", NS)]
            for name in z.namelist():
                if name.startswith("xl/externalLinks/") and name.endswith(".rels"):
                    self.external_links.extend(dict(e.attrib) for e in ET.fromstring(z.read(name)))
            for sh in root.findall("s:sheets/s:sheet", NS):
                target = rels[sh.get(R)]
                member = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
                xml = ET.fromstring(z.read(member))
                cells, shared = {}, {}
                for e in xml.findall("s:sheetData/s:row/s:c", NS):
                    addr, typ = e.get("r"), e.get("t", "n")
                    v, f = e.find("s:v", NS), e.find("s:f", NS)
                    raw = v.text if v is not None else None
                    if typ == "s" and raw is not None:
                        value = strings[int(raw)]
                    elif typ == "inlineStr":
                        value = "".join(e.find("s:is", NS).itertext())
                    elif typ == "b":
                        value = raw == "1"
                    elif typ == "n" and raw is not None:
                        value = float(raw) if re.search(r"[.eE]", raw) else int(raw)
                    else:
                        value = raw
                    formula = None
                    if f is not None:
                        formula = "=" + (f.text or "")
                        if f.get("t") == "shared":
                            si = f.get("si")
                            if f.text:
                                shared[si] = (addr, formula)
                            else:
                                origin, base = shared[si]
                                formula = Translator(base, origin=origin).translate_formula(addr)
                    # Ignore format-only ocean cells; retain style on actual facts/formulas.
                    if formula is None and value is None:
                        continue
                    xf = xfs[int(e.get("s", 0))]
                    cells[addr] = {"value": value, "cached_raw": raw, "type": typ,
                                   "formula": formula, "number_format": formats.get(int(xf.get("numFmtId", 0)), "General"),
                                   "fill": fills[int(xf.get("fillId", 0))], "style_id": int(e.get("s", 0))}
                self.sheets[sh.get("name")] = cells
                self.inventory.append({"sheet": sh.get("name"), "state": sh.get("state", "visible"),
                                       "dimension": xml.find("s:dimension", NS).get("ref"),
                                       "nonempty_cells": len(cells), "formula_cells": sum(bool(c["formula"]) for c in cells.values()),
                                       "worksheet_xml_sha": hashlib.sha256(z.read(member)).hexdigest().upper(),
                                       "data_validations": [dict(e.attrib, formula1=e.findtext("s:formula1", namespaces=NS)) for e in xml.findall("s:dataValidations/s:dataValidation", NS)]})


def main():
    book = SourceBook()
    if digest(SOURCE) != EXPECTED_SHA:
        raise SystemExit("Source registration mismatch; refuse a silently changed source")
    alt = SourceBook(ALTERNATE)
    differences = []
    for sheet in set(book.sheets) | set(alt.sheets):
        current, older = book.sheets.get(sheet, {}), alt.sheets.get(sheet, {})
        changed = [a for a in set(current) | set(older) if current.get(a) != older.get(a)]
        if changed:
            differences.append({"sheet": sheet, "cell_difference_count": len(changed), "examples": sorted(changed, key=coord)[:12]})
    freeze = {"source": str(SOURCE), "sha256": digest(SOURCE), "size_bytes": SOURCE.stat().st_size,
              "authority_evidence": "backend/masterdata/group3_comparison_source.json generatedFrom SHA",
              "alternate": {"path": str(ALTERNATE), "sha256": digest(ALTERNATE), "size_bytes": ALTERNATE.stat().st_size, "differences": differences},
              "authoritative_sheets": TARGETS, "semantic_crosscheck": "木门单公式", "sheets": book.inventory,
              "defined_names": book.names, "external_links": book.external_links, "original_opened_in_excel": False}
    dump("SOURCE_WORKBOOK_FREEZE.json", freeze)
    dump("RAW_WORKBOOK_SNAPSHOT.json", {"sha256": digest(SOURCE), "scope":"authoritative + semantic crosscheck only; dependency facts in MASTER_DATA_SNAPSHOT.json", "sheets": {s:book.sheets[s] for s in (*TARGETS, "木门单公式")}})
    print(json.dumps({"freeze": {k: freeze[k] for k in ["sha256", "size_bytes", "alternate"]}, "sheets": [{k:s[k] for k in ["sheet", "dimension", "nonempty_cells", "formula_cells"]} for s in book.inventory]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
