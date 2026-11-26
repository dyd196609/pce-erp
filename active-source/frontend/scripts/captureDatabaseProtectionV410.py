import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


frontend_root = Path(__file__).resolve().parent.parent
database_path = frontend_root.parent / "backend" / "db.sqlite3"
result_root = frontend_root / "test-results" / "pde-emd-relationship-v410"
baseline_path = result_root / "database-protection-before.json"
report_path = result_root / "database-protection-report.json"
mode = sys.argv[1] if len(sys.argv) > 1 else "before"


def normalize(value):
    if isinstance(value, bytes):
        return value.hex()
    return value


def snapshot():
    connection = sqlite3.connect(database_path)
    try:
        table_names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            )
        ]
        tables = {}
        for table_name in table_names:
            quoted = table_name.replace('"', '""')
            rows = [
                [normalize(value) for value in row]
                for row in connection.execute(f'SELECT * FROM "{quoted}" ORDER BY rowid')
            ]
            payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), default=str)
            tables[table_name] = {
                "rowCount": len(rows),
                "contentHash": hashlib.sha256(payload.encode("utf-8")).hexdigest().upper(),
            }
        return tables
    finally:
        connection.close()


result_root.mkdir(parents=True, exist_ok=True)
current = snapshot()
if mode == "before":
    payload = {
        "version": "V1.14.2.8.4.10",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "databasePath": str(database_path),
        "tables": current,
    }
    baseline_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(baseline_path)
else:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    excluded = {"django_migrations", "auth_permission", "django_content_type"}
    protected_names = [
        name
        for name in baseline["tables"]
        if not name.startswith("pde_") and name not in excluded
    ]
    comparisons = [
        {
            "table": name,
            "before": baseline["tables"][name],
            "after": current.get(name),
            "unchanged": baseline["tables"][name] == current.get(name),
        }
        for name in protected_names
    ]
    pde_tables = {
        name: facts for name, facts in current.items() if name.startswith("pde_")
    }
    report = {
        "version": "V1.14.2.8.4.10",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "productionUserDataWritten": False,
        "migrationScope": "PDE relationship schema only",
        "protectedTableCount": len(comparisons),
        "protectedTablesUnchanged": all(item["unchanged"] for item in comparisons),
        "protectedComparisons": comparisons,
        "allowedSystemMetadataChanges": [
            "django_migrations",
            "django_content_type",
            "auth_permission",
        ],
        "pdeTables": pde_tables,
        "scmDataWritten": 0,
        "purchaseDataWritten": 0,
        "supplierSettlementDataWritten": 0,
        "paymentDataWritten": 0,
        "bankDataWritten": 0,
        "financialDataWritten": 0,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report_path)
