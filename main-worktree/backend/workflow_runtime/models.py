from django.conf import settings
from django.db import models


class ApprovalPolicyAuthority(models.Model):
    policy_code = models.CharField(max_length=80, unique=True)
    document_type = models.CharField(max_length=80)
    legal_entity_id = models.CharField(max_length=80)
    amount_min = models.DecimalField(max_digits=18, decimal_places=2)
    amount_max = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=8)
    active = models.BooleanField(default=True)
    step_count = models.PositiveIntegerField()
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "workflow_approval_policy_authorities"


class ApprovalRouteAuthority(models.Model):
    route_code = models.CharField(max_length=80, unique=True)
    policy = models.ForeignKey(
        ApprovalPolicyAuthority, on_delete=models.PROTECT, related_name="routes"
    )
    steps = models.JSONField(default=list)
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "workflow_approval_route_authorities"


class UserOrganizationRoleAuthority(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="workflow_authorities"
    )
    role_code = models.CharField(max_length=80)
    legal_entity_id = models.CharField(max_length=80)
    department_id = models.CharField(max_length=80, blank=True)
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "workflow_user_role_authorities"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role_code", "legal_entity_id"],
                name="uniq_workflow_user_role_scope",
            )
        ]


class SegregationOfDutiesAuthority(models.Model):
    document_type = models.CharField(max_length=80, unique=True)
    applicant_cannot_approve = models.BooleanField(default=True)
    same_department_restriction = models.BooleanField(default=False)
    same_user_restriction = models.BooleanField(default=True)
    required_role_separation = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "workflow_sod_authorities"


class ProcessDefinition(models.Model):
    definition_code = models.CharField(max_length=80, unique=True)
    definition_name = models.CharField(max_length=120, blank=True, default="")
    business_domain = models.CharField(max_length=80, blank=True, default="")
    description = models.TextField(blank=True)
    document_type = models.CharField(max_length=80)
    version = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)
    definition_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "workflow_process_definitions"


class WorkflowNodeDefinition(models.Model):
    process_definition = models.ForeignKey(
        ProcessDefinition, on_delete=models.PROTECT, related_name="nodes"
    )
    node_code = models.CharField(max_length=100)
    node_name = models.CharField(max_length=120)
    sequence = models.PositiveIntegerField()
    business_action_code = models.CharField(max_length=120)
    active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "workflow_node_definitions"
        ordering = ["process_definition_id", "sequence", "node_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["process_definition", "node_code"],
                name="uniq_workflow_definition_node_code",
            ),
            models.UniqueConstraint(
                fields=["process_definition", "sequence"],
                name="uniq_workflow_definition_node_seq",
            ),
        ]


class WorkflowInstance(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    instance_no = models.CharField(max_length=80, unique=True)
    process_definition = models.ForeignKey(
        ProcessDefinition, on_delete=models.PROTECT, related_name="instances"
    )
    document_type = models.CharField(max_length=80)
    document_id = models.BigIntegerField()
    status = models.CharField(max_length=24, choices=Status.choices)
    current_step = models.PositiveIntegerField(default=1)
    total_steps = models.PositiveIntegerField()
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "workflow_instances"
        constraints = [
            models.UniqueConstraint(
                fields=["document_type", "document_id"],
                name="uniq_workflow_document_instance",
            )
        ]


class ApprovalTask(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CLOSED = "closed", "Closed"

    task_no = models.CharField(max_length=80, unique=True)
    workflow_instance = models.ForeignKey(
        WorkflowInstance, on_delete=models.PROTECT, related_name="tasks"
    )
    step_no = models.PositiveIntegerField()
    required_role_code = models.CharField(max_length=80)
    minimum_approvals = models.PositiveIntegerField(default=1)
    allow_parallel = models.BooleanField(default=False)
    status = models.CharField(max_length=24, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "workflow_approval_tasks"
        constraints = [
            models.UniqueConstraint(
                fields=["workflow_instance", "step_no"],
                name="uniq_workflow_instance_step",
            )
        ]


class ApprovalDecision(models.Model):
    task = models.ForeignKey(
        ApprovalTask, on_delete=models.PROTECT, related_name="decisions"
    )
    decision_sequence = models.PositiveIntegerField(default=1)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="approval_decisions"
    )
    decision = models.CharField(max_length=24)
    comment = models.CharField(max_length=500, blank=True)
    action_id = models.CharField(max_length=80)
    idempotency_key = models.CharField(max_length=120)
    decision_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "workflow_approval_decisions"
        constraints = [
            models.UniqueConstraint(
                fields=["task", "decision_sequence"],
                name="uniq_workflow_task_decision_sequence",
            ),
            models.UniqueConstraint(
                fields=["action_id", "idempotency_key"],
                name="uniq_workflow_decision_idempotency",
            ),
        ]


class BusinessStateTransition(models.Model):
    object_type = models.CharField(max_length=80)
    object_id = models.BigIntegerField()
    source_state = models.CharField(max_length=80)
    target_state = models.CharField(max_length=80)
    action_code = models.CharField(max_length=80)
    workflow_instance = models.ForeignKey(
        WorkflowInstance,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="business_state_transitions",
    )
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="business_state_transitions",
    )
    reason = models.CharField(max_length=240)
    audit_reference = models.CharField(max_length=160)
    version = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "business_state_transitions"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "object_type",
                    "object_id",
                    "version",
                ],
                name="uniq_business_state_transition_version",
            ),
            models.CheckConstraint(
                condition=~models.Q(reason=""),
                name="bst_reason_required",
            ),
            models.CheckConstraint(
                condition=~models.Q(audit_reference=""),
                name="bst_audit_reference_required",
            ),
            models.UniqueConstraint(
                fields=["audit_reference"],
                name="uniq_bst_audit_reference",
            ),
        ]
        indexes = [
            models.Index(
                fields=["object_type", "object_id", "timestamp"],
                name="idx_business_state_history",
            ),
        ]
