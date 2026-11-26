"""Export bounded DO4 projections from exact, read-only A/B databases."""
import json
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
paths = {"A": root / "backend/db.sqlite3", "B": Path("D:/Dev-PCE/Acceptance/PDE-Operable-20260912/pde-operable-acceptance.sqlite3")}
label = sys.argv[1]
database = paths[label]
os.environ["DJANGO_SETTINGS_MODULE"] = "pce_backend.settings"
os.environ["PCE_DATABASE_PATH"] = f"file:{database.as_posix()}?mode=ro"
sys.path.insert(0, str(root / "backend"))
from django.conf import settings
settings.DATABASES["default"]["OPTIONS"] = {"uri": True, "timeout": 30}
import django
django.setup()
from sales.source_intake import build_whole_house_intake_preview
from sales.source_review import source_actor
from sales.services import SalesBusinessError
from system.models import Company, User

result = {"databaseLabel": label, "databasePath": str(database), "connectionMode": "SQLite URI mode=ro", "organizations": []}
for company in Company.objects.filter(pk__in=[1, 3]):
    preview = build_whole_house_intake_preview(company.pk)
    candidates = preview["databaseResolution"]
    bounded = {k: v for k, v in candidates.items() if k not in ("customers", "materials")}
    bounded["commercialMaterialCandidateCount"] = len(candidates["materials"])
    result["organizations"].append({"id": company.pk, "code": company.code,
        "sourceFingerprint": preview["sourceFingerprint"], "mapping": bounded,
        "review": preview["review"], "sourceRows": preview["sourceLineIdentities"],
        "precision": preview["quantityPrecision"]})
account = User.objects.filter(username="pde_acceptance").first()
if account:
    result["historicalAcceptanceAccount"] = {"id": account.pk, "username": account.username, "organizationId": account.company_id, "active": account.is_active}
    try:
        actor, _ = source_actor(account, "confirm-source")
        result["historicalAcceptanceAccount"]["sourceActionAccess"] = "allowed"
    except SalesBusinessError as error:
        result["historicalAcceptanceAccount"]["sourceActionAccess"] = {"code": error.code, "reason": error.message}
else:
    result["historicalAcceptanceAccount"] = None
out = root / "frontend/test-results/pce-order-delivery-planning-do4-operable-closure-20260913"
(out / f"READ_ONLY_{label}_PROJECTION.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
if label == "A":
    rows = result["organizations"][0]["sourceRows"]
    lines = ["# 37 条来源逐行映射（未确认商业明细）", "", "来自同一服务端 source_evidence 投影；归档规范化证据，不是本轮重开 Excel。所有来源行的商业产品/配置/空间/销售单位/交付职责均不足，拟建销售行未确定。数量是工程／工序驱动，不是销售量。", "", "| 源行 | 稳定身份 | 类别 | 工程编码 | 原字段 | 原值＝精确计算输入 | 拟建销售行 |", "|---|---|---|---|---|---|---|"]
    for row in rows:
        lines.append(f'| {row["sourceRow"]} | {row["salesOrderItemNo"]} | {row["productType"]} | {row["engineeringSourceCode"]} | {row["quantityField"]} | {row["rawQuantity"]} | 未确定 |')
    lines.extend(["", "合并边界：无独立商业凭据不能确定销售粒度；同类别不等于同产品/配置/空间/单位/交付职责。源行完整关联且不得重复；工程量只引用一次，商业凭据行单独守恒。跨类别合并及一来源行拆多销售行明确拒绝。", "", "完整原字段、productionMeasureEvidence、identityCompleteness 及未确定项见 READ_ONLY_A_PROJECTION.json；该文档由服务端事实导出，不重算业务数量。"])
    (out / "SOURCE_ROWS_37.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
print(json.dumps({"label": label, "readOnly": True, "organizationIds": [r["id"] for r in result["organizations"]], "output": str(out / f"READ_ONLY_{label}_PROJECTION.json")}, ensure_ascii=False))
