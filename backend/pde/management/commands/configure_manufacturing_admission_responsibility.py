import hashlib
import json
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from pde.manufacturing_admission_responsibility_service import (
    ManufacturingAdmissionConfigurationError,
    configure_manufacturing_admission_responsibility,
)
from system.models import User


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _model_rows(app_label, model_name, **filters):
    model = apps.get_model(app_label, model_name)
    return list(model.objects.filter(**filters).order_by("pk").values())


def _protected_facts():
    payload = {
        "salesOrder": _model_rows("sales", "SalesOrder", pk=3),
        "salesOrderItem": _model_rows("sales", "SalesOrderItem", pk=3),
        "manufacturingOutput": _model_rows("pde", "ProductManufacturingOutput", pk=1),
        "bomVersion": _model_rows("pde", "BOMVersion", pk=3),
        "routingVersion": _model_rows("pde", "RoutingVersion", pk=43),
        "demand": _model_rows("planning", "Demand"),
        "planningRequirement": _model_rows("planning", "PlanningRequirement"),
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return payload, hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper()


def _table_counts():
    targets = (
        ("system", "Permission"),
        ("system", "Role"),
        ("system", "RolePermission"),
        ("system", "UserRoleScopeAssignment"),
        ("system", "Responsibility"),
        ("system", "PositionResponsibility"),
        ("system", "PositionWorkflowResponsibility"),
        ("workflow_runtime", "ProcessDefinition"),
        ("workflow_runtime", "WorkflowNodeDefinition"),
        ("system", "OrganizationOperatingAuditRecord"),
        ("masterdata", "ExternalIdentity"),
        ("masterdata", "MasterDataWriteRequest"),
    )
    return {
        f"{app_label}.{model_name}": apps.get_model(app_label, model_name).objects.count()
        for app_label, model_name in targets
    }


class Command(BaseCommand):
    help = (
        "Additively configure the designated Manufacturing Admission Confirmation "
        "responsibility without submitting, approving or confirming the sales order."
    )

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True)
        parser.add_argument("--order-no", required=True)
        parser.add_argument("--expected-order-id", type=int, required=True)
        parser.add_argument("--employee-no", required=True)
        parser.add_argument("--username", required=True)
        parser.add_argument("--company-code", required=True)
        parser.add_argument("--reason", required=True)
        parser.add_argument("--expected-database-sha256", required=True)

    def handle(self, *args, **options):
        database_name = connections["default"].settings_dict["NAME"]
        database_path = Path(str(database_name)).resolve()
        if not database_path.is_file():
            raise CommandError("Configured SQLite database does not exist.")
        before_hash = _hash_file(database_path)
        expected_hash = options["expected_database_sha256"].strip().upper()
        if before_hash != expected_hash:
            raise CommandError(
                f"DATABASE_SHA256_MISMATCH: expected {expected_hash}, actual {before_hash}"
            )
        actor = User.objects.filter(username=options["actor"], is_active=True).first()
        if not actor:
            raise CommandError("Active configuration actor not found.")

        protected_before, protected_hash_before = _protected_facts()
        counts_before = _table_counts()
        try:
            result = configure_manufacturing_admission_responsibility(
                actor=actor,
                order_no=options["order_no"],
                expected_order_id=options["expected_order_id"],
                employee_no=options["employee_no"],
                username=options["username"],
                company_code=options["company_code"],
                reason=options["reason"],
            )
        except ManufacturingAdmissionConfigurationError as error:
            raise CommandError(
                json.dumps(
                    {"code": error.code, "message": error.message, "details": error.details},
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
            ) from error

        protected_after, protected_hash_after = _protected_facts()
        if protected_after != protected_before:
            raise CommandError("PROTECTED_FACTS_CHANGED: protected business data changed.")
        counts_after = _table_counts()
        connections["default"].close()
        after_hash = _hash_file(database_path)
        payload = {
            **result,
            "database": {
                "path": str(database_path),
                "sha256Before": before_hash,
                "sha256After": after_hash,
                "changed": before_hash != after_hash,
            },
            "protectedFacts": {
                "sha256Before": protected_hash_before,
                "sha256After": protected_hash_after,
                "unchanged": protected_hash_before == protected_hash_after,
            },
            "tableCountsBefore": counts_before,
            "tableCountsAfter": counts_after,
            "tableCountDelta": {
                key: counts_after[key] - counts_before[key] for key in counts_before
            },
        }
        self.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))
