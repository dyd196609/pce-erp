from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .definition_service import (
    WORKFLOW_DEFINITION_CONTRACT,
    WorkflowDefinitionCatalogService,
    WorkflowDefinitionError,
    WorkflowDefinitionOperatingService,
)
from .execution_resolution import WorkflowExecutionResolutionService


def _success(data, *, written=False, status_code=200):
    return Response({
        "success": True,
        "data": data,
        "error": None,
        "meta": {
            "contractVersion": WORKFLOW_DEFINITION_CONTRACT,
            "currentStateSource": "server",
            "productionUserDataWritten": written,
        },
    }, status=status_code)


def _failure(error):
    return Response({
        "success": False,
        "data": None,
        "error": {"code": error.code, "message": error.message},
        "meta": {
            "contractVersion": WORKFLOW_DEFINITION_CONTRACT,
            "currentStateSource": "server",
            "productionUserDataWritten": False,
            "authorization": error.decision,
        },
    }, status=error.http_status)


class ProcessDefinitionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            return _success(WorkflowDefinitionCatalogService.list(user=request.user))
        except WorkflowDefinitionError as error:
            return _failure(error)

    def post(self, request):
        try:
            result = WorkflowDefinitionOperatingService.execute(
                user=request.user,
                action=request.data.get("action"),
                payload=request.data.get("payload") or {},
            )
            return _success(result, written=True)
        except WorkflowDefinitionError as error:
            return _failure(error)


class ProcessDefinitionAtomicMinimalTemplateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            result = WorkflowDefinitionOperatingService.configure_atomic_minimal_template(
                user=request.user,
                payload=request.data or {},
                idempotency_key=request.headers.get("Idempotency-Key", ""),
            )
            replay = bool(result.get("idempotentReplay"))
            return _success(
                result,
                written=not replay,
                status_code=200 if replay else 201,
            )
        except WorkflowDefinitionError as error:
            return _failure(error)


class ProcessDefinitionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, definition_id):
        try:
            return _success(WorkflowDefinitionCatalogService.detail(
                user=request.user, definition_id=definition_id,
            ))
        except WorkflowDefinitionError as error:
            return _failure(error)


class ProcessDefinitionNodesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, definition_id):
        try:
            result = WorkflowDefinitionCatalogService.detail(
                user=request.user, definition_id=definition_id,
            )
            definition = result["definition"]
            return _success({
                "definitionId": definition["id"],
                "definitionCode": definition["definitionCode"],
                "nodes": definition["nodes"],
                "total": len(definition["nodes"]),
                "authorization": result["authorization"],
            })
        except WorkflowDefinitionError as error:
            return _failure(error)


class ProcessDefinitionExecutionResolutionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, definition_id):
        try:
            return _success(WorkflowExecutionResolutionService.resolve(
                user=request.user, definition_id=definition_id,
            ))
        except WorkflowDefinitionError as error:
            return _failure(error)
