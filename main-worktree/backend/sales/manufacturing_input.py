"""Read-only Demand consumer of the formal order-engineering release contract.

Release subject, not a fabricated long-term product or a legacy item backwrite,
determines the engineering identity. No source object or workflow is changed.
"""
from django.core.exceptions import ValidationError

from pde.models import ProductManufacturingOutput
from pde.manufacturing_output_generation_service import (
    ManufacturingOutputError, validate_selected_output,
)

ORDER_ENGINEERED_PRODUCT = "ORDER_ENGINEERED_PRODUCT"
LONG_TERM_PRODUCT = "LONG_TERM_PRODUCT"


class ManufacturingInputError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code, self.message = code, message
        self.details = details or {}


def is_order_engineered_product(item):
    # Legacy ORDER_ENGINEERED + a real ProductDefinition remains the long-term
    # release-subject path. The two existing model vocabularies are not renamed.
    return bool(
        (item.engineering_mode == "ORDER_ENGINEERED" and not item.product_definition_id)
        or (item.manufacturing_output_id and
            item.manufacturing_output.release_subject_type == ORDER_ENGINEERED_PRODUCT)
    )


def resolve_order_engineered_input(item, *, output_id=None):
    """Read a persisted reference or an explicitly selected complete version."""
    try:
        item.full_clean()
        if item.engineering_mode != "ORDER_ENGINEERED" or item.product_definition_id or item.product_version_id:
            raise ManufacturingInputError("ORDER_ENGINEERING_IDENTITY_CONFLICT", "订单工程制造输入不得混入长期产品身份。")
        explicit = output_id is not None
        if explicit and (type(output_id) is not int or output_id <= 0):
            raise ManufacturingInputError("ORDER_ENGINEERING_OUTPUT_SELECTION_INVALID", "必须明确选择有效的正式制造输出编号。")
        outputs = ProductManufacturingOutput.objects.filter(
            order_engineering_instance__sales_order_item_id=item.pk,
            order_engineering_instance__company_id=item.sales_order.company_id,
            release_subject_type=ORDER_ENGINEERED_PRODUCT,
        ).select_related("order_engineering_instance__sales_order_item__sales_order",
            "bom_version", "routing_version", "engineering_document_version")
        if output_id is not None:
            outputs = outputs.filter(pk=output_id)
        candidates = list(outputs[:2])
        if len(candidates) != 1:
            raise ManufacturingInputError(
                "ORDER_ENGINEERING_OUTPUT_NOT_UNIQUE", "请明确选择属于该订单行的正式制造输出版本。",
                {"selectionRequired": len(candidates) > 1,
                 "manufacturingOutputIds": [candidate.pk for candidate in candidates]},
            )
        output = candidates[0]
        from planning.models import Demand
        historical = Demand.objects.filter(
            sales_order_item_id=item.pk, manufacturing_output_id=output.pk,
        ).exists()
        proof = validate_selected_output(output)
        instance, document = proof["instance"], proof["document"]
        # These defaults remain an integrity check for an unpinned new request.
        # An existing Demand or explicit version has its own immutable source.
        if not explicit and not historical:
            if item.manufacturing_output_id and item.manufacturing_output_id != output.pk:
                raise ManufacturingInputError("ORDER_ENGINEERING_ITEM_OUTPUT_CONFLICT", "订单行制造输出默认引用与正式来源链冲突。")
            if item.engineering_document_version_id and item.engineering_document_version_id != document.pk:
                raise ManufacturingInputError("ORDER_ENGINEERING_ITEM_DOCUMENT_CONFLICT", "订单行工程资料默认引用与制造输出来源冲突。")
        return {"output": output, "facts": {
            "definitionMode": ORDER_ENGINEERED_PRODUCT,
            "sourceAuthority": "SalesOrderItem -> OrderEngineeringInstance -> ProductManufacturingOutput",
            "salesOrderItemId": item.pk, "orderEngineeringInstanceId": instance.pk,
            "orderEngineeringBaselineId": output.order_engineering_baseline_id,
            "engineeringCalculationId": output.engineering_calculation_id,
            "engineeringDocumentVersionId": document.pk,
            "manufacturingOutputId": output.pk, "bomVersionId": output.bom_version_id,
            "routingVersionId": output.routing_version_id,
            "outputRevision": output.revision, "predecessorOutputId": output.predecessor_id,
            "engineeringInstanceStatus": instance.status,
            "baselineStatus": document.order_engineering_baseline.status,
            "calculationStatus": document.engineering_calculation.status,
            "documentStatus": document.status, "bomStatus": output.bom_version.status,
            "routingStatus": output.routing_version.status, "outputStatus": output.release_status,
            "sourceFingerprint": proof["sourceFingerprint"],
            "sourceSnapshot": proof["sourceFields"],
            "generationReadback": proof["generationReadback"],
            "releaseReadback": proof["releaseReadback"], "sourceConsistent": True,
            "businessWriteCount": 0,
        }}
    except ManufacturingOutputError as exc:
        raise ManufacturingInputError(exc.code, exc.message) from exc
    except ValidationError as exc:
        raise ManufacturingInputError("ORDER_ENGINEERING_INPUT_INVALID", f"订单工程制造输入关系校验失败：{exc}") from exc
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        raise ManufacturingInputError("ORDER_ENGINEERING_RELEASE_FACT_INVALID", "订单工程发布证据格式不完整或无效。") from exc


def resolve_demand_manufacturing_input(item, *, supply_branch="MAKE", output_id=None):
    if is_order_engineered_product(item) and supply_branch == "MAKE":
        return resolve_order_engineered_input(item, output_id=output_id)
    if is_order_engineered_product(item) and supply_branch == "BUY":
        if output_id is not None:
            raise ManufacturingInputError("ORDER_ENGINEERING_OUTPUT_SELECTION_INVALID", "外购承接不得指定制造输出来源。")
        return {"output": None, "facts": {
            "definitionMode": "NOT_APPLICABLE", "sourceAuthority": "OrderLineSupplyAdmission:BUY",
            "manufacturingOutputId": None,
        }}
    if output_id is not None and (type(output_id) is not int or output_id != item.manufacturing_output_id):
        raise ManufacturingInputError("ORDER_ENGINEERING_OUTPUT_SELECTION_INVALID", "所选制造输出与正式产品订单行来源不一致。")
    return {"output": item.manufacturing_output, "facts": {
        "definitionMode": LONG_TERM_PRODUCT,
        "sourceAuthority": "SalesOrderItem.manufacturing_output",
        "manufacturingOutputId": item.manufacturing_output_id,
    }}
