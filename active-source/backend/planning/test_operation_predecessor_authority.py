"""TEST full frozen-route adapter to the native exact-edge DAG validator.
No completion is inferred from dispatch, start, or planned dates.
"""
from contextlib import contextmanager
from copy import deepcopy
from .operation_dependency_graph import validate_graph
from .scheduling_primitives import _hash
from pde.models import RoutingStep

@contextmanager
def verification_context():
 from .operation_predecessor_authority import verification_context as native_context
 with native_context():yield

def route_nodes(order):
 if order.usage_purpose=='PRODUCTION_USE':
  from .mes_formal_route import route_nodes as formal_nodes
  return formal_nodes(order)
 rows=order.source_schedule.snapshot['preview']['rows'];selections=order.source_snapshot['routeSelections']
 from .custody_dependency_reads import read_rows
 ids=tuple(r['stepId'] for r in rows)
 steps=read_rows('route_steps',(order.company_id,ids),lambda:RoutingStep.objects.in_bulk(ids));selected={x['stepId']:x for x in selections};nodes={}
 for r in rows:
  step=steps.get(r['stepId']);saved=selected.get(r['stepId'])
  if not step or not saved or saved['sequence']!=r['sequence'] or saved['operationId']!=r['operationId'] or saved['decision']!=r['decision'] or saved['decisionBasis']!=r['decisionBasis']:raise ValueError('冻结完整路线选择与来源步骤不一致。')
  n={'frozenPredecessors':r['predecessorSequences'],'currentPredecessors':deepcopy(step.predecessor_sequences),'active':step.is_active,'versionId':step.routing_version_id,'expectedVersionId':order.source_snapshot['scope']['routingVersionId'],'operationId':step.operation_id,'expectedOperationId':r['operationId'],'row':r}
  if r['sequence'] in nodes:raise ValueError('完整路线存在重复序号。')
  nodes[r['sequence']]=n
 return nodes

def predecessor_facts(task,nodes=None):
 nodes=nodes if nodes is not None else route_nodes(task.work_order);issue=validate_graph(nodes,task.source_operation.sequence);items=[]
 def inspect(sequence,path):
  node=nodes[sequence];row=node['row'];item={'sequence':sequence,'stepId':row['stepId'],'operationName':row['operationName'],'decision':row['decision'],'completed':False,'prerequisiteSatisfied':False,'statusLabel':'前序尚无有效审核完工证明'}
  if row['decision']=='NOT_APPLICABLE':
   proofs=[inspect(p,path+[sequence]) for p in node['frozenPredecessors']]
   ready=all(x['prerequisiteSatisfied'] for x in proofs)
   item.update(proofType='TEST_SAVED_ARRANGEMENT_EXCLUSION',basis=row['decisionBasis'],requiredPredecessorProofs=proofs,prerequisiteSatisfied=ready,statusLabel='前序依本测试安排不执行，仍须核验其上游：'+('全部满足' if ready else '上游尚未审核完工'))
   return item
  from .workshop_task_models import ProductionWorkshopTask
  from .operation_start_models import ProductionOperationStart
  from .mes_evidence_graph import raw_input
  previous=raw_input(task.company_id,('predecessor_task_row',task.work_order_id,sequence),lambda:
   ProductionWorkshopTask.objects.filter(company_id=task.company_id,work_order=task.work_order,source_operation__sequence=sequence).first())
  started=bool(previous and raw_input(task.company_id,('predecessor_start_row',previous.pk),lambda:
   ProductionOperationStart.objects.filter(task=previous).first()))
  item.update(taskId=previous.pk if previous else None,taskNo=previous.no if previous else None,started=started)
  if previous and item['started']:
   from .test_mes_predecessor_proofs import execution_proof
   proof=execution_proof(previous,task)
   item.update(completed=bool(proof.get('wholeCompletionVerified')),prerequisiteSatisfied=proof['ready'],mesExecutionProof=proof,statusLabel='前序独审完成及准确来源收讫均已验真' if proof['ready'] else '前序尚缺有效整体完工或对应批次实际接收证明')
   return item
  # An unstarted predecessor cannot supply a valid completion proof. Retain
  # physical history diagnostics without treating row presence as completion.
  from django.db import connection
  names=connection.introspection.table_names();completion_table='planning_production_operation_completion'
  completion_count=None
  if completion_table in names and previous:
   cols=[x.name for x in connection.introspection.get_table_description(connection.cursor(),completion_table)]
   if 'task_id' in cols:
    with connection.cursor() as c:c.execute('select count(*) from '+completion_table+' where task_id=%s',[previous.pk]);completion_count=c.fetchone()[0]
  item['completionRecordCount']=completion_count
  item['statusLabel']=('前序已有完成记录，但尚无本测试链可验证的独立审核完成证明' if completion_count else '前序'+row['operationName']+('已开工但尚未审核完工' if item['started'] else '尚未开工、未审核完工'))
  return item
 if not issue:
  items=[inspect(p,[]) for p in nodes[task.source_operation.sequence]['frozenPredecessors']]
 ready=not issue and all(x['prerequisiteSatisfied'] for x in items)
 return {'contractVersion':'PCE-TEST-OPERATION-PREDECESSOR-V1','ready':ready,'routeRelationshipConsistent':issue is None,'plannedDatesUsedAsCompletion':False,'completionAuthorityAvailable':True,'authority':'VERIFIED_TEST_ARRANGEMENT_FULL_ROUTE_AND_NATIVE_COMPLETION_RECORDS','items':items,'statusLabel':issue or ('固定路线无前序，可核对本人开工资格' if not items else '；'.join(x['statusLabel'] for x in items)),'routeProofHash':_hash(nodes)}

def frozen_predecessors_valid(task,frozen):
 current=predecessor_facts(task)
 if not current['ready'] or not isinstance(frozen,dict) or not frozen.get('ready') or frozen.get('routeProofHash')!=current['routeProofHash']:return False
 old={x['sequence']:x for x in frozen['items']};now={x['sequence']:x for x in current['items']}
 if set(old)!=set(now):return False
 for sequence,previous in old.items():
  if previous.get('mesExecutionProof'):
   captured=previous['mesExecutionProof'];latest=now[sequence].get('mesExecutionProof',{})
   if captured.get('wholeCompletionProofHash')!=latest.get('wholeCompletionProofHash'):return False
   if any(proof not in latest.get('receiptProofs',[]) for proof in captured.get('receiptProofs',[])):return False
  elif previous!=now[sequence]:return False
 return True
