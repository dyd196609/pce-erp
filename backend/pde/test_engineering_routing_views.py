from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import DatabaseError
from . import test_engineering_routing_service as service
from .routing_read_context import routing_read_request


class TestEngineeringRoutingView(APIView):
    permission_classes = [IsAuthenticated]

    @routing_read_request
    def get(self, request):
        from .views import _facts, _read_failure
        try:
            if request.query_params.get('all') == '1':
                service.authorize(request.user,'production.master_data.view',request.user.company_id)
                facts = service.company_facts(request.user)
                payload = _facts('pde-routings', facts, request)
                groups = {}
                for row in facts:
                    identity = row.get('displayIdentity')
                    if identity:
                        group = groups.setdefault(identity['orderId'],{'orderId':identity['orderId'],
                            'orderNo':identity['orderNo'],'testBindingCount':0,'historicalPlanCount':0})
                        group['testBindingCount'] += 1
                        group['historicalPlanCount'] += int(bool(row.get('historicalPlan')))
                summary = {'testBindingCount':len(facts),'orderGroups':list(groups.values()),
                    'countMeaningLabel':'测试绑定按BOM版本记录计数；两页面显示同一批记录，不按页面相加。',
                    'restrictionLabel':'测试引用不等于正式制造承接。'}
                payload['testEngineeringRoutingSummary'] = summary
            else:
                facts = service.read(user=request.user, bom_version_id=int(request.query_params['bomVersionId']))
                payload = _facts('pde-routings', [facts] if facts['bound'] else [], request)
            payload['testEngineeringRouting'] = facts
            for key in ('apiFacts','pageFacts','diagnosticFacts','strictFacts','acceptanceFacts'):
                payload[key]['testEngineeringRouting'] = facts
                if 'testEngineeringRoutingSummary' in payload:
                    payload[key]['testEngineeringRoutingSummary'] = payload['testEngineeringRoutingSummary']
            return Response(payload)
        except (service.TestRoutingError, ObjectDoesNotExist, ValidationError, KeyError, ValueError) as e:
            return _read_failure(request,status_code=409,error_code=getattr(e,'code','TEST_ROUTING_READ_DENIED'),error_message=str(e))
        except DatabaseError:
            return _read_failure(request,status_code=503,error_code='TEST_ROUTING_READ_FAILED',error_message='固定路线读取失败，不是没有绑定或没有材料。')
        except Exception as e:
            from .engineering_calculation_service import EngineeringCalculationError
            if isinstance(e, EngineeringCalculationError):
                return _read_failure(request,status_code=403,error_code=e.code,error_message=e.message)
            raise

    def post(self, request):
        try:
            data = request.data
            allowed = {'action','bomVersionId','routingVersionId','decisions','previewHash','reason','idempotencyKey'}
            if set(data)-allowed or data.get('action') not in ('preview','bind'):
                return Response({'message':'不接受调用者指定用途、来源或未登记动作。'},status=400)
            kwargs = dict(user=request.user,bom_version_id=data['bomVersionId'],routing_version_id=data['routingVersionId'],decisions=data['decisions'])
            if data['action']=='preview':
                return Response(service.preview(**kwargs))
            result = service.bind(**kwargs,preview_hash=data['previewHash'],reason=data['reason'],key=data['idempotencyKey'])
            return Response(result,status=200 if result['idempotent'] else 201)
        except (service.TestRoutingError, ObjectDoesNotExist, ValidationError, KeyError, ValueError) as e:
            return Response({'code':getattr(e,'code','TEST_ROUTING_DENIED'),'message':str(e)},status=409)
        except Exception as e:
            from .engineering_calculation_service import EngineeringCalculationError
            if isinstance(e, EngineeringCalculationError):
                return Response({'code':e.code,'message':e.message},status=403)
            raise
