"""SIMULATED_FOR_TEST only: real ORM/transaction EOR generation and allocation.

Fixtures use abstract area/count operations and declared published rules. They
do not claim that the current customer order has an operation mapping rule.
"""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from masterdata.models import CodeRule, Material, MasterDataWriteRequest, UnitOfMeasure
from pfm.models import Employee
from planning.models import Demand, PlanningRequirement, ProductionPlan
from sales.models import Customer, SalesOrder, SalesOrderItem
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Position,
    PositionResponsibility, Process, Responsibility, Role, RolePermission, User,
    UserRoleScopeAssignment,
)
from workflow_runtime.state_transitions import create_business_object_with_initial_state, transition_business_object
from workflow_runtime.models import BusinessStateTransition
from .models import (
    BOMVersion, CapacityProductType, EngineeringCalculationDetail,
    EngineeringCalculationRecord, EngineeringDerivedFact, EngineeringDocument,
    EngineeringDocumentVersion, EngineeringOperationRequirement, EngineeringRuleDefinition,
    EngineeringSourceRecord, ManufacturingProcessType, OrderEngineeringBaseline,
    OrderEngineeringInstance, ProductBOM, ProductCategory, ProductManufacturingOutput,
    ProductionPlanOperationRequirementAllocation, Routing, RoutingStep, RoutingVersion,
)
from . import operation_requirement_service as service
from .engineering_rule_foundation import specification_hash


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class OperationRequirementTests(TestCase):
    def initial(self, model, state, *, status_field="status", **fields):
        return create_business_object_with_initial_state(model=model, initial_state=state, status_field=status_field, **fields)

    def advance(self, obj, target, *, status_field="status"):
        source = getattr(obj, status_field)
        audit = OrganizationOperatingAuditRecord.objects.create(
            action_code="SIMULATED_FOR_TEST.fixture.transition", actor=self.user, organization=self.company,
            target_type=obj._meta.label, target_id=obj.pk, target_label=str(obj.pk),
            reason="SIMULATED_FOR_TEST uniform source fixture state",
            before_snapshot={status_field: source}, after_snapshot={status_field: target},
        )
        fields = {field.name for field in obj._meta.fields}
        return transition_business_object(business_object=obj, object_type=type(obj).__name__,
            source_state=source, target_state=target, action_code=audit.action_code, operator=self.user,
            reason=audit.reason, audit_reference=f"system.OrganizationOperatingAuditRecord:{audit.pk}",
            allowed_transitions={(source, target)}, status_field=status_field,
            version_field="version" if isinstance(getattr(obj, "version", None), int) else None,
            updated_at_field="updated_at" if "updated_at" in fields else None)

    def setUp(self):
        self.company = Company.objects.create(code="SIM-EOR", name="SIMULATED_FOR_TEST abstract company")
        self.department = Department.objects.create(company=self.company, code="SIM-EOR-D", name="Abstract department")
        self.user = User.objects.create_user(username="sim_eor_operator", company_id=self.company.pk)
        role = Role.objects.create(code="SIM-EOR-ROLE", name="SIMULATED_FOR_TEST operator")
        for code in ("production.engineering.calculation.execute", "production.engineering.calculation.view", "planning.view"):
            permission, _ = Permission.objects.get_or_create(code=code, defaults={"name": code, "module": "PRODUCTION"})
            RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(user=self.user, role=role, organization=self.company,
            scope_code="ORGANIZATION", active=True, business_hash="SIMULATED_FOR_TEST")
        responsibility = Responsibility.objects.create(code="SIM-EOR-RESP", name="Abstract operation requirement executor", status="ACTIVE", is_active=True)
        position = Position.objects.create(company=self.company, department=self.department, code="SIM-EOR-POS", name="Abstract executor", default_role=role)
        PositionResponsibility.objects.create(position=position, responsibility=responsibility, is_primary=True, active=True)
        Employee.objects.create(user=self.user, employee_no="SIM-EOR-E", full_name="SIMULATED_FOR_TEST", department_ref=self.department, position_ref=position, status="active")
        self.pcs = UnitOfMeasure.objects.create(company_id=self.company.pk, code="PCS", name="件", dimension="count")
        self.area = UnitOfMeasure.objects.create(company_id=self.company.pk, code="m2", name="平方米", dimension="area")
        self.material = Material.objects.create(company_id=self.company.pk, code="SIM-EOR-M", name="Abstract output", base_uom=self.pcs, unit="PCS", material_type="finished", is_produced=True)
        customer = Customer.objects.create(company=self.company, code="SIM-EOR-C", name="SIMULATED_FOR_TEST")
        self.order = self.initial(SalesOrder, "draft", company=self.company, department=self.department, customer=customer,
            order_no="SO-SIM-ABSTRACT", order_date=date.today(), required_delivery_date=date.today(), created_by=self.user,
            delivery_information={"businessPurpose": "DEVELOPMENT_VALIDATION", "source": "SIMULATED_FOR_TEST"})
        self.advance(self.order, "confirmed")
        self.item = SalesOrderItem.objects.create(sales_order=self.order, line_no=1, material=self.material, quantity=5,
            uom=self.pcs, required_date=date.today(), engineering_mode="ORDER_ENGINEERED", customer_product_name="Abstract object")
        self.category = ProductCategory.objects.create(company=self.company, code="SIM-CATEGORY", name="Abstract category")
        self.kind = ManufacturingProcessType.objects.create(company=self.company, code="SIM-PROCESS-TYPE", name="Abstract process type")
        self.product_type = CapacityProductType.objects.create(company=self.company, code="SIM-CAPACITY-TYPE", name="Abstract type",
            product_category=self.category, manufacturing_process_type=self.kind)
        payload = {"sourceKind": "SIMULATED_FOR_TEST", "area": "20", "count": "12"}
        self.source = self.initial(EngineeringSourceRecord, "draft", company=self.company, source_no="SIM-EOR-SOURCE",
            source_name="SIMULATED_FOR_TEST frozen input", source_type="manual_confirmed", source_version="V1",
            source_payload=payload, content_hash=digest(payload))
        self.advance(self.source, "confirmed")
        self.instance = self.initial(OrderEngineeringInstance, "draft", company=self.company, instance_no="SIM-EOR-OEI",
            sales_order_item=self.item, product_category=self.category, selected_process_type=self.kind, source_record=self.source)
        self.advance(self.instance, "source_confirmed")
        self.advance(self.instance, "calculated")
        self.op_area = Process.objects.create(company=self.company, code="SIM-OP-A", name="Abstract operation A", calculation_basis="area", calculation_uom=self.area, standard_hours=Decimal("999"))
        self.op_count = Process.objects.create(company=self.company, code="SIM-OP-B", name="Abstract operation B", calculation_basis="count", calculation_uom=self.pcs, standard_hours=Decimal("123"))
        self.rule_counter = 0
        source_rule_area = self.make_rule(self.op_area, self.area, "source_area", output_domain="DERIVED_FACT")
        source_rule_count = self.make_rule(self.op_count, self.pcs, "source_count", output_domain="DERIVED_FACT")
        self.source_calc = self.initial(EngineeringCalculationRecord, "draft", company=self.company, scope="order_engineering",
            source_record=self.source, sales_order_item=self.item, engineering_instance=self.instance,
            calculation_no="SIM-PRESERVED-CALC-3", rule_set_version="SIMULATED_FOR_TEST-V1", input_hash=digest(payload),
            rule_graph_hash=digest([source_rule_area.pk, source_rule_count.pk]), result_hash=digest(["20", "12"]),
            trace={"sourceKind": "SIMULATED_FOR_TEST", "preservePurpose": "CALC3_IMMUTABLE_DERIVED_SOURCE"})
        self.advance(self.source_calc, "prepared")
        self.advance(self.source_calc, "running")
        self.fact_area = self.make_source_fact(source_rule_area, self.area, "source_area", "20", 1)
        self.fact_count = self.make_source_fact(source_rule_count, self.pcs, "source_count", "12", 2)
        self.source_calc.started_at, self.source_calc.finished_at = timezone.now(), timezone.now()
        self.source_calc.save(update_fields=("started_at", "finished_at"))
        self.advance(self.source_calc, "completed")
        self.rule_area = self.make_rule(self.op_area, self.area, "source_area")
        self.rule_count = self.make_rule(self.op_count, self.pcs, "source_count")
        CodeRule.objects.create(company_id=self.company.pk, entity_type="production_engineering_calculation", prefix="SIM-EOR-", date_format="", seq_length=4)
        self.baseline = self.initial(OrderEngineeringBaseline, "draft", company=self.company, sales_order=self.order,
            baseline_no="SIM-EOR-BASE", sequence=1, reason="SIMULATED_FOR_TEST", candidate_hash=digest("candidate"),
            snapshot_hash=digest("frozen"), scope_item_count=1, confirmable_item_count=1, blocker_count=0,
            blocker_summary={}, created_by=self.user)
        self.baseline.confirmed_by, self.baseline.confirmed_at = self.user, timezone.now()
        self.baseline.save(update_fields=("confirmed_by", "confirmed_at"))
        self.advance(self.baseline, "confirmed")
        self.bom = self.initial(ProductBOM, "draft", company=self.company, applicability_scope="ORDER_ENGINEERING",
            order_engineering_instance=self.instance, bom_code="SIM-EOR-BOM", name="SIMULATED_FOR_TEST")
        self.bom_version = self.initial(BOMVersion, "draft", bom=self.bom, bom_version="V1", bom_scope="order_specific",
            order_engineering_instance=self.instance, source_calculation=self.source_calc)
        self.advance(self.bom_version, "reviewed")
        self.advance(self.bom_version, "released")
        self.route = self.initial(Routing, "draft", company=self.company, applicability_scope="PRODUCT_CATEGORY",
            product_category=self.category, manufacturing_process_type=self.kind, routing_code="SIM-TYPE-A", name="Abstract route")
        self.version = self.initial(RoutingVersion, "draft", routing=self.route, routing_version="V1")
        self.step_area = RoutingStep.objects.create(routing_version=self.version, sequence=1, operation=self.op_area,
            standard_hours=Decimal("555"), operation_parameters={"applicability": {"contractVersion": "PCE-ROUTING-STEP-APPLICABILITY-V1.0", "mode": "MANDATORY"}})
        self.step_count = RoutingStep.objects.create(routing_version=self.version, sequence=2, operation=self.op_count,
            predecessor_sequences=[1], operation_parameters={"applicability": {"contractVersion": "PCE-ROUTING-STEP-APPLICABILITY-V1.0", "mode": "MANDATORY"}})
        self.repeat_step = RoutingStep.objects.create(routing_version=self.version, sequence=3, operation=self.op_area, predecessor_sequences=[2])
        self.advance(self.version, "reviewed")
        self.advance(self.version, "released")
        document = EngineeringDocument.objects.create(document_no="SIM-EOR-DOC", document_name="SIMULATED_FOR_TEST",
            document_type="technical", release_subject_type="ORDER_ENGINEERED_PRODUCT", order_engineering_instance=self.instance,
            product_bom=self.bom, routing=self.route)
        self.document = self.initial(EngineeringDocumentVersion, "draft", document=document, document_name="SIMULATED_FOR_TEST",
            document_version="V1", release_subject_type="ORDER_ENGINEERED_PRODUCT", order_engineering_instance=self.instance,
            order_engineering_baseline=self.baseline, engineering_calculation=self.source_calc,
            related_bom=self.bom_version, related_routing=self.version)
        self.advance(self.document, "reviewed")
        self.advance(self.document, "released")
        self.output = self.initial(ProductManufacturingOutput, "draft", status_field="release_status", release_subject_type="ORDER_ENGINEERED_PRODUCT",
            definition_mode="order_specific", engineering_status="ready", order_engineering_instance=self.instance,
            order_engineering_baseline=self.baseline, engineering_calculation=self.source_calc, bom_version=self.bom_version,
            routing_version=self.version, engineering_document_version=self.document)
        self.advance(self.output, "engineering_review", status_field="release_status")
        self.advance(self.output, "released_to_manufacturing", status_field="release_status")
        demand = self.initial(Demand, "draft", demand_no="SIM-EOR-DEMAND", source_type="sales_order", source_document_type="SalesOrder",
            source_document_id=str(self.order.pk), source_document_no=self.order.order_no, sales_order_item=self.item,
            manufacturing_output=self.output, material=self.material, required_qty=5, required_date=date.today(), department=self.department,
            reason="SIMULATED_FOR_TEST", acceptance_marker="SIMULATED_FOR_TEST", created_by=self.user)
        self.advance(demand, "confirmed")
        requirement = self.initial(PlanningRequirement, "draft", requirement_no="SIM-EOR-REQUIREMENT", demand=demand,
            material=self.material, demand_qty=5, available_qty=2, net_required_qty=3, required_date=date.today(), supply_type="production",
            calculation_facts={"sourceKind": "SIMULATED_FOR_TEST", "inventoryAllocationStatus": "ALLOCATED", "allocatedInventoryQty": "2"}, created_by=self.user)
        self.advance(requirement, "calculated")
        self.advance(requirement, "confirmed")
        self.plan = self.initial(ProductionPlan, "draft", plan_no="SIM-EOR-PLAN", planning_requirement=requirement, material=self.material,
            planned_qty=3, required_date=date.today(), source_id=str(requirement.pk), confirmed_by=self.user)
        self.advance(self.plan, "confirmed")

    def make_rule(self, operation, uom, source_name, *, basis="PER_BASIS_QUANTITY", basis_quantity="1", output_domain="OPERATION_REQUIREMENT"):
        self.rule_counter += 1
        input_name = f"raw_{source_name}" if output_domain == "DERIVED_FACT" else source_name
        output_name = source_name if output_domain == "DERIVED_FACT" else f"workload_{self.rule_counter}"
        output = {"canonicalName": output_name, "valueType": "decimal", "unit": uom.code,
                  "unitDimension": uom.dimension, "resultDomain": output_domain}
        if output_domain == "OPERATION_REQUIREMENT":
            output.update(operationId=operation.pk, productTypeId=self.product_type.pk, quantityBasis=basis,
                basisQuantity=basis_quantity, basisUomId=self.pcs.pk, sourceScope="SALES_ORDER_ITEM")
        spec = {"description": "SIMULATED_FOR_TEST explicit abstract rule", "rulePackage": {"code": "SIM.EOR", "version": "V1"},
            "expression": input_name, "inputs": [{"canonicalName": input_name, "valueType": "decimal", "unit": uom.code,
                "unitDimension": uom.dimension, "sourceType": "ENGINEERING_DERIVED", "required": True, "unitRequired": True}],
            "outputs": [output], "dependencies": [], "applicability": {"scope": "order_engineering"},
            "decimalPrecision": 18, "outputScale": 6, "roundingMode": "ROUND_HALF_UP", "priority": 1,
            "sourceEvidence": {"reference": "SIMULATED_FOR_TEST"}}
        rule = self.initial(EngineeringRuleDefinition, "draft", company=self.company, rule_code=f"SIM-EOR-RULE-{self.rule_counter}",
            rule_name="Abstract rule", version="V1", rule_kind="formula", specification=spec)
        self.advance(rule, "reviewed")
        self.advance(rule, "released")
        return rule

    def make_source_fact(self, rule, uom, field, value, sequence):
        detail = self.initial(EngineeringCalculationDetail, "running", calculation=self.source_calc, sequence=sequence,
            rule=rule, rule_code=rule.rule_code, rule_version=rule.version, expression_snapshot=rule.specification["expression"],
            input_snapshot={"sourceKind": "SIMULATED_FOR_TEST", f"raw_{field}": {"value": value, "unit": uom.code}}, dependency_snapshot=[], output_name=field,
            output_value={"decimal": value}, uom=uom, precision=18, rounding="ROUND_HALF_UP", started_at=timezone.now())
        detail.finished_at = timezone.now()
        detail.save(update_fields=("finished_at",))
        self.advance(detail, "succeeded")
        return self.initial(EngineeringDerivedFact, "active", calculation=self.source_calc, rule=rule, source_detail=detail,
            fact_code=field, canonical_field=field, sequence=sequence, value={"decimal": value}, value_type="decimal",
            source_type="ENGINEERING_DERIVED", uom=uom, source_path=f"SIMULATED_FOR_TEST.details[{sequence}]",
            trace={"sourceKind": "SIMULATED_FOR_TEST", "resultDomain": "DERIVED_FACT", "detailId": detail.pk,
                   "ruleCode": rule.rule_code, "ruleVersion": rule.version,
                   "specificationHash": specification_hash(rule.specification)})

    def generate(self, *, fact=None, rule=None, key="generate-area", user=None):
        return service.OperationRequirementService.generate(user=user or self.user, source_calculation_id=self.source_calc.pk,
            source_fact_id=(fact or self.fact_area).pk, rule_id=(rule or self.rule_area).pk, idempotency_key=key, reason="SIMULATED_FOR_TEST")

    def allocate(self, result, *, step=None, key="allocate-area", user=None):
        return service.OperationRequirementService.allocate(user=user or self.user, production_plan_id=self.plan.pk,
            operation_requirement_id=result["operationRequirementId"], routing_step_id=(step or self.step_area).pk,
            idempotency_key=key, reason="SIMULATED_FOR_TEST")

    def assert_rejected(self, action, code):
        with self.assertRaises(Exception) as caught:
            action()
        self.assertEqual(getattr(caught.exception, "code", None), code)

    def test_generation_allocation_reading_are_generic_and_preserve_frozen_source(self):
        preserved = {"calculation": list(EngineeringCalculationRecord.objects.values()), "derived": list(EngineeringDerivedFact.objects.values()),
                     "routing": list(RoutingStep.objects.values()), "plan": list(ProductionPlan.objects.values())}
        with patch("pde.engineering_calculation_service.EngineeringCalculationService.execute", side_effect=AssertionError("Legacy executor forbidden")):
            area = self.generate()
            count = self.generate(fact=self.fact_count, rule=self.rule_count, key="generate-count")
            a = self.allocate(area)
            b = self.allocate(count, step=self.step_count, key="allocate-count")
        self.assertEqual(EngineeringOperationRequirement.objects.get(pk=area["operationRequirementId"]).workload_quantity, Decimal("20"))
        self.assertEqual(EngineeringCalculationRecord.objects.get(pk=area["calculationId"]).scope, "operation_requirement")
        self.assertEqual(EngineeringCalculationRecord.objects.get(pk=count["calculationId"]).scope, "operation_requirement")
        latest_original = EngineeringCalculationRecord.objects.filter(sales_order_item=self.item, scope="order_engineering").order_by("-revision", "-pk").first()
        self.assertEqual(latest_original.pk, self.source_calc.pk)
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.get(pk=a["allocationId"]).allocated_quantity, Decimal("60"))
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.get(pk=b["allocationId"]).allocated_quantity, Decimal("36"))
        demand_area = service.process_demand_for_plan(self.plan, self.output, self.item, {"stepId": self.step_area.pk, "operationId": self.op_area.pk}, company_id=self.company.pk)
        self.assertEqual((demand_area["quantity"], demand_area["uomId"]), (Decimal("60"), self.area.pk))
        readback = service.OperationRequirementService.read(user=self.user, production_plan_id=self.plan.pk)
        self.assertIn(str(a["allocationId"]), json.dumps(readback, default=str))
        self.source_calc.refresh_from_db()
        self.assertEqual(list(EngineeringCalculationRecord.objects.filter(pk=self.source_calc.pk).values()), preserved["calculation"])
        self.assertEqual(list(EngineeringDerivedFact.objects.values()), preserved["derived"])
        self.assertEqual(list(RoutingStep.objects.values()), preserved["routing"])
        self.assertEqual(list(ProductionPlan.objects.values()), preserved["plan"])
        self.assertIsNone(self.source_calc.supersedes_id)
        self.assertEqual(self.source_calc.status, "completed")
        self.assertEqual(EngineeringDerivedFact.objects.filter(trace__resultDomain="DERIVED_FACT").count(), 2)

    def test_same_key_replay_does_not_create_run_detail_requirement_audit_or_ledger(self):
        first = self.generate()
        self.allocate(first)
        models = (EngineeringCalculationRecord, EngineeringCalculationDetail, EngineeringOperationRequirement,
                  ProductionPlanOperationRequirementAllocation, OrganizationOperatingAuditRecord, MasterDataWriteRequest, CodeRule)
        before = {model.__name__: list(model.objects.values()) for model in models}
        replay = self.generate()
        self.assertEqual(replay["operationRequirementId"], first["operationRequirementId"])
        self.allocate(first)
        for model in models:
            self.assertEqual(list(model.objects.values()), before[model.__name__])

    def test_new_semantic_alias_binds_one_audit_and_repeated_alias_is_zero_write(self):
        first = self.generate()
        before = (EngineeringCalculationRecord.objects.count(), EngineeringCalculationDetail.objects.count(),
                  EngineeringOperationRequirement.objects.count(), OrganizationOperatingAuditRecord.objects.count())
        replay = self.generate(key="registered-semantic-alias")
        self.assertEqual(replay["operationRequirementId"], first["operationRequirementId"])
        self.assertEqual((EngineeringCalculationRecord.objects.count(), EngineeringCalculationDetail.objects.count(),
                          EngineeringOperationRequirement.objects.count()), before[:3])
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), before[3] + 1)
        bound_count = OrganizationOperatingAuditRecord.objects.count()
        self.generate(key="registered-semantic-alias")
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), bound_count)
        self.assert_rejected(lambda: self.generate(fact=self.fact_count, rule=self.rule_count, key="registered-semantic-alias"), "IDEMPOTENCY_PAYLOAD_CONFLICT")

    def test_unknown_quantity_basis_and_missing_operation_mapping_are_rejected(self):
        bad = self.make_rule(self.op_area, self.area, "source_area", basis="UNKNOWN")
        self.assert_rejected(lambda: self.generate(rule=bad), "QUANTITY_BASIS_MISSING")
        derived_rule = self.fact_area.rule
        self.assert_rejected(lambda: self.generate(rule=derived_rule), "OPERATION_RULE_MAPPING_MISSING")
        self.assertEqual(EngineeringOperationRequirement.objects.count(), 0)

    def test_missing_origin_fk_and_uom_mismatch_are_rejected(self):
        self.fact_area.source_detail = None
        self.fact_area.save(update_fields=("source_detail",))
        self.assert_rejected(lambda: self.generate(), "SOURCE_FACT_MISMATCH")
        self.fact_area.source_detail = EngineeringCalculationDetail.objects.get(calculation=self.source_calc, sequence=1)
        self.fact_area.save(update_fields=("source_detail",))
        wrong = self.make_rule(self.op_count, self.area, "source_area")
        self.assert_rejected(lambda: self.generate(rule=wrong), "OPERATION_UOM_MISMATCH")

    def test_cross_company_source_and_unauthorized_user_are_rejected(self):
        foreign = Company.objects.create(code="SIM-FOREIGN", name="SIMULATED_FOR_TEST foreign scope")
        foreign_rule = self.make_rule(self.op_area, self.area, "source_area")
        EngineeringRuleDefinition.objects.filter(pk=foreign_rule.pk).update(company=foreign)
        self.assert_rejected(lambda: self.generate(rule=foreign_rule), "OPERATION_RULE_MAPPING_MISSING")
        denied = User.objects.create_user(username="sim_eor_denied", company_id=self.company.pk)
        self.assert_rejected(lambda: self.generate(user=denied), "PERMISSION_DENIED")

    def test_repeated_process_step_cannot_copy_one_eor_quantity_twice(self):
        requirement = self.generate()
        self.allocate(requirement)
        before = OrganizationOperatingAuditRecord.objects.count()
        self.assert_rejected(lambda: self.allocate(requirement, step=self.repeat_step, key="repeat-step"), "PROCESS_STEP_MAPPING_AMBIGUOUS")
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.count(), 1)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), before)

    def test_plan_quantity_cannot_exceed_the_frozen_sales_item_budget(self):
        requirement = self.generate()
        self.plan.planned_qty = Decimal("6")
        self.plan.save(update_fields=("planned_qty",))
        parent_requirement = self.plan.planning_requirement
        parent_requirement.net_required_qty = Decimal("6")
        parent_requirement.save(update_fields=("net_required_qty",))
        self.assert_rejected(lambda: self.allocate(requirement), "ALLOCATION_SCOPE_EXCEEDED")
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.count(), 0)

    def test_total_basis_rejects_undeclared_partial_allocation(self):
        total = self.make_rule(self.op_area, self.area, "source_area", basis="SOURCE_SCOPE_TOTAL", basis_quantity="5")
        requirement = self.generate(rule=total)
        self.assert_rejected(lambda: self.allocate(requirement), "SOURCE_SCOPE_PARTIAL_ALLOCATION_BLOCKED")
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.count(), 0)

    def test_total_basis_full_scope_keeps_workload_once(self):
        total = self.make_rule(self.op_area, self.area, "source_area", basis="SOURCE_SCOPE_TOTAL", basis_quantity="5")
        requirement = self.generate(rule=total)
        self.plan.planned_qty = Decimal("5")
        self.plan.save(update_fields=("planned_qty",))
        parent_requirement = self.plan.planning_requirement
        parent_requirement.net_required_qty, parent_requirement.available_qty = Decimal("5"), Decimal("0")
        parent_requirement.save(update_fields=("net_required_qty", "available_qty"))
        result = self.allocate(requirement)
        row = ProductionPlanOperationRequirementAllocation.objects.get(pk=result["allocationId"])
        self.assertEqual(row.allocated_quantity, Decimal("20"))
        self.assertEqual(row.source_quantity, Decimal("5"))

    def test_source_snapshot_drift_rejects_allocation_without_new_audit(self):
        requirement = self.generate()
        self.source.content_hash = "f" * 64
        self.source.save(update_fields=("content_hash",))
        before = OrganizationOperatingAuditRecord.objects.count()
        self.assert_rejected(lambda: self.allocate(requirement), "OPERATION_FACT_CHANGED")
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), before)

    def test_client_idempotency_key_cannot_represent_different_rule_payload(self):
        self.generate(key="fixed-client-key")
        self.generate(fact=self.fact_count, rule=self.rule_count, key="count-already-exists")
        self.assert_rejected(lambda: self.generate(fact=self.fact_count, rule=self.rule_count, key="fixed-client-key"), "IDEMPOTENCY_PAYLOAD_CONFLICT")

    def test_source_producer_wrong_domain_cannot_be_made_valid_by_fact_trace(self):
        producer = self.fact_area.rule
        changed = deepcopy(producer.specification)
        changed["outputs"][0]["resultDomain"] = "OPERATION_REQUIREMENT"
        EngineeringRuleDefinition.objects.filter(pk=producer.pk).update(specification=changed)
        self.assert_rejected(lambda: self.generate(), "SOURCE_OUTPUT_DOMAIN_MISMATCH")
        self.assertEqual(EngineeringOperationRequirement.objects.count(), 0)

    def test_missing_product_type_fk_is_not_inferred_from_route_or_type_names(self):
        mapping = self.make_rule(self.op_area, self.area, "source_area")
        changed = deepcopy(mapping.specification)
        changed["outputs"][0].pop("productTypeId")
        EngineeringRuleDefinition.objects.filter(pk=mapping.pk).update(specification=changed)
        self.assert_rejected(lambda: self.generate(rule=mapping), "ALLOCATION_PRODUCT_TYPE_MISSING")

    def test_allocation_fraction_without_declared_precision_policy_is_rejected(self):
        rule = self.make_rule(self.op_area, self.area, "source_area", basis_quantity="7")
        result = self.generate(rule=rule)
        self.assert_rejected(lambda: self.allocate(result), "ALLOCATION_PRECISION_UNCONFIRMED")
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.count(), 0)

    def test_allocation_client_key_conflict_is_checked_before_natural_replay(self):
        area = self.generate()
        count = self.generate(fact=self.fact_count, rule=self.rule_count, key="generation-count")
        self.allocate(area, key="allocation-key-a")
        self.allocate(count, step=self.step_count, key="allocation-key-b")
        self.assert_rejected(lambda: self.allocate(count, step=self.step_count, key="allocation-key-a"), "IDEMPOTENCY_PAYLOAD_CONFLICT")
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.count(), 2)

    def test_allocation_alias_is_persistently_bound_without_duplicate_bridge(self):
        area = self.generate()
        count = self.generate(fact=self.fact_count, rule=self.rule_count, key="generation-count")
        first = self.allocate(area)
        self.allocate(count, step=self.step_count, key="allocate-count")
        before = OrganizationOperatingAuditRecord.objects.count()
        alias = self.allocate(area, key="allocation-semantic-alias")
        self.assertEqual(alias["allocationId"], first["allocationId"])
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.count(), 2)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), before + 1)
        self.allocate(area, key="allocation-semantic-alias")
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), before + 1)
        self.assert_rejected(lambda: self.allocate(count, step=self.step_count, key="allocation-semantic-alias"), "IDEMPOTENCY_PAYLOAD_CONFLICT")

    def test_generated_run_result_hash_tampering_blocks_consumption(self):
        result = self.generate()
        EngineeringCalculationRecord.objects.filter(pk=result["calculationId"]).update(result_hash="0" * 64)
        self.assert_rejected(lambda: self.allocate(result), "OPERATION_FACT_CHANGED")
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.count(), 0)

    def test_generated_run_history_missing_cannot_be_replaced_by_status_only(self):
        result = self.generate()
        BusinessStateTransition.objects.filter(object_type="EngineeringCalculationRecord", object_id=result["calculationId"], target_state="completed").delete()
        self.assert_rejected(lambda: self.allocate(result), "OPERATION_STATE_HISTORY_MISSING")
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.count(), 0)

    def test_date_preview_product_type_mismatch_blocks_before_capacity_or_dates(self):
        from .daily_capacity_views import production_plan_date_preview
        requirement = self.generate()
        self.allocate(requirement)
        other_type = CapacityProductType.objects.create(company=self.company, code="OTHER-SIM-TYPE", name="Other abstract type",
            product_category=self.category, manufacturing_process_type=self.kind)
        readiness = {"productTypeId": other_type.pk, "planningReady": True, "steps": [{
            "stepId": self.step_area.pk, "sequence": 1, "operationId": self.op_area.pk,
            "applicability": {"result": "REQUIRED"}, "capacityDateMode": "INDEPENDENT_DATE"}]}
        with patch("pde.daily_capacity_views.DailyCapacityReadinessService.assess", return_value=readiness), \
             patch("pde.daily_capacity_views.StandardCapacity.objects.get", side_effect=AssertionError("Unrelated SC must not be queried")), \
             patch("pde.daily_capacity_views.working_date_window", side_effect=AssertionError("Dates must not be calculated")):
            result = production_plan_date_preview(self.plan, start_date=date.today(), company_id=self.company.pk)
        self.assertFalse(result["previewReady"])
        self.assertEqual(result["dates"], [])
        self.assertEqual(result["processDemandBlockers"][0]["code"], "CAPACITY_PRODUCT_TYPE_SOURCE_MISMATCH")

    def test_reader_cannot_replace_fixed_order_item_with_another_context(self):
        requirement = self.generate()
        self.allocate(requirement)
        other_item = SalesOrderItem.objects.create(sales_order=self.order, line_no=2, material=self.material,
            quantity=1, uom=self.pcs, required_date=date.today(), engineering_mode="ORDER_ENGINEERED")
        self.assert_rejected(lambda: service.process_demand_for_plan(self.plan, self.output, other_item,
            {"stepId": self.step_area.pk, "operationId": self.op_area.pk}, company_id=self.company.pk), "ALLOCATION_SOURCE_MISMATCH")
