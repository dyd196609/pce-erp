from django.conf import settings

from reconciliation.services import ReconciliationError


def assert_execute_authorized(user, tenant_id):
    if not user or not user.is_authenticated:
        raise ReconciliationError("PRR_AUTH_UNAUTHENTICATED", "Authentication required", 401)
    if not getattr(settings, "PCE_PAYMENT_RISK_REVIEW_FEATURE_ENABLED", False):
        raise ReconciliationError("PRR_FEATURE_DISABLED", "Payment risk review is disabled", 403)
    test_tenants = getattr(settings, "PCE_PAYMENT_RISK_REVIEW_TEST_TENANTS", set())
    if tenant_id not in test_tenants:
        if not getattr(settings, "PCE_PAYMENT_RISK_REVIEW_PRODUCTION_ROLLOUT_ENABLED", False):
            raise ReconciliationError("PRR_PRODUCTION_DISABLED", "Production rollout is disabled", 403)
        if not user.has_perm("payment_risk_review.execute_payment_risk_review"):
            raise ReconciliationError("PRR_PERMISSION_DENIED", "Permission denied", 403)

