import hashlib
import inspect
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from rest_framework.test import APIRequestFactory, force_authenticate

from pfm.formal_employee import formal_employee_queryset
from pfm.management.commands.restore_employee_archive_20261008 import EXPECTED_DATABASE
from pfm.models import Employee, EmployeeReportingRelation
from pde.models import (
    EngineeringChangeNotice,
    EngineeringDocument,
    ProductManufacturingOutput,
    ProductVersion,
)
from system.access_control_views import AccessControlFoundationView
from system.models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    Permission,
    Position,
    PositionResponsibility,
    Responsibility,
    Role,
    User,
    UserRoleScopeAssignment,
)
from system.organization_operating import OrganizationOperatingService
from workflow_runtime.models import (
    ApprovalDecision,
    ApprovalTask,
    BusinessStateTransition,
    ProcessDefinition,
    WorkflowInstance,
)


TASK_BASELINE_SHA256 = "5F871D62D1EAEB7C6BA5A36469DFEAB6922D6678CEAB67889704B5E332B1BD2B"
EMPLOYEE_FILTER_FIELDS = {
    "employeeNo",
    "fullName",
    "departmentId",
    "legacyDepartmentName",
    "positionId",
    "legacyPositionName",
    "directManagerId",
    "functionalManagerId",
    "organizationComplete",
    "status",
}


def database_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def protected_counts():
    return {
        "employee": Employee.objects.count(),
        "user": User.objects.count(),
        "role": Role.objects.count(),
        "permission": Permission.objects.count(),
        "position": Position.objects.count(),
        "responsibility": Responsibility.objects.count(),
        "positionResponsibility": PositionResponsibility.objects.count(),
        "employeeReportingRelation": EmployeeReportingRelation.objects.count(),
        "organizationOperatingAudit": OrganizationOperatingAuditRecord.objects.count(),
        "processDefinition": ProcessDefinition.objects.count(),
        "workflowInstance": WorkflowInstance.objects.count(),
        "approvalTask": ApprovalTask.objects.count(),
        "approvalDecision": ApprovalDecision.objects.count(),
        "businessStateTransition": BusinessStateTransition.objects.count(),
        "engineeringDocument": EngineeringDocument.objects.count(),
        "productVersion": ProductVersion.objects.count(),
        "engineeringChangeNotice": EngineeringChangeNotice.objects.count(),
        "productManufacturingOutput": ProductManufacturingOutput.objects.count(),
    }


class Command(BaseCommand):
    help = (
        "Read-only strict gate for the 2026-10-08 organization delivery and "
        "development-test Employee ruling."
    )

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)
        parser.add_argument("--actor-username", default="admin")

    def handle(self, *args, **options):
        database_path = Path(settings.DATABASES["default"]["NAME"]).resolve()
        if database_path != EXPECTED_DATABASE:
            raise CommandError(f"DATABASE_IDENTITY_MISMATCH:{database_path}")

        sha_before = database_sha256(database_path)
        counts_before = protected_counts()
        actor = User.objects.filter(
            username=options["actor_username"], is_active=True, is_superuser=True,
        ).first()
        if not actor:
            raise CommandError("ACTIVE_SUPERUSER_READBACK_ACTOR_NOT_FOUND")

        request = APIRequestFactory().get("/api/access-control/foundation/")
        force_authenticate(request, user=actor)
        response = AccessControlFoundationView.as_view()(request)
        if response.status_code != 200 or not response.data.get("success"):
            raise CommandError("FOUNDATION_API_READBACK_FAILED")
        foundation = response.data["data"]
        employee_api_by_no = {
            row["employeeNo"]: row for row in foundation["employees"]
        }
        account_api_by_no = {
            row["employeeNo"]: row for row in foundation["accountLinkEmployees"]
        }

        employee54 = Employee.objects.select_related(
            "user", "department_ref__company", "position_ref__company",
        ).get(pk=54)
        role32 = Role.objects.get(pk=32)
        permission43 = Permission.objects.get(pk=43)
        position27 = Position.objects.select_related("company", "department").get(pk=27)
        position39 = Position.objects.select_related("company", "department").get(pk=39)
        company = Company.objects.get(code="COMP001")
        department = Department.objects.get(code="RLXZB")

        service_source = inspect.getsource(OrganizationOperatingService._save_employee)
        repository_root = Path(settings.BASE_DIR).resolve().parent
        page_source = (
            repository_root / "frontend/src/meta/pages/AccessControlFoundationPage.vue"
        ).read_text(encoding="utf-8")
        dialog_source = (
            repository_root
            / "frontend/src/meta/components/OrganizationOperatingAdminDialog.vue"
        ).read_text(encoding="utf-8")

        counts_after = protected_counts()
        sha_after = database_sha256(database_path)
        emp054_api = employee_api_by_no.get("EMP054")
        emp054_account_api = account_api_by_no.get("EMP054")
        checks = {
            "databaseIdentityExact": database_path == EXPECTED_DATABASE,
            "databaseShaMatchesTaskBaseline": sha_before == TASK_BASELINE_SHA256,
            "databaseShaUnchangedByGate": sha_before == sha_after,
            "protectedCountsUnchangedByGate": counts_before == counts_after,
            "employeeArchiveCountIs124": counts_after["employee"] == 124,
            "foundationApiEmployeeCountIs124": len(foundation["employees"]) == 124,
            "employee54AcceptedTestEmployeeFact": (
                employee54.employee_no == "EMP054"
                and employee54.full_name == "李婷"
                and employee54.status == "active"
            ),
            "employee54HasNoFormalOrganization": (
                employee54.department_ref_id is None
                and employee54.position_ref_id is None
            ),
            "employee54HasNoUser": employee54.user_id is None,
            "employee54HasNoReportingRelation": not EmployeeReportingRelation.objects.filter(
                employee=employee54,
            ).exists(),
            "employee54VisibleInArchiveApi": bool(
                emp054_api and emp054_api["id"] == employee54.pk
            ),
            "employee54AvailableAsAccountAssociationCandidate": bool(
                emp054_account_api
            ),
            "employee54AccountEligibilitySeparatedFromCandidate": bool(
                emp054_account_api
                and not emp054_account_api["accountProvisioningEligible"]
                and emp054_account_api["accountProvisioningCode"]
                == "ACCOUNT_COMPANY_UNRESOLVED"
            ),
            "employeeSaveLookupUsesPrimaryKeyIdentity": ".filter(pk=row_id)" in service_source,
            "employeeSaveLookupNoLongerRequiresExistingFormalDepartment": (
                "pk=row_id, department_ref__company_id=user.company_id" not in service_source
            ),
            "employeeSaveRetainsCrossCompanyGuard": (
                "CROSS_COMPANY_WRITE_FORBIDDEN" in service_source
                and "EMPLOYEE_ORGANIZATION_CONFLICT" in service_source
            ),
            "companyComp001Preserved": company.is_active,
            "departmentRlxzbPreserved": (
                department.company_id == company.pk and department.is_active
            ),
            "position27Preserved": (
                position27.name == "人力经理"
                and position27.company_id == company.pk
                and position27.department_id == department.pk
            ),
            "position39Preserved": (
                position39.company_id == company.pk
                and position39.department_id == department.pk
                and position39.is_active
            ),
            "role32HasNoAssignment": not UserRoleScopeAssignment.objects.filter(
                role=role32,
            ).exists(),
            "permission43Preserved": (
                permission43.code == "system.organization.responsibility.manage"
                and permission43.module == "SYSTEM"
            ),
            "position39HasNoResponsibilityAssignment": not PositionResponsibility.objects.filter(
                position=position39,
            ).exists(),
            "formalManagerCandidateSourceHasRows": formal_employee_queryset(
                company_id=company.pk,
            ).count() > 0,
            "positionCandidatesRequireActiveFact": "row.isActive!==false" in dialog_source,
            "managerCandidatesRequireFormalEligibility": (
                "formalCandidateBaseEligible" in dialog_source
            ),
            "noPositionReasonIsExplicit": (
                "所选部门当前没有已启用正式岗位" in dialog_source
            ),
            "noManagerReasonIsExplicit": (
                "所选正式公司当前没有符合任职规则的主管候选" in dialog_source
            ),
            "employeeFormalAndOperatingCompanySeparated": (
                "员工正式公司" in dialog_source
                and "当前操作公司" in dialog_source
                and "未关联正式公司" in dialog_source
            ),
            "managerCandidatesRequireFormalCompany": (
                "employeeCompanyId.value?formalEmployeeOptions.value.filter" in dialog_source
                and "未建立正式公司关系时不生成主管候选" in dialog_source
            ),
            "employeeFilterFieldsComplete": all(
                f"field:'{field}'" in page_source for field in EMPLOYEE_FILTER_FIELDS
            ),
            "tabSwitchClearsStaleFilters": "watch(activeTab" in page_source
            and "clearFilters();clearTableSort();clearTableSelection()" in page_source,
            "tabSwitchTableEventsAreNonRecursive": (
                '@clear-sort="handleTableClearSort"' in page_source
                and '@clear-selection="handleTableClearSelection"' in page_source
                and "function handleTableClearSort(){handleSort()}" in page_source
                and "function handleTableClearSelection(){handleSelectionChange([])}" in page_source
                and '@clear-sort="clearSort"' not in page_source
                and '@clear-selection="clearSelection"' not in page_source
            ),
        }
        if not all(checks.values()):
            failed = sorted(key for key, passed in checks.items() if not passed)
            raise CommandError(
                "EMPLOYEE_IDENTITY_CANDIDATE_FILTER_REMEDIATION_FAILED:"
                + ",".join(failed)
            )

        result = {
            "contractVersion": "PCE-ORGANIZATION-STRUCTURE-DELIVERY-20261008-V2.1",
            "result": "PASS",
            "databasePath": str(database_path),
            "databaseSha256Before": sha_before,
            "databaseSha256After": sha_after,
            "protectedCountsBefore": counts_before,
            "protectedCountsAfter": counts_after,
            "supplementalBusinessRuling": {
                "allEmployeeRecordsAreDevelopmentTestData": True,
                "employee54AcceptedAsExistingTestEmployee": True,
                "realWorldIdentityProofRequired": False,
                "accountAssociationCandidateAllowed": bool(emp054_account_api),
                "accountEnablementPrerequisitesRemainEnforced": bool(
                    emp054_account_api
                    and not emp054_account_api["accountProvisioningEligible"]
                ),
            },
            "employee54": {
                "id": employee54.pk,
                "employeeNo": employee54.employee_no,
                "fullName": employee54.full_name,
                "status": employee54.status,
                "legacyDepartmentName": employee54.department_name,
                "legacyPositionName": employee54.position,
                "formalDepartmentId": employee54.department_ref_id,
                "formalPositionId": employee54.position_ref_id,
                "userId": employee54.user_id,
                "reportingRelationCount": EmployeeReportingRelation.objects.filter(
                    employee=employee54,
                ).count(),
                "accountAssociationCandidate": bool(emp054_account_api),
                "accountProvisioningCode": emp054_account_api[
                    "accountProvisioningCode"
                ],
            },
            "organizationFacts": {
                "company": {"id": company.pk, "code": company.code, "name": company.name},
                "department": {
                    "id": department.pk,
                    "code": department.code,
                    "name": department.name,
                },
                "position27": {
                    "id": position27.pk,
                    "code": position27.code,
                    "name": position27.name,
                },
                "position39": {
                    "id": position39.pk,
                    "code": position39.code,
                    "name": position39.name,
                    "responsibilityAssignmentCount": PositionResponsibility.objects.filter(
                        position=position39,
                    ).count(),
                },
                "formalManagerCandidateCount": formal_employee_queryset(
                    company_id=company.pk,
                ).count(),
            },
            "role32": {
                "id": role32.pk,
                "code": role32.code,
                "name": role32.name,
                "assignmentCount": UserRoleScopeAssignment.objects.filter(
                    role=role32,
                ).count(),
            },
            "permission43": {
                "id": permission43.pk,
                "code": permission43.code,
                "name": permission43.name,
                "module": permission43.module,
            },
            "checks": checks,
        }
        output = Path(options["output"]).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
