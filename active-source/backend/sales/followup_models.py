from django.conf import settings
from django.db import models


class ProductionFollowupAssignment(models.Model):
    """Current production follow-up responsibility and its concurrency token."""
    order = models.OneToOneField("sales.SalesOrder", on_delete=models.PROTECT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    version = models.PositiveIntegerField(default=1)
    effective_at = models.DateTimeField()

    class Meta:
        default_permissions = ()


class CustomerAccountBinding(models.Model):
    """Only dedicated external accounts can enter the customer portal."""
    account = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    customer = models.ForeignKey("sales.Customer", on_delete=models.PROTECT)
    effective_at = models.DateTimeField()

    class Meta:
        default_permissions = ()


class CustomerProgressPublication(models.Model):
    order = models.ForeignKey("sales.SalesOrder", on_delete=models.PROTECT)
    source = models.OneToOneField("workflow_runtime.BusinessStateTransition", on_delete=models.PROTECT)
    published_at = models.DateTimeField()

    class Meta:
        default_permissions = ()
