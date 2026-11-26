from django.core.exceptions import ValidationError
from django.db import models


class BusinessStateManagedQuerySet(models.QuerySet):
    """Block ORM shortcuts that bypass the business-state transition service."""

    def update(self, **kwargs):
        if "status" in kwargs:
            raise ValidationError(
                f"{self.model.__name__} status must use BusinessStateTransition"
            )
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        if "status" in fields:
            raise ValidationError(
                f"{self.model.__name__} status must use BusinessStateTransition"
            )
        return super().bulk_update(objs, fields, batch_size=batch_size)

    def bulk_create(self, objs, **kwargs):
        if objs:
            raise ValidationError(
                f"{self.model.__name__} initial status must use state initialization service"
            )
        return super().bulk_create(objs, **kwargs)


class BusinessStateManagedModel(models.Model):
    """Abstract guard for business objects governed by BusinessStateTransition."""

    objects = BusinessStateManagedQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        status_field = self._meta.get_field("status")
        if (
            not self.pk
            and getattr(self, status_field.attname)
            and not getattr(self, "_business_state_initialization_authorized", False)
        ):
            raise ValidationError(
                f"{type(self).__name__} initial status must use state initialization service"
            )
        if self.pk:
            persisted = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list(status_field.attname, flat=True)
                .first()
            )
            if (
                persisted is not None
                and persisted != getattr(self, status_field.attname)
                and not getattr(self, "_business_state_transition_authorized", False)
            ):
                raise ValidationError(
                    f"{type(self).__name__} status must use BusinessStateTransition"
                )
        return super().save(*args, **kwargs)


__all__ = [
    "BusinessStateManagedModel",
    "BusinessStateManagedQuerySet",
]
