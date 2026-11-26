import hashlib
import inspect
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from rest_framework.test import APIRequestFactory, force_authenticate

from pfm.formal_employee import (
    account_link_employee_queryset,
    employee_archive_queryset,
    formal_employee_queryset,
)
from pfm.management.commands.restore_employee_archive_20261008 import EXPECTED_DATABASE
from pfm.models import Employee
from system.access_control_views import AccessControlFoundationView
from system.models import (
    OrganizationOperatingAuditRecord,
    Permission,
    Role,
    User,
    UserRoleScopeAssignment,
)


TARGET_EMPLOYEE_NOS = {"EMP054", "EMP073"}
EXPECTED_PREVIOUS_CANDIDATE_NOS = {"EMP006", "EMP072", "EMP102", "EMP103"}


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
        "scope": UserRoleScopeAssignment.objects.count(),
        "audit": OrganizationOperatingAuditRecord.objects.count(),
    }


class Command(BaseCommand):
    help = "Read-only strict gate for account-link employee visibility and SAVE_USER eligibility separation."

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

        archive_queryset = employee_archive_queryset(
            Employee.objects.select_related(
                "user", "department_ref__company", "position_ref__company",
                "position_ref__department",
            )
        )
        account_link_rows = list(
            account_link_employee_queryset(archive_queryset).order_by("employee_no", "pk")
        )
        account_link_ids = {row.pk for row in account_link_rows}
        account_link_nos = {row.employee_no for row in account_link_rows}
        formal_unlinked_rows = list(
            formal_employee_queryset(archive_queryset)
            .filter(user__isnull=True)
            .order_by("employee_no", "pk")
        )
        formal_unlinked_nos = {row.employee_no for row in formal_unlinked_rows}

        request = APIRequestFactory().get("/api/access-control/foundation/")
        force_authenticate(request, user=actor)
        response = AccessControlFoundationView.as_view()(request)
        if response.status_code != 200 or not response.data.get("success"):
            raise CommandError("FOUNDATION_API_READBACK_FAILED")
        foundation = response.data["data"]
        api_rows = foundation["accountLinkEmployees"]
        api_rows_by_no = {row["employeeNo"]: row for row in api_rows}
        api_ids = {row["id"] for row in api_rows}
        target_rows = {
            employee_no: api_rows_by_no.get(employee_no)
            for employee_no in sorted(TARGET_EMPLOYEE_NOS)
        }
        previous_candidate_rows = [
            {
                "employeeId": row.pk,
                "employeeNo": row.employee_no,
                "fullName": row.full_name,
                "department": row.department_ref.name,
                "position": row.position_ref.name,
                "user": None,
            }
            for row in formal_unlinked_rows
        ]

        linked_employee_ids = set(
            Employee.objects.exclude(user_id__isnull=True).values_list("pk", flat=True)
        )
        inactive_employee_ids = set(
            Employee.objects.exclude(status="active").values_list("pk", flat=True)
        )
        source = inspect.getsource(account_link_employee_queryset)

        counts_after = protected_counts()
        sha_after = database_sha256(database_path)
        checks = {
            "employeeCountIs124": counts_after["employee"] == 124,
            "userCountIs31": counts_after["user"] == 31,
            "accountLinkQueryUsesArchive": "employee_archive_queryset" in source,
            "accountLinkQueryDoesNotUseFormalEmployee": "formal_employee_queryset" not in source,
            "accountLinkQueryMatchesRule": account_link_ids == set(
                Employee.objects.filter(status="active", user__isnull=True)
                .values_list("pk", flat=True)
            ),
            "accountLinkCandidateCountIs91": len(account_link_rows) == 91,
            "apiMatchesAccountLinkQuery": api_ids == account_link_ids,
            "foundationArchiveCountIs124": len(foundation["employees"]) == 124,
            "targetsVisible": TARGET_EMPLOYEE_NOS <= account_link_nos,
            "targetsNotFormalBusinessCandidates": not (
                TARGET_EMPLOYEE_NOS & formal_unlinked_nos
            ),
            "previousFourCandidatesPreserved": (
                EXPECTED_PREVIOUS_CANDIDATE_NOS == formal_unlinked_nos
                and EXPECTED_PREVIOUS_CANDIDATE_NOS <= account_link_nos
            ),
            "linkedEmployeesExcluded": not (linked_employee_ids & account_link_ids),
            "inactiveEmployeesExcluded": not (inactive_employee_ids & account_link_ids),
            "emp054VisibleButSaveBlocked": bool(
                target_rows["EMP054"]
                and not target_rows["EMP054"]["organizationComplete"]
                and not target_rows["EMP054"]["accountProvisioningEligible"]
                and target_rows["EMP054"]["accountProvisioningCode"]
                == "ACCOUNT_COMPANY_UNRESOLVED"
            ),
            "emp073VisibleAndSaveContractAllows": bool(
                target_rows["EMP073"]
                and not target_rows["EMP073"]["organizationComplete"]
                and target_rows["EMP073"]["accountProvisioningEligible"]
                and target_rows["EMP073"]["accountProvisioningCode"]
                == "ACCOUNT_PROVISIONING_READY"
            ),
            "protectedCountsUnchanged": counts_before == counts_after,
            "databaseShaUnchanged": sha_before == sha_after,
        }
        if not all(checks.values()):
            failed = sorted(key for key, passed in checks.items() if not passed)
            raise CommandError(f"ACCOUNT_EMPLOYEE_SELECTION_SCOPE_FAILED:{','.join(failed)}")

        result = {
            "contractVersion": "PCE-ACCOUNT-EMPLOYEE-SELECTION-SCOPE-20261008-V1",
            "result": "PASS",
            "databasePath": str(database_path),
            "databaseSha256Before": sha_before,
            "databaseSha256After": sha_after,
            "protectedCountsBefore": counts_before,
            "protectedCountsAfter": counts_after,
            "employeeArchiveCount": counts_after["employee"],
            "userCount": counts_after["user"],
            "accountLinkCandidateCount": len(account_link_rows),
            "accountLinkRule": "Employee Archive + active + User is null",
            "previousFourCandidateSourceRule": (
                "formal_employee_queryset + User is null = active + complete active "
                "Department/Position/Company chain + no User"
            ),
            "previousFourCandidates": previous_candidate_rows,
            "targetReadback": target_rows,
            "checks": checks,
        }
        output = Path(options["output"]).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))

