import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from bank_send_preparation.models import BankMessagePreview, BankSendPreparation
from bank_send_preparation.services import (
    VERSION,
    create_bank_send_preparation,
    downstream_counts,
    serialize_preparation,
)
from formal_payment_order.models import FormalPaymentOrder


class Command(BaseCommand):
    help = "Create the isolated V58 bank-send preparation canary objects."

    def handle(self, *args, **options):
        if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            raise CommandError(
                "Bank-send preparation canary requires PCE_CANARY_DEMO_MODE"
            )
        actor, _ = get_user_model().objects.get_or_create(
            username="pce-v58-bank-send-preparer",
            defaults={
                "real_name": "V58银行发送准备金丝雀",
                "email": "v58-bank-send-preparer@example.invalid",
                "company_id": 1,
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        changed = False
        for field in ("is_active", "is_staff", "is_superuser"):
            if not getattr(actor, field):
                setattr(actor, field, True)
                changed = True
        if changed:
            actor.save(update_fields=["is_active", "is_staff", "is_superuser"])
        orders = list(
            FormalPaymentOrder.objects.filter(
                tenant_id=settings.PCE_CANARY_TENANT_ID,
                status="frozen_for_execution",
            ).order_by("order_no")
        )
        if len(orders) != 8:
            raise CommandError(
                f"Expected exactly 8 frozen formal payment orders, got {len(orders)}"
            )
        outcomes = [
            create_bank_send_preparation(
                user=actor,
                order=order,
                idempotency_key=f"V58-PREPARE-{order.order_no}",
            )
            for order in orders
        ]
        preparations = list(
            BankSendPreparation.objects.filter(
                tenant_id=settings.PCE_CANARY_TENANT_ID
            ).order_by("prepare_no")
        )
        serialized = [serialize_preparation(row) for row in preparations]
        if len(serialized) != 8:
            raise CommandError(
                f"Expected exactly 8 bank send preparations, got {len(serialized)}"
            )
        if not all(
            row["status"] == "prepared"
            and row["gate"]["eligible"]
            and row["stateMachineConsistent"]
            for row in serialized
        ):
            raise CommandError("V58 preparation facts are incomplete")
        result = {
            "result": "passed",
            "version": VERSION,
            "canonicalName": "银行发送准备",
            "sourceDocumentType": "formalPaymentOrder",
            "formalPaymentOrderCount": len(orders),
            "bankSendPreparationCount": len(serialized),
            "preparedCount": sum(
                row["status"] == "prepared" for row in serialized
            ),
            "eligibleCount": sum(row["gate"]["eligible"] for row in serialized),
            "previewCount": BankMessagePreview.objects.count(),
            "createdCount": sum(row["created"] for row in outcomes),
            "existingResultCount": sum(
                row["classification"] == "existing_result"
                for row in outcomes
            ),
            "downstreamCounts": downstream_counts(),
            "bankSendCreated": False,
            "paymentExecuted": False,
            "fundsDebited": False,
            "bankTransactionCreated": False,
            "productionUserDataWritten": False,
        }
        self.stdout.write(
            json.dumps(result, ensure_ascii=False, sort_keys=True)
        )

