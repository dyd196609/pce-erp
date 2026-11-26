"""Immutable per-workshop acknowledgement; never changes the released work order."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from workflow_runtime.state_models import BusinessStateManagedModel, BusinessStateManagedQuerySet


class WorkshopReceiptQuerySet(BusinessStateManagedQuerySet):
    def update(self, **kwargs):
        raise ValidationError("已保存车间接收记录不可改写。")

    def bulk_update(self, *args, **kwargs):
        raise ValidationError("已保存车间接收记录不可批量改写。")

    def delete(self):
        raise ValidationError("正式车间接收记录不可删除。")


class ProductionWorkOrderWorkshopReceipt(BusinessStateManagedModel):
    objects = WorkshopReceiptQuerySet.as_manager()
    company = models.ForeignKey("system.Company", on_delete=models.PROTECT)
    work_order = models.ForeignKey("planning.ProductionWorkOrder", on_delete=models.PROTECT, related_name="workshop_receipts")
    workshop = models.ForeignKey("system.Workshop", on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=(("received", "本车间工序已接收"),), default="received")
    version = models.PositiveIntegerField(default=0)
    work_order_version = models.PositiveIntegerField()
    work_order_snapshot_hash = models.CharField(max_length=64)
    source_snapshot = models.JSONField()
    snapshot_hash = models.CharField(max_length=64)
    qualification_snapshot = models.JSONField()
    qualification_hash = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=120)
    request_hash = models.CharField(max_length=64)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="production_workshop_receipts")
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "planning_work_order_workshop_receipt"
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=("work_order", "workshop"), name="wo_workshop_receipt_unique"),
            models.UniqueConstraint(fields=("company", "idempotency_key"), name="wo_workshop_receipt_idem"),
            models.CheckConstraint(condition=models.Q(status="received"), name="wo_workshop_receipt_state"),
            models.CheckConstraint(condition=models.Q(version=0), name="wo_workshop_receipt_version"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("车间接收来源、范围、人员和结果不可改写。")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("正式车间接收记录不可删除。")
