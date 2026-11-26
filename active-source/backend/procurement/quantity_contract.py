"""Exact quantity presentation; preserve old expressions where no precision is lost."""
from decimal import Decimal


def quantity_text(value, legacy_places=4):
    if value is None:
        return None
    if isinstance(value, (float, bool)):
        raise ValueError('数量须由准确十进制事实提供，不能采用浮点数。')
    value = Decimal(value)
    if not value.is_finite():
        raise ValueError('数量必须有限。')
    quantum = Decimal(1).scaleb(-legacy_places)
    return format(value, f'.{legacy_places}f') if value == value.quantize(quantum) else format(value, 'f')


def exact_total(queryset, field='quantity'):
    return sum((value for value in queryset.values_list(field, flat=True).iterator() if value is not None), Decimal('0'))
