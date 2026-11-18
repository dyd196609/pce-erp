"""Apply the exact 2026-09-15 human-confirmed inputs to source record 10.

The original workbook and source record remain immutable.  A new controlled draft
revision is appended, the predecessor is retained as superseded, and all preview
quantities are produced by the existing governed calculation adapter.
"""

from copy import deepcopy

from django.db import transaction

from .calculation_batch_reuse import _draft_snapshot, authorize, save_draft
from .models import EngineeringBreakdownOption, EngineeringSourceRecord
from system.models import OrganizationOperatingAuditRecord


TASK_ID = "PCE-FOUR-PAGE-CONFIRMED-EXECUTION-DO-20260915"
SOURCE_ID = 10
SOURCE_VERSION = "R20260915123830164082"
SOURCE_CONTENT_HASH = "9858fbb7418435241cccc12dd3d0a07d7fcdcd78f4dd0774688e3dd8b174aa0a"
SOURCE_NO = "PCE-ENGINEERING-DRAFT-1-REGISTERED-XLSX-EC54A6F6CBAD4A35"

DECISIONS = (
    {"stableRowId": "SOURCE-XLSX-三合一生产单-9", "sourceRow": 9, "field": "edgeMode", "value": "白坯"},
    {"stableRowId": "SOURCE-XLSX-三合一生产单-36", "sourceRow": 36, "field": "visibleCondition", "value": "双"},
    {"stableRowId": "SOURCE-XLSX-三合一生产单-36", "sourceRow": 36, "field": "edgeMode", "value": "四边"},
    {"stableRowId": "SOURCE-XLSX-三合一生产单-60", "sourceRow": 60, "field": "edgeMode", "value": "白坯"},
    {"stableRowId": "SOURCE-XLSX-三合一生产单-68", "sourceRow": 68, "field": "edgeMode", "value": "一长"},
    {"stableRowId": "SOURCE-XLSX-三合一生产单-68", "sourceRow": 68, "field": "visibleCondition", "value": "单"},
)

EXPECTED_ROW_FACTS = {
    9: {"component": "辅助板", "length": 2400, "width": 50, "thickness": 18, "quantity": 1},
    36: {"component": "格栅屏风", "length": 1425, "width": 1040, "thickness": 25, "quantity": 1},
    60: {"component": "辅助板", "length": 2575, "width": 50, "thickness": 18, "quantity": 2.5},
    68: {"component": "辅助板", "length": 2440, "width": 50, "thickness": 18, "quantity": 1},
}


class ConfirmedEngineeringConditionError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _result_rows(snapshot):
    rows = snapshot.get("sourceCalculation", {}).get("rows", [])
    wanted = {(9, "Q"), (9, "R"), (9, "S"), (36, "Q"), (36, "R"), (36, "S"),
              (60, "Q"), (60, "R"), (60, "S"), (68, "Q"), (68, "R"), (68, "S")}
    return [
        {key: row.get(key) for key in ("sheet", "row", "column", "project", "value", "unit", "state", "statusLabel", "expected", "difference")}
        for row in rows if (row.get("row"), row.get("column")) in wanted
    ]


class ConfirmedEngineeringConditionService:
    @classmethod
    def inspect(cls, *, actor):
        isolation = authorize(actor, action_code="production.engineering.source.maintain")
        authorize(actor, action_code="production.engineering.calculation.execute")
        applied = EngineeringSourceRecord.objects.filter(
            company_id=1, source_payload__inputConfirmation__taskId=TASK_ID,
            source_payload__inputConfirmation__predecessorSourceRecordId=SOURCE_ID,
        ).order_by("-pk").first()
        source = EngineeringSourceRecord.objects.filter(pk=SOURCE_ID).first()
        return {
            "taskId": TASK_ID,
            "runtimeIsolation": isolation,
            "actor": {"id": actor.pk, "username": actor.username, "companyId": actor.company_id},
            "predecessor": {
                "id": source.pk if source else None,
                "companyId": source.company_id if source else None,
                "sourceNo": source.source_no if source else None,
                "sourceVersion": source.source_version if source else None,
                "contentHash": source.content_hash if source else None,
                "status": source.status if source else None,
            },
            "existingAppliedRevision": _draft_snapshot(applied) if applied else None,
            "decisions": list(DECISIONS),
        }

    @classmethod
    @transaction.atomic
    def execute(cls, *, actor):
        preflight = cls.inspect(actor=actor)
        if actor.pk != 10 or actor.username != "pce_plan_r12" or actor.company_id != 1 or not actor.is_active:
            raise ConfirmedEngineeringConditionError(
                "CONFIRMED_ENGINEERING_ACTOR_MISMATCH",
                "本轮工程输入必须由已确认的pce_plan_r12掌云身份执行。",
                {"actual": preflight["actor"]},
            )
        if preflight["existingAppliedRevision"]:
            return {"mode": "IDEMPOTENT_REUSE", **preflight, "current": preflight["existingAppliedRevision"]}

        source = EngineeringSourceRecord.objects.select_for_update().filter(pk=SOURCE_ID).first()
        actual = {
            "id": source.pk if source else None,
            "companyId": source.company_id if source else None,
            "sourceNo": source.source_no if source else None,
            "sourceVersion": source.source_version if source else None,
            "contentHash": source.content_hash if source else None,
            "status": source.status if source else None,
        }
        expected = {
            "id": SOURCE_ID, "companyId": 1, "sourceNo": SOURCE_NO,
            "sourceVersion": SOURCE_VERSION, "contentHash": SOURCE_CONTENT_HASH, "status": "draft",
        }
        if actual != expected:
            raise ConfirmedEngineeringConditionError(
                "SOURCE_10_STABLE_IDENTITY_MISMATCH", "来源ID10身份或状态已变化，已停止避免覆盖新成果。",
                {"expected": expected, "actual": actual},
            )
        latest = EngineeringSourceRecord.objects.filter(company_id=1, source_no=SOURCE_NO).order_by("-created_at", "-pk").first()
        if not latest or latest.pk != SOURCE_ID:
            raise ConfirmedEngineeringConditionError(
                "LATER_LEGAL_SOURCE_REVISION_FOUND", "已存在更晚合法来源修订，已停止覆盖。",
                {"latestId": latest.pk if latest else None, "latestVersion": latest.source_version if latest else None},
            )
        payload = source.source_payload if isinstance(source.source_payload, dict) else {}
        rows = deepcopy(payload.get("engineeringRows")) if isinstance(payload.get("engineeringRows"), list) else []
        if len(rows) != 71:
            raise ConfirmedEngineeringConditionError(
                "SOURCE_10_ROW_COUNT_MISMATCH", "来源ID10不再是71行。", {"actual": len(rows)}
            )
        indexed = {row.get("id"): row for row in rows if isinstance(row, dict)}
        changes = []
        edge_names = {decision["value"] for decision in DECISIONS if decision["field"] == "edgeMode"}
        edge_options = {
            row.name: row for row in EngineeringBreakdownOption.objects.filter(
                company_id=1, option_type="edge_method", name__in=edge_names, is_active=True,
            )
        }
        if set(edge_options) != edge_names:
            raise ConfirmedEngineeringConditionError(
                "CONFIRMED_EDGE_OPTION_MISSING", "用户确认的封边条件没有全部对应到掌云启用正式选项。",
                {"expected": sorted(edge_names), "actual": sorted(edge_options)},
            )
        for decision in DECISIONS:
            row = indexed.get(decision["stableRowId"])
            expected_row = EXPECTED_ROW_FACTS[decision["sourceRow"]]
            actual_row = {key: row.get(key) if row else None for key in expected_row}
            if (
                not row or row.get("sourceSheet") != "三合一生产单"
                or row.get("sourceRow") != decision["sourceRow"] or actual_row != expected_row
            ):
                raise ConfirmedEngineeringConditionError(
                    "CONFIRMED_SOURCE_ROW_IDENTITY_MISMATCH", "人工裁决行的稳定身份或尺寸数量已变化。",
                    {"decision": decision, "expectedRow": expected_row, "actualRow": actual_row},
                )
            before = row.get(decision["field"])
            row[decision["field"]] = decision["value"]
            if decision["field"] == "edgeMode":
                option = edge_options[decision["value"]]
                row.update({
                    "edgeMethodOptionId": option.pk,
                    "edgeMethodOptionCode": option.code,
                    "edgeMethodOptionName": option.name,
                })
            changes.append({**decision, "before": before, "after": decision["value"]})

        input_confirmation = {
            "taskId": TASK_ID,
            "predecessorSourceRecordId": SOURCE_ID,
            "predecessorSourceVersion": SOURCE_VERSION,
            "decisionDate": "2026-09-15",
            "source": "用户文字确认；第68行见光=单同时依据用户任务中记载的截图事实",
            "changes": changes,
            "originalWorkbookModified": False,
        }
        result = save_draft(
            actor,
            {
                "orderEngineeringInstanceId": payload.get("orderEngineeringInstanceId"),
                "salesOrderItemId": payload.get("salesOrderItemId"),
                "sourceScopeKey": payload.get("sourceScopeKey"),
                "sourceName": source.source_name,
                "revisionReason": "落实用户确认：9行白坯；36行四边/双；60行白坯；68行一长/单，并重算当前输入修订",
                "responsibilityAssignments": payload.get("responsibilityAssignments") or {},
                "confirmedResponsibilityFacts": payload.get("confirmedResponsibilityFacts") or {},
                "businessOrderReference": payload.get("businessOrderReference") or {},
                "packagingMethod": payload.get("packagingMethod") or {"id": None},
                "rows": rows,
            },
            registered_source_scope=payload.get("registeredSourceScope"),
            input_confirmation=input_confirmation,
        )
        current = EngineeringSourceRecord.objects.select_for_update().get(pk=result["draft"]["id"])
        source.status = "superseded"
        source.save(update_fields=("status", "updated_at"))
        audit = OrganizationOperatingAuditRecord.objects.create(
            action_code="production.engineering.source.confirmed_conditions.apply",
            actor=actor,
            organization_id=1,
            target_type="EngineeringSourceRecord",
            target_id=current.pk,
            target_label=f"{current.source_no} / {current.source_version}",
            reason="落实用户确认的五项缺失条件和第68行见光纠正",
            before_snapshot={
                "sourceRecordId": SOURCE_ID, "sourceVersion": SOURCE_VERSION,
                "sourceStatus": "draft", "changes": changes,
            },
            after_snapshot={
                "currentSourceRecordId": current.pk, "currentSourceVersion": current.source_version,
                "predecessorStatus": "superseded", "rowCount": len(rows),
                "changes": changes, "calculationResults": _result_rows(result["draft"]),
                "missingConditionCount": result["draft"].get("sourceCalculation", {}).get("segments", [{}])[0].get("missingCount"),
                "formalCalculationCreated": False, "originalWorkbookModified": False,
            },
        )
        return {
            "mode": "CREATED_CONFIRMED_REVISION", "preflight": preflight,
            "predecessor": {"id": source.pk, "sourceVersion": source.source_version, "status": source.status},
            "current": result["draft"], "changes": changes,
            "auditIds": [result["auditId"], audit.pk],
            "businessWriteSideEffectCount": 1,
            "auditWriteCount": 2,
            "formalCalculationCreated": False,
            "originalWorkbookModified": False,
        }
