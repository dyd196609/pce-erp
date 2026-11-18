from decimal import Decimal

from payment_order_draft.providers import evidence_dict, read_order_authorities
from payment_order_draft.services import serialize_draft

from .repositories import PaymentOrderDraftRepository


class PaymentOrderDraftRiskEvidenceProvider:
    provider_code = "payment_order_draft_risk_evidence_provider"

    def __init__(self, repository=None):
        self.repository = repository or PaymentOrderDraftRepository()

    def read(self, source_id):
        draft = self.repository.get(source_id)
        if not draft:
            return None
        data = draft.draft_data_snapshots.order_by("-draft_data_version").first()
        maker_id = data.maker_user_id if data else draft.created_by_id
        authorities = evidence_dict(read_order_authorities(draft, maker_id))
        serialized = serialize_draft(draft)
        funds = (authorities.get("funds") or {}).get("payload") or {}
        payer = (authorities.get("payer") or {}).get("payload") or {}
        payee = (authorities.get("payee") or {}).get("payload") or {}
        route = (authorities.get("route") or {}).get("payload") or {}
        interface = (authorities.get("interface") or {}).get("payload") or {}
        calendar = (authorities.get("calendar") or {}).get("payload") or {}
        limit = (authorities.get("limit") or {}).get("payload") or {}
        hold = (authorities.get("hold") or {}).get("payload") or {}
        segregation = (authorities.get("segregation") or {}).get("payload") or {}
        signing = (authorities.get("signingPolicy") or {}).get("payload") or {}
        authorization = (authorities.get("authorizationRoute") or {}).get("payload") or {}
        capability = (authorities.get("signingCapability") or {}).get("payload") or {}
        return {
            "source": {
                "provider": self.provider_code,
                "repository": self.repository.repository_code,
                "authorityObject": "PaymentOrderDraft",
                "draftId": draft.pk,
                "draftNo": draft.draft_no,
                "version": draft.version,
                "reviewVersion": draft.current_review_version,
                "status": draft.status,
                "reviewStatus": draft.review_status,
                "reviewResultCode": draft.review_result_code,
                "draftDataStatus": draft.draft_data_status,
                "paymentAmount": str(draft.payment_amount),
                "currency": draft.currency,
                "plannedExecutionDate": draft.planned_execution_date.isoformat(),
                "plannedExecutionTime": (
                    draft.planned_execution_time.isoformat()
                    if draft.planned_execution_time
                    else ""
                ),
                "supplierId": draft.supplier_id,
                "supplierName": draft.supplier_name,
                "payerBankAccountId": draft.payer_bank_account_id,
                "payeeBankAccountId": draft.payee_bank_account_id,
                "paymentReference": (serialized.get("draftData") or {}).get("paymentReference", ""),
                "previewHash": (serialized.get("preview") or {}).get("previewHash", ""),
            },
            "funds": {
                "provider": "funds_availability_authority_provider",
                "repository": "funds_availability_authority_repository",
                **funds,
            },
            "bank": {
                "payer": payer,
                "payee": payee,
                "route": route,
                "interface": interface,
                "calendar": calendar,
                "limit": limit,
                "hold": hold,
                "signingPolicy": signing,
                "authorizationRoute": authorization,
                "signingCapability": capability,
            },
            "supplier": {
                "provider": "supplier_risk_authority_provider",
                "repository": "payment_order_draft_risk_source_repository",
                "supplierId": draft.supplier_id,
                "supplierName": draft.supplier_name,
                "active": bool(draft.supplier_id and draft.supplier_name),
                "blocked": False,
                "accountActive": bool(payee.get("active") and payee.get("paymentEnabled")),
            },
            "duplicatePayment": {
                "provider": "duplicate_payment_risk_authority_provider",
                "repository": "duplicate_payment_risk_repository",
                "duplicate": bool(authorities.get("duplicateRisk")),
                "key": "|".join([
                    draft.supplier_id,
                    str(Decimal(draft.payment_amount)),
                    draft.currency,
                    draft.planned_execution_date.isoformat(),
                    draft.payee_bank_account_id,
                ]),
            },
            "segregation": {
                "provider": "maker_checker_segregation_authority_provider",
                "repository": "maker_checker_segregation_authority_repository",
                **segregation,
            },
        }


__all__ = ["PaymentOrderDraftRiskEvidenceProvider"]

