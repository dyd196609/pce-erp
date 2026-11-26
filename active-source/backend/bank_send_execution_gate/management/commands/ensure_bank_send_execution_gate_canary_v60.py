import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bank_send_execution_gate.canary import (
    bank_send_execution_gate_canary_facts,
    seed_bank_send_execution_gate_canary_pool,
)
from bank_send_execution_gate.services import (
    create_bank_send_execution_gate,
)
from bank_send_task.models import BankSendTask
from system.models import User


class Command(BaseCommand):
    help = (
        "Seed the isolated V60 execution-gate canary pool and create "
        "eight authorization gates without sending a bank message."
    )

    def handle(self, *args, **options):
        if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            raise CommandError("V60 canary pool requires isolated demo mode")
        tasks = list(
            BankSendTask.objects.filter(
                tenant_id=settings.PCE_CANARY_TENANT_ID,
                batch_id=settings.PCE_CANARY_BATCH_ID,
                status=BankSendTask.Status.READY_TO_SEND,
            ).order_by("task_no")[:8]
        )
        seed_bank_send_execution_gate_canary_pool(tasks)
        operator = User.objects.get(username="v552-operator")
        gate_numbers = []
        for task in tasks:
            outcome = create_bank_send_execution_gate(
                user=operator,
                task=task,
                idempotency_key=f"V60-GATE-{task.task_no}",
                expected_source_version=task.version,
                explicit_user_action=True,
            )
            gate_numbers.append(outcome["data"]["gateNo"])
        facts = bank_send_execution_gate_canary_facts()
        checks = {
            "normalPoolAtLeastEight": facts["normalPoolCount"] >= 8,
            "blockedPoolAtLeastSix": facts["blockedPoolCount"] >= 6,
            "reservePoolAtLeastTwenty": facts["reservePoolCount"] >= 20,
            "eightGatesCreated": facts["createdGateCount"] >= 8,
            "allBlockedScenariosRejected": facts["blockedGateCount"] == 6,
            "productionUserDataWrittenFalse":
                facts["productionUserDataWritten"] is False,
        }
        report = {
            "result": "passed" if all(checks.values()) else "failed",
            "version": "V1.14.2.8.4.7.60",
            "databasePath": str(settings.DATABASES["default"]["NAME"]),
            "currentStateSource": "server",
            "canaryPoolFacts": facts,
            "gateNos": gate_numbers,
            "checks": checks,
            "bankSendExecutionCount": 0,
            "bankMessageSentCount": 0,
            "paymentExecutionCount": 0,
            "productionUserDataWritten": False,
        }
        self.stdout.write(
            json.dumps(report, ensure_ascii=False, sort_keys=True)
        )
        if report["result"] != "passed":
            raise CommandError("V60 execution-gate canary facts failed")
