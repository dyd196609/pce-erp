"""Native quantitative output/custody records; never an inventory ledger.

Quantities are canonical decimal strings. SQLite NUMERIC affinity must not
round an audited source quantity through a binary float. Services compare
Decimal/int values under the database account CAS, never SQL SUM.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from workflow_runtime.state_models import BusinessStateManagedModel, BusinessStateManagedQuerySet


class HandoverQuerySet(BusinessStateManagedQuerySet):
    def update(self, **kwargs):
        raise ValidationError('交接事实只能通过正式事务服务维护。')

    def bulk_update(self, *args, **kwargs):
        raise ValidationError('交接事实不可批量改写。')

    def delete(self):
        raise ValidationError('交接及其来源、审计历史不可删除。')


class HandoverRecord(BusinessStateManagedModel):
    objects = HandoverQuerySet.as_manager()
    company = models.ForeignKey('system.Company', on_delete=models.PROTECT)
    status = models.CharField(max_length=32)
    version = models.PositiveIntegerField(default=0)
    source_snapshot = models.JSONField(default=dict)
    source_snapshot_hash = models.CharField(max_length=64)
    qualification_snapshot = models.JSONField(default=dict)
    intent_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        default_permissions = ()

    def save(self, *args, **kwargs):
        if self._state.adding and not getattr(self, '_business_state_initialization_authorized', False):
            raise ValidationError('交接对象初始状态必须由统一原子初始化服务创建。')
        if self.pk and not (getattr(self, '_handover_projection_authorized', False)
                            or getattr(self, '_business_state_transition_authorized', False)):
            raise ValidationError('交接来源及投影只能由已审计的正式事务更新。')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('正式交接及历史不可删除。')


class OperationQuantityAccount(models.Model):
    """Stable database CAS anchor; a projection, not a second fact authority."""
    company = models.ForeignKey('system.Company', on_delete=models.PROTECT)
    task = models.OneToOneField('planning.ProductionWorkshopTask', on_delete=models.PROTECT)
    revision = models.PositiveBigIntegerField(default=0)
    production_revision = models.PositiveBigIntegerField(default=0)
    release_revision = models.PositiveBigIntegerField(default=0)
    custody_revision = models.PositiveBigIntegerField(default=0)
    account_key = models.CharField(max_length=64, blank=True)
    source_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = 'planning_operation_quantity_account'
        default_permissions = ()


class OperationOutputEvidence(HandoverRecord):
    task = models.ForeignKey('planning.ProductionWorkshopTask', on_delete=models.PROTECT, related_name='output_evidence')
    kind = models.CharField(max_length=32, choices=[(x, x) for x in ('NORMAL_CONFIRM', 'WHOLE_RELEASE', 'EXCESS_REPORT', 'OUTPUT_CORRECTION')])
    quantity = models.CharField(max_length=100)
    uom = models.ForeignKey('masterdata.UnitOfMeasure', on_delete=models.PROTECT)
    account_key = models.CharField(max_length=64)
    batch_label = models.CharField(max_length=160)
    scope_manifest = models.JSONField()
    scope_hash = models.CharField(max_length=64)
    occurred_at = models.DateTimeField()
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name='+')
    confirmed_at = models.DateTimeField(null=True)
    workflow = models.ForeignKey('workflow_runtime.WorkflowInstance', on_delete=models.PROTECT, null=True, related_name='+')
    approval_task = models.ForeignKey('workflow_runtime.ApprovalTask', on_delete=models.PROTECT, null=True, related_name='+')
    approval_decision = models.ForeignKey('workflow_runtime.ApprovalDecision', on_delete=models.PROTECT, null=True, related_name='+')
    correction_of = models.ForeignKey('self', on_delete=models.PROTECT, null=True, related_name='corrections')
    effect_sign = models.SmallIntegerField(default=1)
    data = models.JSONField(default=dict)

    class Meta:
        db_table = 'planning_operation_output_evidence'
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=('declared', 'confirmed', 'rejected')), name='op_output_status'),
            models.CheckConstraint(condition=models.Q(effect_sign__in=(-1, 1)), name='op_output_sign'),
            models.CheckConstraint(condition=models.Q(quantity__regex=r'^(0|[1-9][0-9]*)(\.[0-9]+)?$'), name='op_output_qty_text'),
            models.UniqueConstraint(fields=('company', 'task', 'scope_hash', 'kind'), name='op_output_scope_kind_unique'),
        ]


class OperationOutputAllocation(models.Model):
    evidence = models.ForeignKey(OperationOutputEvidence, on_delete=models.PROTECT, related_name='allocations')
    report = models.ForeignKey('planning.ProductionOperationReport', on_delete=models.PROTECT, null=True)
    coverage_kind = models.CharField(max_length=16, default='RELEASE')
    start_atom = models.CharField(max_length=100)
    end_atom = models.CharField(max_length=100)
    quantity = models.CharField(max_length=100)
    source_hash = models.CharField(max_length=64)
    data = models.JSONField(default=dict)

    class Meta:
        db_table = 'planning_operation_output_allocation'
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=models.Q(start_atom__regex=r'^(0|[1-9][0-9]*)$'), name='op_output_start_atom'),
            models.CheckConstraint(condition=models.Q(end_atom__regex=r'^[1-9][0-9]*$'), name='op_output_end_atom'),
            models.UniqueConstraint(fields=('report', 'start_atom', 'end_atom', 'coverage_kind'), name='op_report_exact_coverage_unique'),
        ]

    def save(self, *args, **kwargs):
        from django.db import connection
        if not self._state.adding or not getattr(self, '_output_allocation_authorized', False) or not connection.in_atomic_block:
            raise ValidationError('产出来源覆盖不可改写。')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('产出来源覆盖不可删除。')


class OperationCustodySlice(HandoverRecord):
    root = models.ForeignKey(OperationOutputEvidence, on_delete=models.PROTECT, related_name='slices')
    parent = models.ForeignKey('self', on_delete=models.PROTECT, null=True, related_name='children')
    quantity = models.CharField(max_length=100)
    start_atom = models.CharField(max_length=100)
    end_atom = models.CharField(max_length=100)
    holder_workshop = models.ForeignKey('system.Workshop', on_delete=models.PROTECT, null=True, related_name='+')
    holder_work_center = models.ForeignKey('pde.WorkCenter', on_delete=models.PROTECT, null=True, related_name='+')
    reserved_by = models.ForeignKey('planning.OperationHandoverAllocation', on_delete=models.PROTECT, null=True, related_name='+')
    frozen = models.BooleanField(default=False)
    data = models.JSONField(default=dict)

    class Meta:
        db_table = 'planning_operation_custody_slice'
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=('U', 'S', 'V', 'I', 'Q', 'Z', 'C', 'closed')), name='op_custody_slice_status'),
            models.CheckConstraint(condition=models.Q(start_atom__regex=r'^(0|[1-9][0-9]*)$'), name='op_slice_start_atom'),
            models.CheckConstraint(condition=models.Q(end_atom__regex=r'^[1-9][0-9]*$'), name='op_slice_end_atom'),
            models.UniqueConstraint(fields=('root', 'start_atom', 'end_atom'), name='op_slice_exact_range_unique'),
        ]


class OperationHandover(HandoverRecord):
    no = models.CharField(max_length=80, unique=True)
    kind = models.CharField(max_length=16, default='NORMAL')
    source_work_center = models.ForeignKey('pde.WorkCenter', on_delete=models.PROTECT, related_name='+')
    source_workshop = models.ForeignKey('system.Workshop', on_delete=models.PROTECT, related_name='+')
    target_work_center = models.ForeignKey('pde.WorkCenter', on_delete=models.PROTECT, related_name='+')
    target_workshop = models.ForeignKey('system.Workshop', on_delete=models.PROTECT, related_name='+')
    target_operation = models.ForeignKey('planning.ProductionWorkOrderOperation', on_delete=models.PROTECT, null=True)
    destination_kind = models.CharField(max_length=16, default='production')
    destination_reference = models.CharField(max_length=160, blank=True)
    previous_handover = models.ForeignKey('self', on_delete=models.PROTECT, null=True)
    sender_employee = models.ForeignKey('pfm.Employee', on_delete=models.PROTECT, null=True, related_name='+')
    receiver_employee = models.ForeignKey('pfm.Employee', on_delete=models.PROTECT, null=True, related_name='+')
    dispatched_at = models.DateTimeField(null=True)
    data = models.JSONField(default=dict)

    class Meta:
        db_table = 'planning_operation_handover'
        default_permissions = ()
        constraints = [models.CheckConstraint(condition=models.Q(status__in=('prepared', 'cancelled', 'in_transit', 'partially_received', 'received', 'discrepancy_pending', 'closed_with_difference')), name='op_handover_status')]


class OperationHandoverAllocation(HandoverRecord):
    handover = models.ForeignKey(OperationHandover, on_delete=models.PROTECT, related_name='allocations')
    source_slice = models.ForeignKey(OperationCustodySlice, on_delete=models.PROTECT, related_name='+')
    root = models.ForeignKey(OperationOutputEvidence, on_delete=models.PROTECT)
    quantity = models.CharField(max_length=100)
    uom = models.ForeignKey('masterdata.UnitOfMeasure', on_delete=models.PROTECT)
    data = models.JSONField(default=dict)

    class Meta:
        db_table = 'planning_operation_handover_allocation'
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=('handover', 'source_slice'), name='op_handover_slice_unique')]


class OperationCustodyEvent(HandoverRecord):
    task = models.ForeignKey('planning.ProductionWorkshopTask', on_delete=models.PROTECT)
    handover = models.ForeignKey(OperationHandover, on_delete=models.PROTECT, null=True, related_name='events')
    allocation = models.ForeignKey(OperationHandoverAllocation, on_delete=models.PROTECT, null=True, related_name='events')
    slice = models.ForeignKey(OperationCustodySlice, on_delete=models.PROTECT, null=True, related_name='events')
    kind = models.CharField(max_length=40)
    quantity = models.CharField(max_length=100)
    debit = models.CharField(max_length=16, blank=True)
    credit = models.CharField(max_length=16, blank=True)
    occurred_at = models.DateTimeField()
    previous_hash = models.CharField(max_length=64, blank=True)
    event_hash = models.CharField(max_length=64)
    data = models.JSONField(default=dict)

    class Meta:
        db_table = 'planning_operation_custody_event'
        default_permissions = ()
        constraints = [models.CheckConstraint(condition=models.Q(status='recorded'), name='op_custody_event_recorded')]


class OperationCustodyException(HandoverRecord):
    task = models.ForeignKey('planning.ProductionWorkshopTask', on_delete=models.PROTECT)
    handover = models.ForeignKey(OperationHandover, on_delete=models.PROTECT, null=True)
    allocation = models.ForeignKey(OperationHandoverAllocation, on_delete=models.PROTECT, null=True)
    slice = models.ForeignKey(OperationCustodySlice, on_delete=models.PROTECT, null=True)
    kind = models.CharField(max_length=40)
    original_quantity = models.CharField(max_length=100)
    quantity = models.CharField(max_length=100)
    occurred_at = models.DateTimeField()
    workflow = models.ForeignKey('workflow_runtime.WorkflowInstance', on_delete=models.PROTECT, null=True, related_name='+')
    approval_task = models.ForeignKey('workflow_runtime.ApprovalTask', on_delete=models.PROTECT, null=True, related_name='+')
    approval_decision = models.ForeignKey('workflow_runtime.ApprovalDecision', on_delete=models.PROTECT, null=True, related_name='+')
    data = models.JSONField(default=dict)

    @property
    def confirmed_by_id(self):
        return self.data.get('reviewerId')

    class Meta:
        db_table = 'planning_operation_custody_exception'
        default_permissions = ()
        constraints = [models.CheckConstraint(condition=models.Q(status__in=('pending', 'confirmed', 'rejected')), name='op_custody_exception_status')]


class OperationInputAllocation(HandoverRecord):
    """Formal upstream share closure for new output; not a JSON-only claim."""
    source_slice = models.ForeignKey(OperationCustodySlice, on_delete=models.PROTECT, related_name='input_allocations')
    output = models.ForeignKey(OperationOutputEvidence, on_delete=models.PROTECT, related_name='input_allocations')
    execution_start = models.ForeignKey('planning.ProductionOperationStart', on_delete=models.PROTECT)
    quantity = models.CharField(max_length=100)
    uom = models.ForeignKey('masterdata.UnitOfMeasure', on_delete=models.PROTECT)
    start_atom = models.CharField(max_length=100)
    end_atom = models.CharField(max_length=100)
    data = models.JSONField(default=dict)

    class Meta:
        db_table = 'planning_operation_input_allocation'
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=('source_slice', 'start_atom', 'end_atom'), name='op_input_exact_range_unique')]
