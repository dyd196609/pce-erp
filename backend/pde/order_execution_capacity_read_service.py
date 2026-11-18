"""Read-only test capacity/calendar handoff over saved arrangement workloads."""
from .order_execution_workload_read_service import read_arrangement_workload,fail
from .models import StandardCapacity,CapacityProductType,WorkCenter,RoutingStep
from .operation_requirement_service import _active,_today
from .daily_capacity_service import capacity_fact,capacity_source_rules,duration_days
from .manufacturing_capacity_scope import capacity_usage_scope_proof
from .routing_planning_readiness_service import RoutingPlanningReadinessService as Calendars
from decimal import Decimal
CONTRACT='PCE-ORDER-TEST-CAPACITY-READ-V1'
from django.db import transaction
from django.db.models import Q
from .capacity_evidence_read_scope import capacity_evidence_scope

@transaction.atomic
@capacity_evidence_scope
def read_capacity_review(*,user,arrangement_id):
 workload=read_arrangement_workload(user=user,arrangement_id=arrangement_id)
 if workload['scope']['usagePurpose']!='TEST_BUSINESS':fail('TEST_PURPOSE_REQUIRED','此无日期核对仅承接测试安排')
 kind=CapacityProductType.objects.get(pk=workload['productType']['id'],company_id=user.company_id) if workload['productType'] else None
 proof=capacity_source_rules(kind,company_id=user.company_id,on_date=_today()) if kind else None
 fixed_steps=RoutingStep.objects.in_bulk([x['stepId'] for x in workload['steps']])
 capacity_index={}
 if kind:
  center_ids={x['workCenterId'] for x in workload['steps']}
  centers=Q(work_center_id__in=center_ids)
  if None in center_ids:centers|=Q(work_center_id__isnull=True)
  for cap in StandardCapacity.objects.filter(centers,company_id=user.company_id,product_type=kind,operation_id__in={x['operationId'] for x in workload['steps']}).select_related('operation','product_type__product_category','product_type__manufacturing_process_type','work_center','uom'):
   capacity_index.setdefault((cap.operation_id,cap.work_center_id),[]).append(cap)
 rows=[]
 for step in workload['steps']:
  row={k:step[k] for k in ('stepId','sequence','operationId','operationName','decision','decisionLabel','workloadQuantity','workloadUnitLabel','workloadUnitId','workCenterId','workCenterName')}
  row.update(capacity=None,calendar=None,result=None,issues=[])
  row['decisionBasis']=step.get('basis','')
  row['savedWorkloadReference']=step.get('savedWorkload')
  if step['decision']!='REQUIRED':
   row['statusLabel']='本场景不执行；不计算产能天数' if step['decision']=='NOT_APPLICABLE' else '执行待核定；不计算';rows.append(row);continue
  candidates=[c for c in capacity_index.get((step['operationId'],step['workCenterId']),[]) if _active(c)] if kind else []
  if len(candidates)!=1:row['issues'].append('准确范围有效产能记录数量为'+str(len(candidates))+'，不能自动选择')
  if not step['savedWorkload']:row['issues'].append('缺少当前安排有效已保存作业量')
  if len(candidates)==1:
   cap=candidates[0];fact=capacity_fact(cap,on_date=_today(),source_rules=proof)
   simulated=cap.conditions.get('measurementEvidenceType')=='SIMULATED_TEST'
   if simulated:
    scope=capacity_usage_scope_proof(cap)
    available=scope is not None and cap.conditions.get('testPurpose')=='TEST_BUSINESS'
   else:available=fact['available']
   row['capacity']={**fact,'evidenceLabel':'模拟测试正数产能（非实测）' if simulated else '既有基础资料已保存标准产能','testOnly':simulated,'sourceVersion':cap.conditions.get('capacityUsageScope',{}).get('version') or cap.effective_from.isoformat(),'sourceBasis':cap.conditions.get('testBasis') if simulated else {'sourceCell':cap.conditions.get('sourceCell'),'sourceHash':cap.conditions.get('sourceSha256')},'noDateTestUsable':available}
   if cap.time_basis!='day' or cap.time_basis_quantity!=Decimal(1) or cap.time_unit!='DAY':row['issues'].append('不是明确的数量/1天基准，不隐式换算')
   if cap.uom_id!=step['workloadUnitId']:row['issues'].append('作业量与产能单位不一致，禁止隐式换算')
   if not available:row['issues'].append('产能用途、正式来源或有效性未获权威服务证明')
   if cap.measurement_status=='zero_capacity' or cap.quantity==0:row['issues'].append('0产能按原配套语义保留，不除法，不代表0作业量')
   fixed=fixed_steps[step['stepId']]
   preparation=fixed.preparation_days if fixed.preparation_days is not None else cap.preparation_days
   transfer=fixed.transfer_days if fixed.transfer_days is not None else cap.transfer_days
   if preparation is None or transfer is None:row['issues'].append('准备或转运DAY时间未维护')
   row['preparationSource']='固定步骤' if fixed.preparation_days is not None else '标准产能记录'
   row['transferSource']='固定步骤' if fixed.transfer_days is not None else '标准产能记录'
   if not row['issues']:
    row['result']=duration_days(demand_quantity=step['workloadQuantity'],capacity_quantity=cap.quantity,demand_uom_id=step['workloadUnitId'],capacity_uom_id=cap.uom_id,preparation_days=preparation,transfer_days=transfer)
  row['resultDisplay']={k:format(Decimal(v),'.6f') for k,v in row['result'].items() if k in ('productionDays','preparationDays','transferDays','durationDays')} if row['result'] else None
  center=WorkCenter.objects.filter(pk=step['workCenterId'],company_id=user.company_id).first()
  row['calendar']=Calendars._calendar_fact(center,usage_purpose='TEST_BUSINESS') if center else {'ready':False,'statusLabel':'工作中心不存在'}
  row['statusLabel']='无日期产能核对完成；日历覆盖单独读取' if row['result'] else '无日期核对受阻；见具体缺项'
  rows.append(row)
 required=[x for x in rows if x['decision']=='REQUIRED']
 return {'contractVersion':CONTRACT,'factSource':'server','scope':workload['scope'],'sourceIdentity':workload['sourceIdentity'],'rows':rows,
  'summary':{'requiredCount':len(required),'calculatedCount':sum(x['result'] is not None for x in required),'calendarReadyCount':sum(x['calendar']['ready'] for x in required),'notApplicableCount':sum(x['decision']=='NOT_APPLICABLE' for x in rows),'simulatedCapacityCount':sum(bool(x['capacity'] and x['capacity']['testOnly']) for x in required),'workloadReady':workload['workloadReady']},
  'formalManufacturingEligible':False,'dateSchedulingPerformed':False,'databaseBusinessWriteCount':0,
  'statusLabel':'无日期资源天与准备、转运分别核对；测试工作制度不授予正式排程资格',
  'calendarCoverageLabel':'已核验周工作分钟与例外日配置；未指定排程起始日期，不输出实际开完工日期',
  'requestIdentity':workload['requestIdentity']}
