from django.db import DatabaseError
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import EngineeringCalculationRecord,BOMVersion
from .engineering_calculation_service import OrderEngineeringClosureService,EngineeringCalculationError
from .test_business_bom_service import authorize
from system.authorization import AuthorizationService

class TestBusinessBomHandoffView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request):
        try:
            authorize(request.user,'production.engineering.calculation.view',request.user.company_id)
            records=EngineeringCalculationRecord.all_records.filter(company_id=request.user.company_id,scope='test_business').order_by('-pk')[:100]
            rows=[]
            for record in records:
                try:
                    preview=OrderEngineeringClosureService.preview_bom(user=request.user,calculation_id=record.pk)
                    valid=True;error=None
                except EngineeringCalculationError as e:
                    preview=None;valid=False;error=e.message
                permission=AuthorizationService.decide(user=request.user,action_code='production.master_data.bom.maintain',organization_id=record.company_id,business_object={'organizationId':record.company_id})
                components=[{'key':x['original']['key'],'name':x['name']} for x in record.trace.get('resultSnapshot',{}).get('inputs',[])]
                versions=BOMVersion.objects.filter(bom__source_calculation=record).select_related('bom').order_by('pk')
                rows.append({'id':record.pk,'calculationNo':record.calculation_no,'salesOrderId':record.sales_order_item.sales_order_id,'orderNo':record.sales_order_item.sales_order.order_no,'baselineNo':record.baseline.baseline_no,'revision':record.design_revision.revision,'sourceVersion':record.source_record.source_version,'sourceId':record.source_record_id,'purposeLabel':'测试业务','restrictionLabel':'仅允许测试草稿；禁止正式评审、发布及制造','sourceValid':valid,'error':error,'components':components,'preview':preview,'canMaintain':permission['allowed'],'maintenanceDisabledReason':permission['reason'],'actionState':('ready' if preview and preview.get('canGenerate') else 'draft' if preview and preview.get('alreadyGenerated') else 'blocked'),'actionPermissions':(['pce.action.bom-management.generate-test-business-bom','pce.action.bom-management.derive-test-business-bom'] if permission['allowed'] else []),'versions':[{'id':v.pk,'name':v.bom_version,'purposeLabel':v.get_usage_purpose_display(),'statusLabel':v.get_status_display(),'actionState':(v.status if valid else 'blocked'),'originVersionId':v.origin_version_id} for v in versions]})
            from .views import _facts
            facts=_facts('pde-product-boms',rows,request)
            facts.update({'records':rows,'factSource':'server','businessWriteSideEffectCount':0})
            for surface in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):
                facts[surface]['testBusinessHandoff']=rows
                facts[surface]['businessWriteSideEffectCount']=0
            return Response(facts)
        except EngineeringCalculationError as e:
            from .views import _read_failure
            return _read_failure(request,status_code=403,error_code=e.code,error_message=e.message)
        except DatabaseError:
            from .views import _read_failure
            return _read_failure(request,status_code=503,error_code='TEST_BOM_HANDOFF_READ_FAILED',error_message='测试BOM承接事实读取失败，不是没有数据。')
    def post(self,request):
        from .test_bom_derivation import derive_test_version
        if set(request.data)-{'versionId','reason','key'}:return Response({'message':'不接受调用者指定用途或来源字段。'},status=400)
        try:return Response(derive_test_version(user=request.user,version_id=request.data['versionId'],key=request.data.get('key',''),reason=request.data.get('reason','')))
        except Exception as e:return Response({'code':getattr(e,'code','TEST_DERIVE_DENIED'),'message':getattr(e,'message',str(e))},status=400)

