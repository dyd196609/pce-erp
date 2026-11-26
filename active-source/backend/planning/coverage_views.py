"""Thin HTTP adapters; all permission/quantity decisions stay in original domain services."""
from django.db import DatabaseError, IntegrityError, OperationalError
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from workflow_runtime.fact_loads import build_fact_load_facts
from sales.services import SalesBusinessError
from pde.product_design_service import ProductDesignError
from sales.manufacturing_input import ManufacturingInputError
from .services import PlanningBusinessError
from .order_batch_service import create_batch, cancel_batch, action_result


class CoverageAPIView(APIView):
    """Preserve original HTTP decisions and expose the native fact-load contract."""
    def finalize_response(self, request, response, *args, **kwargs):
        if request.method == 'GET' and isinstance(response.data, dict):
            failed = response.status_code >= 400
            payload = dict(response.data)
            data = dict(payload.get('data') or {})
            error = payload.get('error') or {}
            code = error.get('code') or ('NOT_AUTHENTICATED' if response.status_code == 401 else 'COVERAGE_READ_DENIED')
            message = error.get('message') or str(payload.get('detail') or '本次事实读取未完成，结果未知。')
            company = getattr(request.user, 'company_id', None)
            facts = build_fact_load_facts(
                fact_load_status=('read_failed' if failed else
                    'empty_valid' if data.get('allocations') == [] else 'loaded'),
                api_url=request.path, http_status=response.status_code,
                error_code=code if failed else '', error_message=message if failed else '',
                tenant_id=str(company) if company is not None else None,
                batch_id='OrderSupplyCoverage', request=request)
            if failed:
                facts['passed'] = False
                payload.update(success=False, error={'code': code, 'message': message})
            data['factLoadFacts'] = facts
            payload['data'] = data
            response.data = payload
        return super().finalize_response(request, response, *args, **kwargs)


def invoke(request, callback):
    def unavailable():
        facts=build_fact_load_facts(fact_load_status='read_failed',api_url=request.path,http_status=503,
            error_code='COVERAGE_FACT_READ_FAILED',error_message='来源读取失败，结果未知。',
            tenant_id=str(request.user.company_id),batch_id='OrderSupplyCoverage')
        facts['passed']=False
        return Response({'success':False,'data':{'factLoadFacts':facts},'error':{'code':'COVERAGE_FACT_READ_FAILED',
            'message':'来源读取失败，结果未知。'}},status=503)
    try:
        return Response({'success':True,'data':callback(),'error':None})
    except (SalesBusinessError, ProductDesignError, PlanningBusinessError, ManufacturingInputError) as exc:
        return Response({'success':False,'data':None,'error':{'code':exc.code,'message':exc.message}},status=getattr(exc,'http_status',409))
    except OperationalError as exc:
        if not any(token in str(exc).lower() for token in ('locked','deadlock','serialization')):
            return unavailable()
        return Response({'success':False,'data':None,'error':{'code':'COVERAGE_CONCURRENT_OR_UNKNOWN',
            'message':'并发状态已变化或本次结果待核实，请先查询同次动作，勿自动重放。'}},status=409)
    except IntegrityError:
        # No blind write replay. The caller must query the original key first.
        return Response({'success':False,'data':None,'error':{'code':'COVERAGE_CONCURRENT_OR_UNKNOWN',
            'message':'并发状态已变化或本次结果待核实，请先查询同次动作，勿自动重放。'}},status=409)
    except DatabaseError:
        return unavailable()


class OrderManufacturingBatchView(CoverageAPIView):
    permission_classes=[IsAuthenticated]

    def post(self,request,item_id):
        return invoke(request,lambda:create_batch(user=request.user,item_id=item_id,payload=request.data,
            key=request.headers.get('Idempotency-Key')))

    def get(self,request,item_id):
        return invoke(request,lambda:action_result(user=request.user,item_id=item_id,entity_type='DemandBatch',
            key=request.query_params.get('idempotencyKey')))


class OrderManufacturingBatchCancelView(CoverageAPIView):
    permission_classes=[IsAuthenticated]

    def post(self,request,item_id,demand_id):
        return invoke(request,lambda:cancel_batch(user=request.user,item_id=item_id,demand_id=demand_id,payload=request.data,
            key=request.headers.get('Idempotency-Key')))

    def get(self,request,item_id,demand_id):
        return invoke(request,lambda:action_result(user=request.user,item_id=item_id,entity_type='DemandBatchCancel',
            key=request.query_params.get('idempotencyKey'),demand_id=demand_id))
