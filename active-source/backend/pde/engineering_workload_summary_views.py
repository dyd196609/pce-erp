"""Add a read-only workload presentation to the existing calculation detail."""
from .views import EngineeringCalculationTraceView
from .engineering_workload_summary import (
    build_engineering_workload_summary,
    engineering_workload_summary_read_failure,
    stamp_engineering_workload_summary,
)


class EngineeringWorkloadCalculationTraceView(EngineeringCalculationTraceView):
    def get(self, request, object_id=None):
        response = super().get(request, object_id=object_id)
        if response.status_code != 200 or not object_id or not isinstance(response.data, dict):
            return response
        calculation = response.data.get("calculation")
        if not isinstance(calculation, dict):
            return response
        try:
            summary = build_engineering_workload_summary(
                user=request.user, source_calculation_ids=[object_id],
            )
        except Exception as exc:
            # Preserve the original calculation response; this new projection
            # alone reports unknown/read_failed rather than replacing facts.
            summary = engineering_workload_summary_read_failure(exc)
        summary = stamp_engineering_workload_summary(
            summary, tenant_id=request.user.company_id,
            api_url=request.path, http_status=response.status_code,
        )
        response.data = {**response.data, "calculation": {**calculation, "engineeringWorkloadSummary": summary}}
        return response
