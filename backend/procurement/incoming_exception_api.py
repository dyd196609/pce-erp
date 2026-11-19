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


class IncomingCustodyDirectoryView(APIView):
 permission_classes=[IsAuthenticated]
 def get(self,request):
  def read():
   if set(request.query_params)-{'q','page','pageSize','category'} or any(len(request.query_params.getlist(k))!=1 for k in request.query_params):service.fail('INCOMING_EXCEPTION_DIRECTORY_INPUT_INVALID','只接受查询、分类及分页，不接受自报身份或范围。',400)
   try:page=int(request.query_params.get('page','1'));size=int(request.query_params.get('pageSize','20'))
   except ValueError:service.fail('INCOMING_EXCEPTION_DIRECTORY_INPUT_INVALID','页码和每页条数须为整数。',400)
   return service.custody_directory(user=request.user,query=request.query_params.get('q',''),page=page,page_size=size,category=request.query_params.get('category','all'))
  return invoke(read)
