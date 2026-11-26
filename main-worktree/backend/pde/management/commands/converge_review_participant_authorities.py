import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from pde.acceptance_isolation import verify_acceptance_connections
from pde.review_permission_catalog import converge_active_review_participant_roles
from system.models import User


class Command(BaseCommand):
    help = "Converge active review object grants into additive governed participant-role assignments."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True)
        parser.add_argument("--reason", required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if not options["apply"]:
            raise CommandError("APPLY_FLAG_REQUIRED")
        isolation = verify_acceptance_connections(settings.DATABASES)
        actor = User.objects.filter(username=options["actor"], is_active=True).first()
        if actor is None or not actor.is_superuser:
            raise CommandError("ACTIVE_SUPERUSER_ACTOR_REQUIRED")
        reason = str(options["reason"] or "").strip()
        if len(reason) < 2:
            raise CommandError("REASON_REQUIRED")
        result = converge_active_review_participant_roles(actor=actor, reason=reason)
        self.stdout.write(json.dumps({"isolation": isolation, "result": result}, ensure_ascii=False, sort_keys=True))
