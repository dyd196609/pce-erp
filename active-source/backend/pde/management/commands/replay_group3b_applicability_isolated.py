import json
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pde.manufacturing_structure_service import ManufacturingStructureService
from pde.models import (
    BOMItem,
    BOMVersion,
    ManufacturingApplicabilityScope,
    ManufacturingProcessType,
    OrderEngineeringInstance,
    ProductBOM,
    ProductCategory,
    ProductDefinition,
    ProductVersion,
    Routing,
    RoutingStep,
    RoutingVersion,
)
from system.models import Company, Process
from sales.models import SalesOrderItem


class Command(BaseCommand):
    help = "Replay the frozen Group 3B source only in an explicitly isolated database."

    def add_arguments(self, parser):
        parser.add_argument("--confirm-isolated", action="store_true")

    def handle(self, *args, **options):
        database_path = Path(settings.DATABASES["default"]["NAME"]).resolve()
        production_path = (Path(settings.BASE_DIR) / "db.sqlite3").resolve()
        if not options["confirm_isolated"] or database_path == production_path:
            raise CommandError("ISOLATED_DATABASE_REQUIRED: refusing Group 3B replay")
        source_path = Path(settings.BASE_DIR) / "masterdata" / "group3_comparison_source.json"
        source = json.loads(source_path.read_text(encoding="utf-8"))
        route_rows = source["routingRows"]
        step_rows = source["routingStepRows"]
        if len(route_rows) != 42 or len(step_rows) != 1137:
            raise CommandError("FROZEN_SOURCE_COUNT_MISMATCH")
        before = self._counts()
        if any(before[key] for key in ("routing", "routingVersion", "routingStep", "processType")):
            raise CommandError(f"ISOLATED_REPLAY_TARGET_NOT_EMPTY: {before}")
        if before["productDefinition"] or before["productVersion"]:
            raise CommandError("FAKE_PRODUCT_GUARD: isolated base must preserve ProductDefinition=0")

        expected_categories = {"房门", "柜体", "饰面"}
        companies = [
            company for company in Company.objects.order_by("pk")
            if set(ProductCategory.objects.filter(company=company).values_list("name", flat=True))
            >= expected_categories
            and Process.objects.filter(company=company, is_active=True).count() == 33
        ]
        if len(companies) != 1:
            raise CommandError(f"ONE_ELIGIBLE_COMPANY_REQUIRED: found={len(companies)}")
        company = companies[0]
        categories = {
            row.name: row for row in ProductCategory.objects.filter(
                company=company, name__in={item["applicableProductCategory"] for item in route_rows},
            )
        }
        if set(categories) != expected_categories:
            raise CommandError(f"CATEGORY_SET_MISMATCH: {sorted(categories)}")
        operations = {row.name: row for row in Process.objects.filter(company=company, is_active=True)}
        accepted_aliases = {"拉丝": "拉丝/打磨"}
        resolved_operation_names = {
            accepted_aliases.get(row["operationName"], row["operationName"])
            for row in step_rows
        }
        missing_operations = sorted(resolved_operation_names - set(operations))
        if missing_operations:
            raise CommandError(f"UNRESOLVED_OPERATION: {missing_operations}")

        route_steps = defaultdict(list)
        for row in step_rows:
            route_steps[row["routeCode"]].append(row)

        process_types = {}
        created_routes = {}
        with transaction.atomic():
            for row in route_rows:
                category_name = row["applicableProductCategory"]
                type_name = row["routeName"]
                if not type_name.endswith(category_name):
                    raise CommandError(f"ROUTE_IDENTITY_NOT_EXPLAINABLE: {row['routeCode']}")
                type_name = type_name[:-len(category_name)]
                type_code = row["routeCode"].split("/", 1)[0]
                process_type = process_types.get(type_code)
                if process_type is None:
                    process_type = ManufacturingProcessType(
                        company=company, code=type_code, name=type_name,
                        description="02工艺路线受控来源（隔离回放）",
                    )
                    process_type.full_clean()
                    process_type.save()
                    process_types[type_code] = process_type
                elif process_type.name != type_name:
                    raise CommandError(f"PROCESS_TYPE_CODE_CONFLICT: {type_code}")
                routing = Routing(
                    company=company,
                    routing_code=row["routeCode"],
                    name=row["routeName"],
                    applicability_scope=ManufacturingApplicabilityScope.PRODUCT_CATEGORY,
                    product_category=categories[category_name],
                    manufacturing_process_type=process_type,
                    status="released",
                    is_active=True,
                )
                routing.full_clean()
                routing.save()
                version = RoutingVersion(
                    routing=routing,
                    routing_version="SYSTEM_INITIAL_VERSION",
                    revision=1,
                    status="released",
                    approval_state="workflow_approved",
                    applicability={},
                )
                version.full_clean()
                version.save()
                for step_row in sorted(route_steps[row["routeCode"]], key=lambda item: item["sequence"]):
                    predecessor = step_row.get("predecessorSequence")
                    step = RoutingStep(
                        routing_version=version,
                        sequence=step_row["sequence"],
                        operation=operations[
                            accepted_aliases.get(step_row["operationName"], step_row["operationName"])
                        ],
                        predecessor_sequences=[predecessor] if predecessor else [],
                        effective_transition_mode=None,
                        instruction="02工艺路线受控来源（隔离回放）",
                    )
                    step.full_clean()
                    step.save()
                created_routes[row["routeCode"]] = routing

            resolution_scopes = Counter()
            for route in created_routes.values():
                instance = SimpleNamespace(
                    pk=None,
                    company_id=company.pk,
                    product_id=None,
                    product_category_id=route.product_category_id,
                    selected_process_type_id=route.manufacturing_process_type_id,
                )
                resolved = ManufacturingStructureService.resolve_effective_routing(instance)
                if resolved["routing"].pk != route.pk:
                    raise CommandError(f"EFFECTIVE_ROUTING_MISMATCH: {route.routing_code}")
                resolution_scopes[resolved["resolved_scope"]] += 1

            first_route = next(iter(created_routes.values()))
            sales_item = SalesOrderItem.objects.filter(
                sales_order__company=company,
            ).order_by("pk").first()
            source_record = first_route.product_category.company.engineering_source_records.order_by("pk").first()
            if not sales_item or not source_record:
                raise CommandError("ORDER_ENGINEERING_SUPPORT_FACTS_REQUIRED")
            engineering_instance = OrderEngineeringInstance(
                company=company,
                instance_no="ISOLATED-G3B-EFFECTIVE-ROUTING",
                sales_order_item=sales_item,
                product_category=first_route.product_category,
                selected_process_type=first_route.manufacturing_process_type,
                source_record=source_record,
                status="source_confirmed",
            )
            engineering_instance.full_clean()
            engineering_instance.save()
            instance_resolution = ManufacturingStructureService.resolve_effective_routing(
                engineering_instance,
            )
            if instance_resolution["routing"].pk != first_route.pk:
                raise CommandError("ORDER_ENGINEERED_EFFECTIVE_ROUTING_MISMATCH")

        after = self._counts()
        duplicate_count = sum(
            1 for count in Counter(
                (row.product_category_id, row.manufacturing_process_type_id)
                for row in Routing.objects.filter(
                    applicability_scope=ManufacturingApplicabilityScope.PRODUCT_CATEGORY,
                    status="released", is_active=True,
                )
            ).values() if count != 1
        )
        expected_kitting = {"白坯检验", "试装", "成品检"}
        transition_errors = []
        for step in RoutingStep.objects.select_related("operation"):
            expected = "KITTING" if step.operation.name in expected_kitting else "GENERAL"
            actual = step.effective_transition_mode or step.operation.default_transition_mode
            if actual != expected:
                transition_errors.append({"stepId": step.pk, "operation": step.operation.name})
        result = {
            "database": str(database_path),
            "sourceRouting": len(route_rows),
            "sourceRoutingStep": len(step_rows),
            "before": before,
            "after": after,
            "routingReplay": after["routing"],
            "routingStepReplay": after["routingStep"],
            "uniqueResolution": sum(resolution_scopes.values()),
            "resolutionScopes": dict(resolution_scopes),
            "orderEngineeredInstanceId": engineering_instance.pk,
            "orderEngineeredEffectiveRouting": "PASS",
            "duplicate": duplicate_count,
            "unresolved": 42 - sum(resolution_scopes.values()),
            "generalKitting": "PASS" if not transition_errors else "FAIL",
            "transitionErrors": transition_errors,
            "fakeProductDefinitionCreated": after["productDefinition"] - before["productDefinition"],
            "fakeProductVersionCreated": after["productVersion"] - before["productVersion"],
            "bomWrite": (
                after["bom"] + after["bomVersion"] + after["bomItem"]
                - before["bom"] - before["bomVersion"] - before["bomItem"]
            ),
        }
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))

    @staticmethod
    def _counts():
        return {
            "productDefinition": ProductDefinition.objects.count(),
            "productVersion": ProductVersion.objects.count(),
            "processType": ManufacturingProcessType.objects.count(),
            "routing": Routing.objects.count(),
            "routingVersion": RoutingVersion.objects.count(),
            "routingStep": RoutingStep.objects.count(),
            "bom": ProductBOM.objects.count(),
            "bomVersion": BOMVersion.objects.count(),
            "bomItem": BOMItem.objects.count(),
        }
