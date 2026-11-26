"""Explicit target-bound configuration through formal permission and workflow authorities."""
from pathlib import Path
from django.conf import settings
from django.db import transaction
from pfm.models import Employee
from system.models import User,Permission,Role,RolePermission,UserRoleScopeAssignment,OrganizationOperatingAuditRecord
from workflow_runtime.models import ProcessDefinition,WorkflowNodeDefinition,SegregationOfDutiesAuthority
from .design_revision_approval_service import PROCESS,DOCUMENT,PREFIX,digest,audit
from system.authorization import AuthorizationService

def configuration_plan(*,company_id,bindings):
    """Read-only deployment plan; no identities or grants are imported from a fixture."""
    if set(bindings)!={'submit','approve','save','confirm'}:
        raise RuntimeError('Exactly four responsibility bindings are required.')
    checked={}
    for responsibility,identity in bindings.items():
        user=User.objects.get(username=identity['username'],real_name=identity['name'],company_id=company_id,is_active=True,is_superuser=False,is_staff=False)
        employee=Employee.objects.get(user=user,status='active')
        if employee.full_name!=identity['name'] or _employee_company_id(employee)!=company_id:
            raise RuntimeError('Employee/company mismatch')
        checked[responsibility]=user
    if len({u.pk for u in checked.values()})!=4:
        raise RuntimeError('Responsibilities must use different users')
    for responsibility,permission in [('save','production.engineering.baseline.save'),('confirm','production.engineering.baseline.confirm')]:
        if not AuthorizationService.decide(user=checked[responsibility],action_code=permission,organization_id=company_id)['allowed']:
            raise RuntimeError('Existing responsibility permission missing: '+responsibility)
    for responsibility,suffix,actions in [('submit','submitter',{'submit'}),('approve','approver',{'approve','revoke'})]:
        role=Role.objects.filter(code='design_revision_'+suffix).first()
        if role:
            if role.user_scope_assignments.exclude(user=checked[responsibility],organization_id=company_id).exists():
                raise RuntimeError('Dedicated role is already shared; refusing expansion')
            actual=set(RolePermission.objects.filter(role=role).values_list('permission__code',flat=True))
            if actual-{PREFIX+a for a in actions}:
                raise RuntimeError('Dedicated role contains unrelated permissions')
            if role.user_scope_assignments.filter(active=False).exists():
                raise RuntimeError('Existing responsibility assignment is inactive')
            if role.user_scope_assignments.exclude(scope_code='ORGANIZATION').exists():
                raise RuntimeError('Existing responsibility scope differs from the reviewed organization scope')
    config={'code':PROCESS,'document':DOCUMENT,'version':1,'approvalPermission':PREFIX+'approve','sod':'applicant_cannot_approve'}
    process=ProcessDefinition.objects.filter(definition_code=PROCESS).first()
    if process:
        from .design_revision_approval_service import process_fingerprint
        if process.version!=1 or not process.active or process.document_type!=DOCUMENT or process.definition_hash!=digest(config):
            raise RuntimeError('Existing workflow definition differs from the reviewed contract')
        process_fingerprint(process)
    plan={'contract':'PCE-DESIGN-APPROVAL-CONFIGURATION-V1','database':str(Path(settings.DATABASES['default']['NAME']).resolve()),'companyId':company_id,'bindings':bindings,'userIds':{k:u.pk for k,u in checked.items()},'processHash':digest(config),'permissionsToEnsure':{PREFIX+'submit':'submit',PREFIX+'approve':'approve',PREFIX+'revoke':'approve'},'businessRecordsImported':0}
    return {**plan,'planHash':digest(plan)}
from .product_design_service import _employee_company_id

@transaction.atomic
def configure(*,company_id,bindings,expected_database=None,expected_plan_hash=None):
    target=Path(settings.DATABASES['default']['NAME']).resolve()
    isolated_roots={'pde-design-approval-implementation','pce-main-integration-candidate'}
    reviewed_target=expected_database is not None and Path(expected_database).resolve()==target and bool(expected_plan_hash)
    if not reviewed_target and (target.name!='design-approval-isolated.sqlite3' or not isolated_roots.intersection(target.parts)):
        raise RuntimeError('Approval configuration is restricted to the explicitly authorized independent database.')
    plan=configuration_plan(company_id=company_id,bindings=bindings)
    if expected_database is not None and (not reviewed_target or expected_plan_hash!=plan['planHash']):
        raise RuntimeError('Reviewed target database or configuration plan hash does not match.')
    actions={'submit':('submit',),'approve':('approve','revoke')}
    checked={}
    for responsibility,identity in bindings.items():
        user=User.objects.get(username=identity['username'],real_name=identity['name'],company_id=company_id,is_active=True,is_superuser=False,is_staff=False)
        employee=Employee.objects.select_related('position_ref','department_ref').get(user=user,status='active')
        if employee.full_name!=identity['name'] or _employee_company_id(employee)!=company_id:raise RuntimeError('Employee/company mismatch')
        checked[responsibility]=user
    if len({x.pk for x in checked.values()})!=len(checked):raise RuntimeError('Responsibilities must use different users')
    for role_name,permissions in actions.items():
        role,_=Role.objects.get_or_create(code='design_revision_'+('approver' if role_name=='approve' else 'submitter'),defaults={'name':'设计修订资料'+('批准专岗' if role_name=='approve' else '提交专岗'),'description':'精确修订资料批准专用角色，不扩共享角色'})
        if role.user_scope_assignments.exists():
            if role.user_scope_assignments.exclude(user=checked[role_name],organization_id=company_id).exists():raise RuntimeError('Dedicated role is already shared; refusing expansion')
        for action in permissions:
            permission,_=Permission.objects.get_or_create(code=PREFIX+action,defaults={'name':{'submit':'提交设计资料批准','approve':'批准或拒绝设计资料','revoke':'撤销设计资料批准'}[action],'module':'PDE'})
            RolePermission.objects.get_or_create(role=role,permission=permission)
        UserRoleScopeAssignment.objects.get_or_create(user=checked[role_name],role=role,organization_id=company_id,defaults={'scope_code':'ORGANIZATION','active':True,'business_hash':digest({'user':checked[role_name].pk,'role':role.code,'company':company_id})})
    config={'code':PROCESS,'document':DOCUMENT,'version':1,'approvalPermission':PREFIX+'approve','sod':'applicant_cannot_approve'}
    process,_=ProcessDefinition.objects.get_or_create(definition_code=PROCESS,defaults={'definition_name':'设计修订资料批准','business_domain':'PDE','document_type':DOCUMENT,'version':1,'active':True,'definition_hash':digest(config)})
    WorkflowNodeDefinition.objects.get_or_create(process_definition=process,node_code='EXACT_REVISION_APPROVAL',defaults={'node_name':'精确设计修订资料批准','sequence':1,'business_action_code':PREFIX+'approve','active':True})
    SegregationOfDutiesAuthority.objects.get_or_create(document_type=DOCUMENT,defaults={'applicant_cannot_approve':True,'same_user_restriction':True,'required_role_separation':True,'business_hash':digest(config)})
    if not OrganizationOperatingAuditRecord.objects.filter(action_code=PREFIX+'configure',organization_id=company_id,after_snapshot__configurationPlanHash=plan['planHash']).exists():
        audit(checked['submit'],'configure',process.pk,'显式受控配置设计资料批准职责；不导入业务记录',{'bindings':{k:v.pk for k,v in checked.items()},'processHash':process.definition_hash,'configurationPlanHash':plan['planHash']})
    return checked
