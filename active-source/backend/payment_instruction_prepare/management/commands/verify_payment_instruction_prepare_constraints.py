import json

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from payment_instruction_prepare.models import (
    PaymentInstructionDataSnapshot,
    PaymentInstructionPrepare,
    PaymentInstructionPrepareSourceRelation,
    PaymentInstructionPrepareValidationIssue,
    PaymentInstructionPreview,
)
from payment_instruction_prepare.services import VERSION


def expect_integrity(label, callback):
    try:
        with transaction.atomic():
            callback()
    except IntegrityError:
        return {"case": label, "expected": "IntegrityError", "actual": "IntegrityError", "passed": True}
    return {"case": label, "expected": "IntegrityError", "actual": "no_error", "passed": False}


class Command(BaseCommand):
    help = "Exercise V49 database hard uniqueness constraints on an isolated clone"

    def handle(self, *args, **options):
        target = PaymentInstructionPrepare.objects.order_by("pk").first()
        if not target:
            raise CommandError("Missing V49 target")
        relation = target.source_relations.first()
        data = target.instruction_data_snapshots.first()
        preview = data.previews.first()
        validation = target.validation_executions.first()
        issue = validation.issues.first()
        if not issue:
            issue = PaymentInstructionPrepareValidationIssue.objects.create(
                validation_execution=validation,
                rule_code="constraint_probe_rule",
                dimension="constraint_probe",
                expected="unique", actual="unique",
                severity="warning", blocking=False,
                message="isolated clone uniqueness probe",
                source_field="validationExecution",
            )
        cases = []

        def duplicate_target():
            row = PaymentInstructionPrepare.objects.get(pk=target.pk)
            row.pk = None
            row._state.adding = True
            row.save(force_insert=True)

        cases.append(expect_integrity("unique_prepare_no_and_source_payment_request", duplicate_target))
        cases.append(expect_integrity(
            "unique_target_source_relation",
            lambda: PaymentInstructionPrepareSourceRelation.objects.create(
                payment_instruction_prepare=target,
                source_type=relation.source_type, source_id=relation.source_id,
                source_no=relation.source_no, source_version=relation.source_version,
                relationship_type=relation.relationship_type, source_hash=relation.source_hash,
            ),
        ))
        cases.append(expect_integrity(
            "unique_instruction_data_version",
            lambda: PaymentInstructionDataSnapshot.objects.create(
                payment_instruction_prepare=target,
                instruction_data_version=data.instruction_data_version,
                payer_bank_account_id=data.payer_bank_account_id,
                payer_account_no_masked=data.payer_account_no_masked,
                payee_bank_account_id=data.payee_bank_account_id,
                payee_account_no_masked=data.payee_account_no_masked,
                payment_route_id=data.payment_route_id,
                payment_route_code=data.payment_route_code,
                bank_interface_profile_id=data.bank_interface_profile_id,
                channel_code=data.channel_code, message_format=data.message_format,
                payment_method_code=data.payment_method_code,
                planned_execution_date=data.planned_execution_date,
                planned_execution_time=data.planned_execution_time,
                currency=data.currency, payment_amount=data.payment_amount,
                payment_purpose=data.payment_purpose,
                payment_summary=data.payment_summary, priority=data.priority,
                instruction_reference=data.instruction_reference,
                authority_evidence=data.authority_evidence, data_hash=data.data_hash,
                created_by=data.created_by,
            ),
        ))
        cases.append(expect_integrity(
            "unique_preview_version",
            lambda: PaymentInstructionPreview.objects.create(
                instruction_data_snapshot=data, preview_version=preview.preview_version,
                debtor_name=preview.debtor_name,
                debtor_account_masked=preview.debtor_account_masked,
                creditor_name=preview.creditor_name,
                creditor_account_masked=preview.creditor_account_masked,
                currency=preview.currency, amount=preview.amount,
                payment_method_code=preview.payment_method_code,
                route_code=preview.route_code, channel_code=preview.channel_code,
                execution_date=preview.execution_date,
                payment_reference=preview.payment_reference,
                purpose=preview.purpose, preview_hash=preview.preview_hash,
            ),
        ))
        cases.append(expect_integrity(
            "unique_validation_issue_rule",
            lambda: PaymentInstructionPrepareValidationIssue.objects.create(
                validation_execution=validation, rule_code=issue.rule_code,
                dimension=issue.dimension, expected=issue.expected,
                actual=issue.actual, severity=issue.severity,
                blocking=issue.blocking, message=issue.message,
                source_field=issue.source_field,
            ),
        ))
        if not all(row["passed"] for row in cases):
            raise CommandError(f"Constraint failure: {cases}")
        self.stdout.write(json.dumps({
            "result": "passed", "version": VERSION,
            "database": "isolated_regression_clone",
            "caseCount": len(cases), "cases": cases,
        }, ensure_ascii=False, indent=2))
