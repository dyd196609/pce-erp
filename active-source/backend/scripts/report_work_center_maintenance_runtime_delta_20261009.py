"""Read-only inspection of login/runtime rows changed during browser acceptance."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


DATABASE = Path(r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3")
PATTERNS = ("user", "audit", "session", "login", "token")


def quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


with sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True) as connection:
    connection.row_factory = sqlite3.Row
    table_names = [
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
        if any(pattern in row["name"].lower() for pattern in PATTERNS)
    ]
    tables = {}
    for table_name in table_names:
        columns = [row["name"] for row in connection.execute(f"PRAGMA table_info({quoted(table_name)})")]
        time_columns = [
            column for column in columns
            if column.lower() in {"created_at", "updated_at", "last_login", "timestamp", "login_at"}
        ]
        recent_rows = []
        for time_column in time_columns:
            statement = (
                f"SELECT * FROM {quoted(table_name)} "
                f"WHERE {quoted(time_column)} >= ? ORDER BY {quoted(time_column)} DESC LIMIT 20"
            )
            for row in connection.execute(statement, ("2026-10-09 12:21:00",)):
                recent_rows.append({key: row[key] for key in row.keys() if key not in {"password", "token"}})
        tables[table_name] = {
            "columns": columns,
            "timeColumns": time_columns,
            "recentRows": recent_rows,
        }

print(json.dumps({"database": str(DATABASE), "tables": tables}, ensure_ascii=False, indent=2, default=str))
