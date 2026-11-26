from pde.order_routing_execution_service import ArrangementError
"""TEST finished goods: native MES closure -> custody -> existing WMS stock."""
from copy import deepcopy
from contextlib import nullcontext
from .finished_goods_formal_authority import product_source
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from system.models import User,OrganizationOperatingAuditRecord
from .finished_goods_models import ProductionFinishedGoodsTransfer as Transfer
from .finished_goods_contract import CODES,codes_for,action_contract,MODULE
from .finished_goods_permissions import source_qualification,warehouse_qualification
from .finished_goods_authority import order_for,task_graph,current_closure,verify_frozen_closure,verify_warehouse_conversion
from .operation_handover_core import (actor_for,fail,strict_id,payload_guard,number,text,add,_hash,lock_accounts,offset_iso,
    initialize,transition,project,audited_projection,verify_record,intent,commit_intent,bump)
from .operation_handover_authority import verify_task_custody,custody_responsibility,custody_event
from .operation_handover_models import OperationCustodySlice as Slice,OperationCustodyEvent as Event
from .operation_resource_read_scope import scoped_execution_read
from .operation_predecessor_authority import verification_context
from procurement.inventory_purpose import TEST,test_purpose_write_scope
from procurement.models import Warehouse,WarehouseLocation,WarehouseInbound,InventoryLot,InventoryTransaction,InventoryBalance
from procurement.scm_runtime_services import _next_number
from workflow_runtime.state_transitions import create_business_object_with_initial_state,record_projected_business_transition,transition_business_object
from .services import PlanningBusinessError
from django.db.models import Max,Q
from workflow_runtime.models import BusinessStateTransition

LABELS={'prepared':'成品已备交，待实际交出','in_transit':'成品已交出，待指定仓管接收','received':'成品已接收并测试入库','cancelled':'未交出备交已取消'}

def _write_markers():
    return {'audit':OrganizationOperatingAuditRecord.objects.aggregate(value=Max('pk'))['value'] or 0,
        'transition':BusinessStateTransition.objects.aggregate(value=Max('pk'))['value'] or 0,
        'event':Event.objects.aggregate(value=Max('pk'))['value'] or 0,
        'transfer':Transfer.objects.aggregate(value=Max('pk'))['value'] or 0,
        **{model.__name__:(model.all_objects.aggregate(value=Max('pk'))['value'] or 0)
            for model in (WarehouseInbound,InventoryLot,InventoryBalance,InventoryTransaction)}}

def _actual_writes(before,row,actor,action,replayed):
    CODES=codes_for(row.work_order.usage_purpose)
    result={'businessWriteCount':0,'auditWriteCount':0,'stateTransitionWriteCount':0,'actualStartCount':0,'actualReportCount':0,
        'inventoryUpdatedCount':0,'resourceOccupancyReleasedCount':0,'quantityAccountCASWriteCount':1}
    if replayed:return result
    events=list(Event.objects.filter(pk__gt=before['event'],task_id=row.task_id,data__finishedGoodsTransferId=row.pk).values_list('pk',flat=True))
    inbounds=list(WarehouseInbound.all_objects.filter(production_transfer=row).values_list('pk',flat=True))
    audit_scope=(Q(target_type='ProductionFinishedGoodsTransfer',target_id=row.pk)|Q(target_type='OperationCustodySlice',target_id__in=row.data['reservedSliceIds'])
        |Q(target_type='OperationCustodyEvent',target_id__in=events)|Q(target_type='WarehouseInbound',target_id__in=inbounds))
    result['auditWriteCount']=OrganizationOperatingAuditRecord.objects.filter(audit_scope,pk__gt=before['audit'],actor=actor,
        organization_id=row.company_id,action_code=CODES[action]).count()
    transition_scope=(Q(object_type='ProductionFinishedGoodsTransfer',object_id=row.pk)|Q(object_type='OperationCustodySlice',object_id__in=row.data['reservedSliceIds'])
        |Q(object_type='OperationCustodyEvent',object_id__in=events)|Q(object_type='WarehouseInbound',object_id__in=inbounds))
    result['stateTransitionWriteCount']=BusinessStateTransition.objects.filter(transition_scope,pk__gt=before['transition'],operator=actor,action_code=CODES[action]).count()
    result['businessWriteCount']=len(events)+int(row.pk>before['transfer'])
    receipt=row.data.get('warehouseReceipt') or {}
    for model,key in ((WarehouseInbound,'inboundId'),(InventoryLot,'lotId'),(InventoryBalance,'balanceId'),(InventoryTransaction,'transactionId')):
        created=model.all_objects.filter(pk=receipt.get(key),pk__gt=before[model.__name__]).count()
        result['businessWriteCount']+=created
        if model is InventoryTransaction:result['inventoryUpdatedCount']=created
    return result

def _review_read(actor,task):
    """Delegate whole-order review reads to the existing native task boundary."""
    from .mes_test_source_bridge import _authority
    read_ok,read_roles,_=_authority(actor,'production.operation.complete.read',task.workshop.department_id,task.assignment_snapshot.get('userId'))
    review_ok,review_roles,_=_authority(actor,'production.operation.complete.approve',task.workshop.department_id,task.assignment_snapshot.get('userId'))
    if not read_ok or not review_ok or not ({x['roleId'] for x in read_roles}&{x['roleId'] for x in review_roles}):return None
    # Navigation/read qualification needs the current exact reviewer duty, not
    # the entire completion page. The closure below still independently checks
    # every current generation, source, custody and actual predecessor receipt.
    from .operation_completion_service import _role,APPROVE_ACTION
    legacy=_role(actor,APPROVE_ACTION,task)
    if legacy['ready']:return legacy['currentActorEvidence']
    from .operation_completion_v3_authority import _role as quantitative_role
    current=quantitative_role(actor,task,'approve')
    return current['currentActorEvidence'] if current['ready'] else None

def _read_qualification(actor,task,row=None):
    source=source_qualification(actor,'read',task,row.pk if row else None,row.status if row else 'open',required=False)
    if source['ready']:return source,'本人真实末道任务及成品交接'
    if row and row.receiver_id==actor.pk:
        receiver=warehouse_qualification(actor,row.pk,row.status,required=False,purpose=row.work_order.usage_purpose)
        if receiver['ready'] and receiver['currentActorEvidence'].get('employeeId')==row.source_snapshot['destination']['receiverEmployeeId']:
            return receiver,'本人被明确指定的成品接收单'
    review=_review_read(actor,task)
    if review:return {'ready':True,'currentActorEvidence':review},'既有生产跟单独审职责内的整单追溯（只读）'
    return None,None

def _warehouse_result(row):
    purpose=row.work_order.usage_purpose
    """Read original WMS objects only after the transfer's native scope/proof checks."""
    receipt=row.data.get('warehouseReceipt')
    if not receipt:return None
    inbound=WarehouseInbound.all_objects.get(pk=receipt['inboundId'],production_transfer_id=row.pk,usage_purpose=purpose)
    stock=InventoryTransaction.all_objects.get(pk=receipt['transactionId'],source_inbound=inbound,usage_purpose=purpose)
    balance=InventoryBalance.all_objects.get(pk=receipt['balanceId'],warehouse_id=row.warehouse_id,
        location_id=row.location_id,material_id=row.material_id,lot_id=receipt['lotId'],usage_purpose=purpose)
    lot=InventoryLot.all_objects.get(pk=receipt['lotId'],material_id=row.material_id,warehouse_id=row.warehouse_id,usage_purpose=purpose)
    return {'factSource':'server','transferId':row.pk,'transferNo':row.no,
        'inboundId':inbound.pk,'inboundNo':inbound.inbound_no,'statusCode':inbound.status,'statusLabel':inbound.get_status_display(),
        'quantity':text(inbound.quantity),'uomId':row.uom_id,'uomLabel':row.source_snapshot['product']['uomLabel'],
        'warehouseName':row.source_snapshot['destination']['warehouseName'],'locationName':row.source_snapshot['destination']['locationName'],
        'inboundDate':inbound.inbound_date.isoformat(),'usagePurpose':purpose,
        'purposeLabel':'正式生产用途' if purpose=='PRODUCTION_USE' else '隔离TEST用途','lotId':lot.pk,'lotNo':lot.lot_no,
        'transaction':{'id':stock.pk,'no':stock.transaction_no,'sourceInboundId':stock.source_inbound_id,
            'directionLabel':stock.get_direction_display(),'quantity':text(stock.quantity),
            'beforeQuantity':text(stock.before_quantity),'afterQuantity':text(stock.after_quantity)},
        'balance':{'id':balance.pk,'quantity':text(balance.quantity)}}

def _row_facts(row):
    verify_header(row)
    history=verify_record(row)
    from masterdata.models import UnitOfMeasure
    units=dict(UnitOfMeasure.objects.filter(pk__in=[x['uomId'] for x in row.source_snapshot['terminalBatch']]).values_list('pk','name'))
    operators=dict(User.objects.filter(pk__in=[x['operatorId'] for x in history['statusTransitionHistory']]).values_list('pk','username'))
    return {'id':row.pk,'no':row.no,'usagePurpose':row.work_order.usage_purpose,'workOrderId':row.work_order_id,'workOrderNo':row.work_order.no,
        'terminalTaskId':row.task_id,'productName':row.source_snapshot['product']['materialName'],'quantity':row.quantity,
        'uomLabel':row.source_snapshot['product']['uomLabel'],'warehouseName':row.source_snapshot['destination']['warehouseName'],
        'locationName':row.source_snapshot['destination']['locationName'],'receiverName':row.source_snapshot['destination']['receiverEmployeeName'],
        'senderName':row.qualification_snapshot['currentActorEvidence']['employeeName'],'statusCode':row.status,'statusLabel':'成品已接收并正式用途入库' if row.status=='received' and row.work_order.usage_purpose=='PRODUCTION_USE' else LABELS[row.status],
        'version':row.version,'sourceSnapshotHash':row.source_snapshot_hash,'preparedAt':offset_iso(row.created_at),
        'dispatchedAt':offset_iso(row.dispatched_at) if row.dispatched_at else None,'receivedAt':row.data.get('receivedAt'),
        'warehouseReceipt':deepcopy(row.data.get('warehouseReceipt')),'warehouseResult':_warehouse_result(row),'executionClosureHash':row.source_snapshot['closureHash'],
        'nativeCompletionTaskCount':len(row.source_snapshot['executionClosure']['tasks']),
        'sourceWorkloadRanges':[{**deepcopy(x),'uomLabel':units.get(x['uomId'])} for x in row.source_snapshot['terminalBatch']],'conversionBasis':deepcopy(row.source_snapshot['conversionBasis']),
        'displayHistory':[{'id':x['id'],'statusLabel':LABELS[x['targetState']],'operatorUsername':operators[x['operatorId']],
            'occurredAt':x['timestamp'],'reason':x['reason'],'auditReference':x['auditReference']} for x in history['statusTransitionHistory']],
        'reason':row.reason,**history}

@scoped_execution_read
def read_finished_goods(*,user,work_order_id=None,transfer_id=None,recovery_action=None,request_hash=None,request_key_hash=None):
    actor=actor_for(user)
    for value in (work_order_id,transfer_id):strict_id(value,'成品读取对象',nullable=True)
    selected=None;qualification=None;scope=None;order=None;terminal=None
    if transfer_id is not None:
        selected=Transfer.objects.filter(pk=transfer_id,company_id=actor.company_id).select_related('work_order','task__workshop','created_by').first()
        if not selected:fail('FG_TRANSFER_NOT_VISIBLE','所选成品单不在本公司范围。',403)
        if work_order_id is not None and selected.work_order_id!=work_order_id:fail('FG_QUERY_OBJECT_MISMATCH','工单与成品单不一致。',400)
        qualification,scope=_read_qualification(actor,selected.task,selected)
        if qualification is None:fail('FG_READ_DENIED','无该末道本人、指定接收或既有独审读取范围。',403)
        work_order_id=selected.work_order_id
    from .work_order_models import ProductionWorkOrder
    options=[]
    for candidate in ProductionWorkOrder.objects.filter(company_id=actor.company_id,usage_purpose__in=('TEST_BUSINESS','PRODUCTION_USE')).select_related('source_schedule','material','uom'):
        try:_,_,last,_=task_graph(candidate)
        except PlanningBusinessError:continue
        q,label=_read_qualification(actor,last)
        if q is None:
            for existing in Transfer.objects.filter(work_order=candidate).order_by('-pk'):
                q,label=_read_qualification(actor,last,existing)
                if q:break
        if q:
            qualification=qualification or q;scope=scope or label
            options.append({'id':candidate.pk,'no':candidate.no,'usagePurpose':candidate.usage_purpose,'terminalTaskId':last.pk,'terminalTaskNo':last.no,'statusLabel':'本人职责范围内正式生产工单' if candidate.usage_purpose=='PRODUCTION_USE' else '本人职责范围内测试生产工单'})
    receiver_q=warehouse_qualification(actor,required=False)
    if not receiver_q['ready']:receiver_q=warehouse_qualification(actor,required=False,purpose='PRODUCTION_USE')
    if qualification is None and receiver_q['ready']:
        qualification=receiver_q;scope='本人被明确指定的成品接收单'
    if qualification is None:fail('FG_READ_DENIED','当前没有本人末道、指定成品接收或既有独审读取资格。',403)
    if work_order_id is not None:
        if not any(x['id']==work_order_id for x in options):fail('FG_READ_DENIED','请求工单超出当前本人／指定接收／独审范围。',403)
        order=order_for(actor,work_order_id);_,_,terminal,_=task_graph(order)
    headers=[]
    for row in Transfer.objects.filter(company_id=actor.company_id).select_related('work_order','task__workshop','created_by').order_by('-pk'):
        if work_order_id is not None and row.work_order_id!=work_order_id:continue
        if _read_qualification(actor,row.task,row)[0]:headers.append(_row_facts(row))
    if selected and not any(x['id']==selected.pk for x in headers):fail('FG_READ_DENIED','成品单已不在读取范围。',403)
    selected_facts=next((x for x in headers if selected and x['id']==selected.pk),None)
    source_q=source_qualification(actor,'prepare',terminal,required=False) if terminal else None
    closure=None;product=None;batch_hash=None;batch=[];blockers=[];current_valid=True
    if order:
        try:
            from .completed_closure_read_cache import read_completed_closure
            closure=read_completed_closure(order);product=product_basis(order);blockers+=closure['blockingReasons'];current_valid=closure['ready']
            if selected is None and source_q['ready']:
                try:_,batch,batch_hash=terminal_batch(terminal)
                except PlanningBusinessError as exc:blockers.append(exc.message)
        except (PlanningBusinessError,ArrangementError) as exc:blockers.append(getattr(exc,"message",str(exc)));current_valid=False
    purpose=order.usage_purpose if order else None
    destinations=[];receivers=[]
    if source_q and source_q['ready'] and selected is None:
        for wh in Warehouse.all_objects.filter(company_id=actor.company_id,usage_purpose=purpose,is_active=True):
            locations=[{'id':x.pk,'code':x.code,'name':x.name} for x in WarehouseLocation.all_objects.filter(warehouse=wh,is_active=True)]
            if locations:destinations.append({'id':wh.pk,'code':wh.code,'name':wh.name,'locations':locations})
        from system.models import UserRoleScopeAssignment,RolePermission
        from .finished_goods_contract import RECEIVE
        if purpose=='PRODUCTION_USE':
            from .finished_goods_formal_contract import RECEIVE
        receiving_roles=RolePermission.objects.filter(permission__code=RECEIVE).values_list('role_id',flat=True)
        account_ids=UserRoleScopeAssignment.objects.filter(organization_id=actor.company_id,active=True,role_id__in=receiving_roles).values_list('user_id',flat=True).distinct()
        for person in User.objects.defer('password').filter(pk__in=account_ids,company_id=actor.company_id,is_active=True,is_superuser=False):
            q=warehouse_qualification(person,required=False,purpose=purpose)
            if q['ready'] and q['currentActorEvidence']['employeeId']!=source_q['currentActorEvidence']['employeeId']:
                receivers.append({'id':person.pk,'employeeName':q['currentActorEvidence']['employeeName'],'username':person.username})
        if not destinations or not receivers:blockers.append('须维护与本工单用途一致的成品仓、有效库位及既有仓库职责的指定接收人。')
        if Transfer.objects.filter(work_order=order,status__in=('prepared','in_transit','received')).exists():blockers.append('本工单已有有效整批成品交接，请读取原单。')
    actions={}
    for key in ('prepare','dispatch','cancel','receive'):
        contract=action_contract(key,selected.pk if selected else None,purpose=purpose or 'TEST_BUSINESS');issues=[]
        if key=='prepare':
            q=source_q
            if not q or not q['ready']:issues.append('须由真实末道获派班组长选择本人已完成工单。')
            issues+=blockers
            if selected:issues.append('请返回工单读取后备交，不对已有单重复生成。')
        else:
            q=warehouse_qualification(actor,selected.pk,selected.status,required=False,purpose=selected.work_order.usage_purpose) if selected and key=='receive' else source_qualification(actor,key,terminal,selected.pk,selected.status,required=False) if selected else None
            expected='in_transit' if key=='receive' else 'prepared'
            if not selected or selected.status!=expected:issues.append('当前单据不在该动作所需状态。')
            if not q or not q['ready']:issues.append('当前账号不具备本单该动作职责及权限。')
            if key=='receive' and selected and selected.receiver_id!=actor.pk:issues.append('当前账号不是原单明确指定的接收人。')
            if key!='cancel':issues+=blockers
        actions[key]={**contract,'enabled':not issues,'disabledReason':'；'.join(dict.fromkeys(issues)),
            'requestObjectId':order.pk if key=='prepare' and order else selected.pk if selected else None}
    recovery={'status':'not_requested','originalIntentProof':None}
    if recovery_action is not None:
        import re
        recovery_key=next((k for k,v in codes_for(purpose or 'TEST_BUSINESS').items() if v==recovery_action and k!='read'),None)
        if recovery_key is None or not all(isinstance(x,str) and re.fullmatch('[a-f0-9]{64}',x) for x in (request_hash,request_key_hash)):
            fail('FG_RECOVERY_QUERY_INVALID','原请求核查须有准确动作及两个不可逆摘要。',400)
        from masterdata.models import MasterDataWriteRequest
        ledger=MasterDataWriteRequest.objects.filter(organization_id=actor.company_id,entity_type='ProductionFinishedGoodsTransfer',
            action_code=recovery_action,request_hash=request_hash,source_identity__external_id=request_key_hash,status='COMMITTED',audit_metadata__actorId=actor.pk).first()
        if ledger:
            result=Transfer.objects.get(pk=ledger.target_entity_id,company_id=actor.company_id)
            if not _read_qualification(actor,result.task,result)[0]:fail('FG_READ_DENIED','原请求结果不在当前读取范围。',403)
            verify_header(result)
            recovery={'status':'verified','actionCode':ledger.action_code,'actorId':actor.pk,'requestHash':request_hash,'requestKeyHash':request_key_hash,
                'objectId':ledger.result['originalObjectId'],'resultObjectId':result.pk,'proofReference':'MasterDataWriteRequest:'+str(ledger.pk),
                'originalIntentProof':{'verified':True,'actionCode':ledger.action_code,'actorId':actor.pk,
                'requestHash':request_hash,'requestKeyHash':request_key_hash,'originalObjectId':ledger.result['originalObjectId'],
                'resultObjectId':result.pk,'sourceSnapshotHash':result.source_snapshot_hash,'usagePurpose':result.work_order.usage_purpose}}
        else:recovery={'status':'unknown','actionCode':recovery_action,'actorId':actor.pk,'requestHash':request_hash,
            'requestKeyHash':request_key_hash,'originalIntentProof':None}
    return {'contractVersion':'PCE-TEST-PRODUCTION-FINISHED-GOODS-V1','moduleCode':MODULE,'factSource':'server','currentStateSource':'server',
        'companyId':actor.company_id,'usagePurpose':purpose or ('MIXED_AUTHORIZED' if any(x['usagePurpose']=='PRODUCTION_USE' for x in options) else 'TEST_BUSINESS'),'purposeLabel':('正式生产用途；独立开发样本，尚未授予企业试点放行' if purpose=='PRODUCTION_USE' else '按当前授权逐单核实原生用途；目录不授予写入资格' if purpose is None else '隔离测试用途；成品测试入库与正式库存隔离，测试代办按真实账号留痕，不冒称用户本人点击。'),
        'currentActorEvidence':qualification['currentActorEvidence'],'readScopeLabel':scope,'workOrderOptions':options,'transfers':headers,
        'selectedTransfer':selected_facts,'selectedWorkOrder':None if not order else {'id':order.pk,'no':order.no,'usagePurpose':order.usage_purpose,'terminalTaskId':terminal.pk,
            'terminalTaskNo':terminal.no,'product':product,'closureReady':bool(closure and closure['ready']),'closureStatusLabel':'生产执行已独审完结' if closure and closure['ready'] else '生产执行完结证明未满足',
            'expectedClosureHash':closure['hash'] if closure else None,'expectedTerminalBatchHash':batch_hash,'terminalWorkloadRanges':batch,
            'expectedTaskVersion':terminal.version,'expectedTaskSourceSnapshotHash':terminal.source_snapshot_hash},
        'currentSourceValid':current_valid,'blockingReasons':blockers,'availableActions':actions,'destinationChoices':destinations,'receiverChoices':receivers,
        'resultRecovery':recovery,'filterOptions':{'statusLabels':sorted({x['statusLabel'] for x in headers})},
        'passed':current_valid,'businessWriteCount':0,'auditWriteCount':0,'actualStartCount':0,'actualReportCount':0,'inventoryUpdatedCount':0}

def product_basis(order):
    quantity=Decimal(order.quantity);unit=order.uom;material=order.material
    if (quantity<=0 or quantity!=quantity.quantize(Decimal('0.0001')) or not unit or not unit.is_active
        or unit.company_id!=order.company_id or material.company_id!=order.company_id or not material.is_active
        or material.base_uom_id!=unit.pk or material.unit_status!='confirmed'):
        fail('FG_PRODUCT_UNIT_UNPROVEN','原产品与库存基础单位须明确一致且符合原WMS精度；不猜换算、不舍入。')
    number(text(quantity),positive=True,precision=unit.decimal_places)
    return {'materialId':material.pk,'materialCode':material.code,'materialName':material.name,'quantity':text(quantity),
        'uomId':unit.pk,'uomLabel':unit.name,'decimalPlaces':min(4,unit.decimal_places),'sourceProduct':product_source(order)}

def terminal_batch(task):
    verify_task_custody(task)
    leaves=list(Slice.objects.filter(root__task=task).exclude(status='closed').select_related('root'))
    if not leaves or any(s.status not in ('U','S','V') or s.frozen or s.reserved_by_id or custody_responsibility(s)!=task.work_center_id for s in leaves):
        fail('FG_TERMINAL_BATCH_NOT_AVAILABLE','末道完整批次尚未全部在本人责任范围可交；不能拿在途、短收、已投入或已占用份额凑成品。')
    basis=[{'sliceId':s.pk,'version':s.version,'rootId':s.root_id,'sourceSnapshotHash':s.source_snapshot_hash,
        'rootSourceHash':s.root.source_snapshot_hash,'quantity':s.quantity,'uomId':s.root.uom_id,
        'startAtom':s.start_atom,'endAtom':s.end_atom} for s in leaves]
    return leaves,basis,_hash(basis)

def resources(actor,warehouse_id,location_id,receiver_id,*,purpose=TEST):
    warehouse=Warehouse.all_objects.filter(pk=warehouse_id,company_id=actor.company_id,usage_purpose=purpose,is_active=True).first()
    location=WarehouseLocation.all_objects.filter(pk=location_id,warehouse=warehouse,is_active=True).first() if warehouse else None
    receiver=User.objects.defer('password').filter(pk=receiver_id,company_id=actor.company_id,is_active=True,is_superuser=False).first()
    if not warehouse or not location or not receiver:fail('FG_EXPLICIT_TEST_DESTINATION_REQUIRED','须明确与本工单同用途、同公司有效成品仓、准确库位和既有普通接收账号，不使用其他用途仓或猜填对象。')
    q=warehouse_qualification(receiver,purpose=purpose)
    return warehouse,location,receiver,q

def resource_snapshot(warehouse,location,receiver,q):
    return {'warehouseId':warehouse.pk,'warehouseCode':warehouse.code,'warehouseName':warehouse.name,'warehouseUpdatedAt':warehouse.updated_at.isoformat(),
        'locationId':location.pk,'locationCode':location.code,'locationName':location.name,'locationUpdatedAt':location.updated_at.isoformat(),
        'usagePurpose':warehouse.usage_purpose,'receiverUserId':receiver.pk,'receiverEmployeeId':q['currentActorEvidence']['employeeId'],
        'receiverEmployeeName':q['currentActorEvidence']['employeeName']}

def _slices(row):
    rows=list(Slice.objects.filter(pk__in=row.data['reservedSliceIds'],root__task_id=row.task_id,company_id=row.company_id).select_related('root'))
    if len(rows)!=len(row.data['reservedSliceIds']):fail('FG_RESERVED_SCOPE_MISSING','成品备交所占原始份额缺失。')
    return rows

def verify_header(row,*,admission=False):
    purpose=row.work_order.usage_purpose
    verify_record(row)
    source=row.source_snapshot
    if (source.get('usagePurpose')!=purpose or source.get('workOrderId')!=row.work_order_id
        or source.get('companyId')!=row.company_id or source.get('terminalTaskId')!=row.task_id
        or source.get('product',{}).get('materialId')!=row.material_id or source['product']['uomId']!=row.uom_id
        or Decimal(source['product']['quantity'])!=Decimal(row.quantity)
        or source.get('destination',{}).get('warehouseId')!=row.warehouse_id or source['destination']['locationId']!=row.location_id
        or source['destination']['receiverUserId']!=row.receiver_id):fail('FG_HEADER_SOURCE_DAMAGED','成品单与原产品、用途、任务或接收资源不一致。')
    if admission:
        order=order_for(row.created_by,row.work_order_id)
        verify_frozen_closure(order,source['executionClosure'])
        current=product_basis(order)
        if current!=source['product']:fail('FG_PRODUCT_CHANGED','原产品或库存单位已变化。')
        wh,location,receiver,q=resources(row.created_by,row.warehouse_id,row.location_id,row.receiver_id,purpose=purpose)
        if resource_snapshot(wh,location,receiver,q)!=source['destination']:fail('FG_DESTINATION_CHANGED','仓、库位或明确接收身份已变化，请核查原备交。')
    rows=_slices(row)
    if row.status in ('prepared','in_transit'):
        if WarehouseInbound.all_objects.filter(production_transfer=row).exists():fail('FG_WMS_PARTIAL_RESULT_UNPROVEN','原单出现未核定入库关联；禁止重复创建，须核查原结果。')
        expected=set(row.data['reservedSliceIds'])
        if any(s.data.get('finishedGoodsTransferId')!=row.pk or (row.status=='prepared' and (not s.frozen or s.status not in ('U','S','V')))
            or (row.status=='in_transit' and s.status!='I') for s in rows):fail('FG_RESERVED_SCOPE_CHANGED','原成品份额已变化或不在准确备交／在途状态。')
    if row.status=='received':
        events=list(Event.objects.filter(task_id=row.task_id,kind='FG_WAREHOUSE_ACCEPT',data__finishedGoodsTransferId=row.pk))
        if len(events)!=1:fail('FG_RECEIPT_EVENT_MISSING','成品入库缺少唯一MES保管转化事件。')
        verify_record(events[0]);verify_warehouse_conversion(events[0])
    return True

def _inbound_audit(actor,inbound,q,source_status,target_status,reason):
    CODES=codes_for(inbound.usage_purpose)
    state={'status':target_status,'usagePurpose':inbound.usage_purpose,'productionTransferId':inbound.production_transfer_id,'quantity':text(inbound.quantity),
        'warehouseId':inbound.warehouse_id,'locationId':inbound.location_id,'operatorEmployeeId':inbound.operator_employee_id,
        'authorization':q['authorization'],'actionPermissionDecision':q['actionPermissionDecision'],'qualification':q}
    return OrganizationOperatingAuditRecord.objects.create(actor=actor,organization_id=actor.company_id,action_code=CODES['receive'],
        target_type='WarehouseInbound',target_id=inbound.pk,target_label=inbound.inbound_no,reason=reason,
        before_snapshot={'state':{'status':source_status}},after_snapshot={'state':state,'workflowNode':{'processCode':q['actionContract']['workflowProcessCode'],
        'nodeId':q['nodeId'],'nodeCode':q['currentActorEvidence']['workflowNodeCode']}})

def _warehouse_receive(actor,row,q,reason,digest):
    purpose=row.work_order.usage_purpose
    CODES=codes_for(purpose)
    from procurement.inventory_posting import post_inbound_stock
    from pfm.models import Employee
    stamp=timezone.now();employee=Employee.objects.get(pk=q['currentActorEvidence']['employeeId'])
    if row.receiver_id!=actor.pk or row.source_snapshot['destination']['receiverEmployeeId']!=employee.pk:
        fail('FG_ASSIGNED_RECEIVER_REQUIRED','只有原备交明确指定的真实仓管本人可接收。',403)
    if row.sender_employee_id==employee.pk:fail('FG_RECEIPT_SEPARATION_REQUIRED','成品交出与仓库接收须由不同真实员工办理。',403)
    with (test_purpose_write_scope() if purpose=='TEST_BUSINESS' else nullcontext()):
        inbound=create_business_object_with_initial_state(model=WarehouseInbound,initial_state='planned',
            inbound_no=_next_number('TFIN' if purpose=='TEST_BUSINESS' else 'FIN',WarehouseInbound,'inbound_no',include_test=True),source_inspection=None,production_transfer=row,
            usage_purpose=purpose,warehouse=row.warehouse,location=row.location,quantity=Decimal(row.quantity),amount=Decimal('0'),
            items=[{'materialId':row.material_id,'quantity':row.quantity,'uomId':row.uom_id,'usagePurpose':purpose,'productionTransferId':row.pk}],
            inbound_date=stamp.date(),operator_employee=employee,operator_account_id=actor.pk)
        audit=_inbound_audit(actor,inbound,q,'','planned',reason)
        record_projected_business_transition(object_type='WarehouseInbound',object_id=inbound.pk,source_state='',target_state='planned',
            action_code=CODES['receive'],operator=actor,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('','planned')})
        for target in ('processing','completed'):
            before=inbound.status
            if target=='completed':
                lot=InventoryLot.all_objects.create(lot_no=('TEST-FG-' if purpose=='TEST_BUSINESS' else 'FG-')+str(row.pk),material_id=row.material_id,company_id=row.company_id,
                    warehouse=row.warehouse,production_date=stamp.date(),is_active=True,usage_purpose=purpose)
                balance,stock_transaction=post_inbound_stock(inbound=inbound,warehouse=row.warehouse,location=row.location,
                    material_id=row.material_id,lot=lot,quantity=Decimal(row.quantity),employee=employee,user=actor)
            audit=_inbound_audit(actor,inbound,q,before,target,reason)
            transition_business_object(business_object=inbound,object_type='WarehouseInbound',source_state=before,target_state=target,
                action_code=CODES['receive'],operator=actor,reason=reason,audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',
                allowed_transitions={(before,target)},version_field=None)
    receipt={'inboundId':inbound.pk,'lotId':lot.pk,'balanceId':balance.pk,'transactionId':stock_transaction.pk,
        'quantity':row.quantity,'uomId':row.uom_id,'usagePurpose':purpose}
    project(row,receiver_employee=employee,data={**row.data,'warehouseReceipt':receipt,'receivedAt':offset_iso(stamp)})
    transition(row,'received',actor=actor,code=CODES['receive'],q=q,reason=reason)
    slices=_slices(row)
    for leaf in slices:
        transition(leaf,'C',actor=actor,code=CODES['receive'],q=q,reason=reason)
        audited_projection(leaf,actor=actor,code=CODES['receive'],q=q,reason=reason,holder_workshop_id=None,holder_work_center_id=None,
            frozen=False,data={**leaf.data,'finishedGoodsWarehouseReceipt':receipt})
    custody_event(actor=actor,code=CODES['receive'],q=q,task=row.task,kind='FG_WAREHOUSE_ACCEPT',quantity=add(*(s.quantity for s in slices)),
        debit='I',credit='C',stamp=stamp,intent_hash=digest,reason=reason,slices=slices,
        data={'finishedGoodsTransferId':row.pk,'usagePurpose':purpose,'warehouseReceipt':receipt,'conversionBasis':row.source_snapshot['conversionBasis']})

def execute_finished_goods(*,user,action,payload,transfer_id=None):
    if action not in ('prepare','dispatch','cancel','receive'):fail('FG_ACTION_INVALID','未登记的成品动作。',400)
    actor=actor_for(user);base={'reason','idempotencyKey'}
    if action=='prepare':
        fields=base|{'workOrderId','terminalTaskId','expectedTaskVersion','expectedTaskSourceSnapshotHash','expectedClosureHash',
            'expectedTerminalBatchHash','quantity','warehouseId','locationId','receiverUserId'}
        payload_guard(payload,fields,fields)
        for key in ('workOrderId','terminalTaskId','warehouseId','locationId','receiverUserId'):strict_id(payload[key],key)
        strict_id(payload['expectedTaskVersion'],'期望任务版本',zero=True)
        task_id=payload['terminalTaskId']
    else:
        payload_guard(payload,base|{'expectedVersion','expectedSourceSnapshotHash'},base|{'expectedVersion','expectedSourceSnapshotHash'})
        strict_id(transfer_id,'成品交接单')
        strict_id(payload['expectedVersion'],'期望成品单版本',zero=True)
        hint=Transfer.objects.filter(pk=transfer_id,company_id=actor.company_id).values('task_id').first()
        if not hint:fail('FG_TRANSFER_NOT_VISIBLE','成品交接单不在本公司范围。',403)
        task_id=hint['task_id']
    with transaction.atomic(),verification_context():
        account=lock_accounts(actor,[task_id])[task_id];actor=actor_for(actor)
        before=_write_markers()
        if action=='prepare':
            order=order_for(actor,payload['workOrderId']);_,_,task,_=task_graph(order)
            if task.pk!=task_id:fail('FG_TERMINAL_TASK_MISMATCH','不是本工单真实终结任务。',403)
            q=source_qualification(actor,action,task)
            object_id=order.pk;purpose=order.usage_purpose
        else:
            row=Transfer.objects.select_related('task','work_order','created_by','warehouse','location').get(pk=transfer_id,company_id=actor.company_id)
            verify_header(row)
            q=warehouse_qualification(actor,row.pk,row.status,purpose=row.work_order.usage_purpose) if action=='receive' else source_qualification(actor,action,row.task,row.pk,row.status)
            if action=='receive' and row.receiver_id!=actor.pk:fail('FG_ASSIGNED_RECEIVER_REQUIRED','本单没有指定当前账号接收。',403)
            object_id=row.pk;purpose=row.work_order.usage_purpose
        CODES=codes_for(purpose)
        digest,replay=intent(actor,CODES[action],object_id,payload)
        if replay:
            if replay.entity_type!='ProductionFinishedGoodsTransfer':fail('FG_IDEMPOTENCY_CONFLICT','原请求绑定其他业务对象。')
            existing=Transfer.objects.get(pk=replay.target_entity_id,company_id=actor.company_id)
            verify_header(existing)
            result_id=existing.pk;replayed=True
        else:
            stamp=timezone.now();reason=payload['reason'].strip();replayed=False
            if action=='prepare':
                if Transfer.objects.filter(work_order=order,status__in=('prepared','in_transit','received')).exists():fail('FG_ORDER_ALREADY_BOUND','本工单已有有效整批成品交接，不换标识重复占额。')
                closure=current_closure(order)
                if not closure['ready']:fail('FG_ORDER_NOT_COMPLETE','；'.join(closure['blockingReasons']))
                leaves,batch,batch_hash=terminal_batch(task);product=product_basis(order)
                if (payload['expectedTaskVersion']!=task.version or payload['expectedTaskSourceSnapshotHash']!=task.source_snapshot_hash
                    or payload['expectedClosureHash']!=closure['hash'] or payload['expectedTerminalBatchHash']!=batch_hash):
                    fail('FG_SOURCE_OR_VERSION_CHANGED','工单独审、末道份额或版本已变化，请只读重读。')
                quantity=number(payload['quantity'],positive=True,precision=product['decimalPlaces'])
                if quantity!=Decimal(product['quantity']):fail('FG_WHOLE_PRODUCT_QUANTITY_REQUIRED','本版终端为整单整批；须明确原产品完整数量，不能把末道工作量当成品数。')
                wh,location,receiver,receiver_q=resources(actor,payload['warehouseId'],payload['locationId'],payload['receiverUserId'],purpose=purpose)
                if receiver_q['currentActorEvidence']['employeeId']==q['currentActorEvidence']['employeeId']:fail('FG_RECEIPT_SEPARATION_REQUIRED','交出与接收须为不同实际员工。',403)
                source={'usagePurpose':purpose,'companyId':actor.company_id,'workOrderId':order.pk,'terminalTaskId':task.pk,
                    'executionClosure':closure['manifest'],'closureHash':closure['hash'],'product':product,
                    'destination':resource_snapshot(wh,location,receiver,receiver_q),'terminalBatch':batch,
                    'conversionBasis':{'kind':'WHOLE_WORK_ORDER_PRODUCT_OBJECT','workOrderSnapshotHash':order.snapshot_hash,
                        'originalProduct':product_source(order),'terminalWorkloadRanges':batch,
                        'productQuantity':product['quantity'],'productUomId':product['uomId'],'numericalEqualityRequired':False}}
                row=initialize(Transfer,actor=actor,code=CODES[action],q=q,status='prepared',source=source,intent_hash=digest,reason=reason,
                    no=_next_number('TFG' if purpose=='TEST_BUSINESS' else 'FG',Transfer,'no'),work_order=order,task=task,material_id=order.material_id,quantity=text(quantity),uom_id=order.uom_id,
                    warehouse=wh,location=location,receiver=receiver,data={'reservedSliceIds':[s.pk for s in leaves]})
                for leaf in leaves:
                    audited_projection(leaf,actor=actor,code=CODES[action],q=q,reason=reason,frozen=True,version=leaf.version+1,
                        data={**leaf.data,'finishedGoodsTransferId':row.pk})
                custody_event(actor=actor,code=CODES[action],q=q,task=task,kind='FG_PREPARE',quantity=add(*(s.quantity for s in leaves)),debit='',credit='',
                    stamp=stamp,intent_hash=digest,reason=reason,slices=leaves,data={'finishedGoodsTransferId':row.pk,'usagePurpose':purpose,'effectiveOutputDelta':'0'})
                bump(account,'release')
            else:
                if payload['expectedVersion']!=row.version or payload['expectedSourceSnapshotHash']!=row.source_snapshot_hash:
                    fail('FG_SOURCE_OR_VERSION_CHANGED','成品单版本或来源已变化。')
                expected='in_transit' if action=='receive' else 'prepared'
                if row.status!=expected:fail('FG_STATE_NOT_READY','本单不在该动作所需状态，不能换key重复执行。')
                verify_header(row,admission=action!='cancel');leaves=_slices(row)
                if action=='dispatch':
                    project(row,sender_employee_id=q['currentActorEvidence']['employeeId'],dispatched_at=stamp)
                    transition(row,'in_transit',actor=actor,code=CODES[action],q=q,reason=reason)
                    for leaf in leaves:
                        transition(leaf,'I',actor=actor,code=CODES[action],q=q,reason=reason)
                        audited_projection(leaf,actor=actor,code=CODES[action],q=q,reason=reason,frozen=False,
                            holder_workshop_id=None,holder_work_center_id=None)
                    kind='FG_DISPATCH';debit='U/S/V';credit='I'
                elif action=='cancel':
                    for leaf in leaves:
                        audited_projection(leaf,actor=actor,code=CODES[action],q=q,reason=reason,frozen=False,version=leaf.version+1,
                            data={**leaf.data,'finishedGoodsTransferId':None})
                    transition(row,'cancelled',actor=actor,code=CODES[action],q=q,reason=reason)
                    kind='FG_CANCEL';debit='';credit=''
                else:
                    _warehouse_receive(actor,row,q,reason,digest);kind=None
                if kind:
                    custody_event(actor=actor,code=CODES[action],q=q,task=row.task,kind=kind,quantity=add(*(s.quantity for s in leaves)),debit=debit,credit=credit,
                        stamp=stamp,intent_hash=digest,reason=reason,slices=leaves,data={'finishedGoodsTransferId':row.pk,'usagePurpose':purpose,'effectiveOutputDelta':'0'})
                bump(account,'custody')
            commit_intent(actor,CODES[action],payload,digest,row,{'transferId':row.pk,'workOrderId':row.work_order_id,
                'taskId':row.task_id,'originalObjectId':object_id,'usagePurpose':purpose})
            verify_header(row);verify_task_custody(row.task);result_id=row.pk
        writes=_actual_writes(before,Transfer.objects.get(pk=result_id),actor,action,replayed)
    facts=read_finished_goods(user=actor,transfer_id=result_id)
    facts['operationResult']={'transferId':result_id,'idempotent':replayed}
    facts.update(writes)
    return facts,writes
