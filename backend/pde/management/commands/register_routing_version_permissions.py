import json

from django.core.management.base import BaseCommand

from pde.routing_version_permission_catalog import ensure_routing_version_permission_catalog


class Command(BaseCommand):
    help = (
        "Idempotently register governed RoutingVersion formal review/release permissions "
        "and the system-owned review Workflow template; never grant personnel authority."
    )

    def handle(self, *args, **options):
        result = ensure_routing_version_permission_catalog()
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
