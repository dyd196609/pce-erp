"""Explicit TEST segregation for the existing WMS tables, not another stock ledger."""
from contextvars import ContextVar
from contextlib import contextmanager
from django.db import models,connection
from django.core.exceptions import ValidationError

TEST='TEST_BUSINESS'
LEGACY='LEGACY_UNCLASSIFIED'
CHOICES=[(LEGACY,'历史用途未分类'),('PRODUCTION_USE','正式生产用途'),(TEST,'隔离测试用途')]
_write_scope=ContextVar('native_test_inventory_write',default=False)

@contextmanager
def test_purpose_write_scope():
    if not connection.in_atomic_block:raise ValidationError('测试资源及库存写入须在完整业务事务内。')
    token=_write_scope.set(True)
    try:yield
    finally:_write_scope.reset(token)

class PurposeQuerySet(models.QuerySet):
    def _guard(self,fields=()):
        lookup=getattr(self.model,'_test_purpose_lookup','usage_purpose')
        if self.filter(**{lookup:TEST}).exists():
            if not _write_scope.get() or self.model.__name__=='WarehouseInbound' and 'status' in fields:
                raise ValidationError('TEST对象只能由带来源、权限及审计的正常服务维护；入库状态须沿统一状态机。')
    def update(self,**kwargs):
        if 'usage_purpose' in kwargs:raise ValidationError('既有对象用途不可通过更新转换；须保留原来源并新建明确用途对象。')
        if self.model.__name__=='InventoryTransaction' and self.filter(usage_purpose=TEST).exists():
            raise ValidationError('TEST库存事务账不可覆盖。')
        self._guard(kwargs);return super().update(**kwargs)
    def delete(self):
        lookup=getattr(self.model,'_test_purpose_lookup','usage_purpose')
        if self.filter(**{lookup:TEST}).exists():raise ValidationError('TEST来源、资源及库存沿革不可删除。')
        return super().delete()
    def bulk_create(self,objs,**kwargs):
        objs=list(objs)
        if any(getattr(x,'usage_purpose',None)==TEST or self.model.__name__=='WarehouseLocation' and getattr(x.warehouse,'usage_purpose',None)==TEST for x in objs):
            raise ValidationError('TEST对象须逐笔沿真实业务服务建立，禁止批量绕过来源与审计。')
        return super().bulk_create(objs,**kwargs)
    def bulk_update(self,objs,fields,batch_size=None):
        if any(getattr(x,'usage_purpose',None)==TEST for x in objs):raise ValidationError('TEST库存及资源不得批量改写。')
        return super().bulk_update(objs,fields,batch_size=batch_size)

class PurposeManager(models.Manager.from_queryset(PurposeQuerySet)):
    def get_queryset(self):
        return super().get_queryset().exclude(**{getattr(self.model,'_test_purpose_lookup','usage_purpose'):TEST})

class PurposeSeparatedModel(models.Model):
    usage_purpose=models.CharField(max_length=32,choices=CHOICES,default=LEGACY)
    objects=PurposeManager()
    all_objects=PurposeQuerySet.as_manager()
    class Meta:
        abstract=True
        default_manager_name='objects'
        base_manager_name='all_objects'
    def save(self,*args,**kwargs):
        if self.pk and not self._state.adding:
            old=self.__class__.all_objects.filter(pk=self.pk).values_list('usage_purpose',flat=True).first()
            if old is not None and old!=self.usage_purpose:raise ValidationError('既有对象用途不得转换。')
        if self.usage_purpose==TEST and not _write_scope.get():
            raise ValidationError('TEST资源或库存写入须沿受控业务服务，不能直接制造入库成功。')
        if self.usage_purpose==TEST and self.__class__.__name__=='InventoryTransaction' and not self._state.adding:
            raise ValidationError('TEST库存事务账不可覆盖。')
        return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs):
        if self.usage_purpose==TEST:raise ValidationError('TEST来源及库存沿革不可删除。')
        return super().delete(*args,**kwargs)
