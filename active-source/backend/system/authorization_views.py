from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count

from .authorization import AUTHORIZATION_CONTRACT_VERSION, AuthorizationService
from .enterprise_organization import EnterpriseOrganizationModelService
from .organization_operating import OrganizationOperatingError, OrganizationOperatingService
from .models import Company, Department, Permission, Position
from .master_data_executor_preview import MasterDataExecutorPreviewService


ORGANIZATION_DIRECTORY_VIEW = "system.organization_directory.view"


def _envelope(data=None, *, error=None, http_status=status.HTTP_200_OK):
    return Response(
        {
            "success": error is None,
            "data": data,
            "error": error,
            "meta": {
                "module": "SYSTEM",
                "source": "server",
                "contractVersion": AUTHORIZATION_CONTRACT_VERSION,
            },
        },
        status=http_status,
    )


class AuthorizationDecisionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        payload = request.data or {}
        decision = AuthorizationService.decide(
            user=request.user,
            action_code=payload.get("actionCode"),
            organization_id=payload.get("organizationId"),
            business_object=payload.get("businessObject") or {},
            context=payload.get("context") or {},
        )
        return _envelope(decision)


class BusinessActionCatalogView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        actions = list(
            Permission.objects.order_by("module", "code").values(
                "code", "name", "module"
            )
        )
        return _envelope(
            {
                "registryOwner": "system.Permission",
                "actions": actions,
                "count": len(actions),
            }
        )


class OrganizationDirectoryView(APIView):
    """Low-risk V1 pilot: read-only organization directory projection."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        organization_id = str(request.user.company_id)
        decision = AuthorizationService.decide(
            user=request.user,
            action_code=ORGANIZATION_DIRECTORY_VIEW,
            organization_id=organization_id,
        )
        if not decision["allowed"]:
            return _envelope(
                data={"authorization": decision, "rows": []},
                error={
                    "code": decision["decisionCode"],
                    "message": decision["reason"],
                },
                http_status=status.HTTP_403_FORBIDDEN,
            )

        companies = Company.objects.filter(pk=organization_id, is_active=True)
        departments = Department.objects.select_related("company", "parent").filter(
            company_id=organization_id,
            is_active=True,
        )
        scope_codes = set(decision["scope"]["codes"])
        if not ({"ALL", "ORGANIZATION"} & scope_codes):
            allowed_department_ids = set(decision["scope"]["departmentIds"])
            if "SELF" in scope_codes:
                try:
                    if request.user.employee_profile.department_ref_id:
                        allowed_department_ids.add(
                            request.user.employee_profile.department_ref_id
                        )
                except Exception:
                    pass
            departments = departments.filter(pk__in=allowed_department_ids)
        departments = list(departments.order_by("code", "pk"))
        department_ids = [row.pk for row in departments]
        position_counts = {
            row["department_id"]: row["count"]
            for row in Position.objects.filter(
                department_id__in=department_ids,
                is_active=True,
            )
            .values("department_id")
            .annotate(count=Count("id"))
        }
        rows = [
            {
                "id": row.pk,
                "code": row.code,
                "name": row.name,
                "companyId": row.company_id,
                "companyName": row.company.name,
                "parentId": row.parent_id,
                "parentName": row.parent.name if row.parent else "",
                "manager": row.manager,
                "positionCount": position_counts.get(row.pk, 0),
                "statusLabel": "启用",
            }
            for row in departments
        ]
        return _envelope(
            {
                "actionCode": ORGANIZATION_DIRECTORY_VIEW,
                "authorization": decision,
                "companies": list(companies.values("id", "code", "name")),
                "rows": rows,
                "strictFacts": {
                    "factSource": "server",
                    "factLoadStatus": "success",
                    "resultCount": len(rows),
                    "businessWriteCount": 0,
                },
            }
        )


class EnterpriseOrganizationModelView(APIView):
    """Scope-aware organization facts and explicitly authorized maintenance actions."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        organization_id = str(request.user.company_id)
        decision = AuthorizationService.decide(
            user=request.user,
            action_code=ORGANIZATION_DIRECTORY_VIEW,
            organization_id=organization_id,
        )
        if not decision["allowed"]:
            return _envelope(
                data={"authorization": decision},
                error={
                    "code": decision["decisionCode"],
                    "message": decision["reason"],
                },
                http_status=status.HTTP_403_FORBIDDEN,
            )
        return _envelope(
            EnterpriseOrganizationModelService.project(
                user=request.user,
                decision=decision,
            )
        )

    def post(self, request):
        body = request.data or {}
        try:
            result = OrganizationOperatingService.execute(
                user=request.user,
                action=body.get("action"),
                payload=body.get("payload") or {},
                request_identity=request.headers.get("Idempotency-Key"),
            )
        except OrganizationOperatingError as error:
            return _envelope(
                data={"authorization": error.decision} if error.decision else None,
                error={"code": error.code, "message": error.message},
                http_status=error.http_status,
            )
        return _envelope(result)


class MasterDataExecutorPreviewView(APIView):
    """Read-only real-employee shortlist and minimal responsibility preview."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        organization_id = str(request.user.company_id)
        decision = AuthorizationService.decide(
            user=request.user,
            action_code=ORGANIZATION_DIRECTORY_VIEW,
            organization_id=organization_id,
        )
        if not decision["allowed"]:
            return _envelope(
                data={"authorization": decision, "rows": []},
                error={
                    "code": decision["decisionCode"],
                    "message": decision["reason"],
                },
                http_status=status.HTTP_403_FORBIDDEN,
            )
        data = MasterDataExecutorPreviewService.project(user=request.user)
        data["authorization"] = decision
        return _envelope(data)
