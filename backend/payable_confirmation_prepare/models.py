from django.conf import settings
from django.db import models

from purchase_accounts_payable_draft.models import PurchaseAccountsPayableDraft
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
)
from workflow_runtime.state_models import BusinessStateManagedModel


class PayableConfirmationPrepare(BusinessStateManagedModel):
    class Status(models.TextChoices):
        PREPARED = "prepared", "已准备"

    prepare_no = models.CharField(max_length=80, unique=True)
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.PREPARED
    )
    source_document_type = models.CharField(
        max_length=48, default="purchaseAccountsPayableDraft"
    )
    source_purchase_accounts_payable_draft = models.OneToOneField(
        PurchaseAccountsPayableDraft,
        on_delete=models.PROTECT,
        related_name="payable_confirmation_prepare",
    )
    source_draft_no = models.CharField(max_length=80)
    source_draft_version = models.PositiveIntegerField()
    source_key = models.CharField(max_length=200, unique=True)
    source_snapshot_hash = models.CharField(max_length=64)
    tenant_id = models.CharField(max_length=64)
    company_id = models.BigIntegerField()
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    legal_entity_id = models.CharField(max_length=80)
    legal_entity_name = models.CharField(max_length=160)
    ledger_book_id = models.CharField(max_length=80)
    currency = models.CharField(max_length=8)
    amount_excluding_tax = models.DecimalField(max_digits=18, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2)
    payable_amount = models.DecimalField(max_digits=18, decimal_places=2)
    accounting_data_version = models.PositiveIntegerField(default=1)
    validation_version = models.PositiveIntegerField(default=1)
    validation_status = models.CharField(max_length=24, default="passed")
    validation_result_code = models.CharField(
        max_length=64, default="PCP_VALIDATED"
    )
    validation_issue_count = models.PositiveIntegerField(default=0)
    payment_terms_code = models.CharField(max_length=48)
    payment_terms_days = models.PositiveIntegerField()
    due_date = models.DateField()
    accounting_date = models.DateField()
    accounting_period = models.CharField(max_length=7)
    debit_total = models.DecimalField(max_digits=18, decimal_places=2)
    credit_total = models.DecimalField(max_digits=18, decimal_places=2)
    idempotency_key = models.CharField(max_length=120)
    number_reservation = models.ForeignKey(
        BusinessDocumentNumberReservation,
        on_delete=models.PROTECT,
        related_name="payable_confirmation_prepares",
    )
    business_transaction = models.OneToOneField(
        BusinessActionTransaction,
        on_delete=models.PROTECT,
        related_name="payable_confirmation_prepare",
    )
    audit_record = models.OneToOneField(
        BusinessActionAuditRecord,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payable_confirmation_prepare",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payable_confirmation_prepares",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "payable_confirmation_prepares"
        permissions = [
            (
                "generate_payable_confirmation_prepare",
                "Can generate payable confirmation prepare",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    source_document_type="purchaseAccountsPayableDraft"
                ),
                name="pcp_source_type_ap_draft",
            ),
            models.CheckConstraint(
                condition=models.Q(status="prepared"),
                name="pcp_status_prepared_only",
            ),
            models.CheckConstraint(
                condition=models.Q(validation_status="passed"),
                name="pcp_validation_passed",
            ),
            models.CheckConstraint(
                condition=models.Q(validation_issue_count=0),
                name="pcp_zero_validation_issues",
            ),
            models.CheckConstraint(
                condition=models.Q(debit_total=models.F("credit_total")),
                name="pcp_debit_credit_balanced",
            ),
            models.CheckConstraint(
                condition=models.Q(payable_amount__gt=0),
                name="pcp_payable_positive",
            ),
        ]


class PayableConfirmationAccountingSnapshot(models.Model):
    payable_confirmation_prepare = models.OneToOneField(
        PayableConfirmationPrepare,
        on_delete=models.PROTECT,
        related_name="accounting_snapshot",
    )
    version = models.PositiveIntegerField(default=1)
    accounts_payable_account = models.CharField(max_length=80)
    input_tax_account = models.CharField(max_length=80)
    counterparty_account = models.CharField(max_length=80)
    supplier_auxiliary_id = models.CharField(max_length=80)
    department_id = models.CharField(max_length=80)
    cost_center_id = models.CharField(max_length=80)
    project_id = models.CharField(max_length=80)
    payment_terms_code = models.CharField(max_length=48)
    payment_terms_days = models.PositiveIntegerField()
    due_date = models.DateField()
    accounting_date = models.DateField()
    accounting_period = models.CharField(max_length=7)
    period_status = models.CharField(max_length=24)
    debit_total = models.DecimalField(max_digits=18, decimal_places=2)
    credit_total = models.DecimalField(max_digits=18, decimal_places=2)
    source_payload_hash = models.CharField(max_length=64)
    snapshot_hash = models.CharField(max_length=64)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payable_confirmation_accounting_snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["payable_confirmation_prepare", "version"],
                name="uniq_pcp_accounting_version",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Payable confirmation accounting snapshot is immutable")
        return super().save(*args, **kwargs)


class PayableConfirmationValidationExecution(models.Model):
    payable_confirmation_prepare = models.ForeignKey(
        PayableConfirmationPrepare,
        on_delete=models.PROTECT,
        related_name="validation_executions",
    )
    validation_version = models.PositiveIntegerField()
    status = models.CharField(max_length=24)
    result_code = models.CharField(max_length=64)
    issue_count = models.PositiveIntegerField(default=0)
    rule_set_version = models.CharField(max_length=48)
    input_hash = models.CharField(max_length=64)
    result_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payable_confirmation_validation_executions"
        constraints = [
            models.UniqueConstraint(
                fields=["payable_confirmation_prepare", "validation_version"],
                name="uniq_pcp_validation_version",
            ),
        ]


class PayableConfirmationValidationIssue(models.Model):
    execution = models.ForeignKey(
        PayableConfirmationValidationExecution,
        on_delete=models.PROTECT,
        related_name="issues",
    )
    rule_code = models.CharField(max_length=80)
    field_name = models.CharField(max_length=80)
    severity = models.CharField(max_length=24, default="error")
    message = models.CharField(max_length=240)
    actual_value = models.CharField(max_length=240, blank=True)
    expected_value = models.CharField(max_length=240, blank=True)

    class Meta:
        db_table = "payable_confirmation_validation_issues"


class PayableConfirmationPrepareSourceRelation(models.Model):
    payable_confirmation_prepare = models.ForeignKey(
        PayableConfirmationPrepare,
        on_delete=models.PROTECT,
        related_name="source_relations",
    )
    source_type = models.CharField(
        max_length=48, default="purchaseAccountsPayableDraft"
    )
    source_id = models.BigIntegerField()
    source_no = models.CharField(max_length=80)
    source_version = models.PositiveIntegerField()
    relationship_type = models.CharField(max_length=40, default="generated_from")
    source_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payable_confirmation_prepare_source_relations"
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_id", "relationship_type"],
                name="uniq_pcp_source_generated",
            ),
            models.UniqueConstraint(
                fields=["payable_confirmation_prepare", "source_type", "source_id"],
                name="uniq_pcp_target_source",
            ),
        ]


class PayableConfirmationCanaryScenario(models.Model):
    batch_id = models.CharField(max_length=80)
    scenario_code = models.CharField(max_length=80)
    scenario_class = models.CharField(max_length=32, default="blocked")
    scenario_role = models.CharField(max_length=80)
    blocking_module = models.CharField(max_length=80)
    blocking_rule_code = models.CharField(max_length=80)
    blocking_reason = models.CharField(max_length=240)
    current_last_valid_object_no = models.CharField(max_length=80, blank=True)
    formal_object_count = models.PositiveIntegerField(default=0)
    next_step_allowed = models.BooleanField(default=False)
    scenario_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "payable_confirmation_canary_scenarios"
        constraints = [
            models.UniqueConstraint(
                fields=["batch_id", "scenario_code"],
                name="uniq_pcp_canary_scenario",
            )
        ]
