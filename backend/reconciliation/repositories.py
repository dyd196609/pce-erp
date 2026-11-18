from .models import PayableCheckAuthorityRecord, SupplierSettlementAuthorityRecord


class SupplierSettlementAuthorityRepository:
    repository_code = "scm_supplier_settlement_authority_repository"

    def get(self, *, tenant_id, company_id, settlement_no):
        return SupplierSettlementAuthorityRecord.objects.filter(
            tenant_id=tenant_id,
            company_id=company_id,
            settlement_no=settlement_no,
        ).first()


class PayableCheckAuthorityRepository:
    repository_code = "finance_payable_check_authority_repository"

    def get(self, *, tenant_id, company_id, payable_check_no):
        return PayableCheckAuthorityRecord.objects.filter(
            tenant_id=tenant_id,
            company_id=company_id,
            payable_check_no=payable_check_no,
        ).first()
