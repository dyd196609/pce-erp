"""Synthetic, in-memory regression of decision versus execution responsibility.

The IDs/names are synthetic fixture identities, not assertions about formal
records. Decision authorization, organization scopes, position responsibilities,
workflow mapping, service writes, audit and transitions are real ORM/service
paths; no permission/identity mocks are used. The production execution owner
gets no confirmation grant or workflow mapping and does not perform/sign an
execution action. Corruption injection is confined to the memory test database.
"""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient

from masterdata.models import Material, UnitOfMeasure
from pfm.models import Employee
from planning.models import Demand, PlanningRequirement
from sales.models import Customer, SalesOrder, SalesOrderItem, SalesOrderItemSupplyAdmission
from sales.supply_admission_contract import (
    ACTION_CODE, MODULE_CODE, NODE_CODE, OBJECT_TYPE, PMC_RESPONSIBILITY_CODE,
    PROCESS_CODE, RESPONSIBILITY_TYPE, ROLE_CODE,
)
from sales.supply_admission_service import (
    SupplyAdmissionError, _fact_payload, authorize, confirm_supply_admission,
    query_supply_admission, supply_admission_facts,
)
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Position,
    PositionResponsibility, PositionWorkflowResponsibility, Responsibility, Role,
    RolePermission, User, UserRoleScopeAssignment,
)
from workflow_runtime.models import (
    ApprovalDecision, ApprovalTask, BusinessStateTransition, ProcessDefinition,
    WorkflowInstance, WorkflowNodeDefinition,
)
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state, record_projected_business_transition,
    transition_business_object,
)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


class SupplyAdmissionExecutionResponsibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        database = str(settings.DATABASES["default"]["NAME"])
        if not (database == ":memory:" or
                database.startswith("file:memorydb_") and "mode=memory" in database):
            raise RuntimeError("执行责任回归只允许内存测试库；禁止正式数据库或持久副本写入。")
        cls.company = Company.objects.create(id=1, code="COMP001", name="合成责任分离公司")
        cls.other_company = Company.objects.create(code="OTHER-COMP", name="合成跨范围公司")
        cls.pmc_department = Department.objects.create(company=cls.company, code="PMC", name="计划物控部")
        cls.production_department = Department.objects.create(company=cls.company, code="PROD", name="生产部")
        cls.pmc_position = Position.objects.create(id=30, company=cls.company,
            department=cls.pmc_department, code="PMC-MGR", name="计划物控部经理")
        cls.production_position = Position.objects.create(id=3, company=cls.company,
            department=cls.production_department, code="PROD-MGR", name="生产经理")
        cls.creator = User.objects.create_user(id=11, username="synthetic-sales-creator", company_id=cls.company.pk)
        cls.decision_user = User.objects.create_user(id=30, username="synthetic-pmc-decider",
            real_name="赵铁柱", company_id=cls.company.pk)
        cls.execution_user = User.objects.create_user(id=23, username="synthetic-production-owner",
            real_name="赵盛世", company_id=cls.company.pk)
        cls.other_execution_user = User.objects.create_user(username="synthetic-other-production-owner",
            real_name="另一个合成执行人", company_id=cls.company.pk)
        cls.decision_employee = Employee.objects.create(id=122, user=cls.decision_user,
            employee_no="SYNTHETIC-PMC-122", full_name="赵铁柱", status="active",
            department_ref=cls.pmc_department, position_ref=cls.pmc_position)
        cls.execution_employee = Employee.objects.create(id=107, user=cls.execution_user,
            employee_no="SYNTHETIC-PROD-107", full_name="赵盛世", status="active",
            department_ref=cls.production_department, position_ref=cls.production_position)
        Employee.objects.create(user=cls.other_execution_user, employee_no="SYNTHETIC-PROD-OTHER",
            full_name="另一个合成执行人", status="active", department_ref=cls.production_department,
            position_ref=cls.production_position)
        cls.pmc_responsibility = Responsibility.objects.create(code=PMC_RESPONSIBILITY_CODE,
            name="物料需求计划与供应协调", status="ACTIVE", is_active=True)
        cls.execution_responsibility = Responsibility.objects.create(code="RESP_PROD_PLAN_001",
            name="生产计划承接与达成", status="ACTIVE", is_active=True)
        cls.pmc_duty = PositionResponsibility.objects.create(position=cls.pmc_position,
            responsibility=cls.pmc_responsibility, active=True)
        cls.execution_duty = PositionResponsibility.objects.create(position=cls.production_position,
            responsibility=cls.execution_responsibility, active=True)
        cls.role = Role.objects.create(code=ROLE_CODE, name="订单行供应承接确认责任人")
        cls.permission = Permission.objects.create(code=ACTION_CODE, name="订单行供应承接确认", module="SALES")
        cls.role_permission = RolePermission.objects.create(role=cls.role, permission=cls.permission)
        cls.grant = UserRoleScopeAssignment.objects.create(user=cls.decision_user, role=cls.role,
            organization=cls.company, scope_code="ORGANIZATION", active=True, business_hash="a" * 64)
        cls.definition = ProcessDefinition.objects.create(definition_code=PROCESS_CODE,
            definition_name="订单行供应承接确认", business_domain="SALES", document_type=OBJECT_TYPE,
            version=1, active=True, definition_hash="b" * 64)
        cls.node = WorkflowNodeDefinition.objects.create(process_definition=cls.definition,
            node_code=NODE_CODE, node_name="订单行供应承接确认", sequence=1,
            business_action_code=ACTION_CODE, active=True)
        cls.mapping = PositionWorkflowResponsibility.objects.create(position=cls.pmc_position,
            responsibility=cls.pmc_responsibility, workflow_node=cls.node,
            workflow_code=PROCESS_CODE, node_code=NODE_CODE, ownership_type="OWNER", active=True)
        cls.uom = UnitOfMeasure.objects.create(company_id=cls.company.pk, code="SYNTHETIC-PCS", name="扇")
        cls.material = Material.objects.create(company_id=cls.company.pk, code="SYNTHETIC-FINISHED",
            name="合成订单产品", unit="扇", base_uom=cls.uom, material_type="finished")
        cls.customer = Customer.objects.create(company=cls.company, code="SYNTHETIC-CUSTOMER", name="合成测试客户")
        # Approved input source is built through the common state service, with
        # synthetic audits; it is not evidence of a real Sales approval workflow.
        cls.order = create_business_object_with_initial_state(model=SalesOrder,
            initial_state="draft", id=3, company=cls.company, department=cls.pmc_department,
            customer=cls.customer, order_no="SYNTHETIC-SUPPLY-ORDER", order_date=date(2026, 10, 11),
            required_delivery_date=date(2026, 10, 20), created_by=cls.creator,
            business_purpose="FORMAL_SALE", delivery_information={"evidenceSource": "SIMULATED_FOR_TEST"})
        initial_audit = OrganizationOperatingAuditRecord.objects.create(actor=cls.creator,
            organization=cls.company, action_code="fixture.sales_order.create", target_type="SalesOrder",
            target_id=cls.order.pk, target_label=cls.order.order_no, reason="隔离来源草稿初始化",
            after_snapshot={"status": "draft", "evidenceSource": "SIMULATED_FOR_TEST"})
        record_projected_business_transition(object_type="SalesOrder", object_id=cls.order.pk,
            source_state="", target_state="draft", action_code="fixture.sales_order.create",
            operator=cls.creator, reason=initial_audit.reason,
            audit_reference=f"OrganizationOperatingAuditRecord:{initial_audit.pk}", allowed_transitions=(("", "draft"),))
        for source, target, operator in (("draft", "submitted", cls.creator), ("submitted", "approved", cls.decision_user)):
            audit = OrganizationOperatingAuditRecord.objects.create(actor=operator,
                organization=cls.company, action_code=f"fixture.sales_order.{target}", target_type="SalesOrder",
                target_id=cls.order.pk, target_label=cls.order.order_no, reason="隔离供应确认上游状态来源",
                before_snapshot={"status": source}, after_snapshot={"status": target, "evidenceSource": "SIMULATED_FOR_TEST"})
            transition_business_object(business_object=cls.order, object_type="SalesOrder",
                source_state=source, target_state=target, action_code=audit.action_code, operator=operator,
                reason=audit.reason, audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}",
                allowed_transitions=((source, target),))
        cls.legacy_item = SalesOrderItem.objects.create(id=3, sales_order=cls.order, line_no=1,
            material=cls.material, quantity=Decimal("5"), uom=cls.uom, required_date=date(2026, 10, 20))
        cls.item = SalesOrderItem.objects.create(id=4, sales_order=cls.order, line_no=2,
            material=cls.material, quantity=Decimal("5"), uom=cls.uom, required_date=date(2026, 10, 20))

    def confirm(self, **changes):
        args = {"user": self.decision_user, "order_id": self.order.pk, "item_id": self.item.pk,
            "supply_type": "MAKE", "idempotency_key": "SYNTHETIC-ITEM4-MAKE-EXECUTION",
            "reason": "隔离业务指定：计划物控决策自产，由独立生产经理承接执行",
            "manufacturing_owner_user_id": self.execution_user.pk}
        args.update(changes)
        return confirm_supply_admission(**args)

    def protected(self):
        models = (SalesOrder, SalesOrderItem, Material, Demand, PlanningRequirement, User,
            Employee, Department, Position, Responsibility, PositionResponsibility,
            PositionWorkflowResponsibility, Role, Permission, RolePermission,
            UserRoleScopeAssignment, ProcessDefinition, WorkflowNodeDefinition,
            WorkflowInstance, ApprovalTask, ApprovalDecision)
        return {model.__name__: list(model.objects.order_by("pk").values()) for model in models}

    def write_counts(self):
        return (SalesOrderItemSupplyAdmission.objects.count(),
            OrganizationOperatingAuditRecord.objects.count(), BusinessStateTransition.objects.count())

    def assert_rejected_without_write(self, code=None, **changes):
        before, protected = self.write_counts(), self.protected()
        with self.assertRaises(SupplyAdmissionError) as caught:
            self.confirm(**changes)
        if code:
            self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.write_counts(), before)
        self.assertEqual(self.protected(), protected)

    def test_real_decision_authorization_and_distinct_execution_snapshot_audit_hash(self):
        protected, before = self.protected(), self.write_counts()
        decision, scope = authorize(user=self.decision_user, item=self.item)
        self.assertTrue(decision["granted"])
        self.assertEqual(scope.pk, self.grant.pk)
        result = self.confirm()
        fact = SalesOrderItemSupplyAdmission.objects.get(sales_order_item=self.item)
        self.assertEqual(result["confirmation"]["status"], "CONFIRMED")
        self.assertEqual(fact.responsibility_type, RESPONSIBILITY_TYPE)
        self.assertEqual((fact.confirmed_by_id, fact.employee_id, fact.workflow_responsibility_id),
            (self.decision_user.pk, self.decision_employee.pk, self.mapping.pk))
        responsibility = fact.responsibility_snapshot
        self.assertEqual(responsibility["userId"], self.decision_user.pk)
        self.assertEqual(responsibility["positionId"], self.pmc_position.pk)
        execution = responsibility["manufacturingExecution"]
        self.assertEqual(execution["userId"], self.execution_user.pk)
        self.assertEqual(execution["employeeId"], self.execution_employee.pk)
        self.assertEqual(execution["positionId"], self.production_position.pk)
        self.assertEqual(execution["departmentId"], self.production_department.pk)
        self.assertEqual(execution["responsibilityCode"], "RESP_PROD_PLAN_001")
        self.assertEqual(execution["positionResponsibilityId"], self.execution_duty.pk)
        self.assertEqual(execution["companyId"], self.company.pk)
        self.assertEqual(execution["assignedBy"], self.decision_user.pk)
        self.assertEqual(execution["assignmentSource"], "USER_DESIGNATED")
        self.assertIs(execution["responsibilityAssignmentOnly"], True)
        self.assertIs(execution["executionPerformed"], False)
        self.assertNotIn("workflowResponsibilityId", execution)
        self.assertFalse(UserRoleScopeAssignment.objects.filter(user=self.execution_user).exists())
        self.assertFalse(PositionWorkflowResponsibility.objects.filter(position=self.production_position).exists())
        self.assertEqual(fact.fact_hash, digest(_fact_payload(fact)))
        self.assertEqual(fact.request_hash, digest({"actor": self.decision_user.pk, "item": self.item.pk,
            "supplyType": "MAKE", "reason": fact.reason, "manufacturingOwnerUserId": self.execution_user.pk}))
        audit = fact.audit_record
        self.assertEqual(audit.actor_id, self.decision_user.pk)
        self.assertEqual(audit.after_snapshot["confirmation"], _fact_payload(fact))
        self.assertEqual(audit.after_snapshot["factHash"], fact.fact_hash)
        self.assertTrue(audit.after_snapshot["authorization"]["granted"])
        transition = BusinessStateTransition.objects.get(object_type=OBJECT_TYPE, object_id=self.item.pk)
        self.assertEqual((transition.operator_id, transition.source_state, transition.target_state),
            (self.decision_user.pk, "UNCONFIRMED", "CONFIRMED"))
        self.assertEqual(transition.audit_reference, f"OrganizationOperatingAuditRecord:{audit.pk}")
        self.assertEqual(self.write_counts(), (before[0] + 1, before[1] + 1, before[2] + 1))
        self.assertEqual(self.protected(), protected)

    def test_same_key_replay_is_zero_write_and_preserves_two_responsibilities(self):
        first = self.confirm()
        before, protected = self.write_counts(), self.protected()
        replay = self.confirm()
        self.assertTrue(replay["idempotent"])
        self.assertEqual((replay["businessWriteCount"], replay["auditWriteCount"]), (0, 0))
        self.assertEqual(replay["confirmation"], first["confirmation"])
        self.assertEqual(self.write_counts(), before)
        self.assertEqual(self.protected(), protected)

    def test_changed_or_omitted_owner_cannot_overwrite_confirmed_fact(self):
        original = self.confirm()["confirmation"]
        for owner in (self.other_execution_user.pk, None):
            self.assert_rejected_without_write("SUPPLY_ADMISSION_ALREADY_CONFIRMED", manufacturing_owner_user_id=owner)
        # Compare the persisted Decimal precision, not the construction-time
        # fixture value whose string representation predates the database read.
        self.item.refresh_from_db()
        self.assertEqual(supply_admission_facts(self.item), original)

    def test_legacy_no_owner_payload_hash_read_and_replay_are_compatible(self):
        first = self.confirm(item_id=self.legacy_item.pk, idempotency_key="SYNTHETIC-LEGACY-ITEM3",
            manufacturing_owner_user_id=None)
        fact = SalesOrderItemSupplyAdmission.objects.get(sales_order_item=self.legacy_item)
        self.assertNotIn("manufacturingExecution", fact.responsibility_snapshot)
        self.assertEqual(fact.request_hash, digest({"actor": self.decision_user.pk, "item": self.legacy_item.pk,
            "supplyType": "MAKE", "reason": fact.reason}))
        before, protected = self.write_counts(), self.protected()
        queried = query_supply_admission(user=self.decision_user, order_id=self.order.pk, item_id=self.legacy_item.pk)
        self.assertEqual(queried, first["confirmation"])
        replay = self.confirm(item_id=self.legacy_item.pk, idempotency_key="SYNTHETIC-LEGACY-ITEM3",
            manufacturing_owner_user_id=None)
        self.assertTrue(replay["idempotent"])
        self.assertEqual(replay["confirmation"], queried)
        self.assertEqual(self.write_counts(), before)
        self.assertEqual(self.protected(), protected)
        self.assert_rejected_without_write("SUPPLY_ADMISSION_ALREADY_CONFIRMED", item_id=self.legacy_item.pk,
            idempotency_key="SYNTHETIC-LEGACY-ITEM3")

    def test_invalid_owner_identifiers_do_not_write(self):
        cases = (("bool-false", False), ("bool-true", True), ("zero", 0),
            ("negative", -1), ("text", "bad"), ("empty", ""),
            ("missing-user", 999999), ("superscript-digit", "²"),
            ("arabic-digits", "٢٣"), ("signed64-overflow", 2 ** 63),
            ("fraction", 23.5), ("oversized-digits", "9" * 5000))
        for label, owner in cases:
            with self.subTest(case=label):
                self.assert_rejected_without_write("MANUFACTURING_OWNER_INVALID", manufacturing_owner_user_id=owner)

    def test_decision_user_cannot_also_be_manufacturing_execution_owner(self):
        self.assert_rejected_without_write("MANUFACTURING_OWNER_INVALID", manufacturing_owner_user_id=self.decision_user.pk)

    def test_buy_cannot_carry_manufacturing_execution_owner(self):
        self.assert_rejected_without_write("MANUFACTURING_OWNER_NOT_APPLICABLE", supply_type="BUY")

    def test_inactive_account_superuser_and_employee_each_rejected(self):
        for model, pk, field, bad, good in (
            (User, self.execution_user.pk, "is_active", False, True),
            (User, self.execution_user.pk, "is_superuser", True, False),
            (Employee, self.execution_employee.pk, "status", "inactive", "active"),
        ):
            with self.subTest(field=field):
                model.objects.filter(pk=pk).update(**{field: bad})
                self.assert_rejected_without_write("MANUFACTURING_OWNER_INVALID")
                model.objects.filter(pk=pk).update(**{field: good})

    def test_missing_employee_or_position_rejected(self):
        no_employee = User.objects.create_user(username="synthetic-no-employee", company_id=self.company.pk)
        self.assert_rejected_without_write("MANUFACTURING_OWNER_INVALID", manufacturing_owner_user_id=no_employee.pk)
        Employee.objects.filter(pk=self.execution_employee.pk).update(position_ref=None)
        self.assert_rejected_without_write("MANUFACTURING_OWNER_INVALID")

    def test_execution_account_company_scope_must_match_order(self):
        User.objects.filter(pk=self.execution_user.pk).update(company_id=self.other_company.pk)
        self.assert_rejected_without_write("MANUFACTURING_OWNER_INVALID")

    def test_execution_position_department_scope_and_lifecycle_must_be_valid(self):
        for model, pk, field, bad, good in (
            (Position, self.production_position.pk, "is_active", False, True),
            (Department, self.production_department.pk, "is_active", False, True),
            (Position, self.production_position.pk, "company_id", self.other_company.pk, self.company.pk),
            (Department, self.production_department.pk, "company_id", self.other_company.pk, self.company.pk),
            (Position, self.production_position.pk, "effective_to", date.today() - timedelta(days=1), None),
            (Employee, self.execution_employee.pk, "department_ref_id", self.pmc_department.pk, self.production_department.pk),
        ):
            with self.subTest(model=model.__name__, field=field):
                model.objects.filter(pk=pk).update(**{field: bad})
                self.assert_rejected_without_write("MANUFACTURING_OWNER_INVALID")
                model.objects.filter(pk=pk).update(**{field: good})

    def test_manufacturing_execution_requires_existing_effective_production_duty(self):
        for model, pk, field, bad, good in (
            (PositionResponsibility, self.execution_duty.pk, "active", False, True),
            (Responsibility, self.execution_responsibility.pk, "is_active", False, True),
            (Responsibility, self.execution_responsibility.pk, "status", "SUSPENDED", "ACTIVE"),
            (Responsibility, self.execution_responsibility.pk, "effective_to", date.today() - timedelta(days=1), None),
        ):
            with self.subTest(field=field):
                model.objects.filter(pk=pk).update(**{field: bad})
                self.assert_rejected_without_write("MANUFACTURING_OWNER_DUTY_MISSING")
                model.objects.filter(pk=pk).update(**{field: good})

    def test_execution_owner_duty_does_not_authorize_supply_confirmation(self):
        self.assert_rejected_without_write("SUPPLY_ADMISSION_PERMISSION_DENIED", user=self.execution_user)

    def test_real_decision_role_scope_and_workflow_mapping_cannot_be_omitted(self):
        for model, pk, field, bad, good, code in (
            (UserRoleScopeAssignment, self.grant.pk, "active", False, True, "SUPPLY_ADMISSION_PERMISSION_DENIED"),
            (UserRoleScopeAssignment, self.grant.pk, "scope_code", "SELF", "ORGANIZATION", "SUPPLY_ADMISSION_SCOPE_DENIED"),
            (PositionWorkflowResponsibility, self.mapping.pk, "active", False, True, "SUPPLY_ADMISSION_WORKFLOW_DUTY_MISSING"),
        ):
            with self.subTest(model=model.__name__, field=field):
                model.objects.filter(pk=pk).update(**{field: bad})
                self.assert_rejected_without_write(code)
                model.objects.filter(pk=pk).update(**{field: good})

    def test_transaction_fault_rolls_back_fact_audit_and_transition(self):
        before, protected = self.write_counts(), self.protected()
        with patch("sales.supply_admission_service.record_projected_business_transition",
                side_effect=RuntimeError("isolated-state-transition-fault")):
            with self.assertRaises(RuntimeError):
                self.confirm()
        self.assertEqual(self.write_counts(), before)
        self.assertEqual(self.protected(), protected)

    def test_execution_audit_tampering_blocks_read_and_idempotent_replay(self):
        self.confirm()
        fact = SalesOrderItemSupplyAdmission.objects.get(sales_order_item=self.item)
        changed = deepcopy(fact.audit_record.after_snapshot)
        changed["confirmation"]["responsibility"]["manufacturingExecution"]["userId"] = self.other_execution_user.pk
        OrganizationOperatingAuditRecord.objects.filter(pk=fact.audit_record_id).update(after_snapshot=changed)
        read = supply_admission_facts(self.item)
        self.assertEqual(read["status"], "INVALID")
        self.assertEqual(read["supplyBranch"], "UNRESOLVED")
        self.assert_rejected_without_write("SUPPLY_ADMISSION_HISTORY_INVALID")

    def test_api_accepts_only_designated_owner_id_not_client_responsibility_facts(self):
        client = APIClient()
        client.force_authenticate(self.decision_user)
        url = f"/api/sales/orders/{self.order.pk}/items/{self.item.pk}/supply-admission/"
        payload = {"supplyType": "MAKE", "idempotencyKey": "SYNTHETIC-API-OWNER",
            "reason": "隔离API人工指定制造执行责任", "manufacturingOwnerUserId": self.execution_user.pk}
        before, protected = self.write_counts(), self.protected()
        for field in ("confirmedBy", "employeeId", "positionId", "manufacturingExecution", "executionPerformed"):
            with self.subTest(field=field):
                response = client.post(url, {**payload, field: self.execution_user.pk}, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.write_counts(), before)
        response = client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        fact = response.data["data"]["confirmation"]
        self.assertEqual(fact["confirmedBy"], self.decision_user.pk)
        self.assertEqual(fact["responsibility"]["manufacturingExecution"]["userId"], self.execution_user.pk)
        self.assertEqual(client.get(url).data["data"]["confirmation"], fact)
        before_replay = self.write_counts()
        self.assertTrue(client.post(url, payload, format="json").data["data"]["idempotent"])
        self.assertEqual(self.write_counts(), before_replay)
        self.assertEqual(self.protected(), protected)

