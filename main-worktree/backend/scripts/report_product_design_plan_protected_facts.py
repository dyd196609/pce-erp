"""Read-only fingerprints for the protected product-design-plan acceptance facts."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path


ORDER_NO = os.environ.get("PCE_PRODUCT_DESIGN_ORDER_NO", "SO202609180003")
database = Path(os.environ.get("PCE_DATABASE_PATH", "")).resolve()
if not database.is_file():
    raise RuntimeError("PCE_DATABASE_PATH must identify an existing SQLite database")

connection = sqlite3.connect(database)
connection.row_factory = sqlite3.Row


def rows(sql: str, parameters: tuple[object, ...] = ()) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute(sql, parameters).fetchall()]


def fingerprint(table: str, where: str = "", parameters: tuple[object, ...] = ()) -> dict[str, object]:
    clause = f" WHERE {where}" if where else ""
    data = rows(f'SELECT * FROM "{table}"{clause} ORDER BY id', parameters)
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return {"count": len(data), "sha256": hashlib.sha256(encoded).hexdigest()}


order = connection.execute("SELECT id FROM sales_order WHERE order_no = ?", (ORDER_NO,)).fetchone()
if order is None:
    raise RuntimeError(f"Sales order not found: {ORDER_NO}")
order_id = int(order["id"])
line_ids = [
    int(row["id"])
    for row in connection.execute(
        "SELECT id FROM sales_order_item WHERE sales_order_id = ? ORDER BY line_no, id", (order_id,)
    )
]
placeholders = ",".join("?" for _ in line_ids)
item_rows = rows(
    f"SELECT id, sales_order_item_id FROM pde_product_design_item "
    f"WHERE sales_order_item_id IN ({placeholders}) ORDER BY id",
    tuple(line_ids),
)
item_ids = [int(row["id"]) for row in item_rows]
item_placeholders = ",".join("?" for _ in item_ids)
source_ids = [
    int(row["source_record_id"])
    for row in connection.execute(
        f"SELECT DISTINCT source_record_id FROM pde_product_design_item "
        f"WHERE id IN ({item_placeholders}) ORDER BY source_record_id",
        tuple(item_ids),
    )
]
source_placeholders = ",".join("?" for _ in source_ids)

group_counts = {
    f"DES-{int(row['line_no']):02d}": int(row["item_count"])
    for row in connection.execute(
        "SELECT soi.line_no, COUNT(pdi.id) AS item_count "
        "FROM sales_order_item soi "
        "LEFT JOIN pde_product_design_item pdi ON pdi.sales_order_item_id = soi.id "
        "WHERE soi.sales_order_id = ? GROUP BY soi.line_no ORDER BY soi.line_no",
        (order_id,),
    )
}

table_names = {
    row["name"]
    for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
}
protected = {
    "salesOrder": fingerprint("sales_order", "id = ?", (order_id,)),
    "salesOrderItems": fingerprint("sales_order_item", f"id IN ({placeholders})", tuple(line_ids)),
    "productDesignItems": fingerprint(
        "pde_product_design_item", f"id IN ({item_placeholders})", tuple(item_ids)
    ),
    "productDesignRevisions": fingerprint(
        "pde_product_design_revision", f"design_item_id IN ({item_placeholders})", tuple(item_ids)
    ),
    "engineeringSourceRecords": fingerprint(
        "pde_engineering_source_record", f"id IN ({source_placeholders})", tuple(source_ids)
    ),
}
for table in sorted(table_names):
    lowered = table.lower()
    if any(token in lowered for token in ("approval", "bom", "production_plan", "engineering_calculation")):
        protected[f"wholeTable:{table}"] = fingerprint(table)

plan_columns = [
    row["name"] for row in connection.execute("PRAGMA table_info('pde_product_design_plan_revision')")
]
if "order_id" in plan_columns:
    plan_revisions = fingerprint("pde_product_design_plan_revision", "order_id = ?", (order_id,))
    latest_group_plans = rows(
        "SELECT p.id, p.order_id, p.design_group, p.designer_employee_id, "
        "p.planned_start_date, p.planned_finish_date, p.plan_type, "
        "p.adjustment_reason, p.revision, p.design_item_id "
        "FROM pde_product_design_plan_revision p "
        "INNER JOIN ("
        "SELECT design_group, MAX(revision) AS revision "
        "FROM pde_product_design_plan_revision "
        "WHERE order_id = ? GROUP BY design_group"
        ") latest ON latest.design_group = p.design_group AND latest.revision = p.revision "
        "WHERE p.order_id = ? ORDER BY p.design_group",
        (order_id, order_id),
    )
else:
    plan_revisions = fingerprint(
        "pde_product_design_plan_revision",
        f"design_item_id IN ({item_placeholders})",
        tuple(item_ids),
    )
    latest_group_plans = []

payload = {
    "database": str(database),
    "databaseSha256": hashlib.sha256(database.read_bytes()).hexdigest(),
    "orderNo": ORDER_NO,
    "orderId": order_id,
    "designItemCount": len(item_ids),
    "designGroupCounts": group_counts,
    "planColumns": plan_columns,
    "planRevisions": plan_revisions,
    "latestGroupPlans": latest_group_plans,
    "protectedFingerprints": protected,
}
print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
