"""V51 authority boundary.

The draft module does not own parallel authority tables.  It re-reads the
formal V50 providers through the persisted payment-order-prepare source.
"""

from payment_order_prepare.providers import (
    PaymentInstructionPrepareRepository,
    FundsAvailabilityRepository,
    FundsAvailabilityProvider,
    PaymentSigningPolicyRepository,
    PaymentSigningPolicyProvider,
    PaymentAuthorizationRouteRepository,
    PaymentAuthorizationRouteProvider,
    PaymentSigningCapabilityRepository,
    PaymentSigningCapabilityProvider,
    MakerCheckerSegregationRepository,
    MakerCheckerSegregationProvider,
    DuplicatePaymentRiskRepository,
    evidence_dict,
    read_order_authorities as read_prepare_authorities,
)


class PaymentOrderPrepareRepository:
    repository_code = "payment_order_prepare_authority_repository"

    def get(self, source_id):
        from payment_order_prepare.models import PaymentOrderPrepare

        return (
            PaymentOrderPrepare.objects.select_related(
                "source_payment_instruction_prepare",
                "source_snapshot",
                "business_transaction",
                "audit_record",
            )
            .prefetch_related(
                "order_data_snapshots__previews",
                "authority_snapshots",
                "validation_executions__issues",
            )
            .filter(pk=source_id)
            .first()
        )


def read_order_authorities(draft, maker_user_id):
    """Read V47-V50 authorities against the formal prepare, never client data."""

    source = draft.source_payment_order_prepare
    source_data = source.order_data_snapshots.order_by("-order_data_version").first()
    authoritative_maker_id = (
        source_data.maker_user_id if source_data else str(maker_user_id)
    )
    return read_prepare_authorities(
        source,
        authoritative_maker_id,
    )


__all__ = [
    "PaymentOrderPrepareRepository",
    "PaymentInstructionPrepareRepository",
    "FundsAvailabilityRepository",
    "FundsAvailabilityProvider",
    "PaymentSigningPolicyRepository",
    "PaymentSigningPolicyProvider",
    "PaymentAuthorizationRouteRepository",
    "PaymentAuthorizationRouteProvider",
    "PaymentSigningCapabilityRepository",
    "PaymentSigningCapabilityProvider",
    "MakerCheckerSegregationRepository",
    "MakerCheckerSegregationProvider",
    "DuplicatePaymentRiskRepository",
    "read_order_authorities",
    "evidence_dict",
]
