import json
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from purchase_canary.catalog import BATCH_ID
from purchase_canary.models import PurchaseCanaryBatch


class Command(BaseCommand):
    help = "Explicitly remove only the durable demonstration batch. Never called by validation runners."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("reset requires --confirm")
        deleted, detail = PurchaseCanaryBatch.objects.filter(batch_id=BATCH_ID).delete()
        self.stdout.write(json.dumps({"result": "reset", "batchId": BATCH_ID, "deleted": deleted, "detail": detail}, sort_keys=True))
