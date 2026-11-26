"""Formal self-start over native PRODUCTION_USE dispatch. No TEST entry change."""
from copy import deepcopy
from django.db import transaction
from django.utils import timezone
from masterdata.models import ExternalIdentity,MasterDataWriteRequest
from workflow_runtime.state_transitions import create_business_object_with_initial_state,record_projected_business_transition
from . import mes_formal_start_protocol as native
from .mes_formal_source_admission import source,fail
from .test_scheduling_service import _actor,_retry
from .scheduling_primitives import _writer_lock
from .operation_start_models import ProductionOperationStart as Start
from .workshop_task_models import ProductionWorkshopTask as Task
from .operation_predecessor_authority import predecessor_facts
from .services import record_audit


def qualification(*,user,task_id):
    actor=_actor(user)
    task=Task.objects.filter(pk=task_id,company_id=actor.company_id,work_order__usage_purpose='PRODUCTION_USE').first()
    if not task:fail('MES_FORMAL_TASK_NOT_VISIBLE','正式任务不在当前公司范围。',403)
    facts=source(task,actor)
    record=Start.objects.filter(task=task).first()
    return task,native._qualification(actor,task,facts,predecessor_facts(task),state='started' if record else 'waiting')


def start(*,user,task_id,payload):
    native._payload(payload);actor=_actor(user)
    def run():
        with transaction.atomic():
            _writer_lock(actor)
            task=Task.objects.select_for_update().filter(pk=task_id,company_id=actor.company_id).first()
            if not task:fail('MES_FORMAL_TASK_NOT_VISIBLE','正式任务不在当前公司范围。',403)
            facts=source(task,actor)
            if (task.version!=payload['expectedVersion'] or task.source_snapshot_hash!=payload['expectedSourceSnapshotHash']
                or task.assignment_hash!=payload['expectedAssignmentHash']):
                fail('MES_FORMAL_START_SOURCE_CHANGED','任务版本或冻结来源已变化。')
            q=native._qualification(actor,task,facts,predecessor_facts(task),state='waiting')
            if not q['ready']:fail('MES_FORMAL_START_NOT_READY','；'.join(q['missingItems']),403)
            rh,old=native._intent(actor,task_id,payload);record=Start.objects.filter(task=task).first()
            if record:
                result=native._verify_record(record,task)
                if old and int(old.target_entity_id)!=record.pk:fail('MES_FORMAL_START_LEDGER_CONFLICT','开工账本未对应原记录。')
                return {'idempotent':True,'createdCount':0,'execution':result}
            if old:fail('MES_FORMAL_START_LEDGER_CONFLICT','开工账本缺少原记录。')
            now=timezone.now()
            if task.dispatched_at is None or now<task.dispatched_at:fail('MES_FORMAL_START_TIME_INVALID','实际开工不得早于实际派工。')
            record=create_business_object_with_initial_state(model=Start,initial_state='started',company_id=task.company_id,
                task=task,work_order_id=task.work_order_id,receipt_id=task.receipt_id,source_operation_id=task.source_operation_id,
                workshop_id=task.workshop_id,work_center_id=task.work_center_id,execution_mode=task.execution_mode,
                workload_quantity=task.workload_quantity,workload_uom_id=task.workload_uom_id,task_version=task.version,
                source_snapshot=deepcopy(task.source_snapshot),source_snapshot_hash=task.source_snapshot_hash,
                assignment_snapshot=deepcopy(task.assignment_snapshot),assignment_hash=task.assignment_hash,
                execution_position_id=task.execution_position_id,execution_employee_id=task.execution_employee_id,
                started_by=actor,started_at=now,start_qualification=deepcopy(q),reason=payload['reason'].strip())
            audit=record_audit(user=actor,action_code=native.START_ACTION,target=record,target_type=native.OBJECT,
                target_no=task.no,before={'status':''},after=native._state(record),authorization=q['authorization'],reason=record.reason)
            node={'processCode':native.PROCESS,'nodeCode':native.WORKFLOW_NODE,'processId':q['definitionId'],'nodeId':q['nodeId']}
            audit.before_snapshot['workflowNode']=node;audit.after_snapshot['workflowNode']=node;audit.save(update_fields=['before_snapshot','after_snapshot'])
            record_projected_business_transition(object_type=native.OBJECT,object_id=record.pk,source_state='',target_state='started',
                action_code=native.START_ACTION,operator=actor,reason=record.reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('','started')})
            identity=ExternalIdentity.objects.create(organization_id=task.company_id,source_system='MES_FORMAL_OPERATION_START',
                source_type='INTERNAL',source_object_type='ProductionWorkshopTask',external_id=str(task.pk),target_entity_type=native.OBJECT,
                target_entity_id=str(record.pk),mapping_status='MATCH',source_fingerprint=task.source_snapshot_hash,
                audit_metadata={'actualStartOnly':True,'usagePurpose':'PRODUCTION_USE'})
            MasterDataWriteRequest.objects.create(organization_id=task.company_id,action_code=native.START_ACTION,entity_type=native.OBJECT,
                idempotency_key=payload['idempotencyKey'],request_hash=rh,source_identity=identity,status='COMMITTED',target_entity_id=str(record.pk),
                result={'taskId':task.pk,'operationStartId':record.pk},audit_metadata={'actorId':actor.pk,'usagePurpose':'PRODUCTION_USE'})
            return {'idempotent':False,'createdCount':1,'execution':native._verify_record(record,task)}
    return _retry(run)
