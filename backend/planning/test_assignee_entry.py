"""Least-privilege navigation projection for a qualified assigned operator.

No engineering catalogue, selection, write permission or company-wide totals.
The waiting state below evaluates capability only, not permission to start now;
actual source/predecessor/state admission remains in the start service.
"""
from system.models import Company
from pde.order_routing_execution_service import fail
from .test_scheduling_service import _actor
from . import test_operation_start_service as starts
from . import test_operation_start_protocol as protocol


def owned_tasks(user, arrangement_id=None):
 actor=_actor(user)
 if not Company.objects.filter(pk=actor.company_id,is_active=True).exists():
  fail('SCOPE_DENIED','公司已失效。')
 qs=starts.tasks.Task.objects.filter(company_id=actor.company_id,
  execution_employee__user_id=actor.pk,work_order__usage_purpose='TEST_BUSINESS')
 if arrangement_id is not None:
  qs=qs.filter(work_order__source_schedule__execution_arrangement_id=arrangement_id)
 result=[]
 for task in qs.select_related('source_operation__work_center','workshop','work_center','work_order__source_schedule__execution_arrangement__source_calculation__sales_order_item__sales_order'):
  if not protocol._effective(task.work_center,protocol._today()) or task.work_center.company_id!=actor.company_id or task.work_center.workshop_id!=task.workshop_id:continue
  qualification=protocol._qualification(actor,task,{'ready':True},{'ready':True},state='waiting')
  if qualification['ready']:
   starts.tasks.verify(task)
   result.append(task)
 return actor,result


def entry(user, arrangement_id=None):
 actor,tasks=owned_tasks(user,arrangement_id)
 if not tasks:fail('MES_ASSIGNEE_SCOPE_NOT_APPLICABLE','当前账号没有有效职责、动作及资源范围内的本人执行任务，此入口不适用。请从业务流程中心→MES→按职责进入与历史验收查看本人授权入口；仓管仅查看指定成品交接及测试入库，不需要工程主数据扩权。')
 arrangements={}
 for task in tasks:
  obj=task.work_order.source_schedule.execution_arrangement
  arrangements[obj.pk]={'id':obj.pk,'orderNo':obj.source_calculation.sales_order_item.sales_order.order_no,
   'arrangementRevision':obj.arrangement_revision,'editVersion':obj.edit_version,
   'statusLabel':obj.get_status_display(),'isCurrent':True,
   'readScope':'qualified_assignee_only','requestIdentity':{'userId':actor.pk,'username':actor.username,'companyId':actor.company_id}}
 return {'readScope':'qualified_assignee_only','orderExecutionArrangements':list(arrangements.values()),
  'requestIdentity':{'userId':actor.pk,'username':actor.username,'companyId':actor.company_id},
  'visibleArrangementCount':len(arrangements),'visibleTaskCount':len(tasks)}
