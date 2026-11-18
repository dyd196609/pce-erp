from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .material_allocation_api import invoke as original_invoke
from . import material_issue_service as service
from .material_issue_configuration import ISSUE,RECEIVE

def invoke(fn):
 try:return original_invoke(fn)
 except Exception:
  import logging
  logging.getLogger(__name__).exception('Native material delivery read/write failed; no empty-success fallback')
  return Response({'success':False,'data':None,'error':{'code':'MATERIAL_READ_FAILED','message':'原料交付事实读取或提交失败，请查询同次结果，不能按0或空成功继续。'},'meta':{'currentStateSource':'server'}},status=500)

class MaterialIssueView(APIView):
 permission_classes=[IsAuthenticated]
 def get(self,request):
  def read():
   if set(request.query_params)-{'allocationId','resultKey'}:service.fail('MATERIAL_ISSUE_INPUT_INVALID','只接收准确备料分配或同次动作键。',400)
   if 'resultKey' in request.query_params:return service.result_query(user=request.user,action=ISSUE,key=request.query_params['resultKey'])
   try:ident=int(request.query_params.get('allocationId',''))
   except ValueError:service.fail('MATERIAL_ISSUE_INPUT_INVALID','须准确备料分配。',400)
   return service.context(user=request.user,allocation_id=ident)
  return invoke(read)
 def post(self,request):
  def execute():
   payload=dict(request.data);key=payload.pop('idempotencyKey',None)
   return service.issue(user=request.user,payload=payload,key=key)
  return invoke(execute)

class MaterialReceiptView(APIView):
 permission_classes=[IsAuthenticated]
 def get(self,request):
  def read():
   if set(request.query_params)-{'issueId','resultKey'}:service.fail('MATERIAL_RECEIPT_INPUT_INVALID','只接收本人指定发料或同次动作键。',400)
   if 'resultKey' in request.query_params:return service.result_query(user=request.user,action=RECEIVE,key=request.query_params['resultKey'])
   if 'issueId' not in request.query_params:return service.own_receipts(user=request.user)
   try:ident=int(request.query_params['issueId'])
   except ValueError:service.fail('MATERIAL_RECEIPT_INPUT_INVALID','须准确发料事实。',400)
   return service.receipt_context(user=request.user,issue_id=ident)
  return invoke(read)
 def post(self,request):
  def execute():
   payload=dict(request.data);key=payload.pop('idempotencyKey',None)
   return service.receive(user=request.user,payload=payload,key=key)
  return invoke(execute)
