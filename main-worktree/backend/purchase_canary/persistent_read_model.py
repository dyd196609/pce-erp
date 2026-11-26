import sqlite3
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings

from .retention import canary_retention_policy
from .scenario_mapping import resolve_scm_canary_mapping, scm_canary_scenario_catalog


def persistent_canary_database_path():
    return Path(settings.BASE_DIR) / "canary-data" / "purchase-flow-demo.sqlite3"


def persistent_canary_database_for_batch(batch_id):
    database_name = {
        "PURCHASE-FLOW-DEMO-V1": "purchase-flow-demo.sqlite3",
        "SCM-CANARY-FLOW-V1": "scm-canary-flow-v1.sqlite3",
    }.get(batch_id, "purchase-flow-demo.sqlite3")
    return Path(settings.BASE_DIR) / "canary-data" / database_name


def _object_data(row):
    if row is None:
        return None
    return {
        "moduleCode": row["module_code"],
        "moduleName": row["module_name"],
        "routePath": row["route_path"],
        "objectNo": row["object_no"],
        "status": row["object_status"],
    }


def load_persistent_canary_context(batch_id, scenario_code, module_code):
    database_path = persistent_canary_database_for_batch(batch_id)
    connection = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        batch = connection.execute(
            "SELECT * FROM pce_purchase_canary_batch WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()
        if batch is None:
            raise LookupError(f"Canary batch not found: {batch_id}")
        scenarios = connection.execute(
            "SELECT * FROM pce_purchase_canary_scenario WHERE batch_id = ? ORDER BY id",
            (batch["id"],),
        ).fetchall()
        frozen_mapping = resolve_scm_canary_mapping(batch_id, scenario_code)
        source_scenario_code = frozen_mapping["sourceScenarioCode"] if frozen_mapping else scenario_code
        selected = next((row for row in scenarios if row["code"] == source_scenario_code), None)
        if selected is None:
            raise LookupError(f"Canary source scenario not found: {source_scenario_code}")
        canary_object_count = connection.execute(
            "SELECT COUNT(*) AS count FROM pce_purchase_canary_module_object o "
            "JOIN pce_purchase_canary_scenario s ON s.id = o.scenario_id "
            "WHERE s.batch_id = ? AND o.module_code = ?",
            (batch["id"], module_code),
        ).fetchone()["count"]
        objects = connection.execute(
            "SELECT * FROM pce_purchase_canary_module_object WHERE scenario_id = ? ORDER BY sequence",
            (selected["id"],),
        ).fetchall()
        purchase_request_object = next(
            (row for row in objects if row["module_code"] == "purchase-request"), None
        )
        if frozen_mapping and (
            purchase_request_object is None
            or purchase_request_object["object_no"] != frozen_mapping["businessNo"]
        ):
            raise LookupError(
                f"Frozen SCM canary object mismatch: {scenario_code}"
            )
        current = next((row for row in objects if row["module_code"] == module_code), objects[0])
        current_index = objects.index(current)
        previous = objects[current_index - 1] if current_index > 0 else None
        following = objects[current_index + 1] if current_index + 1 < len(objects) else None
        policy = canary_retention_policy(SimpleNamespace(purpose=batch["purpose"]))
        return {
            "batchId": batch["batch_id"],
            "tenantId": batch["tenant_id"],
            "purpose": batch["purpose"],
            "dataType": policy["dataType"],
            "retentionPolicy": policy,
            "version": batch["version"],
            "currentStateSource": "server",
            "scenario": {
                "code": scenario_code,
                "name": frozen_mapping["name"] if frozen_mapping else selected["name"],
                "expectedOutcome": selected["expected_outcome"],
            },
            "scenarios": scm_canary_scenario_catalog() if frozen_mapping else [
                {"code": row["code"], "name": row["name"]} for row in scenarios
            ],
            "businessNo": frozen_mapping["businessNo"] if frozen_mapping else current["object_no"],
            "sourceScenarioCode": source_scenario_code,
            "canaryObjectCount": canary_object_count,
            "previous": _object_data(previous),
            "current": {
                **_object_data(current),
                "upstreamObjectNo": current["upstream_object_no"],
                "downstreamObjectNo": current["downstream_object_no"],
                "nextStepAllowed": bool(current["next_step_allowed"]),
                "blockReason": current["block_reason"],
                "evidenceHash": current["evidence_hash"],
            },
            "next": _object_data(following),
            "moduleObjects": [{
                **_object_data(row),
                "nextStepAllowed": bool(row["next_step_allowed"]),
                "blockReason": row["block_reason"],
            } for row in objects],
            "strictSuccessfulPool": [],
            "readModel": "persistent_canary_sqlite_read_only",
        }
    finally:
        connection.close()
