"""Formal MES work orders; source schedules and reservations remain untouched."""
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from workflow_runtime.state_models import BusinessStateManagedModel, BusinessStateManagedQuerySet


class WorkOrderQuerySet(BusinessStateManagedQuerySet):
    def update(self, **kwargs):
        raise ValidationError("工单必须通过正式事务服务维护，不允许直接批量更新。")

    def bulk_update(self, *args, **kwargs):
        raise ValidationError("工单必须通过正式事务服务维护，不允许直接批量更新。")

    def delete(self):
        raise ValidationError("正式工单不可删除。")


class ProductionWorkOrder(BusinessStateManagedModel):
    objects = WorkOrderQuerySet.as_manager()
    STATUS_CHOICES = (("draft", "已生成，待下达"), ("released", "已下达"))
    company = models.ForeignKey("system.Company", on_delete=models.PROTECT)
    production_plan = models.OneToOneField("planning.ProductionPlan", on_delete=models.PROTECT, related_name="production_work_order", null=True, blank=True)
    usage_purpose = models.CharField(max_length=20, default="UNCLASSIFIED")
    source_schedule = models.ForeignKey("planning.FormalProductionSchedule", on_delete=models.PROTECT)
    no = models.CharField(max_length=80)
    material = models.ForeignKey("masterdata.Material", on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    uom = models.ForeignKey("masterdata.UnitOfMeasure", on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    version = models.PositiveIntegerField(default=0)
    source_snapshot = models.JSONField()
    snapshot_hash = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=120)
    request_hash = models.CharField(max_length=64)
    release_idempotency_key = models.CharField(max_length=120, blank=True, default="")
    release_request_hash = models.CharField(max_length=64, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="generated_production_work_orders")
    released_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="released_production_work_orders")
    released_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "planning_production_work_order"
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=("company", "no"), name="wo_company_no_unique"),
            models.UniqueConstraint(fields=("company", "idempotency_key"), name="wo_company_generation_idem"),
            models.UniqueConstraint(fields=("company", "release_idempotency_key"), condition=~models.Q(release_idempotency_key=""), name="wo_company_release_idem"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="wo_quantity_positive"),
            models.CheckConstraint(condition=(models.Q(usage_purpose="PRODUCTION_USE",production_plan__isnull=False)|models.Q(usage_purpose="TEST_BUSINESS",production_plan__isnull=True)|models.Q(usage_purpose="UNCLASSIFIED")),name="wo_purpose_plan_branch"),
            models.UniqueConstraint(fields=("source_schedule",),condition=models.Q(usage_purpose="TEST_BUSINESS"),name="test_wo_source_schedule_unique"),
            models.CheckConstraint(condition=models.Q(status__in=("draft", "released")), name="wo_allowed_status"),
        ]

    def save(self, *args, **kwargs):
        # Preserve the existing formal writer's constructor contract: it never
        # accepted a caller-supplied purpose. Derive only for an authorized NEW
        # initialization with the exact persisted formal parent and snapshot.
        # Historical/uncertain records are never defaulted to formal.
        if self._state.adding and getattr(self, '_business_state_initialization_authorized', False):
            self.usage_purpose = self.source_purpose()
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).values().first()
            immutable = ("usage_purpose", "company_id", "production_plan_id", "source_schedule_id", "no", "material_id", "quantity", "uom_id",
                "source_snapshot", "snapshot_hash", "idempotency_key", "request_hash", "created_by_id", "created_at")
            if original and any(original[key] != getattr(self, key) for key in immutable):
                raise ValidationError("已生成工单的正式来源、数量、单位与编号不可改写。")
        return super().save(*args, **kwargs)

    def source_purpose(self):
        if self.usage_purpose != 'UNCLASSIFIED' or not self.production_plan_id:
            return self.usage_purpose
        parent = self.source_schedule
        source = self.source_snapshot or {}
        if (parent.usage_purpose == 'PRODUCTION_USE' and parent.company_id == self.company_id
                and parent.production_plan_id == self.production_plan_id
                and source.get('companyId') == self.company_id
                and source.get('productionPlanId') == self.production_plan_id
                and source.get('sourceSchedule', {}).get('id') == parent.pk
                and source.get('sourceSchedule', {}).get('snapshotHash') == parent.snapshot_hash):
            return 'PRODUCTION_USE'
        return 'UNCLASSIFIED'

    def delete(self, *args, **kwargs):
        raise ValidationError("正式工单不可删除。")


class ImmutableWorkOrderOperationQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("工单工序来源明细不可编辑。")

    def delete(self):
        raise ValidationError("工单工序来源明细不可删除。")


class ProductionWorkOrderOperation(models.Model):
    objects = ImmutableWorkOrderOperationQuerySet.as_manager()
    work_order = models.ForeignKey(ProductionWorkOrder, on_delete=models.PROTECT, related_name="operations")
    sequence = models.PositiveIntegerField()
    root_step = models.ForeignKey("pde.RoutingStep", on_delete=models.PROTECT, related_name="root_work_order_operations")
    effective_step = models.ForeignKey("pde.RoutingStep", on_delete=models.PROTECT, related_name="effective_work_order_operations")
    root_routing_version = models.ForeignKey("pde.RoutingVersion", on_delete=models.PROTECT, related_name="root_work_order_operations")
    effective_routing_version = models.ForeignKey("pde.RoutingVersion", on_delete=models.PROTECT, related_name="effective_work_order_operations")
    operation = models.ForeignKey("system.Process", on_delete=models.PROTECT)
    work_center = models.ForeignKey("pde.WorkCenter", on_delete=models.PROTECT, null=True, blank=True)
    dependency_only = models.BooleanField(default=False)
    workload_quantity = models.CharField(max_length=100, null=True, blank=True)
    workload_uom = models.ForeignKey("masterdata.UnitOfMeasure", on_delete=models.PROTECT, null=True, blank=True)
    source_snapshot = models.JSONField()
    snapshot_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "planning_production_work_order_operation"
        default_permissions = ()
        ordering = ("work_order_id", "sequence")
        constraints = [
            models.UniqueConstraint(fields=("work_order", "sequence"), name="wo_operation_sequence_unique"),
            models.UniqueConstraint(fields=("work_order", "root_step"), name="wo_operation_root_unique"),
            models.CheckConstraint(condition=(models.Q(workload_quantity__isnull=True, workload_uom__isnull=True)
                | models.Q(workload_quantity__isnull=False, workload_uom__isnull=False)), name="wo_workload_uom_pair"),
        ]

    def clean(self):
        if self.workload_quantity is not None:
            try:
                value = Decimal(self.workload_quantity)
            except (InvalidOperation, TypeError):
                raise ValidationError("工序作业量必须是正式来源的有效十进制数。")
            if not value.is_finite() or value <= 0:
                raise ValidationError("工序作业量必须大于0；未定量保持为空。")
        if self.dependency_only and self.source_snapshot.get("processingMinutes") is not None:
            raise ValidationError("依赖承接节点不得伪造加工时长。")

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("工单工序来源明细不可改写。")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("工单工序来源明细不可删除。")
