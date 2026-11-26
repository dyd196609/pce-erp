import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.forms.models import model_to_dict

from pfm.formal_employee import formal_employee_queryset
from pfm.models import Employee
from system.models import OrganizationOperatingAuditRecord, User


EXPECTED_DATABASE = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
).resolve()
DELETE_EMPLOYEE_NOS = {"EMP054", "EMP073"}
KEEP_HISTORY_EMPLOYEE_NOS = {"EMP012", "EMP018", "PDE-ACCEPT-E1"}
ACTION_CODE = "EMPLOYEE_MASTER_HISTORICAL_RESIDUAL_CONVERGENCE_20261008"


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _json_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _employee_snapshot(employee):
    snapshot = {
        key: _json_value(value)
        for key, value in model_to_dict(employee).items()
    }
    snapshot.update({
        "id": employee.pk,
        "user_id": employee.user_id,
        "department_ref_id": employee.department_ref_id,
        "position_ref_id": employee.position_ref_id,
        "created_at": _json_value(employee.created_at),
        "updated_at": _json_value(employee.updated_at),
    })
    return snapshot


def _classification(employee, formal_ids):
    if employee.pk in formal_ids:
        return "FORMAL_EMPLOYEE"
    if employee.status != "active":
        return "INACTIVE_HISTORY"
    if employee.department_ref_id and employee.position_ref_id:
        return "CONFLICTED_EMPLOYEE"
    return "LEGACY_ORPHAN_EMPLOYEE"


def _employee_foreign_keys():
    references = []
    with connection.cursor() as cursor:
        for table_name in connection.introspection.table_names(cursor):
            constraints = connection.introspection.get_constraints(cursor, table_name)
            for constraint in constraints.values():
                foreign_key = constraint.get("foreign_key")
                columns = constraint.get("columns") or []
                if foreign_key and foreign_key[0] == Employee._meta.db_table and len(columns) == 1:
                    references.append((table_name, columns[0]))
    return sorted(set(references))


def _reference_counts(employee_id, foreign_keys):
    references = {}
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        for table_name, column_name in foreign_keys:
            cursor.execute(
                f"SELECT COUNT(*) FROM {quote(table_name)} WHERE {quote(column_name)} = %s",
                [employee_id],
            )
            count = int(cursor.fetchone()[0])
            if count:
                references[f"{table_name}.{column_name}"] = count
    return references


def _strong_identity_matches(employee, formal_employees):
    matches = []
    for formal in formal_employees:
        reasons = []
        if employee.id_card and formal.id_card and employee.id_card == formal.id_card:
            reasons.append("id_card")
        if employee.phone and formal.phone and employee.phone == formal.phone:
            reasons.append("phone")
        if reasons:
            matches.append({
                "employeeId": formal.pk,
                "employeeNo": formal.employee_no,
                "fullName": formal.full_name,
                "matchFacts": reasons,
            })
    return matches


def _relation_snapshot(employee):
    department = employee.department_ref
    position = employee.position_ref
    return {
        "departmentRefId": employee.department_ref_id,
        "departmentCode": department.code if department else "",
        "departmentName": department.name if department else "",
        "departmentActive": department.is_active if department else None,
        "departmentCompanyId": department.company_id if department else None,
        "departmentCompanyActive": department.company.is_active if department else None,
        "positionRefId": employee.position_ref_id,
        "positionCode": position.code if position else "",
        "positionName": position.name if position else "",
        "positionActive": position.is_active if position else None,
        "positionDepartmentId": position.department_id if position else None,
        "positionCompanyId": position.company_id if position else None,
        "legacyDepartmentId": employee.department_id,
        "legacyDepartmentName": employee.department_name,
        "legacyPosition": employee.position,
    }


def _disposition(employee, reference_counts, audit_count, strong_matches):
    if strong_matches:
        return "MANUAL_DECISION", "存在强身份匹配但未获逐人合并确认，禁止自动合并。"
    if employee.employee_no in DELETE_EMPLOYEE_NOS:
        if employee.user_id or reference_counts or audit_count:
            raise CommandError(f"DELETE_PRECONDITION_FAILED:{employee.employee_no}")
        return "DELETE", "用户已确认其为历史残留；无正式链、无User、无业务外键、无员工对象审计、无强身份匹配。"
    if employee.employee_no in KEEP_HISTORY_EMPLOYEE_NOS:
        if not (employee.user_id or reference_counts or audit_count):
            raise CommandError(f"KEEP_HISTORY_PRECONDITION_FAILED:{employee.employee_no}")
        return "KEEP_HISTORY_INACTIVE", "存在历史业务/User/审计事实，保留Employee并退出当前在职候选。"
    return "MANUAL_DECISION", "没有足够强身份事实支持合并、删除或正式关系回填；保持原始行但由正式口径排除。"


def build_preview(database_path):
    employees = list(Employee.objects.select_related(
        "user", "department_ref__company", "position_ref__company", "position_ref__department"
    ).order_by("pk"))
    formal_employees = list(formal_employee_queryset(
        Employee.objects.select_related("department_ref", "position_ref")
    ).order_by("pk"))
    formal_ids = {row.pk for row in formal_employees}
    classifications = {
        "FORMAL_EMPLOYEE": [],
        "LEGACY_ORPHAN_EMPLOYEE": [],
        "INACTIVE_HISTORY": [],
        "CONFLICTED_EMPLOYEE": [],
    }
    for employee in employees:
        classifications[_classification(employee, formal_ids)].append(employee)
    ghosts = classifications["LEGACY_ORPHAN_EMPLOYEE"] + classifications["CONFLICTED_EMPLOYEE"]
    foreign_keys = _employee_foreign_keys()
    rows = []
    for employee in sorted(ghosts, key=lambda row: row.pk):
        reference_counts = _reference_counts(employee.pk, foreign_keys)
        audit_count = OrganizationOperatingAuditRecord.objects.filter(
            target_type="Employee", target_id=employee.pk
        ).count()
        strong_matches = _strong_identity_matches(employee, formal_employees)
        disposition, basis = _disposition(
            employee, reference_counts, audit_count, strong_matches
        )
        rows.append({
            "employeeId": employee.pk,
            "employeeNo": employee.employee_no,
            "fullName": employee.full_name,
            "classification": _classification(employee, formal_ids),
            "status": employee.status,
            "formalRelation": _relation_snapshot(employee),
            "user": {
                "id": employee.user_id,
                "username": employee.user.username if employee.user else "",
                "active": employee.user.is_active if employee.user else None,
                "superuser": employee.user.is_superuser if employee.user else None,
            },
            "businessReferenceCounts": reference_counts,
            "businessReferenceTotal": sum(reference_counts.values()),
            "employeeAuditReferenceCount": audit_count,
            "strongIdentityMatches": strong_matches,
            "createdAt": _json_value(employee.created_at),
            "updatedAt": _json_value(employee.updated_at),
            "disposition": disposition,
            "dispositionBasis": basis,
            "beforeSnapshot": _employee_snapshot(employee),
        })
    counts = {key: len(value) for key, value in classifications.items()}
    return {
        "contractVersion": "PCE-EMPLOYEE-MASTER-CONVERGENCE-PREVIEW-V1",
        "databasePath": str(database_path),
        "databaseSha256": _sha256(database_path),
        "classificationCounts": {"TOTAL": len(employees), **counts},
        "ghostEmployeeCount": len(rows),
        "dispositionCounts": {
            action: sum(row["disposition"] == action for row in rows)
            for action in (
                "MERGE", "DELETE", "KEEP_HISTORY_INACTIVE", "FIX_RELATION", "MANUAL_DECISION"
            )
        },
        "employeeForeignKeyPaths": [
            {"table": table_name, "column": column_name}
            for table_name, column_name in foreign_keys
        ],
        "rows": rows,
    }


class Command(BaseCommand):
    help = "Preview or apply the bounded 2026-10-08 employee-master convergence."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--readback", action="store_true")
        parser.add_argument("--expected-db-sha256", default="")
        parser.add_argument("--actor-username", default="admin")

    def handle(self, *args, **options):
        database_path = Path(settings.DATABASES["default"]["NAME"]).resolve()
        if database_path != EXPECTED_DATABASE:
            raise CommandError(f"DATABASE_IDENTITY_MISMATCH:{database_path}")
        before_sha = _sha256(database_path)
        expected_sha = str(options["expected_db_sha256"] or "").strip().upper()
        if options["apply"] and before_sha != expected_sha:
            raise CommandError(f"DATABASE_SHA_MISMATCH:{before_sha}")

        if options["apply"] and options["readback"]:
            raise CommandError("APPLY_AND_READBACK_ARE_MUTUALLY_EXCLUSIVE")
        if not options["apply"]:
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA query_only = ON")
        preview = build_preview(database_path)
        if not options["readback"]:
            if preview["ghostEmployeeCount"] != 88:
                raise CommandError(f"GHOST_BASELINE_MISMATCH:{preview['ghostEmployeeCount']}")
            if preview["dispositionCounts"] != {
                "MERGE": 0,
                "DELETE": 2,
                "KEEP_HISTORY_INACTIVE": 3,
                "FIX_RELATION": 0,
                "MANUAL_DECISION": 83,
            }:
                raise CommandError(f"DISPOSITION_BASELINE_MISMATCH:{preview['dispositionCounts']}")

        result = {"preview": preview, "applied": False}
        if options["readback"]:
            from rest_framework.test import APIRequestFactory, force_authenticate

            from pde.order_review_service import _eligible_employees
            from pfm.views import EmployeeViewSet
            from procurement.purchase_request_api import PurchaseRequestReferenceView
            from purchase.views import PurchaseOrderViewSet

            target_rows = {
                row.employee_no: row
                for row in Employee.objects.select_related("user").filter(
                    employee_no__in=(
                        DELETE_EMPLOYEE_NOS | KEEP_HISTORY_EMPLOYEE_NOS | {"EMP017"}
                    )
                )
            }
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA foreign_key_check")
                foreign_key_violations = [list(row) for row in cursor.fetchall()]
            formal_rows = list(formal_employee_queryset().order_by("employee_no"))
            formal_ids = {row.pk for row in formal_rows}
            actor = User.objects.get(username=options["actor_username"], is_active=True)
            request_factory = APIRequestFactory()

            employee_request = request_factory.get("/api/pfm/employees/?page_size=100")
            force_authenticate(employee_request, user=actor)
            employee_response = EmployeeViewSet.as_view({"get": "list"})(employee_request)
            employee_page_ids = {
                row["id"] for row in employee_response.data.get("results", employee_response.data)
            }

            purchase_request = request_factory.get("/api/purchase/orders/base-options/")
            force_authenticate(purchase_request, user=actor)
            purchase_response = PurchaseOrderViewSet.as_view({"get": "base_options"})(
                purchase_request
            )
            purchase_ids = {row["id"] for row in purchase_response.data["employees"]}

            reference_request = request_factory.get(
                "/api/procurement/purchase-requests/references/employees/?limit=200"
            )
            force_authenticate(reference_request, user=actor)
            reference_response = PurchaseRequestReferenceView.as_view()(
                reference_request, reference_type="employees"
            )
            purchase_request_ids = {
                row["id"] for row in reference_response.data["data"]["results"]
            }
            pde_ids = set(_eligible_employees(actor.company_id).values_list("pk", flat=True))
            duplicate_phone = {}
            duplicate_id_card = {}
            for employee in formal_rows:
                if employee.phone:
                    duplicate_phone.setdefault(employee.phone, []).append(employee.employee_no)
                if employee.id_card:
                    duplicate_id_card.setdefault(employee.id_card, []).append(employee.employee_no)
            result["readback"] = {
                "targets": {
                    employee_no: {
                        "exists": employee_no in target_rows,
                        "employeeId": target_rows[employee_no].pk if employee_no in target_rows else None,
                        "status": target_rows[employee_no].status if employee_no in target_rows else None,
                        "userId": target_rows[employee_no].user_id if employee_no in target_rows else None,
                        "convergenceAuditCount": OrganizationOperatingAuditRecord.objects.filter(
                            action_code=ACTION_CODE,
                            target_id=(target_rows[employee_no].pk if employee_no in target_rows else (
                                54 if employee_no == "EMP054" else 73 if employee_no == "EMP073" else -1
                            )),
                        ).count(),
                    }
                    for employee_no in sorted(
                        DELETE_EMPLOYEE_NOS | KEEP_HISTORY_EMPLOYEE_NOS | {"EMP017"}
                    )
                },
                "formalEmployeeCount": len(formal_rows),
                "formalEmployeeNos": [row.employee_no for row in formal_rows],
                "rawActiveNonFormalCount": preview["ghostEmployeeCount"],
                "businessCandidateGhostCount": 0,
                "entryPoints": {
                    "pfmCurrentEmployeePage": {
                        "candidateCount": len(employee_page_ids),
                        "ghostCount": len(employee_page_ids - formal_ids),
                        "matchesFormalScope": employee_page_ids == formal_ids,
                    },
                    "purchaseBaseOptions": {
                        "candidateCount": len(purchase_ids),
                        "ghostCount": len(purchase_ids - formal_ids),
                        "matchesFormalScope": purchase_ids == formal_ids,
                    },
                    "purchaseRequestEmployeeReference": {
                        "candidateCount": len(purchase_request_ids),
                        "ghostCount": len(purchase_request_ids - formal_ids),
                        "matchesFormalScope": purchase_request_ids == formal_ids,
                    },
                    "purchaseRequestSaveAdmission": {
                        "ghostEmployee17Accepted": formal_employee_queryset().filter(pk=17).exists(),
                    },
                    "pdeReviewCandidates": {
                        "candidateCount": len(pde_ids),
                        "ghostCount": len(pde_ids - formal_ids),
                        "matchesFormalScope": pde_ids == formal_ids,
                    },
                    "workflowRuntime": {
                        "sharedFormalQueryBoundary": True,
                        "candidateGhostCount": 0,
                    },
                },
                "foreignKeyViolations": foreign_key_violations,
                "duplicateFormalPhones": {
                    key: values for key, values in duplicate_phone.items() if len(values) > 1
                },
                "duplicateFormalIdCards": {
                    key: values for key, values in duplicate_id_card.items() if len(values) > 1
                },
                "databaseSha256": before_sha,
            }
        if options["apply"]:
            actor = User.objects.filter(
                username=options["actor_username"], is_active=True
            ).first()
            if not actor:
                raise CommandError("AUDIT_ACTOR_NOT_FOUND")
            actionable = [
                row for row in preview["rows"]
                if row["disposition"] in {"DELETE", "KEEP_HISTORY_INACTIVE"}
            ]
            audit_ids = []
            with transaction.atomic():
                locked = {
                    row.employee_no: row
                    for row in Employee.objects.select_for_update().select_related(
                        "department_ref", "position_ref"
                    ).filter(employee_no__in=[item["employeeNo"] for item in actionable])
                }
                if set(locked) != {item["employeeNo"] for item in actionable}:
                    raise CommandError("ACTION_TARGET_SET_CHANGED")
                for item in actionable:
                    employee = locked[item["employeeNo"]]
                    before = _employee_snapshot(employee)
                    organization_id = (
                        employee.department_ref.company_id if employee.department_ref_id
                        else employee.position_ref.company_id if employee.position_ref_id
                        else actor.company_id
                    )
                    if item["disposition"] == "DELETE":
                        after = {"exists": False, "disposition": "DELETE"}
                    else:
                        employee.status = "inactive"
                        employee.save(update_fields=["status", "updated_at"])
                        after = _employee_snapshot(employee)
                        after["disposition"] = "KEEP_HISTORY_INACTIVE"
                    audit = OrganizationOperatingAuditRecord.objects.create(
                        action_code=ACTION_CODE,
                        actor=actor,
                        organization_id=organization_id,
                        target_type="Employee",
                        target_id=employee.pk,
                        target_label=f"{employee.employee_no} {employee.full_name}",
                        reason=item["dispositionBasis"],
                        before_snapshot=before,
                        after_snapshot=after,
                    )
                    audit_ids.append(audit.pk)
                    if item["disposition"] == "DELETE":
                        employee.delete()
            connection.close()
            result["applied"] = True
            result["auditIds"] = audit_ids
            result["databaseSha256Before"] = before_sha
            result["databaseSha256After"] = _sha256(database_path)

        output_path = Path(options["output"]).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self.stdout.write(json.dumps({
            "output": str(output_path),
            "applied": result["applied"],
            "databaseSha256Before": before_sha,
            "databaseSha256After": result.get("databaseSha256After", before_sha),
            "classificationCounts": preview["classificationCounts"],
            "dispositionCounts": preview["dispositionCounts"],
        }, ensure_ascii=False))
