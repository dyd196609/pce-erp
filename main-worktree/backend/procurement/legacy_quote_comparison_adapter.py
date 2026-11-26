"""只读 Legacy 报价比较事实投影；禁止读取浏览器缓存或写入业务表。"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path

from django.conf import settings


LEGACY_SOURCE_RELATIVE_PATH = Path("docs/acceptance/SCM-QUOTE-COMPARISON-LEGACY-SOURCE-R9.json")
LEGACY_SHA_RELATIVE_PATH = Path("docs/acceptance/SCM-QUOTE-COMPARISON-LEGACY-SOURCE-R9.json.sha256")


@dataclass(frozen=True)
class QuoteComparisonFactProjection:
    projectionId: str
    legacyQuoteComparisonNo: str
    canonicalQuoteComparisonNo: str
    factOrigin: str
    sourceConfidence: str
    sourceInquiryNo: str
    sourceQuotationNos: tuple
    supplierEvidence: tuple
    materialLines: tuple
    quantity: str
    quotationAmount: tuple
    lowestPrice: str
    comparisonResult: object
    generatedAt: str
    traceAliasId: str
    sourceFingerprint: str

    def to_dict(self):
        return asdict(self)


class LegacyQuoteComparisonAdapter:
    fact_origin = "legacy_verified_fact"
    source_confidence = "B"

    def __init__(self, repository_root=None):
        self.repository_root = Path(repository_root or Path(settings.BASE_DIR).parent)
        self.source_path = self.repository_root / LEGACY_SOURCE_RELATIVE_PATH
        self.sha_path = self.repository_root / LEGACY_SHA_RELATIVE_PATH

    def _load_verified_source(self):
        source_bytes = self.source_path.read_bytes()
        actual_hash = sha256(source_bytes).hexdigest()
        expected_hash = self.sha_path.read_text(encoding="utf-8").split()[0].strip().lower()
        if actual_hash != expected_hash:
            raise ValueError("LEGACY_QUOTE_COMPARISON_SOURCE_SHA_MISMATCH")
        payload = json.loads(source_bytes.decode("utf-8"))
        records = payload.get("records") or []
        if payload.get("recordCount") != 13 or len(records) != 13:
            raise ValueError("LEGACY_QUOTE_COMPARISON_RECORD_COUNT_INVALID")
        if any(item.get("integrityStatus") != "PASS" for item in records):
            raise ValueError("LEGACY_QUOTE_COMPARISON_INTEGRITY_NOT_VERIFIED")
        return actual_hash, records

    @staticmethod
    def _supplier_evidence(items):
        return tuple({
            "supplierId": item.get("supplierId"),
            "supplierCode": item.get("supplierCode") or item.get("supplierId"),
            "supplierName": item.get("supplierName"),
            "quotationNo": item.get("sourceQuotationNo"),
            "quotationAmount": item.get("quotationAmount"),
            "currency": item.get("currency") or "CNY",
            "quotationStatus": item.get("quotationStatus"),
            "receivedAt": item.get("receivedAt"),
        } for item in items)

    def list_projections(self):
        source_hash, records = self._load_verified_source()
        projections = []
        for index, record in enumerate(records, start=1):
            comparison_no = str(record.get("quoteComparisonNo") or "").strip()
            if not comparison_no:
                raise ValueError("LEGACY_QUOTE_COMPARISON_NO_REQUIRED")
            identity_hash = sha256(comparison_no.encode("utf-8")).hexdigest().upper()
            projections.append(QuoteComparisonFactProjection(
                projectionId=f"LQCP-{source_hash[:12].upper()}-{index:02d}",
                legacyQuoteComparisonNo=comparison_no,
                canonicalQuoteComparisonNo=comparison_no,
                factOrigin=self.fact_origin,
                sourceConfidence=self.source_confidence,
                sourceInquiryNo=str(record.get("sourceInquiryNo") or ""),
                sourceQuotationNos=tuple(record.get("sourceQuotationNo") or ()),
                supplierEvidence=self._supplier_evidence(record.get("supplierEvidence") or ()),
                materialLines=({
                    "materialCode": record.get("materialCode"),
                    "materialName": record.get("materialName"),
                    "quantity": str(record.get("quantity")),
                },),
                quantity=str(record.get("quantity")),
                quotationAmount=tuple(record.get("quotationAmount") or ()),
                lowestPrice=str(record.get("lowestPrice")),
                comparisonResult=record.get("comparisonResult"),
                generatedAt=str(record.get("generatedAt") or ""),
                traceAliasId=f"BTA-LEGACY-QC-{identity_hash[:20]}",
                sourceFingerprint=source_hash,
            ))
        return tuple(projections)

    def get_projection(self, projection_id):
        return next((item for item in self.list_projections()
            if item.projectionId == str(projection_id or "").strip()), None)

