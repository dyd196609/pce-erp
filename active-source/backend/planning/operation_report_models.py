"""Append-only, actual-quantity reports; no completion or inventory projection."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from workflow_runtime.state_models import BusinessStateManagedModel, BusinessStateManagedQuerySet


class OperationReportQuerySet(BusinessStateManagedQuerySet):
    def update(self, **kwargs):
        raise ValidationError('正式报工记录不可改写。')

    def bulk_update(self, *args, **kwargs):
        raise ValidationError('正式报工记录不可批量改写。')

    def bulk_create(self, *args, **kwargs):
        raise ValidationError('正式报工只能由统一状态初始化及事务服务创建。')

    def delete(self):
        raise ValidationError('正式报工记录及历史不可删除。')


class ProductionOperationReport(BusinessStateManagedModel):
    objects = OperationReportQuerySet.as_manager()
    company = models.ForeignKey('system.Company', on_delete=models.PROTECT)
    task = models.ForeignKey('planning.ProductionWorkshopTask', on_delete=models.PROTECT, related_name='operation_reports')
    start = models.ForeignKey('planning.ProductionOperationStart', on_delete=models.PROTECT, related_name='operation_reports')
    work_order = models.ForeignKey('planning.ProductionWorkOrder', on_delete=models.PROTECT)
    receipt = models.ForeignKey('planning.ProductionWorkOrderWorkshopReceipt', on_delete=models.PROTECT)
    source_operation = models.ForeignKey('planning.ProductionWorkOrderOperation', on_delete=models.PROTECT)
    workshop = models.ForeignKey('system.Workshop', on_delete=models.PROTECT)
    work_center = models.ForeignKey('pde.WorkCenter', on_delete=models.PROTECT)
    workload_quantity = models.CharField(max_length=100)
    workload_uom = models.ForeignKey('masterdata.UnitOfMeasure', on_delete=models.PROTECT)
    quantity = models.CharField(max_length=100)
    reported_before = models.CharField(max_length=100)
    reported_after = models.CharField(max_length=100)
    quantity_precision = models.PositiveSmallIntegerField()
    unit_snapshot = models.JSONField()
    task_version = models.PositiveIntegerField()
    source_snapshot = models.JSONField()
    source_snapshot_hash = models.CharField(max_length=64)
    assignment_snapshot = models.JSONField()
    assignment_hash = models.CharField(max_length=64)
    start_snapshot = models.JSONField()
    start_snapshot_hash = models.CharField(max_length=64)
    execution_position = models.ForeignKey('system.Position', on_delete=models.PROTECT)
    execution_employee = models.ForeignKey('pfm.Employee', on_delete=models.PROTECT)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='reported_production_operations')
    reported_at = models.DateTimeField()
    report_qualification = models.JSONField()
    reason = models.TextField()
    request_key_hash = models.CharField(max_length=64)
    request_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=(('reported', '已报工'),), default='reported')
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'planning_production_operation_report'
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=models.Q(status='reported'), name='operation_report_only_reported'),
            models.CheckConstraint(condition=models.Q(quantity_precision__lte=6), name='operation_report_precision_valid'),
            models.UniqueConstraint(fields=('company', 'request_key_hash'), name='operation_report_request_unique'),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding or not getattr(self, '_business_state_initialization_authorized', False):
            raise ValidationError('正式报工只能通过正式事务服务首次保存，提交后不可改写。')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('正式报工记录及历史不可删除。')
