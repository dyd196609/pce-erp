from django.db import DatabaseError,OperationalError,IntegrityError
from django.core.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from . import material_allocation_service as service

def invoke(fn):
 try:return Response({'success':True,'data':fn(),'error':None,'meta':{'currentStateSource':'server'}})
 except DatabaseError as e:
  status=409 if isinstance(e,IntegrityError) or 'locked' in str(e).lower() or 'busy' in str(e).lower() else 500
  return Response({'success':False,'data':None,'error':{'code':'MATERIAL_CONCURRENCY_CONFLICT' if status==409 else 'MATERIAL_READ_FAILED','message':'并发或版本已变化，请查询同次动作，不自动重放。' if status==409 else '原料事实读取失败，不能显示0或空成功。'}},status=status)
 except Exception as e:
  if hasattr(e,'code') and hasattr(e,'http_status'):
   return Response({'success':False,'data':None,'error':{'code':e.code,'message':str(e)}},status=e.http_status)
  if isinstance(e,ValidationError):return Response({'success':False,'data':None,'error':{'code':'MATERIAL_VALIDATION_FAILED','message':'原业务字段验证未通过，事实未提交。'}},status=409)
  raise
class MaterialAllocationView(APIView):
 permission_classes=[IsAuthenticated]
 def get(self,request):
  def read():
   allowed={'demandId','sourceTransactionId','resultKey'}
   if set(request.query_params)-allowed:service.fail('MATERIAL_ALLOCATION_INPUT_INVALID','只接收准确需求、来源或同次动作键。',400)
   try:demand=int(request.query_params.get('demandId',''));source=int(request.query_params['sourceTransactionId']) if 'sourceTransactionId' in request.query_params else None
   except ValueError:service.fail('MATERIAL_ALLOCATION_INPUT_INVALID','需求与库存来源必须为准确ID。',400)
   if 'resultKey' in request.query_params:return service.result_query(user=request.user,demand_id=demand,key=request.query_params['resultKey'])
   return service.context(user=request.user,demand_id=demand,source_id=source)
  return invoke(read)
 def post(self,request):
  def execute():
   data=dict(request.data);key=data.pop('idempotencyKey',None)
   return service.confirm(user=request.user,payload=data,key=key)
  return invoke(execute)

def raw_source_response(request,action,object_id):
 from .material_stock_authority import source_context,source_action_result,ACTIONS
 from .scm_runtime_services import PurchaseReceiptService,PurchaseInspectionService,WarehouseInboundService
 if action not in ACTIONS:return Response({'success':False,'data':None,'error':{'code':'RAW_ACTION_UNKNOWN','message':'没有本次原料来源动作。'}},status=404)
 if request.method=='GET':
  def read():
   if set(request.query_params)-{'usagePurpose','idempotencyKey','purchaseOrderItemId'}:service.fail('RAW_SOURCE_INPUT_INVALID','只接受明确用途及同次动作键，不接受自报身份或范围。',400)
   selected=None
   if 'purchaseOrderItemId' in request.query_params:
    try:selected=int(request.query_params['purchaseOrderItemId'])
    except (ValueError,TypeError):service.fail('RAW_PURCHASE_LINE_INVALID','请从本单候选选择准确采购行。',400)
    if selected<=0:service.fail('RAW_PURCHASE_LINE_INVALID','请从本单候选选择准确采购行。',400)
   if 'idempotencyKey' in request.query_params:return source_action_result(user=request.user,action=action,object_id=object_id,key=request.query_params['idempotencyKey'],purchase_order_item_id=selected)
   return source_context(user=request.user,action=action,object_id=object_id,purchase_order_item_id=selected)
  return invoke(read)
 def execute():
  p=dict(request.data)
  if action=='confirm-receipt':return PurchaseReceiptService.confirm(object_id,p.get('quantity'),request.user,material_payload=p)
  if action=='create-inspection':return PurchaseInspectionService.create_from_receipt(object_id,request.user,material_payload=p)
  if action=='transition-inspection':return PurchaseInspectionService.transition(object_id,None,user=request.user,material_payload=p)
  if action=='confirm-inbound':return WarehouseInboundService.confirm(object_id,p.get('quantity'),p.get('warehouseCode'),request.user,material_payload=p)
  service.fail('RAW_ACTION_UNKNOWN','没有本次原料来源动作。',404)
 return invoke(execute)
