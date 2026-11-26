from dataclasses import dataclass

from payment_request_prepare.providers import (
    PayeeBankAccountProvider,
    PayerBankAccountProvider,
    PaymentHoldProvider,
)

from .models import (
    BankInterfaceProfileAuthority,
    BankPaymentCalendarAuthority,
    PaymentLimitAuthority,
    PaymentRouteAuthority,
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


class PaymentRouteRepository:
    def find(self, *, method, payer_bank, payee_bank, currency, amount):
        return (
            PaymentRouteAuthority.objects.filter(
                payment_method_code=method,
                payer_bank_code=payer_bank,
                payee_bank_code=payee_bank,
                currency=currency,
                amount_min__lte=amount,
                amount_max__gte=amount,
            )
            .order_by("priority", "route_code")
            .first()
        )


class PaymentRouteProvider:
    provider_code = "payment_route_authority_provider"
    repository_code = "payment_route_authority_repository"

    def __init__(self, repository=None):
        self.repository = repository or PaymentRouteRepository()

    def select(self, **criteria):
        row = self.repository.find(**criteria)
        if not row:
            return None
        return AuthorityEvidence(
            self.provider_code, self.repository_code, "PaymentRouteAuthority",
            row.route_id, row.version, row.business_hash,
            {
                "routeId": row.route_id, "routeCode": row.route_code,
                "paymentMethodCode": row.payment_method_code,
                "payerBankCode": row.payer_bank_code,
                "payeeBankCode": row.payee_bank_code,
                "currency": row.currency, "amountMin": str(row.amount_min),
                "amountMax": str(row.amount_max), "priority": row.priority,
                "active": row.active,
            },
        )


class BankInterfaceRepository:
    def find(self, bank_code):
        return BankInterfaceProfileAuthority.objects.filter(
            bank_code=bank_code
        ).order_by("channel_code").first()


class BankInterfaceProvider:
    provider_code = "bank_interface_capability_provider"
    repository_code = "bank_interface_profile_repository"

    def __init__(self, repository=None):
        self.repository = repository or BankInterfaceRepository()

    def read(self, bank_code):
        row = self.repository.find(bank_code)
        if not row:
            return None
        return AuthorityEvidence(
            self.provider_code, self.repository_code,
            "BankInterfaceProfileAuthority", row.interface_profile_id,
            row.version, row.business_hash,
            {
                "interfaceProfileId": row.interface_profile_id,
                "bankCode": row.bank_code, "channelCode": row.channel_code,
                "supportedCurrencies": row.supported_currencies,
                "supportedPaymentMethods": row.supported_payment_methods,
                "messageFormat": row.message_format,
                "connectionStatus": row.connection_status,
                "paymentEnabled": row.payment_enabled, "active": row.active,
            },
        )


class BankCalendarRepository:
    def get(self, bank_code, calendar_date):
        return BankPaymentCalendarAuthority.objects.filter(
            bank_code=bank_code, calendar_date=calendar_date
        ).first()


class BankCalendarProvider:
    provider_code = "bank_business_day_cutoff_provider"
    repository_code = "bank_payment_calendar_repository"

    def __init__(self, repository=None):
        self.repository = repository or BankCalendarRepository()

    def read(self, bank_code, calendar_date):
        row = self.repository.get(bank_code, calendar_date)
        if not row:
            return None
        return AuthorityEvidence(
            self.provider_code, self.repository_code,
            "BankPaymentCalendarAuthority",
            f"{row.bank_code}:{row.calendar_date.isoformat()}",
            row.version, row.business_hash,
            {
                "bankCode": row.bank_code,
                "date": row.calendar_date.isoformat(),
                "businessDay": row.business_day,
                "paymentAllowed": row.payment_allowed,
                "cutoffTime": row.cutoff_time.isoformat(),
                "timezone": row.timezone,
            },
        )


class PaymentLimitRepository:
    def get(self, legal_entity_id, payer_bank_account_id, currency):
        return PaymentLimitAuthority.objects.filter(
            legal_entity_id=legal_entity_id,
            payer_bank_account_id=payer_bank_account_id,
            currency=currency,
        ).first()


class PaymentLimitProvider:
    provider_code = "payment_limit_authority_provider"
    repository_code = "payment_limit_authority_repository"

    def __init__(self, repository=None):
        self.repository = repository or PaymentLimitRepository()

    def read(self, legal_entity_id, payer_bank_account_id, currency):
        row = self.repository.get(legal_entity_id, payer_bank_account_id, currency)
        if not row:
            return None
        return AuthorityEvidence(
            self.provider_code, self.repository_code, "PaymentLimitAuthority",
            str(row.pk), row.version, row.business_hash,
            {
                "legalEntityId": row.legal_entity_id,
                "payerBankAccountId": row.payer_bank_account_id,
                "currency": row.currency,
                "singlePaymentLimit": str(row.single_payment_limit),
                "dailyPaymentLimit": str(row.daily_payment_limit),
                "currentDailyCommittedAmount": str(row.current_daily_committed_amount),
                "active": row.active,
            },
        )


def read_authorities(obj, planned_execution_date):
    payer = PayerBankAccountProvider().read(obj.payer_bank_account_id)
    payee = PayeeBankAccountProvider().read(obj.payee_bank_account_id)
    payer_bank = payer.payload.get("bankName", "") if payer else ""
    payee_bank_code = payee.payload.get("bankCode", "") if payee else ""
    route = PaymentRouteProvider().select(
        method=obj.payment_method_code,
        payer_bank=payer_bank,
        payee_bank=payee_bank_code,
        currency=obj.currency,
        amount=obj.payment_amount,
    ) if payer and payee else None
    interface = BankInterfaceProvider().read(
        route.payload["payerBankCode"] if route else payer_bank
    )
    calendar = BankCalendarProvider().read(
        route.payload["payerBankCode"] if route else payer_bank,
        planned_execution_date,
    )
    limit = PaymentLimitProvider().read(
        obj.legal_entity_id, obj.payer_bank_account_id, obj.currency
    )
    hold = PaymentHoldProvider().read(obj.source_payment_request_id)
    return {
        "payer": payer, "payee": payee, "route": route,
        "interface": interface, "calendar": calendar, "limit": limit,
        "hold": hold,
    }
