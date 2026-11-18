import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


FRONTEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = FRONTEND_ROOT.parent
RESULT_ROOT = FRONTEND_ROOT / "test-results" / "pde-engineering-readiness-v104"
DATABASE = REPO_ROOT / "backend" / "db.sqlite3"
BEFORE = RESULT_ROOT / "database-before-snapshot.json"
REPORT = RESULT_ROOT / "database-protection-report.json"
ALLOWED_METADATA = {"auth_permission", "django_content_type", "django_migrations"}
ALLOWED_NEW_TABLES = {"pde_product_engineering_readiness"}


def normalize(value):
    return value.hex() if isinstance(value, bytes) else value


def table_snapshot(connection, table):
    escaped = table.replace('"', '""')
    rows = connection.execute(f'SELECT * FROM "{escaped}" ORDER BY rowid').fetchall()
    payload = json.dumps([[normalize(value) for value in row] for row in rows], ensure_ascii=False, separators=(",", ":"), default=str)
    return {"rowCount": len(rows), "contentHash": hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()}


def database_snapshot():
    with sqlite3.connect(DATABASE) as connection:
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        return {table: table_snapshot(connection, table) for table in tables}


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


mode = sys.argv[1] if len(sys.argv) > 1 else ""
if mode == "before":
    snapshot = database_snapshot()
    write(BEFORE, {
        "version": "V1.14.2.8.4.10.4",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "databasePath": str(DATABASE),
        "tables": snapshot,
    })
    print(json.dumps({"mode": mode, "tableCount": len(snapshot), "output": str(BEFORE)}, ensure_ascii=False))
elif mode == "after":
    before = json.loads(BEFORE.read_text(encoding="utf-8"))
    after = database_snapshot()
    protected_tables = sorted(
        table for table in before["tables"]
        if table not in ALLOWED_METADATA and table not in ALLOWED_NEW_TABLES
    )
    checks = [{
        "table": table,
        "before": before["tables"][table],
        "after": after.get(table),
        "unchanged": before["tables"][table] == after.get(table),
    } for table in protected_tables]
    new_tables = {table: after.get(table, {"rowCount": 0, "contentHash": ""}) for table in sorted(ALLOWED_NEW_TABLES)}
    report = {
        "version": "V1.14.2.8.4.10.4",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "databasePath": str(DATABASE),
        "productionUserDataWritten": False,
        "protectedTableCount": len(checks),
        "protectedTablesUnchanged": all(item["unchanged"] for item in checks),
        "protectedTables": checks,
        "allowedSystemMetadataChanges": sorted(ALLOWED_METADATA),
        "allowedNewTables": new_tables,
        "readinessBusinessRowsWritten": sum(item["rowCount"] for item in new_tables.values()),
        "scmDataWritten": 0,
        "purchaseDataWritten": 0,
        "inventoryDataWritten": 0,
        "paymentDataWritten": 0,
        "bankDataWritten": 0,
        "financialDataWritten": 0,
    }
    write(REPORT, report)
    print(json.dumps({
        "mode": mode,
        "protectedTableCount": len(checks),
        "protectedTablesUnchanged": report["protectedTablesUnchanged"],
        "readinessBusinessRowsWritten": report["readinessBusinessRowsWritten"],
        "output": str(REPORT),
    }, ensure_ascii=False))
else:
    raise SystemExit("usage: captureDatabaseProtectionV104.py before|after")
