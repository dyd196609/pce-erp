"""Read-only strict gate for SO202609180003 line 1 routing-management adoption."""

import hashlib
import json
import os
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
DATABASE = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
)
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")
os.environ["PCE_DATABASE_PATH"] = str(DATABASE)

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection  # noqa: E402
from rest_framework.test import APIRequestFactory, force_authenticate  # noqa: E402

from pde.models import BOMVersion, Routing, RoutingStep, RoutingVersion  # noqa: E402
from pde.views import RoutingListView  # noqa: E402


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


before_hash = sha256(DATABASE)
user_model = get_user_model()
user = user_model.objects.filter(username="pce_plan", company_id=1).first()
if user is None:
    user = user_model.objects.filter(company_id=1, is_active=True).order_by("pk").first()
assert user is not None, "company 1 has no active read identity"

factory = APIRequestFactory()
request = factory.get("/api/pde/routings/", {"q": "SO202609180003"})
force_authenticate(request, user=user)
response = RoutingListView.as_view()(request)
assert response.status_code == 200, response.data

rows = response.data["rows"]
target_rows = [
    row for row in rows
    if row.get("orderNo") == "SO202609180003" and row.get("orderLineNo") == 1
]
assert len(target_rows) == 1, target_rows
target = target_rows[0]
expected = {
    "companyId": 1,
    "companyCode": "COMP001",
    "orderEngineeringInstanceId": 2,
    "orderEngineeringInstanceNo": "OEI202609000001",
    "productBomId": 3,
    "bomVersionId": 3,
    "bomVersionNo": "CALC-3",
    "sourceCalculationId": 3,
    "sourceCalculationNo": "EC202609000002",
    "materialCount": 5,
    "sourceRequirementCount": 25,
    "routingId": 31,
    "routingCode": "QSFB/FM",
    "routingName": "清水封闭房门",
    "resolvedRoutingScope": "PRODUCT_CATEGORY",
    "routingIdentityCandidateCount": 1,
    "routingVersionId": 31,
    "routingVersionNo": "SYSTEM_INITIAL_VERSION",
    "routingVersionCandidateCount": 1,
    "stepCount": 28,
    "handoffAccepted": True,
    "routingVersionManagementEligible": True,
}
for key, value in expected.items():
    assert target.get(key) == value, f"{key}: expected {value!r}, got {target.get(key)!r}"

expected_operations = [
    "开料", "贴皮", "拉丝/打磨", "精裁后封边", "房门组装", "雕刻",
    "手工贴皮/封边", "加工中心", "六面钻", "加工后封边", "试装", "白坯检验",
    "白胚/打磨", "批灰/涮油", "灰磨", "第一次底漆", "第一次油磨",
    "第二次底漆", "第二次油磨", "油磨质检", "修色", "成品对色", "色磨",
    "面漆", "成品检", "玻璃/镶金属条/拉直器", "移交包装组", "包装",
]
assert target["operationSequenceLabel"] == " → ".join(
    f"{index} {name}" for index, name in enumerate(expected_operations, start=1)
)
assert target["resourceMaintenanceLabel"] == (
    "RoutingStep直接维护0/28；system.Process主数据默认提供28/28"
)
assert target["bomVersionStatusLabel"] == "草稿"
assert target["routingDefinitionStatusLabel"] == "已发布"
assert target["routingVersionStatusLabel"] == "已发布"
assert target["routingVersionManagementEligibilityLabel"] == (
    "已具备下一节点只读承接条件（本轮未进入）"
)

surface_names = (
    "apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts",
)
signatures = []
for name in surface_names:
    facts = response.data[name]
    signatures.append((
        facts["pageCode"], facts["recordCount"], facts["formalHandoffCount"],
        facts["databaseBusinessWriteCount"], facts["routingCreatedCount"],
        facts["routingVersionCreatedCount"], facts["routingStepCreatedCount"],
    ))
assert len(set(signatures)) == 1, signatures
assert signatures[0] == ("pde-routings", 3, 3, 0, 0, 0, 0)

assert BOMVersion.objects.filter(pk=3, bom_version="CALC-3", status="draft").count() == 1
counts = {
    "routingCount": Routing.objects.count(),
    "routingVersionCount": RoutingVersion.objects.count(),
    "routingStepCount": RoutingStep.objects.count(),
}
assert counts == {
    "routingCount": 42,
    "routingVersionCount": 42,
    "routingStepCount": 1137,
}

connection.close()
after_hash = sha256(DATABASE)
assert after_hash == before_hash, (before_hash, after_hash)

print(json.dumps({
    "result": "PASS",
    "formalRelationshipDecision": "A",
    "target": {key: target[key] for key in expected},
    "operationSequence": target["operationSequenceLabel"],
    "resourceMaintenance": target["resourceMaintenanceLabel"],
    "factSurfaceSignature": signatures[0],
    "formalDatabaseSha256Before": before_hash,
    "formalDatabaseSha256After": after_hash,
    **counts,
}, ensure_ascii=False, indent=2))
