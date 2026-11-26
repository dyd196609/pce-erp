"""Wave 2 manufacturing structure domain services.

The service is industry-neutral. Cabinet and timber-door cases live in tests/fixtures,
while the production contract remains ProductTemplate + Configuration + versioned
BOM/Route + governed resource assignment.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import Q

from masterdata.models import ExternalIdentity, MasterDataWriteRequest, Material
from system.models import Process, Workshop

from .models import (
    BOMCompletenessRule,
    BOMItem,
    BOMItemRoutingAssignment,
    BOMVersion,
    ConfiguredProduct,
    ProductBOM,
    ProductConfiguration,
    ProductDefinition,
    ManufacturingApplicabilityScope,
    ProductTemplate,
    Routing,
    RoutingStep,
    RoutingVersion,
    WorkCenter,
)


class ManufacturingStructureError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _decimal(value):
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _matches_applicability(rule, context):
    """Small deterministic matcher; domain formulas stay in governed rules."""
    for key, expected in (rule or {}).items():
        actual = (context or {}).get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


EXACT_ROUTING_VERSION_CONTEXT_KEYS = (
    "organizationId",
    "salesOrderItemId",
    "orderEngineeringInstanceId",
    "orderEngineeringBaselineId",
    "engineeringCalculationId",
    "bomVersionId",
)


def _matches_stored_routing_version_context(version, expected_context):
    """Match one persisted order-engineering identity without name inference.

    ``manualStepApplicability`` is governed evidence attached to a routing
    version, not a generic applicability predicate.  The exact identity is
    used only when every required upstream object is supplied by the caller.
    """
    expected = expected_context if isinstance(expected_context, dict) else {}
    if any(expected.get(key) is None for key in EXACT_ROUTING_VERSION_CONTEXT_KEYS):
        return False
    applicability = version.applicability if isinstance(version.applicability, dict) else {}
    contract = applicability.get("manualStepApplicability")
    if not isinstance(contract, dict):
        return False
    if contract.get("contractVersion") != "PCE-ROUTING-MANUAL-APPLICABILITY-V1.0":
        return False
    contexts = contract.get("contexts")
    if not isinstance(contexts, dict):
        return False
    for context_key, stored in contexts.items():
        snapshot = stored.get("context") if isinstance(stored, dict) else None
        if not isinstance(snapshot, dict) or snapshot.get("contextKey") != context_key:
            continue
        if snapshot.get("routingId") != version.routing_id:
            continue
        if snapshot.get("routingVersionId") != version.pk:
            continue
        if all(snapshot.get(key) == expected[key] for key in EXACT_ROUTING_VERSION_CONTEXT_KEYS):
            return True
    return False


class ManufacturingStructureService:
    WAVE2_MIGRATION = "0019_manufacturing_structure_wave2"
    REQUIRED_TABLES = {
        "pde_product_template",
        "pde_product_configuration",
        "pde_configured_product",
        "pde_bom_completeness_rule",
        "pde_bom_item_routing_assignment",
    }

    @classmethod
    def resolve_current_version(
        cls, queryset, *, on_date=None, context=None, exact_version_context=None,
    ):
        """Resolve by lifecycle + effectivity + applicability, never max(version)."""
        on_date = on_date or date.today()
        effective_versions = []
        for version in queryset.filter(status="released"):
            if version.effective_date and on_date < version.effective_date:
                continue
            if version.expire_date and on_date > version.expire_date:
                continue
            effective_versions.append(version)

        if exact_version_context:
            exact_candidates = [
                version for version in effective_versions
                if _matches_stored_routing_version_context(version, exact_version_context)
            ]
            if len(exact_candidates) > 1:
                raise ManufacturingStructureError(
                    "AMBIGUOUS_EXACT_CONTEXT_VERSION",
                    "存在多个绑定同一订单工程上下文的正式版本；系统拒绝随机选择。",
                    {"versionIds": [item.pk for item in exact_candidates]},
                )
            if exact_candidates:
                return exact_candidates[0]

        candidates = []
        for version in effective_versions:
            if not _matches_applicability(version.applicability, context or {}):
                continue
            candidates.append(version)
        if not candidates:
            raise ManufacturingStructureError(
                "NO_EFFECTIVE_VERSION", "没有满足生命周期、日期和适用条件的正式版本。"
            )
        if len(candidates) > 1:
            raise ManufacturingStructureError(
                "AMBIGUOUS_EFFECTIVE_VERSION",
                "存在多个同时适用的正式版本；系统拒绝随机选择。",
                {"versionIds": [item.pk for item in candidates]},
            )
        return candidates[0]

    @classmethod
    def resolve_effective_routing(
        cls, engineering_instance, *, on_date=None, context=None, exact_version_context=None,
    ):
        """Resolve one ETO route without inventing a permanent ProductDefinition.

        Priority is order-instance route, then product-specific route, then
        category/process-type template. A present but invalid higher-priority
        definition blocks; it never silently falls through to a generic route.
        """
        on_date = on_date or date.today()
        context = context or {}
        base = Routing.objects.filter(
            company_id=engineering_instance.company_id,
            status="released",
            is_active=True,
        ).filter(
            Q(effective_from__isnull=True) | Q(effective_from__lte=on_date),
            Q(effective_to__isnull=True) | Q(effective_to__gte=on_date),
        )
        tiers = [
            (
                "ORDER_ENGINEERING",
                base.filter(
                    applicability_scope=ManufacturingApplicabilityScope.ORDER_ENGINEERING,
                    order_engineering_instance_id=engineering_instance.pk,
                ),
            ),
        ]
        if engineering_instance.product_id:
            tiers.append((
                "PRODUCT_DEFINITION",
                base.filter(
                    applicability_scope=ManufacturingApplicabilityScope.PRODUCT_DEFINITION,
                    product_id=engineering_instance.product_id,
                ),
            ))
        category_id = (
            engineering_instance.product_category_id
            or (
                engineering_instance.product.category_id
                if engineering_instance.product_id else None
            )
        )
        if category_id and engineering_instance.selected_process_type_id:
            tiers.append((
                "PRODUCT_CATEGORY",
                base.filter(
                    applicability_scope=ManufacturingApplicabilityScope.PRODUCT_CATEGORY,
                    product_category_id=category_id,
                    manufacturing_process_type_id=engineering_instance.selected_process_type_id,
                ),
            ))
        checked = []
        for scope, queryset in tiers:
            candidates = list(queryset.order_by("pk"))
            checked.append({"scope": scope, "routingIds": [row.pk for row in candidates]})
            if not candidates:
                continue
            if len(candidates) > 1:
                raise ManufacturingStructureError(
                    "AMBIGUOUS_EFFECTIVE_ROUTING",
                    "同一优先级存在多条同时有效工艺路线。",
                    {"scope": scope, "routingIds": [row.pk for row in candidates]},
                )
            routing = candidates[0]
            version = cls.resolve_current_version(
                routing.versions.all(), on_date=on_date, context=context,
                exact_version_context=exact_version_context,
            )
            return {
                "routing": routing,
                "routing_version": version,
                "resolved_scope": scope,
                "checked": checked,
            }
        raise ManufacturingStructureError(
            "NO_EFFECTIVE_ROUTING",
            "订单工程实例没有可唯一解释的有效工艺路线。",
            {"checked": checked},
        )

    @staticmethod
    def validate_effectivity_conflict(queryset, *, effective_date, expire_date, applicability):
        for version in queryset.filter(status="released"):
            existing_start = version.effective_date or date.min
            existing_end = version.expire_date or date.max
            candidate_start = effective_date or date.min
            candidate_end = expire_date or date.max
            same_scope = (version.applicability or {}) == (applicability or {})
            if same_scope and candidate_start <= existing_end and existing_start <= candidate_end:
                raise ValidationError("同一适用范围内的正式版本有效期不得重叠")

    @staticmethod
    def _quantity(item, parameters):
        quantity = _decimal(item.quantity)
        rule = item.quantity_rule or {}
        if not rule:
            return quantity
        kind = rule.get("kind")
        parameter = rule.get("parameter")
        if kind != "multiply_parameter" or not parameter:
            raise ManufacturingStructureError(
                "UNSUPPORTED_QUANTITY_RULE", "数量规则必须使用受治理的确定性规则类型。",
                {"lineNo": item.line_no, "rule": rule},
            )
        if parameter not in parameters:
            raise ManufacturingStructureError(
                "MISSING_PARAMETER", f"缺少BOM数量解析参数：{parameter}",
                {"lineNo": item.line_no},
            )
        return quantity * _decimal(parameters[parameter]) * _decimal(rule.get("factor", 1))

    @classmethod
    def explode_bom(cls, bom_version, *, order_quantity=1, parameters=None):
        parameters = parameters or {}
        items = list(
            bom_version.items.select_related("material", "uom", "parent_item").filter(
                is_active=True
            ).order_by("line_no")
        )
        children = defaultdict(list)
        for item in items:
            children[item.parent_item_id].append(item)
        rows = []
        visiting = set()

        def visit(parent_id, parent_factor, level):
            for item in children[parent_id]:
                if item.pk in visiting:
                    raise ManufacturingStructureError(
                        "BOM_CYCLE", "BOM层级存在循环引用。", {"lineNo": item.line_no}
                    )
                visiting.add(item.pk)
                net = parent_factor * cls._quantity(item, parameters)
                if item.scrap_rate_status == BOMItem.ScrapRateStatus.MAINTAINED:
                    gross = net / (Decimal("1") - _decimal(item.scrap_rate))
                else:
                    gross = None
                rows.append({
                    "itemId": item.pk,
                    "parentItemId": item.parent_item_id,
                    "level": level,
                    "lineNo": item.line_no,
                    "materialId": item.material_id,
                    "materialCode": item.material.code,
                    "materialName": item.material.name,
                    "itemRole": item.item_role,
                    "requirementType": item.requirement_type,
                    "supplyType": item.supply_type,
                    "netQuantity": net,
                    "grossQuantity": gross,
                    "uomId": item.uom_id,
                    "uomCode": item.uom.code,
                    "orderSpecification": item.order_specification,
                    "manufacturingAttributes": item.manufacturing_attributes,
                })
                visit(item.pk, net, level + 1)
                visiting.remove(item.pk)

        visit(None, _decimal(order_quantity), 0)
        if len(rows) != len(items):
            raise ManufacturingStructureError(
                "ORPHAN_BOM_ITEM", "存在无法从根节点到达的BOM项。"
            )
        return rows

    @staticmethod
    def validate_completeness(template, configuration, rows):
        findings = []
        for rule in template.completeness_rules.filter(is_active=True):
            if not _matches_applicability(rule.predicate, configuration.parameters):
                continue
            requirement = rule.requirement or {}
            matched = [
                row for row in rows
                if all(row.get(key) == value for key, value in requirement.items())
            ]
            if not matched:
                findings.append({
                    "ruleCode": rule.rule_code,
                    "severity": rule.severity,
                    "requirement": requirement,
                    "status": "BLOCK" if rule.severity == "block" else "WARNING",
                })
        return {
            "status": "BLOCK" if any(item["status"] == "BLOCK" for item in findings) else "PASS",
            "findings": findings,
        }

    @staticmethod
    def resolve_routings(rows, *, context=None):
        result = []
        for row in rows:
            assignments = BOMItemRoutingAssignment.objects.select_related(
                "routing_version__routing"
            ).filter(bom_item_id=row["itemId"], is_active=True).order_by("priority")
            matches = [
                assignment for assignment in assignments
                if _matches_applicability(assignment.selection_rule, context or {})
            ]
            if row["supplyType"] == "BUY" and matches:
                raise ManufacturingStructureError(
                    "BUY_INTERNAL_ROUTE", "外购组件不得解析内部工艺路线。",
                    {"itemId": row["itemId"]},
                )
            if row["supplyType"] in {"MAKE", "SUBCONTRACT"} and not matches:
                raise ManufacturingStructureError(
                    "ROUTING_NOT_RESOLVED", "自制或委外组件缺少适用工艺路线。",
                    {"itemId": row["itemId"], "supplyType": row["supplyType"]},
                )
            if len(matches) > 1 and matches[0].priority == matches[1].priority:
                raise ManufacturingStructureError(
                    "AMBIGUOUS_ROUTING", "组件存在相同优先级的多条适用路线。",
                    {"itemId": row["itemId"]},
                )
            result.append({
                "itemId": row["itemId"],
                "routingVersionId": matches[0].routing_version_id if matches else None,
                "routingCode": matches[0].routing_version.routing.routing_code if matches else None,
                "selectionRule": matches[0].selection_rule if matches else {},
            })
        return result

    @staticmethod
    def cost_rollup(rows):
        total = Decimal("0")
        buckets = defaultdict(lambda: Decimal("0"))
        for row in rows:
            material = Material.objects.get(pk=row["materialId"])
            quantity = row["grossQuantity"] if row["grossQuantity"] is not None else row["netQuantity"]
            cost = _decimal(material.standard_cost) * quantity
            if row["supplyType"] == "BUY":
                bucket = "purchasedComponent"
            elif row["supplyType"] == "SUBCONTRACT":
                bucket = "subcontract"
            elif row["itemRole"] == "material":
                bucket = "rawMaterial"
            else:
                bucket = "manufacturing"
            buckets[bucket] += cost
            total += cost
        return {"total": total, "buckets": dict(buckets)}

    @staticmethod
    def production_order_snapshot(configured_product, bom_version, routing_version, rows, routes):
        """Read-only consumability contract; persisting an order remains a later Wave."""
        route_by_item = {row["itemId"]: row for row in routes}
        return {
            "configuredProductId": configured_product.pk,
            "configurationId": configured_product.configuration_id,
            "productDefinitionId": configured_product.product_definition_id,
            "frozenBomVersionId": bom_version.pk,
            "frozenRoutingVersionId": routing_version.pk,
            "projectContext": configured_product.configuration.delivery_context,
            "requirements": [
                {
                    **row,
                    "resolvedRoutingVersionId": route_by_item[row["itemId"]]["routingVersionId"],
                    "demandChannel": {
                        "MAKE": "PRODUCTION",
                        "BUY": "PROCUREMENT",
                        "SUBCONTRACT": "SUBCONTRACT",
                        "MAKE_OR_BUY": "DECISION_REQUIRED",
                    }[row["supplyType"]],
                }
                for row in rows
            ],
        }

    @classmethod
    def foundation_facts(cls):
        tables = set(connection.introspection.table_names())
        missing = sorted(cls.REQUIRED_TABLES - tables)
        migration_applied = MigrationRecorder.Migration.objects.filter(
            app="pde", name=cls.WAVE2_MIGRATION,
        ).exists()
        migration_state = cls.resolve_migration_state(
            migration_applied=migration_applied,
            schema_available=not missing,
        )
        base_counts = {
            "Material": Material.objects.count(),
            "Operation": Process.objects.count(),
            "Workshop": Workshop.objects.count(),
            "WorkCenter": WorkCenter.objects.count(),
            "ExternalIdentity": ExternalIdentity.objects.count(),
            "FormalWriteRequest": MasterDataWriteRequest.objects.count(),
            "ProductDefinition": ProductDefinition.objects.count(),
            "BOM": ProductBOM.objects.count(),
            "BOMVersion": BOMVersion.objects.count(),
            "Routing": Routing.objects.count(),
            "RoutingVersion": RoutingVersion.objects.count(),
        }
        wave2_counts = {}
        if not missing:
            wave2_counts = {
                "ProductTemplate": ProductTemplate.objects.count(),
                "ProductConfiguration": ProductConfiguration.objects.count(),
                "ConfiguredProduct": ConfiguredProduct.objects.count(),
                "BOMCompletenessRule": BOMCompletenessRule.objects.count(),
                "BOMItemRoutingAssignment": BOMItemRoutingAssignment.objects.count(),
            }
        return {
            "factSource": "Django ORM / formal service",
            "formalWriteAuthorized": False,
            "formalWriteButtonDisabled": True,
            "migrationState": migration_state,
            "productionMigrationApplied": migration_applied,
            "missingWave2Tables": missing,
            "recordCounts": {**base_counts, **wave2_counts},
            "canonicalModels": {
                "product": "pde.ProductDefinition/ProductTemplate/ProductConfiguration/ConfiguredProduct",
                "bom": "pde.ProductBOM/BOMVersion/BOMItem",
                "routing": "pde.Routing/RoutingVersion/RoutingStep",
                "resource": "system.Workshop -> pde.WorkCenter -> pde.Equipment",
                "identity": "masterdata.ExternalIdentity/MasterDataWriteRequest",
            },
        }

    @staticmethod
    def resolve_migration_state(*, migration_applied, schema_available,
                                migration_authorized=False, migration_ready=True):
        """Keep readiness, execution permission, recorder state and schema facts separate."""
        if migration_applied:
            authorization = "COMPLETE"
            apply_status = "APPLIED"
        elif migration_authorized:
            authorization = "AUTHORIZED"
            apply_status = "PENDING_APPLY"
        else:
            authorization = "NOT_AUTHORIZED"
            apply_status = "NOT_APPLIED"
        return {
            "readiness": "READY" if migration_ready else "NOT_READY",
            "authorization": authorization,
            "applyStatus": apply_status,
            "schemaAvailability": "AVAILABLE" if schema_available else "UNAVAILABLE",
            "formalWriteAuthorization": "NOT_AUTHORIZED",
            "formalWriteEnabled": False,
        }
