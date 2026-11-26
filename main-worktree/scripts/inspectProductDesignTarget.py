import json
import sqlite3
import sys


path = sys.argv[1]
connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
connection.row_factory = sqlite3.Row

if len(sys.argv) > 2 and sys.argv[2] == "--tables":
    print("\n".join(row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    )))
    raise SystemExit(0)


def table(ends_with):
    matches = [
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ) if row[0].lower().endswith(ends_with.lower())
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Cannot resolve table suffix {ends_with}: {matches}")
    return matches[0]


sales_order = table("sales_order")
sales_order_item = table("sales_order_item")
engineering_attribute = table("sales_order_item_engineering_attribute")
user_table = table("user_system")
design_item = table("pde_product_design_item")
design_revision = table("pde_product_design_revision")
plan_revision = table("pde_product_design_plan_revision")
completion_record = table("pde_product_design_completion_record")
engineering_source = table("pde_engineering_source_record")


def scalar(sql, parameters=()):
    return connection.execute(sql, parameters).fetchone()[0]


facts = {
    "databasePath": path,
    "order": dict(connection.execute(
        f"SELECT id, order_no, version FROM {sales_order} WHERE order_no = ?",
        ("SO202609180003",),
    ).fetchone()),
    "activeUsers": [dict(row) for row in connection.execute(
        f"SELECT id, username, company_id FROM {user_table} WHERE is_active = 1 ORDER BY id"
    )],
}
order_id = facts["order"]["id"]
facts.update({
    "orderLineCount": scalar(f"SELECT COUNT(*) FROM {sales_order_item} WHERE sales_order_id = ?", (order_id,)),
    "engineeringAttributeCount": scalar(
        f"SELECT COUNT(*) FROM {engineering_attribute} a "
        f"JOIN {sales_order_item} i ON i.id = a.sales_order_item_id WHERE i.sales_order_id = ?",
        (order_id,),
    ),
    "designItemCount": scalar(
        f"SELECT COUNT(*) FROM {design_item} d "
        f"JOIN {sales_order_item} i ON i.id = d.sales_order_item_id WHERE i.sales_order_id = ?",
        (order_id,),
    ),
    "blankInstallationPositionCount": scalar(
        f"SELECT COUNT(*) FROM {design_item} d "
        f"JOIN {sales_order_item} i ON i.id = d.sales_order_item_id "
        "WHERE i.sales_order_id = ? AND TRIM(COALESCE(d.installation_position_snapshot, '')) = ''",
        (order_id,),
    ),
    "designRevisionCount": scalar(
        f"SELECT COUNT(*) FROM {design_revision} r JOIN {design_item} d ON d.id = r.design_item_id "
        f"JOIN {sales_order_item} i ON i.id = d.sales_order_item_id WHERE i.sales_order_id = ?",
        (order_id,),
    ),
    "planRevisionCount": scalar(
        f"SELECT COUNT(*) FROM {plan_revision} r JOIN {design_item} d ON d.id = r.design_item_id "
        f"JOIN {sales_order_item} i ON i.id = d.sales_order_item_id WHERE i.sales_order_id = ?",
        (order_id,),
    ),
    "completionCount": scalar(
        f"SELECT COUNT(*) FROM {completion_record} r JOIN {design_item} d ON d.id = r.design_item_id "
        f"JOIN {sales_order_item} i ON i.id = d.sales_order_item_id WHERE i.sales_order_id = ?",
        (order_id,),
    ),
})
source = connection.execute(
    f"SELECT s.id, s.source_version, s.content_hash, s.source_payload FROM {engineering_source} s "
    f"JOIN {design_item} d ON d.source_record_id = s.id "
    f"JOIN {sales_order_item} i ON i.id = d.sales_order_item_id "
    "WHERE i.sales_order_id = ? GROUP BY s.id ORDER BY COUNT(*) DESC LIMIT 1",
    (order_id,),
).fetchone()
facts["source"] = {
    "id": source["id"], "sourceVersion": source["source_version"],
    "contentHash": source["content_hash"],
    "registeredSourceScope": json.loads(source["source_payload"]).get("registeredSourceScope", {}),
}
print(json.dumps(facts, ensure_ascii=False, indent=2))
