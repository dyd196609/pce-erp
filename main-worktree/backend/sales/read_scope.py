from system.authorization import AuthorizationService
from system.models import RolePermission

VIEW_ACTION = "sales.order.view"


def view_evidence(user):
    roles = set(RolePermission.objects.filter(
        permission__code=VIEW_ACTION,
    ).values_list("role__code", flat=True))
    return [
        item for item in AuthorizationService.authority_evidence(user, user.company_id)
        if item.role_code in roles
    ]


def restrict_orders(queryset, user):
    evidence = view_evidence(user)
    scoped = queryset.filter(company_id=user.company_id)
    if any(item.scope_code in {"ALL", "ORGANIZATION"} for item in evidence):
        return scoped
    from django.db.models import Q

    allowed = Q(pk__in=[])
    for item in evidence:
        if item.scope_code == "DEPARTMENT" and item.department_id:
            allowed |= Q(department_id=item.department_id)
        elif item.scope_code == "SELF":
            allowed |= Q(created_by=user)
    return scoped.filter(allowed)
