"""Order execution facts over a fixed standard route; no route/BOM versions."""
from django.db import models
from django.core.exceptions import ValidationError


class OrderRoutingExecutionArrangement(models.Model):
    company = models.ForeignKey('system.Company', on_delete=models.PROTECT)
    engineering_instance = models.ForeignKey('pde.OrderEngineeringInstance', on_delete=models.PROTECT)
    source_calculation = models.ForeignKey('pde.EngineeringCalculationRecord', on_delete=models.PROTECT)
    bom_version = models.ForeignKey('pde.BOMVersion', on_delete=models.PROTECT)
    routing_version = models.ForeignKey('pde.RoutingVersion', on_delete=models.PROTECT)
    usage_purpose = models.CharField(max_length=24, editable=False, choices=(('TEST_BUSINESS','测试业务'),('PRODUCTION_USE','生产业务')))
    status = models.CharField(max_length=16, default='draft', choices=(('draft','草稿'),('confirmed','已确认')))
    arrangement_revision = models.PositiveIntegerField(default=1)
    edit_version = models.PositiveIntegerField(default=1)
    predecessor = models.OneToOneField('self', on_delete=models.PROTECT, null=True, blank=True, related_name='successor')
    reference_proof = models.JSONField(default=dict)
    reference_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey('system.User', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table='pde_order_routing_execution_arrangement'
        default_permissions=()
        constraints=[
            models.UniqueConstraint(fields=('company','bom_version'),condition=models.Q(predecessor__isnull=True),name='pde_order_route_arr_root'),
            models.UniqueConstraint(fields=('company','bom_version','arrangement_revision'),name='pde_order_route_arr_revision'),
            models.CheckConstraint(condition=models.Q(usage_purpose__in=('TEST_BUSINESS','PRODUCTION_USE')),name='pde_order_route_arr_purpose'),
            models.CheckConstraint(condition=models.Q(status__in=('draft','confirmed')),name='pde_order_route_arr_status'),
        ]

    def save(self,*args,**kwargs):
        if not any(getattr(self,flag,False) for flag in ('_arrangement_write_authorized','_business_state_initialization_authorized','_business_state_transition_authorized')):
            raise ValidationError('订单工序执行安排只能由正常办理服务保存。')
        if self.pk:
            old=type(self).objects.get(pk=self.pk)
            if old.status!='draft' or old.manufacturing_outputs.exists():
                raise ValidationError('已确认或被下游引用的安排不可覆盖，请通过安排自身的受控修订办理。')
            if any(getattr(old,k)!=getattr(self,k) for k in ('company_id','engineering_instance_id','source_calculation_id','bom_version_id','usage_purpose','predecessor_id','arrangement_revision')):
                raise ValidationError('订单安排的来源、用途与自身沿革不可改写。')
        return super().save(*args,**kwargs)

    def delete(self,*args,**kwargs):
        raise ValidationError('订单工序安排及历史不可删除。')


class OrderRoutingExecutionDecision(models.Model):
    arrangement=models.ForeignKey(OrderRoutingExecutionArrangement,on_delete=models.PROTECT,related_name='decisions')
    routing_step=models.ForeignKey('pde.RoutingStep',on_delete=models.PROTECT)
    baseline_item=models.ForeignKey('pde.OrderEngineeringBaselineItem',on_delete=models.PROTECT,null=True,blank=True)
    decision=models.CharField(max_length=20,choices=(('REQUIRED','执行'),('NOT_APPLICABLE','不执行'),('PENDING','待核定')))
    basis=models.TextField()
    evidence_class=models.CharField(max_length=24,choices=(('USER_CONFIRMED','用户明确依据'),('TEST_ASSUMPTION','补拟测试假设'),('UNRESOLVED','依据待核定')))
    last_audit=models.ForeignKey('system.OrganizationOperatingAuditRecord',on_delete=models.PROTECT)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        db_table='pde_order_routing_execution_decision'
        default_permissions=()
        constraints=[
            models.UniqueConstraint(fields=('arrangement','routing_step','baseline_item'),condition=models.Q(baseline_item__isnull=False),name='pde_order_route_dec_object'),
            models.UniqueConstraint(fields=('arrangement','routing_step'),condition=models.Q(baseline_item__isnull=True),name='pde_order_route_dec_whole'),
            models.CheckConstraint(condition=models.Q(decision__in=('REQUIRED','NOT_APPLICABLE','PENDING')),name='pde_order_route_dec_value'),
        ]

    def clean(self):
        parent=self.arrangement
        if self.routing_step.routing_version_id!=parent.routing_version_id:
            raise ValidationError('订单安排只能引用所选标准版本已有步骤；缺项请到企业基础资料补正。')
        if self.baseline_item_id and (self.baseline_item.baseline_id!=parent.reference_proof['baselineId']
            or self.baseline_item.design_item.sales_order_item_id!=parent.source_calculation.sales_order_item_id):
            raise ValidationError('适用对象不属于此订单行的冻结工程来源。')

    def save(self,*args,**kwargs):
        if not getattr(self,'_arrangement_write_authorized',False) or self.arrangement.status!='draft' or self.arrangement.manufacturing_outputs.exists():
            raise ValidationError('当前安排不允许直接修改执行明细。')
        self.full_clean()
        return super().save(*args,**kwargs)
