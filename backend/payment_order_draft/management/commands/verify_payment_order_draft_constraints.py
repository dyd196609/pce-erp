import json

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from payment_order_draft.models import (
    PaymentOrderDraft,
    PaymentOrderDraftAuthoritySnapshot,
    PaymentOrderDraftCreationPreview,
    PaymentOrderDraftDataSnapshot,
    PaymentOrderDraftReviewExecution,
    PaymentOrderDraftReviewIssue,
    PaymentOrderDraftSourceRelation,
)
from payment_order_draft.services import GENERATE_ACTION, recover_action_result
from workflow_runtime.state_transitions import create_business_object_with_initial_state


class Command(BaseCommand):
    help = "Verify V51 database constraints and committed idempotency on an isolated clone"

    def handle(self, *args, **options):
        original = PaymentOrderDraft.objects.order_by("pk").first()
        if not original:
            raise CommandError("Missing V51 draft fixture")
        values = {}
        for field in PaymentOrderDraft._meta.concrete_fields:
            if field.primary_key or field.auto_created:
                continue
            values[field.attname] = getattr(original, field.attname)
        values.pop("status", None)
        unique_constraint_triggered = False
        try:
            with transaction.atomic():
                create_business_object_with_initial_state(
                    model=PaymentOrderDraft,
                    initial_state="created",
                    **values,
                )
        except IntegrityError:
            unique_constraint_triggered = True
        if not unique_constraint_triggered:
            raise CommandError("Database unique constraint did not trigger")
        recovered = recover_action_result(GENERATE_ACTION, original.idempotency_key)
        if recovered["classification"] != "existing_result":
            raise CommandError("Committed idempotency result was not recovered")
        constraints = {
            constraint.name
            for model in [
                PaymentOrderDraft,
                PaymentOrderDraftAuthoritySnapshot,
                PaymentOrderDraftCreationPreview,
                PaymentOrderDraftDataSnapshot,
                PaymentOrderDraftReviewExecution,
                PaymentOrderDraftReviewIssue,
                PaymentOrderDraftSourceRelation,
            ]
            for constraint in model._meta.constraints
        }
        output = {
            "result": "passed",
            "version": "V1.14.2.8.4.7.51",
            "databaseUniqueConstraintTriggered": unique_constraint_triggered,
            "committedIdempotencyRecovered": True,
            "constraintNames": sorted(constraints),
            "sqliteConcurrencyStatement": (
                "SQLite safety relies on atomic transactions, hard unique constraints, "
                "optimistic versions and persistent source locks; it is not described as "
                "a full row-lock database."
            ),
        }
        self.stdout.write(json.dumps(output, ensure_ascii=False, indent=2))
