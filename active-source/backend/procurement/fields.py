"""Exact native quantities with the original per-field read representation."""
from decimal import Decimal
from planning.fields import ExactDemandQuantityField


class ExactNativeQuantityField(ExactDemandQuantityField):
    def __init__(self,*args,legacy_decimal_places=4,**kwargs):
        self.legacy_decimal_places=legacy_decimal_places
        super().__init__(*args,**kwargs)

    def deconstruct(self):
        name,path,args,kwargs=super().deconstruct()
        kwargs['legacy_decimal_places']=self.legacy_decimal_places
        return name,path,args,kwargs

    def from_db_value(self,value,expression,connection):
        value=self._exact(value)
        if value is None:return None
        old=value.quantize(Decimal(1).scaleb(-self.legacy_decimal_places))
        return old if old==value else value
