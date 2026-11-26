"""Compare two SQLite databases by schema/data dump and per-table row counts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def snapshot(path: Path) -> tuple[dict, dict[str, int]]:
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro&immutable=1", uri=True,
    )
    try:
        tables = [
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts = {
            table: connection.execute(
                f"SELECT count(*) FROM {_quote(table)}"
            ).fetchone()[0]
            for table in tables
        }
        dump = "\n".join(connection.iterdump()).encode("utf-8")
        return ({
            "path": str(path.resolve()),
            "logicalDumpSha256": hashlib.sha256(dump).hexdigest().upper(),
            "tableCount": len(tables),
            "rowCountTotal": sum(counts.values()),
            "integrityCheck": connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0],
            "foreignKeyCheck": [
                list(row) for row in connection.execute("PRAGMA foreign_key_check")
            ],
        }, counts)
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    args = parser.parse_args()
    first, first_counts = snapshot(args.first)
    second, second_counts = snapshot(args.second)
    print(json.dumps({
        "databases": [first, second],
        "logicalDumpHashEqual": (
            first["logicalDumpSha256"] == second["logicalDumpSha256"]
        ),
        "tableCountsEqual": first_counts == second_counts,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
