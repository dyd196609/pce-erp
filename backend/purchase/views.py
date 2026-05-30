from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import AllowAny   # 新增这一行导入
from django.shortcuts import get_object_or_404
from .models import PurchaseOrder
from .serializers import PurchaseOrderSerializer

class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.all()
    serializer_class = PurchaseOrderSerializer
    filter_backends = [OrderingFilter]
    ordering_fields = ['orderNo', 'amount', 'createDate']
    permission_classes = [AllowAny]   # 添加这一行，允许任何访问

    @action(detail=False, methods=['post'], url_path='batch-delete')
    def batch_delete(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'success': False, 'error': 'ids required'}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = PurchaseOrder.objects.filter(orderNo__in=ids).delete()
        return Response({'success': True, 'deleted_count': deleted})