"""Separate output confirmation authority; no permission is granted here."""
CONTRACT = 'PCE-PRODUCTION-OPERATION-OUTPUT-V1'
MODULE = 'production-operation-output'
GET_PATH = '/api/planning/operation-outputs/'
ACTIONS = {
    'read': ('production.operation.output.read', '读取产出事实'),
    'confirm': ('production.operation.output.confirm', '确认本批实际产出'),
    'excess.report': ('production.operation.output.excess.report', '提交超计划补充报工'),
    'excess.review': ('production.operation.output.excess.review', '审核超计划补充报工'),
    'correct': ('production.operation.output.correct', '确认产出关联更正'),
}


def action_contract(key, object_id=None):
    from .operation_handover_contract import policy_contract
    code, label = ACTIONS[key]
    suffix = {'confirm': 'confirm/', 'excess.report': 'excess-reports/',
        'excess.review': f'excess-reports/{object_id}/review/', 'correct': 'corrections/'}
    path = None if key == 'excess.review' and object_id is None else GET_PATH + suffix[key] if key in suffix else GET_PATH
    return policy_contract(code, label, MODULE, 'planning.operation_output_service.execute_output', path, key)

