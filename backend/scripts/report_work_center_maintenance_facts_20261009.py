"""Read-only evidence for the 2026-10-09 WorkCenter maintenance repair."""

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


def main() -> None:
    connection = sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    company_id = connection.execute(
        "SELECT id FROM system_company WHERE code = ?", ("COMP001",)
    ).fetchone()[0]
    facts = {
        "database": str(DATABASE),
        "sha256": sha256(DATABASE),
        "integrity": connection.execute("PRAGMA integrity_check").fetchone()[0],
        "companyCode": "COMP001",
        "companyId": company_id,
        "counts": {
            "workshops": connection.execute(
                "SELECT COUNT(*) FROM system_workshop WHERE company_id = ?",
                (company_id,),
            ).fetchone()[0],
            "workCenters": connection.execute(
                "SELECT COUNT(*) FROM pde_work_center WHERE company_id = ?",
                (company_id,),
            ).fetchone()[0],
            "operations": connection.execute(
                "SELECT COUNT(*) FROM system_process WHERE company_id = ?",
                (company_id,),
            ).fetchone()[0],
            "capabilities": connection.execute(
                """
                SELECT COUNT(*)
                FROM pde_work_center_operation_capability capability
                JOIN pde_work_center work_center
                  ON work_center.id = capability.work_center_id
                WHERE work_center.company_id = ?
                """,
                (company_id,),
            ).fetchone()[0],
        },
        "workshopRows": [
            {"code": code, "name": name, "formalModel": "system.Workshop"}
            for code, name in connection.execute(
                """
                SELECT code, name
                FROM system_workshop
                WHERE company_id = ? AND code LIKE 'WS%'
                ORDER BY code
                """,
                (company_id,),
            ).fetchall()
        ],
    }
    connection.close()
    print(json.dumps(facts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
