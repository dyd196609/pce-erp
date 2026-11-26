import json
from django.core.management.base import BaseCommand, CommandError
from purchase_canary.services import verify_canary_group


class Command(BaseCommand):
    help = "Verify durable canary scenarios, module objects, relations and hashes without writing."

    def handle(self, *args, **options):
        result = verify_canary_group()
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
        if result["result"] != "passed":
            raise CommandError("purchase canary verification failed")
