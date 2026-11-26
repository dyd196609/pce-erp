import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bank_send_preparation.models import BankSendPreparation
from bank_send_preparation.services import generate_bank_message_preview
from bank_send_task.canary import (
    bank_send_task_canary_facts,
    seed_bank_send_task_canary_pool,
)
from bank_send_task.services import create_bank_send_task
from system.models import User


class Command(BaseCommand):
    help = "Seed isolated V59.1 BankSendTask Canary Pool and eight real tasks."

    def handle(self, *args, **options):
        if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            raise CommandError("V59.1 canary pool requires isolated demo mode")
        preparations = list(
            BankSendPreparation.objects.filter(
                tenant_id=settings.PCE_CANARY_TENANT_ID,
                status="prepared",
            )
            .select_related("source_formal_payment_order")
            .order_by("prepare_no")[:8]
        )
        seed_bank_send_task_canary_pool(preparations)
        operator = User.objects.get(username="v552-operator")
        results = []
        for preparation in preparations:
            if not hasattr(preparation, "message_preview"):
                generate_bank_message_preview(
                    user=operator,
                    preparation=preparation,
                    idempotency_key=f"V591-PREVIEW-{preparation.prepare_no}",
                    expected_version=preparation.version,
                    explicit_user_action=True,
                )
                preparation.refresh_from_db()
            outcome = create_bank_send_task(
                user=operator,
                preparation=preparation,
                idempotency_key=f"V591-TASK-{preparation.prepare_no}",
                expected_source_version=preparation.version,
                explicit_user_action=True,
            )
            results.append(outcome["data"]["taskNo"])
        facts = bank_send_task_canary_facts()
        conditions = {
            "normalPoolAtLeastEight": facts["normalPoolCount"] >= 8,
            "blockedPoolAtLeastFive": facts["blockedPoolCount"] >= 5,
            "reservePoolAtLeastTwenty": facts["reservePoolCount"] >= 20,
            "eightTasksCreated": facts["createdTaskCount"] >= 8,
            "allBlockedScenariosRejected": facts["blockedTaskCount"] == 5,
            "productionUserDataWrittenFalse":
                facts["productionUserDataWritten"] is False,
        }
        report = {
            "result": "passed" if all(conditions.values()) else "failed",
            "version": "V1.14.2.8.4.7.59.1",
            "currentStateSource": "server",
            "databasePath": str(settings.DATABASES["default"]["NAME"]),
            "canaryPoolFacts": facts,
            "taskNos": results,
            "conditions": conditions,
            "bankMessageSent": False,
            "paymentExecuted": False,
            "fundsDebited": False,
            "productionUserDataWritten": False,
        }
        self.stdout.write(
            json.dumps(report, ensure_ascii=False, sort_keys=True)
        )
        if report["result"] != "passed":
            raise CommandError("V59.1 canary pool facts are inconsistent")
