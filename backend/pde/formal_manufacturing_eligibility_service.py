"""Fail-closed formal-manufacturing eligibility projected from persisted order facts.

The service is deliberately read-only.  It never copies the business purpose onto
manufacturing objects and never infers purpose from an order number or UI state.
"""

from __future__ import annotations

from typing import Any

from django.db import DatabaseError, connections

from sales.models import SalesOrder, SalesOrderItem

from .models import (
    BOMVersion,
    EngineeringCalculationRecord,
    OrderEngineeringInstance,
    ProductBOM,
    ProductManufacturingOutput,
)


class FormalManufacturingEligibilityService:
    FORMAL_SALE = "FORMAL_SALE"
    DEVELOPMENT_VALIDATION = "DEVELOPMENT_VALIDATION"
    UNKNOWN = "UNKNOWN"

    PURPOSE_LABELS = {
        FORMAL_SALE: "正式销售订单",
        DEVELOPMENT_VALIDATION: "开发验证订单",
        UNKNOWN: "订单用途未确认",
    }
    DEVELOPMENT_MESSAGE = "开发验证BOM仅允许草稿和只读验证，不得进入正式制造评审或发布。"

    @classmethod
    def _normalize_purpose(cls, value: Any) -> str | None:
        code = str(value or "").strip().upper()
        aliases = {
            "FORMAL_SALE": cls.FORMAL_SALE,
            "FORMAL": cls.FORMAL_SALE,
            "DEVELOPMENT_VALIDATION": cls.DEVELOPMENT_VALIDATION,
            "DEVELOPMENT_ONLY": cls.DEVELOPMENT_VALIDATION,
        }
        return aliases.get(code)

    @staticmethod
    def _database_read_cache(order: SalesOrder, read_cache: Any) -> Any:
        """Use only this actor's live, same-company/DB atomic read context."""
        if read_cache is None:
            return None
        from .operation_requirement_service import _ReadOnlyProofCache
        alias = order._state.db or "default"
        if (not isinstance(read_cache, _ReadOnlyProofCache)
                or read_cache.database_alias != alias
                or read_cache._connection is not connections[alias]
                or not read_cache.is_current(order.company_id)):
            return None
        return read_cache

    @staticmethod
    def _database_purpose(order: SalesOrder, read_cache: Any = None) -> dict[str, Any]:
        """Read the already-persisted compatibility column when it exists."""
        alias = order._state.db or "default"
        db = connections[alias]
        table = order._meta.db_table
        cache = FormalManufacturingEligibilityService._database_read_cache(order, read_cache)
        scope = (order.company_id, cache.user_id, alias, table, cache._write_epoch) if cache is not None else None
        value_key = ("formal_manufacturing_database_purpose", *scope, order.pk) if scope is not None else None
        columns_key = ("formal_manufacturing_purpose_columns", *scope) if scope is not None else None
        if cache is not None and value_key in cache:
            # Only immutable raw DB values are shared, never the eligibility
            # decision or the returned mutable evidence dictionary.
            available, value = cache[value_key]
            return {"available": available, "value": value, "error": None}
        try:
            with db.cursor() as cursor:
                columns = cache.get(columns_key) if cache is not None else None
                if columns is None:
                    columns = frozenset(column.name for column in db.introspection.get_table_description(cursor, table))
                if "business_purpose" not in columns:
                    result = {"available": False, "value": None, "error": None}
                else:
                    quote = db.ops.quote_name
                    cursor.execute(
                        f"SELECT {quote('business_purpose')} FROM {quote(table)} "
                        f"WHERE {quote(order._meta.pk.column)} = %s",
                        [order.pk],
                    )
                    row = cursor.fetchone()
                    result = {"available": True, "value": row[0] if row else None, "error": None}
                # Recheck epoch/connection/actor before retaining successful raw
                # reads. An error never enters either request-owned entry.
                if (cache is not None
                        and FormalManufacturingEligibilityService._database_read_cache(order, cache) is cache
                        and cache._write_epoch == scope[-1]):
                    cache[columns_key] = columns
                    cache[value_key] = (result["available"], result["value"])
                return result
        except DatabaseError as exc:
            return {
                "available": None,
                "value": None,
                "error": type(exc).__name__,
            }

    @classmethod
    def _order_from_source(cls, source: Any) -> tuple[SalesOrder | None, dict[str, Any]]:
        trace = {
            "sourceType": type(source).__name__ if source is not None else None,
            "sourceId": getattr(source, "pk", None),
            "orderEngineeringInstanceId": None,
            "salesOrderItemId": None,
            "path": None,
        }
        if source is None:
            return None, trace
        if isinstance(source, SalesOrder):
            trace["path"] = "SalesOrder"
            return source, trace
        if isinstance(source, SalesOrderItem):
            trace.update({"salesOrderItemId": source.pk, "path": "SalesOrderItem→SalesOrder"})
            return source.sales_order, trace

        instance = None
        if isinstance(source, OrderEngineeringInstance):
            instance = source
            trace["path"] = "OrderEngineeringInstance→SalesOrderItem→SalesOrder"
        elif isinstance(source, ProductBOM):
            instance = source.order_engineering_instance if source.order_engineering_instance_id else None
            trace["path"] = "ProductBOM→OEI→SalesOrderItem→SalesOrder"
        elif isinstance(source, BOMVersion):
            instance = source.order_engineering_instance if source.order_engineering_instance_id else None
            if instance is None and source.bom_id and source.bom.order_engineering_instance_id:
                instance = source.bom.order_engineering_instance
            trace["path"] = "BOMVersion→ProductBOM/OEI→SalesOrderItem→SalesOrder"
        elif isinstance(source, ProductManufacturingOutput):
            instance = source.order_engineering_instance if source.order_engineering_instance_id else None
            if instance is None and source.bom_version_id:
                bom_version = source.bom_version
                instance = (
                    bom_version.order_engineering_instance
                    if bom_version.order_engineering_instance_id else None
                )
            trace["path"] = "ManufacturingOutput→OEI/BOMVersion→SalesOrderItem→SalesOrder"
        elif isinstance(source, EngineeringCalculationRecord):
            instance = source.engineering_instance
            trace["path"] = "Calculation→OEI→SalesOrderItem→SalesOrder"

        if instance is None:
            return None, trace
        item = instance.sales_order_item
        trace.update({
            "orderEngineeringInstanceId": instance.pk,
            "salesOrderItemId": item.pk,
        })
        return item.sales_order, trace

    @classmethod
    def _purpose_evidence(cls, order: SalesOrder, read_cache: Any = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        delivery = order.delivery_information if isinstance(order.delivery_information, dict) else {}
        contract = delivery.get("developmentContract")
        contract = contract if isinstance(contract, dict) else {}
        database = (cls._database_purpose(order, read_cache=read_cache) if read_cache is not None
            else cls._database_purpose(order)) if order.pk else {
            "available": False, "value": None, "error": None,
        }
        candidates: list[dict[str, Any]] = []

        def add(source: str, raw: Any, normalized: str | None = None) -> None:
            purpose = normalized or cls._normalize_purpose(raw)
            if purpose:
                candidates.append({"source": source, "raw": raw, "purpose": purpose})

        add("sales_order.business_purpose", database.get("value"))
        add("delivery_information.businessPurpose", delivery.get("businessPurpose"))
        add("developmentContract.purpose", contract.get("purpose"))
        if order.acceptance_marker == "DEVELOPMENT_ONLY":
            add("sales_order.acceptance_marker", order.acceptance_marker, cls.DEVELOPMENT_VALIDATION)
        if delivery.get("developmentOnly") is True:
            add("delivery_information.developmentOnly", True, cls.DEVELOPMENT_VALIDATION)

        evidence = {
            "databaseBusinessPurpose": database,
            "acceptanceMarker": order.acceptance_marker or None,
            "deliveryBusinessPurpose": delivery.get("businessPurpose"),
            "developmentOnly": delivery.get("developmentOnly"),
            "contractPurpose": contract.get("purpose"),
            "contractReference": order.contract_reference or None,
            "purposeCandidates": candidates,
        }
        return candidates, evidence

    @classmethod
    def resolve(cls, source: Any, read_cache: Any = None) -> dict[str, Any]:
        from .bom_usage_contract import is_test_source
        if is_test_source(source):
            return {"orderId": None, "orderNo": None, "businessPurposeCode": "TEST_BUSINESS",
                    "businessPurposeLabel": "测试业务", "orderTraceUnique": True,
                    "formalManufacturingEligible": False, "decisionCode": "TEST_BUSINESS_PRODUCTION_DENIED",
                    "statusLabel": "测试业务：禁止正式评审、发布及生产消费", "message": "测试BOM仅允许草稿与只读验证。", "evidence": {"purposeSource": "persistent_bom_lineage"}}
        if isinstance(source,(ProductBOM,BOMVersion)) and source.usage_purpose == 'UNCLASSIFIED':
            return {"orderId":None,"orderNo":None,"businessPurposeCode":"UNKNOWN","businessPurposeLabel":"历史用途待核定",
                    "orderTraceUnique":False,"formalManufacturingEligible":False,"decisionCode":"BOM_USAGE_UNCLASSIFIED",
                    "statusLabel":"用途依据不足，禁止正式生产消费","message":"保留历史记录只读；补齐可信来源前不允许正式评审、发布及生产消费。","evidence":{"purposeSource":"persistent_bom_lineage"}}
        order, trace = cls._order_from_source(source)
        if order is None:
            return {
                "orderId": None,
                "orderNo": None,
                "businessPurposeCode": cls.UNKNOWN,
                "businessPurposeLabel": cls.PURPOSE_LABELS[cls.UNKNOWN],
                "orderTraceUnique": False,
                "formalManufacturingEligible": False,
                "decisionCode": "FORMAL_MANUFACTURING_ORDER_TRACE_BROKEN",
                "statusLabel": "正式制造资格已阻断",
                "message": "无法沿正式关系唯一追溯销售订单，已按Fail Closed拒绝正式制造动作。",
                "evidence": {"orderTrace": trace, "purposeCandidates": []},
            }

        candidates, purpose_evidence = (cls._purpose_evidence(order, read_cache=read_cache)
            if read_cache is not None else cls._purpose_evidence(order))
        purposes = sorted({candidate["purpose"] for candidate in candidates})
        common = {
            "orderId": order.pk,
            "orderNo": order.order_no,
            "orderTraceUnique": True,
            "evidence": {"orderTrace": trace, **purpose_evidence},
        }
        if len(purposes) > 1:
            return {
                **common,
                "businessPurposeCode": cls.UNKNOWN,
                "businessPurposeLabel": cls.PURPOSE_LABELS[cls.UNKNOWN],
                "formalManufacturingEligible": False,
                "decisionCode": "BUSINESS_PURPOSE_EVIDENCE_CONFLICT",
                "statusLabel": "订单用途证据冲突，正式制造资格已阻断",
                "message": "订单用途持久证据互相冲突，已按Fail Closed拒绝正式制造动作。",
            }
        if not purposes:
            return {
                **common,
                "businessPurposeCode": cls.UNKNOWN,
                "businessPurposeLabel": cls.PURPOSE_LABELS[cls.UNKNOWN],
                "formalManufacturingEligible": False,
                "decisionCode": "BUSINESS_PURPOSE_EVIDENCE_MISSING",
                "statusLabel": "订单用途证据缺失，正式制造资格已阻断",
                "message": "无法证明订单为正式销售用途，已按Fail Closed拒绝正式制造动作。",
            }

        purpose = purposes[0]
        if purpose == cls.DEVELOPMENT_VALIDATION:
            return {
                **common,
                "businessPurposeCode": purpose,
                "businessPurposeLabel": cls.PURPOSE_LABELS[purpose],
                "formalManufacturingEligible": False,
                "decisionCode": "DEVELOPMENT_VALIDATION_FORMAL_MANUFACTURING_FORBIDDEN",
                "statusLabel": "开发验证订单：禁止正式制造评审与发布",
                "message": cls.DEVELOPMENT_MESSAGE,
            }
        return {
            **common,
            "businessPurposeCode": purpose,
            "businessPurposeLabel": cls.PURPOSE_LABELS[purpose],
            "formalManufacturingEligible": True,
            "decisionCode": "FORMAL_MANUFACTURING_ELIGIBLE",
            "statusLabel": "正式销售用途资格已确认",
            "message": "订单用途允许继续执行原有正式制造门禁；本结论不替代权限、版本或完整性校验。",
        }

