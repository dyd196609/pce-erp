from .repositories import PayableCheckAuthorityRepository, SupplierSettlementAuthorityRepository


class SupplierSettlementEvidenceProvider:
    provider_code = "scm_supplier_settlement_authority_provider"
    authority_type = "supplier_settlement"

    def __init__(self, repository=None):
        self.repository = repository or SupplierSettlementAuthorityRepository()

    def load(self, reconciliation):
        record = self.repository.get(
            tenant_id=reconciliation.tenant_id,
            company_id=reconciliation.company_id,
            settlement_no=reconciliation.source_supplier_settlement_no,
        )
        if not record:
            return None
        return {
            "providerCode": self.provider_code,
            "repositoryCode": self.repository.repository_code,
            "authorityType": self.authority_type,
            "authorityObjectId": record.authority_object_id,
            "authorityObjectNo": record.settlement_no,
            "authorityVersion": record.authority_version,
            "businessHash": record.business_hash,
            "supplierId": record.supplier_id,
            "supplierName": record.supplier_name,
            "legalEntityId": record.legal_entity_id,
            "ledgerBookId": record.ledger_book_id,
            "currency": record.currency,
            "amount": str(record.amount),
            "quantity": str(record.quantity),
            "businessStatus": record.business_status,
        }


class PayableCheckEvidenceProvider:
    provider_code = "finance_payable_check_authority_provider"
    authority_type = "payable_check"

    def __init__(self, repository=None):
        self.repository = repository or PayableCheckAuthorityRepository()

    def load(self, reconciliation):
        record = self.repository.get(
            tenant_id=reconciliation.tenant_id,
            company_id=reconciliation.company_id,
            payable_check_no=reconciliation.source_payable_check_no,
        )
        if not record:
            return None
        return {
            "providerCode": self.provider_code,
            "repositoryCode": self.repository.repository_code,
            "authorityType": self.authority_type,
            "authorityObjectId": record.authority_object_id,
            "authorityObjectNo": record.payable_check_no,
            "authorityVersion": record.authority_version,
            "businessHash": record.business_hash,
            "supplierId": record.supplier_id,
            "legalEntityId": record.legal_entity_id,
            "ledgerBookId": record.ledger_book_id,
            "currency": record.currency,
            "amount": str(record.checked_amount),
            "quantity": str(record.checked_quantity),
            "businessStatus": record.business_status,
        }
