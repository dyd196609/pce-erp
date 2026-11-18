"""GET-local raw completion edges; native consumers retain every proof check.

Uses the existing verification epoch and record history batch reader. No
allow/ready, producer context or whole-proof result is stored here.
"""
from copy import deepcopy

def raw_input(company_id,key,load):
    """Share only original rows; every consumer still runs its native checks.

    The existing physical read epoch includes local writes, other-connection
    commits and rollbacks. Returned copies cannot mutate another consumer.
    POST and non-request service calls always execute their original loader.
    """
    state=_raw(company_id)
    if state is None:return load()
    inputs=state.setdefault('inputs',{})
    if key not in inputs:
        value=load()
        if _raw(company_id) is not state:
            from .operation_handover_core import fail
            fail('MES_RAW_INPUT_READ_CHANGED','原始证明输入读取期间发生变化，请只读重新核查。')
        inputs[key]=value
    return deepcopy(inputs[key])

def definition_rows(company_id,code):
    from workflow_runtime.models import ProcessDefinition,WorkflowNodeDefinition
    from django.db.models import Prefetch
    return raw_input(company_id,('workflow_definition_rows',code),lambda:list(
        ProcessDefinition.objects.filter(definition_code=code).order_by('pk').prefetch_related(
            Prefetch('nodes',queryset=WorkflowNodeDefinition.objects.order_by('pk'),to_attr='_mes_raw_nodes'))))

def workflow_node(company_id,pk):
    from workflow_runtime.models import WorkflowNodeDefinition
    return raw_input(company_id,('workflow_node_row',pk),lambda:
        WorkflowNodeDefinition.objects.select_related('process_definition').filter(pk=pk).first())

def audit_node_matches(company_id,pk,process_id,process_code,node_code,action):
    from workflow_runtime.models import WorkflowNodeDefinition
    if _raw(company_id) is None:
        return WorkflowNodeDefinition.objects.filter(pk=pk,process_definition_id=process_id,
            process_definition__definition_code=process_code,node_code=node_code,
            business_action_code=action,active=True).exists()
    row=workflow_node(company_id,pk)
    return bool(row and row.active and row.process_definition_id==process_id
        and row.process_definition.definition_code==process_code and row.node_code==node_code
        and row.business_action_code==action)

def report_rows(task):
    from .operation_report_models import ProductionOperationReport
    from .operation_handover_core import record_proof_batch
    def load():
        rows=list(ProductionOperationReport.objects.filter(task_id=task.pk).order_by('pk'))
        state=_raw(task.company_id)
        if state is not None:
            safe=[r for r in rows if r.company_id==task.company_id and r.task_id==task.pk]
            histories,audits=record_proof_batch(safe,audit_actor=True)
            state['histories'].update(histories);state['audits'].update(audits)
            from masterdata.models import MasterDataWriteRequest
            from django.db import connection
            ids=[str(r.pk) for r in safe];width=max(1,(connection.features.max_query_params or 1000)-3)
            grouped={r.pk:[] for r in safe}
            for offset in range(0,len(ids),width):
                for ledger in MasterDataWriteRequest.objects.filter(organization_id=task.company_id,
                        entity_type='ProductionOperationReport',target_entity_id__in=ids[offset:offset+width]).select_related('source_identity'):
                    grouped[int(ledger.target_entity_id)].append(ledger)
            state.setdefault('report_ledgers',{}).update(grouped)
        return rows
    return raw_input(task.company_id,('operation_report_rows',task.pk),load)

def report_ledgers(task,record,action):
    state=_raw(task.company_id)
    if state is None or record.pk not in state.get('report_ledgers',{}):return NotImplemented
    return deepcopy([r for r in state['report_ledgers'][record.pk] if r.action_code==action])

def _raw(company_id):
    from pde.routing_read_context import _current
    from .operation_predecessor_authority import _context,_proof_cache_epoch
    request,context=_current.get(),_context.get()
    if (not request or request.get('__http_get_read__') is not True or context is None
            or not request.get('__reader_id__') or request.get('__reader_company_id__')!=company_id):return None
    epoch=_proof_cache_epoch(context)
    if epoch is None:return None
    # The reader identity is already sealed by the outer request. Raw rows may
    # be consumed by distinct native producer contexts, never their decisions.
    key=('completion_raw_edges',request['__reader_id__'],company_id,epoch)
    return request.setdefault(key,{'tasks':{},'histories':{},'audits':{},'ledgers':{}})

def prepare_tasks(tasks):
    """Batch only explicitly authorized task roots supplied by native readers."""
    from .operation_completion_generation_models import OperationCompletionGeneration as Generation
    from .operation_handover_core import record_proof_batch
    from masterdata.models import MasterDataWriteRequest
    from django.db import connection
    groups={}
    for task in tasks:groups.setdefault(task.company_id,{})[task.pk]=task
    for company,roots in groups.items():
        state=_raw(company)
        if state is None:continue
        ids=sorted(set(roots)-set(state['tasks']));width=max(1,(connection.features.max_query_params or 1000)-3)
        if not ids:continue
        rows=[]
        for offset in range(0,len(ids),width):
            rows.extend(Generation.objects.filter(task_id__in=ids[offset:offset+width]).select_related(
                'workflow_instance','approval_task','approval_decision','closure').order_by('sequence','pk'))
        objects=[]
        for row in rows:
            # Bad roots/references are still returned to the original verifier,
            # but never used to broaden the eager dependency read scope.
            task=roots[row.task_id]
            if row.company_id!=company:continue
            objects.append(row)
            workflow=row.workflow_instance
            kind='ProductionOperationCompletion' if row.protocol=='V2_BRIDGE' else 'OperationCompletionGeneration'
            identity=task.pk if row.protocol=='V2_BRIDGE' else row.pk
            if workflow and workflow.document_type==kind and workflow.document_id==identity:
                objects.append(workflow)
                if row.approval_task and row.approval_task.workflow_instance_id==workflow.pk:objects.append(row.approval_task)
            if row.closure and row.closure.company_id==task.company_id:objects.append(row.closure)
        histories,audits=record_proof_batch(objects,audit_actor=True)
        state['histories'].update(histories);state['audits'].update(audits)
        # Query all competing ledgers for the actual generation identities;
        # do not pre-filter committed/valid rows and hide conflicts.
        generation_ids=[str(row.pk) for row in rows]
        for offset in range(0,len(generation_ids),width):
            for ledger in MasterDataWriteRequest.objects.filter(organization_id=company,
                    entity_type='OperationCompletionGeneration',target_entity_id__in=generation_ids[offset:offset+width]).select_related('source_identity'):
                state['ledgers'].setdefault(ledger.target_entity_id,[]).append(ledger)
        if _raw(company) is not state:
            from .operation_handover_core import fail
            fail('MES_RAW_INPUT_READ_CHANGED','原始证明输入读取期间发生变化，请只读重新核查。')
        grouped={pk:[] for pk in ids}
        for row in rows:grouped[row.task_id].append(row)
        state['tasks'].update(grouped)

def generations(task):
    from .operation_completion_generation_models import OperationCompletionGeneration as Generation
    state=_raw(task.company_id)
    if state is None:return list(Generation.objects.filter(task_id=task.pk).select_related(
        'workflow_instance','approval_task','approval_decision','closure').order_by('sequence','pk'))
    if task.pk not in state['tasks']:prepare_tasks([task])
    return deepcopy(state['tasks'][task.pk])

def history(name,object_id,company_id):
    state=_raw(company_id);key=(name,object_id)
    if state is None or key not in state['histories']:return NotImplemented
    return deepcopy(state['histories'][key])

def audit(audit_id,company_id):
    state=_raw(company_id)
    if state is None or audit_id not in state['audits']:return NotImplemented
    return deepcopy(state['audits'][audit_id])

def ledgers(gen,code,request_hash):
    state=_raw(gen.company_id)
    if state is None or gen.task_id not in state['tasks']:return NotImplemented
    return deepcopy([row for row in state['ledgers'].get(str(gen.pk),[]) if row.action_code==code and row.request_hash==request_hash])
