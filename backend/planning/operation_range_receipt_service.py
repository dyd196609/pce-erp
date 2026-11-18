"""Actual recipient acknowledgement of an existing same-workshop MES range.

Reuses receive authority and the native custody event/hash/idempotency ledger;
does not mint output, move quantities or synthesize a physical handover form.
"""
from django.db import transaction
from .operation_handover_core import (actor_for,payload_guard,strict_id,lock_accounts,qualify,intent,commit_intent,occurred,verify_record,fail,text,add,writes,writes_since,capture_counts)
from .operation_handover_models import OperationCustodyEvent as Event,OperationCustodySlice as Slice
from .operation_handover_authority import custody_event,verify_task_custody,custody_responsibility
from .operation_handover_contract import ACTIONS
from .workshop_task_models import ProductionWorkshopTask as Task
from .operation_resource_read_scope import scoped_execution_read

@scoped_execution_read
def receive_range(*,user,payload):
 allowed={'taskId','releaseEventId','targetTaskId','occurredAt','reason','idempotencyKey'}
 payload_guard(payload,allowed,allowed-{'occurredAt'});actor=actor_for(user)
 for key in ('taskId','releaseEventId','targetTaskId'):strict_id(payload[key],key)
 with transaction.atomic():
  before=capture_counts();accounts=lock_accounts(actor,[payload['taskId'],payload['targetTaskId']])
  source=Task.objects.get(pk=payload['taskId'],company_id=actor.company_id)
  target=Task.objects.get(pk=payload['targetTaskId'],company_id=actor.company_id)
  release=Event.objects.filter(pk=payload['releaseEventId'],task=source,company_id=actor.company_id,kind='RANGE_RELEASE').first()
  if not release or source.work_order_id!=target.work_order_id or source.work_order.usage_purpose!=target.work_order.usage_purpose:fail('RANGE_RECEIPT_SOURCE_INVALID','同工单、同用途的真实范围释放不存在。',403)
  verify_record(release);verify_task_custody(source);binding=release.data.get('rangeRelease',{})
  expected={'workCenterId':target.work_center_id,'operationId':target.source_operation_id,'taskId':target.pk,'taskVersion':target.version,'taskSourceSnapshotHash':target.source_snapshot_hash}
  if any(binding.get('target',{}).get(k)!=v for k,v in expected.items()):fail('RANGE_RECEIPT_TARGET_INVALID','释放未准确关联当前接收任务及冻结版本。')
  from .mes_test_source_bridge import _source
  if not _source(target,actor)['ready']:fail('RANGE_RECEIPT_SOURCE_CHANGED','当前目标测试来源已失效。')
  if source.workshop_id!=target.workshop_id or actor.pk==release.created_by_id:fail('RANGE_RECEIPT_SEPARATION_REQUIRED','同车间接收须由不同实际班组长确认。',403)
  code=ACTIONS['receive'][0];q=qualify(actor,code,target.work_center_id,'OperationCustodyEvent',release.pk)
  if q['currentActorEvidence'].get('employeeId')==release.qualification_snapshot.get('currentActorEvidence',{}).get('employeeId'):fail('RANGE_RECEIPT_SEPARATION_REQUIRED','交出与接收须为不同真实员工，不能仅换账号。',403)
  digest,replay=intent(actor,code,release.pk,payload)
  if replay:
   row=Event.objects.get(pk=replay.target_entity_id,kind='RANGE_RECEIVED',company_id=actor.company_id);verify_record(row)
   return _read(actor,source,row,True),writes()
  if Event.objects.filter(task=source,kind='RANGE_RECEIVED',data__releaseEventId=release.pk).exists():fail('RANGE_ALREADY_RECEIVED','该正式来源范围已收讫，不得换key重复接收。')
  leaves=list(Slice.objects.filter(pk__in=[x['sliceId'] for x in binding['ranges']],company_id=actor.company_id))
  if len(leaves)!=len(binding['ranges']) or any(s.status not in ('U','S','V') or custody_responsibility(s)!=target.work_center_id for s in leaves):fail('RANGE_RECEIPT_SCOPE_CHANGED','来源份额已经变化或不属于当前目标责任范围。')
  from django.utils import timezone
  from .operation_handover_core import offset_iso
  stamp=occurred(payload.get('occurredAt') or offset_iso(timezone.now()),not_before=release.occurred_at)
  row=custody_event(actor=actor,code=code,q=q,task=source,kind='RANGE_RECEIVED',quantity=text(add(*(s.quantity for s in leaves))),debit='',credit='',stamp=stamp,intent_hash=digest,reason=payload['reason'],slices=leaves,data={'releaseEventId':release.pk,'releaseEventHash':release.event_hash,'targetTaskId':target.pk,'targetOperationId':target.source_operation_id,'targetWorkCenterId':target.work_center_id,'usagePurpose':source.work_order.usage_purpose,'actualReceiverId':actor.pk,'effectiveOutputDelta':'0'})
  commit_intent(actor,code,payload,digest,row,{'eventId':row.pk,'releaseEventId':release.pk,'originalObjectId':release.pk,'taskId':source.pk,'targetTaskId':target.pk});verify_task_custody(source)
  return _read(actor,source,row,False),writes_since(before)

def _read(actor,source,row,replay):
 from .operation_handover_facts import read_operation_handovers
 facts=read_operation_handovers(user=actor,task_id=source.pk)
 facts['rangeReceiptOperation']={'eventId':row.pk,'eventHash':row.event_hash,'idempotent':replay,'usagePurpose':source.work_order.usage_purpose}
 return facts
