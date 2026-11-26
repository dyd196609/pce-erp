"""Three-layer read-only gate for authenticated acceptance readbacks.

The gate deliberately keeps authentication persistence and business writes as
different facts:

1. the historical login delta is accepted only when it is limited to
   ``django_session`` and one user's ``user_system.last_login``;
2. every table is fingerprinted before and after the post-login readback gate;
3. the database file hash must equal the supplied post-login baseline both at
   entry and exit.

No database is copied, restored, vacuumed, or modified by this command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import site
import sqlite3
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SITE_PACKAGES = BACKEND / "venv" / "Lib" / "site-packages"
DEFAULT_EVIDENCE = (
    ROOT
    / "docs/governance/evidence/"
    "PCE_20261004_LOGIN_AUTH_TECHNICAL_WRITE_CLASSIFICATION_V1.json"
)

APPROVED_AUTH_TABLES = frozenset({"django_session", "user_system"})
APPROVED_USER_FIELDS = frozenset({"last_login"})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def require(condition: bool, message: str, risks: list[str]) -> None:
    if not condition:
        risks.append(message)


def post_login_sha_stable(baseline: str, start: str, final: str) -> bool:
    normalized = baseline.strip().upper()
    return bool(normalized) and normalized == start.upper() == final.upper()


def classify_delta_map(
    deltas: dict[str, list[dict[str, Any]]], target_user_id: int
) -> dict[str, Any]:
    """Classify row deltas against the deliberately narrow auth whitelist."""

    rejected: list[dict[str, Any]] = []
    approved: list[dict[str, Any]] = []
    for table, changes in sorted(deltas.items()):
        if not changes:
            continue
        if table not in APPROVED_AUTH_TABLES:
            rejected.append({"table": table, "reason": "NON_WHITELIST_TABLE"})
            continue
        if table == "django_session":
            approved.append({"table": table, "changeCount": len(changes)})
            continue
        for change in changes:
            fields = set(change.get("fields") or [])
            if (
                change.get("change") != "UPDATED"
                or change.get("rowId") != target_user_id
                or fields != APPROVED_USER_FIELDS
            ):
                rejected.append(
                    {
                        "table": table,
                        "rowId": change.get("rowId"),
                        "fields": sorted(fields),
                        "reason": "USER_CHANGE_OUTSIDE_LAST_LOGIN_WHITELIST",
                    }
                )
            else:
                approved.append(
                    {
                        "table": table,
                        "rowId": target_user_id,
                        "fields": ["last_login"],
                    }
                )
    return {
        "status": "APPROVED" if not rejected else "REJECTED",
        "approved": approved,
        "rejected": rejected,
    }


def _connect_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _json_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"blobSha256": hashlib.sha256(value).hexdigest().upper()}
    return value


def table_fingerprints(path: Path) -> dict[str, dict[str, Any]]:
    """Fingerprint every application table without exposing row contents."""

    connection = _connect_read_only(path)
    result: dict[str, dict[str, Any]] = {}
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        for table in tables:
            quoted = table.replace('"', '""')
            columns = list(connection.execute(f'PRAGMA table_info("{quoted}")'))
            column_names = [row[1] for row in columns]
            pk_names = [row[1] for row in sorted(columns, key=lambda row: row[5]) if row[5]]
            order_names = pk_names or column_names
            order_clause = ", ".join(
                f'"{name.replace(chr(34), chr(34) * 2)}"' for name in order_names
            )
            rows = connection.execute(
                f'SELECT * FROM "{quoted}" ORDER BY {order_clause}'
            )
            digest = hashlib.sha256()
            count = 0
            for row in rows:
                encoded = json.dumps(
                    [_json_value(value) for value in row],
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                digest.update(encoded)
                digest.update(b"\n")
                count += 1
            result[table] = {"rowCount": count, "sha256": digest.hexdigest().upper()}
    finally:
        connection.close()
    return result


def _load_table(path: Path, table: str, key: str) -> dict[Any, dict[str, Any]]:
    connection = _connect_read_only(path)
    try:
        quoted = table.replace('"', '""')
        return {
            row[key]: dict(row)
            for row in connection.execute(f'SELECT * FROM "{quoted}"')
        }
    finally:
        connection.close()


def _user_deltas(baseline: Path, current: Path) -> list[dict[str, Any]]:
    before = _load_table(baseline, "user_system", "id")
    after = _load_table(current, "user_system", "id")
    deltas: list[dict[str, Any]] = []
    for row_id in sorted(set(before) | set(after)):
        if row_id not in before:
            deltas.append({"change": "ADDED", "rowId": row_id, "fields": []})
            continue
        if row_id not in after:
            deltas.append({"change": "DELETED", "rowId": row_id, "fields": []})
            continue
        fields = [name for name in before[row_id] if before[row_id][name] != after[row_id][name]]
        if fields:
            change: dict[str, Any] = {
                "change": "UPDATED",
                "rowId": row_id,
                "username": after[row_id].get("username"),
                "fields": fields,
            }
            if fields == ["last_login"]:
                change["oldLastLogin"] = before[row_id].get("last_login")
                change["newLastLogin"] = after[row_id].get("last_login")
            deltas.append(change)
    return deltas


def _safe_session_record(row: dict[str, Any], session_store: Any) -> dict[str, Any]:
    try:
        decoded = session_store.decode(row["session_data"])
    except Exception:
        decoded = {}
    return {
        "sessionKeySha256": hashlib.sha256(row["session_key"].encode("utf-8")).hexdigest().upper(),
        "decodedUserId": decoded.get("_auth_user_id"),
        "decodedBackend": decoded.get("_auth_user_backend"),
        "expireDate": row.get("expire_date"),
        "dataLength": len(row.get("session_data") or ""),
    }


def session_deltas(baseline: Path, current: Path, session_store: Any) -> dict[str, Any]:
    before = _load_table(baseline, "django_session", "session_key")
    after = _load_table(current, "django_session", "session_key")
    added = [_safe_session_record(after[key], session_store) for key in sorted(set(after) - set(before))]
    deleted = [_safe_session_record(before[key], session_store) for key in sorted(set(before) - set(after))]
    updated = [
        {
            "before": _safe_session_record(before[key], session_store),
            "after": _safe_session_record(after[key], session_store),
        }
        for key in sorted(set(before) & set(after))
        if before[key] != after[key]
    ]
    changes = (
        [{"change": "ADDED"} for _ in added]
        + [{"change": "DELETED"} for _ in deleted]
        + [{"change": "UPDATED"} for _ in updated]
    )
    return {
        "baselineCount": len(before),
        "currentCount": len(after),
        "added": added,
        "deleted": deleted,
        "updated": updated,
        "classifierChanges": changes,
    }


def configure_django(database_path: Path) -> None:
    site.addsitedir(str(SITE_PACKAGES))
    sys.path.insert(0, str(BACKEND))
    os.environ["PCE_DATABASE_PATH"] = str(database_path)
    os.environ["PCE_DATABASE_IDENTITY"] = "PDE-OPERABLE-ACCEPTANCE-20260912"
    os.environ["PCE_RUNTIME_PROFILE"] = "PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE"
    os.environ["PCE_NON_PRODUCTION_ACCEPTANCE"] = "1"
    os.environ["PCE_RUNTIME_LAUNCHER_VERIFIED"] = "1"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")
    import django

    django.setup()
    from django.db import connections

    with connections["default"].cursor() as cursor:
        cursor.execute("PRAGMA query_only = ON")


def protected_business_facts() -> dict[str, Any]:
    from pde.formal_manufacturing_eligibility_service import FormalManufacturingEligibilityService
    from pde.models import (
        BOMItem,
        BOMVersion,
        EngineeringCalculationDetail,
        EngineeringCalculationRecord,
        EngineeringDerivedFact,
        EngineeringMaterialRequirement,
        EngineeringOperationRequirement,
        ProductBOM,
        Routing,
        RoutingStep,
        RoutingVersion,
        WorkCenter,
    )
    from pde.order_bom_handoff_service import order_bom_handoff
    from sales.models import SalesOrder
    from system.models import Process, User, Workshop

    order = SalesOrder.objects.get(order_no="SO202609180003")
    calculations = EngineeringCalculationRecord.objects.filter(
        sales_order_item__sales_order=order
    )
    calculation_ids = list(calculations.values_list("id", flat=True))
    boms = ProductBOM.objects.filter(
        order_engineering_instance__sales_order_item__sales_order=order
    ).order_by("pk")
    bom_versions = BOMVersion.objects.filter(
        order_engineering_instance__sales_order_item__sales_order=order
    ).order_by("pk")
    bom_version_ids = list(bom_versions.values_list("id", flat=True))
    eligibility = [FormalManufacturingEligibilityService.resolve(bom) for bom in boms]
    admin = User.objects.get(username="admin")
    handoff = order_bom_handoff(user=admin, order_id=order.pk)

    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT business_purpose FROM sales_order WHERE id = %s", [order.pk])
        target_business_purpose = cursor.fetchone()[0]

    targets: dict[str, dict[str, Any]] = {}
    for code in ("QSFB/FM", "BTKF/GT", "BTKF/SM"):
        routing = Routing.objects.get(routing_code=code)
        versions = list(RoutingVersion.objects.filter(routing=routing).order_by("pk"))
        targets[code] = {
            "definitionId": routing.pk,
            "definitionStatus": routing.status,
            "versionIds": [row.pk for row in versions],
            "versionStatuses": [row.status for row in versions],
            "stepCounts": [RoutingStep.objects.filter(routing_version=row).count() for row in versions],
        }

    formal_order = SalesOrder.objects.get(order_no="SO202610020004")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT business_purpose FROM sales_order WHERE id = %s", [formal_order.pk]
        )
        formal_business_purpose = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM pde_order_review_sales_order_relation AS relation
            WHERE relation.sales_order_id = %s
              AND NOT EXISTS (
                SELECT 1 FROM pde_admission_chain_revocation AS revocation
                WHERE revocation.crm_order_relation_id = relation.id
              )
            """,
            [formal_order.pk],
        )
        valid_crm_sources = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT revocation.id
            FROM pde_admission_chain_revocation AS revocation
            INNER JOIN pde_order_engineering_instance AS instance
                    ON instance.id = revocation.engineering_instance_id
            INNER JOIN sales_order_item AS item
                    ON item.id = instance.sales_order_item_id
            WHERE item.sales_order_id = %s ORDER BY revocation.id
            """,
            [formal_order.pk],
        )
        revocations = [row[0] for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT instance.id, instance.status
            FROM pde_order_engineering_instance AS instance
            INNER JOIN sales_order_item AS item ON item.id = instance.sales_order_item_id
            WHERE item.sales_order_id = %s ORDER BY instance.id
            """,
            [formal_order.pk],
        )
        formal_instances = [{"id": row[0], "status": row[1]} for row in cursor.fetchall()]

    return {
        "SO202609180003": {
            "businessPurpose": target_business_purpose,
            "engineeringCalculation": calculations.count(),
            "completedEngineeringCalculation": calculations.filter(status="completed").count(),
            "calculationDetail": EngineeringCalculationDetail.objects.filter(
                calculation_id__in=calculation_ids
            ).count(),
            "engineeringDerivedFact": EngineeringDerivedFact.objects.filter(
                calculation_id__in=calculation_ids
            ).count(),
            "engineeringMaterialRequirement": EngineeringMaterialRequirement.objects.filter(
                calculation_id__in=calculation_ids
            ).count(),
            "engineeringOperationRequirement": EngineeringOperationRequirement.objects.filter(
                calculation_id__in=calculation_ids
            ).count(),
            "productBOM": boms.count(),
            "bomVersion": bom_versions.count(),
            "bomItem": BOMItem.objects.filter(bom_version_id__in=bom_version_ids).count(),
            "draftBomVersion": bom_versions.filter(status="draft").count(),
            "formalManufacturingEligible": all(
                row.get("formalManufacturingEligible") is True for row in eligibility
            ),
            "remainingObjectCount": (handoff.get("bomHandoffStatus") or {}).get(
                "remainingObjectCount"
            ),
        },
        "routing": {
            "definitionCount": Routing.objects.count(),
            "versionCount": RoutingVersion.objects.count(),
            "stepCount": RoutingStep.objects.count(),
            "operationCount": Process.objects.count(),
            "workshopCount": Workshop.objects.count(),
            "workCenterCount": WorkCenter.objects.count(),
            "targets": targets,
        },
        "SO202610020004": {
            "businessPurpose": formal_business_purpose,
            "currentValidCrmSource": valid_crm_sources,
            "crmAdmission": "BLOCKED" if valid_crm_sources == 0 else "ELIGIBLE",
            "revocations": revocations,
            "engineeringInstances": formal_instances,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--auth-baseline-database", required=True, type=Path)
    parser.add_argument("--historical-pre-login-sha", required=True)
    parser.add_argument("--post-login-baseline-sha", required=True)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--target-user-id", type=int, default=31)
    args = parser.parse_args()

    database = args.database.resolve()
    auth_baseline = args.auth_baseline_database.resolve()
    evidence_path = args.evidence.resolve()
    risks: list[str] = []
    require(database.is_file(), "formal acceptance database is missing", risks)
    require(auth_baseline.is_file(), "authentication state witness database is missing", risks)
    require(evidence_path.is_file(), "authentication classification evidence is missing", risks)
    if risks:
        print(json.dumps({"gate": "AUTH TECHNICAL WRITE + BUSINESS READ ONLY", "status": "FAIL", "risks": risks}, ensure_ascii=False, indent=2))
        return 1

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    start_hash = sha256(database)
    start_tables = table_fingerprints(database)
    configure_django(database)

    from django.contrib.sessions.backends.db import SessionStore

    user_changes = _user_deltas(auth_baseline, database)
    sessions = session_deltas(auth_baseline, database, SessionStore())
    delta_map = {
        "user_system": user_changes,
        "django_session": sessions["classifierChanges"],
    }
    classification = classify_delta_map(delta_map, args.target_user_id)
    facts = protected_business_facts()
    end_tables = table_fingerprints(database)
    final_hash = sha256(database)
    changed_during_readback = [
        table for table in sorted(set(start_tables) | set(end_tables))
        if start_tables.get(table) != end_tables.get(table)
    ]

    require(
        args.historical_pre_login_sha.upper() == evidence.get("preLoginSha256"),
        "historical PRE_LOGIN SHA does not match the formal classification evidence",
        risks,
    )
    require(
        args.post_login_baseline_sha.upper() == evidence.get("postLoginSha256"),
        "POST_LOGIN baseline SHA does not match the formal classification evidence",
        risks,
    )
    require(
        sha256(auth_baseline) == evidence.get("authStateWitnessSha256"),
        "authentication state witness database hash mismatch",
        risks,
    )
    require(classification["status"] == "APPROVED", "authentication delta exceeded the exact whitelist", risks)
    require(len(user_changes) == 1, "authentication witness has unexpected user row changes", risks)
    if len(user_changes) == 1:
        expected_user = evidence.get("userLastLoginChange") or {}
        require(user_changes[0].get("rowId") == expected_user.get("userId"), "login user identity drift", risks)
        require(user_changes[0].get("fields") == ["last_login"], "login user field drift", risks)
        require(user_changes[0].get("oldLastLogin") == expected_user.get("old"), "old last_login drift", risks)
        require(user_changes[0].get("newLastLogin") == expected_user.get("new"), "new last_login drift", risks)
    expected_session = evidence.get("sessionChange") or {}
    require(len(sessions["added"]) == expected_session.get("added"), "session added count drift", risks)
    require(len(sessions["deleted"]) == expected_session.get("deleted"), "session deleted count drift", risks)
    require(len(sessions["updated"]) == expected_session.get("updated"), "session updated count drift", risks)
    require(not changed_during_readback, "a table changed during the post-login readback interval", risks)
    require(post_login_sha_stable(args.post_login_baseline_sha, start_hash, final_hash), "POST_LOGIN SHA is not stable", risks)

    target = facts["SO202609180003"]
    require(target == {
        "businessPurpose": "DEVELOPMENT_VALIDATION",
        "engineeringCalculation": 4,
        "completedEngineeringCalculation": 4,
        "calculationDetail": 388,
        "engineeringDerivedFact": 388,
        "engineeringMaterialRequirement": 2,
        "engineeringOperationRequirement": 0,
        "productBOM": 2,
        "bomVersion": 2,
        "bomItem": 2,
        "draftBomVersion": 2,
        "formalManufacturingEligible": False,
        "remainingObjectCount": 69,
    }, "SO202609180003 protected business facts drift", risks)
    routing = facts["routing"]
    require(routing["definitionCount"] == 42, "Routing Definition count drift", risks)
    require(routing["operationCount"] == 33, "Operation count drift", risks)
    require(routing["workshopCount"] == 3, "Workshop count drift", risks)
    require(routing["workCenterCount"] == 0, "WorkCenter count drift", risks)
    require(routing["targets"] == {
        "QSFB/FM": {"definitionId": 31, "definitionStatus": "released", "versionIds": [31], "versionStatuses": ["released"], "stepCounts": [28]},
        "BTKF/GT": {"definitionId": 5, "definitionStatus": "released", "versionIds": [5], "versionStatuses": ["released"], "stepCounts": [30]},
        "BTKF/SM": {"definitionId": 6, "definitionStatus": "released", "versionIds": [6], "versionStatuses": ["released"], "stepCounts": [30]},
    }, "target Routing identities or Steps drift", risks)
    require(facts["SO202610020004"] == {
        "businessPurpose": "FORMAL_SALE",
        "currentValidCrmSource": 0,
        "crmAdmission": "BLOCKED",
        "revocations": [1],
        "engineeringInstances": [{"id": 6, "status": "inactive"}],
    }, "SO202610020004 protected facts drift", risks)

    result = {
        "gate": "AUTH TECHNICAL WRITE + BUSINESS READ ONLY",
        "status": "PASS" if not risks else "FAIL",
        "riskTotal": len(risks),
        "historicalEvidenceMode": evidence.get("comparisonMode"),
        "historicalPreLoginSnapshotAvailable": evidence.get("preLoginSnapshotAvailable"),
        "preLoginSha256": args.historical_pre_login_sha.upper(),
        "postLoginBaselineSha256": args.post_login_baseline_sha.upper(),
        "startSha256": start_hash,
        "finalSha256": final_hash,
        "postLoginStableShaGate": "PASS" if post_login_sha_stable(args.post_login_baseline_sha, start_hash, final_hash) else "FAIL",
        "authenticationTechnicalWrite": {
            "status": classification["status"],
            "whitelist": {
                "django_session": "controlled row add/delete/update",
                "user_system": f"user {args.target_user_id}; last_login only",
            },
            "userChanges": user_changes,
            "sessionChanges": sessions,
            "technicalRowChangeCount": len(user_changes) + len(sessions["added"]) + len(sessions["deleted"]) + len(sessions["updated"]),
            "rejected": classification["rejected"],
        },
        "businessDataGate": {
            "status": "PASS" if not changed_during_readback else "FAIL",
            "databaseBusinessWrite": 0 if not changed_during_readback else None,
            "changedTablesDuringPostLoginReadback": changed_during_readback,
            "fingerprintedTableCount": len(start_tables),
        },
        "protectedFacts": facts,
        "schemaChanged": False,
        "migrationExecuted": False,
        "risks": risks,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not risks else 1


if __name__ == "__main__":
    raise SystemExit(main())
