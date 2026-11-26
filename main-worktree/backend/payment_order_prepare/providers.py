from dataclasses import dataclass
from decimal import Decimal

from payment_instruction_prepare.models import PaymentInstructionPrepare
from payment_instruction_prepare.providers import read_authorities as read_instruction_authorities

from .models import (
    FundsAvailabilityAuthority,
    MakerCheckerSegregationAuthority,
    PaymentAuthorizationRouteAuthority,
    PaymentOrderPrepare,
    PaymentSigningCapabilityAuthority,
    PaymentSigningPolicyAuthority,
)


@dataclass(frozen=True)
class AuthorityEvidence:
    provider: str
    repository: str
    authority_object: str
    authority_id: str
    version: int
    business_hash: str
    payload: dict


def _evidence(provider, repository, authority_object, authority_id, row, payload):
    if not row:
        return None
    return AuthorityEvidence(
        provider,
        repository,
        authority_object,
        str(authority_id),
        row.version,
        row.business_hash,
        payload,
    )


class PaymentInstructionPrepareRepository:
    repository_code = "payment_instruction_prepare_authority_repository"

    def get(self, source_id):
        return (
            PaymentInstructionPrepare.objects.select_related(
                "source_payment_request",
                "source_snapshot",
                "business_transaction",
                "audit_record",
            )
            .prefetch_related("instruction_data_snapshots__previews", "validation_executions")
            .filter(pk=source_id)
            .first()
        )


class FundsAvailabilityRepository:
    repository_code = "funds_availability_authority_repository"

    def get(self, *, tenant_id, legal_entity_id, ledger_book_id, payer_bank_account_id, currency):
        return FundsAvailabilityAuthority.objects.filter(
            tenant_id=tenant_id,
            legal_entity_id=legal_entity_id,
            ledger_book_id=ledger_book_id,
            payer_bank_account_id=payer_bank_account_id,
            currency=currency,
        ).first()


class FundsAvailabilityProvider:
    provider_code = "funds_availability_authority_provider"

    def __init__(self, repository=None):
        self.repository = repository or FundsAvailabilityRepository()

    def read(self, obj):
        row = self.repository.get(
            tenant_id=obj.tenant_id,
            legal_entity_id=obj.legal_entity_id,
            ledger_book_id=obj.ledger_book_id,
            payer_bank_account_id=obj.payer_bank_account_id,
            currency=obj.currency,
        )
        if not row:
            return None
        available_for_new = (
            Decimal(row.available_balance)
            - Decimal(row.committed_amount)
            - Decimal(row.reserved_amount)
        )
        return _evidence(
            self.provider_code,
            self.repository.repository_code,
            "FundsAvailabilityAuthority",
            row.funds_evidence_id,
            row,
            {
                "fundsEvidenceId": row.funds_evidence_id,
                "legalEntityId": row.legal_entity_id,
                "ledgerBookId": row.ledger_book_id,
                "payerBankAccountId": row.payer_bank_account_id,
                "currency": row.currency,
                "availableBalance": str(row.available_balance),
                "committedAmount": str(row.committed_amount),
                "reservedAmount": str(row.reserved_amount),
                "availableForNewPayment": str(available_for_new),
                "sufficient": row.active and available_for_new >= obj.payment_amount,
                "asOfTime": row.as_of_time.isoformat(),
                "active": row.active,
                "fundsReservationCreated": False,
                "bankBalanceDebited": False,
            },
        )


class PaymentSigningPolicyRepository:
    repository_code = "payment_signing_policy_authority_repository"

    def find(self, *, bank_code, channel_code, currency, amount):
        return (
            PaymentSigningPolicyAuthority.objects.filter(
                document_type="paymentOrderPrepare",
                bank_code=bank_code,
                channel_code=channel_code,
                currency=currency,
                amount_min__lte=amount,
                amount_max__gte=amount,
            )
            .order_by("amount_max")
            .first()
        )


class PaymentSigningPolicyProvider:
    provider_code = "payment_signing_policy_authority_provider"

    def __init__(self, repository=None):
        self.repository = repository or PaymentSigningPolicyRepository()

    def select(self, *, bank_code, channel_code, currency, amount):
        row = self.repository.find(
            bank_code=bank_code,
            channel_code=channel_code,
            currency=currency,
            amount=amount,
        )
        if not row:
            return None
        return _evidence(
            self.provider_code,
            self.repository.repository_code,
            "PaymentSigningPolicyAuthority",
            row.signing_policy_id,
            row,
            {
                "signingPolicyId": row.signing_policy_id,
                "policyCode": row.policy_code,
                "documentType": row.document_type,
                "bankCode": row.bank_code,
                "channelCode": row.channel_code,
                "currency": row.currency,
                "amountMin": str(row.amount_min),
                "amountMax": str(row.amount_max),
                "requiredSignatures": row.required_signatures,
                "requiredRoles": row.required_roles,
                "sequentialSigning": row.sequential_signing,
                "active": row.active,
            },
        )


class PaymentAuthorizationRouteRepository:
    repository_code = "payment_authorization_route_authority_repository"

    def get(self, signing_policy_id):
        return PaymentAuthorizationRouteAuthority.objects.filter(
            signing_policy__signing_policy_id=signing_policy_id
        ).first()


class PaymentAuthorizationRouteProvider:
    provider_code = "payment_authorization_route_authority_provider"

    def __init__(self, repository=None):
        self.repository = repository or PaymentAuthorizationRouteRepository()

    def read(self, signing_policy_id):
        row = self.repository.get(signing_policy_id)
        if not row:
            return None
        return _evidence(
            self.provider_code,
            self.repository.repository_code,
            "PaymentAuthorizationRouteAuthority",
            row.authorization_route_id,
            row,
            {
                "authorizationRouteId": row.authorization_route_id,
                "signingPolicyId": signing_policy_id,
                "steps": row.steps,
                "stepCount": len(row.steps),
                "allowParallel": row.allow_parallel,
                "active": row.active,
            },
        )


class PaymentSigningCapabilityRepository:
    repository_code = "payment_signing_capability_authority_repository"

    def get(self, bank_interface_profile_id):
        return PaymentSigningCapabilityAuthority.objects.filter(
            bank_interface_profile_id=bank_interface_profile_id
        ).first()


class PaymentSigningCapabilityProvider:
    provider_code = "payment_signing_capability_authority_provider"

    def __init__(self, repository=None):
        self.repository = repository or PaymentSigningCapabilityRepository()

    def read(self, bank_interface_profile_id):
        row = self.repository.get(bank_interface_profile_id)
        if not row:
            return None
        return _evidence(
            self.provider_code,
            self.repository.repository_code,
            "PaymentSigningCapabilityAuthority",
            row.signing_capability_id,
            row,
            {
                "signingCapabilityId": row.signing_capability_id,
                "bankInterfaceProfileId": row.bank_interface_profile_id,
                "credentialProfileIdMasked": row.credential_profile_id_masked,
                "credentialStatus": row.credential_status,
                "certificateStatus": row.certificate_status,
                "signingServiceStatus": row.signing_service_status,
                "supportedMessageFormat": row.supported_message_format,
                "active": row.active,
            },
        )


class MakerCheckerSegregationRepository:
    repository_code = "maker_checker_segregation_authority_repository"

    def get(self, tenant_id, maker_user_id):
        return MakerCheckerSegregationAuthority.objects.filter(
            tenant_id=tenant_id,
            maker_user_id=str(maker_user_id),
        ).first()


class MakerCheckerSegregationProvider:
    provider_code = "maker_checker_segregation_authority_provider"

    def __init__(self, repository=None):
        self.repository = repository or MakerCheckerSegregationRepository()

    def read(self, tenant_id, maker_user_id):
        row = self.repository.get(tenant_id, maker_user_id)
        if not row:
            return None
        roles_disjoint = (
            row.maker_cannot_check
            and row.maker_cannot_authorize
            and row.checker_cannot_final_authorize
            and bool(row.required_checker_roles)
            and bool(row.required_authorizer_roles)
            and not set(row.required_checker_roles).intersection(row.required_authorizer_roles)
        )
        return _evidence(
            self.provider_code,
            self.repository.repository_code,
            "MakerCheckerSegregationAuthority",
            row.segregation_policy_id,
            row,
            {
                "segregationPolicyId": row.segregation_policy_id,
                "makerUserId": row.maker_user_id,
                "requiredCheckerRoles": row.required_checker_roles,
                "requiredAuthorizerRoles": row.required_authorizer_roles,
                "makerCannotCheck": row.maker_cannot_check,
                "makerCannotAuthorize": row.maker_cannot_authorize,
                "checkerCannotFinalAuthorize": row.checker_cannot_final_authorize,
                "segregationValid": row.active and roles_disjoint,
                "active": row.active,
            },
        )


class DuplicatePaymentRiskRepository:
    repository_code = "payment_order_prepare_duplicate_risk_repository"

    def exists(self, obj):
        return PaymentOrderPrepare.objects.filter(
            supplier_id=obj.supplier_id,
            payee_bank_account_id=obj.payee_bank_account_id,
            currency=obj.currency,
            payment_amount=obj.payment_amount,
            planned_execution_date=obj.planned_execution_date,
            status="prepared",
        ).exclude(pk=obj.pk).exists()


def read_order_authorities(obj, maker_user_id):
    instruction = read_instruction_authorities(
        obj.source_payment_instruction_prepare,
        obj.planned_execution_date,
    )
    route = instruction.get("route")
    interface = instruction.get("interface")
    signing_policy = PaymentSigningPolicyProvider().select(
        bank_code=route.payload["payerBankCode"] if route else "",
        channel_code=interface.payload["channelCode"] if interface else "",
        currency=obj.currency,
        amount=obj.payment_amount,
    )
    authorization_route = PaymentAuthorizationRouteProvider().read(
        signing_policy.payload["signingPolicyId"] if signing_policy else ""
    )
    signing_capability = PaymentSigningCapabilityProvider().read(
        interface.payload["interfaceProfileId"] if interface else ""
    )
    return {
        **instruction,
        "funds": FundsAvailabilityProvider().read(obj),
        "signingPolicy": signing_policy,
        "authorizationRoute": authorization_route,
        "signingCapability": signing_capability,
        "segregation": MakerCheckerSegregationProvider().read(
            obj.tenant_id, maker_user_id
        ),
        "duplicateRisk": DuplicatePaymentRiskRepository().exists(obj),
    }


def evidence_dict(authorities):
    result = {}
    for name, evidence in authorities.items():
        if name == "duplicateRisk":
            result[name] = bool(evidence)
        elif evidence:
            result[name] = {
                "provider": evidence.provider,
                "repository": evidence.repository,
                "authorityObject": evidence.authority_object,
                "authorityId": evidence.authority_id,
                "version": evidence.version,
                "businessHash": evidence.business_hash,
                "payload": evidence.payload,
            }
        else:
            result[name] = None
    return result
