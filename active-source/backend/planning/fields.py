"""Exact storage for the one approved Demand(20,6) quantity field.

SQLite NUMERIC affinity rounds a 20-digit decimal through binary REAL (and can
even round the largest valid quantity into a 15-digit integer). A fixed-width
decimal TEXT value keeps both exact storage and ordering for nonnegative demand
quantities. This is still one DecimalField, not an auxiliary quantity column.
"""
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.db import models


class ExactDemandQuantityField(models.DecimalField):
    def get_internal_type(self):
        # Avoid SQLite's DecimalField float converter; this field supplies its
        # own Decimal conversion. PostgreSQL's driver already returns Decimal.
        return 'CharField'

    def db_type(self, connection):
        return 'text' if connection.vendor=='sqlite' else f'numeric({self.max_digits},{self.decimal_places})'

    def _exact(self,value):
        if isinstance(value,float):
            raise ValidationError('需求数量不能通过二进制浮点数承接。')
        value=super().to_python(value)
        if value is None:return None
        quantum=Decimal(1).scaleb(-self.decimal_places)
        try:
            if not value.is_finite() or abs(value)>=Decimal(10)**(self.max_digits-self.decimal_places) or value!=value.quantize(quantum):
                raise ValueError()
            return value.quantize(quantum)
        except (InvalidOperation,ValueError):
            raise ValidationError('需求数量超出原整数容量或已批准的6位精度，不得舍入。')

    def get_db_prep_value(self,value,connection,prepared=False):
        value=self._exact(value)
        if value is None:return None
        if connection.vendor!='sqlite':return value
        width=self.max_digits+1
        return format(value,f'0{width}.{self.decimal_places}f')

    def from_db_value(self,value,expression,connection):
        return self._exact(value)
