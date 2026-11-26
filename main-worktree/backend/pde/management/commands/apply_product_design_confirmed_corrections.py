from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from pde.acceptance_isolation import verify_acceptance_connections
from pde.product_design_service import apply_confirmed_source_corrections
from system.models import User


class Command(BaseCommand):
    help = "Apply the user-authorized installation-position and door-requirement corrections."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--idempotency-key", required=True)

    def handle(self, *args, **options):
        try:
            verify_acceptance_connections(settings.DATABASES)
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        user = User.objects.filter(
            username=options["username"], is_active=True,
        ).first()
        if not user:
            raise CommandError("The requested active user does not exist.")
        facts, replayed, result = apply_confirmed_source_corrections(
            user=user, idempotency_key=options["idempotency_key"],
        )
        self.stdout.write(self.style.SUCCESS(
            " ".join([
                f"database={Path(settings.DATABASES['default']['NAME']).resolve()}",
                f"order={facts['orderContext']['orderNo']}",
                f"replayed={str(replayed).lower()}",
                f"installationChanged={result.get('installationChangedCount', 0)}",
                f"doorClassified={result.get('doorClassifiedCount', 0)}",
                f"doorChanged={result.get('doorChangedCount', 0)}",
                f"doorUnchanged={result.get('doorUnchangedCount', 0)}",
                f"auditId={result.get('auditId')}",
            ])
        ))
