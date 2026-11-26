"""Read-only, schema-driven audit of formal UOM references.

The audit discovers references from SQLite metadata instead of maintaining a
hand-written list.  It also scans non-FK unit/UOM columns and JSON payloads so
that a conversion relationship can be changed without silently rewriting
saved business quantities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def _quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _json_unit_values(value, path="$"):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if "uom" in str(key).casefold() or "unit" in str(key).casefold():
                yield child_path, child
            yield from _json_unit_values(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _json_unit_values(child, f"{path}[{index}]")


def _selected(value, tokens: set[str]) -> bool:
    if isinstance(value, (dict, list)):
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
        return serialized.casefold() in tokens
    return str(value).strip().casefold() in tokens


def _is_measurement_unit_column(name: str) -> bool:
    lowered = name.casefold()
    if "uom" in lowered:
        return True
    if lowered == "unit" or lowered.endswith("_unit"):
        return True
    return lowered.endswith("_unit_id") and not lowered.endswith("organization_unit_id")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--codes", nargs="+", default=["mm", "m"])
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    database = Path(args.database).resolve()
    before = database.stat()
    before_hash = hashlib.sha256(database.read_bytes()).hexdigest().upper()
    connection = sqlite3.connect(
        f"file:{database.as_posix()}?mode=ro&immutable=1", uri=True,
    )
    connection.row_factory = sqlite3.Row
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = [list(row) for row in connection.execute("PRAGMA foreign_key_check")]
        tables = [
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        placeholders = ",".join("?" for _ in args.codes)
        uoms = [dict(row) for row in connection.execute(
            f"SELECT * FROM unit_of_measure WHERE lower(code) IN ({placeholders}) "
            "ORDER BY company_id, id",
            [code.casefold() for code in args.codes],
        )]
        selected_ids = {int(row["id"]) for row in uoms}
        selected_tokens = {
            *(str(value).casefold() for value in selected_ids),
            *(str(row["code"]).strip().casefold() for row in uoms),
            *(str(row["name"]).strip().casefold() for row in uoms),
            *(str(row["symbol"]).strip().casefold() for row in uoms),
        }
        selected_tokens.discard("")

        direct_references = []
        non_fk_unit_columns = []
        json_references = []
        reference_facts = []
        for table in tables:
            columns = [dict(row) for row in connection.execute(
                f"PRAGMA table_info({_quoted(table)})"
            )]
            foreign_key_rows = [dict(row) for row in connection.execute(
                f"PRAGMA foreign_key_list({_quoted(table)})"
            )]
            uom_fk_columns = {
                row["from"] for row in foreign_key_rows
                if row["table"] == "unit_of_measure"
            }
            for column in sorted(uom_fk_columns):
                values = [dict(row) for row in connection.execute(
                    f"SELECT rowid AS row_id, {_quoted(column)} AS value "
                    f"FROM {_quoted(table)} WHERE {_quoted(column)} IS NOT NULL "
                    f"ORDER BY rowid"
                )]
                selected_rows = [
                    row for row in values
                    if str(row["value"]).strip() in {str(item) for item in selected_ids}
                ]
                direct_references.append({
                    "table": table,
                    "column": column,
                    "nonNullCount": len(values),
                    "selectedRows": selected_rows,
                })
                reference_facts.extend(
                    {"kind": "FK", "table": table, "column": column, **row}
                    for row in selected_rows
                )

            for column_info in columns:
                column = column_info["name"]
                lowered = column.casefold()
                if column in uom_fk_columns or not _is_measurement_unit_column(lowered):
                    continue
                values = [dict(row) for row in connection.execute(
                    f"SELECT rowid AS row_id, {_quoted(column)} AS value "
                    f"FROM {_quoted(table)} WHERE {_quoted(column)} IS NOT NULL "
                    f"ORDER BY rowid"
                )]
                selected_rows = [row for row in values if _selected(row["value"], selected_tokens)]
                non_fk_unit_columns.append({
                    "table": table,
                    "column": column,
                    "nonNullCount": len(values),
                    "selectedRows": selected_rows,
                })
                reference_facts.extend(
                    {"kind": "UNIT_COLUMN", "table": table, "column": column, **row}
                    for row in selected_rows
                )

            text_columns = [
                item["name"] for item in columns
                if "TEXT" in str(item["type"] or "").upper()
                or "JSON" in str(item["type"] or "").upper()
            ]
            for column in text_columns:
                for row in connection.execute(
                    f"SELECT rowid AS row_id, {_quoted(column)} AS value "
                    f"FROM {_quoted(table)} WHERE {_quoted(column)} IS NOT NULL "
                    f"AND (trim({_quoted(column)}) LIKE '{{%' "
                    f"OR trim({_quoted(column)}) LIKE '[%') ORDER BY rowid"
                ):
                    try:
                        payload = json.loads(row["value"])
                    except (TypeError, ValueError, json.JSONDecodeError):
                        continue
                    for json_path, value in _json_unit_values(payload):
                        if not _selected(value, selected_tokens):
                            continue
                        fact = {
                            "kind": "JSON", "table": table, "column": column,
                            "row_id": row["row_id"], "jsonPath": json_path,
                            "value": value,
                        }
                        json_references.append(fact)
                        reference_facts.append(fact)

        preserved_reference_facts = [
            fact for fact in reference_facts
            if fact["table"] not in {
                "system_organization_operating_audits",
                "masterdata_external_identity",
                "masterdata_write_request",
                # The conversion definition itself is the authorized write.
                # Preserve/hash only downstream business facts that reference it.
                "unit_of_measure",
            }
        ]
        serialized_facts = json.dumps(
            preserved_reference_facts,
            ensure_ascii=False, sort_keys=True, default=str,
            separators=(",", ":"),
        ).encode("utf-8")
        if args.summary_only:
            direct_output = [{
                "table": entry["table"],
                "column": entry["column"],
                "nonNullCount": entry["nonNullCount"],
                "selectedRowCount": len(entry["selectedRows"]),
                "selectedValueCounts": {
                    str(value): sum(
                        1 for row in entry["selectedRows"]
                        if str(row["value"]) == str(value)
                    )
                    for value in sorted(selected_ids)
                },
                "selectedRowSample": entry["selectedRows"][:10],
            } for entry in direct_references]
            non_fk_output = [{
                "table": entry["table"],
                "column": entry["column"],
                "nonNullCount": entry["nonNullCount"],
                "selectedRowCount": len(entry["selectedRows"]),
                "selectedRowSample": entry["selectedRows"][:10],
            } for entry in non_fk_unit_columns if entry["selectedRows"]]
            json_groups = {}
            for fact in json_references:
                key = (fact["table"], fact["column"])
                json_groups[key] = json_groups.get(key, 0) + 1
            json_output = [
                {"table": key[0], "column": key[1], "selectedValueCount": count}
                for key, count in sorted(json_groups.items())
            ]
        else:
            direct_output = direct_references
            non_fk_output = non_fk_unit_columns
            json_output = json_references
        after = database.stat()
        after_hash = hashlib.sha256(database.read_bytes()).hexdigest().upper()
        print(json.dumps({
            "database": str(database),
            "readOnly": True,
            "size": before.st_size,
            "sha256Before": before_hash,
            "sha256After": after_hash,
            "unchangedDuringAudit": (
                before.st_size == after.st_size
                and before.st_mtime_ns == after.st_mtime_ns
                and before_hash == after_hash
            ),
            "integrityCheck": integrity,
            "foreignKeyCheck": foreign_keys,
            "selectedUoms": uoms,
            "schemaTableCount": len(tables),
            "directReferenceFieldCount": len(direct_references),
            "nonFkUnitColumnScannedCount": len(non_fk_unit_columns),
            "jsonSelectedValueCount": len(json_references),
            "directReferences": direct_output,
            "nonFkUnitColumnsWithSelectedValues": non_fk_output,
            "jsonReferences": json_output,
            "selectedReferenceFactCount": len(reference_facts),
            "preservedReferenceFactCount": len(preserved_reference_facts),
            "preservedReferenceFactsSha256": hashlib.sha256(serialized_facts).hexdigest().upper(),
        }, ensure_ascii=False, indent=2, default=str))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
