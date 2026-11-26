import hashlib
import json
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from pde.manufacturing_admission_confirmation_service import (
    ACTION_CODE,
    ManufacturingAdmissionConfirmationError,
    confirm_manufacturing_admission,
)
from system.models import User


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _rows(app_label, model_name, **filters):
    return list(
        apps.get_model(app_label, model_name)
        .objects.filter(**filters)
        .order_by("pk")
        .values()
    )


def _protected_facts():
    payload = {
        "salesOrder": _rows("sales", "SalesOrder", pk=3),
        "salesOrderItem": _rows("sales", "SalesOrderItem", pk=3),
        "manufacturingOutput": _rows("pde", "ProductManufacturingOutput", pk=1),
        "orderEngineeringInstance": _rows("pde", "OrderEngineeringInstance", pk=2),
        "engineeringBaseline": _rows("pde", "OrderEngineeringBaseline", pk=2),
        "bomVersion": _rows("pde", "BOMVersion", pk=3),
        "bomItems": _rows("pde", "BOMItem", bom_version_id=3),
        "routingVersion": _rows("pde", "RoutingVersion", pk=43),
        "routingSteps": _rows("pde", "RoutingStep", routing_version_id=43),
        "demand": _rows("planning", "Demand"),
        "planningRequirement": _rows("planning", "PlanningRequirement"),
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return payload, hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper()


def _table_counts():
    targets = (
        ("workflow_runtime", "WorkflowInstance"),
        ("workflow_runtime", "ApprovalTask"),
        ("workflow_runtime", "ApprovalDecision"),
        ("workflow_runtime", "BusinessStateTransition"),
        ("system", "OrganizationOperatingAuditRecord"),
        ("masterdata", "ExternalIdentity"),
        ("masterdata", "MasterDataWriteRequest"),
        ("planning", "Demand"),
        ("planning", "PlanningRequirement"),
    )
    return {
        f"{app_label}.{model_name}": apps.get_model(app_label, model_name).objects.count()
        for app_label, model_name in targets
    }


class Command(BaseCommand):
    help = (
        "Execute one formal ORDER_MANUFACTURING_ADMISSION confirmation without "
        "changing SalesOrder status or creating planning objects."
    )

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True)
        parser.add_argument("--order-id", type=int, required=True)
        parser.add_argument("--item-id", type=int, required=True)
        parser.add_argument("--output-id", type=int, required=True)
        parser.add_argument("--oei-id", type=int, required=True)
        parser.add_argument("--baseline-id", type=int, required=True)
        parser.add_argument("--bom-id", type=int, required=True)
        parser.add_argument("--routing-id", type=int, required=True)
        parser.add_argument("--reason", required=True)
        parser.add_argument("--idempotency-key", required=True)
        parser.add_argument("--expected-database-sha256", required=True)

    def handle(self, *args, **options):
        database_path = Path(str(connections["default"].settings_dict["NAME"])).resolve()
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
            raise CommandError("Active manufacturing admission actor not found.")
        protected_before, protected_hash_before = _protected_facts()
        counts_before = _table_counts()
        try:
            result = confirm_manufacturing_admission(
                order_id=options["order_id"],
                user=actor,
                reason=options["reason"],
                idempotency_key=options["idempotency_key"],
                item_id=options["item_id"],
                output_id=options["output_id"],
                oei_id=options["oei_id"],
                baseline_id=options["baseline_id"],
                bom_id=options["bom_id"],
                routing_id=options["routing_id"],
                action=ACTION_CODE,
            )
        except ManufacturingAdmissionConfirmationError as error:
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
