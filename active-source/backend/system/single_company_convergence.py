"""Controlled convergence of the approved single-company non-production business scope.

This service is intentionally narrow.  It preserves historical acceptance records,
uses the existing formal master-data and engineering-draft services, and refuses any
database or stable identity other than the user-approved B database and companies.
"""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from django.conf import settings
from django.db import connection, transaction

from pde.calculation_batch_reuse import save_draft
from pde.models import EngineeringBreakdownOption, EngineeringSourceRecord, ProductCategory
from pde.production_foundation_service import ProductionFoundationService

from .authorization import AuthorizationService
from .models import Company, OrganizationOperatingAuditRecord, OrganizationUnit, User


CONTRACT_VERSION = "PCE-SINGLE-COMPANY-BUSINESS-CONVERGENCE-20260915"
EXPECTED_DATABASE_IDENTITY = "PDE-OPERABLE-ACCEPTANCE-20260912"
EXPECTED_DATABASE_PATH = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
)
TARGET_COMPANY = {"id": 1, "code": "COMP001", "name": "掌云智造科技有限公司"}
EXAMPLE_COMPANY = {"id": 2, "code": "COMP002", "name": "示例制造有限公司"}
ACCEPTANCE_COMPANY = {"id": 3, "code": "PDEACCEPT", "name": "PDE非生产页面验收"}
SOURCE_ID = 9
SOURCE_VERSION = "R20260915102628926771"
SOURCE_CONTENT_HASH = "44bbfe61296f25930c5ea8d0b47956f3156804ae722a8c9c551969c893a40f35"
WORKBOOK_SHA256 = "7ED132C13F6F7B13F5805F3872EC06528D9342A8E821A4D6F3D8B571243FB122"

OPTION_DEFINITIONS = (
    ("door_opening_direction", "DOOR-LEFT-IN", "左内开"),
    ("door_opening_direction", "DOOR-LEFT-OUT", "左外开"),
    ("door_opening_direction", "DOOR-RIGHT-IN", "右内开"),
    ("door_opening_direction", "DOOR-RIGHT-OUT", "右外开"),
    ("line_style", "LINE-40", "40"),
    ("line_style", "LINE-50", "50"),
    ("line_style", "LINE-60", "60"),
    ("line_style", "LINE-70", "70"),
    ("line_style", "LINE-80", "80"),
    ("line_style", "LINE-90", "90"),
    ("edge_method", "EDGE-ONE-LONG", "一长"),
    ("edge_method", "EDGE-ONE-WIDE", "一宽"),
    ("edge_method", "EDGE-TWO-LONG", "两长"),
    ("edge_method", "EDGE-TWO-WIDE", "两宽"),
    ("edge_method", "EDGE-ONE-LONG-ONE-WIDE", "一长一宽"),
    ("edge_method", "EDGE-ONE-LONG-TWO-WIDE", "一长两宽"),
    ("edge_method", "EDGE-TWO-LONG-ONE-WIDE", "两长一宽"),
    ("edge_method", "EDGE-FOUR-SIDES", "四边"),
    ("edge_method", "EDGE-UNFINISHED", "白坯"),
)

RESPONSIBILITY_EMPLOYEES = {
    "salesperson": {"id": 112, "employeeNo": "EMP103", "name": "冯美"},
    "designer": {"id": 111, "employeeNo": "EMP102", "name": "吕锋中"},
    "breakdownOwner": {"id": 110, "employeeNo": "EMP101", "name": "张宏达"},
}

APPROVED_EXAMPLE_CODE_RULES = (
    {"id": 13, "companyId": 2, "entityType": "production_standard_capacity", "prefix": "CAP"},
    {"id": 14, "companyId": 2, "entityType": "production_engineering_source", "prefix": "ENGSRC"},
    {"id": 15, "companyId": 2, "entityType": "production_order_engineering", "prefix": "OEI"},
    {"id": 17, "companyId": 2, "entityType": "production_engineering_calculation", "prefix": "EC"},
)


class SingleCompanyConvergenceError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _stable_company(expected, *, lock=False):
    rows = Company.objects.select_for_update() if lock else Company.objects
    company = rows.filter(pk=expected["id"]).first()
    actual = {
        "id": company.pk if company else None,
        "code": company.code if company else None,
        "name": company.name if company else None,
    }
    if actual != expected:
        raise SingleCompanyConvergenceError(
            "COMPANY_STABLE_IDENTITY_MISMATCH",
            "公司稳定身份与用户裁决不一致，已停止收敛。",
            {"expected": expected, "actual": actual},
        )
    return company


def _database_guard():
    actual_path = Path(settings.DATABASES["default"]["NAME"]).resolve()
    identity = str(__import__("os").environ.get("PCE_DATABASE_IDENTITY") or "")
    non_production = str(__import__("os").environ.get("PCE_NON_PRODUCTION_ACCEPTANCE") or "") == "1"
    if (
        actual_path != EXPECTED_DATABASE_PATH.resolve()
        or identity != EXPECTED_DATABASE_IDENTITY
        or not non_production
    ):
        raise SingleCompanyConvergenceError(
            "NON_PRODUCTION_B_DATABASE_REQUIRED",
            "本动作只允许在用户指定的非生产B库执行。",
            {"databasePath": str(actual_path), "databaseIdentity": identity, "nonProduction": non_production},
        )
    return {"path": str(actual_path), "identity": identity, "nonProduction": True}


def _table_company_references(company_id):
    """Inspect actual tables, including legacy raw company_id columns."""
    references = []
    with connection.cursor() as cursor:
        for table in sorted(connection.introspection.table_names(cursor)):
            description = connection.introspection.get_table_description(cursor, table)
            if "company_id" not in {column.name for column in description}:
                continue
            quoted = connection.ops.quote_name(table)
            cursor.execute(f"SELECT COUNT(*) FROM {quoted} WHERE company_id = %s", [company_id])
            count = int(cursor.fetchone()[0])
            if count:
                references.append({"table": table, "column": "company_id", "count": count})
    return references


def _rows_business_hash(rows):
    reference_fields = {
        "productCategoryId", "productCategoryCode",
        "doorOpeningDirectionOptionId", "doorOpeningDirectionOptionCode", "doorOpeningDirectionOptionName",
        "lineStyleOptionId", "lineStyleOptionCode", "lineStyleOptionName",
        "edgeMethodOptionId", "edgeMethodOptionCode", "edgeMethodOptionName",
    }
    canonical = [{key: value for key, value in row.items() if key not in reference_fields} for row in rows]
    return sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _ensure_options(actor):
    results = []
    for option_type, code, name in OPTION_DEFINITIONS:
        existing = EngineeringBreakdownOption.objects.filter(
            company_id=TARGET_COMPANY["id"], option_type=option_type, name=name,
        ).first()
        if existing:
            if existing.code != code or not existing.is_active:
                raise SingleCompanyConvergenceError(
                    "BASE_OPTION_CONFLICT",
                    "同名基础选项已存在但编码或状态不符合本次正式定义。",
                    {"id": existing.pk, "type": option_type, "code": existing.code, "name": name},
                )
            results.append({"id": existing.pk, "type": option_type, "code": code, "name": name, "mode": "REUSED"})
            continue
        result = ProductionFoundationService.write(
            "engineering-breakdown-options",
            user=actor,
            payload={
                "company_id": TARGET_COMPANY["id"],
                "option_type": option_type,
                "code": code,
                "name": name,
                "description": "工程录入正式基础选项；工序与班组另行管理。",
                "source_reference": f"工程拆单及订单排产数据核算方式.xlsx / {WORKBOOK_SHA256}",
                "is_active": True,
                "reason": "用户确认单一经营主体后，将原来源候选归入掌云正式基础选项",
            },
            idempotency_key=f"{CONTRACT_VERSION}:{option_type}:{code}",
            source_identity={
                "sourceSystem": "PCE_USER_CONFIRMED_WORKBOOK",
                "sourceType": "CONTROLLED_XLSX",
                "sourceObjectType": "ENGINEERING_BREAKDOWN_OPTION",
                "externalId": f"{WORKBOOK_SHA256}:{option_type}:{name}",
                "sourceFingerprint": WORKBOOK_SHA256,
                "auditMetadata": {"taskId": CONTRACT_VERSION, "businessDecisionDate": "2026-09-15"},
            },
        )
        row = result["row"]
        results.append({"id": row["id"], "type": option_type, "code": code, "name": name, "mode": "CREATED"})
    return results


def _correct_source(actor, options):
    for candidate in EngineeringSourceRecord.objects.filter(company_id=TARGET_COMPANY["id"]).order_by("pk"):
        correction = (candidate.source_payload or {}).get("companyOwnershipCorrection") or {}
        if correction.get("predecessorSourceRecordId") == SOURCE_ID:
            return candidate, {"mode": "IDEMPOTENT_REUSE", "previousSourceIds": [7, 8, 9]}

    source = EngineeringSourceRecord.objects.select_for_update().filter(pk=SOURCE_ID).first()
    if not source:
        raise SingleCompanyConvergenceError("SOURCE_NOT_FOUND", "来源ID9不存在。")
    actual = {
        "companyId": source.company_id,
        "version": source.source_version,
        "contentHash": source.content_hash,
    }
    expected = {"companyId": 3, "version": SOURCE_VERSION, "contentHash": SOURCE_CONTENT_HASH}
    if actual != expected:
        raise SingleCompanyConvergenceError("SOURCE_STABLE_IDENTITY_MISMATCH", "来源ID9身份或内容已变化。", {"expected": expected, "actual": actual})
    payload = source.source_payload if isinstance(source.source_payload, dict) else {}
    old_rows = payload.get("engineeringRows") if isinstance(payload.get("engineeringRows"), list) else []
    if len(old_rows) != 71:
        raise SingleCompanyConvergenceError("SOURCE_ROW_COUNT_MISMATCH", "来源ID9不再是71行。", {"actual": len(old_rows)})
    latest = EngineeringSourceRecord.objects.filter(
        company_id=source.company_id, source_no=source.source_no,
    ).order_by("-created_at", "-pk").first()
    if not latest or latest.pk != source.pk:
        raise SingleCompanyConvergenceError("LATER_SOURCE_VERSION_FOUND", "已存在更晚来源版本，停止覆盖。", {"latestId": latest.pk if latest else None})

    rows = deepcopy(old_rows)
    category_remaps = []
    edge_options = {row["name"]: row for row in options if row["type"] == "edge_method"}
    for row in rows:
        category_id = row.get("productCategoryId")
        if category_id:
            old_category = ProductCategory.objects.filter(pk=category_id).first()
            matches = ProductCategory.objects.filter(
                company_id=TARGET_COMPANY["id"], name=row.get("productCategoryName") or getattr(old_category, "name", ""), is_active=True,
            )
            if matches.count() != 1:
                raise SingleCompanyConvergenceError("PRODUCT_CATEGORY_REMAP_AMBIGUOUS", "来源产品分类无法唯一映射到掌云。", {"sourceRowId": row.get("id"), "oldCategoryId": category_id})
            mapped = matches.get()
            category_remaps.append({"fromId": category_id, "fromCode": row.get("productCategoryCode"), "toId": mapped.pk, "toCode": mapped.code, "name": mapped.name})
            row["productCategoryId"] = mapped.pk
            row["productCategoryCode"] = mapped.code
            row["productCategoryName"] = mapped.name
        edge_name = str(row.get("edgeMode") or "").strip()
        if edge_name in edge_options:
            option = edge_options[edge_name]
            row["edgeMethodOptionId"] = option["id"]
            row["edgeMethodOptionCode"] = option["code"]
            row["edgeMethodOptionName"] = option["name"]

    assignments = {
        role: {"employeeId": definition["id"]}
        for role, definition in RESPONSIBILITY_EMPLOYEES.items()
    }
    result = save_draft(
        actor,
        {
            "orderEngineeringInstanceId": None,
            "salesOrderItemId": None,
            "sourceScopeKey": payload.get("sourceScopeKey"),
            "sourceName": source.source_name,
            "revisionReason": "用户确认1-4-正真实归属掌云；追加公司归属纠正修订并建立责任人及精确基础选项引用",
            "responsibilityAssignments": assignments,
            "confirmedResponsibilityFacts": assignments,
            "businessOrderReference": payload.get("businessOrderReference") or {},
            "packagingMethod": {"id": None},
            "rows": rows,
            "metadataOnly": True,
        },
        registered_source_scope=payload.get("registeredSourceScope"),
        ownership_correction={
            "taskId": CONTRACT_VERSION,
            "predecessorSourceRecordId": source.pk,
            "predecessorSourceVersion": source.source_version,
            "predecessorCompany": ACCEPTANCE_COMPANY,
            "targetCompany": TARGET_COMPANY,
            "userDecisionDate": "2026-09-15",
            "reason": "1-4-正、上海王燕、上海 大居苑真实归属掌云",
            "referenceRemap": {"productCategories": category_remaps, "edgeMethodExactMatches": sum(1 for row in rows if row.get("edgeMethodOptionId"))},
            "businessRowsHashBefore": _rows_business_hash(old_rows),
            "businessRowsHashAfter": _rows_business_hash(rows),
        },
    )
    corrected = EngineeringSourceRecord.objects.select_for_update().get(pk=result["draft"]["id"])
    previous = list(EngineeringSourceRecord.objects.select_for_update().filter(pk__in=(7, 8, 9)).order_by("pk"))
    before = [{"id": row.pk, "status": row.status, "companyId": row.company_id, "version": row.source_version} for row in previous]
    for row in previous:
        row.status = "superseded"
        row.save(update_fields=("status", "updated_at"))
    OrganizationOperatingAuditRecord.objects.create(
        action_code="production.engineering.source.company_ownership.correct",
        actor=actor,
        organization_id=TARGET_COMPANY["id"],
        target_type="EngineeringSourceRecord",
        target_id=corrected.pk,
        target_label=f"{corrected.source_no} / {corrected.source_version}",
        reason="用户确认1-4-正真实工程来源归属掌云",
        before_snapshot={"historicalChain": before, "sourceRecordId": SOURCE_ID, "contentHash": SOURCE_CONTENT_HASH},
        after_snapshot={
            "currentSourceRecordId": corrected.pk,
            "currentSourceVersion": corrected.source_version,
            "company": TARGET_COMPANY,
            "historicalSourceIds": [row.pk for row in previous],
            "historicalStatus": "superseded",
            "rowCount": len(rows),
            "workbookSha256": WORKBOOK_SHA256,
            "businessRowsHash": _rows_business_hash(rows),
            "responsibilityEmployeeIds": {key: value["id"] for key, value in RESPONSIBILITY_EMPLOYEES.items()},
        },
    )
    return corrected, {"mode": "CREATED_CORRECTION_REVISION", "previousSourceIds": [row.pk for row in previous]}


def _deactivate_acceptance_company(actor):
    company = _stable_company(ACCEPTANCE_COMPANY, lock=True)
    if not company.is_active:
        return {"mode": "IDEMPOTENT_REUSE", "id": company.pk, "active": False}
    before = {"id": company.pk, "code": company.code, "name": company.name, "isActive": company.is_active}
    company.is_active = False
    company.full_clean()
    company.save(update_fields=("is_active",))
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code="system.company.archive_non_operating_acceptance",
        actor=actor,
        organization_id=TARGET_COMPANY["id"],
        target_type="Company",
        target_id=company.pk,
        target_label=f"{company.code} {company.name}",
        reason="用户确认PDEACCEPT仅保留历史验收追溯，不再作为经营公司",
        before_snapshot=before,
        after_snapshot={**before, "isActive": False, "operatingPurpose": "HISTORICAL_ACCEPTANCE_ONLY", "selectableForNewBusiness": False},
    )
    return {"mode": "DEACTIVATED", "id": company.pk, "active": False, "auditId": audit.pk}


def _delete_empty_example_company(actor):
    if not Company.objects.filter(pk=EXAMPLE_COMPANY["id"]).exists():
        return {"mode": "IDEMPOTENT_ALREADY_DELETED", "companyId": EXAMPLE_COMPANY["id"], "deletedOrganizationUnitIds": []}
    company = _stable_company(EXAMPLE_COMPANY, lock=True)
    references = _table_company_references(company.pk)
    expected = [{"table": OrganizationUnit._meta.db_table, "column": "company_id", "count": 1}]
    units = list(OrganizationUnit.objects.select_for_update().filter(company=company).order_by("pk"))
    if references != expected or len(units) != 1 or units[0].code != "COMP-COMP002" or units[0].parent_id:
        raise SingleCompanyConvergenceError(
            "EXAMPLE_COMPANY_UNEXPECTED_REFERENCES",
            "COMP002出现非预期引用，已停止删除。",
            {"references": references, "organizationUnits": [{"id": row.pk, "code": row.code, "parentId": row.parent_id} for row in units]},
        )
    unit_snapshot = [{"id": row.pk, "code": row.code, "name": row.name, "type": row.unit_type} for row in units]
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code="system.company.delete_empty_development_example",
        actor=actor,
        organization_id=TARGET_COMPANY["id"],
        target_type="Company",
        target_id=company.pk,
        target_label=f"{company.code} {company.name}",
        reason="用户确认COMP002为无业务引用的早期开发示例并明确授权物理删除",
        before_snapshot={"company": {**EXAMPLE_COMPANY, "isActive": company.is_active}, "references": references, "organizationUnits": unit_snapshot},
        after_snapshot={"companyDeleted": True, "deletedOrganizationUnits": unit_snapshot, "recoveryRequiresPreChangeBackup": True},
    )
    deleted_unit_ids = [row.pk for row in units]
    for row in units:
        row.delete()
    remaining = _table_company_references(company.pk)
    if remaining:
        raise SingleCompanyConvergenceError("EXAMPLE_COMPANY_REFERENCES_REMAIN", "删除示例组织单元后仍存在公司引用。", {"references": remaining})
    # The B database intentionally predates several currently registered models.  A
    # normal Django Collector would query absent tables.  After actual-table scanning
    # and under the database FK gate, delete exactly the approved Company primary key.
    with connection.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {connection.ops.quote_name(Company._meta.db_table)} WHERE id = %s AND code = %s AND name = %s",
            [EXAMPLE_COMPANY["id"], EXAMPLE_COMPANY["code"], EXAMPLE_COMPANY["name"]],
        )
        if cursor.rowcount != 1:
            raise SingleCompanyConvergenceError("EXAMPLE_COMPANY_DELETE_COUNT_INVALID", "COMP002精确删除行数不是1。", {"rowCount": cursor.rowcount})
    if Company.objects.filter(pk=EXAMPLE_COMPANY["id"]).exists():
        raise SingleCompanyConvergenceError("EXAMPLE_COMPANY_DELETE_READBACK_FAILED", "COMP002删除后仍可回读。")
    return {"mode": "PHYSICALLY_DELETED", "companyId": EXAMPLE_COMPANY["id"], "deletedOrganizationUnitIds": deleted_unit_ids, "auditId": audit.pk}


def _approved_code_rule_rows(*, lock=False):
    """Read the four user-approved legacy rules without treating similarly numbered models as related."""
    del lock  # SQLite serializes the surrounding atomic write; rows are still identity-locked by the transaction.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, company_id, entity_type, prefix, date_format, seq_length, current_seq, created_at "
            "FROM code_rule WHERE id IN (13, 14, 15, 17) ORDER BY id"
        )
        return [
            {
                "id": row[0], "companyId": row[1], "entityType": row[2], "prefix": row[3],
                "dateFormat": row[4], "seqLength": row[5], "currentSeq": row[6],
                "createdAt": str(row[7]),
            }
            for row in cursor.fetchall()
        ]


def _delete_approved_example_company_with_code_rules(actor):
    """Delete only the exact COMP002 objects explicitly approved on 2026-09-15."""
    database = _database_guard()
    target = _stable_company(TARGET_COMPANY, lock=True)
    if not actor.is_superuser or actor.company_id != target.pk:
        raise SingleCompanyConvergenceError(
            "CONVERGENCE_ADMIN_REQUIRED", "COMP002删除必须由掌云范围的系统管理员执行。"
        )
    decision = AuthorizationService.decide(
        user=actor,
        action_code="system.organization.structure.manage",
        organization_id=target.pk,
        business_object={"organizationId": target.pk},
    )
    if not decision.get("allowed"):
        raise SingleCompanyConvergenceError(
            decision.get("decisionCode", "PERMISSION_DENIED"),
            decision.get("reason", "组织维护权限校验失败。"),
        )

    company_exists = Company.objects.filter(pk=EXAMPLE_COMPANY["id"]).exists()
    units = list(OrganizationUnit.objects.select_for_update().filter(pk=2).order_by("pk"))
    rules = _approved_code_rule_rows(lock=True)
    if not company_exists:
        if units or rules:
            raise SingleCompanyConvergenceError(
                "EXAMPLE_COMPANY_PARTIAL_DELETE_DETECTED",
                "COMP002公司已不存在，但获批附属对象仍存在，已停止避免扩大清理。",
                {"organizationUnits": [row.pk for row in units], "codeRules": rules},
            )
        return {
            "mode": "IDEMPOTENT_ALREADY_DELETED", "database": database,
            "companyId": 2, "deletedOrganizationUnitIds": [], "deletedCodeRuleIds": [],
            "authorization": decision,
        }

    company = _stable_company(EXAMPLE_COMPANY, lock=True)
    expected_rules = [dict(row) for row in APPROVED_EXAMPLE_CODE_RULES]
    actual_rule_identity = [
        {key: row[key] for key in ("id", "companyId", "entityType", "prefix")}
        for row in rules
    ]
    unit_identity = [
        {"id": row.pk, "companyId": row.company_id, "code": row.code, "name": row.name,
         "type": row.unit_type, "parentId": row.parent_id}
        for row in units
    ]
    references = _table_company_references(company.pk)
    expected_references = [
        {"table": "code_rule", "column": "company_id", "count": 4},
        {"table": OrganizationUnit._meta.db_table, "column": "company_id", "count": 1},
    ]
    exact_unit = (
        len(units) == 1 and units[0].company_id == company.pk
        and units[0].code == "COMP-COMP002" and units[0].name == EXAMPLE_COMPANY["name"]
        and units[0].unit_type == OrganizationUnit.UnitType.COMPANY and not units[0].parent_id
    )
    if references != expected_references or actual_rule_identity != expected_rules or not exact_unit:
        raise SingleCompanyConvergenceError(
            "APPROVED_EXAMPLE_DELETE_SCOPE_CHANGED",
            "COMP002当前对象或引用已超出用户批准的六个精确对象，已停止删除。",
            {
                "references": references, "expectedReferences": expected_references,
                "codeRules": actual_rule_identity, "expectedCodeRules": expected_rules,
                "organizationUnits": unit_identity,
            },
        )

    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code="system.company.delete_approved_development_example",
        actor=actor,
        organization_id=TARGET_COMPANY["id"],
        target_type="Company",
        target_id=company.pk,
        target_label=f"{company.code} {company.name}",
        reason="用户明确批准删除COMP002、其专属组织单元ID2及code_rule ID13/14/15/17",
        before_snapshot={
            "taskId": "PCE-FOUR-PAGE-CONFIRMED-EXECUTION-DO-20260915",
            "company": {**EXAMPLE_COMPANY, "isActive": company.is_active},
            "organizationUnits": unit_identity,
            "codeRules": rules,
            "references": references,
        },
        after_snapshot={
            "companyDeleted": True,
            "deletedCompanyIds": [2],
            "deletedOrganizationUnitIds": [2],
            "deletedCodeRuleIds": [13, 14, 15, 17],
            "protectedCodeRuleIds": [10, 11, 12, 16, 20],
            "engineeringBreakdownOptionsUntouched": True,
            "recoveryBackupRequired": True,
        },
    )

    with connection.cursor() as cursor:
        for expected in APPROVED_EXAMPLE_CODE_RULES:
            cursor.execute(
                "DELETE FROM code_rule WHERE id = %s AND company_id = %s "
                "AND entity_type = %s AND prefix = %s",
                [expected["id"], expected["companyId"], expected["entityType"], expected["prefix"]],
            )
            if cursor.rowcount != 1:
                raise SingleCompanyConvergenceError(
                    "APPROVED_CODE_RULE_DELETE_COUNT_INVALID",
                    "获批编号规则精确删除行数不是1，事务已回滚。",
                    {"rule": expected, "rowCount": cursor.rowcount},
                )
    units[0].delete()
    remaining = _table_company_references(company.pk)
    if remaining:
        raise SingleCompanyConvergenceError(
            "EXAMPLE_COMPANY_REFERENCES_REMAIN", "删除获批附属对象后仍存在公司引用。",
            {"references": remaining},
        )
    with connection.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {connection.ops.quote_name(Company._meta.db_table)} "
            "WHERE id = %s AND code = %s AND name = %s AND is_active = %s",
            [2, "COMP002", EXAMPLE_COMPANY["name"], False],
        )
        if cursor.rowcount != 1:
            raise SingleCompanyConvergenceError(
                "EXAMPLE_COMPANY_DELETE_COUNT_INVALID", "COMP002精确删除行数不是1，事务已回滚。",
                {"rowCount": cursor.rowcount},
            )
    if Company.objects.filter(pk=2).exists() or OrganizationUnit.objects.filter(pk=2).exists() or _approved_code_rule_rows():
        raise SingleCompanyConvergenceError(
            "APPROVED_EXAMPLE_DELETE_READBACK_FAILED", "获批六个对象删除后仍有目标对象可回读。"
        )
    return {
        "mode": "PHYSICALLY_DELETED", "database": database,
        "companyId": 2, "deletedCompanyIds": [2], "deletedOrganizationUnitIds": [2],
        "deletedCodeRuleIds": [13, 14, 15, 17], "auditId": audit.pk,
        "authorization": decision,
    }


def _deactivate_blocked_example_company(actor, blocker):
    company = _stable_company(EXAMPLE_COMPANY, lock=True)
    before = {"id": company.pk, "code": company.code, "name": company.name, "isActive": company.is_active}
    if company.is_active:
        company.is_active = False
        company.full_clean()
        company.save(update_fields=("is_active",))
        audit = OrganizationOperatingAuditRecord.objects.create(
            action_code="system.company.deactivate_pending_safe_example_deletion",
            actor=actor,
            organization_id=TARGET_COMPANY["id"],
            target_type="Company",
            target_id=company.pk,
            target_label=f"{company.code} {company.name}",
            reason="COMP002发现未获连带删除授权的技术编号规则；先退出经营范围，物理删除等待最小裁决",
            before_snapshot=before,
            after_snapshot={**before, "isActive": False, "deleteBlocked": True, "blocker": blocker.details},
        )
        audit_id = audit.pk
    else:
        audit_id = None
    return {
        "mode": "DELETE_BLOCKED_DEACTIVATED",
        "companyId": company.pk,
        "active": False,
        "auditId": audit_id,
        "blocker": {"code": blocker.code, "message": blocker.message, "details": blocker.details},
    }


class SingleCompanyBusinessConvergenceService:
    @classmethod
    def inspect(cls):
        database = _database_guard()
        target = _stable_company(TARGET_COMPANY)
        example = Company.objects.filter(pk=EXAMPLE_COMPANY["id"]).first()
        acceptance = _stable_company(ACCEPTANCE_COMPANY)
        source = EngineeringSourceRecord.objects.filter(pk=SOURCE_ID).first()
        return {
            "contractVersion": CONTRACT_VERSION,
            "database": database,
            "targetCompany": {**TARGET_COMPANY, "isActive": target.is_active},
            "exampleCompany": {**EXAMPLE_COMPANY, "exists": bool(example), "references": _table_company_references(EXAMPLE_COMPANY["id"]) if example else []},
            "acceptanceCompany": {**ACCEPTANCE_COMPANY, "isActive": acceptance.is_active},
            "source": {"id": source.pk if source else None, "companyId": source.company_id if source else None, "version": source.source_version if source else None, "rowCount": len((source.source_payload or {}).get("engineeringRows", [])) if source else None},
            "activeCompanies": list(Company.objects.filter(is_active=True).order_by("pk").values("id", "code", "name")),
        }

    @classmethod
    @transaction.atomic
    def execute(cls, *, actor, foundation_actor, reason):
        database = _database_guard()
        target = _stable_company(TARGET_COMPANY, lock=True)
        _stable_company(ACCEPTANCE_COMPANY, lock=True)
        if not target.is_active:
            raise SingleCompanyConvergenceError("TARGET_COMPANY_INACTIVE", "掌云经营公司必须保持启用。")
        if not actor.is_superuser or actor.company_id != target.pk:
            raise SingleCompanyConvergenceError("CONVERGENCE_ADMIN_REQUIRED", "收敛动作必须由掌云范围的系统管理员执行。")
        decision = AuthorizationService.decide(
            user=actor,
            action_code="system.organization.structure.manage",
            organization_id=target.pk,
            business_object={"organizationId": target.pk},
        )
        if not decision.get("allowed"):
            raise SingleCompanyConvergenceError(decision.get("decisionCode", "PERMISSION_DENIED"), decision.get("reason", "组织维护权限校验失败。"))
        if foundation_actor.company_id != target.pk or not foundation_actor.is_active:
            raise SingleCompanyConvergenceError("FOUNDATION_ACTOR_SCOPE_INVALID", "基础资料执行身份不属于启用的掌云范围。")
        options = _ensure_options(foundation_actor)
        corrected, source_result = _correct_source(actor, options)
        archive_result = _deactivate_acceptance_company(actor)
        try:
            with transaction.atomic():
                delete_result = _delete_empty_example_company(actor)
        except SingleCompanyConvergenceError as exc:
            if exc.code != "EXAMPLE_COMPANY_UNEXPECTED_REFERENCES":
                raise
            delete_result = _deactivate_blocked_example_company(actor, exc)
        active = list(Company.objects.filter(is_active=True).order_by("pk").values("id", "code", "name"))
        if active != [TARGET_COMPANY]:
            raise SingleCompanyConvergenceError("ACTIVE_COMPANY_CONVERGENCE_FAILED", "有效经营公司未唯一收敛为掌云。", {"activeCompanies": active})
        return {
            "contractVersion": CONTRACT_VERSION,
            "database": database,
            "reason": str(reason or "")[:300],
            "activeCompanies": active,
            "historicalInactiveCompanies": list(Company.objects.filter(is_active=False).order_by("pk").values("id", "code", "name")),
            "optionResults": options,
            "optionCreatedCount": sum(row["mode"] == "CREATED" for row in options),
            "optionReusedCount": sum(row["mode"] == "REUSED" for row in options),
            "currentSource": {"id": corrected.pk, "sourceNo": corrected.source_no, "sourceVersion": corrected.source_version, "companyId": corrected.company_id, "status": corrected.status, "rowCount": len((corrected.source_payload or {}).get("engineeringRows", [])), "contentHash": corrected.content_hash},
            "sourceCorrection": source_result,
            "acceptanceCompany": archive_result,
            "exampleCompany": delete_result,
            "responsibilityEmployees": RESPONSIBILITY_EMPLOYEES,
            "authorization": decision,
        }

    @classmethod
    @transaction.atomic
    def delete_approved_example_company(cls, *, actor):
        return _delete_approved_example_company_with_code_rules(actor)


def resolve_users(*, actor_username, foundation_actor_username):
    try:
        actor = User.objects.get(username=actor_username, is_active=True)
        foundation_actor = User.objects.get(username=foundation_actor_username, is_active=True)
    except User.DoesNotExist as exc:
        raise SingleCompanyConvergenceError("EXECUTION_ACTOR_NOT_FOUND", "指定的既有执行身份不存在或已停用。") from exc
    return actor, foundation_actor
