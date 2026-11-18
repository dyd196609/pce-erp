from django.conf import settings
from django.db import models

from payment_order_draft.models import PaymentOrderDraft


class PaymentRiskReview(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEWING = "reviewing", "Reviewing"
        PASSED = "passed", "Passed"
        BLOCKED = "blocked", "Blocked"
        REJECTED = "rejected", "Rejected"

    review_no = models.CharField(max_length=80, unique=True)
    source_document_type = models.CharField(max_length=48, default="paymentOrderDraft")
    source_payment_order_draft = models.OneToOneField(
        PaymentOrderDraft,
        on_delete=models.PROTECT,
        related_name="payment_risk_review",
    )
    source_payment_order_draft_no = models.CharField(max_length=80)
    source_draft_version = models.PositiveIntegerField()
    source_draft_review_version = models.PositiveIntegerField()
    source_draft_hash = models.CharField(max_length=64)
    scenario_code = models.CharField(max_length=80, editable=False)
    tenant_id = models.CharField(max_length=64)
    company_id = models.BigIntegerField()
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    risk_result = models.CharField(max_length=24, default="not_reviewed")
    risk_level = models.CharField(max_length=24, default="unknown")
    review_version = models.PositiveIntegerField(default=0)
    issue_count = models.PositiveIntegerField(default=0)
    transaction_status = models.CharField(max_length=24, default="not_started")
    audit_status = models.CharField(max_length=24, default="not_started")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_payment_risk_reviews",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "payment_risk_reviews"
        permissions = [
            ("execute_payment_risk_review", "Can execute payment risk review"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_document_type="paymentOrderDraft"),
                name="prr_source_type_pod",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["draft", "reviewing", "passed", "blocked", "rejected"]),
                name="prr_status_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(scenario_code=""),
                name="prr_scenario_code_not_empty",
            ),
        ]


class RiskReviewExecution(models.Model):
    review = models.ForeignKey(
        PaymentRiskReview,
        on_delete=models.PROTECT,
        related_name="executions",
    )
    execution_id = models.CharField(max_length=80, unique=True)
    rule_version = models.CharField(max_length=64)
    review_version = models.PositiveIntegerField()
    passed_count = models.PositiveIntegerField(default=0)
    blocked_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    idempotency_key = models.CharField(max_length=120, unique=True)
    input_hash = models.CharField(max_length=64)
    result_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=24)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payment_risk_review_executions"
        constraints = [
            models.UniqueConstraint(
                fields=["review", "review_version"],
                name="uniq_prr_review_version",
            ),
        ]


class RiskIssue(models.Model):
    review = models.ForeignKey(
        PaymentRiskReview,
        on_delete=models.PROTECT,
        related_name="issues",
    )
    execution = models.ForeignKey(
        RiskReviewExecution,
        on_delete=models.PROTECT,
        related_name="issues",
    )
    risk_code = models.CharField(max_length=80)
    risk_level = models.CharField(max_length=24)
    description = models.CharField(max_length=240)
    expected = models.CharField(max_length=240)
    actual = models.CharField(max_length=240)

    class Meta:
        db_table = "payment_risk_review_issues"
        constraints = [
            models.UniqueConstraint(
                fields=["execution", "risk_code"],
                name="uniq_prr_execution_risk",
            ),
        ]


class RiskEvidenceSnapshot(models.Model):
    review = models.ForeignKey(
        PaymentRiskReview,
        on_delete=models.PROTECT,
        related_name="evidence_snapshots",
    )
    execution = models.OneToOneField(
        RiskReviewExecution,
        on_delete=models.PROTECT,
        related_name="evidence_snapshot",
    )
    evidence_version = models.PositiveIntegerField()
    funds_evidence = models.JSONField(default=dict)
    bank_evidence = models.JSONField(default=dict)
    supplier_evidence = models.JSONField(default=dict)
    duplicate_payment_evidence = models.JSONField(default=dict)
    segregation_evidence = models.JSONField(default=dict)
    source_draft_evidence = models.JSONField(default=dict)
    evidence_hash = models.CharField(max_length=64)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_risk_evidence_snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["review", "evidence_version"],
                name="uniq_prr_evidence_version",
            ),
        ]


class PaymentRiskReviewCanaryScenario(models.Model):
    batch_id = models.CharField(max_length=80)
    scenario_code = models.CharField(max_length=80)
    scenario_class = models.CharField(max_length=24, default="blocked")
    risk_code = models.CharField(max_length=80)
    risk_level = models.CharField(max_length=24, default="high")
    blocking_reasons = models.JSONField(default=list)
    eligible = models.BooleanField(default=False)
    formal_object_count = models.PositiveIntegerField(default=0)
    scenario_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "payment_risk_review_canary_scenarios"
        constraints = [
            models.UniqueConstraint(
                fields=["batch_id", "scenario_code"],
                name="uniq_prr_canary_scenario",
            ),
        ]
