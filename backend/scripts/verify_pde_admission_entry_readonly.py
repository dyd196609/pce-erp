"""Formal read-only API regression. Run through manage.py shell, no migrations."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from django.apps import apps
from django.db import connection, DatabaseError
from rest_framework.test import APIClient
from system.models import User
from pde.manufacturing_admission_read_views import ManufacturingAdmissionHistoryView

expected_path = Path(r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3")
assert Path(connection.settings_dict["NAME"]).resolve() == expected_path.resolve()
connection.ensure_connection()
connection.cursor().execute("PRAGMA query_only=ON")
def digest():
    return hashlib.sha256(expected_path.read_bytes()).hexdigest().upper()
def counts():
    return {f"{a}.{m}": apps.get_model(a, m).objects.count() for a, m in (
        ("workflow_runtime", "ProcessDefinition"), ("workflow_runtime", "WorkflowNodeDefinition"),
        ("workflow_runtime", "WorkflowInstance"), ("workflow_runtime", "ApprovalTask"),
        ("workflow_runtime", "ApprovalDecision"), ("workflow_runtime", "BusinessStateTransition"),
        ("system", "OrganizationOperatingAuditRecord"), ("planning", "Demand"),
        ("planning", "PlanningRequirement"))}
before, before_counts = digest(), counts()
checks = []
def check(name, condition):
    assert condition, name
    checks.append(name)
client = APIClient()
client.force_authenticate(User.objects.get(pk=23))
path = "/api/pde/manufacturing-admissions/"
response = client.get(path)
check("history_api_200", response.status_code == 200)
data = response.data
row = next(r for r in data["rows"] if r["orderId"] == 3)
check("golden_history_ids", [row[k] for k in ("workflowInstanceId", "approvalTaskId", "approvalDecisionId", "businessStateTransitionId", "auditId")] == [8, 8, 8, 55, 2940])
check("golden_actor", row["responsibleUserId"] == 30 and row["responsibleName"] == "赵铁柱")
check("history_consistency", row["stateMachineConsistent"] and row["statusTransitionCount"] == len(row["statusTransitionHistory"]))
check("formal_binding", data["strictFacts"]["processBinding"]["processDefinitionId"] == 10 and data["strictFacts"]["processBinding"]["workflowNodeId"] == 48)
check("five_surfaces_equal", all(data[k] == data["strictFacts"] for k in ("apiFacts", "pageFacts", "diagnosticFacts", "acceptanceFacts")))
check("read_only_contract", data["strictFacts"]["readOnly"] and not data["strictFacts"]["executionEnabled"])
check("explicit_order_context", client.get(path, {"orderId": 3}).data["rows"] == [row])
check("invalid_context_failed", client.get(path, {"orderId": "invalid"}).status_code == 409)
check("post_denied", client.post(path, {}).status_code == 405)
check("head_safe", client.head(path).status_code == 200)
actor = User.objects.get(pk=23)
actor.company_id = 999999  # In-memory negative scope test, never save.
client.force_authenticate(actor)
outside = client.get(path)
check("company_scope_no_leak", outside.status_code == 200 and outside.data["rows"] == [] and outside.data["factLoadStatus"] == "empty_valid")
actor.is_active = False
check("inactive_actor_denied", client.get(path).status_code == 403)
client.force_authenticate(User.objects.get(pk=30))
check("responsible_user_read", client.get(path).status_code == 200)
check("approver_post_still_denied", client.post(path, {}).status_code == 405)
with patch.object(ManufacturingAdmissionHistoryView, "project", side_effect=ValueError("missing audit")):
    failure = client.get(path)
    check("inconsistent_history_failed", failure.status_code == 409 and failure.data["factLoadStatus"] == "read_failed" and failure.data["recordCount"] is None)
with patch.object(ManufacturingAdmissionHistoryView, "project", side_effect=DatabaseError("unavailable")):
    failure = client.get(path)
    check("database_failure_not_empty", failure.status_code == 503 and failure.data["factLoadStatus"] == "read_failed" and failure.data["strictFacts"]["passed"] is False)
anonymous_client = APIClient()  # Do not use logout(), which may create a test session.
check("anonymous_denied", anonymous_client.get(path).status_code in (401, 403))
client.force_authenticate(User.objects.get(pk=23))
source = client.get("/api/pde/mrp-input-preparation/")
output = client.get("/api/pde/manufacturing-outputs/")
check("mrp_source_api_200", source.status_code == 200)
check("mrp_sources_preserved", source.data["rows"] == output.data["rows"])
check("source_identity_separate", source.data["strictFacts"]["pageCode"] == "pde-mrp-input-preparation" and output.data["strictFacts"]["pageCode"] == "pde-manufacturing-outputs")
check("mrp_source_authority", source.data["strictFacts"]["businessObject"] == "PdeMrpInputSource" and source.data["strictFacts"]["sourceDataAuthority"] == "pde.ProductManufacturingOutput")
check("mrp_post_denied", client.post("/api/pde/mrp-input-preparation/", {}).status_code == 405)
check("engineering_output_preserved", any(r["manufacturingOutputId"] == 1 and r["statusLabel"] == "已发布至制造" for r in output.data["rows"]))
after_counts = counts()
connection.close()
check("database_sha_unchanged", before == digest())
check("all_counts_unchanged", before_counts == after_counts)
print(json.dumps({"checks": checks, "passed": len(checks), "database": str(expected_path),
    "sha256Before": before, "sha256After": digest(), "countsBefore": before_counts,
    "countsAfter": after_counts, "history": row}, ensure_ascii=False, default=str))
