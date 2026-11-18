import json

from django.core.management.base import BaseCommand

from pde.engineering_document_version_permission_catalog import (
    ensure_engineering_document_version_permission_catalog,
)


class Command(BaseCommand):
    help = (
        "Idempotently register the EngineeringDocumentVersion formal-review permission "
        "and system-owned Workflow template; never grant personnel authority."
    )

    def handle(self, *args, **options):
        result = ensure_engineering_document_version_permission_catalog()
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
