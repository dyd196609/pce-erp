from dataclasses import replace
from threading import RLock
from .work_order_release_admission_contract import MODULE,ACTION as REQUIRED_PERMISSION

ACTION='production.operation_source.continue'
_lock=RLock()
_owned=None

def register_action():
    global _owned
    from system.models import RolePermission
    from workflow_runtime.action_permissions import ActionPermissionPolicy,POLICIES
    with _lock:
        roles=tuple(RolePermission.objects.filter(permission__code=REQUIRED_PERMISSION)
            .order_by('role__code').values_list('role__code',flat=True).distinct())
        policy=ActionPermissionPolicy(actionCode=ACTION,moduleCode=MODULE,requiredPermission=REQUIRED_PERMISSION,
            role=roles,organizationScope='legal_entity',scope='single',allowedStatuses=('confirmed',),
            serverValidator='planning.operation_continuation_service.record_route_plan')
        old=POLICIES.get((MODULE,ACTION))
        if old is not None and old!=policy and (old is not _owned or replace(old,role=roles)!=policy):
            raise RuntimeError('正式承接动作契约冲突，禁止覆盖。')
        POLICIES[(MODULE,ACTION)]=policy;_owned=policy
        return policy
