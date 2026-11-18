from payment_risk_review.services import eligibility as risk_review_eligibility

from .repositories import PaymentRiskReviewRepository


class PaymentRiskReviewAuthorityProvider:
    provider_code = "payment_risk_review_authority_provider"

    def __init__(self, repository=None):
        self.repository = repository or PaymentRiskReviewRepository()

    def read(self, source_id):
        review = self.repository.get(source_id)
        if not review:
            return None
        draft = review.source_payment_order_draft
        execution = review.executions.order_by("-review_version").first()
        evidence = review.evidence_snapshots.order_by("-evidence_version").first()
        return {
            "provider": self.provider_code,
            "repository": self.repository.repository_code,
            "authorityObject": "PaymentRiskReview",
            "review": review,
            "source": {
                "id": review.pk,
                "reviewNo": review.review_no,
                "version": review.version,
                "reviewVersion": review.review_version,
                "ruleVersion": execution.rule_version if execution else "",
                "scenarioCode": review.scenario_code,
                "status": review.status,
                "riskResult": review.risk_result,
                "riskLevel": review.risk_level,
                "eligibility": risk_review_eligibility(review),
                "resultHash": execution.result_hash if execution else "",
            },
            "payment": {
                "draftId": draft.pk,
                "draftNo": draft.draft_no,
                "draftVersion": draft.version,
                "supplierId": draft.supplier_id,
                "supplierName": draft.supplier_name,
                "legalEntity": draft.legal_entity_name,
                "ledgerBook": draft.ledger_book_id,
                "currency": draft.currency,
                "amount": str(draft.payment_amount),
                "plannedExecutionDate": draft.planned_execution_date.isoformat(),
            },
            "evidence": {
                "funds": evidence.funds_evidence if evidence else {},
                "bankInterface": (evidence.bank_evidence if evidence else {}).get("interface", {}),
                "account": {
                    "payer": (evidence.bank_evidence if evidence else {}).get("payer", {}),
                    "payee": (evidence.bank_evidence if evidence else {}).get("payee", {}),
                },
                "riskReview": {
                    "reviewNo": review.review_no,
                    "status": review.status,
                    "riskResult": review.risk_result,
                    "riskLevel": review.risk_level,
                    "reviewVersion": review.review_version,
                    "ruleVersion": execution.rule_version if execution else "",
                    "resultHash": execution.result_hash if execution else "",
                },
                "segregation": evidence.segregation_evidence if evidence else {},
            },
        }


__all__ = ["PaymentRiskReviewAuthorityProvider"]
