from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .material_allocation_api import invoke
from . import material_preparation_service as service

class MaterialPreparationView(APIView):
 permission_classes=[IsAuthenticated]
 def get(self,request):
  def read():
   if set(request.query_params)-{'allocationId','resultKey'}:service.fail('MATERIAL_PREPARATION_INPUT_INVALID','只接收准确分配及同次动作键。',400)
   try:allocation=int(request.query_params.get('allocationId',''))
   except ValueError:service.fail('MATERIAL_PREPARATION_INPUT_INVALID','须准确分配ID。',400)
   if 'resultKey' in request.query_params:return service.result_query(user=request.user,allocation_id=allocation,key=request.query_params['resultKey'])
   return service.context(user=request.user,allocation_id=allocation)
  return invoke(read)
 def post(self,request):
  def execute():
   payload=dict(request.data);key=payload.pop('idempotencyKey',None)
   return service.confirm(user=request.user,payload=payload,key=key)
  return invoke(execute)
