"""Existing administrative authority for master-data maintenance only."""
from django.core.exceptions import PermissionDenied

ADMIN_MAINTENANCE_ACTIONS=frozenset({
    'masterdata.customer.maintain','masterdata.supplier.maintain','production.master_data.unit.maintain',
    'production.master_data.material.maintain','production.master_data.capacity.maintain',
    'production.master_data.product.maintain','production.master_data.resource.maintain',
    'production.master_data.bom.maintain','production.master_data.routing.maintain',
    'production.master_data.location.maintain','production.engineering.version.maintain',
    'production.engineering.document.maintain',
    'production.engineering.rule.maintain','production.engineering.rule.create','production.engineering.rule.update_draft',
})

def maintenance_actor(user, *, action_code, organization_id, required_responsibility=None):
    from .production_foundation_service import _actor_chain,ProductionFoundationError
    from system.authorization import AuthorizationService
    if user.company_id!=organization_id:
        raise ProductionFoundationError('SCOPE_DENIED','维护对象不属于当前账号公司。')
    decision=AuthorizationService.decide(user=user,action_code=action_code,organization_id=organization_id,
        business_object={'organizationId':organization_id})
    if not decision.get('allowed'):
        raise ProductionFoundationError('PERMISSION_DENIED',decision.get('reason') or '当前账号没有该维护权限。')
    if (user.is_active and user.is_staff and user.is_superuser and action_code in ADMIN_MAINTENANCE_ACTIONS):
        return {'account':user.username,'userId':user.pk,'organizationId':organization_id,
            'identityType':'EXISTING_SYSTEM_ADMIN','identityLabel':'既有系统管理员账号',
            'employeeId':None,'positionId':None,'responsibilityId':None,
            'boundaryLabel':'仅主数据正常维护；不替代正式业务执行、评审、发布或职责分离'}
    return _actor_chain(user,required_responsibility=required_responsibility)
