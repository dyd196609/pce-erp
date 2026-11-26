"""Read-only formal admission verification: never call a creation/action API."""
import hashlib
import json
from pathlib import Path

from django.apps import apps
from django.db import connection
from rest_framework.test import APIClient
from sales.models import SalesOrder
from sales.services import engineering_readiness_facts, order_stage_readiness_facts
from sales.manufacturing_input import resolve_order_engineered_input
from system.models import User
from system.authorization import AuthorizationService

database = Path(r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3")
assert Path(connection.settings_dict["NAME"]).resolve() == database.resolve()
connection.ensure_connection()
connection.cursor().execute("PRAGMA query_only=ON")


def digest():
    return hashlib.sha256(database.read_bytes()).hexdigest().upper()


def counts():
    return {f"{app}.{model}": apps.get_model(app, model).objects.count() for app, model in (
        ("sales", "SalesOrder"), ("sales", "SalesOrderItem"), ("sales", "SalesOrderItemSupplyAdmission"),
        ("planning", "Demand"), ("planning", "PlanningRequirement"),
        ("pde", "ManufacturingInputReference"), ("pde", "ProductManufacturingOutput"),
        ("pde", "OrderEngineeringInstance"), ("pde", "OrderEngineeringBaseline"),
        ("pde", "EngineeringCalculationRecord"), ("pde", "EngineeringDocumentVersion"),
        ("pde", "BOMVersion"), ("pde", "RoutingVersion"),
        ("workflow_runtime", "WorkflowInstance"), ("workflow_runtime", "ApprovalTask"),
        ("workflow_runtime", "ApprovalDecision"), ("workflow_runtime", "BusinessStateTransition"),
        ("system", "OrganizationOperatingAuditRecord"))}


def structure():
    with connection.cursor() as cursor:
        cursor.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")
        schema = cursor.fetchall()
        cursor.execute("SELECT app,name FROM django_migrations ORDER BY app,name")
        migrations = cursor.fetchall()
    return {"schemaSha256": hashlib.sha256(json.dumps(schema).encode()).hexdigest(),
            "migrationSha256": hashlib.sha256(json.dumps(migrations).encode()).hexdigest(),
            "migrationCount": len(migrations)}


before_sha, before_counts, before_structure = digest(), counts(), structure()
checks = []


def check(name, passed):
    assert passed, name
    checks.append(name)


order = SalesOrder.objects.get(pk=3)
item = order.items.get(pk=3)
check("approved_order_preserved", order.order_no == "SO202609180003" and order.status == "approved")
check("order_quantity_and_date_preserved", str(item.quantity) == "5.0000" and str(item.required_date) == "2026-10-20")
check("no_long_term_product_or_item_output_backwrite", item.product_definition_id is None and item.product_version_id is None and item.manufacturing_output_id is None)
resolved = resolve_order_engineered_input(item)
input_facts = resolved["facts"]
check("exact_order_engineering_chain", [input_facts[key] for key in (
    "salesOrderItemId", "orderEngineeringInstanceId", "orderEngineeringBaselineId",
    "engineeringCalculationId", "engineeringDocumentVersionId", "manufacturingOutputId",
    "bomVersionId", "routingVersionId")] == [3, 2, 2, 3, 1, 1, 3, 43])
check("released_source_states", [input_facts[key] for key in (
    "engineeringInstanceStatus", "baselineStatus", "calculationStatus", "documentStatus",
    "bomStatus", "routingStatus", "outputStatus")] == [
    "calculated", "confirmed", "completed", "released", "released", "released", "released_to_manufacturing"])
check("formal_release_evidence", input_facts["generationReadback"]["completed"] and input_facts["releaseReadback"]["completed"])
readiness = engineering_readiness_facts(order)
line = next(value for value in readiness["lines"] if value["salesOrderItemId"] == 3)
check("item3_make_admission_ready", line["ready"] and line["supplyBranch"] == "MAKE" and not line["blockers"])
check("single_input_reader", line["manufacturingInput"] == input_facts)
check("supply_responsibility_preserved", line["supplyAdmission"]["confirmedBy"] == 30 and line["supplyAdmission"]["status"] == "CONFIRMED")
check("next_real_order_blocker_not_bypassed", not readiness["ready"] and [value["salesOrderItemId"] for value in readiness["lines"] if not value["ready"]] == [4, 5, 6])
check("first_real_blocker_is_item4_supply", readiness["lines"][1]["supplyBranch"] == "UNRESOLVED" and readiness["lines"][1]["blockers"] == ["订单行供应承接事实未确认或无效，无法判定 MAKE / BUY"])
stages = order_stage_readiness_facts(order)
check("whole_order_creation_still_blocked", not stages["orderConfirmationAndDemand"]["eligible"])
actor = User.objects.get(pk=11)
permission = AuthorizationService.decide(user=actor, action_code="sales.order.generate_demand",
    organization_id=str(order.company_id), business_object={"organizationId": str(order.company_id), "departmentId": order.department_id})
check("existing_demand_permission_preserved", permission.get("allowed"))
client = APIClient()
client.force_authenticate(actor)
response = client.get("/api/sales/orders/3/")
check("existing_detail_api_200", response.status_code == 200)
api_order = response.data["data"]["order"]
check("detail_api_uses_service_facts", api_order["engineeringReadiness"] == readiness and api_order["stageReadiness"] == stages)
history = client.get("/api/pde/manufacturing-admissions/", {"orderId": 3})
check("manufacturing_admission_history_unchanged", history.status_code == 200 and [history.data["rows"][0][key] for key in (
    "workflowInstanceId", "approvalDecisionId", "businessStateTransitionId", "auditId")] == [8, 8, 55, 2940])
check("order_has_no_demand", apps.get_model("planning", "Demand").objects.filter(sales_order_item__sales_order=order).count() == 0)
after_counts, after_structure = counts(), structure()
connection.close()
check("schema_and_migration_unchanged", before_structure == after_structure)
check("business_counts_unchanged", before_counts == after_counts)
check("database_sha_unchanged", before_sha == digest())
print(json.dumps({"checks": checks, "passed": len(checks), "database": str(database),
    "sha256Before": before_sha, "sha256After": digest(), "countsBefore": before_counts,
    "countsAfter": after_counts, "structureBefore": before_structure, "structureAfter": after_structure,
    "orderStatus": order.status, "item3": line, "engineeringReadiness": readiness,
    "stageReadiness": stages, "permissionAllowed": permission.get("allowed"),
    "firstBlocker": {"code": "ORDER_DEMAND_MANUFACTURING_NOT_READY", "salesOrderItemId": 4,
        "reason": readiness["lines"][1]["blockers"][0]},
    "businessWriteCount": 0, "creationServiceCalled": False}, ensure_ascii=False, default=str))
