from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .material_allocation_api import invoke
from . import incoming_exception_service as service
class IncomingExceptionView(APIView):
 permission_classes=[IsAuthenticated]
 def get(self,request,inspection_id,kind):
  def read():
   if set(request.query_params)-{'registrationId','resultKey','intentId'}:service.fail('INCOMING_EXCEPTION_INPUT_INVALID','只接受准确登记或同次结果键，不接受自报范围。',400)
   if 'resultKey' in request.query_params:return service.result_query(user=request.user,inspection_id=inspection_id,kind=kind,key=request.query_params['resultKey'],intent_id=request.query_params.get('intentId'))
   try:root=int(request.query_params['registrationId']) if 'registrationId' in request.query_params else None
   except ValueError:service.fail('INCOMING_EXCEPTION_INPUT_INVALID','须准确登记身份。',400)
   return service.context(user=request.user,inspection_id=inspection_id,kind=kind,registration_id=root)
  return invoke(read)
 def post(self,request,inspection_id,kind):
  return invoke(lambda:service.execute(user=request.user,inspection_id=inspection_id,kind=kind,payload=dict(request.data)))
