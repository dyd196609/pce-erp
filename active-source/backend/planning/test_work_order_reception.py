"""Read-only test source reception; physical contract decides schema support."""
from decimal import Decimal
from django.db import connection
from workflow_runtime.models import WorkflowNodeDefinition
from pde.models import OrderRoutingExecutionArrangement,EngineeringOperationRequirement
from pde.order_routing_execution_service import fail
from .test_scheduling_service import read as read_schedule
from .work_order_release_admission_contract import ALLOWED_ORDER_STATES,PROCESS,WORKFLOW_NODE

def _read_source(*,user,arrangement_id,schedule_id,expected_snapshot_hash=None):
    saved=read_schedule(user=user,arrangement_id=arrangement_id)
    current=saved['activeSchedule']
    if current is None or current['id']!=schedule_id or not current['currentSourceValid']:
        fail('WORK_ORDER_CURRENT_TEST_SCHEDULE_REQUIRED','指定排程不是本安排当前有效测试来源；历史、取消或失效版本不能承接。')
    if expected_snapshot_hash is not None and expected_snapshot_hash!=current['snapshotHash']:
        fail('WORK_ORDER_SCHEDULE_VERSION_CHANGED','排程冻结凭据不一致，请重新读取，不能承接旧凭据。')
    arr=OrderRoutingExecutionArrangement.objects.select_related('source_calculation__sales_order_item__sales_order','source_calculation__sales_order_item__material','source_calculation__sales_order_item__uom').get(pk=arrangement_id,company_id=user.company_id)
    item=arr.source_calculation.sales_order_item
    if item.sales_order.status not in ALLOWED_ORDER_STATES:
        fail('WORK_ORDER_ORDER_STATE_INVALID','订单当前状态不符合已有工单承接规范。')
    if item.sales_order.company_id!=user.company_id or item.material is None or item.material.company_id!=user.company_id or not item.material.is_active or item.uom is None or item.uom.company_id!=user.company_id or not item.uom.is_active or item.quantity<=0:
        fail('WORK_ORDER_PRODUCT_SOURCE_UNPROVEN','订单行产品、公司、正数数量或有效单位未获证明。')
    if item.quantity.quantize(Decimal(1).scaleb(-item.uom.decimal_places))!=item.quantity:
        fail('WORK_ORDER_UOM_PRECISION_INVALID','产品数量不符合有效单位精度，不舍入或隐式换算。')
    from .models import FormalProductionSchedule
    header=FormalProductionSchedule.objects.get(pk=current['id'],company_id=user.company_id)
    v=header.snapshot['preview'];rows=[];required=[]
    for step in v['rows']:
        row={k:step[k] for k in ('stepId','sequence','operationId','operationName','decision','decisionBasis','workloadQuantity','workloadUnitLabel','start','end','workCenterId','workCenterName')}
        row['statusLabel']='执行（候选，尚未生成工单）' if step['decision']=='REQUIRED' else '不执行（保留原依据）'
        if step['decision']=='REQUIRED':
            ref=step['savedWorkloadReference'];req=EngineeringOperationRequirement.objects.get(pk=ref['id'],execution_arrangement=arr,routing_step_id=step['stepId'])
            if req.basis_quantity!=item.quantity or req.basis_uom_id!=item.uom_id or req.arrangement_revision!=arr.arrangement_revision or req.arrangement_edit_version!=arr.edit_version:
                fail('WORK_ORDER_PRODUCT_BASIS_CHANGED','当前订单数量或单位与已保存投产基准不一致，不从作业量推算产品数量。')
            required.append(req.pk);row['requirementId']=req.pk
        rows.append(row)
    table='planning_production_work_order'
    with connection.cursor() as cursor:
        tables=connection.introspection.table_names(cursor)
        columns={x.name:x for x in connection.introspection.get_table_description(cursor,table)} if table in tables else {}
        blockers=[]
        if 'usage_purpose' not in columns:blockers.append('现有工单主表没有持久用途字段，不能可靠隔离测试工单。')
        if 'production_plan_id' not in columns or not columns['production_plan_id'].null_ok:blockers.append('工单主表强制关联正式生产计划；本单测试排程没有正式计划，不得冒用。')
        if 'source_schedule_id' not in columns:blockers.append('工单主表缺少可靠排程来源关联。')
        cursor.execute('SELECT COUNT(*) FROM planning_production_work_order WHERE company_id=%s',[user.company_id]);legacy=cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM planning_processing_reservation WHERE schedule_id=%s AND released_at IS NULL',[schedule_id]);segments=cursor.fetchone()[0]
    nodes=list(WorkflowNodeDefinition.objects.filter(node_code=WORKFLOW_NODE,process_definition__definition_code=PROCESS,active=True).select_related('process_definition'))
    if len(nodes)!=1:fail('WORK_ORDER_WORKFLOW_NODE_AMBIGUOUS','系统已登记工单节点缺失或不唯一，不能自行选择。')
    node=nodes[0]
    workflow={'processCode':node.process_definition.definition_code,'processName':node.process_definition.definition_name,'nodeId':node.pk,'nodeCode':node.node_code,'nodeName':node.node_name,'actionCode':node.business_action_code} if node else None
    if node is None:fail('WORK_ORDER_WORKFLOW_NODE_MISSING','系统未登记适用生产工单节点，不能凭页面名称推定入口。')
    return {'contractVersion':'PCE-TEST-WORK-ORDER-RECEPTION-V1','factSource':'server','requestIdentity':saved['requestIdentity'],'scope':saved['scope'],
        'sourceSchedule':current,'workflow':workflow,'formalReceptionApiTemplate':'/api/planning/production-plans/{productionPlanId}/work-order-reception/','formalGenerationApiTemplate':'/api/planning/production-plans/{productionPlanId}/work-order/generate/',
        'product':{'orderId':item.sales_order_id,'orderNo':item.sales_order.order_no,'salesOrderItemId':item.pk,'materialId':item.material_id,'materialCode':item.material.code,'materialName':item.material.name,'quantity':str(item.quantity),'uomId':item.uom_id,'uomLabel':item.uom.name,'sourceLabel':'有效订单行及逐条已保存需求投产基准一致；不是工序作业量或占用段数之和'},
        'rows':rows,'summary':{'executingSteps':len(required),'skippedSteps':sum(r['decision']=='NOT_APPLICABLE' for r in rows),'reservationSegments':segments},'existingWorkOrderCount':legacy,'newWorkOrderCount':0,'newWorkOrderOperationCount':0,
        'canGenerate':False,'blockerCode':'TEST_WORK_ORDER_STRUCTURE_EXTENSION_REQUIRED' if blockers else 'TEST_WORK_ORDER_SOURCE_ADAPTER_REQUIRED','blockers':blockers,
        'statusLabel':'测试工单尚未生成；承接来源已核对，保存结构待扩展','formalManufacturingEligible':False,'releaseAllowed':False,'databaseBusinessWriteCount':0}


def read_reception(**kwargs):
    from .test_work_order_service import read
    return read(**kwargs)
