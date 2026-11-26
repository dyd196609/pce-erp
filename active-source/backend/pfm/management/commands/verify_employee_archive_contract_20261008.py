import inspect
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from rest_framework.test import APIRequestFactory, force_authenticate

from pde.bom_version_control_service import control_chain_readiness, eligible_action_actors
from pde.engineering_work_context import RESPONSIBILITY_ROLES, _employee_queryset
from pde.models import BOMVersion
from pfm.formal_employee import (
    employee_archive_queryset,
    formal_employee_queryset,
    organization_complete_employee_queryset,
)
from pfm.management.commands.restore_employee_archive_20261008 import (
    ACTION_CODE,
    EXPECTED_BACKUP,
    EXPECTED_DATABASE,
    RESTORE_EMPLOYEE_NOS,
    TARGET_EMPLOYEE_NOS,
    _database_snapshot,
    _json_row,
    _sha256,
    _write_json,
)
from pfm.models import Employee
from pfm.views import EmployeeViewSet
from procurement.purchase_request_api import PurchaseRequestReferenceView
from purchase.views import PurchaseOrderViewSet
from system.access_control_views import AccessControlFoundationView
from system.models import OrganizationOperatingAuditRecord, User
from workflow_runtime.execution_resolution import WorkflowExecutionResolutionService
from workflow_runtime.models import ProcessDefinition


class Command(BaseCommand):
    help = "Read-only formal-database verification for the 124-row Employee archive contract."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)
        parser.add_argument("--actor-username", default="admin")

    def handle(self, *args, **options):
        database_path = Path(settings.DATABASES["default"]["NAME"]).resolve()
        if database_path != EXPECTED_DATABASE:
            raise CommandError(f"DATABASE_IDENTITY_MISMATCH:{database_path}")
        sha_before = _sha256(database_path)
        employee_count_before = employee_archive_queryset().count()
        audit_count_before = OrganizationOperatingAuditRecord.objects.count()

        current_columns, current_targets = _database_snapshot(database_path)
        backup_columns, backup_targets = _database_snapshot(EXPECTED_BACKUP)
        if current_columns != backup_columns:
            raise CommandError("EMPLOYEE_SCHEMA_MISMATCH")
        exact_target_rows = {
            employee_no: _json_row(current_targets.get(employee_no, {}))
            == _json_row(backup_targets.get(employee_no, {}))
            for employee_no in TARGET_EMPLOYEE_NOS
        }

        actor = User.objects.filter(
            username=options["actor_username"], is_active=True, is_superuser=True
        ).first()
        if not actor:
            raise CommandError("ACTIVE_SUPERUSER_READBACK_ACTOR_NOT_FOUND")

        request_factory = APIRequestFactory()

        def authenticated_get(path, data=None):
            request = request_factory.get(path, data=data or {})
            force_authenticate(request, user=actor)
            return request

        foundation_response = AccessControlFoundationView.as_view()(
            authenticated_get("/api/system/access-control/foundation/")
        )
        if foundation_response.status_code != 200 or not foundation_response.data.get("success"):
            raise CommandError("FOUNDATION_API_READBACK_FAILED")
        foundation = foundation_response.data["data"]
        foundation_employees = foundation["employees"]

        archive_response = EmployeeViewSet.as_view({"get": "list"})(
            authenticated_get(
                "/api/pfm/employees/", {"view": "all", "page_size": 100}
            )
        )
        if archive_response.status_code != 200:
            raise CommandError("EMPLOYEE_ARCHIVE_API_READBACK_FAILED")

        search_results = {}
        for employee_no, full_name in (("EMP054", "李婷"), ("EMP073", "沈涛")):
            response = EmployeeViewSet.as_view({"get": "list"})(
                authenticated_get(
                    "/api/pfm/employees/",
                    {"view": "all", "page_size": 100, "full_name": full_name},
                )
            )
            rows = response.data.get("results", [])
            search_results[employee_no] = {
                "fullName": full_name,
                "httpStatus": response.status_code,
                "count": response.data.get("count"),
                "ids": [row["id"] for row in rows],
                "employeeNos": [row["employee_no"] for row in rows],
            }

        purchase_response = PurchaseOrderViewSet.as_view({"get": "base_options"})(
            authenticated_get("/api/purchase/orders/base-options/")
        )
        purchase_employee_nos = {
            row.get("employee_no") or row.get("employeeNo")
            for row in purchase_response.data.get("employees", [])
        }
        reference_response = PurchaseRequestReferenceView.as_view()(
            authenticated_get(
                "/api/procurement/purchase-requests/references/employees/",
                {"limit": 200},
            ),
            reference_type="employees",
        )
        reference_rows = reference_response.data.get("data", {}).get("results", [])
        reference_employee_nos = {
            row.get("employeeNo") or row.get("employee_no") for row in reference_rows
        }
        purchase_employee_nos.discard(None)
        reference_employee_nos.discard(None)

        pde_candidates_by_role = {
            role: list(_employee_queryset(actor, role).values_list("employee_no", flat=True))
            for role in RESPONSIBILITY_ROLES
        }
        pde_candidate_employee_nos = sorted({
            employee_no
            for employee_nos in pde_candidates_by_role.values()
            for employee_no in employee_nos
        })

        workflow_candidate_employee_nos = set()
        workflow_executable_employee_nos = set()
        workflow_definition_count = 0
        for definition in ProcessDefinition.objects.filter(active=True).order_by("pk"):
            resolution = WorkflowExecutionResolutionService.resolve(
                user=actor, definition_id=definition.pk
            )
            workflow_definition_count += 1
            for node in resolution["nodes"]:
                for employee in node["employees"]:
                    workflow_candidate_employee_nos.add(employee["employeeNo"])
                    if employee["executable"]:
                        workflow_executable_employee_nos.add(employee["employeeNo"])

        bom_review_candidate_employee_nos = set()
        bom_release_candidate_employee_nos = set()
        bom_version_count = 0
        for version in BOMVersion.objects.select_related("bom").order_by("pk"):
            readiness = control_chain_readiness(version)
            bom_version_count += 1
            sod = readiness["segregationOfDuties"]
            bom_review_candidate_employee_nos.update(
                row["employeeNo"] for row in sod["reviewActors"]
            )
            bom_release_candidate_employee_nos.update(
                row["employeeNo"] for row in sod["releaseActors"]
            )

        restored_rows = {
            row["employeeNo"]: row
            for row in foundation_employees
            if row["employeeNo"] in RESTORE_EMPLOYEE_NOS
        }
        restored_ids = set(
            Employee.objects.filter(employee_no__in=RESTORE_EMPLOYEE_NOS)
            .values_list("pk", flat=True)
        )
        formal_restored_ids = set(
            formal_employee_queryset().filter(pk__in=restored_ids)
            .values_list("pk", flat=True)
        )
        organization_complete_restored_ids = set(
            organization_complete_employee_queryset().filter(pk__in=restored_ids)
            .values_list("pk", flat=True)
        )

        with connection.cursor() as cursor:
            cursor.execute("PRAGMA foreign_key_check")
            foreign_key_violations = cursor.fetchall()
            cursor.execute("PRAGMA integrity_check")
            integrity_check = [row[0] for row in cursor.fetchall()]

        source_guards = {
            "purchaseBaseOptionsUsesFormalEmployeeQuery": (
                "formal_employee_queryset" in inspect.getsource(PurchaseOrderViewSet.base_options)
            ),
            "procurementReferenceUsesFormalEmployeeQuery": (
                "formal_employee_queryset" in inspect.getsource(PurchaseRequestReferenceView.get)
            ),
            "pdeEngineeringCandidatesUseFormalEmployeeQuery": (
                "formal_employee_queryset" in inspect.getsource(_employee_queryset)
            ),
            "bomCandidatesUseFormalEmployeeQuery": (
                "formal_employee_queryset" in inspect.getsource(eligible_action_actors)
            ),
            "workflowCandidatesUseFormalEmployeeQuery": (
                "formal_employee_queryset"
                in inspect.getsource(WorkflowExecutionResolutionService)
            ),
        }

        sha_after = _sha256(database_path)
        employee_count_after = employee_archive_queryset().count()
        audit_count_after = OrganizationOperatingAuditRecord.objects.count()
        target_candidate_leaks = sorted(
            ({"EMP054", "EMP073"} & purchase_employee_nos)
            | ({"EMP054", "EMP073"} & reference_employee_nos)
            | {
                employee_no
                for employee_no, row in restored_rows.items()
                if row.get("formalCandidateBaseEligible")
            }
            | ({"EMP054", "EMP073"} & set(pde_candidate_employee_nos))
            | ({"EMP054", "EMP073"} & workflow_candidate_employee_nos)
            | ({"EMP054", "EMP073"} & workflow_executable_employee_nos)
            | ({"EMP054", "EMP073"} & bom_review_candidate_employee_nos)
            | ({"EMP054", "EMP073"} & bom_release_candidate_employee_nos)
        )
        checks = {
            "archiveCountIs124": employee_count_after == 124,
            "employeeArchiveApiCountIs124": archive_response.data.get("count") == 124,
            "foundationEmployeeCountIs124": len(foundation_employees) == 124,
            "foundationSummaryCountIs124": (
                foundation.get("employeeArchiveSummary", {}).get("employeeArchiveCount") == 124
            ),
            "allFiveRowsMatchBackupExactly": all(exact_target_rows.values()),
            "restoredEmployeesPresent": set(restored_rows) == {"EMP054", "EMP073"},
            "restoredEmployeesSearchableByChineseName": all(
                result["count"] == 1 and result["employeeNos"] == [employee_no]
                for employee_no, result in search_results.items()
            ),
            "restoredEmployeesShowMissingFormalOrganization": all(
                not row.get("organizationComplete")
                and row.get("departmentId") is None
                for row in restored_rows.values()
            ),
            "restoredEmployeesHaveNoUser": all(
                row.get("userId") is None and not row.get("username")
                for row in restored_rows.values()
            ),
            "restoredEmployeesNotFormalCandidates": not formal_restored_ids,
            "restoredEmployeesNotOrganizationComplete": not organization_complete_restored_ids,
            "restoredEmployeesAbsentFromPurchaseCandidates": not (
                {"EMP054", "EMP073"} & purchase_employee_nos
            ),
            "restoredEmployeesAbsentFromProcurementCandidates": not (
                {"EMP054", "EMP073"} & reference_employee_nos
            ),
            "candidateSourceGuardsComplete": all(source_guards.values()),
            "targetCandidateLeakCountIsZero": not target_candidate_leaks,
            "correctionAuditCountIsFive": OrganizationOperatingAuditRecord.objects.filter(
                action_code=ACTION_CODE
            ).count() == 5,
            "foreignKeyCheckPassed": not foreign_key_violations,
            "integrityCheckPassed": integrity_check == ["ok"],
            "readbackEmployeeWriteCountIsZero": employee_count_before == employee_count_after,
            "readbackAuditWriteCountIsZero": audit_count_before == audit_count_after,
            "readbackDatabaseShaUnchanged": sha_before == sha_after,
        }
        if not all(checks.values()):
            failed = sorted(key for key, passed in checks.items() if not passed)
            raise CommandError(f"EMPLOYEE_ARCHIVE_CONTRACT_FAILED:{','.join(failed)}")

        result = {
            "contractVersion": "PCE-EMPLOYEE-ARCHIVE-CONTRACT-20261008-V1",
            "result": "PASS",
            "databasePath": str(database_path),
            "databaseSha256Before": sha_before,
            "databaseSha256After": sha_after,
            "employeeCount": employee_count_after,
            "organizationCompleteCount": organization_complete_employee_queryset().count(),
            "organizationIncompleteCount": (
                employee_count_after - organization_complete_employee_queryset().count()
            ),
            "inactiveHistoryCount": employee_archive_queryset().exclude(status="active").count(),
            "formalCandidateBaseCount": formal_employee_queryset().count(),
            "correctionAuditCount": OrganizationOperatingAuditRecord.objects.filter(
                action_code=ACTION_CODE
            ).count(),
            "exactTargetRows": exact_target_rows,
            "restoredArchiveRows": restored_rows,
            "searchResults": search_results,
            "candidateSourceGuards": source_guards,
            "domainCandidateFacts": {
                "formalEmployeeBaseCount": formal_employee_queryset().count(),
                "purchaseBaseOptionsCount": len(purchase_employee_nos),
                "purchaseRequestReferenceCount": len(reference_employee_nos),
                "pde": {
                    "countsByResponsibilityRole": {
                        role: len(employee_nos)
                        for role, employee_nos in pde_candidates_by_role.items()
                    },
                    "distinctEmployeeCount": len(pde_candidate_employee_nos),
                    "employeeNos": pde_candidate_employee_nos,
                },
                "workflow": {
                    "activeDefinitionCount": workflow_definition_count,
                    "candidateEmployeeCount": len(workflow_candidate_employee_nos),
                    "executableEmployeeCount": len(workflow_executable_employee_nos),
                    "candidateEmployeeNos": sorted(workflow_candidate_employee_nos),
                    "executableEmployeeNos": sorted(workflow_executable_employee_nos),
                },
                "bom": {
                    "versionCount": bom_version_count,
                    "reviewCandidateEmployeeCount": len(bom_review_candidate_employee_nos),
                    "releaseCandidateEmployeeCount": len(bom_release_candidate_employee_nos),
                    "reviewCandidateEmployeeNos": sorted(bom_review_candidate_employee_nos),
                    "releaseCandidateEmployeeNos": sorted(bom_release_candidate_employee_nos),
                },
            },
            "candidateLeakEmployeeNos": target_candidate_leaks,
            "foreignKeyViolations": foreign_key_violations,
            "integrityCheck": integrity_check,
            "employeeWriteCount": employee_count_after - employee_count_before,
            "auditWriteCount": audit_count_after - audit_count_before,
            "checks": checks,
        }
        _write_json(Path(options["output"]).resolve(), result)
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
