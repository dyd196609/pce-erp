"""Shared loss-parameter layer, independent of the unchanged engineering net rules."""
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError

class MaterialLossPolicyService:
    METHOD='PER_EDGE_ALLOWANCE'

    @staticmethod
    def per_edge_preview(net_quantity, segments, allowance_mm):
        def number(value):
            if isinstance(value,bool):raise ValidationError('布尔值不是长度或数量')
            try: n=Decimal(str(value))
            except (InvalidOperation,ValueError):raise ValidationError('无效数字')
            if not n.is_finite() or n<0:raise ValidationError('长度、数量和预留必须为非负有限值')
            return n
        if net_quantity is None or segments is None:
            return {'netQuantity':None if net_quantity is None else str(net_quantity),'edgeCount':None,
                'totalAllowanceM':None,'grossLengthM':None,'status':'BLOCKED_NET_OR_SEGMENTS'}
        net=number(net_quantity);total=Decimal(0);count=0
        for segment in segments:
            length=number(segment['netSegmentLengthMm']);qty=number(segment['quantityMultiplier'])
            if qty!=int(qty):raise ValidationError('逐边数量必须为整数')
            total+=length*qty/1000;count+=int(qty)
        if abs(total-net)>Decimal('0.00000000001'):
            raise ValidationError('边段净量与来源不一致，禁止进入损耗层')
        if allowance_mm is None:
            return {'netQuantity':str(net),'edgeCount':count,'totalAllowanceM':None,
                'grossLengthM':None,'status':'BLOCKED_PARAMETER_PENDING'}
        allowance=number(allowance_mm)*count/1000
        return {'netQuantity':str(net),'edgeCount':count,'totalAllowanceM':str(allowance),
            'grossLengthM':str(net+allowance),'status':'CALCULABLE_PREVIEW_NOT_ISSUED'}

    @classmethod
    def preview(cls, requirement):
        policy=requirement.loss_policy
        if policy is None or policy.method!=cls.METHOD:
            raise ValidationError('缺少同一逐边损耗策略')
        policy.full_clean()
        value=policy.allowance_mm if policy.parameter_status=='CONFIRMED' else None
        return cls.per_edge_preview(requirement.net_quantity,
            requirement.edge_segment_trace if requirement.edge_trace_status=='READY' else None,value)
