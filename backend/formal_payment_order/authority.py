from django.conf import settings

from reconciliation.services import ReconciliationError


def assert_generate_authorized(user, tenant_id):
    if not user or not user.is_authenticated:
        raise ReconciliationError("FPO_AUTH_UNAUTHENTICATED", "Authentication required", 401)
    if not getattr(settings, "PCE_FORMAL_PAYMENT_ORDER_FEATURE_ENABLED", False):
        raise ReconciliationError("FPO_FEATURE_DISABLED", "Formal payment order is disabled", 403)
    test_tenants = getattr(settings, "PCE_FORMAL_PAYMENT_ORDER_TEST_TENANTS", set())
    if tenant_id not in test_tenants:
        if not getattr(settings, "PCE_FORMAL_PAYMENT_ORDER_PRODUCTION_ROLLOUT_ENABLED", False):
            raise ReconciliationError("FPO_PRODUCTION_DISABLED", "Production rollout is disabled", 403)
        if not user.has_perm("formal_payment_order.generate_formal_payment_order"):
            raise ReconciliationError("FPO_PERMISSION_DENIED", "Permission denied", 403)

