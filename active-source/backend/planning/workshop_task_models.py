"""One native dispatch task per immutable work-order operation."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from workflow_runtime.state_models import BusinessStateManagedModel, BusinessStateManagedQuerySet


class WorkshopTaskQuerySet(BusinessStateManagedQuerySet):
    def update(self, **kwargs):
        raise ValidationError('车间任务只能通过正式动作服务保存。')

    def bulk_update(self, *args, **kwargs):
        raise ValidationError('车间任务不可批量改写。')

    def delete(self):
        raise ValidationError('车间任务及历史不可删除。')


class ProductionWorkshopTask(BusinessStateManagedModel):
    objects = WorkshopTaskQuerySet.as_manager()
    company = models.ForeignKey('system.Company', on_delete=models.PROTECT)
    no = models.CharField(max_length=80)
    work_order = models.ForeignKey('planning.ProductionWorkOrder', on_delete=models.PROTECT)
    receipt = models.ForeignKey('planning.ProductionWorkOrderWorkshopReceipt', on_delete=models.PROTECT)
    source_operation = models.OneToOneField('planning.ProductionWorkOrderOperation', on_delete=models.PROTECT)
    workshop = models.ForeignKey('system.Workshop', on_delete=models.PROTECT)
    work_center = models.ForeignKey('pde.WorkCenter', on_delete=models.PROTECT)
    execution_mode = models.CharField(max_length=32, default='QUANTIFIED', db_default='QUANTIFIED', choices=(
        ('QUANTIFIED', '可统计数量'), ('NON_QUANTIFIED_REQUIRED', '必经但不统计实际量')))
    workload_quantity = models.CharField(max_length=100, null=True, blank=True)
    workload_uom = models.ForeignKey('masterdata.UnitOfMeasure', on_delete=models.PROTECT, null=True, blank=True)
    work_order_version = models.PositiveIntegerField()
    source_snapshot = models.JSONField()
    source_snapshot_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=(('draft', '草稿'), ('dispatched', '已派工')), default='draft')
    version = models.PositiveIntegerField(default=0)
    execution_position = models.ForeignKey('system.Position', on_delete=models.PROTECT, null=True, blank=True)
    execution_employee = models.ForeignKey('pfm.Employee', on_delete=models.PROTECT, null=True, blank=True)
    assignment_snapshot = models.JSONField(default=dict)
    assignment_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_workshop_tasks')
    dispatched_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='dispatched_workshop_tasks')
    dispatched_at = models.DateTimeField(null=True, blank=True)
    dispatch_qualification = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'planning_production_workshop_task'
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=('company', 'no'), name='workshop_task_company_no'),
            models.CheckConstraint(condition=models.Q(status__in=('draft', 'dispatched')), name='workshop_task_state'),
            models.CheckConstraint(condition=models.Q(execution_mode__in=('QUANTIFIED', 'NON_QUANTIFIED_REQUIRED')), name='workshop_task_exec_mode'),
            models.CheckConstraint(condition=(models.Q(workload_quantity__isnull=True, workload_uom__isnull=True)
                | (models.Q(workload_quantity__isnull=False, workload_uom__isnull=False) & ~models.Q(workload_quantity=''))),
                name='workshop_task_workload_pair'),
            models.CheckConstraint(condition=(~models.Q(execution_mode='QUANTIFIED')
                | models.Q(workload_quantity__isnull=False, workload_uom__isnull=False)),
                name='workshop_task_quant_required'),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status == 'dispatched':
                raise ValidationError('已派工任务不可修改。')
            frozen = ('company_id', 'no', 'work_order_id', 'receipt_id', 'source_operation_id', 'workshop_id',
                'work_center_id', 'execution_mode', 'workload_quantity', 'workload_uom_id', 'work_order_version',
                'source_snapshot', 'source_snapshot_hash', 'created_by_id', 'created_at')
            if any(getattr(self, field) != getattr(previous, field) for field in frozen):
                raise ValidationError('任务正式来源不可改写。')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('车间任务及历史不可删除。')
