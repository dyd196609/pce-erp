"""Add the native report node after start without granting or executing work."""
from django.db import transaction
from system.models import Permission
from workflow_runtime.definition_service import (
    WorkflowDefinitionCatalogService, WorkflowDefinitionOperatingService, serialize_definition,
)
from workflow_runtime.models import WorkflowNodeDefinition
from .work_order_workshop_receipt_catalog import _definition, _fail
from .operation_start_models import ProductionOperationStart
from .operation_report_models import ProductionOperationReport
from .operation_report_contract import READ_PERMISSION, REPORT_ACTION, WORKFLOW_NODE


PERMISSIONS = (
    {'code': READ_PERMISSION, 'name': '本人已开工任务报工查看', 'module': 'MES'},
    {'code': REPORT_ACTION, 'name': '本人已开工任务报工', 'module': 'MES'},
)


@transaction.atomic
def register_operation_report_configuration_catalog(*, user, reason, request_identity):
    reason, request_identity = str(reason or '').strip(), str(request_identity or '').strip()
    if not 2 <= len(reason) <= 300 or not 1 <= len(request_identity) <= 160:
        _fail('OPERATION_REPORT_CATALOG_REASON_REQUIRED', '报工目录登记须有明确原因及请求标识。')
    WorkflowDefinitionCatalogService.authorize(user)
    process = _definition(True)
    start = process.nodes.filter(node_code='PRODUCTION_OPERATION_START', active=True).first()
    if start is None or start.business_action_code != 'production.operation.start':
        _fail('OPERATION_REPORT_START_NODE_REQUIRED', '正式工序开工节点须先登记生效。')
    if WorkflowNodeDefinition.objects.filter(business_action_code=REPORT_ACTION, active=True,
            process_definition__active=True).exclude(process_definition=process, node_code=WORKFLOW_NODE).exists():
        _fail('OPERATION_REPORT_NODE_AUTHORITY_CONFLICT', '已有其他正式节点绑定报工动作，禁止重复登记。')
    node = process.nodes.filter(node_code=WORKFLOW_NODE).first()
    if node and (not node.active or node.node_name != '工序报工节点' or node.business_action_code != REPORT_ACTION
            or node.sequence != start.sequence + 1):
        _fail('OPERATION_REPORT_NODE_CONFLICT', '已有报工节点含义或顺序冲突，禁止覆盖。')
    if node is None and process.nodes.filter(sequence=start.sequence + 1).exists():
        _fail('OPERATION_REPORT_NEXT_NODE_OCCUPIED', '开工后已有正式节点，不得覆盖或跳过。')
    starts, reports = ProductionOperationStart.objects.count(), ProductionOperationReport.objects.count()
    created, audits = [], []
    for expected in PERMISSIONS:
        permission = Permission.objects.select_for_update().filter(code=expected['code']).first()
        if permission and (permission.name != expected['name'] or permission.module != expected['module']):
            _fail('OPERATION_REPORT_PERMISSION_CONFLICT', '已有同码报工权限含义冲突，禁止覆盖。')
        if permission is None:
            permission = Permission.objects.create(**expected)
            audit = WorkflowDefinitionOperatingService._audit(
                user=user, action='REGISTER_OPERATION_REPORT_PERMISSION', target=permission,
                target_type='Permission', label=permission.name, reason=reason, before={},
                after={'permission': {'id': permission.pk, **expected}, 'configurationOnly': True,
                    'ownFrozenStartedTasksOnly': True, 'requestIdentity': request_identity,
                    'actualStartCount': starts, 'actualReportCount': reports})
            created.append(permission.pk)
            audits.append(audit.pk)
    node_result = None
    if node is None:
        node_result = WorkflowDefinitionOperatingService.execute(
            user=user, action='SAVE_WORKFLOW_NODE', payload={
                'processDefinitionId': process.pk, 'nodeCode': WORKFLOW_NODE,
                'nodeName': '工序报工节点', 'businessActionCode': REPORT_ACTION,
                'sequence': start.sequence + 1, 'active': True,
                'description': '冻结执行人及实际开工人本人提交独立分次报工；累计不超任务量，不代报工、不完工或转移。',
                'reason': reason})
    process = _definition(True)
    return {'readbackVerified': True, 'definition': serialize_definition(process, include_nodes=True),
        'nodeId': process.nodes.get(node_code=WORKFLOW_NODE).pk,
        'permissionCreatedIds': created, 'auditIds': audits, 'workflowResult': node_result,
        'humanAuthorizationWriteCount': 0, 'actualStartCount': starts, 'actualReportCount': reports}
