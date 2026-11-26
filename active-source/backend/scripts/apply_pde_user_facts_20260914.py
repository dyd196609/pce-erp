"""Apply the user's confirmed metadata as an append-only B-database source revision."""

from copy import deepcopy

from pde.calculation_batch_reuse import save_draft
from pde.models import EngineeringSourceRecord
from pfm.models import Employee
from system.models import User


source = EngineeringSourceRecord.objects.get(pk=7)
user = User.objects.get(username="pde_acceptance", company_id=source.company_id)
payload = source.source_payload
rows = deepcopy(payload["engineeringRows"])
row36 = next(
    row for row in rows
    if row.get("sourceSheet") == "三合一生产单" and int(row.get("sourceRow") or 0) == 36
)
row36["drawingReference"] = {
    "status": "NOT_MAINTAINED",
    "statusLabel": "图纸引用待维护",
    "displayText": "见〔图号〕图〔页码〕页",
    "drawingNo": None,
    "pageNo": None,
    "fileId": None,
    "sourceNameContainsDrawingHint": "图7餐边柜",
    "sourceNameIsFormalDrawingReference": False,
}
employees = {
    name: Employee.objects.get(full_name=name, status="active")
    for name in ("冯美", "吕锋中", "张宏达")
}
result = save_draft(user, {
    "orderEngineeringInstanceId": None,
    "salesOrderItemId": None,
    "sourceScopeKey": payload["sourceScopeKey"],
    "sourceName": source.source_name,
    "revisionReason": "落实用户确认：责任人业务事实、同一来源订单1-4-正、三合一第36行图纸引用格式；工程计算输入未变",
    "responsibilityAssignments": payload.get("responsibilityAssignments") or {},
    "confirmedResponsibilityFacts": {
        "salesperson": {"employeeId": employees["冯美"].pk},
        "designer": {"employeeId": employees["吕锋中"].pk},
        "breakdownOwner": {"employeeId": employees["张宏达"].pk},
    },
    "businessOrderReference": {
        "sourceOrderNo": "1-4-正",
        "customerName": "上海王燕",
        "projectName": "上海 大居苑",
        "sameWorkbookOrderConfirmed": True,
        "sourceEvidence": "表头!C3 + 房门单!F2 + 三合一生产单!F2；房门单!I2/三合一生产单!H2；两Sheet!F3",
    },
    "packagingMethod": payload.get("packagingMethod") or {"id": None},
    "metadataOnly": True,
    "rows": rows,
}, registered_source_scope=payload.get("registeredSourceScope"))

print({
    "sourceRecordId": result["draft"]["id"],
    "sourceVersion": result["draft"]["sourceVersion"],
    "previousSourceOverwritten": result["previousSourceOverwritten"],
    "calculationRequired": result["draft"]["calculationRequired"],
    "calculationImpact": result["draft"]["calculationImpact"],
    "rowCount": len(result["draft"]["rows"]),
    "auditId": result["auditId"],
})
