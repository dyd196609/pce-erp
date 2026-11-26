"""A1 production master-data service boundary.

Requirement trace: PCM-MD-002/003/006, PCM-MRP-001, PCM-MES-007/013,
PCM-XMOD-002/007/008 and Production Foundation A-02..A-09/A-17/A-21/A-22.
"""

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Case, IntegerField, Max, Prefetch, Value, When
from django.utils import timezone
from django.utils.dateparse import parse_date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json

from masterdata.models import (
    CodeRule, ExternalIdentity, MasterDataWriteRequest, Material, MaterialCategory,
    UnitOfMeasure,
)
from masterdata.material_identity import (
    canonical_identity, canonical_material_readback, matching_materials,
    normalize_identity_text,
)
from procurement.models import InventoryLot, Warehouse, WarehouseLocation
from procurement.models import Supplier
from pfm.models import Employee
from sales.models import Customer
from system.authorization import AuthorizationService
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, PositionResponsibility,
    Process, ProcessTeamCapability, Team, TeamMembership, Workshop,
)

from .models import (
    BOMItem,
    BOMCompletenessRule,
    BOMItemRoutingAssignment,
    BOMItemSubstitute,
    BOMVersion,
    EngineeringBreakdownItem,
    EngineeringCalculationRecord,
    EngineeringDerivedFact,
    EngineeringDocument,
    EngineeringDocumentVersion,
    EngineeringBreakdownOption,
    EngineeringRuleDefinition,
    EngineeringSourceRecord,
    Equipment,
    ConfiguredProduct,
    CapacityProductType,
    ManufacturingInputReference,
    ManufacturingProcessType,
    OrderEngineeringInstance,
    PDEEngineeringPreparationAuthorization,
    ProductBOM,
    ProductCategory,
    ProductConfiguration,
    ProductDefinition,
    ProductTemplate,
    ProductVersion,
    ProductEngineeringReadiness,
    ProductManufacturingOutput,
    Routing,
    RoutingStep,
    RoutingVersion,
    StandardCapacity,
    WorkCenter,
    WorkCenterOperationCapability,
    WorkCenterTeamAssignment,
)
from .engineering_rule_foundation import (
    EngineeringRuleError,
    expression_hash,
    specification_hash,
    validate_specification,
)
from .formal_manufacturing_eligibility_service import FormalManufacturingEligibilityService


class ProductionFoundationError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


ENTITY_CONFIG = {
    "customers": (Customer, "masterdata.customer.maintain"),
    "suppliers": (Supplier, "masterdata.supplier.maintain"),
    "units": (UnitOfMeasure, "production.master_data.unit.maintain"),
    "material-categories": (
        MaterialCategory, "production.master_data.material.maintain",
    ),
    "materials": (Material, "production.master_data.material.maintain"),
    "product-categories": (ProductCategory, "production.master_data.product.maintain"),
    "manufacturing-process-types": (
        ManufacturingProcessType, "production.master_data.routing.maintain",
    ),
    "engineering-breakdown-options": (
        EngineeringBreakdownOption, "production.master_data.product.maintain",
    ),
    "product-templates": (ProductTemplate, "production.master_data.product.maintain"),
    "product-configurations": (ProductConfiguration, "production.master_data.product.maintain"),
    "configured-products": (ConfiguredProduct, "production.master_data.product.maintain"),
    "products": (ProductDefinition, "production.master_data.product.maintain"),
    "product-versions": (ProductVersion, "production.engineering.version.maintain"),
    "workshops": (Workshop, "production.master_data.resource.maintain"),
    "teams": (Team, "production.master_data.resource.maintain"),
    "operation-team-capabilities": (
        ProcessTeamCapability, "production.master_data.resource.maintain",
    ),
    "team-memberships": (TeamMembership, "production.master_data.resource.maintain"),
    "team-membership-employees": (Employee, "system.organization_directory.view"),
    "team-departments": (Department, "system.organization_directory.view"),
    "work-centers": (WorkCenter, "production.master_data.resource.maintain"),
    "operations": (Process, "production.master_data.resource.maintain"),
    "work-center-operation-capabilities": (
        WorkCenterOperationCapability, "production.master_data.resource.maintain",
    ),
    "work-center-team-assignments": (
        WorkCenterTeamAssignment, "production.master_data.resource.maintain",
    ),
    "equipment": (Equipment, "production.master_data.resource.maintain"),
    "standard-capacities": (StandardCapacity, "production.master_data.capacity.maintain"),
    "capacity-product-types": (CapacityProductType, "production.master_data.capacity.maintain"),
    "boms": (ProductBOM, "production.master_data.bom.maintain"),
    "bom-versions": (BOMVersion, "production.master_data.bom.maintain"),
    "bom-items": (BOMItem, "production.master_data.bom.maintain"),
    "bom-substitutes": (BOMItemSubstitute, "production.master_data.bom.maintain"),
    "bom-completeness-rules": (BOMCompletenessRule, "production.master_data.bom.maintain"),
    "bom-routing-assignments": (BOMItemRoutingAssignment, "production.master_data.routing.maintain"),
    "routings": (Routing, "production.master_data.routing.maintain"),
    "routing-versions": (RoutingVersion, "production.master_data.routing.maintain"),
    "routing-steps": (RoutingStep, "production.master_data.routing.maintain"),
    "engineering-documents": (
        EngineeringDocument, "production.engineering.document.maintain",
    ),
    "engineering-document-versions": (
        EngineeringDocumentVersion, "production.engineering.document.maintain",
    ),
    "manufacturing-outputs": (
        ProductManufacturingOutput, "production.engineering.release",
    ),
    "engineering-readiness": (
        ProductEngineeringReadiness, "production.engineering.readiness.maintain",
    ),
    "manufacturing-input-references": (
        ManufacturingInputReference, "production.engineering.release",
    ),
    "engineering-source-records": (
        EngineeringSourceRecord, "production.engineering.source.maintain",
    ),
    "engineering-rule-definitions": (
        EngineeringRuleDefinition, "production.engineering.rule.maintain",
    ),
    "order-engineering-instances": (
        OrderEngineeringInstance, "production.engineering.order.maintain",
    ),
    "engineering-calculation-records": (
        EngineeringCalculationRecord, "production.engineering.calculation.record",
    ),
    "engineering-breakdown-items": (
        EngineeringBreakdownItem, "production.engineering.calculation.record",
    ),
    "engineering-derived-facts": (
        EngineeringDerivedFact, "production.engineering.calculation.record",
    ),
    "warehouses": (Warehouse, "production.master_data.location.maintain"),
    "warehouse-locations": (WarehouseLocation, "production.master_data.location.maintain"),
    "inventory-lots": (InventoryLot, "production.master_data.location.maintain"),
}

ENTITY_CODE_FIELDS = {
    "materials": ("code", "production_material"),
    "product-categories": ("code", "production_product_category"),
    "manufacturing-process-types": ("code", "production_process_type"),
    "products": ("product_code", "production_product"),
    "product-templates": ("template_code", "production_product_template"),
    "work-centers": ("code", "production_work_center"),
    "operations": ("code", "production_operation"),
    "workshops": ("code", "production_workshop"),
    "equipment": ("code", "production_equipment"),
    "standard-capacities": ("code", "production_standard_capacity"),
    "boms": ("bom_code", "production_bom"),
    "routings": ("routing_code", "production_routing"),
    "warehouse-locations": ("code", "warehouse_location"),
    "inventory-lots": ("lot_no", "inventory_lot"),
    "engineering-source-records": ("source_no", "production_engineering_source"),
    "order-engineering-instances": ("instance_no", "production_order_engineering"),
}


INITIAL_VERSION_FIELDS = {
    "product-versions": ("version_no", "product_id", ProductVersion),
    "bom-versions": ("bom_version", "bom_id", BOMVersion),
    "routing-versions": ("routing_version", "routing_id", RoutingVersion),
    "engineering-document-versions": (
        "document_version", "document_id", EngineeringDocumentVersion,
    ),
}


FK_CONFIG = {
    "company_id": Company,
    "parent_id": ProductCategory,
    "category_id": ProductCategory,
    "product_category_id": ProductCategory,
    "manufacturing_process_type_id": ManufacturingProcessType,
    "product_type_id": CapacityProductType,
    "selected_process_type_id": ManufacturingProcessType,
    "template_id": ProductTemplate,
    "configuration_id": ProductConfiguration,
    "product_definition_id": ProductDefinition,
    "material_id": Material,
    "department_id": Department,
    "workshop_id": Workshop,
    "work_center_id": WorkCenter,
    "equipment_id": Equipment,
    "team_id": Team,
    "employee_id": Employee,
    "product_id": ProductDefinition,
    "product_bom_id": ProductBOM,
    "product_version_id": ProductVersion,
    "bom_id": ProductBOM,
    "bom_version_id": BOMVersion,
    "uom_id": UnitOfMeasure,
    "bom_item_id": BOMItem,
    "parent_item_id": BOMItem,
    "applies_to_item_id": BOMItem,
    "substitute_material_id": Material,
    "routing_id": Routing,
    "routing_version_id": RoutingVersion,
    "operation_id": Process,
    "warehouse_id": Warehouse,
    "document_id": EngineeringDocument,
    "related_product_id": ProductDefinition,
    "related_bom_id": BOMVersion,
    "related_routing_id": RoutingVersion,
    "engineering_document_version_id": EngineeringDocumentVersion,
    "source_manufacturing_output_id": ProductManufacturingOutput,
    "source_record_id": EngineeringSourceRecord,
    "baseline_product_version_id": ProductVersion,
    "order_engineering_instance_id": OrderEngineeringInstance,
    "engineering_instance_id": OrderEngineeringInstance,
    "engineering_preparation_authorization_id": PDEEngineeringPreparationAuthorization,
    "calculation_id": EngineeringCalculationRecord,
    "breakdown_item_id": EngineeringBreakdownItem,
    "rule_id": EngineeringRuleDefinition,
}

FK_ENTITY_OVERRIDES = {
    ("units", "conversion_base_id"): UnitOfMeasure,
    ("material-categories", "parent_id"): MaterialCategory,
    ("materials", "category_id"): MaterialCategory,
    ("materials", "base_uom_id"): UnitOfMeasure,
    ("materials", "purchase_uom_id"): UnitOfMeasure,
    ("engineering-breakdown-items", "parent_id"): EngineeringBreakdownItem,
    ("bom-items", "parent_id"): BOMItem,
    ("order-engineering-instances", "sales_order_item_id"): "sales.SalesOrderItem",
}


ENTITY_READ_ONLY_FIELDS = {
    # WorkCenter owns an independent formal number allocated by CodeRule on
    # CREATE.  Clients may keep sending ``code`` for legacy compatibility, but
    # it is never authoritative and cannot be changed by ordinary maintenance.
    "work-centers": {"code"},
    # Archived hourly values and version-hash compatibility are immutable.
    "standard-capacities": {"standard_hours"},
    "operations": {"standard_hours", "workload_source_selection"},
    "routing-steps": {"standard_hours", "setup_hours", "transfer_hours", "preparation_days", "transfer_days"},
    "products": {"version"},
    "product-templates": {"status"},
    "product-configurations": {"status"},
    "configured-products": {"status"},
    "product-versions": {"version_status"},
    "bom-versions": {"status"},
    "routing-versions": {"status"},
    "engineering-document-versions": {"status"},
    "manufacturing-outputs": {"release_status"},
    "engineering-source-records": {"status"},
    "engineering-rule-definitions": {"status"},
    "order-engineering-instances": {"status"},
    "engineering-calculation-records": {"status"},
    "engineering-readiness": {"order_no"},
}


def _organization_id(model, values, instance=None):
    if values.get("company_id"):
        return values["company_id"]
    if values.get("organization_id"):
        return values["organization_id"]
    if values.get("work_center_id"):
        return WorkCenter.objects.only("company_id").get(pk=values["work_center_id"]).company_id
    if values.get("team_id"):
        return Team.objects.only("company_id").get(pk=values["team_id"]).company_id
    if values.get("operation_id"):
        return Process.objects.only("company_id").get(pk=values["operation_id"]).company_id
    if values.get("routing_id"):
        return Routing.objects.only("company_id").get(pk=values["routing_id"]).company_id
    if values.get("bom_id"):
        return ProductBOM.objects.only("company_id").get(pk=values["bom_id"]).company_id
    if values.get("product_id"):
        return ProductDefinition.objects.only("company_id").get(pk=values["product_id"]).company_id
    if values.get("template_id"):
        return ProductTemplate.objects.only("company_id").get(pk=values["template_id"]).company_id
    if values.get("configuration_id"):
        return ProductConfiguration.objects.select_related("template").get(
            pk=values["configuration_id"]
        ).template.company_id
    if values.get("bom_version_id"):
        return BOMVersion.objects.select_related("bom", "product").get(pk=values["bom_version_id"]).bom.company_id
    if values.get("routing_version_id"):
        return RoutingVersion.objects.select_related("routing", "product").get(pk=values["routing_version_id"]).routing.company_id
    if values.get("bom_item_id"):
        return BOMItem.objects.select_related("bom_version__bom").get(pk=values["bom_item_id"]).bom_version.bom.company_id
    if values.get("parent_item_id"):
        return BOMItem.objects.select_related("bom_version__bom").get(
            pk=values["parent_item_id"]
        ).bom_version.bom.company_id
    if values.get("warehouse_id"):
        return Warehouse.objects.only("company_id").get(pk=values["warehouse_id"]).company_id
    if values.get("product_version_id"):
        return ProductVersion.objects.select_related("product").get(pk=values["product_version_id"]).product.company_id
    if values.get("engineering_document_version_id"):
        document_version = EngineeringDocumentVersion.objects.select_related(
            "related_product", "order_engineering_instance",
        ).get(pk=values["engineering_document_version_id"])
        return (
            document_version.related_product.company_id
            if document_version.related_product_id
            else document_version.order_engineering_instance.company_id
        )
    if values.get("source_manufacturing_output_id"):
        output = ProductManufacturingOutput.objects.select_related(
            "product", "order_engineering_instance",
        ).get(pk=values["source_manufacturing_output_id"])
        return (
            output.product.company_id
            if output.product_id else output.order_engineering_instance.company_id
        )
    if values.get("order_engineering_instance_id"):
        return OrderEngineeringInstance.objects.only("company_id").get(
            pk=values["order_engineering_instance_id"]
        ).company_id
    if values.get("engineering_instance_id"):
        return OrderEngineeringInstance.objects.only("company_id").get(
            pk=values["engineering_instance_id"]
        ).company_id
    if values.get("calculation_id"):
        return EngineeringCalculationRecord.objects.select_related(
            "engineering_instance"
        ).get(pk=values["calculation_id"]).engineering_instance.company_id
    if values.get("breakdown_item_id"):
        return EngineeringBreakdownItem.objects.select_related(
            "calculation__engineering_instance"
        ).get(pk=values["breakdown_item_id"]).calculation.engineering_instance.company_id
    if values.get("related_product_id"):
        return ProductDefinition.objects.only("company_id").get(pk=values["related_product_id"]).company_id
    if values.get("material_id"):
        return Material.objects.only("company_id").get(pk=values["material_id"]).company_id
    source = instance
    if source is not None:
        if getattr(source, "company_id", None):
            return source.company_id
        if getattr(source, "work_center_id", None):
            return source.work_center.company_id
        if getattr(source, "team_id", None):
            return source.team.company_id
        if getattr(source, "operation_id", None):
            return source.operation.company_id
        if getattr(source, "product_id", None):
            return source.product.company_id
        if getattr(source, "routing_id", None):
            return source.routing.company_id
        if getattr(source, "bom_id", None):
            return source.bom.company_id
        if getattr(source, "template_id", None):
            return source.template.company_id
        if getattr(source, "configuration_id", None):
            return source.configuration.template.company_id
        if getattr(source, "related_product_id", None):
            return source.related_product.company_id
        if getattr(source, "source_manufacturing_output_id", None):
            output = source.source_manufacturing_output
            return (
                output.product.company_id
                if output.product_id else output.order_engineering_instance.company_id
            )
        if getattr(source, "order_engineering_instance_id", None):
            return source.order_engineering_instance.company_id
        if getattr(source, "engineering_instance_id", None):
            return source.engineering_instance.company_id
        if getattr(source, "calculation_id", None):
            return source.calculation.engineering_instance.company_id
        if getattr(source, "breakdown_item_id", None):
            return source.breakdown_item.calculation.engineering_instance.company_id
        if getattr(source, "bom_version_id", None):
            return source.bom_version.bom.company_id
        if getattr(source, "routing_version_id", None):
            return source.routing_version.routing.company_id
        if getattr(source, "warehouse_id", None):
            return source.warehouse.company_id
    return None


def _snapshot(instance, *, capacity_source_rules_cache=None, include_workload_source_selection=False):
    result = {"id": instance.pk}
    for field in instance._meta.concrete_fields:
        # This new maintenance control is independently audited and consumed
        # only for new generation, not part of pre-existing frozen proofs.
        if isinstance(instance, Process) and field.name == 'workload_source_selection' and not include_workload_source_selection:
            continue
        value = getattr(instance, field.attname)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = str(value)
        result[field.attname] = value
    if isinstance(instance, WorkCenter):
        from .daily_capacity_service import work_center_capacity_facts
        daily = work_center_capacity_facts(instance, source_rules_cache=capacity_source_rules_cache)
        result["dailyCapacityFacts"] = daily
        result["dailyCapacitySummary"] = "；".join(
            f"{row['productTypeCode']} / {row['operationName']}：{row['capacityQuantity']} {row['uomLabel']}/天"
            for row in daily
        ) or "未维护日产能"
        result["statusLabel"] = "启用" if instance.is_active else "停用"
    elif isinstance(instance, StandardCapacity):
        from .daily_capacity_service import capacity_fact
        fact = capacity_fact(instance, source_rules_cache=capacity_source_rules_cache)
        result.update({
            "dailyCapacityFact": fact,
            "statusLabel": fact["statusLabel"],
            "product_type_name": fact["productTypeName"],
            "timeUnitLabel": "天", "timeBasisLabel": "每日" if instance.time_basis == "day" else "历史时间基准（APS停用）",
            "preparationDays": fact["preparationDays"], "transferDays": fact["transferDays"],
        })
    elif isinstance(instance, CapacityProductType):
        result["statusLabel"] = "启用" if instance.is_active else "停用"
    if isinstance(instance, Material):
        result["category_name"] = instance.category.name if instance.category_id else ""
        result["base_uom_name"] = instance.base_uom.name if instance.base_uom_id else ""
        result["purchase_uom_name"] = (
            instance.purchase_uom.name if instance.purchase_uom_id else ""
        )
        result["supply_type"] = instance.supply_type
        result["supply_type_display"] = instance.supply_type_display
    elif isinstance(instance, MaterialCategory):
        result["parent_name"] = instance.parent.name if instance.parent_id else ""
    elif isinstance(instance, UnitOfMeasure):
        result["conversion_base_name"] = (
            instance.conversion_base.name if instance.conversion_base_id else ""
        )
    return result


def _clean_values(entity, model, payload):
    concrete_fields = {
        field.attname: field for field in model._meta.concrete_fields if not field.auto_created
    }
    if entity == 'routing-versions' and set(payload) & {'usage_purpose','origin_version_id','test_origin_bom_id'}:
        raise ProductionFoundationError('ROUTE_PURPOSE_SERVER_OWNED', '路线用途及来源只能由后继版本服务派生。')
    if entity == 'manufacturing-outputs' and 'order_routing_arrangement_id' in payload:
        raise ProductionFoundationError('DEDICATED_CONSUMER_REQUIRED','订单执行安排引用只能由正式消费服务核定。')
    permitted = set(concrete_fields)
    immutable = {"id", "created_at", "updated_at"} | ENTITY_READ_ONLY_FIELDS.get(entity, set())
    values = {
        key: value for key, value in payload.items()
        if key in permitted and key not in immutable
    }
    control_fields = {"reason", "materialAction", "justification"}
    unknown = sorted(set(payload) - permitted - control_fields - immutable)
    if unknown:
        raise ProductionFoundationError(
            "UNKNOWN_FIELDS", "请求包含未定义字段。", {"fields": unknown}
        )
    for key, value in list(values.items()):
        if value == "" and concrete_fields[key].null:
            values[key] = None
    return values


def _validate_references(entity, values):
    fields = dict(FK_CONFIG)
    fields.update({
        field: model for (entity_name, field), model in FK_ENTITY_OVERRIDES.items()
        if entity_name == entity
    })
    for field, model in fields.items():
        value = values.get(field)
        if value in (None, "") or model is None:
            continue
        if isinstance(model, str):
            app_label, model_name = model.split(".", 1)
            model = apps.get_model(app_label, model_name)
        row = model.objects.filter(pk=value).first()
        if row is None:
            raise ProductionFoundationError(
                "REFERENCE_NOT_FOUND", f"正式引用不存在：{field}={value}",
            )
        if hasattr(row, "is_active") and not row.is_active:
            raise ProductionFoundationError(
                "INACTIVE_REFERENCE", f"停用对象不得进入新业务默认选择：{field}={value}",
            )


def _actor_chain(user, *, required_responsibility=None):
    employee = Employee.objects.select_related("position_ref").filter(
        user=user, status="active",
    ).first()
    position = employee.position_ref if employee else None
    mappings = PositionResponsibility.objects.select_related("responsibility").filter(
        position=position, active=True, responsibility__is_active=True,
        responsibility__status="ACTIVE",
    ) if position and position.is_active else PositionResponsibility.objects.none()
    # A position can legitimately carry several responsibilities. For formal
    # master-data writes, prefer the explicitly governed executor duty instead
    # of whichever mapping happens to have the lowest primary key.
    if required_responsibility:
        mappings = mappings.filter(responsibility__code=required_responsibility)
    mapping = mappings.annotate(
        executor_priority=Case(
            When(
                responsibility__code="ENTERPRISE_MASTER_DATA_MAINTAINER",
                then=Value(0),
            ),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by("executor_priority", "pk").first()
    if not employee or not position or not position.is_active or not mapping:
        raise ProductionFoundationError(
            "FORMAL_EXECUTION_CHAIN_REQUIRED",
            "企业基础资料维护账户必须关联在职员工、启用岗位和有效职责。",
        )
    return {
        "account": user.username,
        "employeeId": employee.pk,
        "employeeNo": employee.employee_no,
        "positionId": position.pk,
        "positionCode": position.code,
        "responsibilityId": mapping.responsibility_id,
        "responsibilityCode": mapping.responsibility.code,
    }


def _material_canonical_gate(*, values, instance, payload, organization_id):
    """Fail closed for exact active duplicates and explicit inactive decisions."""

    effective_active = values.get(
        "is_active", instance.is_active if instance is not None else True,
    )
    action = str(payload.get("materialAction") or "").strip().upper()
    justification = str(payload.get("justification") or "").strip()
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise ProductionFoundationError(
            "MATERIAL_MAINTENANCE_REASON_REQUIRED",
            "Material正式新增或维护必须提供维护原因。",
        )
    if instance is not None and instance.is_active and not effective_active:
        if not reason:
            raise ProductionFoundationError(
                "DEACTIVATION_REASON_REQUIRED", "停用Material必须提供维护原因。",
            )
        return {"decision": "DEACTIVATE", "identity": canonical_identity(values=values, instance=instance)}
    if not effective_active:
        return {"decision": "INACTIVE_UPDATE", "identity": canonical_identity(values=values, instance=instance)}

    reactivating = bool(instance is not None and not instance.is_active and effective_active)
    if reactivating and action != "REACTIVATE":
        raise ProductionFoundationError(
            "REACTIVATE_ACTION_REQUIRED",
            "停用Material重新启用必须明确提交REACTIVATE动作。",
            {"candidate": canonical_material_readback(instance)},
        )
    if action == "REACTIVATE" and not reactivating:
        raise ProductionFoundationError(
            "REACTIVATE_TARGET_INVALID", "REACTIVATE只适用于当前停用Material。",
        )

    identity = canonical_identity(values=values, instance=instance)
    matches = matching_materials(
        company_id=organization_id, identity=identity,
        exclude_id=instance.pk if instance else None,
    )
    active = [row for row in matches if row.is_active]
    if active:
        raise ProductionFoundationError(
            "DUPLICATE_ACTIVE_MATERIAL",
            "同公司已存在完全相同的启用Material，禁止重复建立或重新启用。",
            {"canonicalMaterial": canonical_material_readback(active[0])},
        )

    inactive = [row for row in matches if not row.is_active]
    if inactive and not reactivating:
        candidates = [canonical_material_readback(row) for row in inactive]
        if action != "CREATE_NEW_WITH_JUSTIFICATION":
            raise ProductionFoundationError(
                "INACTIVE_MATERIAL_CANDIDATE_REQUIRES_DECISION",
                "存在完全相同的停用Material；请选择重新启用或说明理由后新建。",
                {
                    "inactiveCandidates": candidates,
                    "requiredActions": ["REACTIVATE", "CREATE_NEW_WITH_JUSTIFICATION"],
                },
            )
        if not justification:
            raise ProductionFoundationError(
                "CREATE_NEW_JUSTIFICATION_REQUIRED",
                "存在停用候选时，新建Material必须提供明确理由。",
                {"inactiveCandidates": candidates},
            )
    elif action == "CREATE_NEW_WITH_JUSTIFICATION" and not justification:
        raise ProductionFoundationError(
            "CREATE_NEW_JUSTIFICATION_REQUIRED", "该动作必须提供明确理由。",
        )
    return {
        "decision": "REACTIVATE" if reactivating else (
            "CREATE_NEW_WITH_JUSTIFICATION" if inactive else "CANONICAL_CLEAR"
        ),
        "identity": identity,
        "inactiveCandidates": [row.pk for row in inactive],
        "justification": justification,
    }


def _material_category_duplicate_gate(*, values, instance, organization_id):
    effective_active = values.get(
        "is_active", instance.is_active if instance is not None else True,
    )
    if not effective_active:
        return
    name = values.get("name", instance.name if instance is not None else "")
    normalized_name = normalize_identity_text(name)
    if not normalized_name:
        return
    rows = MaterialCategory.objects.filter(
        company_id=organization_id, is_active=True,
    ).order_by("pk")
    if instance is not None:
        rows = rows.exclude(pk=instance.pk)
    duplicate = next(
        (row for row in rows if normalize_identity_text(row.name) == normalized_name),
        None,
    )
    if duplicate:
        raise ProductionFoundationError(
            "DUPLICATE_ACTIVE_MATERIAL_CATEGORY",
            "同公司已存在同名启用物料类别。",
            {"category": {"id": duplicate.pk, "code": duplicate.code, "name": duplicate.name}},
        )


def _audit(*, user, organization_id, action_code, instance, before, after, reason, authorization, execution_chain, audit_context=None):
    import_context = dict(audit_context or {})
    return OrganizationOperatingAuditRecord.objects.create(
        action_code=action_code,
        actor=user,
        organization_id=organization_id,
        target_type=instance.__class__.__name__,
        target_id=instance.pk,
        target_label=str(
            getattr(instance, "code", None)
            or getattr(instance, "product_code", None)
            or getattr(instance, "bom_code", None)
            or getattr(instance, "routing_code", None)
            or getattr(instance, "source_no", None)
            or getattr(instance, "rule_code", None)
            or getattr(instance, "instance_no", None)
            or getattr(instance, "calculation_no", None)
            or instance.pk
        )[:200],
        reason=str(reason or "企业基础资料正式维护")[:300],
        before_snapshot={
            "state": before,
            "authorization": authorization,
            "executionChain": execution_chain,
            "importContext": import_context,
            "factSource": "server",
        },
        after_snapshot={
            "state": after,
            "authorization": authorization,
            "executionChain": execution_chain,
            "importContext": import_context,
            "factSource": "server",
        },
    )


class ProductionFoundationService:
    @staticmethod
    def scoped_queryset(entity, *, organization_id, include_inactive=True):
        config = ENTITY_CONFIG.get(entity)
        if not config:
            raise ProductionFoundationError("ENTITY_NOT_SUPPORTED", "不支持的企业基础资料对象。")
        model, _ = config
        queryset = model.objects.all()
        if organization_id:
            field_names = {field.name for field in model._meta.fields}
            if entity == 'manufacturing-outputs':
                from django.db.models import Q
                queryset = queryset.filter(
                    Q(definition_mode='order_specific', order_engineering_instance__company_id=organization_id)
                    | Q(definition_mode='standard', product__company_id=organization_id)
                )
            elif "company" in field_names:
                queryset = queryset.filter(company_id=organization_id)
            elif "company_id" in field_names:
                queryset = queryset.filter(company_id=organization_id)
            elif "routing" in field_names:
                queryset = queryset.filter(routing__company_id=organization_id)
            elif "bom" in field_names:
                queryset = queryset.filter(bom__company_id=organization_id)
            elif "product" in field_names:
                queryset = queryset.filter(product__company_id=organization_id)
            elif "related_product" in field_names:
                queryset = queryset.filter(related_product__company_id=organization_id)
            elif "warehouse" in field_names:
                queryset = queryset.filter(warehouse__company_id=organization_id)
            elif "team" in field_names:
                queryset = queryset.filter(team__company_id=organization_id)
            elif "operation" in field_names:
                queryset = queryset.filter(operation__company_id=organization_id)
            elif "department_ref" in field_names:
                queryset = queryset.filter(department_ref__company_id=organization_id)
            elif "bom_version" in field_names:
                queryset = queryset.filter(bom_version__bom__company_id=organization_id)
            elif "routing_version" in field_names:
                queryset = queryset.filter(routing_version__routing__company_id=organization_id)
            elif "engineering_instance" in field_names:
                queryset = queryset.filter(engineering_instance__company_id=organization_id)
            elif "calculation" in field_names:
                queryset = queryset.filter(calculation__engineering_instance__company_id=organization_id)
        if not include_inactive and any(field.name == "is_active" for field in model._meta.fields):
            queryset = queryset.filter(is_active=True)
        return queryset

    @staticmethod
    def reference_options(entity, *, organization_id):
        model=ENTITY_CONFIG[entity][0]
        names={'id','code','name','company_id','is_active','status','material_code','material_name','product_code','product_name',
            'instance_no','bom_code','bom_version','routing_code','routing_version','source_no','source_name','rule_code','rule_name','version',
            'calculation_no','specification','base_uom_id','unit_name','symbol','department_code','employee_no','full_name','serial_number'}
        fields=[f.attname for f in model._meta.concrete_fields if f.primary_key or f.attname in names]
        return list(ProductionFoundationService.scoped_queryset(entity,organization_id=organization_id).values(*fields).order_by('pk'))

    @staticmethod
    def list(entity, *, include_inactive=True, organization_id=None, source_scheme_operation_id=None):
        queryset = ProductionFoundationService.scoped_queryset(entity,organization_id=organization_id,include_inactive=include_inactive)
        if entity == "standard-capacities":
            queryset = queryset.select_related("product_type", "uom", "operation", "work_center")
        elif entity == "work-centers":
            queryset = queryset.prefetch_related(Prefetch("standard_capacities",
                queryset=StandardCapacity.objects.filter(time_basis="day", product_type__isnull=False)
                    .select_related("product_type", "uom", "operation", "work_center")
                    .order_by("product_type__code", "operation_id", "pk"),
                to_attr="_pce_snapshot_capacities"))
        ordering = ("display_order", "pk") if entity == "operations" else ("pk",)
        records = list(queryset.order_by(*ordering))
        if entity in {"standard-capacities", "work-centers"}:
            proof_cache = {}
            rows = [_snapshot(row, capacity_source_rules_cache=proof_cache) for row in records]
        else:
            rows = [_snapshot(row) for row in records]
        if entity == "operations":
            from .operation_workload_source_service import project_operation_sources
            sources = {}
            for company_id in {record.company_id for record in records}:
                sources.update(project_operation_sources(
                    [record for record in records if record.company_id == company_id],
                    company_id=company_id, include_schemes=source_scheme_operation_id is not None,
                    scheme_operation_ids={source_scheme_operation_id},
                ))
            for row in rows:
                row["workloadSource"] = sources[row["id"]]
        return rows

    @staticmethod
    def maintenance_authorization(entity, *, user):
        """Return the same permission and execution-chain facts enforced on write."""
        config = ENTITY_CONFIG.get(entity)
        if not config:
            raise ProductionFoundationError("ENTITY_NOT_SUPPORTED", "不支持的企业基础资料对象。")
        _model, action_code = config
        organization_id = getattr(user, "company_id", None)
        decision = AuthorizationService.decide(
            user=user,
            action_code=action_code,
            organization_id=organization_id,
            business_object={"organizationId": organization_id},
        )
        execution_chain = {}
        chain_error = None
        if decision.get("allowed"):
            required_responsibility = (
                "ENTERPRISE_MASTER_DATA_MAINTAINER"
                if entity in {"materials", "material-categories", "units"}
                else None
            )
            try:
                from .master_data_actor import maintenance_actor
                execution_chain = maintenance_actor(user, action_code=action_code, organization_id=organization_id, required_responsibility=required_responsibility)
            except ProductionFoundationError as exc:
                chain_error = exc
        allowed = bool(decision.get("allowed")) and chain_error is None
        return {
            "entity": entity,
            "actor": getattr(user, "username", ""),
            "organizationId": organization_id,
            "actionCode": action_code,
            "allowed": allowed,
            "permissionAllowed": bool(decision.get("allowed")),
            "decisionCode": (
                decision.get("decisionCode", "PERMISSION_DENIED")
                if chain_error is None else chain_error.code
            ),
            "reason": (
                decision.get("reason", "当前账户无权执行该动作。")
                if chain_error is None else chain_error.message
            ),
            "requiredScope": f"ORGANIZATION:{organization_id}" if organization_id else "ORGANIZATION",
            "executionChainComplete": bool(execution_chain),
            "maintenanceIdentityLabel": execution_chain.get('identityLabel') or ('正式员工岗位职责链' if execution_chain else '维护身份不完整'),
            "formalEmployeeChainComplete": bool(execution_chain.get('employeeId') and execution_chain.get('positionId') and execution_chain.get('responsibilityId')),
            "executionChain": execution_chain,
            "authorization": decision,
        }

    @classmethod
    @transaction.atomic
    def correct_released_rule_effectivity(
        cls, *, user, object_id, expected_company_id, expected_rule_code,
        expected_version, expected_status, expected_effective_from,
        expected_effective_to, expected_specification_hash,
        expected_updated_at, corrected_effective_to, reason,
        approval_reference, idempotency_key,
    ):
        """Correct only a released rule's end date through an audited technical gate."""
        if not (user.is_active and user.is_staff and user.is_superuser):
            raise ProductionFoundationError(
                "TECHNICAL_CORRECTION_AUTHORITY_REQUIRED",
                "已发布规则有效期纠正仅允许真实技术管理员通过专用动作执行。",
            )
        approval_reference = str(approval_reference or "").strip()
        idempotency_key = str(idempotency_key or "").strip()
        reason = str(reason or "").strip()
        if not approval_reference or not idempotency_key or not reason:
            raise ProductionFoundationError(
                "CORRECTION_APPROVAL_REQUIRED",
                "受控纠正必须提供批准引用、幂等键和真实原因。",
            )
        try:
            expected_company_id = int(expected_company_id)
        except (TypeError, ValueError):
            raise ProductionFoundationError(
                "CORRECTION_SCOPE_INVALID", "目标公司必须是正式公司ID。",
            )
        if expected_company_id != user.company_id:
            raise ProductionFoundationError(
                "CROSS_COMPANY_WRITE_FORBIDDEN", "只能纠正当前登录公司的正式规则。",
            )
        if corrected_effective_to not in (None, ""):
            raise ProductionFoundationError(
                "CORRECTION_VALUE_DENIED", "本专用动作只允许将失效日期纠正为空值。",
            )
        expected_from = parse_date(str(expected_effective_from or ""))
        expected_to = parse_date(str(expected_effective_to or ""))
        if expected_from is None or expected_to is None:
            raise ProductionFoundationError(
                "CORRECTION_SCOPE_INVALID", "预期生效日期和原失效日期必须是有效日期。",
            )
        instance = EngineeringRuleDefinition.objects.select_for_update().filter(
            pk=object_id,
        ).first()
        if not instance:
            raise ProductionFoundationError("OBJECT_NOT_FOUND", "待纠正规则不存在。")

        scope = {
            "companyId": expected_company_id,
            "objectId": int(object_id),
            "ruleCode": str(expected_rule_code or "").strip(),
            "version": str(expected_version or "").strip(),
            "status": str(expected_status or "").strip(),
            "effectiveFrom": expected_from.isoformat(),
            "expectedEffectiveTo": expected_to.isoformat(),
            "correctedEffectiveTo": None,
            "specificationHash": str(expected_specification_hash or "").strip(),
        }
        scope_hash = sha256(json.dumps(
            scope, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        prior_audits = OrganizationOperatingAuditRecord.objects.filter(
            organization_id=expected_company_id,
            action_code="production.engineering.rule.correct_effectivity",
            target_type="EngineeringRuleDefinition",
            target_id=instance.pk,
        ).order_by("pk")
        for prior in prior_audits:
            context = (prior.after_snapshot or {}).get("importContext") or {}
            correction = context.get("correction") or {}
            if (
                correction.get("idempotencyKey") == idempotency_key
                and correction.get("approvalReference") == approval_reference
                and correction.get("scopeHash") == scope_hash
            ):
                if instance.effective_to is not None:
                    raise ProductionFoundationError(
                        "CORRECTION_STATE_DRIFTED",
                        "既有纠正审计与当前规则日期不一致，禁止重复覆盖。",
                    )
                return {
                    "row": _snapshot(instance), "auditId": prior.pk,
                    "idempotent": True, "approvalReference": approval_reference,
                    "scopeHash": scope_hash,
                }

        actual_hash = specification_hash(instance.specification)
        actual_updated_at = instance.updated_at.isoformat()
        expected = {
            "company_id": expected_company_id,
            "rule_code": scope["ruleCode"],
            "version": scope["version"],
            "status": scope["status"],
            "effective_from": expected_from,
            "effective_to": expected_to,
            "specification_hash": scope["specificationHash"],
            "updated_at": str(expected_updated_at or "").strip(),
        }
        actual = {
            "company_id": instance.company_id,
            "rule_code": instance.rule_code,
            "version": instance.version,
            "status": instance.status,
            "effective_from": instance.effective_from,
            "effective_to": instance.effective_to,
            "specification_hash": actual_hash,
            "updated_at": actual_updated_at,
        }
        mismatches = {
            key: {"expected": str(expected[key]), "actual": str(actual[key])}
            for key in expected if expected[key] != actual[key]
        }
        if mismatches:
            raise ProductionFoundationError(
                "CORRECTION_SCOPE_MISMATCH",
                "规则当前事实与获批纠正范围不一致，已停止。",
                {"mismatches": mismatches},
            )

        decision = AuthorizationService.decide(
            user=user,
            action_code="production.engineering.rule.release",
            organization_id=expected_company_id,
            business_object={
                "organizationId": expected_company_id,
                "entity": "engineering-rule-definitions",
                "id": instance.pk,
                "technicalCorrection": "released_effective_to_clear",
                "approvalReference": approval_reference,
                "scopeHash": scope_hash,
            },
        )
        if not decision.get("allowed"):
            raise ProductionFoundationError(
                decision.get("decisionCode", "PERMISSION_DENIED"),
                decision.get("reason", "当前技术账户无权执行规则有效期纠正。"),
                {"authorization": decision},
            )

        execution_chain = {
            "account": user.username,
            "technicalCorrection": True,
            "authority": "active staff superuser + AuthorizationService + target approval",
            "approvalReference": approval_reference,
        }
        before = {
            **_snapshot(instance),
            "rule_version": instance.version,
            "specification_hash": actual_hash,
            "expression_hash": expression_hash(instance.specification),
            "operator": user.username,
        }
        corrected_at = timezone.now()
        updated = EngineeringRuleDefinition.objects.filter(
            pk=instance.pk,
            company_id=expected_company_id,
            updated_at=instance.updated_at,
            effective_to=expected_to,
        ).update(effective_to=None, updated_at=corrected_at)
        if updated != 1:
            raise ProductionFoundationError(
                "CORRECTION_CONCURRENT_WRITE",
                "规则在纠正期间发生变化，未覆盖最新事实。",
            )
        instance.refresh_from_db()
        after = {
            **_snapshot(instance),
            "rule_version": instance.version,
            "specification_hash": specification_hash(instance.specification),
            "expression_hash": expression_hash(instance.specification),
            "operator": user.username,
        }
        audit = _audit(
            user=user,
            organization_id=expected_company_id,
            action_code="production.engineering.rule.correct_effectivity",
            instance=instance,
            before=before,
            after=after,
            reason=reason,
            authorization=decision,
            execution_chain=execution_chain,
            audit_context={
                "correction": {
                    "type": "released_effective_to_clear",
                    "approvalReference": approval_reference,
                    "idempotencyKey": idempotency_key,
                    "scope": scope,
                    "scopeHash": scope_hash,
                    "correctedAt": corrected_at.isoformat(),
                }
            },
        )
        return {
            "row": after, "auditId": audit.pk, "idempotent": False,
            "authorization": decision, "executionChain": execution_chain,
            "approvalReference": approval_reference, "scopeHash": scope_hash,
        }

    @classmethod
    @transaction.atomic
    def save(cls, entity, *, user, payload, object_id=None, audit_context=None):
        """Canonical persistence primitive; external callers use ``write`` for CREATE."""
        config = ENTITY_CONFIG.get(entity)
        if not config:
            raise ProductionFoundationError("ENTITY_NOT_SUPPORTED", "不支持的企业基础资料对象。")
        if entity in {"team-membership-employees", "team-departments"}:
            raise ProductionFoundationError(
                "READ_ONLY_REFERENCE_ENTITY",
                "组织员工和部门仅作为班组维护的正式引用；其档案仍在组织与权限入口维护。",
            )
        if entity in {
            "engineering-calculation-records",
            "engineering-breakdown-items",
            "engineering-derived-facts",
        }:
            raise ProductionFoundationError(
                "CALCULATION_EXECUTION_SERVICE_REQUIRED",
                "工程计算、明细和派生事实只能由DO-3正式计算服务原子生成。",
            )
        model, action_code = config
        instance = model.objects.select_for_update().filter(pk=object_id).first() if object_id else None
        if object_id and instance is None:
            raise ProductionFoundationError("OBJECT_NOT_FOUND", "待维护对象不存在。")
        payload = dict(payload)
        source_intent = payload.pop('sourceSchemeSelection', None) if entity == 'operations' else None
        if entity == 'operations' and 'workload_source_selection' in payload:
            raise ProductionFoundationError('WORKLOAD_SOURCE_SELECTION_INTENT_REQUIRED',
                '正式来源引用只能通过服务器方案选择意图维护，不能直接提交JSON字段。')
        values = _clean_values(entity, model, payload)
        if entity=='routings' and 'status' in values:
            expected_status=instance.status if instance else 'draft'
            if values.pop('status')!=expected_status:
                raise ProductionFoundationError('STANDARD_STATUS_CONTROL_REQUIRED','标准主档状态不能通过普通字段直接推进，须按正常状态控制办理。')

        if entity=='routing-versions' and instance is None and RoutingVersion.objects.filter(routing_id=values.get('routing_id')).exists():
            raise ProductionFoundationError('STANDARD_SUCCESSOR_SERVICE_REQUIRED','已有标准版本必须通过企业基础资料的后继服务增加，不能手工编号绕过沿革。')
        if entity in ('routing-versions','routing-steps'):
            from .standard_routing_owner_service import require_draft_edit
            require_draft_edit(entity,values,instance)
        if entity == "standard-capacities":
            for field in ("preparation_days", "transfer_days"):
                value = values.get(field)
                if value is None:
                    continue
                try:
                    if isinstance(value, bool):
                        raise ValueError
                    days = Decimal(str(value))
                    if not days.is_finite() or days < 0:
                        raise ValueError
                    # Keep model precision validation on a numeric value, even
                    # when DecimalField rejects its scale or digit count.
                    values[field] = days
                except (InvalidOperation, TypeError, ValueError):
                    raise ProductionFoundationError("APS_CAPACITY_DAY_TIME_INVALID",
                        "准备、转运时间必须为有限非负十进制天数或留空，不能使用布尔值。", {"field": field})
            if values.get("measurement_status", getattr(instance, "measurement_status", None)) == "not_determinable":
                raise ProductionFoundationError("CAPACITY_LEGACY_STATUS_NOT_ALLOWED",
                    "历史“适用但无法确定”不能新增或继续维护为有效产能类别。请按工艺及实际范围维护正数或0；不经过须有正式适用性依据，NULL或缺记录不能推断为不经过。")
            try:
                basis_quantity = Decimal(str(values.get("time_basis_quantity", getattr(instance, "time_basis_quantity", 0)) or 0))
            except (InvalidOperation, TypeError, ValueError):
                raise ProductionFoundationError("APS_CAPACITY_DAY_REQUIRED", "日产能基准数量必须为1。")
            if (values.get("time_basis", getattr(instance, "time_basis", None)) != "day"
                    or not basis_quantity.is_finite() or basis_quantity != 1):
                raise ProductionFoundationError("APS_CAPACITY_DAY_REQUIRED", "APS标准产能仅允许数量/天，基准数量必须为1。")
            if not values.get("product_type_id", getattr(instance, "product_type_id", None)):
                raise ProductionFoundationError("CAPACITY_PRODUCT_TYPE_REQUIRED", "必须选择正式产品/半成品类型。")
            if not values.get("effective_from", getattr(instance, "effective_from", None)):
                raise ProductionFoundationError("CAPACITY_EFFECTIVE_DATE_REQUIRED", "必须维护日产能生效日期。")
        if entity == "manufacturing-outputs":
            from .manufacturing_output_generation_service import ACTION, OBJECT, ManufacturingOutputError, scoped_item
            from workflow_runtime.models import BusinessStateTransition
            generated = bool(instance and BusinessStateTransition.objects.filter(
                object_type=OBJECT, object_id=instance.pk, action_code=ACTION).exists())
            scoped_create = False
            if instance is None and values.get("order_engineering_instance_id"):
                try:
                    item = scoped_item(user.company_id)
                    scoped_create = OrderEngineeringInstance.objects.filter(
                        pk=values["order_engineering_instance_id"], sales_order_item=item).exists()
                except ManufacturingOutputError:
                    pass
            if generated or scoped_create:
                raise ProductionFoundationError("MANUFACTURING_OUTPUT_DEDICATED_CONTROL_REQUIRED",
                    "本轮制造输出必须由原制造输出确认节点的专用正式服务办理，不得回退通用维护写入。")
        if entity == "operations" and instance is None and "display_order" not in values:
            current_max = Process.objects.filter(
                company_id=values.get("company_id") or user.company_id,
                display_order__lt=Process.UNSPECIFIED_DISPLAY_ORDER,
            ).aggregate(value=Max("display_order"))["value"] or 0
            values["display_order"] = current_max + 1
        if entity == "engineering-rule-definitions":
            if instance is None and not values.get("version"):
                rule_code = values.get("rule_code")
                if not rule_code:
                    raise ProductionFoundationError(
                        "RULE_CODE_REQUIRED", "自动产生首版前必须先填写正式规则编码。"
                    )
                if EngineeringRuleDefinition.objects.filter(
                    company_id=values.get("company_id") or user.company_id,
                    rule_code=rule_code,
                ).exists():
                    raise ProductionFoundationError(
                        "VERSION_CHANGE_ACTION_REQUIRED",
                        "该规则已有正式版本；后续版本必须由版本变更动作产生。",
                    )
                values["version"] = "V1.0"
            action_code = (
                "production.engineering.rule.update_draft"
                if instance else "production.engineering.rule.create"
            )
            if instance and instance.status != "draft":
                raise ProductionFoundationError(
                    "RELEASED_RULE_IMMUTABLE",
                    "只有草稿规则允许修改；已评审、已发布或已失效规则必须创建新版本。",
                )
            try:
                validate_specification(values.get("specification", getattr(instance, "specification", None)))
            except EngineeringRuleError as exc:
                raise ProductionFoundationError(exc.code, exc.message, exc.details)
        _validate_references(entity, values)
        organization_id = _organization_id(model, values, instance)
        has_company_field = any(field.attname == "company_id" for field in model._meta.fields)
        if not organization_id and has_company_field:
            organization_id = user.company_id
        if not organization_id:
            raise ProductionFoundationError("ORGANIZATION_REQUIRED", "正式主数据必须明确所属公司。")
        if not Company.objects.filter(pk=organization_id, is_active=True).exists():
            raise ProductionFoundationError(
                "ORGANIZATION_INACTIVE",
                "目标公司已退出有效经营范围，不允许新增或修改企业基础资料。",
            )
        if has_company_field and not values.get("company_id"):
            values["company_id"] = organization_id
        if entity == "engineering-source-records":
            from .source_format_mapping_service import SourceFormatMappingError, normalize_source_payload
            old_payload = getattr(instance, "source_payload", {})
            source_payload = values.get("source_payload", old_payload)
            mapped = isinstance(source_payload, dict) and "sourceFormatReference" in source_payload
            mapped_before = isinstance(old_payload, dict) and "sourceFormatReference" in old_payload
            if instance and instance.status != "draft" and (mapped or mapped_before):
                protected = ("company_id", "source_no", "source_name", "source_type", "source_version",
                    "source_payload", "content_hash", "effective_date")
                changed = [field for field in protected if field in values and values[field] != getattr(instance, field)]
                if changed:
                    raise ProductionFoundationError("CONFIRMED_SOURCE_FORMAT_IMMUTABLE",
                        "已确认来源的格式映射及原始规范快照不可修改；请建立新来源版本。", {"fields": changed})
            if mapped:
                try:
                    values["source_payload"] = normalize_source_payload(source_payload, company_id=organization_id)
                    values["content_hash"] = values["source_payload"]["normalization"]["rawContentHash"]
                except SourceFormatMappingError as exc:
                    raise ProductionFoundationError(exc.code, exc.message, exc.details)
        from .engineering_workbook_source_service import is_workbook_source,is_workbook_rule
        workbook_governed=(entity=='engineering-source-records' and is_workbook_source(values.get('source_payload',getattr(instance,'source_payload',{})))) or (
            entity=='engineering-rule-definitions' and is_workbook_rule(values.get('specification',getattr(instance,'specification',{}))))
        material_canonical = None
        if entity == "materials":
            material_canonical = _material_canonical_gate(
                values=values, instance=instance, payload=payload,
                organization_id=organization_id,
            )
        elif entity == "material-categories":
            _material_category_duplicate_gate(
                values=values, instance=instance, organization_id=organization_id,
            )
        code_config = ENTITY_CODE_FIELDS.get(entity)
        if instance is None and code_config and not values.get(code_config[0]):
            try:
                values[code_config[0]] = CodeRule.next_code(
                    entity_type=code_config[1], company_id=organization_id,
                )
            except CodeRule.DoesNotExist:
                raise ProductionFoundationError(
                    "CODE_RULE_REQUIRED", f"缺少正式编码规则：{code_config[1]}"
                )
        version_config = INITIAL_VERSION_FIELDS.get(entity)
        if instance is None and version_config and not values.get(version_config[0]):
            version_field, owner_field, version_model = version_config
            owner_id = values.get(owner_field)
            if not owner_id:
                raise ProductionFoundationError(
                    "VERSION_OWNER_REQUIRED", "自动产生首版前必须先选择正式版本所属对象。"
                )
            if version_model.objects.filter(**{owner_field: owner_id}).exists():
                raise ProductionFoundationError(
                    "VERSION_CHANGE_ACTION_REQUIRED",
                    "已有正式版本；后续版本必须由版本变更动作产生，不得手工填写流水。",
                )
            values[version_field] = "V1.0"
        decision = AuthorizationService.decide(
            user=user,
            action_code=action_code,
            organization_id=organization_id,
            business_object={"organizationId": organization_id},
        )
        if not decision.get("allowed"):
            raise ProductionFoundationError(
                decision.get("decisionCode", "PERMISSION_DENIED"),
                decision.get("reason", "当前账户无权执行该动作。"),
                {"authorization": decision},
            )
        required_responsibility = (
            "ENTERPRISE_MASTER_DATA_MAINTAINER"
            if entity in {"materials", "material-categories", "units"}
            else None
        )
        from .master_data_actor import maintenance_actor
        execution_chain = maintenance_actor(user,action_code=action_code,organization_id=organization_id,required_responsibility=required_responsibility)
        before = _snapshot(instance, include_workload_source_selection=entity == 'operations') if instance else {}
        if entity == "engineering-rule-definitions" and instance:
            before.update({
                "rule_code": instance.rule_code,
                "rule_version": instance.version,
                "specification_hash": specification_hash(instance.specification),
                "expression_hash": expression_hash(instance.specification),
                "operator": execution_chain["account"],
            })
        # Saved-fact formula mappings share the existing unified state contract.
        # Other legacy rule kinds keep their existing paths and history.
        mapping_governed = (
            entity == "engineering-rule-definitions"
            and values.get("specification", getattr(instance, "specification", {})).get("contractCode")
            == "PCE-MATERIAL-REQUIREMENT-FORMULA-MAPPING-V1"
        )
        governed_created=instance is None and (workbook_governed or mapping_governed or entity in ('routings','routing-versions'))
        if governed_created:
            from workflow_runtime.state_transitions import create_business_object_with_initial_state
            instance=create_business_object_with_initial_state(model=model,initial_state='draft',**values)
        elif instance is None:
            instance = model(**values)
        else:
            for field, value in values.items():
                setattr(instance, field, value)
        source_authorization = None
        if entity == 'operations':
            from .operation_workload_source_service import prepare_source_scheme_selection, source_selection_readback
            if source_intent is not None:
                if not instance.pk:
                    raise ProductionFoundationError('WORKLOAD_SOURCE_SELECTION_OPERATION_REQUIRED',
                        '请先保存正式工序，再为其明确选择完整来源方案。')
                selected, source_authorization = prepare_source_scheme_selection(
                    user=user, operation=instance, intent=source_intent)
                instance.workload_source_selection = selected
            else:
                source_selection_readback(instance)
        try:
            instance.full_clean()
        except ValidationError as exc:
            raise ProductionFoundationError("VALIDATION_FAILED", "正式主数据校验失败。", exc.message_dict)
        if not governed_created:instance.save()
        instance = model.objects.get(pk=instance.pk)
        after = _snapshot(instance, include_workload_source_selection=entity == 'operations')
        if entity == "engineering-rule-definitions":
            after.update({
                "rule_code": instance.rule_code,
                "rule_version": instance.version,
                "specification_hash": specification_hash(instance.specification),
                "expression_hash": expression_hash(instance.specification),
                "operator": execution_chain["account"],
            })
        effective_audit_context = dict(audit_context or {})
        if source_authorization is not None:
            effective_audit_context['sourceSchemeAuthorization'] = source_authorization
        if material_canonical is not None:
            effective_audit_context["materialCanonicalGate"] = material_canonical
        audit = _audit(
            user=user,
            organization_id=organization_id,
            action_code=action_code,
            instance=instance,
            before=before,
            after=after,
            reason=payload.get("reason"),
            authorization=decision,
            execution_chain=execution_chain,
            audit_context=effective_audit_context,
        )
        if entity == 'operations':
            from .operation_workload_source_service import project_operation_sources, source_selection_readback
            source_selection_readback(instance)
            after['workloadSource'] = project_operation_sources([instance], organization_id,
                include_schemes=True)[instance.pk]
        initial_transition = None
        if governed_created:
            from workflow_runtime.state_transitions import record_projected_business_transition
            initial_transition = record_projected_business_transition(object_type=model.__name__,object_id=instance.pk,
                source_state='',target_state='draft',action_code=action_code,operator=user,
                reason=str(payload.get('reason') or '正式来源版本初始化'),
                audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={('','draft')})
        return {
            "row": after, "auditId": audit.pk, "authorization": decision,
            "executionChain": execution_chain,
            **({"transitionId": initial_transition.pk} if initial_transition else {}),
        }

    @classmethod
    @transaction.atomic
    def _write_existing(cls, entity, *, user, payload, idempotency_key, object_id):
        """Idempotent update/deactivate/reactivate path for an existing object."""

        key = str(idempotency_key or "").strip()
        if not key:
            raise ProductionFoundationError(
                "IDEMPOTENCY_KEY_REQUIRED", "维护正式主数据必须提供幂等键。",
            )
        model, action_code = ENTITY_CONFIG[entity]
        instance = model.objects.select_for_update().filter(pk=object_id).first()
        if instance is None:
            raise ProductionFoundationError("OBJECT_NOT_FOUND", "待维护对象不存在。")
        organization_id = _organization_id(model, {}, instance) or user.company_id
        if not organization_id:
            raise ProductionFoundationError("ORGANIZATION_REQUIRED", "正式主数据必须明确所属公司。")
        if entity == 'operations' and 'sourceSchemeSelection' in payload:
            from .operation_workload_source_service import _configure_authorization
            resource = AuthorizationService.decide(user=user, action_code=action_code,
                organization_id=organization_id, business_object={'organizationId': organization_id})
            if not resource.get('allowed') or not _configure_authorization(user)['allowed']:
                raise ProductionFoundationError('PERMISSION_DENIED', '来源方案保存及幂等重放均须具备当前维护和规则权限。')
        request_hash = sha256(json.dumps(
            {"entity": entity, "objectId": object_id, "payload": payload},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
        ).encode("utf-8")).hexdigest()
        identity_lookup = {
            "organization_id": organization_id,
            "source_system": "PCE",
            "source_type": "FORMAL_EXISTING_OBJECT",
            "source_object_type": f"{entity}:formal-maintenance",
            "external_id": f"{entity}:{object_id}",
        }
        source_row, _ = ExternalIdentity.objects.select_for_update().get_or_create(
            **identity_lookup,
            defaults={
                "target_entity_type": entity,
                "target_entity_id": str(object_id),
                "mapping_status": ExternalIdentity.MappingStatus.MATCH,
                "audit_metadata": {"channel": "ProductionFoundationService.update"},
            },
        )
        if (
            source_row.target_entity_type != entity
            or source_row.target_entity_id != str(object_id)
            or source_row.mapping_status != ExternalIdentity.MappingStatus.MATCH
        ):
            raise ProductionFoundationError(
                "SOURCE_IDENTITY_TARGET_CONFLICT",
                "既有正式对象维护身份与目标记录不一致。",
            )
        ledger, created = MasterDataWriteRequest.objects.select_for_update().get_or_create(
            organization_id=organization_id,
            action_code=action_code,
            idempotency_key=key,
            defaults={
                "entity_type": entity,
                "request_hash": request_hash,
                "source_identity": source_row,
                "target_entity_id": str(object_id),
                "audit_metadata": {"operatorId": user.pk, "operation": "UPDATE"},
            },
        )
        if not created and ledger.request_hash != request_hash:
            raise ProductionFoundationError(
                "IDEMPOTENCY_PAYLOAD_CONFLICT", "同一幂等键不得提交不同内容。",
            )
        if not created and ledger.status == MasterDataWriteRequest.Status.COMMITTED:
            return {**ledger.result, "idempotentReplay": True}
        result = cls.save(
            entity, user=user, payload=payload, object_id=object_id,
            audit_context={
                "idempotencyKey": key,
                "actionRequestId": ledger.pk,
                "sourceIdentityId": source_row.pk,
            },
        )
        result.update({
            "idempotentReplay": False,
            "sourceIdentityId": source_row.pk,
            "actionRequestId": ledger.pk,
        })
        ledger.entity_type = entity
        ledger.request_hash = request_hash
        ledger.source_identity = source_row
        ledger.status = MasterDataWriteRequest.Status.COMMITTED
        ledger.target_entity_id = str(object_id)
        ledger.result = result
        ledger.save(update_fields=(
            "entity_type", "request_hash", "source_identity", "status",
            "target_entity_id", "result", "updated_at",
        ))
        return result

    @classmethod
    @transaction.atomic
    def write(
        cls, entity, *, user, payload, idempotency_key, source_identity,
        object_id=None,
    ):
        """Single formal write chain with source identity and create idempotency."""
        if entity not in ENTITY_CONFIG:
            raise ProductionFoundationError("ENTITY_NOT_SUPPORTED", "不支持的企业基础资料对象。")
        if object_id:
            return cls._write_existing(
                entity, user=user, payload=payload,
                idempotency_key=idempotency_key, object_id=object_id,
            )
        key = str(idempotency_key or "").strip()
        if not key:
            raise ProductionFoundationError(
                "IDEMPOTENCY_KEY_REQUIRED", "新增正式主数据必须提供幂等键。",
            )
        identity = dict(source_identity or {})
        required = (
            "sourceSystem", "sourceType", "sourceObjectType", "externalId",
        )
        missing = [field for field in required if not str(identity.get(field) or "").strip()]
        if missing:
            raise ProductionFoundationError(
                "SOURCE_IDENTITY_REQUIRED", "新增正式主数据必须提供完整来源身份。",
                {"missing": missing},
            )
        organization_id = int(payload.get("company_id") or user.company_id or 0)
        if not organization_id:
            raise ProductionFoundationError("ORGANIZATION_REQUIRED", "正式主数据必须明确所属公司。")
        if entity == "order-engineering-instances":
            from .pde_engineering_preparation_admission import (
                PDEEngineeringPreparationAdmissionError,
                require_pde_engineering_preparation_admission,
            )
            try:
                admission = require_pde_engineering_preparation_admission(
                    company_id=organization_id,
                    sales_order_item_id=payload.get("sales_order_item_id"),
                    authorization_id=payload.get("engineering_preparation_authorization_id"),
                    lock=True,
                )
            except PDEEngineeringPreparationAdmissionError as exc:
                raise ProductionFoundationError(exc.code, exc.message, exc.details) from exc
            payload = dict(payload)
            payload["engineering_preparation_authorization_id"] = admission.authorization_id
        request_hash = sha256(json.dumps(
            {"entity": entity, "payload": payload, "sourceIdentity": identity},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
        ).encode("utf-8")).hexdigest()
        lookup = {
            "organization_id": organization_id,
            "source_system": str(identity["sourceSystem"]).strip(),
            "source_type": str(identity["sourceType"]).strip(),
            "source_object_type": str(identity["sourceObjectType"]).strip(),
            "external_id": str(identity["externalId"]).strip(),
        }
        try:
            source_row, created = ExternalIdentity.objects.select_for_update().get_or_create(
                **lookup,
                defaults={
                    "target_entity_type": entity,
                    "mapping_status": ExternalIdentity.MappingStatus.CREATE,
                    "source_fingerprint": str(identity.get("sourceFingerprint") or ""),
                    "audit_metadata": identity.get("auditMetadata") or {},
                },
            )
        except IntegrityError:
            source_row = ExternalIdentity.objects.select_for_update().get(**lookup)
            created = False
        if source_row.target_entity_type != entity:
            raise ProductionFoundationError(
                "SOURCE_IDENTITY_TARGET_CONFLICT",
                "同一来源身份已经绑定其他正式实体类型。",
            )
        existing_ledger = MasterDataWriteRequest.objects.select_for_update().filter(
            organization_id=organization_id,
            action_code="production.master_data.create",
            idempotency_key=key,
        ).first()
        if existing_ledger and existing_ledger.request_hash != request_hash:
            raise ProductionFoundationError(
                "IDEMPOTENCY_PAYLOAD_CONFLICT", "同一幂等键不得提交不同内容。",
            )
        if existing_ledger and existing_ledger.status == MasterDataWriteRequest.Status.COMMITTED:
            return {**existing_ledger.result, "idempotentReplay": True}
        if source_row.mapping_status == ExternalIdentity.MappingStatus.MATCH:
            model = ENTITY_CONFIG[entity][0]
            existing = model.objects.filter(pk=source_row.target_entity_id).first()
            if not existing:
                raise ProductionFoundationError(
                    "SOURCE_IDENTITY_DANGLING", "来源身份指向的正式主数据不存在。",
                )
            replay = {
                "row": _snapshot(existing), "idempotentReplay": True,
                "sourceIdentityId": source_row.pk,
            }
            if existing_ledger is None:
                MasterDataWriteRequest.objects.create(
                    organization_id=organization_id,
                    action_code="production.master_data.create",
                    entity_type=entity,
                    idempotency_key=key,
                    request_hash=request_hash,
                    source_identity=source_row,
                    status=MasterDataWriteRequest.Status.COMMITTED,
                    target_entity_id=str(existing.pk),
                    result=replay,
                    audit_metadata={"operatorId": user.pk, "sourceIdentityReplay": True},
                )
            return replay

        ledger, ledger_created = MasterDataWriteRequest.objects.select_for_update().get_or_create(
            organization_id=organization_id,
            action_code="production.master_data.create",
            idempotency_key=key,
            defaults={
                "entity_type": entity,
                "request_hash": request_hash,
                "source_identity": source_row,
                "audit_metadata": {"operatorId": user.pk},
            },
        )
        if not ledger_created:
            if ledger.request_hash != request_hash:
                raise ProductionFoundationError(
                    "IDEMPOTENCY_PAYLOAD_CONFLICT",
                    "同一幂等键不得提交不同内容。",
                )
            if ledger.status == MasterDataWriteRequest.Status.COMMITTED:
                return {**ledger.result, "idempotentReplay": True}

        result = cls.save(
            entity, user=user, payload=payload,
            audit_context=identity.get("auditMetadata") or {},
        )
        target_id = str(result["row"]["id"])
        source_row.target_entity_id = target_id
        source_row.mapping_status = ExternalIdentity.MappingStatus.MATCH
        source_row.source_fingerprint = str(identity.get("sourceFingerprint") or source_row.source_fingerprint)
        source_row.audit_metadata = identity.get("auditMetadata") or source_row.audit_metadata
        source_row.full_clean()
        source_row.save(update_fields=(
            "target_entity_id", "mapping_status", "source_fingerprint",
            "audit_metadata", "last_seen",
        ))
        result.update({
            "idempotentReplay": False,
            "sourceIdentityId": source_row.pk,
            "actionRequestId": ledger.pk,
        })
        ledger.entity_type = entity
        ledger.request_hash = request_hash
        ledger.source_identity = source_row
        ledger.status = MasterDataWriteRequest.Status.COMMITTED
        ledger.target_entity_id = target_id
        ledger.result = result
        ledger.save(update_fields=(
            "entity_type", "request_hash", "source_identity", "status",
            "target_entity_id", "result", "updated_at",
        ))
        return result


class EngineeringLifecycleService:
    """Formal version/release state transitions; scalar version fields are projections."""

    CONFIG = {
        "product-versions": (ProductVersion, "version_status", "production.engineering.version.release"),
        # The BOMVersion branch delegates to bom_version_control_service before
        # reading CONFIG.  Keep this metadata aligned with that exact business
        # contract so static consumers cannot treat generic engineering release
        # authority as BOM formal-release authority.
        "bom-versions": (BOMVersion, "status", "pde.bom_version.release"),
        "routing-versions": (RoutingVersion, "status", "production.engineering.version.release"),
        "engineering-document-versions": (
            EngineeringDocumentVersion, "status", "production.engineering.document.release",
        ),
        "manufacturing-outputs": (
            ProductManufacturingOutput, "release_status", "production.engineering.release",
        ),
        "engineering-source-records": (
            EngineeringSourceRecord, "status", "production.engineering.source.maintain",
        ),
        "engineering-rule-definitions": (
            EngineeringRuleDefinition, "status", "production.engineering.rule.release",
        ),
        "order-engineering-instances": (
            OrderEngineeringInstance, "status", "production.engineering.order.maintain",
        ),
        "engineering-calculation-records": (
            EngineeringCalculationRecord, "status", "production.engineering.calculation.record",
        ),
    }
    ALLOWED = {
        "product-versions": {("draft", "reviewed"), ("reviewed", "released"), ("released", "obsolete")},
        "bom-versions": {("draft", "reviewed"), ("reviewed", "released"), ("released", "obsolete")},
        "routing-versions": {("draft", "reviewed"), ("reviewed", "released"), ("released", "obsolete")},
        "engineering-document-versions": {("draft", "reviewed"), ("reviewed", "released"), ("released", "obsolete")},
        "manufacturing-outputs": {
            ("draft", "engineering_review"),
            ("engineering_review", "released_to_manufacturing"),
            ("released_to_manufacturing", "inactive"),
        },
        "engineering-source-records": {
            ("draft", "confirmed"), ("confirmed", "superseded"),
        },
        "engineering-rule-definitions": {
            ("draft", "reviewed"), ("reviewed", "released"), ("released", "obsolete"),
        },
        "order-engineering-instances": {
            ("draft", "source_confirmed"),
            ("source_confirmed", "calculated"),
            ("released", "inactive"),
        },
        "engineering-calculation-records": {
            ("draft", "completed"), ("draft", "failed"),
        },
    }

    @staticmethod
    def _formal_manufacturing_eligibility(entity, instance, target_status):
        guarded = (
            entity == "bom-versions"
            and instance.bom_scope == "order_specific"
            and target_status in {"reviewed", "released"}
        ) or (
            entity == "manufacturing-outputs"
            and instance.definition_mode == "order_specific"
            and target_status in {"engineering_review", "released_to_manufacturing"}
        )
        if not guarded:
            return None
        eligibility = FormalManufacturingEligibilityService.resolve(instance)
        if not eligibility["formalManufacturingEligible"]:
            raise ProductionFoundationError(
                eligibility["decisionCode"],
                eligibility["message"],
                {"formalManufacturingEligibility": eligibility},
            )
        return eligibility

    @classmethod
    @transaction.atomic
    def transition(
        cls,
        entity,
        *,
        object_id,
        target_status,
        user,
        reason="",
        idempotency_key=None,
        action="",
    ):
        if entity == "bom-versions":
            # The historical endpoint remains compatible, but BOMVersion now
            # has one and only one formal write service.  Never fall back to
            # the legacy scalar-status implementation on failure.
            from .bom_version_control_service import transition_bom_version

            return transition_bom_version(
                object_id=object_id,
                target_status=target_status,
                user=user,
                reason=reason,
                idempotency_key=idempotency_key,
                action=action,
            )
        if entity == "routing-versions":
            if target_status == "reviewed":
                from .routing_version_review_service import review_routing_version

                return review_routing_version(
                    object_id=object_id,
                    user=user,
                    reason=reason,
                    idempotency_key=idempotency_key,
                    action=action,
                )
            raise ProductionFoundationError(
                "ROUTING_VERSION_DEDICATED_CONTROL_REQUIRED",
                "工艺路线版本发布或失效必须由后续独立正式控制链办理；不得回退通用状态写入。",
            )
        if entity == "engineering-document-versions" and target_status == "reviewed":
            # Preserve the historical endpoint while enforcing one formal
            # draft -> reviewed path.  Review authority must never fall back
            # to the engineering-document release permission.
            from .engineering_document_version_review_service import (
                review_engineering_document_version,
            )

            return review_engineering_document_version(
                object_id=object_id,
                user=user,
                reason=reason,
                idempotency_key=idempotency_key,
                action=action,
            )
        if entity == "engineering-document-versions" and target_status == "released":
            # Keep the historical transition endpoint compatible while making
            # the dedicated release service the single reviewed -> released
            # write path.  The generic scalar transition cannot prove the
            # formal review, content fingerprint, idempotency or duty split.
            from .engineering_document_version_release_service import (
                release_engineering_document_version,
            )

            return release_engineering_document_version(
                object_id=object_id,
                user=user,
                reason=reason,
                idempotency_key=idempotency_key,
                action=action,
            )
        config = cls.CONFIG.get(entity)
        if not config:
            raise ProductionFoundationError("ENTITY_NOT_SUPPORTED", "不支持的工程状态对象。")
        model, state_field, action_code = config
        instance = model.objects.select_for_update().filter(pk=object_id).first()
        if not instance:
            raise ProductionFoundationError("OBJECT_NOT_FOUND", "待转换工程对象不存在。")
        if entity == "manufacturing-outputs":
            from .manufacturing_output_generation_service import ACTION, OBJECT
            from workflow_runtime.models import BusinessStateTransition
            if BusinessStateTransition.objects.filter(object_type=OBJECT, object_id=instance.pk, action_code=ACTION).exists():
                from .manufacturing_output_release_service import ACTION as RELEASE_ACTION, release_manufacturing_output
                if target_status == "released_to_manufacturing" and action == RELEASE_ACTION:
                    from .manufacturing_output_release_service import release_preflight
                    readiness = release_preflight(instance, user)
                    return release_manufacturing_output(user=user, output_id=instance.pk,
                        payload={"action": action, "reason": reason,
                            "sourceFingerprint": readiness.get("sourceFingerprint")}, idempotency_key=idempotency_key)
                raise ProductionFoundationError("MANUFACTURING_OUTPUT_RELEASE_NOT_OPEN",
                    "正式发布至制造必须使用独立发布动作及完整准入；通用状态写入不得绕过。")
        formal_manufacturing_eligibility = cls._formal_manufacturing_eligibility(
            entity, instance, target_status,
        )
        organization_id = _organization_id(model, {}, instance)
        before_status = getattr(instance, state_field)
        if before_status == target_status:
            return {"row": _snapshot(instance), "auditId": None, "idempotent": True}
        if (before_status, target_status) not in cls.ALLOWED[entity]:
            raise ProductionFoundationError(
                "STATE_TRANSITION_DENIED",
                f"不允许的工程状态转换：{before_status} -> {target_status}",
            )
        if entity == "engineering-rule-definitions" and target_status in {"reviewed", "released"}:
            try:
                validate_specification(instance.specification)
            except EngineeringRuleError as exc:
                raise ProductionFoundationError(exc.code, exc.message, exc.details)
        if (entity == "engineering-source-records" and target_status == "confirmed"
                and isinstance(instance.source_payload, dict)
                and "sourceFormatReference" in instance.source_payload):
            from .source_format_mapping_service import SourceFormatMappingError, mapped_order_inputs
            try:
                from .engineering_workbook_source_service import is_workbook_source
                if is_workbook_source(instance):
                    from .source_format_mapping_service import normalize_source_payload
                    if normalize_source_payload(instance.source_payload,company_id=instance.company_id)!=instance.source_payload:
                        raise SourceFormatMappingError('WORKBOOK_SOURCE_SNAPSHOT_CHANGED','工作簿规范快照与当前正式来源不一致')
                else:mapped_order_inputs(instance, {})
            except SourceFormatMappingError as exc:
                raise ProductionFoundationError(exc.code, exc.message, exc.details)
        decision = AuthorizationService.decide(
            user=user, action_code=action_code, organization_id=organization_id,
            business_object={"organizationId": organization_id, "entity": entity, "id": object_id},
        )
        if not decision.get("allowed"):
            raise ProductionFoundationError(
                decision.get("decisionCode", "PERMISSION_DENIED"),
                decision.get("reason", "当前账户无权执行工程状态动作。"),
                {"authorization": decision},
            )
        execution_chain = _actor_chain(user)
        before = _snapshot(instance)
        from .engineering_workbook_source_service import is_workbook_source,is_workbook_rule
        workbook_governed=(entity=='engineering-source-records' and is_workbook_source(instance)) or (
            entity=='engineering-rule-definitions' and is_workbook_rule(instance))
        mapping_governed = (
            entity == "engineering-rule-definitions"
            and instance.specification.get("contractCode")
            == "PCE-MATERIAL-REQUIREMENT-FORMULA-MAPPING-V1"
        )
        if workbook_governed or mapping_governed:
            from workflow_runtime.state_transitions import transition_business_object
            audit=_audit(user=user,organization_id=organization_id,action_code=action_code,instance=instance,
                before=before,after={**before,'status':target_status},reason=reason,authorization=decision,execution_chain=execution_chain)
            state_transition = transition_business_object(business_object=instance,object_type=model.__name__,source_state=before_status,
                target_state=target_status,action_code=action_code,operator=user,reason=reason,
                audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',allowed_transitions={(before_status,target_status)},
                version_field=None)
            return {'row':_snapshot(instance),'auditId':audit.pk,'idempotent':False,
                'relatedAuditIds':[],'authorization':decision,'executionChain':execution_chain,
                'transitionId':state_transition.pk}
        if entity == "engineering-rule-definitions":
            before.update({
                "rule_code": instance.rule_code,
                "rule_version": instance.version,
                "specification_hash": specification_hash(instance.specification),
                "expression_hash": expression_hash(instance.specification),
                "operator": execution_chain["account"],
            })
        if entity == "order-engineering-instances" and target_status == "source_confirmed":
            if instance.source_record.status != "confirmed":
                raise ProductionFoundationError(
                    "ENGINEERING_SOURCE_NOT_CONFIRMED",
                    "订单工程实例的来源记录尚未正式确认。",
                )
        if entity == "order-engineering-instances" and target_status == "calculated":
            completed = instance.calculation_records.filter(status="completed")
            if not completed.filter(derived_facts__isnull=False).exists():
                raise ProductionFoundationError(
                    "ENGINEERING_DERIVED_FACT_REQUIRED",
                    "订单工程实例必须至少具有一条完成计算及派生事实。",
                )
            # Keep this entry's permission, actor and completed-result checks;
            # the shared state service owns the status write and its fact.
            from workflow_runtime.state_transitions import transition_business_object
            setattr(instance, state_field, target_status)
            try:
                instance.full_clean()
            except ValidationError as exc:
                raise ProductionFoundationError(
                    "ENGINEERING_RELEASE_GATE_FAILED", "工程发布组合校验失败。", exc.message_dict,
                ) from exc
            finally:
                setattr(instance, state_field, before_status)
            audit = _audit(
                user=user, organization_id=organization_id, action_code=action_code,
                instance=instance, before=before, after={**before, state_field: target_status},
                reason=reason, authorization=decision, execution_chain=execution_chain,
            )
            transition_business_object(
                business_object=instance, object_type=model.__name__,
                source_state=before_status, target_state=target_status,
                action_code=action_code, operator=user, reason=reason,
                audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}",
                allowed_transitions=cls.ALLOWED[entity], status_field=state_field, version_field=None,
            )
            # Finalize this newly-created audit's authoritative readback inside
            # the same transaction, including auto_now fields set by save().
            audit.after_snapshot = {**audit.after_snapshot, "state": _snapshot(instance)}
            audit.save(update_fields=["after_snapshot"])
            return {
                "row": _snapshot(instance), "auditId": audit.pk, "idempotent": False,
                "relatedAuditIds": [], "authorization": decision, "executionChain": execution_chain,
                "formalManufacturingEligibility": formal_manufacturing_eligibility,
            }
        related_before = None
        if (
            entity == "manufacturing-outputs"
            and target_status == "released_to_manufacturing"
            and instance.definition_mode == "order_specific"
        ):
            order_instance = instance.order_engineering_instance
            if order_instance.status != "calculated":
                raise ProductionFoundationError(
                    "ORDER_ENGINEERING_NOT_CALCULATED",
                    "按单制造定义发布前，订单工程实例必须完成工程转换。",
                )
            related_before = _snapshot(order_instance)
        setattr(instance, state_field, target_status)
        try:
            instance.full_clean()
        except ValidationError as exc:
            raise ProductionFoundationError(
                "ENGINEERING_RELEASE_GATE_FAILED", "工程发布组合校验失败。", exc.message_dict,
            )
        instance.save(update_fields=[state_field, "updated_at"])
        related_audit_ids = []
        if related_before is not None:
            order_instance = instance.order_engineering_instance
            sales_item = order_instance.sales_order_item
            update_fields = ["manufacturing_output"]
            if instance.release_subject_type == "LONG_TERM_PRODUCT":
                sales_item.product_definition = instance.product
                sales_item.product_version = instance.product_version
                update_fields.extend(["product_definition", "product_version"])
            sales_item.manufacturing_output = instance
            try:
                sales_item.full_clean()
            except ValidationError as exc:
                raise ProductionFoundationError(
                    "SALES_ENGINEERING_LINK_INVALID",
                    "按单制造定义无法回写正式销售明细引用。",
                    exc.message_dict,
                )
            sales_item.save(update_fields=update_fields)
            order_instance.status = "released"
            order_instance.save(update_fields=["status", "updated_at"])
        if entity == "product-versions" and target_status == "released":
            ProductDefinition.objects.filter(pk=instance.product_id).update(version=instance.version_no)
        if entity == "engineering-document-versions" and target_status == "released":
            EngineeringDocument.objects.filter(pk=instance.document_id).update(
                version=instance.document_version,
            )
        after = _snapshot(instance)
        if entity == "engineering-rule-definitions":
            after.update({
                "rule_code": instance.rule_code,
                "rule_version": instance.version,
                "specification_hash": specification_hash(instance.specification),
                "expression_hash": expression_hash(instance.specification),
                "operator": execution_chain["account"],
            })
        audit = _audit(
            user=user, organization_id=organization_id, action_code=action_code,
            instance=instance, before=before, after=after, reason=reason,
            authorization=decision, execution_chain=execution_chain,
        )
        if related_before is not None:
            related_audit = _audit(
                user=user, organization_id=organization_id, action_code=action_code,
                instance=order_instance, before=related_before,
                after={
                    **_snapshot(order_instance),
                    "salesOrderItemId": order_instance.sales_order_item_id,
                    "manufacturingOutputId": instance.pk,
                },
                reason=reason or "按单制造定义正式发布并回写销售明细稳定引用",
                authorization=decision, execution_chain=execution_chain,
            )
            related_audit_ids.append(related_audit.pk)
        return {
            "row": after, "auditId": audit.pk, "idempotent": False,
            "relatedAuditIds": related_audit_ids,
            "authorization": decision, "executionChain": execution_chain,
            "formalManufacturingEligibility": formal_manufacturing_eligibility,
        }
    OrderEngineeringInstance,
