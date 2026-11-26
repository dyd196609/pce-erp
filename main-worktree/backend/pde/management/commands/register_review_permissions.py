import json

from django.core.management.base import BaseCommand

from pde.review_permission_catalog import ensure_review_permission_catalog


class Command(BaseCommand):
    help = "Idempotently register governed permissions for order and production-feasibility reviews."

    def handle(self, *args, **options):
        result = ensure_review_permission_catalog()
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
