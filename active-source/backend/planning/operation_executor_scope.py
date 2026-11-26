"""Read the existing formal position/process or team/resource configuration."""
from django.utils import timezone
from system.models import ProcessTeamCapability
from pde.models import WorkCenterTeamAssignment
from .workshop_receipt_protocol import _effective


def executor_scope(position, *, company_id, workshop_id, operation_id, work_center_id=None):
    today = timezone.localdate() if timezone.is_aware(timezone.now()) else timezone.now().date()
    evidence = {'source': 'system.Position.process/team;system.ProcessTeamCapability;pde.WorkCenterTeamAssignment',
        'positionId': position.pk if position else None, 'companyId': company_id,
        'workshopId': workshop_id, 'operationId': operation_id, 'workCenterId': work_center_id,
        'processId': position.process_id if position else None, 'teamId': position.team_id if position else None,
        'capabilityIds': [], 'workCenterAssignmentIds': []}
    issues = []
    if not position or position.company_id != company_id:
        issues.append('执行岗位不属于本公司。')
    elif position.workshop_id != workshop_id:
        issues.append('执行岗位所属车间与本次任务车间不一致；品保等跨车间模式须保留正式职责边界。')
    elif position.process_id:
        if (position.process_id != operation_id or position.process.company_id != company_id
                or not _effective(position.process, today)):
            issues.append('执行岗位正式所属工序与本次任务工序不一致或已失效。')
    if position and position.team_id:
        team = position.team
        if (team.company_id != company_id or team.workshop_id != workshop_id
                or not _effective(team, today)):
            issues.append('执行岗位班组与本公司、任务车间或有效期不一致。')
        capabilities = [row for row in ProcessTeamCapability.objects.filter(team_id=team.pk,
            operation_id=operation_id).order_by('pk') if _effective(row, today)]
        evidence['capabilityIds'] = [row.pk for row in capabilities]
        if not capabilities:
            issues.append('执行岗位班组缺少本工序有效能力关系。')
        assignments = list(WorkCenterTeamAssignment.objects.filter(team_id=team.pk,
            work_center_id=work_center_id, is_active=True).order_by('pk')) if work_center_id else []
        evidence['workCenterAssignmentIds'] = [row.pk for row in assignments]
        if not assignments:
            issues.append('执行岗位班组未正式关联本次任务工作中心。')
    bound = bool(position and (position.process_id or position.team_id))
    if position and not bound:
        issues.append('执行岗位尚未维护正式所属工序或班组能力关系，请先通过岗位管理核实绑定。')
    return {**evidence, 'ready': not issues, 'bound': bound,
        'bindingMode': 'FORMAL_POSITION_CONFIGURATION' if bound else 'MISSING_FORMAL_BINDING',
        'statusLabel': '；'.join(issues) if issues else '岗位正式工序及工作中心范围匹配',
        'missingItems': issues}
