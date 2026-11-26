import json

from django.core.management.base import BaseCommand

from pde.bom_version_permission_catalog import ensure_bom_version_permission_catalog


class Command(BaseCommand):
    help = "Idempotently register the governed BOMVersion review and release permissions."

    def handle(self, *args, **options):
        result = ensure_bom_version_permission_catalog()
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
