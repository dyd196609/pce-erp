"""Read-only strict gate for SO202609180003 line 1 routing-version management."""

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

from pde.models import (  # noqa: E402
    BOMVersion, EngineeringDocument, Routing, RoutingStep, RoutingVersion,
)
from pde.views import RoutingVersionListView  # noqa: E402


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
request = factory.get("/api/pde/routing-versions/", {"q": "SO202609180003"})
force_authenticate(request, user=user)
response = RoutingVersionListView.as_view()(request)
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
    "definitionId": 31,
    "routingCode": "QSFB/FM",
    "routingName": "清水封闭房门",
    "resolvedRoutingScope": "PRODUCT_CATEGORY",
    "versionId": 31,
    "routingVersionNo": "SYSTEM_INITIAL_VERSION",
    "revision": 1,
    "stepCount": 28,
    "statusLabel": "已发布",
    "routingVersionHandoffAccepted": True,
    "isCurrentlyEffective": True,
    "stepRelationshipSemanticsCode": "VERSION_SCOPED_RELATIONAL_DEFINITION",
    "immutableSnapshotProven": False,
}
for key, value in expected.items():
    assert target.get(key) == value, f"{key}: expected {value!r}, got {target.get(key)!r}"

assert target["routingVersionHandoffStatusLabel"] == "已承接唯一正式工艺路线版本"
assert target["effectiveStatusLabel"] == "当前订单行唯一有效版本"
assert target["stepRelationLabel"] == "RoutingStep.routing_version_id=31（正式FK）"
assert target["stepRelationshipSemanticsLabel"] == (
    "当前版本直接拥有版本范围工序定义；模型未单独声明不可变序列化快照"
)
assert target["engineeringDocumentReleaseEligibilityLabel"] == (
    "已具备下一节点只读核验条件（本轮未进入、未发布）"
)
assert len(target["steps"]) == 28
assert [row["sequence"] for row in target["steps"]] == list(range(1, 29))
assert all(row["operationId"] for row in target["steps"])

step_field = RoutingStep._meta.get_field("routing_version")
assert step_field.remote_field.model is RoutingVersion
assert step_field.remote_field.on_delete.__name__ == "PROTECT"
assert RoutingStep.objects.filter(routing_version_id=31).count() == 28
assert RoutingStep.objects.filter(routing_version_id=31).values("sequence").distinct().count() == 28

surface_names = (
    "apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts",
)
signatures = []
for name in surface_names:
    facts = response.data[name]
    signatures.append((
        facts["pageCode"], facts["recordCount"], facts["formalHandoffCount"],
        facts["stepRelationshipSemanticsCode"], facts["immutableSnapshotProven"],
        facts["databaseBusinessWriteCount"], facts["routingCreatedCount"],
        facts["routingVersionCreatedCount"], facts["routingStepCreatedCount"],
        facts["engineeringDocumentCreatedCount"],
    ))
assert len(set(signatures)) == 1, signatures
assert signatures[0] == (
    "pde-routing-versions", 3, 3, "VERSION_SCOPED_RELATIONAL_DEFINITION",
    False, 0, 0, 0, 0, 0,
), signatures

assert BOMVersion.objects.filter(pk=3, bom_version="CALC-3", status="draft").count() == 1
assert Routing.objects.filter(pk=31, routing_code="QSFB/FM", status="released").count() == 1
assert RoutingVersion.objects.filter(
    pk=31, routing_id=31, routing_version="SYSTEM_INITIAL_VERSION",
    revision=1, status="released",
).count() == 1
counts = {
    "routingCount": Routing.objects.count(),
    "routingVersionCount": RoutingVersion.objects.count(),
    "routingStepCount": RoutingStep.objects.count(),
    "engineeringDocumentCount": EngineeringDocument.objects.count(),
}
assert counts["routingCount"] == 42
assert counts["routingVersionCount"] == 42
assert counts["routingStepCount"] == 1137

connection.close()
after_hash = sha256(DATABASE)
assert after_hash == before_hash, (before_hash, after_hash)

print(json.dumps({
    "result": "PASS",
    "formalRelationshipDecision": "C",
    "formalRelationshipExplanation": (
        "RoutingStep直接以PROTECT外键归属RoutingVersion；该关系证明版本范围，"
        "但模型未声明独立冻结的序列化快照。"
    ),
    "target": {key: target[key] for key in expected},
    "factSurfaceSignature": signatures[0],
    "formalDatabaseSha256Before": before_hash,
    "formalDatabaseSha256After": after_hash,
    **counts,
}, ensure_ascii=False, indent=2))
