"""Existing PDE authority for previewing and committing scoped version handoffs."""
from django.core.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from workflow_runtime.fact_loads import failed_fact_load_facts, successful_fact_load_facts


def _identifier(data, key, *, optional=False):
    value = data.get(key)
    if optional and value is None:
        return None
    if isinstance(value, bool) or not str(value or '').isdigit() or int(value) <= 0:
        raise ValueError(f'{key}必须是有效的正式记录编号。')
    return int(value)


class PlanStepVersionHandoffView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .plan_step_version_handoff_service import PlanStepVersionHandoffService
        from .plan_step_context_service import PlanStepContextError
        data = request.data
        try:
            action = data.get('action', 'preview')
            if action in {'preview', 'activate'}:
                selected_main = (_identifier(data, 'mainCalculationId')
                    if 'mainCalculationId' in data else None)
                scope = {
                    'user': request.user,
                    'production_plan_id': _identifier(data, 'productionPlanId'),
                    'root_step_id': _identifier(data, 'rootRoutingStepId'),
                    'manufacturing_output_id': _identifier(data, 'manufacturingOutputId', optional=selected_main is not None),
                    'target_step_id': _identifier(data, 'targetRoutingStepId'),
                    'impact_basis': data.get('impactBasis'),
                }
                if selected_main is not None:
                    scope['main_calculation_id'] = selected_main
                if action == 'preview':
                    result = PlanStepVersionHandoffService.preview(**scope)
                else:
                    result = PlanStepVersionHandoffService.activate(
                        **scope, expected_context_hash=data.get('expectedContextHash'),
                        expected_impact_hash=data.get('impactHash'),
                        predecessor_id=_identifier(data, 'predecessorBindingId', optional=True),
                        idempotency_key=data.get('idempotencyKey'), reason=data.get('reason', ''),
                    )
            else:
                raise ValueError('请选择已注册的查看或承接动作。')
            return Response({**result, 'factSource': 'server', **successful_fact_load_facts(
                result_count=1, api_url=request.path, tenant_id=request.user.company_id,
                batch_id=f'PDE-PLAN-STEP-HANDOFF-{data.get("productionPlanId", data.get("bindingId", "read"))}',
                request=request,
            )})
        except PlanStepContextError as exc:
            return self._error(request, exc.code, exc.message, exc.details, getattr(exc, 'http_status', 409))
        except (ValueError, KeyError, TypeError, ValidationError) as exc:
            return self._error(request, 'PLAN_STEP_HANDOFF_INPUT_INVALID', str(exc), {}, 400)
        except Exception as exc:
            # Only typed business failures are translated. Unexpected faults must
            # reach the normal server error handler, never become an empty fact.
            if not hasattr(exc, 'code') or not hasattr(exc, 'message'):
                raise
            return self._error(request, exc.code, exc.message, getattr(exc, 'details', {}),
                               getattr(exc, 'http_status', 409))

    @staticmethod
    def _error(request, code, message, details, http_status):
        return Response({'code': code, 'message': message, 'details': details,
            **failed_fact_load_facts(api_url=request.path, http_status=http_status,
                error_code=code, error_message=message, tenant_id=request.user.company_id,
                batch_id='PDE-PLAN-STEP-HANDOFF', request=request)}, status=http_status)
