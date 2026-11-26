from dataclasses import dataclass

from .models import (
    PayeeBankAccountAuthority,
    PayerBankAccountAuthority,
    PaymentCalendarAuthority,
    PaymentHoldAuthority,
    PaymentMethodAuthority,
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


class PayeeBankAccountRepository:
    model = PayeeBankAccountAuthority

    def get(self, bank_account_id):
        return self.model.objects.filter(bank_account_id=bank_account_id).first()


class PayeeBankAccountProvider:
    provider_code = "payee_bank_account_authority_provider"
    repository_code = "payee_bank_account_authority_repository"

    def __init__(self, repository=None):
        self.repository = repository or PayeeBankAccountRepository()

    def read(self, bank_account_id):
        row = self.repository.get(bank_account_id)
        if not row:
            return None
        return AuthorityEvidence(
            self.provider_code,
            self.repository_code,
            "PayeeBankAccountAuthority",
            row.bank_account_id,
            row.version,
            row.business_hash,
            {
                "bankAccountId": row.bank_account_id,
                "accountName": row.account_name,
                "maskedAccountNo": row.masked_account_no,
                "bankName": row.bank_name,
                "bankBranch": row.bank_branch,
                "bankCode": row.bank_code,
                "supplierId": row.supplier_id,
                "currency": row.currency,
                "active": row.active,
                "paymentEnabled": row.payment_enabled,
                "tenantId": row.tenant_id,
            },
        )


class PayerBankAccountRepository:
    model = PayerBankAccountAuthority

    def get(self, bank_account_id):
        return self.model.objects.filter(bank_account_id=bank_account_id).first()


class PayerBankAccountProvider:
    provider_code = "payer_bank_account_authority_provider"
    repository_code = "payer_bank_account_authority_repository"

    def __init__(self, repository=None):
        self.repository = repository or PayerBankAccountRepository()

    def read(self, bank_account_id):
        row = self.repository.get(bank_account_id)
        if not row:
            return None
        return AuthorityEvidence(
            self.provider_code,
            self.repository_code,
            "PayerBankAccountAuthority",
            row.bank_account_id,
            row.version,
            row.business_hash,
            {
                "bankAccountId": row.bank_account_id,
                "accountName": row.account_name,
                "maskedAccountNo": row.masked_account_no,
                "bankName": row.bank_name,
                "legalEntityId": row.legal_entity_id,
                "ledgerBookId": row.ledger_book_id,
                "currency": row.currency,
                "availableForPayment": row.available_for_payment,
                "active": row.active,
                "tenantId": row.tenant_id,
            },
        )


class PaymentMethodRepository:
    model = PaymentMethodAuthority

    def get(self, payment_method_code):
        return self.model.objects.filter(
            payment_method_code=payment_method_code
        ).first()


class PaymentMethodProvider:
    provider_code = "payment_method_authority_provider"
    repository_code = "payment_method_authority_repository"

    def __init__(self, repository=None):
        self.repository = repository or PaymentMethodRepository()

    def read(self, payment_method_code):
        row = self.repository.get(payment_method_code)
        if not row:
            return None
        return AuthorityEvidence(
            self.provider_code,
            self.repository_code,
            "PaymentMethodAuthority",
            row.payment_method_code,
            row.version,
            row.business_hash,
            {
                "paymentMethodCode": row.payment_method_code,
                "paymentMethodName": row.payment_method_name,
                "active": row.active,
                "supportedCurrency": row.supported_currency,
                "requiresBankAccount": row.requires_bank_account,
                "requiresApproval": row.requires_approval,
            },
        )


class PaymentCalendarRepository:
    model = PaymentCalendarAuthority

    def get(self, calendar_date):
        return self.model.objects.filter(calendar_date=calendar_date).first()


class PaymentCalendarProvider:
    provider_code = "payment_calendar_authority_provider"
    repository_code = "payment_calendar_authority_repository"

    def __init__(self, repository=None):
        self.repository = repository or PaymentCalendarRepository()

    def read(self, calendar_date):
        row = self.repository.get(calendar_date)
        if not row:
            return None
        return AuthorityEvidence(
            self.provider_code,
            self.repository_code,
            "PaymentCalendarAuthority",
            row.calendar_date.isoformat(),
            row.version,
            row.business_hash,
            {
                "date": row.calendar_date.isoformat(),
                "businessDay": row.business_day,
                "paymentAllowed": row.payment_allowed,
                "holidayCode": row.holiday_code,
            },
        )


class PaymentHoldRepository:
    model = PaymentHoldAuthority

    def get(self, source_object_id):
        return self.model.objects.filter(
            source_object_id=str(source_object_id)
        ).first()


class PaymentHoldProvider:
    provider_code = "payment_hold_authority_provider"
    repository_code = "payment_hold_authority_repository"

    def __init__(self, repository=None):
        self.repository = repository or PaymentHoldRepository()

    def read(self, source_object_id):
        row = self.repository.get(source_object_id)
        if not row:
            return None
        return AuthorityEvidence(
            self.provider_code,
            self.repository_code,
            "PaymentHoldAuthority",
            row.source_object_id,
            row.version,
            row.business_hash,
            {
                "sourceObjectId": row.source_object_id,
                "holdStatus": row.hold_status,
                "holdReason": row.hold_reason,
                "releaseRequired": row.release_required,
            },
        )


def read_all_payment_authorities(
    *,
    payee_bank_account_id,
    payer_bank_account_id,
    payment_method_code,
    planned_payment_date,
    source_object_id,
):
    return {
        "payee": PayeeBankAccountProvider().read(payee_bank_account_id),
        "payer": PayerBankAccountProvider().read(payer_bank_account_id),
        "method": PaymentMethodProvider().read(payment_method_code),
        "calendar": PaymentCalendarProvider().read(planned_payment_date),
        "hold": PaymentHoldProvider().read(source_object_id),
    }
