"""Exact authorized Item4 action; default is read-only, never creates Demand."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")
import django
django.setup()

from django.db import connection, transaction
from rest_framework.test import APIClient
from sales.models import SalesOrder, SalesOrderItemSupplyAdmission
from sales.services import engineering_readiness_facts
from sales.supply_admission_service import (
    authorize, confirm_supply_admission, resolve_manufacturing_execution_responsibility,
    resolve_responsibility, supply_admission_facts,
)
from system.models import User
from workflow_runtime.models import BusinessStateTransition

DATABASE = Path(r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3")
BACKUP = DATABASE.parent / "Backups" / "SO202609180003-item4-supply-admission-20261011" / "before-confirmation.sqlite3"
BASELINE = "D6DBE38E6416D5F45C291B9B38BD06A9D5EFAB6319D8469541478DD481C84384"
KEY = "SO202609180003-ITEM4-MAKE-DECISION30-EXECUTION23-V1"
REASON = "业务负责人已确认：SO202609180003第2行Item4由企业内部制造（MAKE）；赵铁柱/User30以计划物控部经理岗位负责供应决策，赵盛世/User23以生产部经理岗位承担生产执行责任，两项责任分离。本动作仅确认供应承接，不执行生产或创建Demand。"
ALLOWED = {"sales_order_item_supply_admission", "system_organization_operating_audits", "business_state_transitions"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def physical_snapshot():
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        names = [row[0] for row in cursor.fetchall()]
        rows = {}
        for name in names:
            cursor.execute(f"SELECT * FROM {connection.ops.quote_name(name)}")
            rows[name] = Counter(json.dumps(row, ensure_ascii=False, default=str) for row in cursor.fetchall())
        cursor.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")
        schema = hashlib.sha256(json.dumps(cursor.fetchall()).encode()).hexdigest()
    return rows, schema


def compare(before, after, *, wrote):
    old_rows, old_schema = before
    new_rows, new_schema = after
    assert old_schema == new_schema and old_rows.keys() == new_rows.keys(), "schema_changed"
    changes = {}
    for table, rows in old_rows.items():
        current = new_rows[table]
        if current == rows:
            continue
        if table == "sqlite_sequence" and wrote:
            # Counters may advance only for the three append-only target tables.
            old = {json.loads(row)[0]: json.loads(row)[1] for row in rows}
            new = {json.loads(row)[0]: json.loads(row)[1] for row in current}
            assert old.keys() == new.keys()
            assert all(new[name] == value for name, value in old.items() if name not in ALLOWED)
            assert all(new[name] == old[name] + 1 for name in ALLOWED)
            continue
        assert wrote and table in ALLOWED and not (rows - current), f"protected_table_changed:{table}"
        added = list((current - rows).elements())
        assert len(added) == 1, f"unexpected_append_count:{table}"
        changes[table] = {"before": sum(rows.values()), "after": sum(current.values()), "added": 1}
    assert set(changes) == (ALLOWED if wrote else set()), "unexpected_business_write_set"
    return {"physicalTableCount": len(old_rows), "unchangedTableCount": len(old_rows) - len(changes) - int(wrote),
            "allExistingRowsPreserved": True, "schemaSha256": old_schema, "changes": changes,
            "businessObjectWriteCount": 2 if wrote else 0, "auditWriteCount": 1 if wrote else 0}


def action(user):
    return confirm_supply_admission(user=user, order_id=3, item_id=4, supply_type="MAKE",
        manufacturing_owner_user_id=23, idempotency_key=KEY, reason=REASON)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-authorized-item4", action="store_true")
    args = parser.parse_args()
    assert Path(connection.settings_dict["NAME"]).resolve() == DATABASE.resolve(), "wrong_database"
    assert os.environ.get("PCE_RUNTIME_PROFILE") == "PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE"
    connection.ensure_connection()
    connection.cursor().execute("PRAGMA query_only=ON")
    assert connection.cursor().execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    before_sha = sha(DATABASE)
    before = physical_snapshot()
    counts_before = {name: sum(before[0][name].values()) for name in (
        "planning_demand", "planning_requirement", "sales_order_item_supply_admission",
        "system_organization_operating_audits", "business_state_transitions", "django_migrations")}
    order = SalesOrder.objects.get(pk=3)
    item = order.items.get(pk=4)
    assert order.order_no == "SO202609180003" and order.status == "approved" and order.created_by_id == 11
    assert item.line_no == 2 and item.material_id == 276 and str(item.quantity) == "3.0000"
    assert str(item.required_date) == "2026-10-20" and item.engineering_mode == "ORDER_ENGINEERED"
    user = User.objects.get(pk=30)
    permission, scope = authorize(user=user, item=item)
    employee, position, department, duty = resolve_responsibility(user, 1)
    assert [employee.pk, position.pk, department.pk, duty.pk, scope.pk] == [122, 30, 15, 118, 73]
    execution = resolve_manufacturing_execution_responsibility(user_id=23, company_id=1, decision_user=user)
    assert [execution[key] for key in ("employeeId", "positionId", "departmentId", "positionResponsibilityId")] == [116, 3, 2, 31]
    assert execution["name"] == "赵盛世" and execution["positionName"] == "生产部经理"
    item3_before = supply_admission_facts(order.items.get(pk=3))
    assert item3_before["status"] == "CONFIRMED" and item3_before["supplyBranch"] == "MAKE"
    readiness_before = engineering_readiness_facts(order)
    initial = supply_admission_facts(item)
    result = None
    if args.execute_authorized_item4:
        assert before_sha == BASELINE and sha(BACKUP) == BASELINE, "baseline_or_backup_mismatch"
        assert initial["status"] == "UNRESOLVED" and not SalesOrderItemSupplyAdmission.objects.filter(sales_order_item=item).exists()
        assert not BusinessStateTransition.objects.filter(object_type="SalesOrderItemSupplyAdmission", object_id=4).exists()
        # Only the official action service writes. Atomic post-checks prevent any
        # unrelated physical-table change from being committed by this runner.
        connection.cursor().execute("PRAGMA query_only=OFF")
        with transaction.atomic():
            result = action(user)
            assert not result["idempotent"] and result["businessWriteCount"] == 2 and result["auditWriteCount"] == 1
            assert result["confirmation"]["status"] == "CONFIRMED" and result["confirmation"]["confirmedBy"] == 30
            assert result["confirmation"]["responsibility"]["manufacturingExecution"] == execution
            compare(before, physical_snapshot(), wrote=True)
            assert supply_admission_facts(order.items.get(pk=3)) == item3_before
        connection.cursor().execute("PRAGMA query_only=ON")
    wrote = result is not None
    protection = compare(before, physical_snapshot(), wrote=wrote)
    fact = supply_admission_facts(item)
    replay = None
    if fact["status"] == "CONFIRMED":
        assert fact["supplyBranch"] == "MAKE" and fact["confirmedBy"] == 30
        assert fact["responsibility"]["manufacturingExecution"] == execution
        # A formally complete identical request must succeed with writes disabled.
        replay = action(user)
        assert replay["idempotent"] and replay["businessWriteCount"] == 0 and replay["auditWriteCount"] == 0
        client = APIClient()
        client.force_authenticate(user)
        response = client.get("/api/sales/orders/3/items/4/supply-admission/")
        assert response.status_code == 200 and response.data["data"]["confirmation"] == fact
    readiness_after = engineering_readiness_facts(order)
    client = APIClient()
    client.force_authenticate(User.objects.get(pk=11))
    detail = client.get("/api/sales/orders/3/")
    assert detail.status_code == 200 and detail.data["data"]["order"]["engineeringReadiness"] == readiness_after
    history = client.get("/api/pde/manufacturing-admissions/", {"orderId": 3})
    assert history.status_code == 200 and [history.data["rows"][0][key] for key in (
        "workflowInstanceId", "approvalDecisionId", "businessStateTransitionId", "auditId")] == [8, 8, 55, 2940]
    final_snapshot = physical_snapshot()
    protection = compare(before, final_snapshot, wrote=wrote)
    counts_after = {name: sum(final_snapshot[0][name].values()) for name in counts_before}
    transitions = list(BusinessStateTransition.objects.filter(object_type="SalesOrderItemSupplyAdmission", object_id=4).values(
        "id", "source_state", "target_state", "operator_id", "action_code", "audit_reference", "version", "timestamp"))
    fact_row = SalesOrderItemSupplyAdmission.objects.filter(sales_order_item=item).values("id", "fact_hash", "request_hash").first()
    first = next((line for line in readiness_after["lines"] if line["blockers"]), None)
    line_facts = {"salesOrderId": order.pk, "salesOrderNo": order.order_no,
        "status": order.status, "salesOrderItemId": item.pk, "lineNo": item.line_no,
        "materialId": item.material_id, "materialName": item.material.name,
        "quantity": str(item.quantity), "uomId": item.uom_id, "uomName": item.uom.name,
        "requiredDate": str(item.required_date), "engineeringMode": item.engineering_mode}
    connection.close()
    after_sha = sha(DATABASE)
    assert wrote or before_sha == after_sha
    print(json.dumps({"mode": "AUTHORIZED_FORMAL_ACTION" if wrote else "READ_ONLY", "database": str(DATABASE),
        "sha256Before": before_sha, "sha256After": after_sha, "backup": str(BACKUP) if wrote else None,
        "result": result, "readOnlyIdempotentReplay": replay, "confirmation": fact, "factHashes": fact_row,
        "permission": permission, "executionResponsibility": execution, "protection": protection,
        "countsBefore": counts_before, "countsAfter": counts_after,
        "orderLineFacts": line_facts,
        "transitions": transitions, "readinessBefore": readiness_before, "readinessAfter": readiness_after,
        "firstBlocker": {"code": "ORDER_DEMAND_MANUFACTURING_NOT_READY", "salesOrderItemId": first["salesOrderItemId"],
                         "reason": first["blockers"][0], "engineeringBlockerCode": first["engineeringBlockerCode"]} if first else None,
        "item3Preserved": True, "manufacturingAdmissionHistoryPreserved": True,
        "apiFactsEqualService": True, "demandCreationServiceCalled": False, "planningRequirementCreationServiceCalled": False},
        ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
