"""Display Django-local task timestamps without changing scheduling semantics."""
from django.utils import timezone


def task_datetime_label(value, zone):
    """Label one task timestamp, preserving its stored value and actual instant.

    Task lifecycle fields use Django's normal datetime storage. Under USE_TZ=False
    their naive values belong to the configured default timezone. They must not
    use the UTC-naive interpretation reserved for formal scheduling intervals.
    """
    if value is None:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_default_timezone())
    # Reuse the existing display projection only after the instant is explicit.
    from .workshop_receipt_protocol import formal
    _label = formal._label
    return _label(value, zone)
