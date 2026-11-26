"""Read-only formal evidence for the 2026-10-09 WorkCenter auto-code repair."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


DATABASE = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def scalar(connection: sqlite3.Connection, sql: str, parameters=()) -> int:
    return int(connection.execute(sql, parameters).fetchone()[0])


def main() -> None:
    connection = sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    company_id = scalar(
        connection, "SELECT id FROM system_company WHERE code = ?", ("COMP001",),
    )
    rule = connection.execute(
        """
        SELECT entity_type, prefix, date_format, seq_length, current_seq
        FROM code_rule
        WHERE company_id = ? AND entity_type = 'production_work_center'
        """,
        (company_id,),
    ).fetchone()
    facts = {
        "database": str(DATABASE),
        "sha256": sha256(DATABASE),
        "queryOnly": True,
        "integrity": connection.execute("PRAGMA integrity_check").fetchone()[0],
        "companyCode": "COMP001",
        "companyId": company_id,
        "workCenterCodeRule": None if rule is None else {
            "entityType": rule[0],
            "prefix": rule[1],
            "dateFormat": rule[2],
            "sequenceLength": rule[3],
            "currentSequence": rule[4],
            "renderingContract": f"{rule[1]}{rule[2]}+{rule[3]}-digit-sequence",
        },
        "counts": {
            "workshops": scalar(
                connection, "SELECT COUNT(*) FROM system_workshop WHERE company_id = ?",
                (company_id,),
            ),
            "workCenters": scalar(
                connection, "SELECT COUNT(*) FROM pde_work_center WHERE company_id = ?",
                (company_id,),
            ),
            "operations": scalar(
                connection, "SELECT COUNT(*) FROM system_process WHERE company_id = ?",
                (company_id,),
            ),
            "capabilities": scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM pde_work_center_operation_capability capability
                JOIN pde_work_center work_center
                  ON work_center.id = capability.work_center_id
                WHERE work_center.company_id = ?
                """,
                (company_id,),
            ),
            "workCenterWriteRequests": scalar(
                connection,
                """
                SELECT COUNT(*) FROM masterdata_write_request
                WHERE organization_id = ? AND entity_type = 'work-centers'
                """,
                (company_id,),
            ),
            "workCenterAudits": scalar(
                connection,
                """
                SELECT COUNT(*) FROM system_organization_operating_audits
                WHERE organization_id = ? AND target_type = 'WorkCenter'
                """,
                (company_id,),
            ),
        },
        "workCenterRows": [
            {"id": row_id, "code": code, "name": name}
            for row_id, code, name in connection.execute(
                """
                SELECT id, code, name FROM pde_work_center
                WHERE company_id = ? ORDER BY id
                """,
                (company_id,),
            ).fetchall()
        ],
    }
    connection.close()
    print(json.dumps(facts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
