"""Append a separate native scope for reports on a user's own started tasks."""
from types import SimpleNamespace
from django.db import transaction
from django.utils import timezone
from pfm.formal_employee import formal_employee_queryset
from system.access_control_views import AccessControlFoundationView, business_hash
from system.models import (
    Company, OrganizationOperatingAuditRecord, PositionResponsibility,
    PositionWorkflowResponsibility, Role, RolePermission, User, UserRoleScopeAssignment,
)
from workflow_runtime.definition_service import WorkflowDefinitionCatalogService, WorkflowDefinitionError
from workflow_runtime.models import WorkflowNodeDefinition
from .mes_test_source_bridge import _effective
from .operation_start_models import ProductionOperationStart
from .operation_report_models import ProductionOperationReport
from .operation_report_contract import READ_PERMISSION, REPORT_ACTION, PROCESS, WORKFLOW_NODE, RESPONSIBILITY


def _fail(code, message):
    raise WorkflowDefinitionError(code, message, http_status=409)


@transaction.atomic
def append_operation_report_authority(*, user, account_id, role_id, reason, request_identity):
    """Require a report-only role and preserve every pre-existing scope row.

    The native company scope is necessary but insufficient to execute reports.
    The report service rechecks the frozen employee, account and position plus
    the actual starter for each read/write. This adds no proxy or chief grant.
    """
    WorkflowDefinitionCatalogService.authorize(user)
    denied = AccessControlFoundationView()._admin_guard(SimpleNamespace(user=user))
    if denied is not None:
        error = denied.data['error']
        raise WorkflowDefinitionError(error['code'], error['message'], http_status=403)
    reason, request_identity = str(reason or '').strip(), str(request_identity or '').strip()
    if not 2 <= len(reason) <= 300 or not 1 <= len(request_identity) <= 160:
        _fail('OPERATION_REPORT_AUTHORITY_REQUEST_REQUIRED', '报工授权维护须有明确原因及唯一请求标识。')
    if type(account_id) is not int or type(role_id) is not int or min(account_id, role_id) <= 0:
        _fail('OPERATION_REPORT_AUTHORITY_ID_INVALID', '请选择有效的既有账号和普通角色。')
    if not Company.objects.filter(pk=user.company_id, is_active=True).exists():
        _fail('OPERATION_REPORT_AUTHORITY_COMPANY_INACTIVE', '当前公司未启用，不能维护报工授权。')
    account = User.objects.only('id', 'username', 'real_name', 'company_id', 'is_active', 'is_superuser')\
        .select_for_update().filter(pk=account_id, company_id=user.company_id,
            is_active=True, is_superuser=False).first()
    role = Role.objects.select_for_update().filter(pk=role_id).first()
    if account is None or role is None:
        _fail('OPERATION_REPORT_AUTHORITY_ACCOUNT_INVALID', '报工授权须关联本公司启用的既有普通账号及角色。')
    permissions = set(RolePermission.objects.filter(role=role).values_list('permission__code', flat=True))
    if permissions != {READ_PERMISSION, REPORT_ACTION}:
        _fail('OPERATION_REPORT_AUTHORITY_ROLE_BOUNDARY', '报工专用角色必须且仅包含本人已开工任务查看和报工权限。')
    employees = list(formal_employee_queryset(company_id=user.company_id).filter(user_id=account.pk)
        .select_related('position_ref__workshop', 'department_ref')[:2])
    employee = employees[0] if len(employees) == 1 else None
    now = timezone.now()
    today = timezone.localdate(now) if timezone.is_aware(now) else now.date()
    position = employee.position_ref if employee else None
    department = employee.department_ref if employee else None
    if not (employee and _effective(position, today) and _effective(department, today)
            and position.company_id == department.company_id == user.company_id
            and position.department_id == department.pk and position.workshop_id
            and position.workshop.is_active and position.workshop.company_id == user.company_id
            and (employee.hire_date is None or employee.hire_date <= today)
            and (employee.leave_date is None or employee.leave_date > today)
            and (employee.resignation_date is None or employee.resignation_date > today)):
        _fail('OPERATION_REPORT_AUTHORITY_EMPLOYMENT_REQUIRED', '账号须有唯一有效任职、同公司部门岗位及启用车间。')
    duties = list(PositionResponsibility.objects.filter(position=position, active=True,
        responsibility__code=RESPONSIBILITY, responsibility__status='ACTIVE', responsibility__is_active=True)
        .select_related('responsibility'))
    node = WorkflowNodeDefinition.objects.filter(node_code=WORKFLOW_NODE, active=True,
        business_action_code=REPORT_ACTION, process_definition__definition_code=PROCESS,
        process_definition__active=True).first()
    if len(duties) != 1 or not _effective(duties[0].responsibility, today) or node is None:
        _fail('OPERATION_REPORT_AUTHORITY_DUTY_REQUIRED', '独立报工职责或正式报工节点尚未生效。')
    mappings = list(PositionWorkflowResponsibility.objects.filter(position=position,
        responsibility=duties[0].responsibility, workflow_node=node, workflow_code=PROCESS,
        node_code=WORKFLOW_NODE, ownership_type='EXECUTOR', active=True))
    if len(mappings) != 1 or not _effective(mappings[0], today):
        _fail('OPERATION_REPORT_AUTHORITY_NODE_EXECUTOR_REQUIRED', '岗位须有有效报工职责及精确报工节点执行关系。')
    preserved = list(UserRoleScopeAssignment.objects.filter(user=account).order_by('pk').values())
    preserved_ids = [row['id'] for row in preserved]
    payload = {'userId': account.pk, 'roleCode': role.code, 'legalEntityId': str(user.company_id),
        'departmentId': None, 'scopeCode': 'ORGANIZATION', 'version': 1}
    assignment, created = UserRoleScopeAssignment.objects.select_for_update().get_or_create(
        user=account, role=role, organization_id=user.company_id,
        defaults={'department': None, 'scope_code': 'ORGANIZATION', 'active': True,
            'version': 1, 'business_hash': business_hash(payload)})
    if not (assignment.active and assignment.scope_code == 'ORGANIZATION' and assignment.department_id is None
            and assignment.business_hash == business_hash(payload) and assignment.version == 1):
        _fail('OPERATION_REPORT_AUTHORITY_EXISTING_CONFLICT', '既有同角色范围不同，禁止静默覆盖。')
    for old in preserved:
        if UserRoleScopeAssignment.objects.filter(pk=old['id']).values().get() != old:
            _fail('OPERATION_REPORT_AUTHORITY_HISTORY_CHANGED', '历史授权发生变化，禁止保存报工授权。')
    starts, reports = ProductionOperationStart.objects.count(), ProductionOperationReport.objects.count()
    audit = None
    if created:
        audit = OrganizationOperatingAuditRecord.objects.create(actor=user, organization_id=user.company_id,
            action_code='APPEND_OPERATION_REPORT_AUTHORITY', target_type='User', target_id=account.pk,
            target_label=f'{account.username} - {account.real_name}', reason=reason,
            before_snapshot={'preservedAuthorityIds': preserved_ids},
            after_snapshot={'authority': {**payload, 'id': assignment.pk, 'businessHash': assignment.business_hash},
                'permissionCodes': sorted(permissions), 'requestIdentity': request_identity,
                'positionId': position.pk, 'workshopId': position.workshop_id, 'employeeId': employee.pk,
                'workflowNodeId': node.pk, 'ownershipType': 'EXECUTOR', 'configurationOnly': True,
                'dataConstraint': 'OWN_FROZEN_STARTED_TASKS', 'preservedAuthorityIds': preserved_ids,
                'actualStartCount': starts, 'actualReportCount': reports})
    return {'accountId': account.pk, 'username': account.username, 'employeeId': employee.pk,
        'roleId': role.pk, 'roleCode': role.code, 'authorityId': assignment.pk, 'authorityCreated': created,
        'auditId': audit.pk if audit else None, 'preservedAuthorityIds': preserved_ids,
        'permissionCodes': sorted(permissions), 'positionId': position.pk, 'workshopId': position.workshop_id,
        'dataConstraint': 'OWN_FROZEN_STARTED_TASKS', 'configurationWriteCount': 2 if created else 0,
        'actualStartCount': starts, 'actualReportCount': reports}
