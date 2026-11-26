from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from system.models import User

from .action_permissions import (
    ActionPermissionValidator,
    CONTRACT_VERSION,
    MODULE_ACTIONS,
    list_module_policies,
    serialize_permission_matrix,
)
from .authentication import CanaryActorAuthentication
from .acceptance_observability import (
    AcceptanceFactsNotRegistered,
    build_acceptance_facts,
)


def _object_ids(request):
    if request.method == "GET":
        raw = request.query_params.get("objectIds", "")
        return [item.strip() for item in raw.split(",") if item.strip()]
    values = request.data.get("objectIds", [])
    return values if isinstance(values, list) else []


class ActionPermissionMatrixView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        module_code = request.query_params.get("moduleCode", "").strip()
        object_ids = _object_ids(request)
        selection_count = int(
            request.query_params.get("selectionCount", len(object_ids)) or 0
        )
        legal_entity_id = request.query_params.get("legalEntityId", "").strip()
        policies = list_module_policies(module_code)
        if not policies:
            return Response(
                {
                    "result": "blocked",
                    "contractVersion": CONTRACT_VERSION,
                    "error": {
                        "code": "MODULE_NOT_REGISTERED",
                        "message": "业务模块未注册动作权限契约。",
                    },
                },
                status=404,
            )
        validator = ActionPermissionValidator()
        decisions = [
            validator.evaluate(
                user=request.user,
                module_code=module_code,
                action_code=policy.actionCode,
                object_ids=object_ids,
                selection_count=(
                    0 if policy.scope == "view" else selection_count
                ),
                requested_legal_entity_id=legal_entity_id,
            )
            for policy in policies
        ]
        return Response(
            {
                "result": "passed",
                "contractVersion": CONTRACT_VERSION,
                "moduleCode": module_code,
                "currentStateSource": "server",
                "frontendVisibilityIsAuthority": False,
                "serverValidationRequired": True,
                "data": {
                    "decisions": decisions,
                    "grantedPermissionCodes": sorted(
                        {
                            item["action"]["requiredPermission"]
                            for item in decisions
                            if item["granted"] and item["action"]
                        }
                    ),
                },
            }
        )


class ActionPermissionValidationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        module_code = str(request.data.get("moduleCode", "")).strip()
        action_code = str(request.data.get("actionCode", "")).strip()
        object_ids = _object_ids(request)
        decision = ActionPermissionValidator().evaluate(
            user=request.user,
            module_code=module_code,
            action_code=action_code,
            object_ids=object_ids,
            selection_count=int(
                request.data.get("selectionCount", len(object_ids)) or 0
            ),
            requested_legal_entity_id=str(
                request.data.get("legalEntityId", "")
            ).strip(),
        )
        return Response(
            {
                "result": "passed" if decision["granted"] else "blocked",
                "contractVersion": CONTRACT_VERSION,
                "currentStateSource": "server",
                "data": decision,
            },
            status=200 if decision["granted"] else 403,
        )


class ActionPermissionContractView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "result": "passed",
                "contractVersion": CONTRACT_VERSION,
                "currentStateSource": "server",
                "data": {
                    "moduleCount": len(MODULE_ACTIONS),
                    "actionCount": len(serialize_permission_matrix()),
                    "actions": serialize_permission_matrix(),
                },
            }
        )


class CanaryActorSessionView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        if not getattr(
            settings, "PCE_ACTION_PERMISSION_CANARY_AUTH_ENABLED", False
        ):
            return Response({"result": "not_found"}, status=404)
        actor = request.query_params.get("actor", "").strip()
        allowed_actors = {
            "v552-viewer",
            "v552-operator",
            "v552-batch-operator",
            "v552-outscope",
            "v59-bank-operator",
            "v831-payable-buyer",
            "v831-payable-supervisor",
            "v831-payment-applicant",
            "v831-payment-owner",
        }
        if actor not in allowed_actors:
            return Response(
                {
                    "result": "blocked",
                    "error": {
                        "code": "TEST_ACTOR_NOT_ALLOWED",
                        "message": "测试角色未列入服务端白名单。",
                    },
                },
                status=403,
            )
        if not User.objects.filter(username=actor, is_active=True).exists():
            return Response(
                {
                    "result": "blocked",
                    "error": {
                        "code": "TEST_ACTOR_NOT_FOUND",
                        "message": "服务端测试角色不存在。",
                    },
                },
                status=404,
            )
        response = Response(
            {
                "result": "passed",
                "contractVersion": CONTRACT_VERSION,
                "actor": actor,
                "serverResolved": True,
            }
        )
        response.set_cookie(
            CanaryActorAuthentication.cookie_name,
            actor,
            max_age=3600,
            httponly=True,
            secure=False,
            samesite="Lax",
        )
        return response


class AcceptanceObservabilityView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, page_code):
        try:
            acceptance_facts = build_acceptance_facts(
                page_code,
                request=request,
            )
        except AcceptanceFactsNotRegistered:
            return Response(
                {
                    "result": "not_found",
                    "error": {
                        "code": "ACCEPTANCE_PAGE_NOT_REGISTERED",
                        "message": "The requested page has no acceptance facts provider.",
                    },
                },
                status=404,
            )
        return Response(
            {
                "result": "passed",
                "currentStateSource": "server",
                "acceptanceFacts": acceptance_facts,
                "strictFacts": {"acceptanceFacts": acceptance_facts},
            }
        )
