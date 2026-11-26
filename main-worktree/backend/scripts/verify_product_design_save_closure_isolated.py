"""Write/readback proof for product-design save chains on an explicit DB copy."""

from __future__ import annotations

import json
import os
from pathlib import Path

import django


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")
django.setup()

from pde.models import (  # noqa: E402
    ManufacturingProcessType, ProductDesignCompletionRecord, ProductDesignItem,
    ProductDesignPlanRevision, ProductDesignRevision,
)
from pde.product_design_service import (  # noqa: E402
    ProductDesignError, product_design_facts, record_design_completion,
    save_design_content, save_design_plan,
)
from system.models import User  # noqa: E402


database = Path(os.environ.get("PCE_DATABASE_PATH", "")).resolve()
protected = Path(r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3").resolve()
if not database.name.endswith("isolated.sqlite3") or database == protected:
    raise RuntimeError("PCE_DATABASE_PATH must identify the task isolated copy")

user = User.objects.filter(company_id=1, is_active=True).order_by("id").first()
if not user:
    raise RuntimeError("No active company-1 user")

facts = product_design_facts(user.company_id, user=user)
designer = (facts.get("designerOptions") or [None])[0]
configurations = facts.get("masterOptions", {}).get("processConfigurations") or []
configuration = next((row for row in configurations if row["code"] == "QSFB/FM"), configurations[0])
item = ProductDesignItem.objects.filter(
    company_id=user.company_id, pk__in=configuration["compatibleItemIds"],
).order_by("pk").first()
if not item or not designer or not configuration.get("paintProcessTypeId"):
    raise RuntimeError("Isolated copy lacks one eligible item, designer, or exact configuration-paint link")

baseline = {
    "itemCount": ProductDesignItem.objects.filter(company_id=user.company_id).count(),
    "planRevisionCount": ProductDesignPlanRevision.objects.count(),
    "designRevisionCount": ProductDesignRevision.objects.count(),
    "completionRecordCount": ProductDesignCompletionRecord.objects.count(),
    "targetItemId": item.pk, "targetItemNo": item.item_no, "targetVersion": item.version,
}

plan_payload = {
    "designGroups": [f"DES-{item.sales_order_item.line_no:02d}"],
    "designerEmployeeId": designer["employeeId"], "plannedStartDate": "2026-09-19",
    "plannedFinishDate": "2026-09-20", "planType": "SIMULATED_FOR_TEST",
    "adjustmentReason": "隔离数据库分组计划保存与回读验证",
}
facts, _ = save_design_plan(user=user, payload=plan_payload, idempotency_key="isolated-plan-save-v1")
plan_readback = next(row for row in facts["rows"] if row["id"] == item.pk)["plan"]

item.refresh_from_db()
design_payload = {
    "designItemIds": [item.pk], "expectedVersions": {str(item.pk): item.version},
    "designNature": "SIMULATED_FOR_TEST", "reason": "隔离数据库完整配置与油漆分离保存验证",
    "designData": {
        "processConfigurationId": configuration["id"],
        "paintProcessTypeId": configuration["paintProcessTypeId"],
        "designNotes": "ISOLATED_SAVE_CLOSURE_PROOF",
    },
}
facts, _ = save_design_content(user=user, payload=design_payload, idempotency_key="isolated-design-save-v1")
design_readback = next(row for row in facts["rows"] if row["id"] == item.pk)["designRevision"]
design_count_after_first = ProductDesignRevision.objects.filter(design_item=item).count()
item.refresh_from_db()
design_payload["expectedVersions"] = {str(item.pk): item.version}
save_design_content(user=user, payload=design_payload, idempotency_key="isolated-design-no-change-v2")
design_count_after_no_change = ProductDesignRevision.objects.filter(design_item=item).count()

item.refresh_from_db()
completion_payload = {
    "designItemIds": [item.pk], "expectedVersions": {str(item.pk): item.version},
    "completionNature": "SIMULATED_FOR_TEST", "actualCompletionDate": "2026-09-19",
    "designerEmployeeId": designer["employeeId"], "completionBasis": "隔离数据库模拟完成保存与回读验证",
}
facts, _ = record_design_completion(
    user=user, payload=completion_payload, idempotency_key="isolated-completion-save-v1",
)
completion_readback = next(row for row in facts["rows"] if row["id"] == item.pk)["completion"]
completion_count_after_first = ProductDesignCompletionRecord.objects.filter(design_item=item).count()
item.refresh_from_db()
completion_payload["expectedVersions"] = {str(item.pk): item.version}
record_design_completion(
    user=user, payload=completion_payload, idempotency_key="isolated-completion-no-change-v2",
)
completion_count_after_no_change = ProductDesignCompletionRecord.objects.filter(design_item=item).count()

rejections = {}
item.refresh_from_db()
for name, design_data in {
    "wrongTypeId": {"materialProcessTypeId": configuration["paintProcessTypeId"]},
    "invalidConfiguration": {"processConfigurationId": "NOT-A-REAL-CONFIG"},
}.items():
    try:
        save_design_content(user=user, payload={
            "designItemIds": [item.pk], "expectedVersions": {str(item.pk): item.version},
            "designNature": "SIMULATED_FOR_TEST", "reason": f"隔离拒绝验证-{name}",
            "designData": design_data,
        }, idempotency_key=f"isolated-reject-{name}")
    except ProductDesignError as exc:
        rejections[name] = exc.code

other_paint = ManufacturingProcessType.objects.filter(
    company_id=user.company_id, is_active=True,
).exclude(pk=configuration["paintProcessTypeId"]).order_by("pk").first()
if other_paint:
    try:
        save_design_content(user=user, payload={
            "designItemIds": [item.pk], "expectedVersions": {str(item.pk): item.version},
            "designNature": "SIMULATED_FOR_TEST", "reason": "隔离不兼容油漆拒绝验证",
            "designData": {"processConfigurationId": configuration["id"], "paintProcessTypeId": other_paint.pk},
        }, idempotency_key="isolated-reject-incompatible-paint")
    except ProductDesignError as exc:
        rejections["incompatiblePaint"] = exc.code

final = product_design_facts(user.company_id, user=user)
result = {
    "database": str(database), "baseline": baseline,
    "configuration": {
        "id": configuration["id"], "code": configuration["code"],
        "paintProcessTypeId": configuration["paintProcessTypeId"],
        "paintProcessCode": configuration["paintProcessCode"],
    },
    "planReadback": plan_readback,
    "designReadback": {
        "revision": design_readback["revision"],
        "processConfigurationCode": design_readback["processConfigurationCode"],
        "paintProcessTypeId": design_readback["paintProcessTypeId"],
        "designNotes": design_readback["designNotes"],
    },
    "completionReadback": completion_readback,
    "noChange": {
        "designRevisionCountBefore": design_count_after_first,
        "designRevisionCountAfter": design_count_after_no_change,
        "completionCountBefore": completion_count_after_first,
        "completionCountAfter": completion_count_after_no_change,
    },
    "rejections": rejections,
    "finalFacts": {
        "recordCount": final["recordCount"], "actualSourceCounts": final["actualSourceCounts"],
        "legacyD1Count": final["legacyD1Count"], "permanentProductCreated": final["permanentProductCreated"],
        "publishedDownstreamObjectCount": final["publishedDownstreamObjectCount"],
    },
}
print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
