from django.conf import settings
from django.db import models

from purchase_invoice_prepare.models import PurchaseInvoicePrepare
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
    PurchaseReconciliation,
)
from workflow_runtime.state_models import BusinessStateManagedModel


class PurchaseAccountsPayableDraft(BusinessStateManagedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "采购应付账款草稿"

    draft_no = models.CharField(max_length=80, unique=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    source_document_type = models.CharField(max_length=48, default="purchaseInvoicePrepare")
    source_purchase_invoice_prepare = models.OneToOneField(
        PurchaseInvoicePrepare,
        on_delete=models.PROTECT,
        related_name="purchase_accounts_payable_draft",
    )
    source_purchase_invoice_prepare_no = models.CharField(max_length=80)
    source_prepare_version = models.PositiveIntegerField()
    source_invoice_data_version = models.PositiveIntegerField()
    source_validation_version = models.PositiveIntegerField()
    source_purchase_reconciliation = models.ForeignKey(
        PurchaseReconciliation,
        on_delete=models.PROTECT,
        related_name="purchase_accounts_payable_drafts",
    )
    source_purchase_reconciliation_no = models.CharField(max_length=80)
    source_reconciliation_version = models.PositiveIntegerField()
    source_check_version = models.PositiveIntegerField()
    source_invoice_identity_key = models.CharField(max_length=64)
    source_eligibility_hash = models.CharField(max_length=64)
    source_key = models.CharField(max_length=200, unique=True)
    tenant_id = models.CharField(max_length=64)
    company_id = models.BigIntegerField()
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    seller_tax_id = models.CharField(max_length=40)
    legal_entity_id = models.CharField(max_length=80)
    legal_entity_name = models.CharField(max_length=160)
    buyer_tax_id = models.CharField(max_length=40)
    ledger_book_id = models.CharField(max_length=80)
    currency = models.CharField(max_length=8)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.CharField(max_length=24)
    amount_excluding_tax = models.DecimalField(max_digits=18, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2)
    amount_including_tax = models.DecimalField(max_digits=18, decimal_places=2)
    payable_amount = models.DecimalField(max_digits=18, decimal_places=2)
    invoice_type = models.CharField(max_length=40)
    invoice_code = models.CharField(max_length=40, blank=True)
    invoice_number = models.CharField(max_length=80)
    invoice_date = models.DateField()
    idempotency_key = models.CharField(max_length=120)
    number_reservation = models.ForeignKey(
        BusinessDocumentNumberReservation,
        on_delete=models.PROTECT,
        related_name="purchase_accounts_payable_drafts",
    )
    business_transaction = models.OneToOneField(
        BusinessActionTransaction,
        on_delete=models.PROTECT,
        related_name="purchase_accounts_payable_draft",
    )
    audit_record = models.OneToOneField(
        BusinessActionAuditRecord,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="purchase_accounts_payable_draft",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="purchase_accounts_payable_drafts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "purchase_accounts_payable_drafts"
        permissions = [
            (
                "generate_purchase_accounts_payable_draft",
                "Can generate purchase accounts payable draft",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_document_type="purchaseInvoicePrepare"),
                name="papd_source_type_invoice_prepare",
            ),
            models.CheckConstraint(
                condition=models.Q(status="draft"),
                name="papd_status_draft_only",
            ),
            models.CheckConstraint(
                condition=models.Q(payable_amount=models.F("amount_including_tax")),
                name="papd_payable_equals_including_tax",
            ),
            models.CheckConstraint(
                condition=models.Q(payable_amount__gt=0),
                name="papd_payable_positive",
            ),
        ]


class PurchaseAccountsPayableDraftSourceSnapshot(models.Model):
    purchase_accounts_payable_draft = models.OneToOneField(
        PurchaseAccountsPayableDraft,
        on_delete=models.PROTECT,
        related_name="source_snapshot",
    )
    source_purchase_invoice_prepare_id = models.BigIntegerField()
    source_purchase_invoice_prepare_no = models.CharField(max_length=80)
    source_prepare_version = models.PositiveIntegerField()
    source_invoice_data_snapshot_id = models.BigIntegerField()
    source_invoice_data_version = models.PositiveIntegerField()
    source_validation_execution_id = models.BigIntegerField()
    source_validation_version = models.PositiveIntegerField()
    source_invoice_identity_claim_id = models.BigIntegerField()
    source_invoice_identity_key = models.CharField(max_length=64)
    source_purchase_reconciliation_id = models.BigIntegerField()
    source_purchase_reconciliation_no = models.CharField(max_length=80)
    source_reconciliation_version = models.PositiveIntegerField()
    source_check_version = models.PositiveIntegerField()
    source_prepare_hash = models.CharField(max_length=64)
    source_invoice_data_hash = models.CharField(max_length=64)
    source_validation_result_hash = models.CharField(max_length=64)
    source_eligibility_hash = models.CharField(max_length=64)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "purchase_accounts_payable_draft_source_snapshots"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Purchase accounts payable draft source snapshot is immutable")
        return super().save(*args, **kwargs)


class PurchaseAccountsPayableDraftSourceRelation(models.Model):
    purchase_accounts_payable_draft = models.ForeignKey(
        PurchaseAccountsPayableDraft,
        on_delete=models.PROTECT,
        related_name="source_relations",
    )
    source_type = models.CharField(max_length=48, default="purchaseInvoicePrepare")
    source_id = models.BigIntegerField()
    source_no = models.CharField(max_length=80)
    source_version = models.PositiveIntegerField()
    relationship_type = models.CharField(max_length=40, default="generated_from")
    source_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "purchase_accounts_payable_draft_source_relations"
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_accounts_payable_draft", "source_type", "source_id"],
                name="uniq_papd_target_source",
            ),
            models.UniqueConstraint(
                fields=["source_type", "source_id", "relationship_type"],
                name="uniq_papd_source_generated",
            ),
            models.CheckConstraint(
                condition=models.Q(source_type="purchaseInvoicePrepare"),
                name="papd_relation_source_invoice_prepare",
            ),
            models.CheckConstraint(
                condition=models.Q(relationship_type="generated_from"),
                name="papd_relation_generated_from",
            ),
        ]
