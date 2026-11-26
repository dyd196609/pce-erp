from .models import RoutingVersion,TestEngineeringRoutingBinding
from django.db import transaction

def edit_boundary(version):
    if version.status!='draft':return '已确认或已发布标准版本须在企业基础资料创建后继版本，不能覆盖。'
    if TestEngineeringRoutingBinding.objects.filter(routing_version=version).exists():return '该版本是已保存历史固定绑定的一部分，不可改写；请从基础资料办理结构后继。'
    from .order_routing_models import OrderRoutingExecutionArrangement
    if OrderRoutingExecutionArrangement.objects.filter(routing_version=version,status='confirmed').exists():return '该标准草稿已被确认安排引用，不可覆盖，须办理标准结构后继。'
    return ''

def require_draft_edit(entity,values,instance):
    if entity not in ('routing-versions','routing-steps'):return
    version=instance if entity=='routing-versions' else (instance.routing_version if instance else RoutingVersion.objects.get(pk=values['routing_version_id']))
    if version is None:return
    reason=edit_boundary(version)
    if reason:
        from .production_foundation_service import ProductionFoundationError
        raise ProductionFoundationError('STANDARD_VERSION_PROTECTED',reason)

def structure_hash(version):
    from .production_foundation_service import _snapshot
    from .design_revision_approval_service import digest
    return digest({'version':_snapshot(version),'steps':[_snapshot(x) for x in version.steps.order_by('sequence')]})

@transaction.atomic
def save_structure(*,user,version_id,rows,expected_hash,reason,key):
    from .production_foundation_service import ProductionFoundationService,_snapshot,_audit,ProductionFoundationError
    from .routing_version_successor_service import _authorize,_identity,_ledger,_canonical_hash
    from masterdata.models import MasterDataWriteRequest
    version=RoutingVersion.objects.select_for_update().select_related('routing').get(pk=version_id)
    company,authorization,chain=_authorize(user,version)
    boundary=edit_boundary(version)
    if boundary:raise ProductionFoundationError('STANDARD_VERSION_PROTECTED',boundary)
    if not reason or not key:raise ProductionFoundationError('MAINTENANCE_REASON_REQUIRED','结构维护须填写依据及幂等键。')
    identity,_=_identity(organization_id=company,object_type='STANDARD_ROUTING_STRUCTURE',external_id=f'RoutingVersion:{version.pk}:structure',target_type='routing-steps',fingerprint_payload={'routingVersionId':version.pk})
    payload={'versionId':version.pk,'rows':rows,'expectedHash':expected_hash,'reason':reason}
    ledger=_ledger(organization_id=company,action_code='production.master_data.routing.maintain',entity_type='routing-standard-structure',idempotency_key=key,request_hash=_canonical_hash(payload),identity=identity,user=user)
    if ledger.status==MasterDataWriteRequest.Status.COMMITTED:return {**ledger.result,'idempotent':True}
    if structure_hash(version)!=expected_hash:raise ProductionFoundationError('STANDARD_STRUCTURE_CHANGED','标准结构已更新，请回读后维护。')
    if not isinstance(rows,list) or not rows or len(rows)>500:raise ProductionFoundationError('STANDARD_STEPS_REQUIRED','标准路线须有完整工序结构。')
    keys=[r.get('key') for r in rows];ids=[r.get('id') for r in rows if r.get('id') is not None]
    existing={step.pk:step for step in version.steps.all()}
    if any(not isinstance(k,str) or not k.strip() for k in keys) or len(set(keys))!=len(keys) or len(set(ids))!=len(ids) or set(ids)-set(existing):raise ProductionFoundationError('STANDARD_STEP_IDENTITY_INVALID','步骤必须属于本标准版本且身份唯一。')
    position={k:i+1 for i,k in enumerate(keys)}
    for i,row in enumerate(rows,1):
        if set(row)-{'key','id','operationId','predecessorKeys','workCenterId'} or any(k not in position or position[k]>=i for k in row.get('predecessorKeys',[])):
            raise ProductionFoundationError('STANDARD_DEPENDENCY_INVALID','前序必须是本版本中排在当前步骤之前的工序；不自动删除条件或交接分支。')
    before={'version':_snapshot(version),'steps':[_snapshot(x) for x in version.steps.order_by('sequence')]}
    # Controlled two-pass order update, reusing the same normal draft service.
    for number,step in enumerate(existing.values(),10000):
        ProductionFoundationService.write('routing-steps',user=user,object_id=step.pk,payload={'sequence':number,'reason':reason},idempotency_key=f'{key}:temporary:{step.pk}',source_identity=None)
    result_ids=[]
    for i,row in enumerate(rows,1):
        values={'routing_version_id':version.pk,'sequence':i,'operation_id':row['operationId'],
            'predecessor_sequences':[position[k] for k in row.get('predecessorKeys',[])],'reason':reason}
        if 'workCenterId' in row:values['work_center_id']=row['workCenterId']
        result=ProductionFoundationService.write('routing-steps',user=user,object_id=row.get('id'),payload=values,idempotency_key=f'{key}:row:{row["key"]}',
            source_identity={'sourceSystem':'PCE_SYSTEM','sourceType':'AUTHORIZED_STANDARD_ROUTING_MAINTENANCE','sourceObjectType':'RoutingStep','externalId':f'RoutingVersion:{version.pk}:step:{row["key"]}'})
        result_ids.append(result['row']['id'])
    removed=set(existing)-set(ids)
    if removed:
        # Protected downstream foreign keys intentionally reject deletion.
        version.steps.filter(pk__in=removed).delete()
    audit=_audit(user=user,organization_id=company,action_code='production.master_data.routing.maintain',instance=version,before=before,
        after={'steps':[_snapshot(x) for x in version.steps.order_by('sequence')],'owner':'ENTERPRISE_FOUNDATION'},reason=reason,authorization=authorization,execution_chain=chain)
    result={'routingVersionId':version.pk,'stepIds':result_ids,'stepCount':len(result_ids),'auditId':audit.pk,'idempotent':False}
    ledger.status=MasterDataWriteRequest.Status.COMMITTED;ledger.target_entity_id=str(version.pk);ledger.result=result;ledger.save(update_fields=['status','target_entity_id','result','updated_at'])
    return result
