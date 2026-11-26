from django.conf import settings
from django.db import models

from reconciliation.models import PurchaseReconciliation
from workflow_runtime.state_models import BusinessStateManagedModel


class PurchaseInvoicePrepare(BusinessStateManagedModel):
    class Status(models.TextChoices):
        PREPARED = "prepared", "Prepared"
        DRAFT = "draft", "采购发票准备草稿"

    class InvoiceDataStatus(models.TextChoices):
        INCOMPLETE = "incomplete", "Incomplete"
        COMPLETE = "complete", "Complete"
        NOT_COLLECTED = "not_collected", "Not collected"

    prepare_no = models.CharField(max_length=80, unique=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    source_document_type = models.CharField(max_length=48, default="purchaseReconciliation")
    source_purchase_reconciliation = models.OneToOneField(
        PurchaseReconciliation,
        on_delete=models.PROTECT,
        related_name="purchase_invoice_prepare",
    )
    source_purchase_reconciliation_no = models.CharField(max_length=80)
    source_reconciliation_version = models.PositiveIntegerField()
    source_check_version = models.PositiveIntegerField()
    source_eligibility_hash = models.CharField(max_length=64)
    source_key = models.CharField(max_length=200, unique=True)
    tenant_id = models.CharField(max_length=64)
    company_id = models.BigIntegerField()
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    legal_entity_id = models.CharField(max_length=80)
    ledger_book_id = models.CharField(max_length=80)
    currency = models.CharField(max_length=8)
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.CharField(max_length=24)
    settlement_amount = models.DecimalField(max_digits=18, decimal_places=2)
    invoice_data_status = models.CharField(
        max_length=32,
        choices=InvoiceDataStatus.choices,
        default=InvoiceDataStatus.NOT_COLLECTED,
    )
    validation_status = models.CharField(max_length=32, default="not_validated")
    validation_result_code = models.CharField(max_length=80, default="not_validated")
    current_data_version = models.PositiveIntegerField(default=0)
    current_validation_version = models.PositiveIntegerField(default=0)
    validation_issue_count = models.PositiveIntegerField(default=0)
    prepared_at = models.DateTimeField(null=True, blank=True)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="prepared_purchase_invoice_prepares",
    )
    idempotency_key = models.CharField(max_length=120)
    number_reservation_id = models.BigIntegerField()
    transaction_id = models.CharField(max_length=80)
    audit_record_id = models.BigIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="purchase_invoice_prepares",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "purchase_invoice_prepares"
        permissions = [
            ("generate_purchase_invoice_prepare", "Can generate purchase invoice prepare"),
            ("edit_invoice_data", "Can edit purchase invoice data"),
            ("validate_invoice_data", "Can validate purchase invoice data"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_document_type="purchaseReconciliation"),
                name="pip_source_type_reconciliation",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["draft", "prepared"]),
                name="pip_status_valid",
            ),
        ]


class PurchaseInvoicePrepareSourceRelation(models.Model):
    purchase_invoice_prepare = models.ForeignKey(
        PurchaseInvoicePrepare,
        on_delete=models.PROTECT,
        related_name="source_relations",
    )
    source_type = models.CharField(max_length=48, default="purchaseReconciliation")
    source_id = models.BigIntegerField()
    source_no = models.CharField(max_length=80)
    source_version = models.PositiveIntegerField()
    relationship_type = models.CharField(max_length=40, default="generated_from")
    source_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "purchase_invoice_prepare_source_relations"
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_invoice_prepare", "source_type", "source_id"],
                name="uniq_pip_relation_target_source",
            ),
            models.UniqueConstraint(
                fields=["source_type", "source_id", "relationship_type"],
                name="uniq_pip_relation_source_generated",
            ),
            models.CheckConstraint(
                condition=models.Q(source_type="purchaseReconciliation"),
                name="pip_relation_source_reconciliation",
            ),
            models.CheckConstraint(
                condition=models.Q(relationship_type="generated_from"),
                name="pip_relation_generated_from",
            ),
        ]


class SupplierInvoiceAuthorityRecord(models.Model):
    tenant_id = models.CharField(max_length=64)
    company_id = models.BigIntegerField()
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    seller_tax_id = models.CharField(max_length=40)
    status = models.CharField(max_length=24, default="active")
    authority_version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "supplier_invoice_authority_records"
        constraints = [
            models.UniqueConstraint(fields=["tenant_id", "supplier_id"], name="uniq_supplier_invoice_authority"),
        ]


class LegalEntityInvoiceAuthorityRecord(models.Model):
    tenant_id = models.CharField(max_length=64)
    company_id = models.BigIntegerField()
    legal_entity_id = models.CharField(max_length=80)
    legal_entity_name = models.CharField(max_length=160)
    buyer_tax_id = models.CharField(max_length=40)
    ledger_book_id = models.CharField(max_length=80)
    currency = models.CharField(max_length=8)
    status = models.CharField(max_length=24, default="active")
    authority_version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "legal_entity_invoice_authority_records"
        constraints = [
            models.UniqueConstraint(fields=["tenant_id", "legal_entity_id"], name="uniq_legal_invoice_authority"),
        ]


class PurchaseInvoiceDataSnapshot(models.Model):
    purchase_invoice_prepare = models.ForeignKey(
        PurchaseInvoicePrepare, on_delete=models.PROTECT, related_name="invoice_data_snapshots"
    )
    data_version = models.PositiveIntegerField()
    data_source = models.CharField(max_length=32, default="manual_entry")
    invoice_type = models.CharField(max_length=40)
    invoice_code = models.CharField(max_length=40, blank=True)
    invoice_number = models.CharField(max_length=80)
    invoice_date = models.DateField(null=True, blank=True)
    seller_name = models.CharField(max_length=160)
    seller_tax_id = models.CharField(max_length=40)
    buyer_name = models.CharField(max_length=160)
    buyer_tax_id = models.CharField(max_length=40)
    currency = models.CharField(max_length=8)
    amount_excluding_tax = models.DecimalField(max_digits=18, decimal_places=2, null=True)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True)
    amount_including_tax = models.DecimalField(max_digits=18, decimal_places=2, null=True)
    invoice_identity_key = models.CharField(max_length=64, blank=True)
    data_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="purchase_invoice_data_snapshots"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "purchase_invoice_data_snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_invoice_prepare", "data_version"], name="uniq_pip_invoice_data_version"
            ),
            models.CheckConstraint(condition=models.Q(data_source="manual_entry"), name="pip_data_source_manual"),
        ]


class PurchaseInvoiceDataLine(models.Model):
    invoice_data_snapshot = models.ForeignKey(
        PurchaseInvoiceDataSnapshot, on_delete=models.PROTECT, related_name="lines"
    )
    line_no = models.PositiveIntegerField()
    item_code = models.CharField(max_length=80)
    item_name = models.CharField(max_length=160)
    specification = models.CharField(max_length=160, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.CharField(max_length=24)
    unit_price = models.DecimalField(max_digits=18, decimal_places=6)
    amount_excluding_tax = models.DecimalField(max_digits=18, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=9, decimal_places=6)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2)
    amount_including_tax = models.DecimalField(max_digits=18, decimal_places=2)
    line_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "purchase_invoice_data_lines"
        constraints = [
            models.UniqueConstraint(fields=["invoice_data_snapshot", "line_no"], name="uniq_pip_invoice_line_no"),
        ]


class PurchaseInvoiceValidationExecution(models.Model):
    purchase_invoice_prepare = models.ForeignKey(
        PurchaseInvoicePrepare, on_delete=models.PROTECT, related_name="validation_executions"
    )
    action_id = models.CharField(max_length=80, default="VALIDATE_PURCHASE_INVOICE_PREPARE")
    idempotency_key = models.CharField(max_length=120, unique=True)
    data_version = models.PositiveIntegerField()
    source_reconciliation_version = models.PositiveIntegerField()
    source_check_version = models.PositiveIntegerField()
    validation_policy_version = models.CharField(max_length=40, default="pip-invoice-validation-v1")
    status = models.CharField(max_length=24)
    result_code = models.CharField(max_length=80)
    input_hash = models.CharField(max_length=64)
    result_hash = models.CharField(max_length=64)
    issue_count = models.PositiveIntegerField(default=0)
    rule_count = models.PositiveIntegerField(default=0)
    passed_rule_count = models.PositiveIntegerField(default=0)
    blocking_rule_count = models.PositiveIntegerField(default=0)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="purchase_invoice_validations"
    )
    transaction_id = models.CharField(max_length=80)
    audit_record_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "purchase_invoice_validation_executions"


class PurchaseInvoiceValidationIssue(models.Model):
    validation_execution = models.ForeignKey(
        PurchaseInvoiceValidationExecution, on_delete=models.PROTECT, related_name="issues"
    )
    rule_code = models.CharField(max_length=100)
    dimension = models.CharField(max_length=80)
    line_no = models.PositiveIntegerField(null=True, blank=True)
    expected = models.CharField(max_length=240, blank=True)
    actual = models.CharField(max_length=240, blank=True)
    delta = models.CharField(max_length=80, blank=True)
    severity = models.CharField(max_length=24, default="error")
    blocking = models.BooleanField(default=True)
    message = models.CharField(max_length=320)
    rule_version = models.CharField(max_length=40, default="v1")

    class Meta:
        db_table = "purchase_invoice_validation_issues"
        constraints = [
            models.UniqueConstraint(
                fields=["validation_execution", "rule_code", "line_no"],
                name="uniq_pip_validation_issue_rule_line",
            ),
        ]


class PurchaseInvoiceIdentityClaim(models.Model):
    tenant_id = models.CharField(max_length=64)
    legal_entity_id = models.CharField(max_length=80)
    invoice_identity_key = models.CharField(max_length=64)
    purchase_invoice_prepare = models.ForeignKey(
        PurchaseInvoicePrepare, on_delete=models.PROTECT, related_name="invoice_identity_claims"
    )
    invoice_data_snapshot = models.ForeignKey(
        PurchaseInvoiceDataSnapshot, on_delete=models.PROTECT, related_name="identity_claims"
    )
    status = models.CharField(max_length=24, default="active")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "purchase_invoice_identity_claims"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "legal_entity_id", "invoice_identity_key"],
                condition=models.Q(status="active"),
                name="uniq_active_purchase_invoice_identity",
            ),
        ]
