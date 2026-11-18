"""Canonical UOM normalization independent of any one import workbook."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re
import unicodedata


@dataclass(frozen=True)
class CanonicalUom:
    code: str
    name: str
    dimension: str
    symbol: str
    decimal_places: int = 4
    requires_item_conversion: bool = False


CANONICAL_ALIASES = {
    "kg": CanonicalUom("kg", "千克", "mass", "kg"),
    "公斤": CanonicalUom("kg", "千克", "mass", "kg"),
    "千克": CanonicalUom("kg", "千克", "mass", "kg"),
    "m": CanonicalUom("m", "米", "length", "m"),
    "米": CanonicalUom("m", "米", "length", "m"),
    "mm": CanonicalUom("mm", "毫米", "length", "mm"),
    "毫米": CanonicalUom("mm", "毫米", "length", "mm"),
    "m2": CanonicalUom("m2", "平方米", "area", "m²"),
    "m²": CanonicalUom("m2", "平方米", "area", "m²"),
    "㎡": CanonicalUom("m2", "平方米", "area", "m²"),
    "平方米": CanonicalUom("m2", "平方米", "area", "m²"),
    "平方": CanonicalUom("m2", "平方米", "area", "m²"),
    "袋": CanonicalUom("袋", "袋", "count", "袋", 0, True),
    "根": CanonicalUom("根", "根", "count", "根", 0, True),
    "桶": CanonicalUom("桶", "桶", "count", "桶", 0, True),
}

AMBIGUOUS_DIMENSION_MARKERS = {
    "面积": "area",
}

# These are product-independent UOM definitions.  A packaging unit can exist
# centrally without asserting how many base units one bag/barrel contains;
# that conversion remains an item-level business fact.
STANDARD_INITIALIZATION_UNITS = tuple({
    item.code: item for item in CANONICAL_ALIASES.values()
    if item.code in {"kg", "m", "m2", "袋", "根", "桶"}
}.values())


def normalize_uom_token(value):
    text = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    return re.sub(r"[\s._-]+", "", text)


class UnitOfMeasureNormalizer:
    EXACT_MATCH = "EXACT_MATCH"
    NORMALIZED_MATCH = "NORMALIZED_MATCH"
    SEMANTIC_REVIEW = "SEMANTIC_REVIEW"
    INVALID = "INVALID"

    @classmethod
    def resolve(cls, raw_value, units):
        raw = str(raw_value or "").strip()
        if not raw:
            return {
                "classification": cls.INVALID,
                "raw": raw,
                "reason": "来源未提供计量单位。",
                "match": None,
            }
        exact = [
            row for row in units
            if raw in {str(row.get("code") or ""), str(row.get("name") or ""), str(row.get("symbol") or "")}
        ]
        if len(exact) == 1:
            return {
                "classification": cls.EXACT_MATCH,
                "raw": raw,
                "reason": "来源值精确命中一个正式计量单位。",
                "match": exact[0],
            }

        token = normalize_uom_token(raw)
        normalized = [
            row for row in units
            if token and token in {
                normalize_uom_token(row.get("code")),
                normalize_uom_token(row.get("name")),
                normalize_uom_token(row.get("symbol")),
            }
        ]
        if len(normalized) == 1:
            return {
                "classification": cls.NORMALIZED_MATCH,
                "raw": raw,
                "reason": "大小写、空白或符号规范化后命中一个正式计量单位。",
                "match": normalized[0],
            }

        if token in AMBIGUOUS_DIMENSION_MARKERS:
            return {
                "classification": cls.SEMANTIC_REVIEW,
                "raw": raw,
                "dimension": AMBIGUOUS_DIMENSION_MARKERS[token],
                "reason": "来源值只表达计量维度，未给出可换算的具体正式单位。",
                "match": None,
            }

        canonical = CANONICAL_ALIASES.get(token)
        if canonical:
            candidates = [
                row for row in units
                if normalize_uom_token(row.get("code")) == normalize_uom_token(canonical.code)
                or normalize_uom_token(row.get("name")) == normalize_uom_token(canonical.name)
                or normalize_uom_token(row.get("symbol")) == normalize_uom_token(canonical.symbol)
            ]
            if len(candidates) == 1:
                return {
                    "classification": cls.NORMALIZED_MATCH,
                    "raw": raw,
                    "reason": "来源别名已规范化为现有正式计量单位。",
                    "match": candidates[0],
                    "canonical": canonical.__dict__,
                }
            return {
                "classification": cls.NORMALIZED_MATCH,
                "raw": raw,
                "reason": "已映射到统一UOM标准；初始化Migration已就绪但尚未获准应用正式库。",
                "match": {
                    "id": None,
                    "code": canonical.code,
                    "name": canonical.name,
                    "symbol": canonical.symbol,
                    "dimension": canonical.dimension,
                    "decimal_places": canonical.decimal_places,
                    "standardInitialization": True,
                },
                "canonical": canonical.__dict__,
                "persistenceStatus": "MIGRATION_READY_NOT_APPLIED",
                "requiresItemConversion": canonical.requires_item_conversion,
            }

        return {
            "classification": cls.INVALID,
            "raw": raw,
            "reason": "来源值无法映射到受治理的正式UOM语义。",
            "match": None,
        }


def convert_uom_quantity(value, *, source_uom, target_uom) -> Decimal:
    """Convert using the formal rule: 1 current = factor x conversion base."""

    if not source_uom.is_active or not target_uom.is_active:
        raise ValueError("停用计量单位不得用于正式换算。")
    if source_uom.company_id != target_uom.company_id:
        raise ValueError("计量单位必须属于同一公司。")
    if source_uom.dimension != target_uom.dimension:
        raise ValueError("计量单位必须属于同一计量维度。")
    source_root = source_uom.conversion_base_id or source_uom.pk
    target_root = target_uom.conversion_base_id or target_uom.pk
    if source_root != target_root:
        raise ValueError("计量单位没有共同换算基准。")
    return (
        Decimal(str(value))
        * source_uom.conversion_factor
        / target_uom.conversion_factor
    )
