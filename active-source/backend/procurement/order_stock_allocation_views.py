from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from planning.coverage_views import invoke, CoverageAPIView
from .order_stock_allocation import allocate, release, allocations_for_line
from planning.order_batch_service import action_result, fail, actor_line
from .models import OrderStockAllocation


class OrderStockAllocateView(CoverageAPIView):
    permission_classes=[IsAuthenticated]

    def post(self,request,item_id):
        return invoke(request,lambda:allocate(user=request.user,item_id=item_id,payload=request.data,
            key=request.headers.get('Idempotency-Key')))

    def get(self,request,item_id):
        if not request.query_params.get('idempotencyKey'):
            def history():
                _,item,_=actor_line(request.user,item_id,'warehouse.production.putaway')
                return {'salesOrderItemId':item.pk,'allocations':allocations_for_line(item,include_inactive=True),
                    'factSource':'server','businessWriteCount':0}
            return invoke(request,history)
        return invoke(request,lambda:action_result(user=request.user,item_id=item_id,entity_type='OrderStockAllocate',
            key=request.query_params.get('idempotencyKey')))


class OrderStockReleaseView(CoverageAPIView):
    permission_classes=[IsAuthenticated]

    def post(self,request,allocation_id):
        return invoke(request,lambda:release(user=request.user,allocation_id=allocation_id,payload=request.data,
            key=request.headers.get('Idempotency-Key')))

    def get(self,request,allocation_id):
        def result():
            row=OrderStockAllocation.objects.filter(pk=allocation_id,company_id=request.user.company_id).first()
            if not row:fail('STOCK_ALLOCATION_NOT_FOUND','库存分配不存在或不属于当前企业。',404)
            return action_result(user=request.user,item_id=row.sales_order_item_id,entity_type='OrderStockRelease',
                key=request.query_params.get('idempotencyKey'),allocation_id=row.pk)
        return invoke(request,result)
