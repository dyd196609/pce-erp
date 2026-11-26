from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import DatabaseError

from .order_engineering_intake_service import (
    OrderEngineeringIntakeError,
    OrderEngineeringIntakeService,
)


class OrderEngineeringIntakeView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _item_id(value):
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise OrderEngineeringIntakeError(
                "SALES_ORDER_ITEM_ID_REQUIRED",
                "必须提供有效的销售订单行标识。",
                http_status=400,
            ) from exc

    @staticmethod
    def _error(exc):
        return Response(
            {"code": exc.code, "message": exc.message, "details": exc.details},
            status=exc.http_status,
        )

    def get(self, request):
        try:
            if request.query_params.get('includeSourceRowBindings') == '1':
                from .order_source_row_binding import read_for_item
                return Response(read_for_item(user=request.user,sales_order_item_id=self._item_id(request.query_params.get('salesOrderItemId'))))
            facts = OrderEngineeringIntakeService.facts(
                user=request.user,
                sales_order_item_id=self._item_id(
                    request.query_params.get("salesOrderItemId")
                ),
            )
            return Response(facts, status=status.HTTP_200_OK)
        except OrderEngineeringIntakeError as exc:
            return self._error(exc)
        except DatabaseError:
            if request.query_params.get('includeSourceRowBindings') != '1':raise
            from workflow_runtime.fact_loads import build_fact_load_facts
            failed=build_fact_load_facts(fact_load_status='read_failed',api_url=request.path,http_status=503,
                error_code='SOURCE_ROW_BINDING_READ_FAILED',error_message='来源逐行关联读取失败，结果未知。',
                tenant_id=str(request.user.company_id),batch_id='SalesOrderItem:'+str(request.query_params.get('salesOrderItemId')))
            return Response({**failed,'passed':False,'rows':None,'factLoadFacts':failed},status=503)
        except ValueError as exc:
            from .product_design_service import ProductDesignError
            from .pde_engineering_preparation_admission import PDEEngineeringPreparationAdmissionError
            if isinstance(exc,(ProductDesignError,PDEEngineeringPreparationAdmissionError)):
                return self._error(exc)
            raise

    def post(self, request):
        try:
            if request.data.get("action") == "registerSourceRows":
                from .order_source_row_binding import register
                result=register(user=request.user,context=request.data.get("instanceContext") or {},
                    bindings=request.data.get("bindings"),idempotency_key=request.headers.get("Idempotency-Key", ""),
                    reason=request.data.get("reason", ""))
                return Response(result,status=status.HTTP_200_OK if result['idempotent'] else status.HTTP_201_CREATED)
            result = OrderEngineeringIntakeService.confirm_identity_and_create(
                user=request.user,
                sales_order_item_id=self._item_id(
                    request.data.get("salesOrderItemId")
                ),
                customer_product_name=request.data.get("customerProductName"),
                product_category_id=request.data.get("productCategoryId"),
                selected_process_type_id=request.data.get("selectedProcessTypeId"),
                source_record_id=request.data.get("sourceRecordId"),
                authorization_id=request.data.get("authorizationId"),
                idempotency_key=request.headers.get("Idempotency-Key", ""),
                reason=request.data.get("reason", ""),
                expected_order_version=request.data.get("expectedOrderVersion"),
                expected_source_content_hash=request.data.get("expectedSourceContentHash"),
            )
            return Response(
                result,
                status=(
                    status.HTTP_200_OK
                    if result["idempotent"]
                    else status.HTTP_201_CREATED
                ),
            )
        except OrderEngineeringIntakeError as exc:
            return self._error(exc)
        except ValueError as exc:
            from .product_design_service import ProductDesignError
            from .production_foundation_service import ProductionFoundationError
            from .pde_engineering_preparation_admission import PDEEngineeringPreparationAdmissionError
            if isinstance(exc,(ProductDesignError,ProductionFoundationError,PDEEngineeringPreparationAdmissionError)):
                return self._error(exc)
            raise

