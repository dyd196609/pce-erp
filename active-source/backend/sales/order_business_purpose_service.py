"""Read-only SalesOrder business-purpose resolution.

Stage A deliberately keeps this service outside every admission, PDE, BOM and
planning path.  A legacy mapping is an interpretation for readback only; it is
never persisted and is not a formal ``SalesOrder.business_purpose`` fact.
"""

from dataclasses import dataclass

from .models import SalesOrder


PERSISTED_FACT = "PERSISTED_BUSINESS_PURPOSE"
LEGACY_MAPPING = "LEGACY_MAPPING"


@dataclass(frozen=True)
class OrderBusinessPurposeResolution:
    business_purpose: str
    business_purpose_label: str
    fact_source: str
    is_persisted: bool
    is_legacy_mapping: bool
    legacy_basis: str
    admission_enforcement_enabled: bool = False

    def as_dict(self):
        return {
            "businessPurpose": self.business_purpose,
            "businessPurposeLabel": self.business_purpose_label,
            "factSource": self.fact_source,
            "isPersisted": self.is_persisted,
            "isLegacyMapping": self.is_legacy_mapping,
            "legacyBasis": self.legacy_basis,
            "admissionEnforcementEnabled": self.admission_enforcement_enabled,
        }


def _label(purpose):
    return dict(SalesOrder.BusinessPurpose.choices)[purpose]


def resolve_order_business_purpose(order):
    """Return the persisted purpose or a non-authoritative legacy mapping.

    The resolver performs no saves, updates or state transitions.  Stage A
    callers must not use this result to change CRM/PDE/BOM/Planning behavior.
    """

    persisted = str(getattr(order, "business_purpose", "") or "").strip()
    valid_purposes = set(SalesOrder.BusinessPurpose.values)
    if persisted:
        if persisted not in valid_purposes:
            raise ValueError(f"Unsupported SalesOrder business purpose: {persisted}")
        return OrderBusinessPurposeResolution(
            business_purpose=persisted,
            business_purpose_label=_label(persisted),
            fact_source=PERSISTED_FACT,
            is_persisted=True,
            is_legacy_mapping=False,
            legacy_basis="",
        )

    marker = str(getattr(order, "acceptance_marker", "") or "").strip()
    if marker == "DEVELOPMENT_ONLY":
        purpose = SalesOrder.BusinessPurpose.DEVELOPMENT_VALIDATION
        basis = "acceptance_marker=DEVELOPMENT_ONLY"
    elif marker:
        purpose = SalesOrder.BusinessPurpose.SYSTEM_TEST
        basis = "acceptance_marker is non-empty"
    else:
        purpose = SalesOrder.BusinessPurpose.FORMAL_SALE
        basis = "acceptance_marker is empty"

    return OrderBusinessPurposeResolution(
        business_purpose=purpose,
        business_purpose_label=_label(purpose),
        fact_source=LEGACY_MAPPING,
        is_persisted=False,
        is_legacy_mapping=True,
        legacy_basis=basis,
    )


def order_business_purpose_facts(order):
    """Dictionary projection for future API consumers; currently query-only."""

    return resolve_order_business_purpose(order).as_dict()

