from datetime import date, timedelta
from decimal import Decimal
from copy import deepcopy
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from masterdata.models import ExternalIdentity, MasterDataWriteRequest, Material, UnitOfMeasure
from pfm.models import Employee
from planning.models import Demand, PlanningRequirement
from system.models import Company, Department, OrganizationOperatingAuditRecord, Position, PositionResponsibility, PositionWorkflowResponsibility, Responsibility, User, Permission
from workflow_runtime.models import ApprovalDecision, ApprovalTask, BusinessStateTransition, ProcessDefinition, WorkflowInstance, WorkflowNodeDefinition
from workflow_runtime import state_transitions

from .models import Customer, SalesOrder, SalesOrderActionRequest
from .services import (
    SalesBusinessError, confirm_order, create_order, engineering_readiness_facts,
    generate_demand, perform_order_action, update_order, update_order_item,
)
from .source_intake import _canonical_hash, commit_source_intake, governed_source_contract
from .whole_house_preview import SOURCE_SHA256, WHOLE_HOUSE_ORDER_SOURCE_MAPPING, whole_house_order_preview


class SalesOrderToDemandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company=Company.objects.create(code="SO-T",name="销售订单测试组织")
        cls.department=Department.objects.create(company=cls.company,code="YXB-T",name="营销测试部")
        cls.position=Position.objects.create(company=cls.company,department=cls.department,code="YXB-SALES-T",name="销售订单测试岗")
        cls.responsibility,_=Responsibility.objects.update_or_create(code="RESP_SALES_ORDER_002",defaults={"name":"销售需求与订单协调","is_active":True,"status":"ACTIVE"})
        cls.user=User.objects.create_user(username="sales_test",password="not-used",real_name="销售测试",company_id=cls.company.pk)
        Employee.objects.create(user=cls.user,employee_no="SOE-T",full_name="销售测试",status="active",department_ref=cls.department,position_ref=cls.position)
        cls.approver=User.objects.create_user(username="sales_approver",password="not-used",real_name="销售审批",company_id=cls.company.pk)
        Employee.objects.create(user=cls.approver,employee_no="SOA-T",full_name="销售审批",status="active",department_ref=cls.department,position_ref=cls.position)
        cls.customer=Customer.objects.create(company=cls.company,code="C-T",name="测试客户")
        cls.material=Material.objects.create(code="MT-SO-T",name="销售订单测试物料",unit="件",company_id=cls.company.pk,is_active=True,is_purchased=True,is_produced=False)
        process,_=ProcessDefinition.objects.update_or_create(definition_code="SALES_ORDER_TO_SUPPLY_PLAN",defaults={"definition_name":"测试销售订单流程","business_domain":"SALES","document_type":"SalesOrder","version":1,"active":True,"definition_hash":"t"})
        actions = (
            ("CREATE", "sales.order.create"), ("CONFIRM", "sales.order.confirm"),
            ("DEMAND", "sales.order.generate_demand"), ("UPDATE", "sales.order.update"),
            ("SUBMIT", "sales.order.submit"), ("APPROVE", "sales.order.approve"),
            ("ENG_START", "sales.order.engineering.start"),
            ("ENG_COMPLETE", "sales.order.engineering.complete"),
            ("EXEC_START", "sales.order.execution.start"),
        )
        for sequence,(node_code,action) in enumerate(actions,1):
            node,_=WorkflowNodeDefinition.objects.update_or_create(process_definition=process,node_code=node_code,defaults={"node_name":node_code,"sequence":sequence+100,"business_action_code":action,"active":True})
            PositionWorkflowResponsibility.objects.update_or_create(position=cls.position,workflow_code="SALES_ORDER_TO_SUPPLY_PLAN",node_code=node_code,ownership_type="OWNER",defaults={"responsibility":cls.responsibility,"workflow_node":node,"active":True})

    def payload(self):
        return {"customerId":self.customer.pk,"materialId":self.material.pk,"departmentId":self.department.pk,"quantity":"6","requiredDate":(date.today()+timedelta(days=15)).isoformat()}

    def provide_buy_admission(self, order):
        # Supply is now an explicit order-line fact, never a Material fallback.
        from .supply_admission_configuration import configure_supply_admission
        from .supply_admission_service import confirm_supply_admission
        manager = User.objects.create_superuser(username="sales_supply_test_config", password="not-used", real_name="隔离配置", company_id=self.company.pk)
        duty, _ = Responsibility.objects.get_or_create(code="RESP_PMC_MATERIAL_002", defaults={"name": "物料需求计划与供应协调", "status": "ACTIVE", "is_active": True})
        PositionResponsibility.objects.get_or_create(position=self.position, responsibility=duty)
        Permission.objects.get_or_create(code="system.organization.workflow_responsibility.manage", defaults={"name": "流程责任维护", "module": "SYSTEM"})
        configure_supply_admission(actor=manager, responsible_user=self.approver, order_id=order.pk, company_code=self.company.code, reason="隔离回归：指定独立供应确认责任人")
        for item in order.items.all():
            confirm_supply_admission(user=self.approver, order_id=order.pk, item_id=item.pk, supply_type="BUY", idempotency_key=f"TEST-BUY-{item.pk}", reason="隔离回归：该订单行采购承接")

    def test_confirmed_order_generates_one_linked_demand_with_inherited_facts(self):
        order,item,_=create_order(user=self.user,payload=self.payload(),authorization={"allowed":True},business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE)
        self.assertEqual(order.status,"draft")
        order,_=confirm_order(user=self.user,order_id=order.pk,authorization={"allowed":True})
        self.provide_buy_admission(order)
        demand,_=generate_demand(user=self.user,order_id=order.pk,authorization={"allowed":True})
        self.assertEqual(demand.sales_order_item_id,item.pk)
        self.assertEqual(demand.required_qty,Decimal("6"))
        self.assertEqual(demand.required_date,item.required_date)
        self.assertEqual(demand.source_type,"sales_order")
        self.assertEqual(BusinessStateTransition.objects.filter(object_type="SalesOrder",object_id=order.pk).count(),1)

    def test_unconfirmed_and_duplicate_generation_are_blocked(self):
        order,_,_=create_order(user=self.user,payload=self.payload(),authorization={"allowed":True},business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE)
        with self.assertRaisesRegex(SalesBusinessError,"只有已确认"):
            generate_demand(user=self.user,order_id=order.pk,authorization={"allowed":True})
        confirm_order(user=self.user,order_id=order.pk,authorization={"allowed":True})
        self.provide_buy_admission(order)
        generate_demand(user=self.user,order_id=order.pk,authorization={"allowed":True})
        repeated, audit = generate_demand(user=self.user,order_id=order.pk,authorization={"allowed":True})
        self.assertIsNone(audit)
        self.assertEqual(repeated.sales_order_item.sales_order_id, order.pk)
        self.assertEqual(Demand.objects.filter(sales_order_item__sales_order=order).count(),1)

    def _ready_demand_order(self):
        order, _, _ = create_order(
            user=self.user, payload=self.payload(), authorization={"allowed": True},
            business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
        )
        confirm_order(user=self.user, order_id=order.pk, authorization={"allowed": True})
        self.provide_buy_admission(order)
        return order

    def _demand_write_snapshot(self):
        return {
            "demands": list(Demand.objects.order_by("pk").values()),
            "audits": list(OrganizationOperatingAuditRecord.objects.order_by("pk").values()),
            "transitions": list(BusinessStateTransition.objects.order_by("pk").values()),
            "requirements": list(PlanningRequirement.objects.order_by("pk").values()),
        }

    def test_demand_uses_shared_draft_initialization_and_audited_state_history(self):
        order = self._ready_demand_order()
        initialized_states = []

        def initialize(**kwargs):
            demand = state_transitions.create_business_object_with_initial_state(**kwargs)
            initialized_states.append(demand.status)
            self.assertFalse(BusinessStateTransition.objects.filter(
                object_type="Demand", object_id=demand.pk,
            ).exists())
            return demand

        def confirm(**kwargs):
            demand = kwargs["business_object"]
            self.assertEqual(demand.status, "draft")
            initial = BusinessStateTransition.objects.get(
                object_type="Demand", object_id=demand.pk,
            )
            self.assertEqual((initial.source_state, initial.target_state, initial.version),
                             ("", "draft", 1))
            return state_transitions.transition_business_object(**kwargs)

        with patch("sales.services.create_business_object_with_initial_state", side_effect=initialize) as initializer, \
                patch("sales.services.transition_business_object", side_effect=confirm):
            demand, audit = generate_demand(
                user=self.user, order_id=order.pk, authorization={"allowed": True},
            )
        initializer.assert_called_once()
        self.assertIs(initializer.call_args.kwargs["model"], Demand)
        self.assertEqual(initializer.call_args.kwargs["initial_state"], "draft")
        self.assertEqual(initialized_states, ["draft"])
        demand.refresh_from_db()
        self.assertEqual(demand.status, "confirmed")
        history = list(BusinessStateTransition.objects.filter(
            object_type="Demand", object_id=demand.pk,
        ).order_by("version"))
        self.assertEqual([(row.source_state, row.target_state, row.version) for row in history],
                         [("", "draft", 1), ("draft", "confirmed", 2)])
        self.assertEqual(len({row.audit_reference for row in history}), 2)
        for row in history:
            self.assertEqual(row.action_code, "sales.order.generate_demand")
            self.assertEqual(row.operator_id, self.user.pk)
            self.assertTrue(row.reason.strip())
            self.assertIsNotNone(row.timestamp)
            prefix, audit_id = row.audit_reference.split(":")
            self.assertEqual(prefix, "OrganizationOperatingAuditRecord")
            proof = OrganizationOperatingAuditRecord.objects.get(pk=int(audit_id))
            self.assertEqual(proof.target_type, "Demand")
            self.assertEqual(proof.target_id, demand.pk)
            self.assertEqual(proof.actor_id, self.user.pk)
            self.assertEqual(proof.action_code, row.action_code)
            self.assertEqual(proof.after_snapshot["state"]["status"], row.target_state)
            self.assertLessEqual(proof.created_at, row.timestamp)
        initial_audit = OrganizationOperatingAuditRecord.objects.get(
            pk=int(history[0].audit_reference.split(":")[1]),
        )
        self.assertEqual(initial_audit.before_snapshot["state"], {})
        self.assertEqual(audit.pk, int(history[1].audit_reference.split(":")[1]))
        self.assertEqual(audit.before_snapshot["state"]["status"], "draft")
        self.assertEqual(audit.after_snapshot["state"]["initialState"], "draft")
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(
            target_type="Demand", target_id=demand.pk,
        ).count(), 2)
        self.assertEqual(PlanningRequirement.objects.count(), 0)

    def test_demand_generation_replay_preserves_rows_audits_and_transitions(self):
        order = self._ready_demand_order()
        demand, audit = generate_demand(
            user=self.user, order_id=order.pk, authorization={"allowed": True},
        )
        before = self._demand_write_snapshot()
        repeated, repeated_audit = generate_demand(
            user=self.user, order_id=order.pk, authorization={"allowed": True},
        )
        self.assertEqual(repeated.pk, demand.pk)
        self.assertIsNone(repeated_audit)
        all_demands, all_audits = generate_demand(
            user=self.user, order_id=order.pk, authorization={"allowed": True}, return_all=True,
        )
        self.assertEqual([value.pk for value in all_demands], [demand.pk])
        self.assertEqual(all_audits, [])
        self.assertEqual(before, self._demand_write_snapshot())
        self.assertTrue(OrganizationOperatingAuditRecord.objects.filter(pk=audit.pk).exists())

    def test_existing_legacy_demand_replay_does_not_backfill_state_history(self):
        order = self._ready_demand_order()
        demand, _ = generate_demand(
            user=self.user, order_id=order.pk, authorization={"allowed": True},
        )
        # Isolated legacy-history fault injection: no formal data is changed,
        # and replay must not manufacture missing historical state evidence.
        BusinessStateTransition.objects.filter(object_type="Demand", object_id=demand.pk).delete()
        before = self._demand_write_snapshot()
        with patch("sales.services.create_business_object_with_initial_state") as initializer, \
                patch("sales.services.record_projected_business_transition") as initial_history, \
                patch("sales.services.transition_business_object") as confirmer:
            repeated, repeated_audit = generate_demand(
                user=self.user, order_id=order.pk, authorization={"allowed": True},
            )
        self.assertEqual(repeated.pk, demand.pk)
        self.assertEqual(repeated.status, "confirmed")
        self.assertIsNone(repeated_audit)
        initializer.assert_not_called()
        initial_history.assert_not_called()
        confirmer.assert_not_called()
        self.assertEqual(before, self._demand_write_snapshot())

    def test_demand_initial_transition_failure_rolls_back_creation_and_audits(self):
        order = self._ready_demand_order()
        before = self._demand_write_snapshot()

        def record_then_fail(**kwargs):
            state_transitions.record_projected_business_transition(**kwargs)
            raise RuntimeError("isolated Demand initialization failure")

        with patch("sales.services.record_projected_business_transition", side_effect=record_then_fail):
            with self.assertRaisesRegex(RuntimeError, "Demand initialization failure"):
                generate_demand(user=self.user, order_id=order.pk, authorization={"allowed": True})
        self.assertEqual(before, self._demand_write_snapshot())
        self.assertEqual(Demand.objects.count(), 0)

    def test_formal_lifecycle_uses_approval_sod_idempotency_and_state_history(self):
        order,_,_=create_order(user=self.user,payload=self.payload(),authorization={"allowed":True},business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE)
        request = lambda key: {"idempotencyKey": key, "requestId": f"REQ-{key}", "source": "test"}
        order,_,_,_=perform_order_action(user=self.user,order_id=order.pk,action="submit",payload=request("submit"),authorization={"allowed":True})
        self.assertEqual(order.status,"submitted")
        self.assertEqual(WorkflowInstance.objects.filter(document_type="SalesOrder",document_id=order.pk,status="pending").count(),1)
        self.assertEqual(ApprovalTask.objects.filter(workflow_instance__document_id=order.pk,status="pending").count(),1)
        with self.assertRaisesRegex(SalesBusinessError,"不得批准本人"):
            perform_order_action(user=self.user,order_id=order.pk,action="approve",payload=request("self-approve"),authorization={"allowed":True})
        order,_,action_request,idempotent=perform_order_action(user=self.approver,order_id=order.pk,action="approve",payload=request("approve"),authorization={"allowed":True})
        self.assertFalse(idempotent)
        self.assertEqual(order.status,"approved")
        self.assertEqual(ApprovalDecision.objects.filter(task__workflow_instance__document_id=order.pk,decision="approved").count(),1)
        repeated,_,repeated_request,idempotent=perform_order_action(user=self.approver,order_id=order.pk,action="approve",payload=request("approve"),authorization={"allowed":True})
        self.assertTrue(idempotent)
        self.assertEqual(repeated_request.pk,action_request.pk)
        self.assertEqual(repeated.status,"approved")
        self.provide_buy_admission(order)
        order,_,_,_=perform_order_action(user=self.user,order_id=order.pk,action="start-engineering",payload=request("engineering"),authorization={"allowed":True})
        order,_,_,_=perform_order_action(user=self.user,order_id=order.pk,action="complete-engineering",payload=request("ready"),authorization={"allowed":True})
        order,_,_,_=perform_order_action(user=self.user,order_id=order.pk,action="start-execution",payload=request("execute"),authorization={"allowed":True})
        self.assertEqual(order.status,"in_progress")
        self.assertEqual(BusinessStateTransition.objects.filter(object_type="SalesOrder",object_id=order.pk).count(),5)
        self.assertEqual(SalesOrderActionRequest.objects.filter(sales_order=order).count(),5)

    def test_draft_update_uses_optimistic_version(self):
        order,item,_=create_order(user=self.user,payload=self.payload(),authorization={"allowed":True},business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE)
        order,_=update_order(user=self.user,order_id=order.pk,payload={"version":1,"orderType":"project","remark":"客户确认范围"},authorization={"allowed":True})
        self.assertEqual(order.order_type,"project")
        self.assertEqual(order.version,2)
        order,item,_=update_order_item(user=self.user,order_id=order.pk,item_id=item.pk,payload={"version":2,"quantity":"7","unitPrice":"12.5","spaceCode":"ROOM-A"},authorization={"allowed":True})
        self.assertEqual(order.version,3)
        self.assertEqual(item.quantity,Decimal("7"))
        self.assertEqual(item.amount,Decimal("87.5"))
        with self.assertRaisesRegex(SalesBusinessError,"刷新后重试"):
            update_order(user=self.user,order_id=order.pk,payload={"version":1,"remark":"过期写入"},authorization={"allowed":True})

    def test_api_exposes_server_detail_and_idempotent_action_contract(self):
        self.user.is_superuser=True
        self.user.save(update_fields=["is_superuser"])
        order,_,_=create_order(user=self.user,payload=self.payload(),authorization={"allowed":True},business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE)
        client=APIClient();client.force_authenticate(self.user)
        facts=client.get("/api/sales/facts/",{"search":order.order_no,"status":"draft"})
        self.assertEqual(facts.status_code,200)
        self.assertEqual(facts.data["data"]["orders"][0]["orderNo"],order.order_no)
        self.assertEqual(facts.data["data"]["factLoadFacts"]["factLoadStatus"],"loaded")
        detail=client.get(f"/api/sales/orders/{order.pk}/")
        self.assertEqual(detail.status_code,200)
        self.assertEqual(detail.data["data"]["order"]["engineeringReadiness"]["blockerCount"],1)
        self.assertEqual(detail.data["data"]["order"]["engineeringReadiness"]["lines"][0]["supplyBranch"],"UNRESOLVED")
        payload={"requestId":"API-REQ-1","idempotencyKey":"API-IDEMP-1","source":"api-test"}
        first=client.post(f"/api/sales/orders/{order.pk}/actions/submit/",payload,format="json")
        repeated=client.post(f"/api/sales/orders/{order.pk}/actions/submit/",payload,format="json")
        self.assertEqual(first.status_code,200)
        self.assertEqual(repeated.status_code,200)
        self.assertFalse(first.data["data"]["idempotent"])
        self.assertTrue(repeated.data["data"]["idempotent"])

    def test_detail_projects_all_order_lines_and_distinct_delivery_dates(self):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        required = (date.today() + timedelta(days=15)).isoformat()
        committed = (date.today() + timedelta(days=12)).isoformat()
        planned = (date.today() + timedelta(days=10)).isoformat()
        actual = (date.today() + timedelta(days=9)).isoformat()
        payload = {
            **self.payload(),
            "deliveryInformation": {
                "committedDeliveryDate": committed,
                "plannedCompletionDate": planned,
                "batches": [
                    {"batchNo": "D-1", "lineNo": 1, "quantity": "2", "actualDeliveryDate": actual},
                    {"batchNo": "D-2", "lineNo": 2, "quantity": "1", "committedDeliveryDate": committed},
                ],
            },
            "items": [
                {"materialId": self.material.pk, "quantity": "6", "requiredDate": required, "engineeringMode": "STANDARD"},
                {"materialId": self.material.pk, "quantity": "3", "requiredDate": required, "engineeringMode": "STANDARD"},
            ],
        }
        order, _, _ = create_order(user=self.user, payload=payload, authorization={"allowed": True}, business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE)
        client = APIClient()
        client.force_authenticate(self.user)
        detail = client.get(f"/api/sales/orders/{order.pk}/")
        self.assertEqual(detail.status_code, 200)
        facts = detail.data["data"]["order"]
        self.assertEqual(len(facts["items"]), 2)
        self.assertEqual(len(facts["planningChain"]["lines"]), 2)
        self.assertEqual(facts["deliveryFacts"]["customerRequiredDate"], required)
        self.assertEqual(facts["deliveryFacts"]["committedDeliveryDate"], committed)
        self.assertEqual(facts["deliveryFacts"]["plannedCompletionDate"], planned)
        self.assertEqual(facts["deliveryFacts"]["lines"][0]["deliveredQty"], "2")
        self.assertEqual(facts["deliveryFacts"]["lines"][1]["remainingQty"], "3.0000")

    def test_delivery_conflicts_are_exposed_and_not_counted_as_actual_delivery(self):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        required = (date.today() + timedelta(days=15)).isoformat()
        actual = (date.today() + timedelta(days=9)).isoformat()
        payload = {
            **self.payload(),
            "deliveryInformation": {
                "batches": [
                    {"batchNo": "D-VALID", "lineNo": 1, "quantity": "2", "actualDeliveryDate": actual},
                    {"batchNo": "D-VALID", "lineNo": 1, "quantity": "2", "actualDeliveryDate": actual},
                    {"batchNo": "D-UNMATCHED", "lineNo": 99, "quantity": "5", "actualDeliveryDate": actual},
                ],
            },
            "items": [
                {"materialId": self.material.pk, "quantity": "6", "requiredDate": required, "engineeringMode": "STANDARD"},
            ],
        }
        order, _, _ = create_order(user=self.user, payload=payload, authorization={"allowed": True}, business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE)
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get(f"/api/sales/orders/{order.pk}/")
        facts = response.data["data"]["order"]["deliveryFacts"]
        self.assertEqual(facts["lines"][0]["deliveredQty"], "2")
        self.assertEqual(facts["lines"][0]["remainingQty"], "4.0000")
        self.assertEqual(facts["associationConflictCount"], 2)
        self.assertEqual(facts["unmatchedBatches"][0]["lineNo"], 99)
        self.assertEqual(facts["batches"][1]["associationStatus"], "CONFLICT")

    def test_historical_system_acceptance_order_is_retained_but_excluded_from_future_demand(self):
        payload = {**self.payload(), "acceptanceMarker": "PCE-SO-PLAN-V1.0 / TEST"}
        order, _, _ = create_order(user=self.user, payload=payload, authorization={"allowed": True}, business_purpose=SalesOrder.BusinessPurpose.SYSTEM_TEST)
        confirm_order(user=self.user, order_id=order.pk, authorization={"allowed": True})
        readiness = engineering_readiness_facts(order)
        self.assertEqual(readiness["businessClassification"]["code"], "TEST_SYSTEM_ACCEPTANCE_NON_BUSINESS_SAMPLE")
        self.assertFalse(readiness["businessClassification"]["planningDemandEligible"])
        with self.assertRaises(SalesBusinessError) as caught:
            generate_demand(user=self.user, order_id=order.pk, authorization={"allowed": True})
        self.assertEqual(caught.exception.code, "SALES_ORDER_NON_BUSINESS_SAMPLE_EXCLUDED")
        self.assertEqual(Demand.objects.filter(sales_order_item__sales_order=order).count(), 0)

    def test_whole_house_sample_preview_is_read_only_and_source_complete(self):
        preview = whole_house_order_preview()
        self.assertTrue(preview["readOnly"])
        self.assertEqual(preview["businessWriteCount"], 0)
        self.assertEqual(preview["source"]["sha256"], SOURCE_SHA256)
        self.assertEqual(preview["order"]["customerOrDealer"], "温岭江公馆")
        self.assertEqual(preview["order"]["externalOrderNo"], "2023/11/12-6-正单")
        self.assertEqual(len(preview["productGroups"]), 3)
        self.assertEqual(len(preview["sourceLineIdentities"]), 37)
        self.assertEqual(len(preview["mapping"]), len(WHOLE_HOUSE_ORDER_SOURCE_MAPPING))

        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get("/api/sales/previews/whole-house-order/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["preview"]["formalApplication"]["status"], "BLOCKED")
        self.assertEqual(response.data["data"]["preview"]["formalApplication"]["businessWriteCount"], 0)
        self.assertEqual(response.data["data"]["strictFacts"]["businessWriteCount"], 0)

        before = (ExternalIdentity.objects.count(), MasterDataWriteRequest.objects.count())
        blocked = client.post(
            "/api/sales/orders/source-intake/whole-house/",
            {"confirmed": True, "previewFingerprint": "irrelevant"},
            format="json", HTTP_IDEMPOTENCY_KEY="SOURCE-BLOCKED-1",
        )
        self.assertEqual(blocked.status_code, 403)
        self.assertIn("FORMAL_IMPORT_ACTOR_", blocked.data["error"]["code"])
        self.assertEqual(before, (ExternalIdentity.objects.count(), MasterDataWriteRequest.objects.count()))


class SourceReviewDo4Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from system.models import Permission, Role, RolePermission, PositionResponsibility, UserRoleScopeAssignment
        SalesOrderToDemandTests.setUpTestData.__func__(cls)
        role = Role.objects.create(code="DO4-SOURCE", name="来源办理测试角色")
        cls.position.default_role = role
        cls.position.save(update_fields=["default_role"])
        PositionResponsibility.objects.create(position=cls.position, responsibility=cls.responsibility, active=True)
        for code in ("sales.order.view", "sales.order.update", "sales.order.confirm", "sales.order.create"):
            permission, _ = Permission.objects.get_or_create(code=code, defaults={"name":code,"module":"SALES"})
            RolePermission.objects.get_or_create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(user=cls.user, role=role, organization=cls.company,
            scope_code="ORGANIZATION", active=True, business_hash="DO4-ISOLATED")
        cls.unit = UnitOfMeasure.objects.create(company_id=cls.company.pk, code="DO4-EA", name="测试件", dimension="count")
        cls.material.material_type = "finished"
        cls.material.base_uom = cls.unit
        cls.material.save(update_fields=["material_type","base_uom"])

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def state(self):
        response = self.client.get("/api/sales/previews/whole-house-order/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["apiFacts"], response.data["data"]["strictFacts"])
        return response.data["data"]["preview"]

    def resolution(self):
        refs = self.state()["sourceLineIdentities"]
        parts = [refs[:3], refs[3:7], refs[7:15], refs[15:]]
        return {"customerId":self.customer.pk, "departmentId":self.department.pk,
            "customerEvidence":"隔离凭据 DO4：测试客户归属", "departmentEvidence":"隔离合同 DO4：营销测试部",
            "lines":[{"commercialPosition":f"ISOLATED-CONTRACT:{i}", "productIdentity":f"独立商业产品{i}",
                "configuration":f"同配置{i}", "space":f"ROOM{i}", "deliveryResponsibility":f"交付范围{i}",
                "materialId":self.material.pk, "quantityUomId":self.unit.pk, "quantity":str(i+1),
                "quantityBasis":"COMMERCIAL_DOCUMENT", "quantityEvidence":f"隔离合同原数量{i+1}件",
                "mappingEvidence":f"隔离凭据附件{i}逐行同配置、同空间；工程量只引用不加总",
                "sourceLineIds":[r["salesOrderItemNo"] for r in group]} for i, group in enumerate(parts)]}

    def action(self, action, resolution=None, binding=None, expected=200):
        payload={"binding":binding or self.state()["review"]["binding"],"evidence":"隔离测试商业凭据：仅此库有效，不代表真实确认","confirmed":True}
        if resolution is not None: payload["resolution"]=resolution
        response=self.client.post(f"/api/sales/orders/source-intake/whole-house/actions/{action}/",payload,format="json")
        self.assertEqual(response.status_code,expected,response.data)
        return response

    def qualify(self):
        self.action("save-mapping",self.resolution())
        self.action("confirm-source")
        self.action("confirm-mapping")
        return self.state()["review"]

    def create(self, key="DO4-CREATE", binding=None, expected=201):
        response=self.client.post("/api/sales/orders/source-intake/whole-house/",
            {"binding":binding or self.state()["review"]["binding"],"confirmed":True},format="json",
            HTTP_IDEMPOTENCY_KEY=key,HTTP_X_REQUEST_ID="DO4-ISOLATED")
        self.assertEqual(response.status_code,expected,response.data)
        return response

    def test_archived_row_semantics_and_decimal_precision(self):
        p=self.state()
        self.assertEqual(len(p["sourceLineIdentities"]),37)
        self.assertEqual(p["quantityPrecision"]["exactFinishTotal"],"3.951972")
        self.assertEqual(p["quantityPrecision"]["salesQuantity"],None)
        self.assertEqual(p["review"]["resolution"]["lines"],[])
        self.assertEqual(sum(Decimal(v) for v in p["quantityPrecision"]["rawFinishValues"]),Decimal("3.951972"))
        for row in p["sourceLineIdentities"]:
            self.assertEqual(row["businessQuantity"],None)
            self.assertEqual(row["rawFields"]["salesOrderItemNo"],row["salesOrderItemNo"])

    def test_real_authorized_confirmations_then_four_dynamic_sales_lines(self):
        from system.models import OrganizationOperatingAuditRecord
        import secrets
        credential = secrets.token_urlsafe(32)
        self.user.set_password(credential)
        self.user.save(update_fields=["password"])
        self.client = APIClient()
        login = self.client.post("/api/auth/login/", {"username": self.user.username, "password": credential}, format="json")
        self.assertEqual(login.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + login.json()["token"])
        self.assertFalse(self.user.is_superuser)
        self.create(expected=409)
        state=self.qualify()
        self.assertTrue(state["allowed"])
        self.assertEqual(self.state()["previewStatus"], "QUALIFIED")
        result=self.create()
        order=SalesOrder.objects.get(pk=result.data["data"]["order"]["id"])
        self.assertEqual(order.status,"draft")
        self.assertEqual(order.items.count(),4)
        self.assertEqual(sum(x.engineering_attributes.count() for x in order.items.all()),37)
        self.assertEqual(sum(x.quantity for x in order.items.all()),Decimal("10"))
        self.assertEqual(Demand.objects.count(),0)
        self.assertEqual(BusinessStateTransition.objects.filter(object_type="SalesOrder",object_id=order.pk).count(),0)
        audits=OrganizationOperatingAuditRecord.objects.filter(target_type="SalesSourceReview")
        self.assertEqual(audits.count(),3)
        self.assertTrue(all(a.after_snapshot["actorContext"]["authorizationDecision"]=="ALLOWED" for a in audits))
        self.assertEqual(self.create(expected=200).data["data"]["order"]["id"],order.pk)
        self.assertEqual(self.create(key="DO4-SECOND",expected=200).data["data"]["order"]["id"],order.pk)
        self.assertEqual(SalesOrder.objects.count(),1)

    def test_mapping_change_and_stale_preview_invalidate_confirmations(self):
        state=self.qualify()
        resolution=deepcopy(state["resolution"])
        resolution["lines"][0]["configuration"]="变更配置（隔离）"
        self.action("save-mapping",resolution)
        self.assertFalse(self.state()["review"]["allowed"])
        self.assertEqual(self.state()["review"]["effectiveConfirmations"],{})
        self.action("confirm-mapping",binding=state["binding"],expected=409)
        self.create(expected=409)

    def test_master_rule_change_invalidates_old_confirmation(self):
        self.qualify()
        self.unit.decimal_places=3
        self.unit.save(update_fields=["decimal_places"])
        self.assertFalse(self.state()["review"]["allowed"])
        self.create(expected=409)

    def test_missing_confirmation_and_evidence_are_rejected(self):
        self.action("save-mapping",self.resolution())
        self.action("confirm-source")
        self.create(expected=409)
        response=self.client.post("/api/sales/orders/source-intake/whole-house/actions/confirm-mapping/",
            {"binding":self.state()["review"]["binding"],"confirmed":True},format="json")
        self.assertEqual(response.status_code,409)

    def test_duplicate_cross_category_and_incomplete_mapping_rejected(self):
        cases=[]
        r=self.resolution();r["lines"][1]["sourceLineIds"].append(r["lines"][0]["sourceLineIds"][0]);cases.append((r,"SOURCE_REFERENCE_DUPLICATE"))
        r=self.resolution();r["lines"][0]["sourceLineIds"].append(r["lines"][2]["sourceLineIds"].pop());cases.append((r,"SOURCE_ILLEGAL_AGGREGATION"))
        r=self.resolution();r["lines"][0]["sourceLineIds"].pop();cases.append((r,"SOURCE_MAPPING_INCOMPLETE"))
        r=self.resolution();r["lines"][1]["commercialPosition"]=r["lines"][0]["commercialPosition"];cases.append((r,"SOURCE_COMMERCIAL_DUPLICATE"))
        for resolution,code in cases:
            self.action("save-mapping",resolution)
            response=self.action("confirm-mapping",expected=409)
            self.assertEqual(response.data["error"]["code"],code)

    def test_unit_mismatch_precision_and_engineering_quantity_rejected(self):
        area=UnitOfMeasure.objects.create(company_id=self.company.pk,code="DO4-M2",name="平方米",dimension="area",decimal_places=6)
        cases=[]
        r=self.resolution();r["lines"][0]["quantityUomId"]=area.pk;cases.append((r,"SOURCE_UOM_MISMATCH"))
        r=self.resolution();r["lines"][0]["quantity"]="3.951972";cases.append((r,"SOURCE_QUANTITY_PRECISION_UNRESOLVED"))
        r=self.resolution();r["lines"][0]["quantityBasis"]="SOURCE_SUM";cases.append((r,"SOURCE_QUANTITY_BASIS_INVALID"))
        for resolution,code in cases:
            self.action("save-mapping",resolution)
            response=self.action("confirm-mapping",expected=409)
            self.assertEqual(response.data["error"]["code"],code)
        self.assertEqual(self.state()["quantityPrecision"]["exactFinishTotal"],"3.951972")

    def test_exact_governed_unit_conversion_conserves_quantity(self):
        dozen=UnitOfMeasure.objects.create(company_id=self.company.pk,code="DO4-DOZEN",name="打",
            dimension="count",conversion_base=self.unit,conversion_factor=12)
        resolution=self.resolution()
        resolution["lines"][0].update(quantityUomId=dozen.pk,quantity="0.5")
        self.action("save-mapping",resolution)
        self.action("confirm-source")
        self.action("confirm-mapping")
        self.assertEqual(self.state()["review"]["checks"][0]["businessQuantity"],"6")
        self.create()

    def test_authentication_permission_and_tenant_boundaries(self):
        from system.models import UserRoleScopeAssignment
        self.assertEqual(APIClient().get("/api/sales/previews/whole-house-order/").status_code,401)
        other=Company.objects.create(code="DO4-OTHER",name="另一组织")
        customer=Customer.objects.create(company=other,code="OTHER-C",name="其他客户")
        resolution=self.resolution();resolution["customerId"]=customer.pk
        self.action("save-mapping",resolution)
        self.assertEqual(self.action("confirm-mapping",expected=409).data["error"]["code"],"CUSTOMER_INVALID")
        assignment=UserRoleScopeAssignment.objects.get(user=self.user)
        assignment.active=False;assignment.save(update_fields=["active"])
        self.user.is_superuser=True;self.user.save(update_fields=["is_superuser"])
        response=self.client.post("/api/sales/orders/source-intake/whole-house/actions/confirm-source/",
            {"binding":{},"evidence":"不应放行","confirmed":True},format="json")
        self.assertEqual(response.status_code,403)
        self.assertEqual(SalesOrder.objects.count(),0)

    def test_failure_after_order_create_rolls_back_business_identity_and_ledger(self):
        state=self.qualify()
        before=ExternalIdentity.objects.get(pk=state["identityId"]).audit_metadata
        def fail_after_order(_stage,_row):
            raise RuntimeError("injected transaction failure")
        with self.assertRaisesRegex(RuntimeError,"injected transaction"):
            commit_source_intake(user=self.user, resolver={"binding":state["binding"],"confirmed":True,"idempotencyKey":"DO4-ROLLBACK"},
                authorization={},failure_injector=fail_after_order)
        self.assertEqual(SalesOrder.objects.count(),0)
        self.assertEqual(MasterDataWriteRequest.objects.count(),0)
        identity=ExternalIdentity.objects.get(pk=state["identityId"])
        self.assertFalse(identity.target_entity_id)
        self.assertEqual(identity.audit_metadata,before)
        self.assertTrue(self.state()["review"]["allowed"])

    def test_source_version_change_invalidates_real_confirmations(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from . import source_semantics
        self.qualify()
        changed = json.loads(source_semantics.ARCHIVE.read_text(encoding="utf-8"))
        changed["schedulingRows"][0]["sourceSpecification"] = "新来源版本配置"
        with TemporaryDirectory(prefix="do4-source-version-") as directory:
            alternate = Path(directory) / "changed-archive.json"
            alternate.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
            # Only the isolated evidence file differs. Authorization and every
            # confirmation validator execute unchanged, without a success stub.
            with patch.object(source_semantics, "ARCHIVE", alternate):
                self.assertFalse(self.state()["review"]["allowed"])
                self.assertEqual(self.state()["review"]["effectiveConfirmations"], {})
                self.create(expected=409)

    def test_malformed_draft_rejected_without_audit_or_identity_write(self):
        self.action("save-mapping", {"customerId": {}, "lines": []}, expected=400)
        self.assertEqual(ExternalIdentity.objects.count(), 0)

    def test_exact_customer_cross_reference_resolves_but_ambiguity_does_not(self):
        self.customer.name = "温岭江公馆"
        self.customer.save(update_fields=["name"])
        ExternalIdentity.objects.create(organization_id=self.company.pk, source_system="07经销商.xlsx",
            source_type="USER_VALIDATED_XLSX", source_object_type="DEALER_SOURCE_ROW", external_id="6",
            target_entity_type="customers", target_entity_id=str(self.customer.pk), mapping_status="MATCH")
        self.assertEqual(self.state()["databaseResolution"]["resolvedCustomerId"], self.customer.pk)
        Customer.objects.create(company=self.company, code="DO4-DUPLICATE", name="温岭江公馆")
        self.assertIsNone(self.state()["databaseResolution"]["resolvedCustomerId"])

    def test_formal_engineering_alias_is_resolved_without_becoming_a_sales_line(self):
        ExternalIdentity.objects.create(organization_id=self.company.pk, source_system="PCE_FOUNDATION_WAVE1",
            source_type="APPROVED_XLSX", source_object_type="SEMI_FINISHED_MATERIAL_SOURCE",
            external_id="05半成品板材.xlsx|半成品板材|CODE:HYFB0101016", target_entity_type="materials",
            target_entity_id=str(self.material.pk), mapping_status="MATCH")
        preview = self.state()
        source = next(r for r in preview["sourceLineIdentities"] if r["sourceRow"] == 2)
        self.assertEqual(source["engineeringMapping"]["matches"][0]["id"], self.material.pk)
        self.assertEqual(source["savedProposedSalesLines"], [])
        self.assertEqual(preview["review"]["resolution"]["lines"], [])
