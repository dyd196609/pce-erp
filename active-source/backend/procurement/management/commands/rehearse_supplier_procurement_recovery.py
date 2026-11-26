import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from procurement.data_recovery_application_service import (
    DataRecoveryError, SupplierProcurementDataRecoveryService,
)


class Command(BaseCommand):
    help = "Preview or execute a governed Supplier/Procurement recovery against an isolated recovery DB."

    def add_arguments(self, parser):
        parser.add_argument("--ledger", required=True)
        parser.add_argument("--run-id", required=True)
        parser.add_argument("--output", required=True)
        mode = parser.add_mutually_exclusive_group(required=False)
        mode.add_argument("--preview", action="store_true")
        mode.add_argument("--execute", action="store_true")
        mode.add_argument("--phase", choices=("precheck", "dry-run", "commit"))
        parser.add_argument("--actor-id", type=int)
        parser.add_argument("--target-kind", choices=("production", "isolated-production-like"))
        parser.add_argument("--authorization-id")
        parser.add_argument("--changeset")
        parser.add_argument("--expected-database-sha")
        parser.add_argument("--expected-ledger-sha")
        parser.add_argument("--expected-changeset-sha")
        parser.add_argument("--backup")
        parser.add_argument("--expected-backup-sha")
        parser.add_argument("--quiescence-proof")
        parser.add_argument("--expected-quiescence-proof-sha")
        parser.add_argument("--dry-run-proof")
        parser.add_argument("--expected-dry-run-proof-sha")

    def handle(self, *args, **options):
        try:
            if options.get("phase"):
                actor = None
                if options["phase"] == "commit":
                    if not options.get("actor_id"):
                        raise CommandError("--actor-id is required for commit")
                    actor = get_user_model().objects.get(pk=options["actor_id"], is_active=True)
                result = SupplierProcurementDataRecoveryService.production_phase(
                    phase=options["phase"], target_kind=options.get("target_kind"),
                    ledger_path=options["ledger"], changeset_path=options.get("changeset"),
                    run_id=options["run_id"], authorization_id=options.get("authorization_id"),
                    expected_database_sha=options.get("expected_database_sha"),
                    expected_ledger_sha=options.get("expected_ledger_sha"),
                    expected_changeset_sha=options.get("expected_changeset_sha"), actor=actor,
                    backup_path=options.get("backup"),
                    expected_backup_sha=options.get("expected_backup_sha"),
                    quiescence_proof_path=options.get("quiescence_proof"),
                    expected_quiescence_proof_sha=options.get("expected_quiescence_proof_sha"),
                    dry_run_proof_path=options.get("dry_run_proof"),
                    expected_dry_run_proof_sha=options.get("expected_dry_run_proof_sha"),
                )
            elif options.get("preview"):
                result = SupplierProcurementDataRecoveryService.preview(
                    options["ledger"], options["run_id"],
                    source_snapshot=options.get("backup"),
                    expected_source_snapshot_sha=options.get("expected_backup_sha"),
                )
            elif options.get("execute"):
                if not options.get("actor_id"):
                    raise CommandError("--actor-id is required for execution")
                actor = get_user_model().objects.get(pk=options["actor_id"], is_active=True)
                result = SupplierProcurementDataRecoveryService.execute(
                    options["ledger"], options["run_id"], actor,
                    source_snapshot=options.get("backup"),
                    expected_source_snapshot_sha=options.get("expected_backup_sha"),
                )
            else:
                raise CommandError("one of --preview, --execute or --phase is required")
        except (DataRecoveryError, OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        output = Path(options["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        self.stdout.write(json.dumps(result.get("counts", result), ensure_ascii=False, default=str))
