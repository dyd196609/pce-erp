"""Immutable actual-start record; an unstarted Task has no execution row."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from workflow_runtime.state_models import BusinessStateManagedModel, BusinessStateManagedQuerySet


class OperationStartQuerySet(BusinessStateManagedQuerySet):
    def update(self, **kwargs):
        raise ValidationError('正式开工记录不可改写。')

    def bulk_update(self, *args, **kwargs):
        raise ValidationError('正式开工记录不可批量改写。')

    def bulk_create(self, *args, **kwargs):
        raise ValidationError('正式开工只能由统一状态初始化及事务服务创建。')

    def delete(self):
        raise ValidationError('正式开工记录及历史不可删除。')


class ProductionOperationStart(BusinessStateManagedModel):
    objects = OperationStartQuerySet.as_manager()
    company = models.ForeignKey('system.Company', on_delete=models.PROTECT)
    task = models.OneToOneField('planning.ProductionWorkshopTask', on_delete=models.PROTECT, related_name='operation_start')
    work_order = models.ForeignKey('planning.ProductionWorkOrder', on_delete=models.PROTECT)
    receipt = models.ForeignKey('planning.ProductionWorkOrderWorkshopReceipt', on_delete=models.PROTECT)
    source_operation = models.ForeignKey('planning.ProductionWorkOrderOperation', on_delete=models.PROTECT)
    workshop = models.ForeignKey('system.Workshop', on_delete=models.PROTECT)
    work_center = models.ForeignKey('pde.WorkCenter', on_delete=models.PROTECT)
    execution_mode = models.CharField(max_length=32, default='QUANTIFIED', db_default='QUANTIFIED', choices=(
        ('QUANTIFIED', '可统计数量'), ('NON_QUANTIFIED_REQUIRED', '必经但不统计实际量')))
    workload_quantity = models.CharField(max_length=100, null=True, blank=True)
    workload_uom = models.ForeignKey('masterdata.UnitOfMeasure', on_delete=models.PROTECT, null=True, blank=True)
    task_version = models.PositiveIntegerField()
    source_snapshot = models.JSONField()
    source_snapshot_hash = models.CharField(max_length=64)
    assignment_snapshot = models.JSONField()
    assignment_hash = models.CharField(max_length=64)
    execution_position = models.ForeignKey('system.Position', on_delete=models.PROTECT)
    execution_employee = models.ForeignKey('pfm.Employee', on_delete=models.PROTECT)
    started_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='started_production_operations')
    started_at = models.DateTimeField()
    start_qualification = models.JSONField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=(('started', '已开工'),), default='started')
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'planning_production_operation_start'
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=models.Q(status='started'), name='operation_start_only_started'),
            models.CheckConstraint(condition=models.Q(execution_mode__in=('QUANTIFIED', 'NON_QUANTIFIED_REQUIRED')), name='operation_start_exec_mode'),
            models.CheckConstraint(condition=(models.Q(workload_quantity__isnull=True, workload_uom__isnull=True)
                | (models.Q(workload_quantity__isnull=False, workload_uom__isnull=False) & ~models.Q(workload_quantity=''))),
                name='operation_start_workload_pair'),
            models.CheckConstraint(condition=(~models.Q(execution_mode='QUANTIFIED')
                | models.Q(workload_quantity__isnull=False, workload_uom__isnull=False)),
                name='operation_start_quant_required'),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding or not getattr(self, '_business_state_initialization_authorized', False):
            raise ValidationError('正式开工只能通过正式事务服务首次保存，提交后不可改写。')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('正式开工记录及历史不可删除。')
