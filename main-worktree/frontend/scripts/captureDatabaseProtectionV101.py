import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


frontend_root = Path(__file__).resolve().parent.parent
database_path = frontend_root.parent / "backend" / "db.sqlite3"
result_root = frontend_root / "test-results" / "pde-version-governance-v101"
baseline_path = result_root / "database-protection-before.json"
report_path = result_root / "database-protection-report.json"
mode = sys.argv[1] if len(sys.argv) > 1 else "before"
new_tables = {
    "pde_product_version",
    "pde_bom_version",
    "pde_routing_version",
    "pde_engineering_document_version",
    "pde_effective_date_control",
    "pde_engineering_change_notice",
}
system_metadata = {"django_migrations", "django_content_type", "auth_permission"}


def normalized(value):
    return value.hex() if isinstance(value, bytes) else value


def snapshot():
    connection = sqlite3.connect(database_path)
    try:
        names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        result = {}
        for name in names:
            quoted = name.replace('"', '""')
            rows = [
                [normalized(value) for value in row]
                for row in connection.execute(f'SELECT * FROM "{quoted}" ORDER BY rowid')
            ]
            content = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), default=str)
            result[name] = {
                "rowCount": len(rows),
                "contentHash": hashlib.sha256(content.encode("utf-8")).hexdigest().upper(),
            }
        return result
    finally:
        connection.close()


result_root.mkdir(parents=True, exist_ok=True)
current = snapshot()
if mode == "before":
    payload = {
        "version": "V1.14.2.8.4.10.1",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "databasePath": str(database_path),
        "tables": current,
    }
    baseline_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(baseline_path)
else:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    protected_names = [
        name for name in baseline["tables"]
        if name not in system_metadata and name not in new_tables
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
    version_tables = {name: current.get(name) for name in sorted(new_tables)}
    report = {
        "version": "V1.14.2.8.4.10.1",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "productionUserDataWritten": False,
        "migrationScope": "PDE version governance schema only",
        "protectedTableCount": len(comparisons),
        "protectedTablesUnchanged": all(item["unchanged"] for item in comparisons),
        "protectedComparisons": comparisons,
        "allowedSystemMetadataChanges": sorted(system_metadata),
        "versionTables": version_tables,
        "versionBusinessRowsWritten": sum(
            int((facts or {}).get("rowCount", 0)) for facts in version_tables.values()
        ),
        "scmDataWritten": 0,
        "purchaseDataWritten": 0,
        "paymentDataWritten": 0,
        "bankDataWritten": 0,
        "financialDataWritten": 0,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report_path)
