from django.conf import settings
from django.db import models

from workflow_runtime.state_models import BusinessStateManagedModel


class ProcurementEvidenceRisk(BusinessStateManagedModel):
    class Status(models.TextChoices):
        RECEIVED = "received", "已受理"
        PROCESSED = "processed", "待独立复核"
        CLOSED = "closed", "已关闭"

    difference = models.OneToOneField("reconciliation.PurchaseReconciliationDifference",
                                      on_delete=models.PROTECT)
    handler = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    disposition = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()


class OperationalEvidenceRisk(BusinessStateManagedModel):
    """Risk handling is independent of the state of the linked original record."""

    Status = ProcurementEvidenceRisk.Status
    task = models.OneToOneField("planning.ProductionWorkshopTask", on_delete=models.PROTECT,
                                null=True, blank=True)
    inspection = models.OneToOneField("procurement.PurchaseInspection", on_delete=models.PROTECT,
                                      null=True, blank=True)
    handler = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    source_evidence = models.JSONField()
    disposition = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(task__isnull=False, inspection__isnull=True)
                           | models.Q(task__isnull=True, inspection__isnull=False)),
                name="operational_risk_one_native_source",
            )
        ]
