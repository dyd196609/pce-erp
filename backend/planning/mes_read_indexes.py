"""One GET/reader/company/epoch raw authority index, never decisions."""
from contextlib import contextmanager
from copy import deepcopy

def _state(actor):
    from pde.routing_read_context import _current
    from .operation_predecessor_authority import _context,_proof_cache_epoch
    request,context=_current.get(),_context.get()
    if not request or request.get('__http_get_read__') is not True or context is None:return None
    if not getattr(actor,'pk',None) or not getattr(actor,'company_id',None):return None
    epoch=_proof_cache_epoch(context)
    if epoch is None:return None
    key=('mes_authority_inputs',epoch,actor.pk,actor.company_id)
    if key not in request:request[key]={'grants':{},'complete_roles':set(),'complete_permissions':set(),'raw':{}}
    return request[key]

def _formal(state,actor):
    from system.models import UserRoleScopeAssignment
    if 'formal' not in state:
        # Native fallback depends on ALL formal assignments, not a company subset.
        state['formal']=list(UserRoleScopeAssignment.objects.filter(user=actor,active=True)
            .select_related('role','organization','department'))
    return state['formal']

def _grants(state,codes,kind):
    from system.models import RolePermission
    from django.db import connection
    missing=set(codes)-state['complete_'+kind]
    if not missing:return
    field='role__code__in' if kind=='roles' else 'permission__code__in'
    limit=connection.features.max_query_params or 1000
    width=max(1,limit//2);values=sorted(missing);loaded={}
    for offset in range(0,len(values),width):
        group=values[offset:offset+width]
        rows=RolePermission.objects.filter(**{field:group}).select_related('role','permission')
        known=list(state['grants'])
        if known and len(known)+len(group)<limit:rows=rows.exclude(pk__in=known)
        loaded.update((row.pk,row) for row in rows)
    state['grants'].update(loaded);state['complete_'+kind].update(missing)

def authority_inputs(actor):
    state=_state(actor)
    if state is None:return None
    rows=sorted((r for r in _formal(state,actor) if r.organization_id==actor.company_id
        and r.organization.is_active),key=lambda r:(r.role.code,r.pk))
    ids={r.role_id for r in rows};_grants(state,{r.role.code for r in rows},'roles')
    by_permission={}
    for row in state['grants'].values():
        if row.role_id in ids:by_permission.setdefault(row.permission.code,{})[row.role_id]=row
    return rows,by_permission

def _fields(row):
    if row is None:return None
    deferred=row.get_deferred_fields()
    return tuple((f.attname,repr(getattr(row,f.attname))) for f in row._meta.concrete_fields if f.attname not in deferred)

class RawAuthorityInputs:
    def __init__(self,reader):self.reader=reader
    def actor(self,user):
        from system.models import User
        state=_state(user)
        if state is None:return NotImplemented
        if 'actor' not in state['raw']:state['raw']['actor']=User.objects.get(pk=user.pk)
        return deepcopy(state['raw']['actor'])
    def company(self,user,organization_id):
        from system.models import Company
        state=_state(user)
        if state is None:return NotImplemented
        key=('company',str(organization_id));saved=state['raw'].get(key)
        if saved is None or _fields(saved[0])!=saved[1]:
            row=Company.objects.filter(pk=organization_id).only('id','is_active','code','name').first()
            saved=(row,_fields(row));state['raw'][key]=saved
        return saved[0]
    def formal(self,user):
        state=_state(user)
        return NotImplemented if state is None else _formal(state,user)
    def legacy(self,user,organization_id):
        from workflow_runtime.models import UserOrganizationRoleAuthority
        state=_state(user)
        if state is None:return NotImplemented
        key=('legacy',str(organization_id))
        if key not in state['raw']:
            rows=UserOrganizationRoleAuthority.objects.filter(user=user,active=True)
            if organization_id:rows=rows.filter(legal_entity_id=organization_id)
            state['raw'][key]=list(rows)
        return state['raw'][key]
    def permissions(self,user,role_codes):
        state=_state(user)
        if state is None:return NotImplemented
        _grants(state,role_codes,'roles')
        return {r.permission.code for r in state['grants'].values() if r.role.code in role_codes}
    def policy_roles(self,permission):
        state=_state(self.reader)
        if state is None:return NotImplemented
        from .operation_handover_contract import ACTIONS as HANDOVER
        from .operation_output_contract import ACTIONS as OUTPUT
        codes={permission}|{x[0] for x in HANDOVER.values()}|{x[0] for x in OUTPUT.values()}
        _grants(state,codes,'permissions')
        return tuple(sorted({r.role.code for r in state['grants'].values() if r.permission.code==permission}))
    def employees(self,actor):
        from pfm.formal_employee import formal_employee_queryset
        state=_state(actor)
        if state is None:return NotImplemented
        def guard(rows):
            values=[]
            for row in rows:
                pos=row.position_ref;dept=row.department_ref;shop=pos.workshop if pos and pos.workshop_id else None
                values.append(tuple(_fields(x) for x in (row,pos,dept,shop)))
            return tuple(values)
        saved=state['raw'].get('employees')
        if saved is None or guard(saved[0])!=saved[1]:
            rows=list(formal_employee_queryset(company_id=actor.company_id).filter(user_id=actor.pk)
                .select_related('position_ref__workshop','department_ref')[:2])
            saved=(rows,guard(rows));state['raw']['employees']=saved
        return saved[0]
    def definition(self):
        from workflow_runtime.models import ProcessDefinition
        state=_state(self.reader)
        if state is None:return NotImplemented
        def guard(row):return None if row is None else (_fields(row),tuple(_fields(x) for x in row.nodes.all()))
        saved=state['raw'].get('handover_definition')
        if saved is None or guard(saved[0])!=saved[1]:
            row=ProcessDefinition.objects.filter(definition_code='MES_OPERATION_HANDOVER',active=True,
                business_domain='MES',document_type='OperationHandover').prefetch_related('nodes').first()
            saved=(row,guard(row));state['raw']['handover_definition']=saved
        return saved[0]
    def center(self,actor,work_center_id):
        from pde.models import WorkCenter
        state=_state(actor)
        if state is None:return NotImplemented
        def guard(row):return None if row is None else (_fields(row),_fields(row.workshop) if row.workshop_id else None)
        key=('center',work_center_id);saved=state['raw'].get(key)
        if saved is None or guard(saved[0])!=saved[1]:
            row=WorkCenter.objects.filter(pk=work_center_id,company_id=actor.company_id,is_active=True).select_related('workshop').first()
            saved=(row,guard(row));state['raw'][key]=saved
        return saved[0]
    def scopes(self,actor,position,process_code):
        from pde.work_center_responsibility_models import WorkCenterResponsibilityScope
        state=_state(actor)
        if state is None:return NotImplemented
        key=('duty_scopes',position.pk,process_code);saved=state['raw'].get(key)
        def guard(rows):return tuple(tuple(_fields(x) for x in (r,r.workflow_responsibility,r.workflow_responsibility.responsibility)) for r in rows)
        if saved is None or guard(saved[0])!=saved[1]:
            rows=list(WorkCenterResponsibilityScope.objects.filter(company_id=actor.company_id,status='active',
                workflow_responsibility__position_id=position.pk,workflow_responsibility__workflow_code=process_code,
                workflow_responsibility__ownership_type='OWNER',workflow_responsibility__active=True
                ).select_related('workflow_responsibility__responsibility'))
            saved=(rows,guard(rows));state['raw'][key]=saved
            self._scope_records(state,actor,rows)
        return saved[0]
    def _scope_records(self,state,actor,rows):
        import re
        from workflow_runtime.models import BusinessStateTransition
        from system.models import OrganizationOperatingAuditRecord
        from django.db import connection
        from pde.work_center_responsibility_service import OBJECT
        ids=sorted({row.pk for row in rows});histories={pk:[] for pk in ids};audits={}
        limit=connection.features.max_query_params or 1000;width=max(1,(limit-3)//2)
        for offset in range(0,len(ids),width):
            group=ids[offset:offset+width];audit_ids=set()
            for event in BusinessStateTransition.objects.filter(object_type=OBJECT,object_id__in=group).order_by('version','pk'):
                histories[event.object_id].append(event)
                match=re.fullmatch(r'OrganizationOperatingAuditRecord:([1-9][0-9]*)',event.audit_reference or '')
                if match:audit_ids.add(int(match[1]))
            audit_ids=sorted(audit_ids);audit_width=max(1,limit-len(group)-2)
            for start in range(0,len(audit_ids),audit_width):
                audits.update((row.pk,row) for row in OrganizationOperatingAuditRecord.objects.filter(
                    pk__in=audit_ids[start:start+audit_width],organization_id=actor.company_id,
                    target_type=OBJECT,target_id__in=group))
        state['raw'].setdefault('scope_histories',{}).update((pk,(events,audits)) for pk,events in histories.items())
    def scope_history_rows(self,actor,row):
        state=_state(actor)
        if state is None or row.company_id!=actor.company_id:return NotImplemented
        return state['raw'].get('scope_histories',{}).get(row.pk,NotImplemented)
    def duty_membership(self,actor,position):
        from system.models import PositionResponsibility
        state=_state(actor)
        if state is None:return NotImplemented
        key=('position_duties',position.pk)
        if key not in state['raw']:
            state['raw'][key]=frozenset(PositionResponsibility.objects.filter(position=position,active=True).values_list('responsibility_id',flat=True))
        return state['raw'][key]
    def position_employee_count(self,actor,position_id):
        from pfm.formal_employee import formal_employee_queryset
        state=_state(actor)
        if state is None:return NotImplemented
        key=('position_employee_count',position_id)
        if key not in state['raw']:
            state['raw'][key]=formal_employee_queryset(company_id=actor.company_id).filter(position_ref_id=position_id).count()
        return state['raw'][key]

@contextmanager
def authorization_input_scope(reader=None):
    from pde.routing_read_context import _current
    from system.authorization_read_inputs import current_inputs,use_inputs
    request=_current.get()
    if not request or request.get('__http_get_read__') is not True or current_inputs() is not None:
        yield;return
    with use_inputs(RawAuthorityInputs(reader)):yield
