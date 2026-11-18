import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bank_send_preparation.repositories import BankSendPreparationRepository
from bank_send_task.models import BankSendTask
from bank_send_task.canary import bank_send_task_canary_facts
from bank_send_task.repositories import BankSendTaskRepository
from bank_send_task.services import (
    VERSION,
    bank_send_task_facts_for_rows,
    downstream_counts,
    evaluate_task_creation_gate,
    serialize_task,
)


class Command(BaseCommand):
    help = "Report persisted V59 bank-send task facts without writes."

    def handle(self, *args, **options):
        if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            raise CommandError("V59 report requires PCE_CANARY_DEMO_MODE")
        source_rows = list(
            BankSendPreparationRepository().queryset().filter(
                tenant_id=settings.PCE_CANARY_TENANT_ID
            )
        )
        sources = [
            {
                "id": row.pk,
                "prepareNo": row.prepare_no,
                "taskEligibility": evaluate_task_creation_gate(row),
                "targetExists": hasattr(row, "send_task"),
            }
            for row in source_rows
        ]
        rows = [
            serialize_task(row)
            for row in BankSendTaskRepository().queryset().filter(
                tenant_id=settings.PCE_CANARY_TENANT_ID
            )
        ]
        facts = bank_send_task_facts_for_rows(
            sources=sources,
            rows=rows,
            canary_pool_facts=bank_send_task_canary_facts(),
            tenant_id=settings.PCE_CANARY_TENANT_ID,
            batch_id=settings.PCE_CANARY_BATCH_ID,
        )
        report = {
            "result": "passed" if facts["passed"] else "blocked",
            "version": VERSION,
            "canonicalName": "银行发送任务",
            "sourceDocumentType": "bankSendPreparation",
            "currentStateSource": "server",
            **facts,
            "rows": rows,
            "downstreamCounts": downstream_counts(),
            "bankMessageCount": 0,
            "paymentExecutionCount": 0,
            "fundsDebitCount": 0,
            "bankTransactionCount": 0,
            "productionTenantObjectCount":
                BankSendTask.objects.exclude(
                    tenant_id=settings.PCE_CANARY_TENANT_ID
                ).count(),
            "productionUserDataWritten": False,
        }
        self.stdout.write(
            json.dumps(report, ensure_ascii=False, sort_keys=True)
        )
