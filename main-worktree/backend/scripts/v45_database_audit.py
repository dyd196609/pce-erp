import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


TABLES = (
    "purchase_reconciliations",
    "purchase_invoice_prepares",
    "purchase_accounts_payable_drafts",
    "business_action_idempotency",
    "business_action_transactions",
    "business_action_audit_records",
    "business_document_number_reservations",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("database")
    parser.add_argument("--tenant", default="tenant-v45")
    args = parser.parse_args()
    path = Path(args.database).resolve()
    digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""
    connection = sqlite3.connect(path)
    names = {
        row[0]
        for row in connection.execute(
            "select name from sqlite_master where type = 'table'"
        )
    }
    counts = {}
    for table in TABLES:
        if table not in names:
            counts[table] = 0
            continue
        columns = {
            row[1] for row in connection.execute(f'pragma table_info("{table}")')
        }
        if "tenant_id" not in columns:
            counts[table] = 0
            continue
        counts[table] = connection.execute(
            f'select count(*) from "{table}" where tenant_id = ?',
            (args.tenant,),
        ).fetchone()[0]
    print(json.dumps({
        "databasePath": str(path),
        "sha256": digest,
        "length": path.stat().st_size if path.exists() else 0,
        "tenantId": args.tenant,
        "counts": counts,
        "totalTenantRecords": sum(counts.values()),
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
