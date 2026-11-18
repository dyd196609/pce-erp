import json

from django.core.management.base import BaseCommand, CommandError

from pde.order_review_signoff_readiness import SignoffReadinessError, apply, readback


class Command(BaseCommand):
    help = "Preview or apply the approved exact-object sign-off readiness for order review #1."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--actor", default="admin")

    def handle(self, *args, **options):
        try:
            result = apply(actor_username=options["actor"]) if options["apply"] else readback()
        except SignoffReadinessError as exc:
            raise CommandError(f"{exc.code}: {exc.message}") from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
