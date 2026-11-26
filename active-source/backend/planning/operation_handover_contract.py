"""Native output/custody action contracts, consumed by HTTP and the UI."""
CONTRACT = 'PCE-PRODUCTION-OPERATION-HANDOVER-V1'
MODULE = 'production-operation-handover'
GET_PATH = '/api/planning/operation-handovers/'
ACTIONS = {key: ('production.operation.handover.' + key, label) for key, label in (
    ('read', '读取工序交接事实'), ('prepare', '确认备交并占用份额'),
    ('dispatch', '确认实际交出'), ('cancel', '取消尚未交出的备交'),
    ('receive', '确认本次实际收讫'), ('forward', '备交转送'), ('return', '备交退回'),
    ('exception.submit', '登记关联异常'), ('exception.confirm', '确认异常处置'),
    ('input.confirm', '确认实际投入范围'),
    ('range.release', '确认已有批次范围用途'),
)}


def policy_contract(code, label, module, validator, path, key):
    from system.models import RolePermission
    from workflow_runtime.action_permissions import ActionPermissionPolicy, POLICIES
    from system.authorization_read_inputs import current_inputs
    inputs=current_inputs();roles=inputs.policy_roles(code) if inputs is not None else NotImplemented
    if roles is NotImplemented:
        roles = tuple(RolePermission.objects.filter(permission__code=code).order_by('role__code')
                      .values_list('role__code', flat=True).distinct())
    states = ('open', 'declared', 'pending', 'confirmed', 'prepared', 'in_transit',
              'partially_received', 'discrepancy_pending', 'U', 'S', 'V', 'Q')
    policy = ActionPermissionPolicy(actionCode=code, moduleCode=module, requiredPermission=code,
        role=roles, organizationScope='legal_entity', serverValidator=validator,
        allowedStatuses=states, scope='single')
    prior = POLICIES.get((module, code))
    if prior and (prior.serverValidator != validator or prior.requiredPermission != code):
        raise RuntimeError('工序交接动作身份冲突，禁止覆盖。')
    POLICIES[(module, code)] = policy
    return {**policy.serialize(), 'key': key, 'displayName': label, 'apiPath': path,
        'httpMethod': 'GET' if key == 'read' else 'POST', 'processCode': 'MES_OPERATION_HANDOVER',
        'workflowProcessCode': 'MES_OPERATION_HANDOVER', 'businessProcessCode': 'MES_PRODUCTION_OPERATION',
        'sameRolePermissionAndScopeRequired': True, 'currentStateSource': 'server',
        'manualExecutionSupported': True, 'executionEnabled': key != 'read'}


def action_contract(key, object_id=None):
    code, label = ACTIONS[key]
    suffix = {'prepare': 'prepare/', 'forward': 'forward/', 'return': 'return/',
        'exception.submit': 'exceptions/', 'exception.confirm': f'exceptions/{object_id}/resolve/',
        'input.confirm': 'inputs/confirm/', 'range.release':'ranges/release/'}
    requires_object = key in ('dispatch', 'cancel', 'receive', 'exception.confirm')
    path = None if requires_object and object_id is None else GET_PATH if key == 'read' else GET_PATH + suffix.get(key, f'{object_id}/{key}/')
    return policy_contract(code, label, MODULE, 'planning.operation_handover_service.execute_handover', path, key)

