import json

from django.core.management.base import BaseCommand, CommandError

from system.employee_account_provisioning import (
    EmployeeAccountProvisioningError,
    provision_missing_management_accounts,
)
from system.models import User


class Command(BaseCommand):
    help = "Dry-run or provision missing employee accounts for active management positions."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True)
        parser.add_argument("--reason", required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        actor = User.objects.filter(username=options["actor"], is_active=True).first()
        if not actor:
            raise CommandError("Active actor not found")
        try:
            result = provision_missing_management_accounts(
                actor=actor, reason=options["reason"], apply=options["apply"],
            )
        except EmployeeAccountProvisioningError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
