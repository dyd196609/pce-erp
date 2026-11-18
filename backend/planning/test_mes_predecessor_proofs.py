"""TEST source adapter consuming native completion and custody proofs."""
from .operation_handover_models import OperationCustodyEvent as Event,OperationHandover
from .operation_handover_core import verify_record,_hash
from .operation_handover_authority import verify_task_custody,verify_handover

def _retained_receipt_range(previous,successor,ranges):
 """A historical receipt alone is not current custody for this task.

 Preserve historical starts after their own real input consumption, while
 rejecting returned, lost, reserved or forwarded-to-another-purpose shares.
 """
 from .operation_handover_models import OperationCustodySlice,OperationInputAllocation
 from .operation_handover_authority import custody_responsibility,input_custody_basis
 from .services import PlanningBusinessError
 verify_task_custody(previous)
 for span in ranges:
  for leaf in OperationCustodySlice.objects.filter(root_id=span['rootId'],root__task=previous,
      company_id=successor.company_id,status__in=('U','S','V','C')):
   if max(int(leaf.start_atom),int(span['startAtom']))>=min(int(leaf.end_atom),int(span['endAtom'])):continue
   if leaf.status!='C' and (leaf.frozen or leaf.reserved_by_id or custody_responsibility(leaf)!=successor.work_center_id):continue
   try:basis=input_custody_basis(leaf,successor)
   except PlanningBusinessError as exc:
    if exc.code in ('OUTPUT_INPUT_SOURCE_UNPROVEN','OUTPUT_SOURCE_RANGE_RELEASE_UNPROVEN',
        'OUTPUT_INPUT_UNRECEIVED_SOURCE_BLOCKED','OUTPUT_INPUT_RECEIPT_UNPROVEN','OUTPUT_SOURCE_RANGE_RELEASE_REQUIRED'):continue
    raise
   if leaf.status!='C':return True
   for allocation in OperationInputAllocation.objects.filter(source_slice=leaf,output__task=successor,
       company_id=successor.company_id,status='confirmed').select_related('output','execution_start'):
    verify_record(allocation);verify_record(allocation.output)
    bound=allocation.output.source_snapshot.get('task',{})
    if (allocation.output.status=='confirmed' and allocation.execution_start.task_id==successor.pk
        and allocation.execution_start.company_id==successor.company_id
        and bound.get('taskId')==successor.pk and bound.get('taskVersion')==successor.version
        and bound.get('sourceSnapshotHash')==successor.source_snapshot_hash
        and allocation.source_snapshot.get('sourceSliceId')==leaf.pk
        and allocation.source_snapshot.get('sourceHash')==leaf.source_snapshot_hash
        and allocation.source_snapshot.get('sourceRangeReleaseProof')==basis
        and int(allocation.start_atom)==int(leaf.start_atom) and int(allocation.end_atom)==int(leaf.end_atom)):
     return True
 return False

def execution_proof(previous,successor):
 from copy import deepcopy
 from .operation_predecessor_authority import verification_context,_proof_cache_epoch
 from .mes_test_source_bridge import _fail
 with verification_context() as context:
  epoch=_proof_cache_epoch(context)
  if context.get('testExecutionProofEpoch')!=epoch:
   context['testExecutionProofEpoch']=epoch;context['testExecutionProofs']={}
  key=(previous.company_id,previous.pk,previous.version,previous.source_snapshot_hash,
       successor.company_id,successor.pk,successor.version,successor.source_snapshot_hash)
  cache=context['testExecutionProofs'];active=context.setdefault('testExecutionProofPath',set())
  if key in cache:return deepcopy(cache[key])
  if key in active:_fail('TEST_MES_PREDECESSOR_CYCLE','测试MES证明出现递归循环，不能放行。')
  active.add(key)
  try:
   value=_execution_proof_unscoped(previous,successor)
   if _proof_cache_epoch(context)!=epoch:_fail('TEST_MES_PROOF_READ_CHANGED','证明核验期间数据变化，请重新读取。')
   cache[key]=deepcopy(value);return value
  finally:active.remove(key)

def _execution_proof_unscoped(previous,successor):
 if previous.company_id!=successor.company_id or previous.work_order_id!=successor.work_order_id or previous.work_order.usage_purpose!=successor.work_order.usage_purpose:return {'ready':False}
 from .operation_completion_v3_authority import read_quantitative_whole_coverage
 whole=read_quantitative_whole_coverage(previous)
 receipts=[]
 for event in Event.objects.filter(task=previous,company_id=previous.company_id,kind='RANGE_RECEIVED',data__targetTaskId=successor.pk).order_by('pk'):
  verify_record(event);release=Event.objects.filter(pk=event.data.get('releaseEventId'),task=previous,kind='RANGE_RELEASE').first()
  if not release:continue
  verify_record(release);target=release.data.get('rangeRelease',{}).get('target',{})
  if event.data.get('releaseEventHash')!=release.event_hash or target.get('taskId')!=successor.pk or target.get('taskVersion')!=successor.version or target.get('taskSourceSnapshotHash')!=successor.source_snapshot_hash:continue
  if event.created_by_id==release.created_by_id or event.occurred_at<release.occurred_at:continue
  if (event.qualification_snapshot.get('currentActorEvidence',{}).get('employeeId')==release.qualification_snapshot.get('currentActorEvidence',{}).get('employeeId')
      or event.data.get('actualReceiverId')!=event.created_by_id or event.data.get('usagePurpose')!=previous.work_order.usage_purpose):continue
  if not _retained_receipt_range(previous,successor,release.data['rangeRelease']['ranges']):continue
  receipts.append({'kind':'SAME_WORKSHOP_ACTUAL_RANGE_RECEIPT','eventId':event.pk,'eventHash':event.event_hash,'sourceEventId':release.pk,'quantity':event.quantity,'sourceUnitId':previous.workload_uom_id,'actualReceiverId':event.created_by_id,'occurredAt':event.occurred_at.isoformat()})
 for header in OperationHandover.objects.filter(company_id=previous.company_id,data__taskId=previous.pk,target_operation_id=successor.source_operation_id,status__in=('received','partially_received','discrepancy_pending')).order_by('pk'):
  verify_handover(header)
  if header.target_work_center_id!=successor.work_center_id or header.sender_employee_id==header.receiver_employee_id:continue
  valid_events=[]
  for event in Event.objects.filter(handover=header,task=previous,company_id=previous.company_id,kind='RECEIVE').order_by('pk'):
   verify_record(event)
   ranges=[s for s in event.data.get('afterSlices',[]) if s.get('status') in ('U','S','V')
       and s.get('data',{}).get('receivedLegId')==header.pk
       and s.get('data',{}).get('receivedEmployeeId')==event.data.get('receiverEmployeeId')]
   if ranges and _retained_receipt_range(previous,successor,ranges):valid_events.append(event)
  if not valid_events:continue
  # Retain the immutable legacy shape for already-frozen, fully received starts.
  if header.status=='received':
   receipts.append({'kind':'NATIVE_PHYSICAL_HANDOVER_RECEIPT','handoverId':header.pk,'sourceHash':header.source_snapshot_hash,'version':header.version,'targetOperationId':header.target_operation_id})
  for event in valid_events:
   receipts.append({'kind':'NATIVE_PHYSICAL_RECEIPT_EVENT','handoverId':header.pk,'sourceHash':header.source_snapshot_hash,
    'eventId':event.pk,'eventHash':event.event_hash,'targetOperationId':header.target_operation_id,
    'actualReceiverEmployeeId':event.data['receiverEmployeeId'],'occurredAt':event.occurred_at.isoformat()})
 if receipts:verify_task_custody(previous)
 # The frozen graph has no partial-start policy. Do not infer it from receipt.
 # Partial output/transfer remain legal independently of whole start admission.
 return {'ready':whole['valid'] and bool(receipts),'wholeCompletionVerified':whole['valid'],'wholeCompletionProofHash':_hash(whole['proof']) if whole['valid'] else None,'receiptProofs':receipts,'edgeRule':'FROZEN_WHOLE_COMPLETION_AND_IDENTIFIED_RECEIPT','sourceTaskId':previous.pk,'targetTaskId':successor.pk,'usagePurpose':previous.work_order.usage_purpose}
