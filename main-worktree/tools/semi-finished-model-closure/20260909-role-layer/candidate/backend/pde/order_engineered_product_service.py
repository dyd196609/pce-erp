"""Pre-release order-engineering checks; never a formal MRP/cost/procurement source."""

from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    ComponentMaterialRequirement, OrderConfiguredProduct, OrderProductComponent,
)


class OrderEngineeredProductService:
    FORMAL_DOWNSTREAM_GATE = "NOT_YET_RELEASE_INTEGRATED"

    @staticmethod
    def effective_component_order_quantity(component, memo=None):
        """Resolve a node quantity from the root with explicit mixed-basis semantics."""
        memo = memo if memo is not None else {}
        if component.pk in memo:
            return memo[component.pk]
        if component.quantity_basis == "UNKNOWN":
            memo[component.pk] = None
            return None
        if component.quantity_basis == "ORDER_TOTAL" or component.parent_id is None:
            result = component.quantity
        else:
            parent_quantity = OrderEngineeredProductService.effective_component_order_quantity(
                component.parent, memo,
            )
            result = None if parent_quantity is None else parent_quantity * component.quantity
        memo[component.pk] = result
        return result

    @staticmethod
    def engineering_material_preview(order_product):
        """Return a derived engineering preview; unresolved facts remain excluded and visible."""
        if not isinstance(order_product, OrderConfiguredProduct):
            order_product = OrderConfiguredProduct.objects.get(pk=order_product)
        totals = defaultdict(Decimal)
        unresolved = []
        memo = {}
        lines = ComponentMaterialRequirement.objects.select_related(
            "component__parent__parent__parent", "material__base_uom", "uom"
        ).filter(component__order_product=order_product, is_active=True)
        for line in lines:
            component = line.component
            base_quantity = line.normalized_base_quantity
            blockers = []
            if component.quantity_basis == "UNKNOWN":
                blockers.append("COMPONENT_QUANTITY_BASIS_UNKNOWN")
            if component.uom_status != "confirmed" or not component.uom_id:
                blockers.append("COMPONENT_UOM_NOT_CONFIRMED")
            if component.supply_strategy == "UNKNOWN":
                blockers.append("COMPONENT_SUPPLY_STRATEGY_UNKNOWN")
            if line.quantity_basis == "UNKNOWN":
                blockers.append("REQUIREMENT_QUANTITY_BASIS_UNKNOWN")
            if line.identity_status != "resolved" or not line.material_id:
                blockers.append("MATERIAL_IDENTITY_UNRESOLVED")
            if base_quantity is None:
                blockers.append("REQUIREMENT_UOM_NOT_NORMALIZED")
            if line.supply_strategy == "UNKNOWN":
                blockers.append("REQUIREMENT_SUPPLY_STRATEGY_UNKNOWN")
            if blockers:
                unresolved.append({
                    "requirementId": line.pk,
                    "componentId": component.pk,
                    "materialId": line.material_id,
                    "unresolvedRequirement": line.unresolved_requirement,
                    "blockers": blockers,
                })
                continue
            quantity = base_quantity if line.quantity_basis == "ORDER_TOTAL" else (
                OrderEngineeredProductService.effective_component_order_quantity(
                    component, memo,
                ) * base_quantity
            )
            totals[(line.material_id, line.material.base_uom_id)] += quantity
        return {"readyLines": [
            {
                "materialId": material_id,
                "uomId": uom_id,
                "quantity": quantity,
                "source": "ComponentMaterialRequirement",
                "projectionClass": "PRE_RELEASE_ENGINEERING_PREVIEW",
            }
            for (material_id, uom_id), quantity in sorted(totals.items())
        ], "unresolvedLines": unresolved, "formalDownstreamGate": OrderEngineeredProductService.FORMAL_DOWNSTREAM_GATE}

    @staticmethod
    def structure(order_product):
        if not isinstance(order_product, OrderConfiguredProduct):
            order_product = OrderConfiguredProduct.objects.get(pk=order_product)
        return {
            "orderProductId": order_product.pk,
            "salesOrderId": order_product.sales_order_id,
            "definitionMode": order_product.definition_mode,
            "preReleaseStatus": order_product.status,
            "templateId": order_product.template_id,
            "contexts": list(order_product.installation_contexts.values(
                "id", "context_code", "raw_source_value", "normalized_display_value",
            )),
            "components": list(order_product.components.values(
                "id", "parent_id", "installation_context_id", "component_code",
                "component_name", "component_type", "quantity", "quantity_basis",
                "uom_id", "uom_status", "supply_strategy", "source_lineage",
                "template_node_id", "status",
            )),
            "engineeringMaterialPreview": OrderEngineeredProductService.engineering_material_preview(order_product),
            "releaseBoundary": "ProductManufacturingOutput",
            "formalDownstreamGate": OrderEngineeredProductService.FORMAL_DOWNSTREAM_GATE,
        }

    @staticmethod
    @transaction.atomic
    def instantiate_template(order_product, node_configurations):
        """Create isolated order facts from structural slots and explicit order inputs."""
        if not isinstance(order_product, OrderConfiguredProduct):
            order_product = OrderConfiguredProduct.objects.select_for_update().get(pk=order_product)
        if order_product.definition_mode != "template_assisted":
            raise ValidationError({"definition_mode": "只有模板辅助订单可以实例化结构模板"})
        if not order_product.template_id or not order_product.configuration_id:
            raise ValidationError({"configuration": "实例化前必须锁定模板与配置快照"})
        if order_product.components.exists():
            raise ValidationError({"components": "订单工程结构只能从模板实例化一次"})

        requested = {str(row["nodeCode"]): row for row in node_configurations}
        nodes = list(order_product.template.structure_nodes.filter(is_active=True).select_related("parent"))
        by_node_id = {}
        created = []
        pending = {node.pk: node for node in nodes}
        while pending:
            progressed = False
            for node_id, node in list(pending.items()):
                if node.parent_id and node.parent_id not in by_node_id:
                    continue
                values = requested.get(node.node_code)
                if values is None:
                    if node.slot_requirement == "required":
                        raise ValidationError({"node_configurations": f"必需结构槽位未配置：{node.node_code}"})
                    del pending[node_id]
                    progressed = True
                    continue
                required = ("componentCode", "componentName", "quantity", "quantityBasis")
                missing = [key for key in required if values.get(key) in (None, "")]
                if missing:
                    raise ValidationError({"node_configurations": f"{node.node_code}缺少显式订单事实：{', '.join(missing)}"})
                component = OrderProductComponent(
                    order_product=order_product,
                    installation_context_id=values.get("installationContextId"),
                    parent=by_node_id.get(node.parent_id),
                    template_node=node,
                    component_code=values["componentCode"],
                    component_name=values["componentName"],
                    component_type=values.get("componentType") or node.component_type,
                    dimensions=values.get("dimensions") or {},
                    quantity=Decimal(str(values["quantity"])),
                    quantity_basis=values["quantityBasis"],
                    uom_id=values.get("uomId"),
                    uom_status=values.get("uomStatus") or "not_confirmed",
                    supply_strategy=values.get("supplyStrategy") or "UNKNOWN",
                    process_attributes=values.get("processAttributes") or {},
                    finish_attributes=values.get("finishAttributes") or {},
                    source_lineage={
                        **(values.get("sourceLineage") or {}),
                        "instantiatedFromTemplateId": order_product.template_id,
                        "instantiatedFromTemplateNodeId": node.pk,
                        "configurationId": order_product.configuration_id,
                    },
                )
                component.full_clean()
                component.save()
                by_node_id[node.pk] = component
                created.append(component)
                del pending[node_id]
                progressed = True
            if not progressed:
                raise ValidationError({"template": "模板槽位层级存在循环或缺失上级"})
        return created

    @staticmethod
    @transaction.atomic
    def resolve_material_identity(requirement, *, material, resolver, decision):
        """Resolve the same requirement row so structure, quantity and lineage stay intact."""
        requirement_id = requirement.pk if isinstance(requirement, ComponentMaterialRequirement) else requirement
        row = ComponentMaterialRequirement.objects.select_for_update().select_related(
            "component__order_product", "uom", "material",
        ).get(pk=requirement_id)
        if row.identity_status != "unresolved" or row.material_id:
            raise ValidationError({"identity_status": "只有未决物料身份需求可以执行解析"})
        if material.company_id != row.component.order_product.company_id:
            raise ValidationError({"material": "解析后的正式物料必须属于订单构件所在公司"})
        if not decision:
            raise ValidationError({"decision": "物料身份解析必须保存正式决策证据"})
        row.material = material
        row.identity_status = "resolved"
        row.identity_resolution_decision = dict(decision)
        row.resolved_by = resolver
        row.resolved_at = timezone.now()
        row.full_clean()
        row.save(update_fields=(
            "material", "identity_status", "identity_resolution_decision",
            "resolved_by", "resolved_at", "updated_at",
        ))
        return row
