"""Read-only evidence for the 2026-09-14 user-fact revision in B acceptance."""

import json

from pde.calculation_batch_reuse import _draft_snapshot
from pde.models import EngineeringBreakdownOption, EngineeringSourceRecord
from pfm.models import Employee
from sales.models import SalesOrder
from system.models import OrganizationOperatingAuditRecord, User


user = User.objects.get(username="pde_acceptance")
old = EngineeringSourceRecord.objects.get(pk=7)
current = EngineeringSourceRecord.objects.get(pk=8)
snapshot = _draft_snapshot(current)
calculation = snapshot["sourceCalculation"]
rows = calculation["rows"]
row36 = next(
    row for row in snapshot["rows"]
    if row.get("sourceSheet") == "三合一生产单" and int(row.get("sourceRow") or 0) == 36
)

states = {}
for row in rows:
    states[row.get("state") or "unknown"] = states.get(row.get("state") or "unknown", 0) + 1

employees = []
for name in ("冯美", "吕锋中", "张宏达"):
    employee = Employee.objects.get(full_name=name, status="active")
    employees.append({
        "id": employee.pk,
        "code": employee.employee_no,
        "name": employee.full_name,
        "companyId": employee.position_ref.company_id if employee.position_ref_id else None,
        "position": employee.position_ref.name if employee.position_ref_id else employee.position,
    })

facts = {
    "runtime": {
        "username": user.username,
        "companyId": user.company_id,
    },
    "preservedSource": {
        "id": old.pk,
        "version": old.source_version,
        "rowCount": len(old.source_payload.get("engineeringRows") or []),
        "contentHash": old.content_hash,
    },
    "currentRevision": {
        "id": current.pk,
        "version": current.source_version,
        "status": current.status,
        "rowCount": len(snapshot["rows"]),
        "calculationRequired": snapshot["calculationRequired"],
        "calculationImpact": snapshot["calculationImpact"],
        "order": snapshot["businessOrderReference"],
        "responsibilities": snapshot["confirmedResponsibilityFacts"],
        "row36Drawing": row36.get("drawingReference"),
    },
    "employees": employees,
    "formalSalesOrderMatch": list(SalesOrder.objects.filter(order_no="1-4-正").values("id", "company_id", "order_no")),
    "calculation": {
        "version": calculation["version"],
        "sourceCount": calculation["sourceCount"],
        "resultCount": len(rows),
        "states": states,
        "statusLabels": calculation["counts"],
        "formalResultsCreated": calculation["formalResultsCreated"],
        "businessWriteSideEffectCount": calculation["businessWriteSideEffectCount"],
        "segments": calculation["segments"],
    },
    "formalOptionCounts": {
        value: EngineeringBreakdownOption.objects.filter(company_id=user.company_id, option_type=value).count()
        for value in ("door_opening_direction", "line_style", "edge_method", "packaging_method")
    },
    "revisionAuditCount": OrganizationOperatingAuditRecord.objects.filter(
        organization_id=user.company_id,
        target_id=str(current.pk),
    ).count(),
}

print(json.dumps(facts, ensure_ascii=False, indent=2, default=str))
