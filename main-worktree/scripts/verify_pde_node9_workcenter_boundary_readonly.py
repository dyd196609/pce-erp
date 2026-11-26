"""Read-only evidence gate for the PDE node-9 WorkCenter boundary decision.

The command opens the acceptance SQLite database in read-only/query-only mode,
reports the formal Workshop/Operation/Routing facts, and proves that the file
hash did not move during the inspection.  It never creates or updates business
objects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


TARGET_ROUTINGS = ("QSFB/FM", "BTKF/GT", "BTKF/SM")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def fetch_all(connection: sqlite3.Connection, sql: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(sql, parameters).fetchall()]


def scalar(connection: sqlite3.Connection, sql: str, parameters: tuple[Any, ...] = ()) -> Any:
    row = connection.execute(sql, parameters).fetchone()
    return row[0] if row else None


def column_contract(connection: sqlite3.Connection, table: str, column: str) -> dict[str, Any]:
    rows = fetch_all(connection, f'PRAGMA table_info("{table}")')
    match = next((row for row in rows if row["name"] == column), None)
    if match is None:
        return {"table": table, "column": column, "exists": False}
    return {
        "table": table,
        "column": column,
        "exists": True,
        "declaredType": match["type"],
        "notNull": bool(match["notnull"]),
    }


def build_evidence(database: Path, post_login_baseline_sha256: str) -> dict[str, Any]:
    start_sha = sha256(database)
    risks: list[str] = []
    baseline = post_login_baseline_sha256.strip().upper()
    if start_sha != baseline:
        risks.append("POST_LOGIN_BASELINE_SHA_MISMATCH_AT_START")

    uri = database.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        query_only = scalar(connection, "PRAGMA query_only")

        workshops = fetch_all(
            connection,
            """
            SELECT
                w.id,
                w.code,
                w.name,
                CASE WHEN w.is_active = 1 THEN 'ACTIVE' ELSE 'INACTIVE' END AS status,
                w.company_id,
                c.code AS company_code,
                c.name AS company_name,
                (SELECT COUNT(*) FROM system_process p WHERE p.workshop_id = w.id) AS operation_count,
                (SELECT COUNT(*) FROM pde_work_center wc WHERE wc.workshop_id = w.id) AS work_center_count
            FROM system_workshop w
            JOIN system_company c ON c.id = w.company_id
            ORDER BY w.id
            """,
        )

        operations = fetch_all(
            connection,
            """
            SELECT
                p.id,
                p.code,
                p.name,
                CASE WHEN p.is_active = 1 THEN 'ACTIVE' ELSE 'INACTIVE' END AS status,
                p.company_id,
                c.code AS company_code,
                c.name AS company_name,
                p.workshop_id,
                w.code AS workshop_code,
                w.name AS workshop_name,
                p.work_center_id,
                wc.code AS work_center_code,
                wc.name AS work_center_name
            FROM system_process p
            LEFT JOIN system_company c ON c.id = p.company_id
            LEFT JOIN system_workshop w ON w.id = p.workshop_id
            LEFT JOIN pde_work_center wc ON wc.id = p.work_center_id
            ORDER BY p.display_order, p.id
            """,
        )

        targets: dict[str, Any] = {}
        for routing_code in TARGET_ROUTINGS:
            versions = fetch_all(
                connection,
                """
                SELECT r.id AS routing_id, r.routing_code, r.name AS routing_name,
                       r.status AS routing_status, r.is_active AS routing_is_active,
                       rv.id AS version_id, rv.routing_version, rv.status AS version_status,
                       rv.revision
                FROM pde_routing r
                JOIN pde_routing_version rv ON rv.routing_id = r.id
                WHERE r.routing_code = ?
                ORDER BY rv.id
                """,
                (routing_code,),
            )
            steps = fetch_all(
                connection,
                """
                SELECT
                    rs.id AS step_id,
                    rs.routing_version_id AS version_id,
                    rs.sequence,
                    rs.is_active,
                    rs.operation_id,
                    p.code AS operation_code,
                    p.name AS operation_name,
                    COALESCE(rs.workshop_id, p.workshop_id) AS resolved_workshop_id,
                    COALESCE(rsw.code, opw.code) AS resolved_workshop_code,
                    COALESCE(rsw.name, opw.name) AS resolved_workshop_name,
                    CASE
                      WHEN rs.workshop_id IS NOT NULL THEN 'RoutingStep.workshop'
                      WHEN p.workshop_id IS NOT NULL THEN 'Operation.workshop'
                      ELSE 'NOT_MAINTAINED'
                    END AS workshop_source,
                    COALESCE(rs.work_center_id, p.work_center_id) AS resolved_work_center_id,
                    COALESCE(rswc.code, opwc.code) AS resolved_work_center_code,
                    COALESCE(rswc.name, opwc.name) AS resolved_work_center_name,
                    CASE
                      WHEN rs.work_center_id IS NOT NULL THEN 'RoutingStep.work_center'
                      WHEN p.work_center_id IS NOT NULL THEN 'Operation.work_center'
                      ELSE 'NOT_MAINTAINED'
                    END AS work_center_source,
                    rs.resource_selection_rule
                FROM pde_routing r
                JOIN pde_routing_version rv ON rv.routing_id = r.id
                JOIN pde_routing_step rs ON rs.routing_version_id = rv.id
                JOIN system_process p ON p.id = rs.operation_id
                LEFT JOIN system_workshop rsw ON rsw.id = rs.workshop_id
                LEFT JOIN system_workshop opw ON opw.id = p.workshop_id
                LEFT JOIN pde_work_center rswc ON rswc.id = rs.work_center_id
                LEFT JOIN pde_work_center opwc ON opwc.id = p.work_center_id
                WHERE r.routing_code = ?
                ORDER BY rv.id, rs.sequence, rs.id
                """,
                (routing_code,),
            )
            summary = {
                "stepCount": len(steps),
                "activeStepCount": sum(1 for row in steps if row["is_active"]),
                "workshopResolvedStepCount": sum(1 for row in steps if row["resolved_workshop_id"] is not None),
                "workCenterResolvedStepCount": sum(1 for row in steps if row["resolved_work_center_id"] is not None),
                "missingWorkCenterStepCount": sum(1 for row in steps if row["resolved_work_center_id"] is None),
                "allStepsMissingWorkCenter": bool(steps) and all(row["resolved_work_center_id"] is None for row in steps),
                "explicitNoWorkCenterRequirementFlagCount": 0,
                "explicitNoWorkCenterRequirementFlagNote": "RoutingStep has no field that declares a step inherently exempt from WorkCenter; NULL means NOT_MAINTAINED, not NOT_REQUIRED.",
                "distinctOperationCount": len({row["operation_id"] for row in steps}),
            }
            seen_operation_ids: set[int] = set()
            operation_facts = []
            for row in steps:
                if row["operation_id"] in seen_operation_ids:
                    continue
                seen_operation_ids.add(row["operation_id"])
                operation_facts.append({
                    "operationId": row["operation_id"],
                    "operationCode": row["operation_code"],
                    "operationName": row["operation_name"],
                    "workshopCode": row["resolved_workshop_code"],
                    "workshopName": row["resolved_workshop_name"],
                    "workCenterCode": row["resolved_work_center_code"],
                    "workCenterName": row["resolved_work_center_name"],
                    "workCenterStatus": "MAINTAINED" if row["resolved_work_center_id"] is not None else "NOT_MAINTAINED",
                })
            targets[routing_code] = {
                "versions": versions,
                "summary": summary,
                "operationFacts": operation_facts,
                "steps": steps,
            }

        counts = {
            "workshop": scalar(connection, "SELECT COUNT(*) FROM system_workshop"),
            "operation": scalar(connection, "SELECT COUNT(*) FROM system_process"),
            "workCenter": scalar(connection, "SELECT COUNT(*) FROM pde_work_center"),
            "routingDefinition": scalar(connection, "SELECT COUNT(*) FROM pde_routing"),
            "routingVersion": scalar(connection, "SELECT COUNT(*) FROM pde_routing_version"),
            "routingStep": scalar(connection, "SELECT COUNT(*) FROM pde_routing_step"),
            "engineeringOperationRequirement": scalar(connection, "SELECT COUNT(*) FROM pde_engineering_operation_requirement"),
        }

        model_contract = {
            "routingDefinitionHasWorkCenterColumn": any(
                row["name"] == "work_center_id" for row in fetch_all(connection, 'PRAGMA table_info("pde_routing")')
            ),
            "routingVersionHasWorkCenterColumn": any(
                row["name"] == "work_center_id" for row in fetch_all(connection, 'PRAGMA table_info("pde_routing_version")')
            ),
            "operationWorkCenter": column_contract(connection, "system_process", "work_center_id"),
            "routingStepWorkCenter": column_contract(connection, "pde_routing_step", "work_center_id"),
            "workCenterWorkshop": column_contract(connection, "pde_work_center", "workshop_id"),
            "equipmentWorkCenter": column_contract(connection, "pde_equipment", "work_center_id"),
            "standardCapacityWorkCenter": column_contract(connection, "pde_standard_capacity", "work_center_id"),
            "engineeringOperationRequirementHasWorkCenterColumn": any(
                row["name"] == "work_center_id"
                for row in fetch_all(connection, 'PRAGMA table_info("pde_engineering_operation_requirement")')
            ),
        }
    finally:
        connection.close()

    final_sha = sha256(database)
    if final_sha != baseline or final_sha != start_sha:
        risks.append("POST_LOGIN_TO_FINAL_SHA_CHANGED")

    expected_counts = {
        "workshop": 3,
        "operation": 33,
        "workCenter": 0,
        "routingDefinition": 42,
        "routingVersion": 42,
        "routingStep": 1137,
        "engineeringOperationRequirement": 0,
    }
    for key, expected in expected_counts.items():
        if counts[key] != expected:
            risks.append(f"COUNT_MISMATCH:{key}:expected={expected}:actual={counts[key]}")

    expected_steps = {"QSFB/FM": 28, "BTKF/GT": 30, "BTKF/SM": 30}
    for code, expected in expected_steps.items():
        target = targets[code]
        if len(target["versions"]) != 1:
            risks.append(f"TARGET_VERSION_CARDINALITY:{code}:{len(target['versions'])}")
        elif target["versions"][0]["version_status"] != "released":
            risks.append(f"TARGET_VERSION_NOT_RELEASED:{code}")
        if target["summary"]["stepCount"] != expected:
            risks.append(f"TARGET_STEP_COUNT:{code}:expected={expected}:actual={target['summary']['stepCount']}")
        if target["summary"]["workshopResolvedStepCount"] != expected:
            risks.append(f"TARGET_WORKSHOP_GAP:{code}")
        if target["summary"]["workCenterResolvedStepCount"] != 0:
            risks.append(f"TARGET_UNEXPECTED_WORKCENTER:{code}")

    return {
        "gate": "PDE NODE 9 WORKCENTER BUSINESS BOUNDARY READ ONLY",
        "status": "PASS" if not risks else "FAIL",
        "riskTotal": len(risks),
        "database": str(database),
        "queryOnly": query_only == 1,
        "postLoginBaselineSha256": baseline,
        "startSha256": start_sha,
        "finalSha256": final_sha,
        "databaseBusinessWrite": 0 if start_sha == final_sha else None,
        "counts": counts,
        "modelContract": model_contract,
        "workshops": workshops,
        "operations": operations,
        "targets": targets,
        "risks": risks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--post-login-baseline-sha", required=True)
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Omit per-step rows while retaining every aggregate and all Operation rows.",
    )
    parser.add_argument(
        "--target-operation-tsv",
        action="store_true",
        help="Print the three target Routing operation lists as compact tab-separated evidence.",
    )
    args = parser.parse_args()
    evidence = build_evidence(args.database, args.post_login_baseline_sha)
    if args.target_operation_tsv:
        print("routing\toperationCode\toperationName\tworkshop\tworkCenter")
        for routing_code, target in evidence["targets"].items():
            for row in target["operationFacts"]:
                print("\t".join((
                    routing_code,
                    row["operationCode"],
                    row["operationName"],
                    row["workshopName"] or "未维护",
                    row["workCenterName"] or "未维护",
                )))
        print(f"GATE\t{evidence['status']}\tRISK_TOTAL\t{evidence['riskTotal']}")
        return 0 if evidence["status"] == "PASS" else 1
    if args.summary_only:
        for target in evidence["targets"].values():
            target.pop("steps", None)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
