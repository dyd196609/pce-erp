import hashlib
import json
import sqlite3
import sys
from pathlib import Path


def scalar(connection, sql):
    return connection.execute(sql).fetchone()[0]


def table_exists(connection, table):
    return bool(connection.execute(
        "select 1 from sqlite_master where type='table' and name=?", (table,)
    ).fetchone())


def status_counts(connection, table, column):
    if not table_exists(connection, table):
        return []
    return [
        {"status": row[0], "count": row[1]}
        for row in connection.execute(
            f'select "{column}", count(*) from "{table}" group by "{column}" order by "{column}"'
        ).fetchall()
    ]


def aggregate(connection, table, fields):
    if not table_exists(connection, table):
        return {"table": table, "exists": False, "rowCount": 0, "fields": {}}
    values = {field: scalar(connection, f'select coalesce(sum("{field}"), 0) from "{table}"') for field in fields}
    return {
        "table": table,
        "exists": True,
        "rowCount": scalar(connection, f'select count(*) from "{table}"'),
        "fields": values,
    }


def main():
    database = Path(sys.argv[1]).resolve()
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    tables = [row[0] for row in connection.execute(
        "select name from sqlite_master where type='table' order by name"
    ).fetchall()]
    watched = [
        "purchase_order", "purchase_order_item", "purchase_orders", "purchase_order_items",
        "supplier_reconciliations", "supplier_reconciliation_differences",
        "supplier_reconciliation_confirmations", "supplier_payable_confirmations",
        "supplier_payment_requests", "supplier_payment_status_records",
        "supplier_settlement_completions", "supplier_performance_metrics",
        "buyer_performance_metrics",
    ]
    report = {
        "databasePath": str(database),
        "databaseSha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        "tableCount": len(tables),
        "tableCounts": {
            table: scalar(connection, f'select count(*) from "{table}"') if table_exists(connection, table) else None
            for table in watched
        },
        "statusCounts": {
            "purchase_order": status_counts(connection, "purchase_order", "status"),
            "purchase_orders.document_status": status_counts(connection, "purchase_orders", "document_status"),
            "purchase_orders.progress_status": status_counts(connection, "purchase_orders", "progress_status"),
            "supplier_reconciliations": status_counts(connection, "supplier_reconciliations", "status"),
            "supplier_payable_confirmations": status_counts(connection, "supplier_payable_confirmations", "status"),
            "supplier_payment_requests": status_counts(connection, "supplier_payment_requests", "status"),
            "supplier_payment_status_records": status_counts(connection, "supplier_payment_status_records", "status"),
        },
        "quantityFacts": [
            aggregate(connection, "purchase_order_item", ["quantity", "actual_quantity"]),
            aggregate(connection, "purchase_order_items", [
                "plan_quantity", "actual_quantity", "arrival_quantity", "qualified_quantity",
                "rejected_quantity", "inbound_quantity", "settled_quantity",
            ]),
            aggregate(connection, "supplier_reconciliations", ["purchase_amount", "received_amount", "qualified_amount", "reconciliation_amount"]),
        ],
        "amountFacts": [
            aggregate(connection, "purchase_order", ["total_amount"]),
            aggregate(connection, "purchase_order_item", ["amount", "actual_amount"]),
            aggregate(connection, "purchase_orders", ["total_plan_amount", "total_actual_amount"]),
            aggregate(connection, "purchase_order_items", ["plan_amount", "actual_amount", "settled_amount"]),
            aggregate(connection, "supplier_reconciliations", ["purchase_amount", "received_amount", "qualified_amount", "reconciliation_amount"]),
            aggregate(connection, "supplier_payable_confirmations", ["confirmed_amount", "qualified_amount", "deduction_amount", "final_payable_amount"]),
            aggregate(connection, "supplier_payment_requests", ["request_amount"]),
            aggregate(connection, "supplier_payment_status_records", ["payment_amount"]),
        ],
    }
    connection.close()
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
