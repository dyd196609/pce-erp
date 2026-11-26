from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from formal_payment_order.models import FormalPaymentOrder
from reconciliation.models import BusinessActionAuditRecord


class BankSendPreparationQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "status" in kwargs:
            raise ValidationError(
                "Bank send preparation status must use BusinessStateTransition"
            )
        return super().update(**kwargs)


class BankSendPreparation(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PREPARED = "prepared", "Prepared"

    prepare_no = models.CharField(max_length=80, unique=True)
    source_document_type = models.CharField(
        max_length=48,
        default="formalPaymentOrder",
        editable=False,
    )
    source_formal_payment_order = models.OneToOneField(
        FormalPaymentOrder,
        on_delete=models.PROTECT,
        related_name="bank_send_preparation",
    )
    source_formal_payment_order_no = models.CharField(max_length=80)
    source_formal_payment_order_version = models.PositiveIntegerField()
    source_freeze_hash = models.CharField(max_length=64)
    tenant_id = models.CharField(max_length=64)
    company_id = models.BigIntegerField()
    legal_entity_id = models.CharField(max_length=160)
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    currency = models.CharField(max_length=8)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    planned_execution_date = models.DateField()
    status = models.CharField(max_length=24, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    gate_hash = models.CharField(max_length=64)
    audit_record = models.ForeignKey(
        BusinessActionAuditRecord,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="bank_send_preparations",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_bank_send_preparations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = BankSendPreparationQuerySet.as_manager()

    class Meta:
        db_table = "bank_send_preparations"
        permissions = [
            ("view_bank_send_gate", "Can view bank send gate"),
            ("generate_bank_message_preview", "Can generate bank message preview"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_document_type="formalPaymentOrder"),
                name="bsp_source_type_formal_payment_order",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["draft", "prepared"]),
                name="bsp_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="bsp_amount_positive",
            ),
            models.CheckConstraint(
                condition=~models.Q(source_freeze_hash=""),
                name="bsp_source_freeze_hash_required",
            ),
            models.CheckConstraint(
                condition=~models.Q(gate_hash=""),
                name="bsp_gate_hash_required",
            ),
        ]

    def save(self, *args, **kwargs):
        if (
            not self.pk
            and self.status
            and not getattr(
                self,
                "_business_state_initialization_authorized",
                False,
            )
        ):
            raise ValidationError(
                "Bank send preparation initial status must use state initialization service"
            )
        if self.pk:
            persisted = type(self).objects.filter(pk=self.pk).values("status").first()
            if (
                persisted
                and persisted["status"] != self.status
                and not getattr(
                    self,
                    "_business_state_transition_authorized",
                    False,
                )
            ):
                raise ValidationError(
                    "Bank send preparation status must use BusinessStateTransition"
                )
        return super().save(*args, **kwargs)


class BankSendGate(models.Model):
    preparation = models.OneToOneField(
        BankSendPreparation,
        on_delete=models.PROTECT,
        related_name="send_gate",
    )
    source_status_passed = models.BooleanField(default=False)
    approval_passed = models.BooleanField(default=False)
    freeze_hash_passed = models.BooleanField(default=False)
    risk_review_passed = models.BooleanField(default=False)
    funds_available = models.BooleanField(default=False)
    bank_interface_available = models.BooleanField(default=False)
    signing_capability_ready = models.BooleanField(default=False)
    segregation_valid = models.BooleanField(default=False)
    eligible = models.BooleanField(default=False)
    blocking_reasons = models.JSONField(default=list)
    source_freeze_hash = models.CharField(max_length=64)
    current_freeze_hash = models.CharField(max_length=64)
    bank_interface_code = models.CharField(max_length=120, blank=True)
    bank_interface_status = models.CharField(max_length=40, blank=True)
    gate_hash = models.CharField(max_length=64, unique=True)
    evaluated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_send_gates"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Bank send gate is immutable")
        return super().save(*args, **kwargs)


class BankMessagePreview(models.Model):
    class Status(models.TextChoices):
        PREVIEW_ONLY = "preview_only", "Preview only"

    preparation = models.OneToOneField(
        BankSendPreparation,
        on_delete=models.PROTECT,
        related_name="message_preview",
    )
    preview_no = models.CharField(max_length=80, unique=True)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.PREVIEW_ONLY,
        editable=False,
    )
    message_type = models.CharField(
        max_length=48,
        default="payment_instruction_preview",
        editable=False,
    )
    sanitized_payload = models.JSONField(default=dict)
    payload_hash = models.CharField(max_length=64, unique=True)
    audit_record = models.ForeignKey(
        BusinessActionAuditRecord,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="bank_message_previews",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_bank_message_previews",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_message_previews"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status="preview_only"),
                name="bmp_preview_only_enforced",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not getattr(self, "_audit_binding_authorized", False):
            raise ValidationError("Bank message preview is immutable")
        if self.status != self.Status.PREVIEW_ONLY:
            raise ValidationError("Bank message preview status must remain preview_only")
        return super().save(*args, **kwargs)
