import json

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError

from pde.group3b_routing_formalization_service import Group3BRoutingFormalizationService
from pde.production_foundation_service import ProductionFoundationError
from system.models import User


class Command(BaseCommand):
    help = "Atomically formalize only the user-validated Group 3B routing source."

    def add_arguments(self, parser):
        parser.add_argument("--confirm-production-authorization", action="store_true")

    def handle(self, *args, **options):
        if not options["confirm_production_authorization"]:
            raise CommandError("EXPLICIT_PRODUCTION_AUTHORIZATION_CONFIRMATION_REQUIRED")
        try:
            result = Group3BRoutingFormalizationService.execute(
                admin=User.objects.get(username="admin", is_superuser=True, is_active=True),
                executor=User.objects.get(username="emd_emp047", is_active=True),
            )
        except ObjectDoesNotExist as exc:
            raise CommandError(f"EXECUTOR_CHAIN_REQUIRED: {exc}")
        except ProductionFoundationError as exc:
            raise CommandError(f"{exc.code}: {exc.message}")
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
