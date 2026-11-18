import json
from django.core.management.base import BaseCommand
from purchase_canary.services import ensure_canary_group, verify_canary_group


class Command(BaseCommand):
    help = "Idempotently create or repair the durable purchase demonstration canary group."

    def handle(self, *args, **options):
        batch, changed_count = ensure_canary_group()
        result = verify_canary_group()
        result.update({"changedCount": changed_count, "idempotent": changed_count == 0})
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
