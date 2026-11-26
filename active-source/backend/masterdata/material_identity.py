"""Generic Material canonical identity policy.

The policy deliberately stays at service level.  Historical active duplicates
remain readable and no hash column or database uniqueness constraint is added.
"""

from __future__ import annotations

import re
import unicodedata

from .models import Material


IDENTITY_FIELDS = (
    "name", "category_id", "purpose", "specification", "base_uom_id",
)


def normalize_identity_text(value) -> str:
    """Apply only lossless basic text normalization used by exact matching."""

    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", normalized.strip()).casefold()


def canonical_identity(*, values: dict, instance: Material | None = None) -> dict:
    def effective(field, default=None):
        if field in values:
            return values[field]
        if instance is not None:
            return getattr(instance, field, default)
        return default

    def identity_id(field):
        value = effective(field)
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return value

    return {
        "name": normalize_identity_text(effective("name", "")),
        "category_id": identity_id("category_id"),
        "purpose": normalize_identity_text(effective("purpose", "")),
        "specification": normalize_identity_text(effective("specification", "")),
        "base_uom_id": identity_id("base_uom_id"),
    }


def material_identity(material: Material) -> dict:
    return canonical_identity(values={}, instance=material)


def matching_materials(*, company_id: int, identity: dict, exclude_id=None):
    """Return exact normalized matches without fuzzy specification matching."""

    rows = Material.objects.select_related("category", "base_uom").filter(
        company_id=company_id,
    ).order_by("pk")
    if exclude_id:
        rows = rows.exclude(pk=exclude_id)
    return [row for row in rows if material_identity(row) == identity]


def canonical_material_readback(material: Material) -> dict:
    return {
        "id": material.pk,
        "code": material.code,
        "name": material.name,
        "categoryId": material.category_id,
        "categoryName": material.category.name if material.category_id else "",
        "purpose": material.purpose,
        "specification": material.specification or "",
        "baseUomId": material.base_uom_id,
        "baseUomName": material.base_uom.name if material.base_uom_id else "",
        "isActive": material.is_active,
    }
