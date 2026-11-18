"""Task integration tests: run ONLY on the guarded acceptance database clone."""
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase
from rest_framework.test import APIClient

from planning.models import Demand, PlanningRequirement
from system.models import User, UserRoleScopeAssignment, OrganizationOperatingAuditRecord, Role, RolePermission, Permission, PositionWorkflowResponsibility, PositionResponsibility
from workflow_runtime.action_permissions import ActionPermissionValidator, POLICIES
from workflow_runtime.models import BusinessStateTransition

from .models import SalesOrder, SalesOrderItem, SalesOrderItemSupplyAdmission
from .services import engineering_readiness_facts, generate_demand, SalesBusinessError
from .supply_admission_contract import ACTION_CODE, MODULE_CODE, PROCESS_CODE, ROLE_CODE
from .supply_admission_configuration import configure_supply_admission
from .supply_admission_service import SupplyAdmissionError, confirm_supply_admission, query_supply_admission, supply_admission_facts


class OrderLineSupplyAdmissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        if "order-line-supply-admission-isolated" not in str(settings.DATABASES["default"]["NAME"]):
            raise RuntimeError("这些测试必须使用隔离数据库，禁止真实订单测试写入。")
        cls.actor = User.objects.get(pk=1)
        cls.owner = User.objects.get(pk=30)
        cls.creator = User.objects.get(pk=11)
        cls.order = SalesOrder.objects.get(pk=3)
        cls.item = SalesOrderItem.objects.get(pk=3)
        cls.config = configure_supply_admission(actor=cls.actor, responsible_user=cls.owner, order_id=3, company_code="COMP001", reason="隔离测试：人工已指定计划物控经理承担订单行供应承接确认")

    def confirm(self, **changes):
        args = dict(user=self.owner, order_id=3, item_id=3, supply_type="MAKE", idempotency_key="ISOLATED-SUPPLY-ITEM3", reason="隔离测试：订单行5扇由企业内部制造承接")
        args.update(changes)
        return confirm_supply_admission(**args)

    def test_formal_make_fact_and_all_protected_rows_unchanged(self):
        order_before = SalesOrder.objects.filter(pk=3).values().get()
        item_before = SalesOrderItem.objects.filter(pk=3).values().get()
        material_before = type(self.item.material).objects.filter(pk=275).values().get()
        counts = (Demand.objects.count(), PlanningRequirement.objects.count())
        result = self.confirm()
        fact = SalesOrderItemSupplyAdmission.objects.get(sales_order_item_id=3)
        self.assertEqual(result["confirmation"]["status"], "CONFIRMED")
        self.assertEqual(fact.supply_type, "MAKE")
        self.assertEqual((fact.confirmed_by_id, fact.employee_id, fact.position_responsibility_id), (30, 122, 118))
        self.assertEqual(result["confirmation"]["responsibility"]["positionName"], "计划物控部经理")
        self.assertEqual(SalesOrder.objects.filter(pk=3).values().get(), order_before)
        self.assertEqual(SalesOrderItem.objects.filter(pk=3).values().get(), item_before)
        self.assertEqual(type(self.item.material).objects.filter(pk=275).values().get(), material_before)
        self.assertEqual((Demand.objects.count(), PlanningRequirement.objects.count()), counts)
        self.assertEqual(fact.audit_record.actor_id, 30)
        transition = BusinessStateTransition.objects.get(object_type="SalesOrderItemSupplyAdmission", object_id=3)
        self.assertEqual(transition.operator_id, 30)

    def test_same_request_replay_writes_nothing(self):
        first = self.confirm()
        audit_count = OrganizationOperatingAuditRecord.objects.count()
        replay = self.confirm()
        self.assertTrue(replay["idempotent"])
        self.assertEqual(replay["businessWriteCount"], 0)
        self.assertEqual(first["confirmation"]["factId"], replay["confirmation"]["factId"])
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), audit_count)

    def test_conflicting_mode_reason_and_key_cannot_overwrite(self):
        self.confirm()
        for change in ({"supply_type": "BUY"}, {"reason": "不同确认依据"}, {"idempotency_key": "OTHER-KEY"}):
            with self.assertRaises(SupplyAdmissionError):
                self.confirm(**change)
        self.assertEqual(SalesOrderItemSupplyAdmission.objects.get(sales_order_item_id=3).supply_type, "MAKE")

    def test_other_modes_and_invalid_keys_are_fail_closed(self):
        for change in ({"supply_type": "OTHER"}, {"supply_type": ""}, {"idempotency_key": ""}, {"reason": "x"}):
            with self.assertRaises(SupplyAdmissionError):
                self.confirm(**change)
        self.assertFalse(SalesOrderItemSupplyAdmission.objects.exists())

    def test_no_fact_is_unresolved_even_if_material_looks_buy_or_make(self):
        for mode in ("purchase", "production"):
            with patch.object(type(self.item.material), "supply_type", new=property(lambda row: mode)):
                facts = engineering_readiness_facts(self.order)
                self.assertEqual(facts["lines"][0]["supplyBranch"], "UNRESOLVED")
        self.assertEqual(query_supply_admission(user=self.owner, order_id=3, item_id=3)["status"], "UNRESOLVED")

    def test_shared_registry_validator_and_demand_read_same_fact(self):
        decision = ActionPermissionValidator().evaluate(user=self.owner, module_code=MODULE_CODE, action_code=ACTION_CODE, object_ids=[3], selection_count=1)
        self.assertTrue(decision["granted"])
        self.confirm()
        facts = engineering_readiness_facts(self.order)["lines"][0]
        self.assertEqual(facts["supplyBranch"], "MAKE")
        self.assertFalse(any("供应" in reason for reason in facts["blockers"]))
        self.assertFalse(facts["ready"])
        self.assertIn("制造型订单行缺少正式销售产品身份/ProductDefinition", facts["blockers"])
        with self.assertRaises(SalesBusinessError) as caught:
            generate_demand(user=self.creator, order_id=3, authorization={"allowed": True})
        self.assertEqual(caught.exception.code, "ORDER_DEMAND_MANUFACTURING_NOT_READY")

    def test_sales_approver_or_admin_cannot_substitute(self):
        grant = UserRoleScopeAssignment.objects.get(user_id=30, role__code=ROLE_CODE)
        grant.active = False
        grant.save(update_fields=["active"])
        with self.assertRaises(SupplyAdmissionError):
            self.confirm()
        with self.assertRaises(SupplyAdmissionError):
            self.confirm(user=self.actor)
        with self.assertRaises(SupplyAdmissionError):
            self.confirm(user=self.creator)

    def test_exact_role_scope_and_effective_duty_required(self):
        grant = UserRoleScopeAssignment.objects.get(user_id=30, role__code=ROLE_CODE)
        grant.scope_code = "SELF"
        grant.save(update_fields=["scope_code"])
        with self.assertRaisesRegex(SupplyAdmissionError, "专用角色范围"):
            self.confirm()

    def test_missing_workflow_mapping_rejects_without_writes(self):
        mapping = PositionWorkflowResponsibility.objects.get(pk=self.config["workflowResponsibilityId"])
        mapping.active = False
        mapping.save(update_fields=["active"])
        before = OrganizationOperatingAuditRecord.objects.count()
        with self.assertRaises(SupplyAdmissionError):
            self.confirm()
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), before)

    def test_missing_pmc_duty_rejects_without_writes(self):
        duty = PositionResponsibility.objects.get(pk=118)
        duty.active = False
        duty.save(update_fields=["active"])
        with self.assertRaises(SupplyAdmissionError):
            self.confirm()

    def test_transaction_rolls_back_fact_and_audit_on_transition_failure(self):
        before = OrganizationOperatingAuditRecord.objects.count()
        with patch("sales.supply_admission_service.record_projected_business_transition", side_effect=RuntimeError("isolated failure")):
            with self.assertRaises(RuntimeError):
                self.confirm()
        self.assertFalse(SalesOrderItemSupplyAdmission.objects.exists())
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), before)

    def test_broken_audit_or_transition_never_grants_readiness(self):
        self.confirm()
        transition = BusinessStateTransition.objects.get(object_type="SalesOrderItemSupplyAdmission", object_id=3)
        transition.audit_reference = "MISSING"
        transition.save(update_fields=["audit_reference"])
        self.assertEqual(supply_admission_facts(self.item)["status"], "INVALID")
        self.assertEqual(engineering_readiness_facts(self.order)["lines"][0]["supplyBranch"], "UNRESOLVED")

    def test_stale_source_and_model_mutation_are_rejected(self):
        self.confirm()
        item = SalesOrderItem.objects.get(pk=3)
        item.quantity += 1  # In-memory drift only, no protected source writes.
        self.assertEqual(supply_admission_facts(item)["status"], "STALE")
        fact = SalesOrderItemSupplyAdmission.objects.get(sales_order_item_id=3)
        with self.assertRaises(ValidationError):
            fact.save()
        with self.assertRaises(ValidationError):
            fact.delete()

    def test_configuration_replay_preserves_old_role_permissions(self):
        before = list(RolePermission.objects.order_by("pk").values())
        replay = configure_supply_admission(actor=self.actor, responsible_user=self.owner, order_id=3, company_code="COMP001", reason="隔离重复配置")
        self.assertTrue(replay["idempotent"])
        self.assertEqual(before, list(RolePermission.objects.order_by("pk").values()))
        self.assertEqual(RolePermission.objects.filter(role__code=ROLE_CODE).count(), 1)

    def test_api_confirmation_query_replay_and_identity_spoof_rejection(self):
        client = APIClient()
        client.force_authenticate(self.owner)
        url = "/api/sales/orders/3/items/3/supply-admission/"
        payload = {"supplyType": "MAKE", "idempotencyKey": "API-ISOLATED", "reason": "隔离API确认自产"}
        response = client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["confirmation"]["confirmedBy"], 30)
        self.assertTrue(client.post(url, payload, format="json").data["data"]["idempotent"])
        self.assertEqual(client.get(url).data["data"]["confirmation"]["status"], "CONFIRMED")
        response = client.post(url, {**payload, "confirmedBy": 1}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_configuration_permission_or_conflict_rolls_back(self):
        with self.assertRaises(SupplyAdmissionError):
            configure_supply_admission(actor=self.owner, responsible_user=self.owner, order_id=3, company_code="COMP001", reason="隔离未授权配置")
        role = Role.objects.get(code=ROLE_CODE)
        role.description = "冲突"
        role.save(update_fields=["description"])
        with self.assertRaises(SupplyAdmissionError):
            configure_supply_admission(actor=self.actor, responsible_user=self.owner, order_id=3, company_code="COMP001", reason="隔离语义冲突")

    def test_buy_is_explicit_and_key_cannot_move_to_another_line(self):
        result = self.confirm(supply_type="BUY")
        self.assertEqual(result["confirmation"]["supplyBranch"], "BUY")
        self.assertEqual(result["confirmation"]["reason"], "隔离测试：订单行5扇由企业内部制造承接")
        with self.assertRaises(SupplyAdmissionError) as caught:
            self.confirm(item_id=4)
        self.assertEqual(caught.exception.code, "IDEMPOTENCY_KEY_CONFLICT")

    def test_creator_cannot_confirm_even_with_dedicated_role(self):
        UserRoleScopeAssignment.objects.create(user=self.creator, role=Role.objects.get(code=ROLE_CODE), organization_id=1, scope_code="ORGANIZATION", business_hash="isolated-test")
        with self.assertRaises(SupplyAdmissionError) as caught:
            self.confirm(user=self.creator)
        self.assertEqual(caught.exception.code, "SUPPLY_ADMISSION_SOD_DENIED")

    def test_inactive_account_and_employee_are_rejected(self):
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with self.assertRaises(SupplyAdmissionError):
            self.confirm()
        self.owner.is_active = True
        self.owner.save(update_fields=["is_active"])
        employee = self.owner.employee_profile
        employee.status = "inactive"
        employee.save(update_fields=["status"])
        with self.assertRaises(SupplyAdmissionError):
            self.confirm()

    def test_api_invalid_shape_and_db_failure_are_not_empty_success(self):
        from django.db import DatabaseError
        client = APIClient()
        client.force_authenticate(self.owner)
        url = "/api/sales/orders/3/items/3/supply-admission/"
        self.assertEqual(client.post(url, [], format="json").status_code, 400)
        with patch("sales.supply_admission_views.query_supply_admission", side_effect=DatabaseError("isolated read failure")):
            response = client.get(url)
        self.assertEqual(response.status_code, 503)
        facts = response.data["data"]["factLoadFacts"]
        self.assertEqual(facts["factLoadStatus"], "read_failed")
        for key in ("apiUrl", "errorCode", "errorMessage", "loadedAt", "tenantId", "batchId"):
            self.assertTrue(facts[key])
        self.assertFalse(response.data["data"]["strictFacts"]["passed"])
