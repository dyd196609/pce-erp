"""Synthetic memory-only supply projection tests; never reuse formal order rows."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.test import TestCase

from masterdata.models import Material, UnitOfMeasure
from pfm.models import Employee
from sales.models import Customer, SalesOrder, SalesOrderItem, SalesOrderItemSupplyAdmission
from sales.supply_admission_contract import (
    ACTION_CODE, NODE_CODE, OBJECT_TYPE, PMC_RESPONSIBILITY_CODE, PROCESS_CODE, ROLE_CODE,
)
from sales.supply_admission_service import confirm_supply_admission, supply_admission_facts
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Position,
    PositionResponsibility, PositionWorkflowResponsibility, Responsibility, Role,
    RolePermission, User, UserRoleScopeAssignment,
)
from workflow_runtime.models import BusinessStateTransition, ProcessDefinition, WorkflowNodeDefinition
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state, record_projected_business_transition,
    transition_business_object,
)

from . import services
from .models import Demand, PlanningRequirement


class PlanningRequirementSupplyProjectionTests(TestCase):
    @classmethod
    def fixture_state(cls, row, source, target, operator):
        """Real state evidence for synthetic inputs, not a formal approval claim."""
        audit = OrganizationOperatingAuditRecord.objects.create(
            actor=operator, organization=cls.company, action_code=f"fixture.{row._meta.model_name}.{target}",
            target_type=type(row).__name__, target_id=row.pk, target_label=str(row.pk),
            reason="SIMULATED_FOR_TEST：供应投影隔离输入状态",
            before_snapshot={"status": source}, after_snapshot={"status": target},
        )
        values = dict(object_type=type(row).__name__, source_state=source, target_state=target,
            action_code=audit.action_code, operator=operator, reason=audit.reason,
            audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}", allowed_transitions=((source, target),))
        if source:
            transition_business_object(business_object=row, version_field=None, **values)
        else:
            record_projected_business_transition(object_id=row.pk, **values)

    @classmethod
    def setUpTestData(cls):
        name = str(settings.DATABASES["default"]["NAME"])
        if not (name == ":memory:" or name.startswith("file:memorydb_") and "mode=memory" in name):
            raise RuntimeError("供应投影测试仅允许内存数据库，禁止业务库或持久副本。")
        cls.company = Company.objects.create(code="PCE", name="供应投影隔离公司")
        cls.other_company = Company.objects.create(code="SUP-OTHER", name="跨公司隔离夹具")
        cls.department = Department.objects.create(company=cls.company, code="SUP-PMC", name="计划物控部")
        cls.other_department = Department.objects.create(company=cls.other_company, code="OTHER-PMC", name="其他公司部门")
        cls.creator = User.objects.create_user(username="supply-projection-creator", company_id=cls.company.pk)
        cls.user = User.objects.create_user(username="supply-projection-pmc", company_id=cls.company.pk)
        position = Position.objects.create(company=cls.company, department=cls.department, code="SUP-PMC-P", name="计划物控经理")
        Employee.objects.create(user=cls.user, employee_no="SUP-PMC-E", full_name="隔离供应责任人",
            status="active", department_ref=cls.department, position_ref=position)
        responsibility = Responsibility.objects.create(code=PMC_RESPONSIBILITY_CODE, name="物料需求计划与供应协调", status="ACTIVE", is_active=True)
        PositionResponsibility.objects.create(position=position, responsibility=responsibility, active=True)
        role = Role.objects.create(code=ROLE_CODE, name="订单供应确认责任")
        permission = Permission.objects.create(code=ACTION_CODE, name="订单供应确认", module="SALES")
        RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(user=cls.user, role=role, organization=cls.company,
            scope_code="ORGANIZATION", active=True, business_hash="a" * 64)
        definition = ProcessDefinition.objects.create(definition_code=PROCESS_CODE, definition_name="供应确认",
            business_domain="SALES", document_type=OBJECT_TYPE, active=True, definition_hash="b" * 64)
        node = WorkflowNodeDefinition.objects.create(process_definition=definition, node_code=NODE_CODE,
            node_name="供应确认", sequence=1, business_action_code=ACTION_CODE, active=True)
        PositionWorkflowResponsibility.objects.create(position=position, responsibility=responsibility,
            workflow_node=node, workflow_code=PROCESS_CODE, node_code=NODE_CODE, ownership_type="OWNER", active=True)
        cls.uom = UnitOfMeasure.objects.create(company_id=cls.company.pk, code="SUP-PCS", name="件")
        cls.material = Material.objects.create(company_id=cls.company.pk, code="SUP-MAT", name="合成订单产品",
            unit="件", base_uom=cls.uom, material_type="finished", is_purchased=False, is_produced=False)
        cls.other_material = Material.objects.create(company_id=cls.company.pk, code="SUP-MAT-OTHER", name="其他合成物料", unit="件")
        customer = Customer.objects.create(company=cls.company, code="SUP-CUSTOMER", name="合成客户")
        cls.order = create_business_object_with_initial_state(model=SalesOrder, initial_state="draft",
            company=cls.company, department=cls.department, customer=customer, created_by=cls.creator,
            order_no="SYNTHETIC-SUPPLY-PROJECTION", order_date=date(2026, 10, 12),
            required_delivery_date=date(2026, 10, 20), business_purpose="FORMAL_SALE")
        for source, target, operator in (("", "draft", cls.creator), ("draft", "submitted", cls.creator), ("submitted", "approved", cls.user)):
            cls.fixture_state(cls.order, source, target, operator)
        cls.item = SalesOrderItem.objects.create(sales_order=cls.order, line_no=1, material=cls.material,
            quantity=Decimal("5"), uom=cls.uom, required_date=date(2026, 10, 20))
        cls.demand = create_business_object_with_initial_state(model=Demand, initial_state="draft",
            demand_no="SYNTHETIC-SUPPLY-DEMAND", source_type="sales_order", source_document_type="SalesOrderItem",
            source_document_id=str(cls.item.pk), source_document_no=cls.order.order_no, sales_order_item=cls.item,
            material=cls.material, required_qty=Decimal("5"), required_date=cls.item.required_date,
            department=cls.department, created_by=cls.creator, reason="合成供应投影输入")
        cls.fixture_state(cls.demand, "", "draft", cls.creator)
        cls.fixture_state(cls.demand, "draft", "confirmed", cls.creator)
        cls.authorization = {"allowed": True, "decisionCode": "ALLOWED", "roleCodes": ["TEST_PLAN"],
            "permissionCodes": ["planning.requirement.calculate"], "authoritySource": "ISOLATED_TEST_AUTHORIZATION"}

    def confirm(self, mode="MAKE"):
        result = confirm_supply_admission(user=self.user, order_id=self.order.pk, item_id=self.item.pk,
            supply_type=mode, idempotency_key="SYNTHETIC-SUPPLY-PROJECTION-KEY", reason=f"人工合成业务事实：该行采用{mode}")
        self.assertEqual(result["confirmation"]["status"], "CONFIRMED")
        return result["confirmation"]

    def calculate(self):
        return services.calculate_requirement(user=self.user, demand_id=self.demand.pk, authorization=self.authorization)

    @staticmethod
    def snapshot(include_state=False):
        result = {}
        for model in apps.get_models():
            label = model._meta.label
            if not include_state and label == "planning.PlanningRequirement":
                continue
            rows = model.objects.order_by("pk")
            if not include_state and label == "system.OrganizationOperatingAuditRecord":
                rows = rows.exclude(target_type="PlanningRequirement")
            if not include_state and label == "workflow_runtime.BusinessStateTransition":
                rows = rows.exclude(object_type="PlanningRequirement")
            result[label] = list(rows.values())
        return result

    def assert_rejected_without_write(self, code):
        before = self.snapshot(include_state=True)
        with self.assertRaises(services.PlanningBusinessError) as caught:
            self.calculate()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.snapshot(include_state=True), before)

    def assert_confirmed_resolution(self, mode, expected):
        facts = self.confirm(mode)
        before = self.snapshot()
        row, audit = self.calculate()
        metadata = row.calculation_facts["supplyResolution"]
        self.assertEqual((row.supply_type, row.status, row.net_required_qty), (expected, "calculated", Decimal("5")))
        self.assertEqual(metadata["sourceAuthority"], "ORDER_LINE_SUPPLY_ADMISSION")
        self.assertEqual(metadata["supplyAdmissionId"], facts["factId"])
        self.assertEqual((metadata["status"], metadata["supplyBranch"], metadata["resolvedSupplyType"]), ("CONFIRMED", mode, expected))
        self.assertEqual((metadata["confirmedBy"], metadata["auditId"]), (self.user.pk, facts["auditId"]))
        self.assertTrue(metadata["stateMachineConsistent"])
        self.assertEqual(metadata["statusTransitionCount"], 1)
        audits = OrganizationOperatingAuditRecord.objects.filter(target_type="PlanningRequirement", target_id=row.pk)
        self.assertEqual(audits.count(), 2)
        for event in audits:
            self.assertEqual(event.after_snapshot["state"]["supplyResolution"], metadata)
        history = BusinessStateTransition.objects.filter(object_type="PlanningRequirement", object_id=row.pk).order_by("version")
        self.assertEqual([(v.source_state, v.target_state, v.version) for v in history], [("", "draft", 1), ("draft", "calculated", 2)])
        self.assertEqual(audit.pk, audits.order_by("pk").last().pk)
        self.assertEqual(self.snapshot(), before)

    def test_confirmed_make_is_production_without_material_flags(self):
        self.assert_confirmed_resolution("MAKE", "production")

    def test_confirmed_buy_is_purchase_without_material_flags(self):
        self.assert_confirmed_resolution("BUY", "purchase")

    def test_purchase_flag_cannot_override_confirmed_make(self):
        Material.objects.filter(pk=self.material.pk).update(is_purchased=True, is_produced=False)
        self.assert_confirmed_resolution("MAKE", "production")

    def test_production_flag_cannot_override_confirmed_buy(self):
        Material.objects.filter(pk=self.material.pk).update(is_purchased=False, is_produced=True)
        self.assert_confirmed_resolution("BUY", "purchase")

    def test_absent_order_admission_remains_ambiguous_even_with_positive_flags(self):
        for purchased, produced in ((False, False), (True, False), (False, True)):
            with self.subTest(purchased=purchased, produced=produced):
                Material.objects.filter(pk=self.material.pk).update(is_purchased=purchased, is_produced=produced)
                demand = Demand.objects.select_related("material", "department", "sales_order_item__sales_order").get(pk=self.demand.pk)
                before = self.snapshot(include_state=True)
                resolved, facts = services.requirement_supply_type_for(demand)
                self.assertEqual(resolved, "ambiguous")
                self.assertEqual(facts["sourceAuthority"], "UNRESOLVED_ORDER_SUPPLY")
                self.assertEqual(self.snapshot(include_state=True), before)
        row, _ = self.calculate()
        self.assertEqual(row.supply_type, "ambiguous")
        self.assertFalse(SalesOrderItemSupplyAdmission.objects.exists())

    def test_manual_non_order_fallback_keeps_legacy_protection(self):
        demand = Demand.objects.get(pk=self.demand.pk)
        demand.sales_order_item = None
        demand.source_type, demand.source_document_type = "manual_demand", "ManualDemand"
        for purchased, produced, expected in ((True, False, "purchase"), (False, True, "production"), (False, False, "ambiguous"), (True, True, "ambiguous")):
            with self.subTest(purchased=purchased, produced=produced):
                demand.material.is_purchased, demand.material.is_produced = purchased, produced
                resolved, facts = services.requirement_supply_type_for(demand)
                self.assertEqual(resolved, expected)
                self.assertEqual(facts["sourceAuthority"], "MATERIAL_MASTER_AUXILIARY")

    def test_invalid_fact_hash_is_fail_closed_before_requirement_write(self):
        self.confirm()
        SalesOrderItemSupplyAdmission.objects.filter(sales_order_item=self.item).update(fact_hash="c" * 64)
        self.assert_rejected_without_write("REQUIREMENT_SUPPLY_ADMISSION_INVALID")

    def test_broken_admission_audit_is_fail_closed(self):
        fact = self.confirm()
        OrganizationOperatingAuditRecord.objects.filter(pk=fact["auditId"]).update(after_snapshot={"corruptFixture": True})
        self.assert_rejected_without_write("REQUIREMENT_SUPPLY_ADMISSION_INVALID")

    def test_broken_admission_transition_is_fail_closed(self):
        self.confirm()
        BusinessStateTransition.objects.filter(object_type=OBJECT_TYPE, object_id=self.item.pk).update(audit_reference="BROKEN-SYNTHETIC-REFERENCE")
        self.assert_rejected_without_write("REQUIREMENT_SUPPLY_ADMISSION_INVALID")

    def test_stale_source_is_not_replaced_by_positive_material_flags(self):
        self.confirm()
        SalesOrderItem.objects.filter(pk=self.item.pk).update(engineering_mode="ORDER_ENGINEERED")
        Material.objects.filter(pk=self.material.pk).update(is_produced=True)
        self.assertEqual(supply_admission_facts(SalesOrderItem.objects.get(pk=self.item.pk))["status"], "STALE")
        self.assert_rejected_without_write("REQUIREMENT_SUPPLY_ADMISSION_INVALID")

    def test_demand_source_material_and_company_conflicts_fail_before_write(self):
        self.confirm()
        for field, value in (("source_type", "manual_demand"), ("source_document_type", "SalesOrder"),
                ("source_document_id", "other-item"), ("source_document_no", "OTHER-ORDER"),
                ("material_id", self.other_material.pk), ("department_id", self.other_department.pk),
                ("required_qty", Decimal("6")), ("required_date", date(2026, 10, 21)), ("sales_order_item_id", None)):
            with self.subTest(field=field):
                original = Demand.objects.values_list(field, flat=True).get(pk=self.demand.pk)
                Demand.objects.filter(pk=self.demand.pk).update(**{field: value})
                self.assert_rejected_without_write("REQUIREMENT_SUPPLY_SOURCE_CONFLICT")
                Demand.objects.filter(pk=self.demand.pk).update(**{field: original})

    def test_material_company_conflict_cannot_consume_admission(self):
        self.confirm()
        Material.objects.filter(pk=self.material.pk).update(company_id=self.other_company.pk)
        self.assert_rejected_without_write("REQUIREMENT_SUPPLY_SOURCE_CONFLICT")

    def test_replay_does_not_resolve_again_or_write_history(self):
        self.confirm()
        row, _ = self.calculate()
        before = self.snapshot(include_state=True)
        with patch.object(services, "requirement_supply_type_for", side_effect=AssertionError("unexpected replay resolution")):
            replay, audit = self.calculate()
        self.assertEqual(replay.pk, row.pk)
        self.assertIsNone(audit)
        self.assertEqual(self.snapshot(include_state=True), before)

    def test_actual_calculated_transition_failure_rolls_back_with_sources_unchanged(self):
        self.confirm()
        before = self.snapshot(include_state=True)
        original = services.transition_business_object
        calls = []

        def write_then_fail(**kwargs):
            result = original(**kwargs)
            calls.append(result)
            self.assertEqual(PlanningRequirement.objects.get().supply_type, "production")
            self.assertEqual(BusinessStateTransition.objects.filter(object_type="PlanningRequirement").count(), 2)
            raise RuntimeError("injected after actual calculated transition")

        with patch.object(services, "transition_business_object", side_effect=write_then_fail):
            with self.assertRaisesRegex(RuntimeError, "after actual calculated"):
                self.calculate()
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.snapshot(include_state=True), before)
