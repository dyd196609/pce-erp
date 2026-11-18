"""SIMULATED_FOR_TEST: versioned manufacturing configuration and real EOR facts.

Only an isolated Django test database is populated. Abstract operations and
canonical selectors prove generic behavior; they are not customer-order rules.
"""

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from masterdata.models import UnitOfMeasure
from sales.models import SalesOrder, SalesOrderItem
from system.models import OrganizationOperatingAuditRecord, Permission, Process, Role, RolePermission, Workshop
from workflow_runtime.models import BusinessStateTransition
from .manufacturing_configuration_service import CREATE, RELEASE, ManufacturingConfigurationService
from . import operation_requirement_service as service
from . import tests_operation_requirement as fixtures
from .models import (
    CapacityProductType, EngineeringCalculationDetail, EngineeringCalculationRecord,
    EngineeringDerivedFact, EngineeringOperationRequirement, EngineeringRuleDefinition,
    ManufacturingMode, OrderEngineeringInstance, ProductCategory, StandardCapacity,
    WorkCenter, WorkCenterOperationCapability,
)


CONTRACT = "PCE-MANUFACTURING-EOR-RULE-V1"


class ManufacturingEorConfigurationTests(TestCase):
    # Borrow fixture construction only, so unittest does not rerun old test methods.
    initial = fixtures.OperationRequirementTests.initial
    advance = fixtures.OperationRequirementTests.advance
    make_rule = fixtures.OperationRequirementTests.make_rule
    make_source_fact = fixtures.OperationRequirementTests.make_source_fact
    generate = fixtures.OperationRequirementTests.generate
    allocate = fixtures.OperationRequirementTests.allocate

    def setUp(self):
        fixtures.OperationRequirementTests.setUp(self)
        self.workshop = Workshop.objects.create(company=self.company, department=self.department,
            code="SIM-CFG-WS", name="Abstract manufacturing area")
        self.center = WorkCenter.objects.create(company=self.company, workshop=self.workshop,
            department=self.department, code="SIM-CFG-WC", name="Abstract resource")
        self.mode = self.make_mode(self.area, "SIM-AREA-MODE")
        self.capability = WorkCenterOperationCapability.objects.create(work_center=self.center,
            operation=self.op_area, assignment_role="primary", is_active=True)
        self.capacity = self.make_capacity(self.op_area, self.area, "SIM-CFG-CAP-A")
        self.mapping = self.make_mapping(self.fact_area, self.op_area, self.area,
            mode=self.mode, capacity=self.capacity)

    def make_mode(self, uom, code):
        mode = self.initial(ManufacturingMode, "draft", company=self.company, code=code,
            name="Abstract quantity mode", version="V1", uom=uom,
            effective_from=date.today() - timedelta(days=1))
        self.advance(mode, "reviewed")
        self.advance(mode, "released")
        return mode

    def make_capacity(self, operation, uom, code, **overrides):
        fields = dict(company=self.company, code=code, name="Abstract daily capacity",
            resource_scope="work_center", work_center=self.center, operation=operation,
            product_type=self.product_type, measurement_status="measured", quantity=Decimal("500"),
            uom=uom, time_basis="day", time_basis_quantity=Decimal("1"), time_unit="DAY",
            standard_hours=Decimal("888"), is_active=True,
            effective_from=date.today() - timedelta(days=1))
        fields.update(overrides)
        return StandardCapacity.objects.create(**fields)

    def make_mapping(self, fact, operation, uom, *, mode, capacity, manufacturing_overrides=None,
                     output_overrides=None, release=True, dynamic_source_basis=False):
        self.rule_counter += 1
        spec = deepcopy(self.rule_area.specification)
        spec["expression"] = fact.canonical_field
        spec["inputs"] = [{"canonicalName": fact.canonical_field, "sourceCanonicalField": fact.canonical_field,
            "valueType": "decimal", "unit": fact.uom.code, "unitDimension": fact.uom.dimension,
            "sourceType": "ENGINEERING_DERIVED", "required": True, "unitRequired": True}]
        spec["outputs"][0].update(canonicalName=f"abstract_workload_{self.rule_counter}",
            unit=uom.code, unitDimension=uom.dimension, operationId=operation.pk,
            productTypeId=self.product_type.pk, uomId=uom.pk)
        spec["outputs"][0].update(output_overrides or {})
        if dynamic_source_basis:
            output = spec["outputs"][0]
            output.pop("basisQuantity")
            output.pop("basisUomId")
            output.update(quantityBasis="SOURCE_SCOPE_TOTAL", basisQuantitySource="SALES_ORDER_ITEM",
                basisUomSource="SALES_ORDER_ITEM")
        spec["manufacturing"] = {"contractVersion": CONTRACT, "modeId": mode.pk,
            "modeVersion": mode.version, "workCenterId": self.center.pk, "standardCapacityId": capacity.pk,
            "factoryScope": {"companyId": self.company.pk, "workshopId": self.workshop.pk},
            "sourceSelector": {"canonicalField": fact.canonical_field,
                "producerRuleId": fact.source_detail.rule_id,
                "producerRuleVersion": fact.source_detail.rule_version,
                "traceEquals": {"sourceKind": "SIMULATED_FOR_TEST"}},
            "factDisposition": "GENERATE_EOR"}
        spec["manufacturing"].update(manufacturing_overrides or {})
        rule = self.initial(EngineeringRuleDefinition, "draft", company=self.company,
            rule_code=f"SIM-CONFIG-RULE-{self.rule_counter}", rule_name="Abstract configured rule",
            version="V1", rule_kind="formula", specification=spec)
        if release:
            self.advance(rule, "reviewed")
            self.advance(rule, "released")
        return rule

    def counts(self):
        return tuple(model.objects.count() for model in (EngineeringCalculationRecord,
            EngineeringCalculationDetail, EngineeringOperationRequirement, OrganizationOperatingAuditRecord))

    def assert_blocked(self, rule=None, *, expected_code=None):
        before = self.counts()
        ready = service.OperationRequirementService.generate_readiness(user=self.user,
            source_calculation_id=self.source_calc.pk, source_fact_id=self.fact_area.pk,
            rule_id=(rule or self.mapping).pk)
        self.assertFalse(ready["ready"], ready)
        self.assertEqual(ready["businessWriteCount"], 0)
        if expected_code:
            self.assertEqual(ready["blockers"][0]["code"], expected_code)
        with self.assertRaises(service.OperationRequirementError):
            self.generate(rule=rule or self.mapping)
        self.assertEqual(self.counts(), before)
        return ready["blockers"][0]["code"]

    def replacement(self, **manufacturing_overrides):
        return self.make_mapping(self.fact_area, self.op_area, self.area,
            mode=self.mode, capacity=self.capacity, manufacturing_overrides=manufacturing_overrides)

    def test_configured_generation_preserves_source_and_returns_persisted_trace(self):
        before = list(EngineeringCalculationRecord.objects.filter(pk=self.source_calc.pk).values())
        facts = list(EngineeringDerivedFact.objects.order_by("pk").values())
        with patch("pde.engineering_calculation_service.EngineeringCalculationService.execute",
                   side_effect=AssertionError("The original calculation must not run")):
            result = self.generate(rule=self.mapping)
        req = EngineeringOperationRequirement.objects.get(pk=result["operationRequirementId"])
        self.assertEqual((req.manufacturing_mode_id, req.work_center_id, req.standard_capacity_id),
            (self.mode.pk, self.center.pk, self.capacity.pk))
        self.assertEqual(req.workload_quantity, Decimal("20"))
        self.assertEqual(req.uom_id, self.area.pk)
        self.assertEqual(len(req.source_hash), 64)
        self.assertEqual(len(req.input_hash), 64)
        api_fact = result["operationRequirement"]
        self.assertEqual(api_fact["manufacturingModeId"], self.mode.pk)
        self.assertEqual(api_fact["workCenterId"], self.center.pk)
        self.assertEqual(api_fact["standardCapacityId"], self.capacity.pk)
        self.assertEqual(api_fact["sourceSnapshot"], req.calculation.trace["sourceSnapshot"])
        self.assertIn("manufacturing", api_fact["sourceSnapshot"])
        readback = service.OperationRequirementService.read_source_conversion(user=self.user,
            source_calculation_id=self.source_calc.pk, source_fact_ids=[self.fact_area.pk])
        proof = readback["facts"][0]["requirements"][0]
        for key in ("sourceHash", "inputHash", "ruleVersion", "manufacturingModeId", "workCenterId", "standardCapacityId"):
            self.assertEqual(proof[key], api_fact[key])
        self.assertEqual(list(EngineeringCalculationRecord.objects.filter(pk=self.source_calc.pk).values()), before)
        self.assertEqual(list(EngineeringDerivedFact.objects.order_by("pk").values()), facts)

    def test_generic_area_length_set_and_piece_modes_use_declared_units(self):
        length = UnitOfMeasure.objects.create(company_id=self.company.pk, code="m", name="米", dimension="length")
        sets = UnitOfMeasure.objects.create(company_id=self.company.pk, code="SET", name="套", dimension="count")
        cases = [(self.fact_area, self.op_area, self.area, "20", self.mode, self.capacity),
                 (self.fact_count, self.op_count, self.pcs, "12", None, None)]
        for index, (uom, quantity) in enumerate(((length, "17"), (sets, "3")), start=3):
            operation = Process.objects.create(company=self.company, code=f"SIM-CFG-OP-{index}",
                name=f"Abstract operation {index}", calculation_basis=uom.dimension, calculation_uom=uom)
            producer = self.make_rule(operation, uom, f"source_measure_{index}", output_domain="DERIVED_FACT")
            fact = self.make_source_fact(producer, uom, f"source_measure_{index}", quantity, index)
            cases.append((fact, operation, uom, quantity, None, None))
        original_facts = list(EngineeringDerivedFact.objects.order_by("pk").values())
        for index, (fact, operation, uom, quantity, mode, capacity) in enumerate(cases):
            with self.subTest(unit=uom.code):
                mode = mode or self.make_mode(uom, f"SIM-GENERIC-MODE-{index}")
                capacity = capacity or self.make_capacity(operation, uom, f"SIM-GENERIC-CAP-{index}")
                WorkCenterOperationCapability.objects.get_or_create(work_center=self.center, operation=operation,
                    defaults={"assignment_role": "primary", "is_active": True})
                mapping = self.make_mapping(fact, operation, uom, mode=mode, capacity=capacity)
                result = self.generate(fact=fact, rule=mapping, key=f"generic-{index}")
                req = EngineeringOperationRequirement.objects.get(pk=result["operationRequirementId"])
                self.assertEqual((req.workload_quantity, req.uom_id), (Decimal(quantity), uom.pk))
        self.assertEqual(EngineeringOperationRequirement.objects.count(), 4)
        self.assertEqual(list(EngineeringDerivedFact.objects.order_by("pk").values()), original_facts)

    def test_same_request_replay_has_no_business_or_audit_writes(self):
        first = self.generate(rule=self.mapping)
        before = self.counts()
        again = self.generate(rule=self.mapping)
        self.assertEqual(first["operationRequirementId"], again["operationRequirementId"])
        self.assertEqual(again["businessWriteCount"], 0)
        self.assertEqual(self.counts(), before)

    def test_wrong_mode_version_is_blocked(self):
        self.assert_blocked(self.replacement(modeVersion="V2"), expected_code="MANUFACTURING_MODE_INVALID")

    def test_unpublished_mode_is_blocked(self):
        mode = self.initial(ManufacturingMode, "draft", company=self.company, code="SIM-DRAFT-MODE",
            name="Draft mode", version="V1", uom=self.area)
        self.assert_blocked(self.replacement(modeId=mode.pk), expected_code="MANUFACTURING_MODE_INVALID")

    def test_mode_unit_mismatch_is_blocked(self):
        mode = self.make_mode(self.pcs, "SIM-WRONG-UNIT-MODE")
        self.assert_blocked(self.replacement(modeId=mode.pk), expected_code="MANUFACTURING_UOM_MISMATCH")

    def test_wrong_factory_company_is_blocked(self):
        self.assert_blocked(self.replacement(factoryScope={"companyId": self.company.pk + 1000,
            "workshopId": self.workshop.pk}), expected_code="MANUFACTURING_FACTORY_SCOPE_MISMATCH")

    def test_wrong_factory_workshop_is_blocked(self):
        another = Workshop.objects.create(company=self.company, department=self.department,
            code="SIM-OTHER-WS", name="Another abstract manufacturing area")
        self.assert_blocked(self.replacement(factoryScope={"companyId": self.company.pk,
            "workshopId": another.pk}), expected_code="MANUFACTURING_FACTORY_SCOPE_MISMATCH")

    def test_missing_or_inactive_work_center_is_blocked(self):
        self.assert_blocked(self.replacement(workCenterId=999999), expected_code="MANUFACTURING_RESOURCE_INVALID")
        self.center.is_active = False
        self.center.save(update_fields=("is_active",))
        self.assert_blocked(expected_code="MANUFACTURING_RESOURCE_INVALID")

    def test_capacity_product_mismatch_is_blocked(self):
        other = CapacityProductType.objects.create(company=self.company, code="SIM-OTHER-TYPE",
            name="Another abstract type", product_category=self.category, manufacturing_process_type=self.kind)
        self.capacity.product_type = other
        self.capacity.save(update_fields=("product_type",))
        self.assert_blocked(expected_code="MANUFACTURING_PRODUCT_TYPE_MISMATCH")

    def test_rule_product_type_must_match_the_source_category(self):
        category = ProductCategory.objects.create(company=self.company, code="SIM-OTHER-CATEGORY",
            name="Another abstract source category")
        other = CapacityProductType.objects.create(company=self.company, code="SIM-FOREIGN-CATEGORY-TYPE",
            name="Another abstract category type", product_category=category, manufacturing_process_type=self.kind)
        capacity = self.make_capacity(self.op_area, self.area, "SIM-OTHER-CATEGORY-CAP", product_type=other)
        mapping = self.make_mapping(self.fact_area, self.op_area, self.area, mode=self.mode,
            capacity=capacity, output_overrides={"productTypeId": other.pk})
        self.assert_blocked(mapping, expected_code="MANUFACTURING_PRODUCT_TYPE_MISMATCH")

    def test_missing_process_still_blocks_before_generation(self):
        mapping = self.make_mapping(self.fact_area, self.op_area, self.area, mode=self.mode,
            capacity=self.capacity, output_overrides={"operationId": 999999})
        self.assert_blocked(mapping, expected_code="OPERATION_RULE_MAPPING_MISSING")

    def test_capacity_resource_mismatch_is_blocked(self):
        other = WorkCenter.objects.create(company=self.company, workshop=self.workshop,
            code="SIM-OTHER-WC", name="Another abstract resource")
        self.capacity.work_center = other
        self.capacity.save(update_fields=("work_center",))
        self.assert_blocked(expected_code="MANUFACTURING_CAPACITY_INVALID")

    def test_missing_capacity_is_blocked(self):
        self.assert_blocked(self.replacement(standardCapacityId=999999), expected_code="MANUFACTURING_CAPACITY_INVALID")

    def test_zero_capacity_remains_zero_and_blocks_generation(self):
        self.capacity.quantity = Decimal("0")
        self.capacity.measurement_status = "zero_capacity"
        self.capacity.save(update_fields=("quantity", "measurement_status"))
        self.assert_blocked(expected_code="MANUFACTURING_CAPACITY_INVALID")
        self.capacity.refresh_from_db()
        self.assertEqual(self.capacity.quantity, Decimal("0"))

    def test_unknown_or_inactive_capacity_blocks_generation(self):
        self.capacity.quantity = None
        self.capacity.measurement_status = "not_determinable"
        self.capacity.save(update_fields=("quantity", "measurement_status"))
        self.assert_blocked(expected_code="MANUFACTURING_CAPACITY_INVALID")
        self.capacity.quantity = Decimal("500")
        self.capacity.measurement_status = "measured"
        self.capacity.is_active = False
        self.capacity.save(update_fields=("quantity", "measurement_status", "is_active"))
        self.assert_blocked(expected_code="MANUFACTURING_CAPACITY_INVALID")

    def test_capacity_unit_mismatch_is_blocked(self):
        self.capacity.uom = self.pcs
        self.capacity.save(update_fields=("uom",))
        self.assert_blocked(expected_code="MANUFACTURING_UOM_MISMATCH")

    def test_source_selector_requires_exact_field_producer_version_and_trace(self):
        selector = deepcopy(self.mapping.specification["manufacturing"]["sourceSelector"])
        for changed in ({"canonicalField": "unrelated_measure"},
                        {"producerRuleId": self.rule_count.pk}, {"producerRuleVersion": "V2"},
                        {"traceEquals": {"sourceKind": "UNPROVEN"}}):
            with self.subTest(changed=changed):
                self.assert_blocked(self.replacement(sourceSelector={**selector, **changed}),
                    expected_code="MANUFACTURING_SOURCE_SELECTOR_MISMATCH")

    def test_rule_must_be_published_and_fact_disposition_must_generate(self):
        draft = self.make_mapping(self.fact_area, self.op_area, self.area,
            mode=self.mode, capacity=self.capacity, release=False)
        self.assert_blocked(draft, expected_code="OPERATION_RULE_MAPPING_MISSING")
        self.assert_blocked(self.replacement(factDisposition="FACT_ONLY"), expected_code="MANUFACTURING_CONFIG_INVALID")

    def test_standard_hours_are_never_read_by_generation(self):
        def forbidden_read(_instance):
            raise AssertionError("Standard hours must not enter manufacturing EOR generation")
        def allow_orm_hydration(instance, value):
            instance.__dict__["standard_hours"] = value
        guard = property(forbidden_read, allow_orm_hydration)
        with patch.object(StandardCapacity, "standard_hours", guard), \
             patch.object(Process, "standard_hours", guard):
            result = self.generate(rule=self.mapping)
            self.assertEqual(Decimal(result["operationRequirement"]["workloadQuantity"]), Decimal("20"))

    def test_generated_requirement_blocks_source_selector_drift_on_read(self):
        self.generate(rule=self.mapping)
        changed = deepcopy(self.fact_area.trace)
        changed["sourceKind"] = "UNPROVEN"
        self.fact_area.trace = changed
        self.fact_area.save(update_fields=("trace",))
        before = self.counts()
        result = service.OperationRequirementService.read_source_conversion(user=self.user,
            source_calculation_id=self.source_calc.pk, source_fact_ids=[self.fact_area.pk])
        fact = result["facts"][0]
        self.assertEqual(fact["requirements"], [])
        self.assertEqual(fact["conversionStatusCode"], "BLOCKED")
        self.assertTrue(fact["blockers"])
        self.assertEqual(self.counts(), before)

    def test_published_mode_core_is_immutable(self):
        self.mode.name = "Changed core"
        with self.assertRaises(ValidationError):
            self.mode.save()
        with self.assertRaises(ValidationError):
            ManufacturingMode.objects.filter(pk=self.mode.pk).update(uom=self.pcs)
        with self.assertRaises(ValidationError):
            ManufacturingMode.objects.filter(pk=self.mode.pk).delete()

    def grant_configuration_permissions(self, *codes):
        role = Role.objects.get(code="SIM-EOR-ROLE")
        for code in codes:
            permission, _ = Permission.objects.get_or_create(code=code,
                defaults={"name": code, "module": "PRODUCTION"})
            RolePermission.objects.get_or_create(role=role, permission=permission)

    def configuration_package(self):
        spec = deepcopy(self.mapping.specification)
        spec["manufacturing"].pop("modeId")
        spec["manufacturing"]["modeCode"] = "SIM-PACKAGE-MODE"
        return {"contractVersion": CONTRACT, "companyId": self.company.pk,
            "modes": [{"code": "SIM-PACKAGE-MODE", "name": "Abstract package mode",
                "version": "V1", "uomId": self.area.pk}],
            "rules": [{"ruleCode": "SIM-PACKAGE-RULE", "ruleName": "Abstract package rule",
                "version": "V1", "ruleKind": "formula", "specification": spec}],
            "pendingRules": []}

    def configuration_snapshot(self):
        return {model._meta.label: list(model.objects.order_by("pk").values())
            for model in (ManufacturingMode, EngineeringRuleDefinition,
                OrganizationOperatingAuditRecord, BusinessStateTransition)}

    def test_configuration_requires_both_create_and_release_permissions(self):
        package = self.configuration_package()
        before = self.configuration_snapshot()
        with self.assertRaises(service.OperationRequirementError) as caught:
            ManufacturingConfigurationService.configure(user=self.user, package=package, reason="SIMULATED_FOR_TEST")
        self.assertEqual(caught.exception.code, "PERMISSION_DENIED")
        self.assertEqual(self.configuration_snapshot(), before)
        self.grant_configuration_permissions(CREATE)
        with self.assertRaises(service.OperationRequirementError) as caught:
            ManufacturingConfigurationService.configure(user=self.user, package=package, reason="SIMULATED_FOR_TEST")
        self.assertEqual(caught.exception.code, "PERMISSION_DENIED")
        self.assertEqual(self.configuration_snapshot(), before)

    def test_configuration_publishes_with_real_audit_history_and_is_idempotent(self):
        self.grant_configuration_permissions(CREATE, RELEASE)
        package = self.configuration_package()
        source = list(EngineeringDerivedFact.objects.order_by("pk").values())
        result = ManufacturingConfigurationService.configure(user=self.user, package=package, reason="SIMULATED_FOR_TEST")
        mode = ManufacturingMode.objects.get(pk=result["manufacturingModes"][0]["id"])
        rule = EngineeringRuleDefinition.objects.get(pk=result["rules"][0]["id"])
        self.assertEqual((mode.status, rule.status), ("released", "released"))
        self.assertEqual(rule.specification["manufacturing"]["modeId"], mode.pk)
        for obj in (mode, rule):
            history = list(BusinessStateTransition.objects.filter(object_type=type(obj).__name__,
                object_id=obj.pk).order_by("version"))
            self.assertEqual([(row.source_state, row.target_state) for row in history],
                [("", "draft"), ("draft", "reviewed"), ("reviewed", "released")])
            for transition in history:
                self.assertEqual(transition.operator_id, self.user.pk)
                audit_id = int(transition.audit_reference.split(":")[-1])
                audit = OrganizationOperatingAuditRecord.objects.get(pk=audit_id)
                self.assertEqual((audit.actor_id, audit.organization_id), (self.user.pk, self.company.pk))
        before = self.configuration_snapshot()
        repeated = ManufacturingConfigurationService.configure(user=self.user, package=package, reason="SIMULATED_FOR_TEST")
        self.assertEqual(repeated, result)
        self.assertEqual(self.configuration_snapshot(), before)
        self.assertEqual(list(EngineeringDerivedFact.objects.order_by("pk").values()), source)

    def test_configuration_failure_rolls_back_mode_rule_audit_and_transitions(self):
        self.grant_configuration_permissions(CREATE, RELEASE)
        package = self.configuration_package()
        package["rules"][0]["specification"]["manufacturing"]["standardCapacityId"] = 999999
        before = self.configuration_snapshot()
        with self.assertRaises(service.OperationRequirementError) as caught:
            ManufacturingConfigurationService.configure(user=self.user, package=package, reason="SIMULATED_FOR_TEST")
        self.assertEqual(caught.exception.code, "MANUFACTURING_CAPACITY_INVALID")
        self.assertEqual(self.configuration_snapshot(), before)

    def test_configuration_existing_version_cannot_be_overwritten(self):
        self.grant_configuration_permissions(CREATE, RELEASE)
        package = self.configuration_package()
        ManufacturingConfigurationService.configure(user=self.user, package=package, reason="SIMULATED_FOR_TEST")
        package["rules"][0]["specification"]["expression"] += " * 2"
        before = self.configuration_snapshot()
        with self.assertRaises(service.OperationRequirementError) as caught:
            ManufacturingConfigurationService.configure(user=self.user, package=package, reason="SIMULATED_FOR_TEST")
        self.assertEqual(caught.exception.code, "MANUFACTURING_VERSION_CONFLICT")
        self.assertEqual(self.configuration_snapshot(), before)

    def test_one_dynamic_total_rule_uses_each_order_quantity_and_unit(self):
        mapping = self.make_mapping(self.fact_area, self.op_area, self.area, mode=self.mode,
            capacity=self.capacity, dynamic_source_basis=True)
        fixed_specification = deepcopy(mapping.specification)
        first = self.generate(rule=mapping)
        sets = UnitOfMeasure.objects.create(company_id=self.company.pk, code="SIM-DYNAMIC-SET",
            name="Abstract set unit", dimension="count")
        order = self.initial(SalesOrder, "draft", company=self.company, department=self.department,
            customer=self.order.customer, order_no="SO-SIM-SECOND-ABSTRACT", order_date=date.today(),
            required_delivery_date=date.today(), created_by=self.user,
            delivery_information={"businessPurpose": "DEVELOPMENT_VALIDATION", "source": "SIMULATED_FOR_TEST"})
        self.advance(order, "confirmed")
        item = SalesOrderItem.objects.create(sales_order=order, line_no=1, material=self.material,
            quantity=Decimal("9"), uom=sets, required_date=date.today(), engineering_mode="ORDER_ENGINEERED")
        instance = self.initial(OrderEngineeringInstance, "draft", company=self.company,
            instance_no="SIM-DYNAMIC-SECOND-OEI", sales_order_item=item, product_category=self.category,
            selected_process_type=self.kind, source_record=self.source)
        self.advance(instance, "source_confirmed")
        self.advance(instance, "calculated")
        calculation = self.initial(EngineeringCalculationRecord, "draft", company=self.company,
            scope="order_engineering", source_record=self.source, sales_order_item=item,
            engineering_instance=instance, calculation_no="SIM-DYNAMIC-SECOND-CALC",
            rule_set_version="SIMULATED_FOR_TEST", input_hash=fixtures.digest("second-input"),
            rule_graph_hash=fixtures.digest("second-rule-graph"), result_hash=fixtures.digest("second-result"),
            trace={"sourceKind": "SIMULATED_FOR_TEST"})
        self.advance(calculation, "prepared")
        self.advance(calculation, "running")
        original_calculation = self.source_calc
        self.source_calc = calculation
        try:
            fact = self.make_source_fact(self.fact_area.rule, self.area, "source_area", "32", 1)
            self.advance(calculation, "completed")
            second = self.generate(fact=fact, rule=mapping, key="dynamic-second-order")
        finally:
            self.source_calc = original_calculation
        for result, quantity, basis_unit, workload, source_id in (
            (first, Decimal("5"), self.pcs.pk, Decimal("20"), original_calculation.pk),
            (second, Decimal("9"), sets.pk, Decimal("32"), calculation.pk),
        ):
            req = EngineeringOperationRequirement.objects.get(pk=result["operationRequirementId"])
            self.assertEqual((req.quantity_basis, req.basis_quantity, req.basis_uom_id),
                ("SOURCE_SCOPE_TOTAL", quantity, basis_unit))
            self.assertEqual((req.workload_quantity, req.uom_id), (workload, self.area.pk))
            self.assertEqual(req.source_calculation_id, source_id)
            self.assertEqual(req.source_detail.rule_id, mapping.pk)
        mapping.refresh_from_db()
        self.assertEqual(mapping.specification, fixed_specification)
        self.assertNotIn("basisQuantity", mapping.specification["outputs"][0])
        self.assertNotIn("basisUomId", mapping.specification["outputs"][0])

    def test_dynamic_total_rule_rejects_mixed_fixed_basis_values(self):
        for fixed in ({"basisQuantity": "5"}, {"basisUomId": self.pcs.pk}):
            with self.subTest(fixed=fixed):
                mapping = self.make_mapping(self.fact_area, self.op_area, self.area, mode=self.mode,
                    capacity=self.capacity, dynamic_source_basis=True)
                spec = deepcopy(mapping.specification)
                spec["outputs"][0].update(fixed)
                # A corrupted published rule is simulated only in this isolated database.
                EngineeringRuleDefinition.objects.filter(pk=mapping.pk).update(specification=spec)
                self.assert_blocked(mapping, expected_code="QUANTITY_BASIS_MISMATCH")

    def test_draft_mode_status_update_and_bulk_update_cannot_bypass_history(self):
        mode = self.initial(ManufacturingMode, "draft", company=self.company,
            code="SIM-BYPASS-DRAFT-MODE", name="Abstract draft mode", version="V1", uom=self.area)
        before = self.configuration_snapshot()
        with self.assertRaises(ValidationError):
            ManufacturingMode.objects.filter(pk=mode.pk).update(status="released")
        mode.refresh_from_db()
        self.assertEqual(mode.status, "draft")
        self.assertEqual(self.configuration_snapshot(), before)
        mode.status = "released"
        with self.assertRaises(ValidationError):
            ManufacturingMode.objects.bulk_update([mode], ["status"])
        mode.refresh_from_db()
        self.assertEqual(mode.status, "draft")
        self.assertEqual(self.configuration_snapshot(), before)
        mode.status = "released"
        with self.assertRaises(ValidationError):
            mode.save(update_fields=["status"])
        mode.refresh_from_db()
        self.assertEqual(mode.status, "draft")
        self.assertEqual(self.configuration_snapshot(), before)

    def test_bulk_mode_creation_and_obsolete_core_mutation_leave_no_writes(self):
        before = self.configuration_snapshot()
        candidate = ManufacturingMode(company=self.company, code="SIM-BULK-BYPASS-MODE",
            name="Unpublished bulk candidate", version="V1", uom=self.area, status="released")
        with self.assertRaises(ValidationError):
            ManufacturingMode.objects.bulk_create([candidate])
        self.assertEqual(self.configuration_snapshot(), before)
        self.assertFalse(ManufacturingMode.objects.filter(code=candidate.code).exists())
        forced_identity = ManufacturingMode(id=999999, company=self.company,
            code="SIM-FORCED-IDENTITY-MODE", name="Uninitialized explicit identity candidate",
            version="V1", uom=self.area, status="released")
        with self.assertRaises(ValidationError):
            forced_identity.save(force_insert=True)
        self.assertFalse(ManufacturingMode.objects.filter(pk=999999).exists())
        self.assertEqual(self.configuration_snapshot(), before)
        self.advance(self.mode, "obsolete")
        before = self.configuration_snapshot()
        self.mode.name = "Attempted obsolete core mutation"
        with self.assertRaises(ValidationError):
            self.mode.save(update_fields=["name"])
        with self.assertRaises(ValidationError):
            ManufacturingMode.objects.filter(pk=self.mode.pk).update(name=self.mode.name)
        with self.assertRaises(ValidationError):
            ManufacturingMode.objects.bulk_update([self.mode], ["name"])
        with self.assertRaises(ValidationError):
            self.mode.delete()
        with self.assertRaises(ValidationError):
            ManufacturingMode.objects.filter(pk=self.mode.pk).delete()
        self.mode.refresh_from_db()
        self.assertEqual(self.mode.status, "obsolete")
        self.assertEqual(self.configuration_snapshot(), before)
