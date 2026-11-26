"""Read-only row-hash/count differences, with no disclosure of authentication data."""
import json
import sqlite3
from pathlib import Path
from semi_finished_model_closure_runtime import ROOT, ISO, OUT

with sqlite3.connect((ROOT / "backend/db.sqlite3").as_uri() + "?mode=ro", uri=True) as a, sqlite3.connect((ISO / "rollback-r2.sqlite3").as_uri() + "?mode=ro", uri=True) as b:
    a.execute("PRAGMA query_only=ON")
    b.execute("PRAGMA query_only=ON")
    tables = [r[0] for r in a.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    differences = []
    for table in tables:
        if table in {"sqlite_sequence", "django_migrations"}:
            continue
        before, after = a.execute(f'SELECT * FROM "{table}"').fetchall(), b.execute(f'SELECT * FROM "{table}"').fetchall()
        if sorted(before, key=repr) != sorted(after, key=repr):
            differences.append({"table": table, "beforeCount": len(before), "afterCount": len(after),
                "addedPrimaryKeys": sorted({r[0] for r in after} - {r[0] for r in before}),
                "removedPrimaryKeys": sorted({r[0] for r in before} - {r[0] for r in after})})
    (OUT / "ROLLBACK_TECHNICAL_DIAGNOSTIC.json").write_text(json.dumps(differences, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(differences))
