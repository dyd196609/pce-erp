import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bank_send_execution_gate.models import BankSendExecutionGate
from bank_send_request.canary import (
    bank_send_request_canary_facts,
    seed_bank_send_request_canary_pool,
)
from bank_send_request.services import create_bank_send_request
from system.models import User


class Command(BaseCommand):
    help = "Seed isolated V61 BankSendRequest 8/8/20 canary pool."

    def handle(self, *args, **options):
        if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            raise CommandError("V61 canary requires isolated demo mode")
        gates = list(BankSendExecutionGate.objects.filter(
            tenant_id=settings.PCE_CANARY_TENANT_ID,
            batch_id=settings.PCE_CANARY_BATCH_ID,
            status="ready_for_execution",
        ).order_by("gate_no")[:8])
        seed_bank_send_request_canary_pool(gates)
        operator = User.objects.get(username="v552-operator")
        request_numbers = []
        for gate in gates:
            outcome = create_bank_send_request(
                user=operator, gate=gate,
                idempotency_key=f"V61-REQUEST-{gate.gate_no}",
                expected_source_version=gate.version,
                explicit_user_action=True,
            )
            request_numbers.append(outcome["data"]["requestNo"])
        facts = bank_send_request_canary_facts()
        checks = {
            "normalPoolAtLeastEight": facts["normalPoolCount"] >= 8,
            "blockedPoolAtLeastEight": facts["blockedPoolCount"] >= 8,
            "reservePoolAtLeastTwenty": facts["reservePoolCount"] >= 20,
            "eightRequestsCreated": facts["createdRequestCount"] >= 8,
            "allBlockedScenariosRejected": facts["blockedRequestCount"] == 8,
            "productionUserDataWrittenFalse":
                facts["productionUserDataWritten"] is False,
        }
        report = {
            "result": "passed" if all(checks.values()) else "failed",
            "version": "V1.14.2.8.4.7.61",
            "databasePath": str(settings.DATABASES["default"]["NAME"]),
            "currentStateSource": "server",
            "canaryPoolFacts": facts,
            "requestNos": request_numbers,
            "checks": checks,
            "bankMessageSentCount": 0,
            "paymentExecutionCount": 0,
            "fundsDebitCount": 0,
            "productionUserDataWritten": False,
        }
        self.stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True))
        if report["result"] != "passed":
            raise CommandError("V61 canary facts failed")

