"""Persistent completion attempts. A generation is not a parallel approval."""
from django.conf import settings
from django.db import models
from workflow_runtime.state_models import BusinessStateManagedModel


class OperationCompletionGeneration(BusinessStateManagedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "待生产跟单员审核"
        APPROVED = "approved", "工序完工已生效"
        SUPERSEDED = "superseded", "因生产事实变化撤回待审"
        REJECTED = "rejected", "申请未通过"

    task = models.ForeignKey("planning.ProductionWorkshopTask", on_delete=models.PROTECT, related_name="completion_generations")
    company_id = models.PositiveBigIntegerField()
    sequence = models.PositiveIntegerField()
    protocol = models.CharField(max_length=16, choices=[("V2_BRIDGE", "原待审申请桥接"), ("V3", "新版完工申请")])
    status = models.CharField(max_length=24, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="operation_completion_generations")
    preceding_generation = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="replacement_generation")
    legacy_request = models.OneToOneField("workflow_runtime.BusinessStateTransition", null=True, blank=True, on_delete=models.PROTECT, related_name="completion_generation_bridge")
    workflow_instance = models.OneToOneField("workflow_runtime.WorkflowInstance", null=True, blank=True, on_delete=models.PROTECT, related_name="operation_completion_generation")
    approval_task = models.OneToOneField("workflow_runtime.ApprovalTask", null=True, blank=True, on_delete=models.PROTECT)
    approval_decision = models.OneToOneField("workflow_runtime.ApprovalDecision", null=True, blank=True, on_delete=models.PROTECT)
    source_snapshot = models.JSONField(default=dict)
    source_snapshot_hash = models.CharField(max_length=64)
    production_snapshot = models.JSONField(default=dict)
    production_revision = models.PositiveIntegerField(default=0)
    production_hash = models.CharField(max_length=64)
    request_snapshot = models.JSONField(default=dict)
    request_hash = models.CharField(max_length=64)
    request_key_hash = models.CharField(max_length=64)
    requested_at = models.DateTimeField()
    request_reason = models.CharField(max_length=240)
    request_audit_reference = models.CharField(max_length=160, blank=True, default="")
    closure = models.OneToOneField("workflow_runtime.WorkflowClosure", null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "planning_operation_completion_generation"
        constraints = [
            models.UniqueConstraint(fields=["task", "sequence"], name="uniq_operation_completion_generation_seq"),
            models.UniqueConstraint(fields=["task"], condition=models.Q(status__in=["pending", "approved"]), name="uniq_operation_completion_active_slot"),
        ]
