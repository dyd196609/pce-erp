"""Export bounded, read-only product-design calculation acceptance evidence."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[1]
DATABASE = Path("D:/Dev-PCE/Acceptance/PDE-Operable-20260912/pde-operable-acceptance.sqlite3")
OUTPUT = ROOT / "reports/product-design-engineering-calculation-20260919"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest().upper()


def effective_value(existing, revision, column, key):
    value = revision[column] if revision and column and revision[column] is not None else None
    if value is not None:
        return value
    design_data = json.loads(revision["design_data"] or "{}") if revision else {}
    return design_data.get(key, existing.get(key))


def main():
    before_hash = sha256(DATABASE)
    connection = sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    items = list(connection.execute("""
        SELECT p.*, o.order_no, i.line_no, a.raw_sheet,
               json_extract(a.raw_value, '$.sourceRow') AS source_row,
               c.completion_nature, c.actual_completion_date,
               r.revision AS design_revision, r.design_length, r.design_width,
               r.design_thickness, r.design_data
          FROM pde_product_design_item p
          JOIN sales_order_item i ON i.id = p.sales_order_item_id
          JOIN sales_order o ON o.id = i.sales_order_id
          JOIN sales_order_item_engineering_attribute a ON a.id = p.source_attribute_id
          LEFT JOIN pde_product_design_completion_record c ON c.id = (
               SELECT cc.id FROM pde_product_design_completion_record cc
                WHERE cc.design_item_id = p.id ORDER BY cc.sequence DESC LIMIT 1)
          LEFT JOIN pde_product_design_revision r ON r.id = (
               SELECT rr.id FROM pde_product_design_revision rr
                WHERE rr.design_item_id = p.id ORDER BY rr.revision DESC LIMIT 1)
         WHERE o.order_no = 'SO202609180003'
         ORDER BY i.line_no, p.source_attribute_id, p.id
    """))
    output_rows = []
    for sequence, item in enumerate(items, start=1):
        existing = json.loads(item["existing_design_data"] or "{}")
        length = effective_value(existing, item, "design_length", "designLength")
        width = effective_value(existing, item, "design_width", "designWidth")
        thickness = effective_value(existing, item, "design_thickness", "designThickness")
        visible = effective_value(existing, item, None, "visibleCondition")
        edge = effective_value(existing, item, None, "edgeMethod")
        required = {
            "source": item["raw_sheet"] and item["source_row"] is not None,
            "length": length not in (None, ""),
            "width": width not in (None, ""),
            "thickness": thickness not in (None, ""),
            "quantity": item["physical_quantity"] not in (None, ""),
        }
        if item["raw_sheet"] == "三合一生产单":
            required.update(visible=visible not in (None, ""), edge=edge not in (None, ""))
        missing = [key for key, ready in required.items() if not ready]
        gaps = [key for key in ("hardware", "glass") if existing.get(key) in (None, "")]
        output_rows.append({
            "sequence": sequence,
            "designItemId": item["id"],
            "designItemNo": item["item_no"],
            "group": f"DES-{item['line_no']:02d}",
            "sourceSheet": item["raw_sheet"],
            "sourceRow": item["source_row"],
            "designRevision": item["design_revision"] or "",
            "lengthMm": length,
            "widthMm": width,
            "thicknessMm": thickness,
            "physicalQuantity": item["physical_quantity"],
            "visibleCondition": visible or "",
            "edgeMethod": edge or "",
            "calculationReady": "YES" if not missing else "NO",
            "missingCalculationFields": ";".join(missing),
            "designGaps": ";".join(gaps),
            "completionNature": item["completion_nature"] or "",
            "actualCompletionDate": item["actual_completion_date"] or "",
        })
    connection.close()
    after_hash = sha256(DATABASE)
    if before_hash != after_hash:
        raise RuntimeError("Acceptance database hash changed during read-only export")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT / "PRODUCT_DESIGN_71_READINESS.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    groups = {}
    for row in output_rows:
        groups[row["group"]] = groups.get(row["group"], 0) + 1
    summary = {
        "database": str(DATABASE),
        "connectionMode": "SQLite URI mode=ro + PRAGMA query_only=ON",
        "databaseSha256Before": before_hash,
        "databaseSha256After": after_hash,
        "orderNo": "SO202609180003",
        "total": len(output_rows),
        "groups": groups,
        "calculationReady": sum(row["calculationReady"] == "YES" for row in output_rows),
        "calculationBlocked": sum(row["calculationReady"] == "NO" for row in output_rows),
        "hardwareGapCount": sum("hardware" in row["designGaps"] for row in output_rows),
        "glassGapCount": sum("glass" in row["designGaps"] for row in output_rows),
        "designRevisionCount": sum(bool(row["designRevision"]) for row in output_rows),
        "completionFactCount": sum(bool(row["completionNature"]) for row in output_rows),
        "datedCompletionCount": sum(bool(row["actualCompletionDate"]) for row in output_rows),
        "csvSha256": sha256(csv_path),
    }
    (OUTPUT / "PRODUCT_DESIGN_71_READINESS_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
