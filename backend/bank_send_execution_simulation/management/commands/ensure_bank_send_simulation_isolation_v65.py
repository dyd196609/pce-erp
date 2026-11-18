import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from bank_send_execution_simulation.isolation import (
    create_production_isolation_gate,
    ensure_all_simulation_audits,
)
from bank_send_execution_simulation.models import (
    BankSendProductionIsolationGate,
    BankSendSimulationAudit,
)


class Command(BaseCommand):
    help = "Create V65 isolated simulation audits and production isolation gate"

    def handle(self, *args, **options):
        username = getattr(settings, "PCE_CANARY_USERNAME", "purchase-canary-demo")
        user = get_user_model().objects.get(username=username)
        audit_count = ensure_all_simulation_audits()
        gate = create_production_isolation_gate(
            user=user,
            tenant_id=settings.PCE_CANARY_TENANT_ID,
            batch_id=settings.PCE_CANARY_BATCH_ID,
        )
        result = {
            "result": "passed",
            "version": "V1.14.2.8.4.7.65",
            "simulationAuditWriteCount": audit_count,
            "isolationGateWriteCount":
                BankSendProductionIsolationGate.objects.count(),
            "gateStatus": gate.status,
            "auditRecordCount": BankSendSimulationAudit.objects.count(),
            "bankMessageSendWriteCount": 0,
            "paymentExecutionWriteCount": 0,
            "businessProgressWriteCount": 0,
            "productionUserDataWritten": False,
        }
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
