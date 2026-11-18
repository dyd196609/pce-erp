"""Read-only evidence for the product-design batch/field-integrity acceptance scope."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path


EXPECTED_DATABASE = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
).resolve()
EXPECTED_IDENTITY = "PDE-OPERABLE-ACCEPTANCE-20260912"
ORDER_NO = "SO202609180003"
TARGET_ITEM_NO = "SO202609180003-DES-01-SRC-0003"

database = Path(os.environ.get("PCE_DATABASE_PATH", "")).resolve()
if database != EXPECTED_DATABASE or not database.is_file():
    raise RuntimeError("READ_ONLY_ACCEPTANCE_DATABASE_MISMATCH")
if os.environ.get("PCE_DATABASE_IDENTITY") != EXPECTED_IDENTITY:
    raise RuntimeError("READ_ONLY_ACCEPTANCE_IDENTITY_MISMATCH")

connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
connection.row_factory = sqlite3.Row


def one(sql, parameters=()):
    row = connection.execute(sql, parameters).fetchone()
    return dict(row) if row else None


def many(sql, parameters=()):
    return [dict(row) for row in connection.execute(sql, parameters).fetchall()]


try:
    company = one("SELECT id, code, name FROM system_company WHERE code = 'COMP001'")
    order = one(
        "SELECT id, order_no, company_id, version FROM sales_order WHERE order_no = ?",
        (ORDER_NO,),
    )
    lines = many(
        "SELECT id, line_no FROM sales_order_item WHERE sales_order_id = ? ORDER BY line_no",
        (order["id"],),
    )
    items = many(
        "SELECT p.id, p.item_no, p.version, p.product_definition_id, p.physical_uom_snapshot, "
        "p.existing_design_data, s.line_no "
        "FROM pde_product_design_item p "
        "JOIN sales_order_item s ON s.id = p.sales_order_item_id "
        "WHERE s.sales_order_id = ? ORDER BY s.line_no, p.id",
        (order["id"],),
    )
    target = next(item for item in items if item["item_no"] == TARGET_ITEM_NO)
    revision = one(
        "SELECT id, revision, design_width, design_uom_id, design_data, change_reason, created_at "
        "FROM pde_product_design_revision WHERE design_item_id = ? "
        "ORDER BY revision DESC, id DESC LIMIT 1",
        (target["id"],),
    )
    design_data = json.loads(revision["design_data"] or "{}") if revision else {}
    uom = one(
        "SELECT id, code, name, dimension FROM unit_of_measure WHERE id = ?",
        (revision["design_uom_id"],),
    ) if revision and revision["design_uom_id"] else None
    plan_rows = many(
        "SELECT p.design_group, p.revision, p.planned_start_date, p.planned_finish_date, "
        "p.designer_employee_id FROM pde_product_design_plan_revision p "
        "JOIN (SELECT design_group, MAX(revision) revision FROM pde_product_design_plan_revision "
        "WHERE order_id = ? GROUP BY design_group) latest "
        "ON latest.design_group = p.design_group AND latest.revision = p.revision "
        "WHERE p.order_id = ? ORDER BY p.design_group",
        (order["id"], order["id"]),
    )
    material = one(
        "SELECT id, code, name, specification FROM material WHERE code = ?",
        ("MAT202608000048",),
    )
    group_counts = {
        f"DES-{line['line_no']:02d}": sum(1 for item in items if item["line_no"] == line["line_no"])
        for line in lines
    }
    payload = {
        "runtime": {
            "profile": os.environ.get("PCE_RUNTIME_PROFILE"),
            "databaseIdentity": os.environ.get("PCE_DATABASE_IDENTITY"),
            "database": str(database),
            "databaseSha256AtRead": hashlib.sha256(database.read_bytes()).hexdigest(),
        },
        "company": company,
        "order": order,
        "orderLineCount": len(lines),
        "designItemCount": len(items),
        "designGroupCounts": group_counts,
        "target": {
            "itemNo": target["item_no"],
            "itemVersion": target["version"],
            "formalProductDefinitionId": target["product_definition_id"],
            "physicalUnit": target["physical_uom_snapshot"],
            "latestRevision": revision,
            "latestDesignNotes": design_data.get("designNotes"),
            "designUnit": uom,
        },
        "latestGroupPlans": plan_rows,
        "materialSample": material,
        "readOnly": True,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
finally:
    connection.close()
