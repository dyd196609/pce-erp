import json
from django.core.management.base import BaseCommand
from system.models import User
from masterdata.material_targeted_remediation_service import MaterialTargetedRemediationService


class Command(BaseCommand):
    help = "Execute the user-authorized Group 2 targeted material remediation."

    def handle(self, *args, **options):
        result = MaterialTargetedRemediationService.execute(admin=User.objects.get(username="admin"))
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
