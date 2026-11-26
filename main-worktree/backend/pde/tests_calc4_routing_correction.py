"""SIMULATED_FOR_TEST: formal routing context and immutable EOR correction.

Only the guarded isolated Django test database is populated. Formal source,
Resolver, permissions, state transitions and writers are exercised directly.
The small fixture is not the customer's 39-row correction result.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json

from django.db import connection, IntegrityError
from django.test import TestCase
from django.utils import timezone

from masterdata.models import CodeRule, Material, UnitOfMeasure
from pfm.models import Employee
from sales.models import Customer, SalesOrder, SalesOrderItem, SalesOrderItemEngineeringAttribute
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Position,
    PositionResponsibility, Process, Responsibility, Role, RolePermission,
    User, UserRoleScopeAssignment, Workshop,
)
from workflow_runtime.models import BusinessStateTransition
from . import operation_requirement_service as operation
from . import tests_operation_requirement as original
from . import tests_manufacturing_eor_configuration as manufacturing
from . import tests_classified_fact_eor as classified
from .engineering_rule_foundation import specification_hash
from .formal_engineering_continuation_service import _baseline_reference, _snapshot_design_input
from .manufacturing_rule_configuration import publication_config_validation
from .models import (
    BOMVersion, CapacityProductType, EngineeringCalculationDetail,
    EngineeringCalculationRecord, EngineeringDerivedFact, EngineeringDocument,
    EngineeringDocumentVersion, EngineeringOperationRequirement,
    EngineeringRuleDefinition, EngineeringSourceRecord, ManufacturingProcessType,
    OrderEngineeringBaseline, OrderEngineeringBaselineItem, OrderEngineeringInstance, ProductBOM,
    ProductCategory, ProductDesignItem, ProductDesignRevision, ProductManufacturingOutput, Routing, RoutingStep,
    RoutingVersion, StandardCapacity, WorkCenter, WorkCenterOperationCapability,
)


ROUTE_CONTRACT = "PCE-MANUFACTURING-ROUTING-CONTEXT-V1"
EXECUTE = operation.EXECUTE


class Calc4RoutingCorrectionTests(TestCase):
    initial = original.OperationRequirementTests.initial
    advance = original.OperationRequirementTests.advance
    make_rule = original.OperationRequirementTests.make_rule
    make_mode = manufacturing.ManufacturingEorConfigurationTests.make_mode
    make_capacity = manufacturing.ManufacturingEorConfigurationTests.make_capacity
    make_mapping = manufacturing.ManufacturingEorConfigurationTests.make_mapping
    full_database_snapshot = classified.ClassifiedFactEorTests.full_database_snapshot
    corrupt_json = classified.ClassifiedFactEorTests.corrupt_json

    def setUp(self):
        self.company = Company.objects.create(code="SIM-CTX", name="SIMULATED_FOR_TEST")
        self.department = Department.objects.create(company=self.company, code="SIM-CTX-D", name="Abstract department")
        self.user = User.objects.create_user(username="sim_ctx_operator", company_id=self.company.pk)
        self.role = Role.objects.create(code="SIM-CTX-ROLE", name="Abstract executor")
        for code in (EXECUTE, operation.VIEW):
            permission, _ = Permission.objects.get_or_create(code=code, defaults={"name": code, "module": "PRODUCTION"})
            RolePermission.objects.create(role=self.role, permission=permission)
        self.assignment = UserRoleScopeAssignment.objects.create(user=self.user, role=self.role,
            organization=self.company, scope_code="ORGANIZATION", active=True, business_hash="SIMULATED_FOR_TEST")
        responsibility = Responsibility.objects.create(code="SIM-CTX-RESP", name="Abstract executor", status="ACTIVE", is_active=True)
        position = Position.objects.create(company=self.company, department=self.department,
            code="SIM-CTX-POS", name="Abstract executor", default_role=self.role)
        PositionResponsibility.objects.create(position=position, responsibility=responsibility, is_primary=True, active=True)
        self.employee = Employee.objects.create(user=self.user, employee_no="SIM-CTX-E", full_name="SIMULATED_FOR_TEST",
            department_ref=self.department, position_ref=position, status="active")
        self.pcs = UnitOfMeasure.objects.create(company_id=self.company.pk, code="PCS", name="件", dimension="count")
        self.area = UnitOfMeasure.objects.create(company_id=self.company.pk, code="m2", name="平方米", dimension="area")
        material = Material.objects.create(company_id=self.company.pk, code="SIM-CTX-M", name="Abstract output",
            base_uom=self.pcs, unit="PCS", material_type="finished", is_produced=True)
        customer = Customer.objects.create(company=self.company, code="SIM-CTX-C", name="Abstract customer")
        self.order = self.initial(SalesOrder, "draft", company=self.company, department=self.department,
            customer=customer, order_no="SO-SIM-CONTEXT", order_date=date.today(), required_delivery_date=date.today(),
            created_by=self.user, delivery_information={"businessPurpose": "DEVELOPMENT_VALIDATION", "source": "SIMULATED_FOR_TEST"})
        self.advance(self.order, "confirmed")
        self.item = SalesOrderItem.objects.create(sales_order=self.order, line_no=1, material=material,
            quantity=37, uom=self.pcs, required_date=date.today(), engineering_mode="ORDER_ENGINEERED")
        self.category = ProductCategory.objects.create(company=self.company, code="SIM-CTX-CAT", name="Abstract category")
        self.kind = ManufacturingProcessType.objects.create(company=self.company, code="SIM-CTX-TYPE", name="Abstract full type")
        self.product_type = CapacityProductType.objects.create(company=self.company, code="SIM-CTX-CAP-T", name="Abstract capacity type",
            product_category=self.category, manufacturing_process_type=self.kind)
        payload = {"sourceKind": "SIMULATED_FOR_TEST", "objects": ["1.5", "0.5", "2"]}
        self.source = self.initial(EngineeringSourceRecord, "draft", company=self.company, source_no="SIM-CTX-SOURCE",
            source_name="Abstract frozen source", source_type="manual_confirmed", source_version="SIM-V1",
            source_payload=payload, content_hash=operation._digest(payload))
        self.advance(self.source, "confirmed")
        self.instance = self.initial(OrderEngineeringInstance, "draft", company=self.company, instance_no="SIM-CTX-INSTANCE",
            sales_order_item=self.item, product_category=self.category, selected_process_type=self.kind, source_record=self.source)
        self.advance(self.instance, "source_confirmed")
        self.advance(self.instance, "calculated")
        self.baseline = self.initial(OrderEngineeringBaseline, "draft", company=self.company, sales_order=self.order,
            baseline_no="SIM-CTX-BASE", sequence=1, reason="SIMULATED_FOR_TEST", candidate_hash=operation._digest("candidate"),
            snapshot_hash=operation._digest("frozen"), scope_item_count=3, confirmable_item_count=3,
            blocker_count=0, blocker_summary={}, created_by=self.user)
        self.baseline_items = []
        for index, quantity in enumerate(payload["objects"], 1):
            attribute = SalesOrderItemEngineeringAttribute.objects.create(sales_order_item=self.item, sequence=index,
                raw_source="SIMULATED_FOR_TEST", raw_sheet="SIM-SHEET", raw_field="stable_object",
                raw_value={"sourceRow": index, "routingProcessCode": "SIM-FULL/CTX"},
                canonical_field="stable_object", normalized_value={"decimal": quantity}, value_type="json",
                source_type="ENGINEERING_INPUT", created_by=self.user)
            design = ProductDesignItem.objects.create(company=self.company, sales_order_item=self.item,
                source_record=self.source, source_attribute=attribute, item_no=f"SIM-CTX-OBJECT-{index}",
                item_name="Abstract frozen object", source_version=self.source.source_version,
                source_content_hash=self.source.content_hash, product_category=self.category,
                physical_quantity=Decimal("37"), physical_uom=self.pcs)
            revision = ProductDesignRevision.objects.create(design_item=design, revision=1, design_nature="FORMAL",
                design_length=100, design_width=100, design_thickness=10, design_data={}, created_by=self.user)
            snapshot = {"designItem": {"id": design.pk, "physicalQuantity": "37.000000", "physicalUomId": self.pcs.pk,
                "physicalUom": self.pcs.code, "productCategoryId": self.category.pk, "productDefinitionId": None,
                "existingDesignData": {"provenance": {"sourceSheet": "SIM-SHEET", "sourceRow": index}}},
                "source": {"recordId": self.source.pk, "rawSheet": "SIM-SHEET"},
                "revision": {"id": revision.pk, "revision": 1, "designNature": "FORMAL", "designLength": "100.000000",
                    "designWidth": "100.000000", "designThickness": "10.000000", "designUomId": None,
                    "materialId": None, "paintProcessTypeId": None, "materialProcessTypeId": None,
                    "edgeMethodId": None, "designData": {}}}
            item = OrderEngineeringBaselineItem.objects.create(baseline=self.baseline, design_item=design,
                design_revision=revision, source_record=self.source, source_attribute=attribute, source_type="DESIGN_REVISION",
                item_no_snapshot=design.item_no, item_name_snapshot=design.item_name, design_item_version=design.version,
                design_revision_no=1, design_nature_snapshot="FORMAL", source_version_snapshot=self.source.source_version,
                source_content_hash_snapshot=self.source.content_hash, content_snapshot=snapshot,
                content_hash=operation._digest(snapshot), confirmable=True)
            self.baseline_items.append(item)
        self.baseline.snapshot_hash = operation._digest([item.content_hash for item in self.baseline_items])
        self.baseline.confirmed_by, self.baseline.confirmed_at = self.user, timezone.now()
        self.baseline.save(update_fields=("snapshot_hash", "confirmed_by", "confirmed_at"))
        self.advance(self.baseline, "confirmed")
        self.op_area = Process.objects.create(company=self.company, code="SIM-CTX-OP", name="Abstract area operation",
            calculation_basis="area", calculation_uom=self.area, standard_hours=Decimal("999"))
        self.rule_counter = 0
        self.producer = self.make_rule(self.op_area, self.area, "opaque_area", output_domain="DERIVED_FACT")
        reference = _baseline_reference(self.baseline, self.baseline_items)
        objects = [{"baselineItemId": item.pk, "designItemId": item.design_item_id,
            "designItemNo": item.item_no_snapshot, "sourceAttributeId": item.source_attribute_id,
            "sourceKey": f"SIM-SHEET:{index}", "contentHash": item.content_hash,
            "sourceVersion": self.source.source_version, "sourceContentHash": self.source.content_hash,
            "input": _snapshot_design_input(item)} for index, item in enumerate(self.baseline_items, 1)]
        input_hash = operation._digest({"baseline": reference, "objects": objects})
        self.source_calc = self.initial(EngineeringCalculationRecord, "draft", company=self.company,
            scope="order_engineering", source_record=self.source, sales_order_item=self.item, engineering_instance=self.instance,
            calculation_no="SIM-CTX-SOURCE-CALC", rule_set_version="SIM-V1", input_hash=input_hash,
            rule_graph_hash=specification_hash(self.producer.specification), result_hash=operation._digest(payload),
            trace={"sourceKind": "SIMULATED_FOR_TEST", "baselineId": self.baseline.pk,
                "baselineReference": reference, "objectInputSnapshot": objects, "objectInputSnapshotHash": input_hash,
                "sourceReference": {"id": self.source.pk, "sourceVersion": self.source.source_version,
                    "contentHash": self.source.content_hash}})
        self.advance(self.source_calc, "prepared")
        self.advance(self.source_calc, "running")
        self.facts = [self.make_fact(value, index) for index, value in enumerate(payload["objects"], 1)]
        self.advance(self.source_calc, "completed")
        self.fact_area = self.facts[0]
        self.rule_area = self.make_rule(self.op_area, self.area, "opaque_area")
        self.workshop = Workshop.objects.create(company=self.company, department=self.department, code="SIM-CTX-WS", name="Abstract workshop")
        self.center = WorkCenter.objects.create(company=self.company, workshop=self.workshop, department=self.department,
            code="SIM-CTX-WC", name="Abstract work center")
        self.mode = self.make_mode(self.area, "SIM-CTX-MODE")
        WorkCenterOperationCapability.objects.create(work_center=self.center, operation=self.op_area, assignment_role="primary", is_active=True)
        self.capacity = self.make_capacity(self.op_area, self.area, "SIM-CTX-CAP")
        CodeRule.objects.create(company_id=self.company.pk, entity_type="production_engineering_calculation", prefix="SIM-CTX-", date_format="", seq_length=4)
        self.bom = self.initial(ProductBOM, "draft", company=self.company, applicability_scope="ORDER_ENGINEERING",
            order_engineering_instance=self.instance, bom_code="SIM-CTX-BOM", name="Abstract BOM")
        self.bom_version = self.initial(BOMVersion, "draft", bom=self.bom, bom_version="SIM-V1", bom_scope="order_specific",
            order_engineering_instance=self.instance, source_calculation=self.source_calc)
        self.advance(self.bom_version, "reviewed")
        self.advance(self.bom_version, "released")
        self.route = self.initial(Routing, "draft", company=self.company, applicability_scope="PRODUCT_CATEGORY",
            product_category=self.category, manufacturing_process_type=self.kind, routing_code="SIM-FULL/CTX", name="Abstract route")
        self.advance(self.route, "reviewed")
        self.advance(self.route, "released")
        self.version, self.step = self.make_version("SIM-V1", exact=True)
        self.wrong_version, self.wrong_step = self.make_version("SIM-V99", exact=False)
        self.mapping = self.make_mapping(self.fact_area, self.op_area, self.area,
            mode=self.mode, capacity=self.capacity, dynamic_source_basis=True, release=False)
        self.mapping.specification["sourceEvidence"]["formalRouting"] = self.route_evidence(self.wrong_version, self.wrong_step)
        self.mapping.save(update_fields=("specification",))
        self.advance(self.mapping, "reviewed")
        self.advance(self.mapping, "released")
        document = EngineeringDocument.objects.create(document_no="SIM-CTX-DOC", document_name="Abstract document",
            document_type="technical", release_subject_type="ORDER_ENGINEERED_PRODUCT", order_engineering_instance=self.instance,
            product_bom=self.bom, routing=self.route)
        self.document = self.initial(EngineeringDocumentVersion, "draft", document=document, document_name="Abstract document",
            document_version="SIM-V1", release_subject_type="ORDER_ENGINEERED_PRODUCT", order_engineering_instance=self.instance,
            order_engineering_baseline=self.baseline, engineering_calculation=self.source_calc,
            related_bom=self.bom_version, related_routing=self.version)
        self.advance(self.document, "reviewed")
        self.advance(self.document, "released")
        self.output = self.initial(ProductManufacturingOutput, "draft", status_field="release_status",
            release_subject_type="ORDER_ENGINEERED_PRODUCT", definition_mode="order_specific", engineering_status="ready",
            order_engineering_instance=self.instance, order_engineering_baseline=self.baseline,
            engineering_calculation=self.source_calc, bom_version=self.bom_version,
            routing_version=self.version, engineering_document_version=self.document)
        self.advance(self.output, "engineering_review", status_field="release_status")
        self.advance(self.output, "released_to_manufacturing", status_field="release_status")
        self.correct_rule = self.new_rule()
        self.old_ids = [self.generate(fact=fact, rule=self.mapping, key=f"sim-old-{fact.pk}")["operationRequirementId"] for fact in self.facts]
        self.old_audit_ids = list(OrganizationOperatingAuditRecord.objects.values_list("pk", flat=True))
        self.old_transition_ids = list(BusinessStateTransition.objects.values_list("pk", flat=True))
        self.original_rows = self.protected_snapshot()

    def make_fact(self, value, sequence):
        item = self.baseline_items[sequence - 1]
        detail = self.initial(EngineeringCalculationDetail, "running", calculation=self.source_calc, sequence=sequence,
            rule=self.producer, rule_code=self.producer.rule_code, rule_version=self.producer.version,
            expression_snapshot=self.producer.specification["expression"], input_snapshot={"raw_opaque_area": value,
                "object": deepcopy(self.source_calc.trace["objectInputSnapshot"][sequence - 1]["input"])},
            dependency_snapshot=[], output_name="opaque_area", output_value={"decimal": value}, uom=self.area,
            precision=18, rounding="ROUND_HALF_UP", started_at=timezone.now(), finished_at=timezone.now())
        self.advance(detail, "succeeded")
        return self.initial(EngineeringDerivedFact, "active", calculation=self.source_calc, rule=self.producer,
            source_detail=detail, fact_code="opaque_area", canonical_field="opaque_area", sequence=sequence,
            value={"decimal": value}, value_type="decimal", source_type="ENGINEERING_DERIVED", uom=self.area,
            source_path=f"SIMULATED_FOR_TEST.object[{sequence}]", trace={"sourceKind": "SIMULATED_FOR_TEST",
                "resultDomain": "DERIVED_FACT", "detailId": detail.pk, "ruleCode": self.producer.rule_code,
                "ruleVersion": self.producer.version, "specificationHash": specification_hash(self.producer.specification),
                "baselineId": self.baseline.pk, "baselineItemId": item.pk, "designItemId": item.design_item_id,
                "sourceAttributeId": item.source_attribute_id, "baselineContentHash": item.content_hash,
                "ProductPaintingProcessCode": "SIM-FULL/CTX"})

    def make_version(self, code, *, exact):
        version = self.initial(RoutingVersion, "draft", routing=self.route, routing_version=code)
        context = {"organizationId": self.company.pk, "salesOrderItemId": self.item.pk,
            "orderEngineeringInstanceId": self.instance.pk, "orderEngineeringBaselineId": self.baseline.pk,
            "engineeringCalculationId": self.source_calc.pk if exact else self.source_calc.pk + 1000,
            "bomVersionId": self.bom_version.pk, "routingId": self.route.pk, "routingVersionId": version.pk,
            "contextKey": "SIMULATED_FOR_TEST_CONTEXT"}
        version.applicability = {"manualStepApplicability": {"contractVersion": "PCE-ROUTING-MANUAL-APPLICABILITY-V1.0",
            "contexts": {context["contextKey"]: {"context": context}}}}
        version.save(update_fields=("applicability",))
        step = RoutingStep.objects.create(routing_version=version, sequence=1, operation=self.op_area,
            standard_hours=Decimal("777"), operation_parameters={"applicability": {
                "contractVersion": "PCE-ROUTING-STEP-APPLICABILITY-V1.0", "mode": "MANDATORY"}})
        self.advance(version, "reviewed")
        self.advance(version, "released")
        return version, step

    def new_rule(self, edit=None, *, release=True):
        self.rule_counter += 1
        spec = deepcopy(self.mapping.specification)
        spec["rulePackage"]["version"] = "V3"
        spec["manufacturing"]["routingContext"] = {"contractVersion": ROUTE_CONTRACT,
            "routingId": self.route.pk, "routingVersionId": self.version.pk, "routingStepId": self.step.pk}
        spec["sourceEvidence"]["formalRouting"] = self.route_evidence(self.version, self.step)
        if edit:
            edit(spec)
        rule = self.initial(EngineeringRuleDefinition, "draft", company=self.company,
            rule_code=(self.mapping.rule_code if not hasattr(self, "correct_rule") else f"SIM-CTX-CORRECTION-{self.rule_counter}"),
            rule_name="Abstract routing correction", version="V3",
            rule_kind="formula", specification=spec)
        if release:
            self.advance(rule, "reviewed")
            self.advance(rule, "released")
        return rule

    def route_evidence(self, version, step):
        return {"routingId": self.route.pk, "routingCode": self.route.routing_code,
            "routingVersionId": version.pk, "routingVersion": version.routing_version,
            "routingStepId": step.pk, "sequence": step.sequence, "operationId": step.operation_id}

    def edit_json(self, obj, field, edit):
        value = deepcopy(getattr(obj, field))
        edit(value)
        self.corrupt_json(obj, field, value)

    def generate(self, *, fact=None, rule=None, key="sim-new", user=None, old_id=None):
        kwargs = dict(user=user or self.user, source_calculation_id=self.source_calc.pk,
            source_fact_id=(fact or self.fact_area).pk, rule_id=(rule or self.correct_rule).pk,
            idempotency_key=key, reason="SIMULATED_FOR_TEST")
        if old_id is not None:
            kwargs["supersedes_requirement_id"] = old_id
        return operation.OperationRequirementService.generate(**kwargs)

    def correct(self, *, replacements=None, key="sim-correct", user=None):
        from .operation_requirement_correction_service import OperationRequirementCorrectionService
        rows = replacements if replacements is not None else [
            {"operationRequirementId": identifier, "ruleId": self.correct_rule.pk} for identifier in self.old_ids]
        return OperationRequirementCorrectionService.correct(user=user or self.user,
            replacements=rows, idempotency_key=key, reason="SIMULATED_FOR_TEST")

    def lifecycle(self, identifier):
        from .operation_requirement_correction_service import requirement_lifecycle
        return requirement_lifecycle(EngineeringOperationRequirement.objects.get(pk=identifier), self.company.pk)

    def protected_snapshot(self):
        models = (EngineeringSourceRecord, OrderEngineeringInstance, OrderEngineeringBaseline, EngineeringDerivedFact,
            OrderEngineeringBaselineItem, ProductDesignItem, ProductDesignRevision, SalesOrderItemEngineeringAttribute,
            BOMVersion, ProductBOM, ProductManufacturingOutput, EngineeringDocumentVersion,
            Routing, RoutingVersion, RoutingStep, Process, WorkCenter, StandardCapacity,
            EngineeringRuleDefinition)
        result = {model.__name__: list(model.objects.order_by("pk").values()) for model in models}
        old_calcs = list(EngineeringOperationRequirement.objects.filter(pk__in=getattr(self, "old_ids", [])).values_list("calculation_id", flat=True))
        result["calculations"] = list(EngineeringCalculationRecord.objects.filter(pk__in=[self.source_calc.pk, *old_calcs]).order_by("pk").values())
        result["details"] = list(EngineeringCalculationDetail.objects.filter(calculation_id__in=[self.source_calc.pk, *old_calcs]).order_by("pk").values())
        result["eors"] = list(EngineeringOperationRequirement.objects.filter(pk__in=getattr(self, "old_ids", [])).order_by("pk").values())
        result["originalAudits"] = list(OrganizationOperatingAuditRecord.objects.filter(
            pk__in=getattr(self, "old_audit_ids", [])).order_by("pk").values())
        result["originalTransitions"] = list(BusinessStateTransition.objects.filter(
            pk__in=getattr(self, "old_transition_ids", [])).order_by("pk").values())
        return result

    def no_write_failure(self, action, *, code=None, error=operation.OperationRequirementError):
        before = self.full_database_snapshot()
        with self.assertRaises(error) as caught:
            action()
        if code:
            self.assertEqual(getattr(caught.exception, "code", None), code)
        self.assertEqual(self.full_database_snapshot(), before)
        return caught.exception

    def readiness(self, rule=None):
        return operation.OperationRequirementService.generate_readiness(user=self.user,
            source_calculation_id=self.source_calc.pk, source_fact_id=self.fact_area.pk,
            rule_id=(rule or self.correct_rule).pk)

    def test_correct_formal_context_uses_exact_version_not_highest_version(self):
        before = self.full_database_snapshot()
        result = self.readiness()
        self.assertTrue(result["ready"], result)
        context = result["sourceSnapshot"]["manufacturing"]["routingContext"]
        self.assertEqual(context["routingVersionId"], self.version.pk)
        self.assertNotEqual(context["routingVersionId"], self.wrong_version.pk)
        self.assertEqual(context["routingStepId"], self.step.pk)
        self.assertEqual(self.full_database_snapshot(), before)

    def test_wrong_released_version_is_rejected_without_new_objects(self):
        def wrong(spec):
            spec["manufacturing"]["routingContext"].update(
                routingVersionId=self.wrong_version.pk, routingStepId=self.wrong_step.pk)
            spec["sourceEvidence"]["formalRouting"] = self.route_evidence(self.wrong_version, self.wrong_step)
        rule = self.new_rule(wrong)
        self.assertFalse(self.readiness(rule)["ready"])
        self.no_write_failure(lambda: self.generate(rule=rule), code="MANUFACTURING_ROUTING_VERSION_MISMATCH")

    def test_config_rejects_unknown_keys_boolean_ids_missing_and_wrong_contract(self):
        for change in (lambda obj: obj.update(routingId=True), lambda obj: obj.pop("routingStepId"),
                       lambda obj: obj.update(unknown=True), lambda obj: obj.update(contractVersion="UNKNOWN")):
            with self.subTest(change=change):
                rule = self.new_rule(lambda spec: change(spec["manufacturing"]["routingContext"]))
                self.no_write_failure(lambda: publication_config_validation(rule, require_released=True))

    def test_publication_rejects_step_from_another_version(self):
        rule = self.new_rule(lambda spec: spec["manufacturing"]["routingContext"].update(routingStepId=self.wrong_step.pk))
        self.no_write_failure(lambda: publication_config_validation(rule, require_released=True))

    def test_unreleased_rule_and_version_cannot_generate(self):
        rule = self.new_rule(release=False)
        self.no_write_failure(lambda: self.generate(rule=rule))
        self.advance(self.version, "obsolete")
        self.no_write_failure(lambda: self.generate())

    def test_missing_confirmed_baseline_or_matching_released_output_blocks(self):
        self.advance(self.output, "inactive", status_field="release_status")
        self.no_write_failure(lambda: self.generate())

    def test_source_baseline_identity_drift_is_rejected(self):
        self.edit_json(self.fact_area, "trace", lambda trace: trace.update(baselineId=self.baseline.pk + 9999))
        self.no_write_failure(lambda: self.generate())

    def test_conditional_step_without_formal_condition_fails_closed(self):
        self.edit_json(self.step, "operation_parameters", lambda params: params.update(applicability={
            "contractVersion": "PCE-ROUTING-STEP-APPLICABILITY-V1.0", "mode": "CONDITIONAL",
            "conditionCode": "DRAWING_ENGRAVING_REQUIRED"}))
        self.no_write_failure(lambda: self.generate())

    def test_configured_process_must_be_the_exact_step_process(self):
        other = Process.objects.create(company=self.company, code="SIM-OTHER-OP", name="Abstract different process",
            calculation_basis="area", calculation_uom=self.area)
        with connection.cursor() as cursor:
            cursor.execute("UPDATE pde_routing_step SET operation_id=%s WHERE id=%s", [other.pk, self.step.pk])
        self.no_write_failure(lambda: self.generate())

    def test_capacity_uom_mismatch_cannot_be_fixed_by_routing_context(self):
        other = self.make_capacity(self.op_area, self.pcs, "SIM-WRONG-UNIT-CAP")
        rule = self.new_rule(lambda spec: spec["manufacturing"].update(standardCapacityId=other.pk))
        self.no_write_failure(lambda: self.generate(rule=rule))

    def test_whole_correction_keeps_old_rows_and_creates_one_new_eor_per_source(self):
        counted = (EngineeringCalculationRecord, EngineeringCalculationDetail, EngineeringOperationRequirement,
            OrganizationOperatingAuditRecord, BusinessStateTransition)
        before = [model.objects.count() for model in counted]
        result = self.correct()
        deltas = [model.objects.count() - count for model, count in zip(counted, before)]
        self.assertEqual(deltas, [3, 3, 3, 21, 21])
        self.assertEqual(result["businessWriteCount"], sum(deltas[:3]))
        self.assertEqual(result["auditWriteCount"], deltas[3])
        self.assertEqual(result["stateTransitionWriteCount"], deltas[4])
        newer = list(EngineeringOperationRequirement.objects.exclude(pk__in=self.old_ids).order_by("pk"))
        self.assertEqual(len(newer), 3)
        self.assertEqual({req.source_fact_id for req in newer}, {fact.pk for fact in self.facts})
        self.assertEqual(sum(req.workload_quantity for req in newer), Decimal("4"))
        for req in newer:
            old = EngineeringOperationRequirement.objects.get(pk__in=self.old_ids, source_fact=req.source_fact)
            self.assertEqual(req.calculation.supersedes_id, old.calculation_id)
            self.assertEqual(req.calculation.revision, old.calculation.revision + 1)
            self.assertEqual(req.workload_quantity, old.workload_quantity)
            self.assertEqual(req.uom_id, old.uom_id)
            self.assertEqual(req.source_detail.rule_version, "V3")
            operation._validate_requirement(req, self.company.pk)
        self.assertEqual(self.protected_snapshot(), self.original_rows)

    def test_subset_correction_never_marks_unselected_old_requirements(self):
        before = list(BusinessStateTransition.objects.filter(object_type="EngineeringOperationRequirement",
            object_id__in=self.old_ids[1:]).values())
        self.correct(replacements=[{"operationRequirementId": self.old_ids[0], "ruleId": self.correct_rule.pk}])
        self.assertEqual(EngineeringOperationRequirement.objects.count(), 4)
        self.assertEqual(list(BusinessStateTransition.objects.filter(object_type="EngineeringOperationRequirement",
            object_id__in=self.old_ids[1:]).values()), before)
        self.assertEqual(self.protected_snapshot(), self.original_rows)

    def test_native_supersedes_argument_retains_old_facts_and_records_typed_lineage(self):
        result = self.generate(old_id=self.old_ids[0])
        req = EngineeringOperationRequirement.objects.get(pk=result["operationRequirementId"])
        old = EngineeringOperationRequirement.objects.get(pk=self.old_ids[0])
        self.assertEqual(req.calculation.supersedes_id, old.calculation_id)
        self.assertEqual(req.calculation.trace["sourceSnapshot"]["sourceReplacement"]["operationRequirementId"], old.pk)
        operation._validate_requirement(req, self.company.pk)
        self.assertEqual(self.protected_snapshot(), self.original_rows)

    def test_wrong_source_replacement_is_rejected_before_write(self):
        self.no_write_failure(lambda: self.generate(fact=self.facts[1], old_id=self.old_ids[0]))

    def test_same_key_replay_preserves_every_database_table_and_code_sequence(self):
        first = self.correct()
        before = self.full_database_snapshot()
        second = self.correct()
        self.assertEqual(self.full_database_snapshot(), before)
        self.assertTrue(second["idempotent"])
        self.assertEqual(second["businessWriteCount"], 0)
        self.assertEqual(second["auditWriteCount"], 0)
        self.assertEqual(first["replacements"], second["replacements"])

    def test_same_key_changed_payload_is_rejected(self):
        self.correct()
        self.no_write_failure(lambda: self.correct(replacements=[{
            "operationRequirementId": self.old_ids[0], "ruleId": self.correct_rule.pk}]))

    def test_duplicate_old_identity_and_empty_batch_are_rejected(self):
        row = {"operationRequirementId": self.old_ids[0], "ruleId": self.correct_rule.pk}
        for value in ([], [row, row], [{"operationRequirementId": True, "ruleId": self.correct_rule.pk}]):
            with self.subTest(value=value):
                self.no_write_failure(lambda: self.correct(replacements=value))

    def test_unprivileged_actor_cannot_generate_or_correct(self):
        unauthorized = User.objects.create_user(username="sim_ctx_reader", company_id=self.company.pk)
        self.no_write_failure(lambda: self.generate(user=unauthorized))
        self.no_write_failure(lambda: self.correct(user=unauthorized))

    def test_expired_organization_scope_is_rechecked_before_correction(self):
        self.assignment.active = False
        self.assignment.save(update_fields=("active",))
        self.no_write_failure(lambda: self.correct())

    def test_actual_actor_and_authoritative_audits_back_each_lifecycle_transition(self):
        self.correct()
        rows = list(BusinessStateTransition.objects.filter(object_type="EngineeringOperationRequirement").order_by("object_id", "version"))
        self.assertEqual(len(rows), 9)
        self.assertEqual(len({transition.audit_reference for transition in rows}), 9)
        for transition in rows:
            self.assertEqual(transition.operator_id, self.user.pk)
            reference = transition.audit_reference.split(":")[-1]
            audit = OrganizationOperatingAuditRecord.objects.get(pk=int(reference))
            self.assertEqual(audit.actor_id, self.user.pk)
            self.assertEqual(audit.organization_id, self.company.pk)
            self.assertEqual(audit.target_id, transition.object_id)
            relationship = audit.after_snapshot["state"]["relationship"]
            proof = relationship["routingContext"]
            self.assertEqual(proof["context"], {"organizationId": self.company.pk,
                "salesOrderItemId": self.item.pk, "orderEngineeringInstanceId": self.instance.pk,
                "orderEngineeringBaselineId": self.baseline.pk,
                "engineeringCalculationId": self.source_calc.pk, "bomVersionId": self.bom_version.pk})
            self.assertEqual((proof["routingId"], proof["routingVersionId"], proof["routingStepId"]),
                (self.route.pk, self.version.pk, self.step.pk))
            new = EngineeringOperationRequirement.objects.get(pk=relationship["new"]["operationRequirementId"])
            self.assertEqual(proof, new.calculation.trace["sourceSnapshot"]["manufacturing"]["routingContext"])
            self.assertEqual(proof["sourceEngineeringCalculationId"], self.source_calc.pk)
            self.assertEqual(proof["sourceFactId"], new.source_fact_id)
            self.assertEqual(proof["manufacturingOutputId"], self.output.pk)
            self.assertEqual((proof["operationId"], proof["workCenterId"], proof["standardCapacityId"],
                proof["productTypeId"], proof["uomId"]),
                (self.op_area.pk, self.center.pk, self.capacity.pk, self.product_type.pk, self.area.pk))
            from .production_foundation_service import _snapshot
            expected_hashes = {"engineeringCalculationInputHash": self.source_calc.input_hash,
                "engineeringCalculationResultHash": self.source_calc.result_hash,
                "baselineSnapshotHash": self.baseline.snapshot_hash,
                **{key: operation._digest(_snapshot(type(obj).objects.get(pk=obj.pk))) for key, obj in (
                    ("manufacturingOutputHash", self.output), ("bomVersionHash", self.bom_version),
                    ("routingHash", self.route), ("routingVersionHash", self.version), ("routingStepHash", self.step))}}
            self.assertEqual(proof["formalSourceHashes"], expected_hashes)
        for identifier in self.old_ids:
            self.assertEqual(self.lifecycle(identifier)["statusCode"], "SUPERSEDED")
        for req in EngineeringOperationRequirement.objects.exclude(pk__in=self.old_ids):
            self.assertEqual(self.lifecycle(req.pk)["statusCode"], "EFFECTIVE")

    def test_lifecycle_audit_corruption_is_not_accepted_as_supersession(self):
        self.correct()
        transition = BusinessStateTransition.objects.filter(object_type="EngineeringOperationRequirement",
            object_id=self.old_ids[0]).order_by("-version").first()
        audit = OrganizationOperatingAuditRecord.objects.get(pk=int(transition.audit_reference.split(":")[-1]))
        self.edit_json(audit, "after_snapshot", lambda payload: payload.update(state={"status": "effective"}))
        self.no_write_failure(lambda: self.lifecycle(self.old_ids[0]))

    def test_database_failure_after_one_generated_replacement_rolls_back_whole_batch(self):
        inserts = 0
        def fail_second(execute, sql, params, many, context):
            nonlocal inserts
            if sql.lstrip().upper().startswith("INSERT INTO") and '"pde_engineering_operation_requirement"' in sql:
                inserts += 1
                if inserts == 2:
                    raise IntegrityError("SIMULATED_FOR_TEST second-EOR database failure")
            return execute(sql, params, many, context)
        with connection.execute_wrapper(fail_second):
            self.no_write_failure(lambda: self.correct(), error=IntegrityError)
        self.assertEqual(inserts, 2)

    def test_legacy_rule_without_opt_in_keeps_exact_stored_hash_and_replay_behavior(self):
        req = EngineeringOperationRequirement.objects.get(pk=self.old_ids[0])
        self.assertNotIn("routingContext", req.calculation.trace["sourceSnapshot"]["manufacturing"])
        before = self.full_database_snapshot()
        self.generate(rule=self.mapping, key=f"sim-old-{self.fact_area.pk}")
        self.assertEqual(self.full_database_snapshot(), before)
        operation._validate_requirement(req, self.company.pk)

    def test_source_quantity_is_dynamic_and_thirty_seven_basis_does_not_multiply(self):
        self.correct(replacements=[{"operationRequirementId": self.old_ids[0], "ruleId": self.correct_rule.pk}])
        req = EngineeringOperationRequirement.objects.exclude(pk__in=self.old_ids).get()
        self.assertEqual(req.workload_quantity, Decimal("1.5"))
        self.assertEqual(req.basis_quantity, Decimal("37"))
        self.assertEqual(req.quantity_basis, "SOURCE_SCOPE_TOTAL")

    def test_no_planning_or_allocation_objects_are_created(self):
        from planning.models import ProductionPlan
        from .models import ProductionPlanOperationRequirementAllocation
        self.assertEqual(ProductionPlan.objects.count(), 0)
        self.correct()
        self.assertEqual(ProductionPlan.objects.count(), 0)
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.count(), 0)
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA foreign_key_check")
            self.assertEqual(cursor.fetchall(), [])

    def test_superseded_old_requirement_is_ineligible_but_its_new_pair_is_effective(self):
        from .operation_requirement_correction_service import require_effective_requirement
        result = self.correct()
        old = EngineeringOperationRequirement.objects.get(pk=self.old_ids[0])
        self.no_write_failure(lambda: require_effective_requirement(old, self.company.pk),
            code="OPERATION_REQUIREMENT_SUPERSEDED")
        new = EngineeringOperationRequirement.objects.get(pk=result["operationRequirementIds"][0])
        before = self.full_database_snapshot()
        self.assertEqual(require_effective_requirement(new, self.company.pk)["statusCode"], "EFFECTIVE")
        self.assertEqual(self.full_database_snapshot(), before)

    def test_missing_counterpart_transition_cannot_claim_effective_replacement(self):
        result = self.correct()
        transition = BusinessStateTransition.objects.get(object_type="EngineeringOperationRequirement",
            object_id=self.old_ids[0], target_state="SUPERSEDED")
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM business_state_transitions WHERE id=%s", [transition.pk])
        self.no_write_failure(lambda: self.lifecycle(result["operationRequirementIds"][0]),
            code="CORRECTION_HISTORY_UNPROVEN")

    def test_routing_correction_rejects_a_rule_that_changes_workload(self):
        rule = self.new_rule(lambda spec: spec.update(expression="opaque_area * 2"))
        self.no_write_failure(lambda: self.correct(replacements=[{
            "operationRequirementId": self.old_ids[0], "ruleId": rule.pk}]), code="CORRECTION_SOURCE_MISMATCH")

    def test_unprojected_replacement_cannot_be_used_as_an_effective_requirement(self):
        from .operation_requirement_correction_service import require_effective_requirement
        result = self.generate(old_id=self.old_ids[0])
        req = EngineeringOperationRequirement.objects.get(pk=result["operationRequirementId"])
        self.assertIsNone(self.lifecycle(req.pk))
        self.no_write_failure(lambda: require_effective_requirement(req, self.company.pk),
            code="CORRECTION_HISTORY_UNPROVEN")
