from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from purchase_canary.operation_data import (
    ensure_payable_check_operation_pool,
    payable_check_operation_facts,
    payable_check_operation_rows,
)


EXPECTED_DATABASE_NAME = "pce-canary-operation-data-v571-iab.sqlite3"


class Command(BaseCommand):
    help = "Create the isolated V57.1 payable-check operation data pool."

    def handle(self, *args, **options):
        if not getattr(settings, "PCE_V571_ISOLATED_ACCEPTANCE", False):
            raise CommandError("PCE_V571_ISOLATED_ACCEPTANCE is required")
        database = Path(connection.settings_dict["NAME"]).resolve()
        if database.name != EXPECTED_DATABASE_NAME:
            raise CommandError(
                f"V57.1 command only accepts {EXPECTED_DATABASE_NAME}"
            )
        batch = ensure_payable_check_operation_pool()
        rows = payable_check_operation_rows(batch)
        facts = payable_check_operation_facts(rows)
        if not facts["operationPoolConsistent"]:
            raise CommandError(f"Operation pool inconsistent: {facts}")
        self.stdout.write(
            self.style.SUCCESS(
                "V57.1 operation data ready: "
                f"pending={facts['pendingCheckCount']}, "
                f"checked={facts['checkedCount']}"
            )
        )
