from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from bank_send_request.models import BankSendRequest


class GovernedStatusQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "status" in kwargs or "recovery_status" in kwargs:
            raise ValidationError("Simulation status must use BusinessStateTransition")
        return super().update(**kwargs)


class GovernedStatusModel(models.Model):
    objects = GovernedStatusQuerySet.as_manager()

    class Meta:
        abstract = True

    def _guard_status_save(self, field):
        if not self.pk:
            if getattr(self, field) and not getattr(
                self, "_business_state_initialization_authorized", False
            ):
                raise ValidationError("Initial status must use state initialization service")
            return
        persisted = type(self).objects.filter(pk=self.pk).values(field).first()
        if (
            persisted
            and persisted[field] != getattr(self, field)
            and not getattr(self, "_business_state_transition_authorized", False)
        ):
            raise ValidationError("Status must use BusinessStateTransition")


class BankSendExecutionSimulation(GovernedStatusModel):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        VALIDATED = "validated", "Validated"
        RUNNING = "simulation_running", "Simulation running"
        SUCCESS = "simulation_success", "Simulation success"
        FAILED = "simulation_failed", "Simulation failed"

    simulation_no = models.CharField(max_length=112, unique=True)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    source_request = models.ForeignKey(
        BankSendRequest, on_delete=models.PROTECT, related_name="execution_simulations"
    )
    bank_send_request_no = models.CharField(max_length=96)
    bank_send_execution_gate_no = models.CharField(max_length=96)
    execution_version = models.PositiveIntegerField(default=1)
    execution_simulation_idempotency_key = models.CharField(max_length=160, unique=True)
    status = models.CharField(max_length=32, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    checks = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    failure_code = models.CharField(max_length=96, blank=True)
    failure_reason = models.CharField(max_length=320, blank=True)
    audit_events = models.JSONField(default=list)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_bank_send_execution_simulations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bank_send_execution_simulations"
        constraints = [
            models.UniqueConstraint(
                fields=("source_request", "execution_version"),
                name="bses_request_execution_version_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=[
                    "created", "validated", "simulation_running",
                    "simulation_success", "simulation_failed",
                ]),
                name="bses_status_valid",
            ),
        ]

    def save(self, *args, **kwargs):
        self._guard_status_save("status")
        return super().save(*args, **kwargs)


class BankSendExecutionRecovery(GovernedStatusModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RESOLVED = "resolved", "Resolved"

    recovery_no = models.CharField(max_length=112, unique=True)
    simulation = models.OneToOneField(
        BankSendExecutionSimulation, on_delete=models.PROTECT, related_name="recovery"
    )
    failure_code = models.CharField(max_length=96)
    failure_reason = models.CharField(max_length=320)
    recovery_status = models.CharField(max_length=16, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    resolution_note = models.CharField(max_length=320, blank=True)
    audit_events = models.JSONField(default=list)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="resolved_bank_send_execution_recoveries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bank_send_execution_recoveries"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(recovery_status__in=["pending", "resolved"]),
                name="bser_status_valid",
            ),
        ]

    @property
    def status(self):
        return self.recovery_status

    @status.setter
    def status(self, value):
        self.recovery_status = value

    def save(self, *args, **kwargs):
        self._guard_status_save("recovery_status")
        return super().save(*args, **kwargs)


class BankSendSimulationAudit(models.Model):
    class AuditType(models.TextChoices):
        CREATED = "simulation_created", "Simulation created"
        VALIDATED = "simulation_validated", "Simulation validated"
        STARTED = "simulation_started", "Simulation started"
        COMPLETED = "simulation_completed", "Simulation completed"
        FAILED = "simulation_failed", "Simulation failed"
        RECOVERED = "simulation_recovered", "Simulation recovered"

    audit_no = models.CharField(max_length=144, unique=True)
    simulation = models.ForeignKey(
        BankSendExecutionSimulation,
        on_delete=models.PROTECT,
        related_name="independent_audits",
    )
    simulation_no = models.CharField(max_length=112)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    audit_type = models.CharField(max_length=32, choices=AuditType.choices)
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bank_send_simulation_audits",
    )
    occurred_at = models.DateTimeField()
    reason = models.CharField(max_length=320)
    audit_reference = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_send_simulation_audits"
        constraints = [
            models.UniqueConstraint(
                fields=("simulation", "audit_type"),
                name="bssa_simulation_audit_type_unique",
            ),
        ]


class BankSendProductionIsolationGate(GovernedStatusModel):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        CHECKED = "checked", "Checked"
        ISOLATED = "isolated", "Isolated"

    gate_no = models.CharField(max_length=112, unique=True)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    simulation_environment = models.BooleanField(default=True)
    production_connection_enabled = models.BooleanField(default=False)
    production_secret_available = models.BooleanField(default=False)
    production_send_allowed = models.BooleanField(default=False)
    payment_execution_allowed = models.BooleanField(default=False)
    approval_status = models.CharField(max_length=40, default="not_approved")
    status = models.CharField(max_length=16, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    checks = models.JSONField(default=dict)
    audit_events = models.JSONField(default=list)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_bank_send_production_isolation_gates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bank_send_production_isolation_gates"
        constraints = [
            models.UniqueConstraint(
                fields=("tenant_id", "batch_id"),
                name="bspig_tenant_batch_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["created", "checked", "isolated"]),
                name="bspig_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(production_connection_enabled=False),
                name="bspig_production_connection_disabled",
            ),
            models.CheckConstraint(
                condition=models.Q(production_secret_available=False),
                name="bspig_production_secret_absent",
            ),
            models.CheckConstraint(
                condition=models.Q(production_send_allowed=False),
                name="bspig_production_send_forbidden",
            ),
            models.CheckConstraint(
                condition=models.Q(payment_execution_allowed=False),
                name="bspig_payment_execution_forbidden",
            ),
        ]

    def save(self, *args, **kwargs):
        self._guard_status_save("status")
        return super().save(*args, **kwargs)


class BankSendChainTrace(models.Model):
    trace_no = models.CharField(max_length=128, unique=True)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    source_simulation = models.OneToOneField(
        BankSendExecutionSimulation,
        on_delete=models.PROTECT,
        related_name="chain_trace",
    )
    isolation_gate = models.ForeignKey(
        BankSendProductionIsolationGate,
        on_delete=models.PROTECT,
        related_name="chain_traces",
    )
    formal_payment_order_no = models.CharField(max_length=80)
    bank_send_preparation_no = models.CharField(max_length=80)
    bank_send_task_no = models.CharField(max_length=80)
    bank_send_execution_gate_no = models.CharField(max_length=96)
    bank_send_request_no = models.CharField(max_length=96)
    simulation_no = models.CharField(max_length=112)
    simulation_audit_no = models.CharField(max_length=144)
    isolation_gate_no = models.CharField(max_length=112)
    trace_complete = models.BooleanField(default=False)
    trace_source = models.CharField(max_length=16, default="server", editable=False)
    node_snapshot = models.JSONField(default=list)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_bank_send_chain_traces",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_send_chain_traces"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(trace_source="server"),
                name="bsct_trace_source_server",
            ),
        ]


class BankSendFinalApproval(GovernedStatusModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        FIRST_APPROVED = "first_approved", "First approved"
        SECOND_APPROVED = "second_approved", "Second approved"
        FINAL_LOCKED = "final_locked", "Final locked"

    approval_no = models.CharField(max_length=128, unique=True)
    trace = models.OneToOneField(
        BankSendChainTrace,
        on_delete=models.PROTECT,
        related_name="final_approval",
    )
    trace_no = models.CharField(max_length=128)
    request_no = models.CharField(max_length=96)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    status = models.CharField(max_length=32, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    checks = models.JSONField(default=dict)
    audit_events = models.JSONField(default=list)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_bank_send_final_approvals",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bank_send_final_approvals"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "pending",
                        "first_approved",
                        "second_approved",
                        "final_locked",
                    ]
                ),
                name="bsfa_status_valid",
            ),
        ]

    def save(self, *args, **kwargs):
        self._guard_status_save("status")
        return super().save(*args, **kwargs)


class BankSendFinalApprovalDecision(models.Model):
    class Stage(models.TextChoices):
        FIRST = "first", "First approval"
        SECOND = "second", "Second approval"

    approval = models.ForeignKey(
        BankSendFinalApproval,
        on_delete=models.PROTECT,
        related_name="decisions",
    )
    stage = models.CharField(max_length=16, choices=Stage.choices)
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bank_send_final_approval_decisions",
    )
    role = models.CharField(max_length=64)
    occurred_at = models.DateTimeField()
    reason = models.CharField(max_length=320)
    audit_reference = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_send_final_approval_decisions"
        constraints = [
            models.UniqueConstraint(
                fields=("approval", "stage"),
                name="bsfad_approval_stage_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    role__in=[
                        "bank_send_business_reviewer",
                        "bank_send_fund_owner",
                    ]
                ),
                name="bsfad_role_valid",
            ),
        ]


class BankSendDualIsolationCheck(models.Model):
    class Result(models.TextChoices):
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"

    check_no = models.CharField(max_length=160, unique=True)
    trace = models.OneToOneField(
        BankSendChainTrace,
        on_delete=models.PROTECT,
        related_name="dual_isolation_check",
    )
    approval = models.OneToOneField(
        BankSendFinalApproval,
        on_delete=models.PROTECT,
        related_name="dual_isolation_check",
    )
    trace_no = models.CharField(max_length=128)
    approval_no = models.CharField(max_length=128)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    environment_isolated = models.BooleanField(default=True)
    production_interface_disabled = models.BooleanField(default=True)
    production_credential_absent = models.BooleanField(default=True)
    send_permission_disabled = models.BooleanField(default=True)
    payment_permission_disabled = models.BooleanField(default=True)
    category_results = models.JSONField(default=dict)
    result = models.CharField(max_length=16, choices=Result.choices)
    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bank_send_dual_isolation_checks",
    )
    checked_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_send_dual_isolation_checks"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(result__in=["passed", "failed"]),
                name="bsdic_result_valid",
            ),
        ]


class BankSendProductionReleaseReview(GovernedStatusModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEWING = "reviewing", "Reviewing"
        REVIEW_PASSED = "review_passed", "Review passed"
        LOCKED = "locked", "Locked"

    review_no = models.CharField(max_length=176, unique=True)
    trace = models.OneToOneField(
        BankSendChainTrace,
        on_delete=models.PROTECT,
        related_name="production_release_review",
    )
    approval = models.OneToOneField(
        BankSendFinalApproval,
        on_delete=models.PROTECT,
        related_name="production_release_review",
    )
    isolation_check = models.OneToOneField(
        BankSendDualIsolationCheck,
        on_delete=models.PROTECT,
        related_name="release_review",
    )
    trace_no = models.CharField(max_length=128)
    approval_no = models.CharField(max_length=128)
    isolation_check_no = models.CharField(max_length=160)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    status = models.CharField(max_length=32, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    checks = models.JSONField(default=dict)
    audit_events = models.JSONField(default=list)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_bank_send_production_release_reviews",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bank_send_production_release_reviews"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "draft",
                        "reviewing",
                        "review_passed",
                        "locked",
                    ]
                ),
                name="bsprr_status_valid",
            ),
        ]

    def save(self, *args, **kwargs):
        self._guard_status_save("status")
        return super().save(*args, **kwargs)


class BankSendProductionReleaseDecision(models.Model):
    class Stage(models.TextChoices):
        BUSINESS = "business", "Business owner"
        FUND = "fund", "Fund owner"
        SECURITY = "security", "Security owner"

    review = models.ForeignKey(
        BankSendProductionReleaseReview,
        on_delete=models.PROTECT,
        related_name="decisions",
    )
    stage = models.CharField(max_length=16, choices=Stage.choices)
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bank_send_production_release_decisions",
    )
    role = models.CharField(max_length=64)
    occurred_at = models.DateTimeField()
    reason = models.CharField(max_length=320)
    decision = models.CharField(max_length=24, default="confirmed")
    audit_reference = models.CharField(max_length=220, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_send_production_release_decisions"
        constraints = [
            models.UniqueConstraint(
                fields=("review", "stage"),
                name="bsprd_review_stage_unique",
            ),
            models.UniqueConstraint(
                fields=("review", "operator"),
                name="bsprd_review_operator_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    role__in=[
                        "bank_send_business_owner",
                        "bank_send_fund_owner",
                        "bank_send_security_owner",
                    ]
                ),
                name="bsprd_role_valid",
            ),
        ]


class BankSendExecutionFramework(GovernedStatusModel):
    class Environment(models.TextChoices):
        SIMULATION = "simulation", "Simulation"
        SANDBOX = "sandbox", "Sandbox"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        DESIGNED = "designed", "Designed"
        SECURITY_REVIEWED = "security_reviewed", "Security reviewed"

    framework_no = models.CharField(max_length=192, unique=True)
    source_review = models.OneToOneField(
        BankSendProductionReleaseReview,
        on_delete=models.PROTECT,
        related_name="execution_framework",
    )
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    environment = models.CharField(
        max_length=16,
        choices=Environment.choices,
        default=Environment.SIMULATION,
    )
    interface_mode = models.CharField(max_length=24, default="simulated")
    execution_mode = models.CharField(max_length=24, default="design_only")
    production_connection_enabled = models.BooleanField(default=False)
    production_secret_available = models.BooleanField(default=False)
    send_permission_enabled = models.BooleanField(default=False)
    payment_permission_enabled = models.BooleanField(default=False)
    status = models.CharField(max_length=32, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    design_snapshot = models.JSONField(default=dict)
    audit_events = models.JSONField(default=list)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_bank_send_execution_frameworks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bank_send_execution_frameworks"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(environment__in=["simulation", "sandbox"]),
                name="bsef_environment_nonproduction",
            ),
            models.CheckConstraint(
                condition=models.Q(interface_mode="simulated"),
                name="bsef_interface_simulated",
            ),
            models.CheckConstraint(
                condition=models.Q(execution_mode="design_only"),
                name="bsef_execution_design_only",
            ),
            models.CheckConstraint(
                condition=models.Q(production_connection_enabled=False),
                name="bsef_production_connection_disabled",
            ),
            models.CheckConstraint(
                condition=models.Q(production_secret_available=False),
                name="bsef_production_secret_absent",
            ),
            models.CheckConstraint(
                condition=models.Q(send_permission_enabled=False),
                name="bsef_send_permission_disabled",
            ),
            models.CheckConstraint(
                condition=models.Q(payment_permission_enabled=False),
                name="bsef_payment_permission_disabled",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["draft", "designed", "security_reviewed"]
                ),
                name="bsef_status_valid",
            ),
        ]

    def save(self, *args, **kwargs):
        self._guard_status_save("status")
        return super().save(*args, **kwargs)


class BankSendProductionSafetyReview(models.Model):
    review_no = models.CharField(max_length=208, unique=True)
    framework = models.OneToOneField(
        BankSendExecutionFramework,
        on_delete=models.PROTECT,
        related_name="safety_review",
    )
    result = models.CharField(max_length=24, default="passed")
    checks = models.JSONField(default=dict)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bank_send_production_safety_reviews",
    )
    reviewed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_send_production_safety_reviews"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(result__in=["passed", "failed"]),
                name="bspsr_result_valid",
            ),
        ]


class BankSendRequestSignature(models.Model):
    signature_no = models.CharField(max_length=208, unique=True)
    request = models.OneToOneField(
        BankSendRequest,
        on_delete=models.PROTECT,
        related_name="simulation_signature",
    )
    request_no = models.CharField(max_length=96)
    algorithm = models.CharField(max_length=32, default="SHA256_SIMULATION")
    payload_hash = models.CharField(max_length=64)
    certificate_mode = models.CharField(
        max_length=24, default="simulation_only"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_send_request_signatures"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(certificate_mode="simulation_only"),
                name="bsrs_simulation_certificate_only",
            ),
        ]


class BankSendExecutionIdempotency(models.Model):
    idempotency_key = models.CharField(max_length=160, unique=True)
    request = models.ForeignKey(
        BankSendRequest,
        on_delete=models.PROTECT,
        related_name="execution_idempotencies",
    )
    request_no = models.CharField(max_length=96)
    execution_version = models.PositiveIntegerField()
    status = models.CharField(max_length=24, default="reserved")
    simulation_result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_send_execution_idempotencies"
        constraints = [
            models.UniqueConstraint(
                fields=("request", "execution_version"),
                name="bsei_request_version_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["reserved", "simulated"]),
                name="bsei_status_nonproduction",
            ),
        ]


class BankSendExecutionFailure(models.Model):
    class FailureType(models.TextChoices):
        TIMEOUT = "timeout", "Timeout"
        CONNECTION_ERROR = "connection_error", "Connection error"
        SIGNATURE_ERROR = "signature_error", "Signature error"
        RESPONSE_ERROR = "response_error", "Response error"

    failure_no = models.CharField(max_length=208, unique=True)
    request = models.ForeignKey(
        BankSendRequest,
        on_delete=models.PROTECT,
        related_name="execution_framework_failures",
    )
    request_no = models.CharField(max_length=96)
    failure_type = models.CharField(
        max_length=32, choices=FailureType.choices
    )
    failure_reason = models.CharField(max_length=320)
    retry_allowed = models.BooleanField(default=False)
    simulated = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_send_execution_failures"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(retry_allowed=False),
                name="bsefail_auto_retry_forbidden",
            ),
            models.CheckConstraint(
                condition=models.Q(simulated=True),
                name="bsefail_simulation_only",
            ),
        ]


class BankSendResponseReceipt(models.Model):
    class ResponseStatus(models.TextChoices):
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        UNKNOWN = "unknown", "Unknown"

    receipt_no = models.CharField(max_length=208, unique=True)
    request = models.OneToOneField(
        BankSendRequest,
        on_delete=models.PROTECT,
        related_name="simulation_response_receipt",
    )
    request_no = models.CharField(max_length=96)
    response_status = models.CharField(
        max_length=16, choices=ResponseStatus.choices
    )
    response_time = models.DateTimeField()
    response_hash = models.CharField(max_length=64)
    simulated = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_send_response_receipts"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(simulated=True),
                name="bsrr_simulation_only",
            ),
        ]
