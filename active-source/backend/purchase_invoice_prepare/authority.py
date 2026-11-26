from dataclasses import dataclass

from .models import LegalEntityInvoiceAuthorityRecord, SupplierInvoiceAuthorityRecord


@dataclass(frozen=True)
class SupplierInvoiceAuthority:
    supplier_id: str
    supplier_name: str
    seller_tax_id: str
    status: str
    version: int
    business_hash: str


@dataclass(frozen=True)
class LegalEntityInvoiceAuthority:
    legal_entity_id: str
    legal_entity_name: str
    buyer_tax_id: str
    ledger_book_id: str
    currency: str
    status: str
    version: int
    business_hash: str


class SupplierInvoiceAuthorityRepository:
    def get_active(self, tenant_id, supplier_id):
        return SupplierInvoiceAuthorityRecord.objects.filter(
            tenant_id=tenant_id, supplier_id=supplier_id, status="active"
        ).first()


class LegalEntityInvoiceAuthorityRepository:
    def get_active(self, tenant_id, legal_entity_id):
        return LegalEntityInvoiceAuthorityRecord.objects.filter(
            tenant_id=tenant_id, legal_entity_id=legal_entity_id, status="active"
        ).first()


class SupplierInvoiceAuthorityProvider:
    provider_code = "SupplierInvoiceAuthorityProvider"
    repository_code = "SupplierInvoiceAuthorityRepository"

    def __init__(self, repository=None):
        self.repository = repository or SupplierInvoiceAuthorityRepository()

    def read(self, prepare):
        record = self.repository.get_active(prepare.tenant_id, prepare.supplier_id)
        if not record:
            return None
        return SupplierInvoiceAuthority(
            record.supplier_id,
            record.supplier_name,
            record.seller_tax_id,
            record.status,
            record.authority_version,
            record.business_hash,
        )


class LegalEntityInvoiceAuthorityProvider:
    provider_code = "LegalEntityInvoiceAuthorityProvider"
    repository_code = "LegalEntityInvoiceAuthorityRepository"

    def __init__(self, repository=None):
        self.repository = repository or LegalEntityInvoiceAuthorityRepository()

    def read(self, prepare):
        record = self.repository.get_active(prepare.tenant_id, prepare.legal_entity_id)
        if not record:
            return None
        return LegalEntityInvoiceAuthority(
            record.legal_entity_id,
            record.legal_entity_name,
            record.buyer_tax_id,
            record.ledger_book_id,
            record.currency,
            record.status,
            record.authority_version,
            record.business_hash,
        )
