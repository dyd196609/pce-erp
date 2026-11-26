"""Targeted evidence for the engineering condition-preflight read contract.

This verifier refuses every database except the named non-production acceptance
database.  It performs two authenticated GET calls, one anonymous call and one
isolated simulated database-read failure.  It never invokes a write endpoint.
"""

import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from django.db import OperationalError
from rest_framework.test import APIClient

from pde.models import (
    EngineeringCalculationRecord,
    EngineeringRuleDefinition,
    EngineeringSourceRecord,
    OrderEngineeringBaseline,
    OrderEngineeringInstance,
)
from system.models import OrganizationOperatingAuditRecord, User


EXPECTED_DATABASE = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
).resolve()
EXPECTED_IDENTITY = "PDE-OPERABLE-ACCEPTANCE-20260912"


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def counts():
    return {
        "calculations": EngineeringCalculationRecord.objects.count(),
        "targetOrderCalculations": EngineeringCalculationRecord.objects.filter(
            sales_order_item__sales_order__order_no="SO202609180003"
        ).count(),
        "instances": OrderEngineeringInstance.objects.count(),
        "rules": EngineeringRuleDefinition.objects.count(),
        "sources": EngineeringSourceRecord.objects.count(),
        "baselines": OrderEngineeringBaseline.objects.count(),
        "operatingAudits": OrganizationOperatingAuditRecord.objects.count(),
    }


URL = "/api/pde/a1-engineering/order-calculation/condition-preflight/"
PARAMS = {"orderNo": "SO202609180003", "sourceRecordId": 11}


configured_database = Path(os.environ.get("PCE_DATABASE_PATH", "")).resolve()
if configured_database != EXPECTED_DATABASE:
    raise RuntimeError(f"PCE_DATABASE_PATH must be {EXPECTED_DATABASE}")
if os.environ.get("PCE_DATABASE_IDENTITY") != EXPECTED_IDENTITY:
    raise RuntimeError(f"PCE_DATABASE_IDENTITY must be {EXPECTED_IDENTITY}")
if os.environ.get("PCE_NON_PRODUCTION_ACCEPTANCE") != "1":
    raise RuntimeError("PCE_NON_PRODUCTION_ACCEPTANCE must be 1")

user = User.objects.get(username="pce_emp_comp001_0002")
client = APIClient()
client.force_authenticate(user=user)
before = counts()
hash_before = file_hash(EXPECTED_DATABASE)
readiness_response = client.get("/api/pde/a1-engineering/calculations/readiness/")
source_order_lines = [
    row for row in readiness_response.data.get("orders", [])
    if row.get("orderNo") == "SO202609180003"
]
design_line_identity_counts = Counter(
    design.get("salesOrderItemId")
    for order_line in source_order_lines
    for design in order_line.get("currentDesignInputs", [])
)
responses = []
for _ in range(2):
    response = client.get(URL, PARAMS)
    line_results = [{
        "salesOrderItemId": row.get("salesOrderItemId"),
        "lineNo": row.get("lineNo"),
        "designObjectCount": row.get("designObjectCount"),
        "sourceStatus": row.get("sourceStatus"),
        "instanceId": row.get("orderEngineeringInstanceId"),
        "instanceNo": row.get("orderEngineeringInstanceNo"),
        "instanceStatus": row.get("instanceStatus"),
        "baselineNo": (row.get("confirmedBaseline") or {}).get("baselineNo"),
        "rules": f'{row.get("releasedRulePackageCount")}/{row.get("requiredRulePackageCount")}',
        "summary": row.get("saveReadinessSummary"),
        "blockerCodes": row.get("blockerCodes"),
        "fullValidation": row.get("fullValidation"),
    } for row in response.data.get("lines", [])]
    responses.append({
        "status": response.status_code,
        "readyForFullValidation": response.data.get("readyForFullValidation"),
        "blockerCodes": [row["code"] for row in response.data.get("blockers", [])],
        "lineCount": len(response.data.get("lines", [])),
        "lines": line_results,
        "permissionDecisionCodes": {
            code: decision.get("decisionCode")
            for code, decision in response.data.get("permissions", {}).items()
        },
        "businessWriteSideEffectCount": response.data.get("businessWriteSideEffectCount"),
    })

anonymous_response = APIClient().get(URL, PARAMS)
with patch(
    "pde.formal_engineering_continuation_service."
    "FormalEngineeringContinuationService.condition_preflight",
    side_effect=OperationalError("isolated simulated read failure"),
):
    failure_response = client.get(URL, PARAMS)

after = counts()
hash_after = file_hash(EXPECTED_DATABASE)
report = {
    "database": str(EXPECTED_DATABASE),
    "databaseIdentity": EXPECTED_IDENTITY,
    "responses": responses,
    "readinessStatus": readiness_response.status_code,
    "designLineIdentityCounts": dict(design_line_identity_counts),
    "anonymousStatus": anonymous_response.status_code,
    "readFailureStatus": failure_response.status_code,
    "readFailureCode": failure_response.data.get("code"),
    "before": before,
    "after": after,
    "businessCountsUnchanged": before == after,
    "hashBefore": hash_before,
    "hashAfter": hash_after,
    "databaseHashUnchanged": hash_before == hash_after,
}
print(json.dumps(report, ensure_ascii=False, indent=2))

if not all(row["status"] == 200 and row["businessWriteSideEffectCount"] == 0 for row in responses):
    raise SystemExit("authenticated preflight contract failed")
if before["targetOrderCalculations"] != 0 or after["targetOrderCalculations"] != 0:
    raise SystemExit("target order formal calculation records must remain zero")
if readiness_response.status_code != 200 or sorted(design_line_identity_counts.values()) != [1, 3, 5, 62]:
    raise SystemExit("stable design-to-sales-order-line identity projection failed")
expected = {
    3: (2, "OEI202609000001", 5, 85),
    4: (3, "OEI202609000002", 3, 51),
    5: (4, "OEI202609000003", 62, 248),
    6: (5, "OEI202609000004", 1, 4),
}
if not all(row["lineCount"] == 4 and row["readyForFullValidation"] for row in responses):
    raise SystemExit("order-level read-only preflight did not return four ready lines")
for response in responses:
    actual = {
        line["salesOrderItemId"]: (
            line["instanceId"], line["instanceNo"], line["designObjectCount"],
            (line["fullValidation"] or {}).get("resultPositionCount"),
        )
        for line in response["lines"]
    }
    if actual != expected:
        raise SystemExit(f"four-line validation projection mismatch: {actual}")
    if not all(
        line["sourceStatus"] == "confirmed"
        and line["instanceStatus"] == "source_confirmed"
        and str(line["baselineNo"] or "").endswith("-002")
        and line["rules"] == "2/2"
        and (line["fullValidation"] or {}).get("status") == "passed"
        and (line["fullValidation"] or {}).get("businessWriteSideEffectCount") == 0
        for line in response["lines"]
    ):
        raise SystemExit("formal source, instance, baseline, rule or full-validation facts mismatch")
if anonymous_response.status_code not in {401, 403}:
    raise SystemExit("anonymous request was not denied")
if failure_response.status_code != 503 or failure_response.data.get("code") != "CONDITION_PREFLIGHT_READ_FAILED":
    raise SystemExit("read failure was not distinguished")
if before != after or hash_before != hash_after:
    raise SystemExit("preflight changed protected business data")
