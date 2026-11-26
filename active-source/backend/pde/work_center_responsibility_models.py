"""Exact WorkCenter duty scope, maintained through the formal governance service."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from workflow_runtime.state_models import BusinessStateManagedModel, BusinessStateManagedQuerySet

class ScopeQuerySet(BusinessStateManagedQuerySet):
    def update(self, **kwargs): raise ValidationError('工作中心责任范围只允许正式维护服务修改。')
    def bulk_update(self, *args, **kwargs): raise ValidationError('工作中心责任范围不可批量改写。')
    def delete(self): raise ValidationError('工作中心责任范围及审计不可删除。')

class WorkCenterResponsibilityScope(BusinessStateManagedModel):
    objects=ScopeQuerySet.as_manager()
    company=models.ForeignKey('system.Company',on_delete=models.PROTECT)
    work_center=models.ForeignKey('pde.WorkCenter',on_delete=models.PROTECT)
    workflow_responsibility=models.ForeignKey('system.PositionWorkflowResponsibility',on_delete=models.PROTECT)
    employee=models.ForeignKey('pfm.Employee',on_delete=models.PROTECT,null=True,blank=True)
    effective_from=models.DateField(null=True,blank=True)
    effective_to=models.DateField(null=True,blank=True)
    status=models.CharField(max_length=20,choices=(('active','生效'),('disabled','已停用')))
    version=models.PositiveIntegerField(default=0)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        db_table='pde_work_center_responsibility_scope'
        default_permissions=()
        constraints=[models.UniqueConstraint(fields=('company','work_center','workflow_responsibility'),name='wc_responsibility_unique'),
            models.CheckConstraint(condition=models.Q(status__in=('active','disabled')),name='wc_responsibility_state')]
    def save(self,*args,**kwargs):
        if self._state.adding:
            if not getattr(self,'_business_state_initialization_authorized',False): raise ValidationError('责任范围只能正式初始化。')
        elif not (getattr(self,'_business_state_transition_authorized',False) or getattr(self,'_scope_fields_authorized',False)):
            raise ValidationError('责任范围只能正式维护及状态转换。')
        return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs): raise ValidationError('责任范围及历史不可删除。')
