from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase

from masterdata.models import Material
from pfm.models import Employee
from sales.models import Customer, SalesOrder, SalesOrderItem
from sales.services import SalesBusinessError, create_order, perform_order_action
from system.models import (
    Company, Department, Position, PositionResponsibility,
    PositionWorkflowResponsibility, Responsibility, User,
)
from workflow_runtime.models import (
    ApprovalDecision, ApprovalTask, ProcessDefinition, WorkflowInstance,
    WorkflowNodeDefinition,
)
from workflow_runtime.state_transitions import create_business_object_with_initial_state

from .models import (
    EngineeringSourceRecord, OrderCrossFunctionalReview,
    OrderEngineeringInstance, OrderReviewSalesOrderRelation, OrderReviewScopeItem,
    PDEEngineeringPreparationAuthorization, PDEReviewPredecessorRelation,
)
from sales.views import crm_order_admission_candidates
from .crm_order_admission import (
    CRMOrderAdmissionError,
    current_crm_sales_order_admission_facts,
    require_current_crm_sales_order_admission,
)


class OrderReviewSalesOrderRelationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="P1REL", name="P1正式关系测试公司")
        cls.department = Department.objects.create(
            code="P1REL-SALES", name="销售部", company=cls.company,
        )
        cls.user = User.objects.create_superuser(
            username="p1_relation_user", password="unused", real_name="P1关系测试人",
            company_id=cls.company.pk,
        )
        cls.position = Position.objects.create(
            code="P1REL-POS", name="销售订单岗", company=cls.company,
            department=cls.department,
        )
        cls.responsibility, _ = Responsibility.objects.update_or_create(
            code="RESP_SALES_ORDER_002",
            defaults={
                "name": "销售需求与订单协调", "status": "ACTIVE", "is_active": True,
            },
        )
        PositionResponsibility.objects.create(
            position=cls.position, responsibility=cls.responsibility,
            is_primary=True, active=True,
        )
        Employee.objects.create(
            user=cls.user, employee_no="P1REL-E001", full_name="P1关系测试人",
            department_ref=cls.department, position_ref=cls.position, status="active",
        )
        sales_process, _ = ProcessDefinition.objects.update_or_create(
            definition_code="SALES_ORDER_TO_SUPPLY_PLAN",
            defaults={
                "definition_name": "销售订单创建", "business_domain": "SALES",
                "document_type": "SalesOrder", "version": 1, "active": True,
                "definition_hash": "p1-relation-sales",
            },
        )
        create_node, _ = WorkflowNodeDefinition.objects.update_or_create(
            process_definition=sales_process, node_code="CREATE",
            defaults={
                "node_name": "创建订单", "sequence": 1,
                "business_action_code": "sales.order.create", "active": True,
            },
        )
        PositionWorkflowResponsibility.objects.update_or_create(
            position=cls.position, workflow_code="SALES_ORDER_TO_SUPPLY_PLAN",
            node_code="CREATE", ownership_type="OWNER",
            defaults={
                "responsibility": cls.responsibility,
                "workflow_node": create_node,
                "active": True,
            },
        )
        cls.review_process = ProcessDefinition.objects.create(
            definition_code="CRM_ORDER_REVIEW_P1_RELATION_TEST",
            definition_name="CRM订单评审", business_domain="CRM",
            document_type="CRMOrderReview", version=1, active=True,
            definition_hash="p1-relation-review",
        )
        cls.customer = Customer.objects.create(
            company=cls.company, code="P1REL-C", name="测试客户",
        )
        cls.material = Material.objects.create(
            company_id=cls.company.pk, code="P1REL-M", name="测试产品",
            unit="件", material_type="finished", is_active=True,
        )
        cls.source = EngineeringSourceRecord.objects.create(
            company=cls.company, source_no="P1REL-SOURCE", source_name="CRM订单来源",
            source_type="controlled_import", source_version="R1",
            content_hash="1" * 64, status="confirmed", source_payload={
                "businessOrderReference": {
                    "sourceOrderNo": "CRM-P1-REL-001",
                    "customerName": "测试客户",
                    "projectName": "测试项目",
                },
                "formalSalesOrderScope": {
                    "authority": "CRM_FORMAL_ORDER_SCOPE",
                    "items": [
                        {"key": "EXT-10", "customerProductName": "测试产品", "quantity": "1", "unit": "件"},
                        {"key": "EXT-20", "customerProductName": "测试产品", "quantity": "2", "unit": "件"},
                    ],
                },
            },
        )

    def _review(self, *, version=1, conclusion="", approved=True):
        review = OrderCrossFunctionalReview.objects.create(
            company=self.company, source_record=self.source,
            review_type="CRM_ORDER_REVIEW", source_order_no="CRM-P1-REL-001",
            source_version="R1", source_content_hash=self.source.content_hash,
            review_version=version, conclusion=conclusion, reviewer=self.user,
            idempotency_key=f"p1-rel-review-{version}-{conclusion or 'blank'}",
            audit_hash=f"{version:064x}", record_status="SUBMITTED",
        )
        workflow = WorkflowInstance.objects.create(
            instance_no=f"P1REL-WF-{review.pk}", process_definition=self.review_process,
            document_type="CRMOrderReview", document_id=review.pk,
            status="approved" if approved else "rejected",
            current_step=1, total_steps=1, version=1,
        )
        task = ApprovalTask.objects.create(
            task_no=f"P1REL-TASK-{review.pk}", workflow_instance=workflow,
            step_no=1, required_role_code="CRM_REVIEWER",
            status="approved" if approved else "rejected", version=1,
        )
        ApprovalDecision.objects.create(
            task=task, decision_sequence=1, actor=self.user,
            decision="approved" if approved else "rejected",
            comment="P1关系测试", action_id=f"p1-rel-action-{review.pk}",
            idempotency_key=f"p1-rel-decision-{review.pk}",
            decision_hash=f"{review.pk + 1000:064x}",
        )
        return review

    def _payload(self, *, scope_mode="WHOLE_ORDER", selected=None, reason=""):
        payload = {
            "customerId": self.customer.pk,
            "departmentId": self.department.pk,
            "requiredDate": (date.today() + timedelta(days=10)).isoformat(),
            "orderSource": "crm",
            "externalSourceNo": "CRM-P1-REL-001",
            "deliveryInformation": {
                "sourceRecordId": self.source.pk,
                "sourceVersion": self.source.source_version,
            },
            "sourceIntakeFacts": {
                "sourceRecordId": self.source.pk,
                "sourceVersion": self.source.source_version,
                "sourceContentHash": self.source.content_hash,
            },
            "projectReference": "测试项目",
            "reviewScopeMode": scope_mode,
            "reviewScopeReason": reason,
            "items": [
                {"lineNo": 10, "externalLineNo": "EXT-10", "materialId": self.material.pk, "quantity": "1"},
                {"lineNo": 20, "externalLineNo": "EXT-20", "materialId": self.material.pk, "quantity": "2"},
            ],
        }
        if selected is not None:
            payload["reviewScopeItemLineNos"] = selected
            payload["reviewScopeSourceItemKeys"] = [f"EXT-{value}" for value in selected]
        return payload

    def _create_order(
        self,
        *,
        business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
        **payload_overrides,
    ):
        payload = self._payload()
        payload.update(payload_overrides)
        if (
            payload.get("reviewScopeMode") == "SELECTED_ITEMS"
            and not payload.get("reviewScopeSourceItemKeys")
        ):
            payload["reviewScopeSourceItemKeys"] = [
                f"EXT-{value}" for value in payload.get("reviewScopeItemLineNos") or []
            ]
        return create_order(
            user=self.user,
            payload=payload,
            authorization={"allowed": True},
            business_purpose=business_purpose,
        )

    def _direct_order(self, suffix):
        return create_business_object_with_initial_state(
            model=SalesOrder, initial_state="draft", company=self.company,
            department=self.department, customer=self.customer,
            order_no=f"P1REL-DIRECT-{suffix}", order_date=date.today(),
            required_delivery_date=date.today() + timedelta(days=10),
            business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
            created_by=self.user,
        )

    def _direct_item(self, order, line_no=1):
        return SalesOrderItem.objects.create(
            sales_order=order, line_no=line_no, material=self.material,
            quantity=1, required_date=order.required_delivery_date,
        )

    def test_gate_review_id_is_persisted_in_formal_relation(self):
        review = self._review()
        order, _, _ = self._create_order()
        relation = OrderReviewSalesOrderRelation.objects.get(sales_order=order)
        self.assertEqual(relation.review_id, review.pk)
        self.assertEqual(relation.order_version_snapshot, order.version)

    def test_reject_cannot_create_order_or_relation(self):
        self._review(conclusion="REJECT", approved=True)
        with self.assertRaises(SalesBusinessError) as caught:
            self._create_order()
        self.assertEqual(caught.exception.code, "CRM_ORDER_REVIEW_EXPLICITLY_REJECTED")
        self.assertEqual(SalesOrder.objects.count(), 0)
        self.assertEqual(OrderReviewSalesOrderRelation.objects.count(), 0)

    def test_approved_creates_runtime_gate_relation(self):
        review = self._review()
        order, _, _ = self._create_order()
        relation = OrderReviewSalesOrderRelation.objects.get(review=review)
        self.assertEqual(relation.sales_order_id, order.pk)
        self.assertEqual(relation.company_id, self.company.pk)
        self.assertEqual(relation.resolution_basis, "RUNTIME_GATE")
        self.assertEqual(relation.source_content_hash_snapshot, review.source_content_hash)

    def test_one_review_cannot_link_two_orders(self):
        review = self._review()
        self._create_order()
        other_order = self._direct_order("SECOND")
        duplicate = OrderReviewSalesOrderRelation(
            company=self.company, review=review, sales_order=other_order,
            scope_mode="WHOLE_ORDER", order_version_snapshot=other_order.version,
            source_content_hash_snapshot=review.source_content_hash,
            resolution_basis="RUNTIME_GATE", created_by=self.user,
            audit_hash="a" * 64,
        )
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_one_order_allows_multiple_review_versions(self):
        review1 = self._review(version=1)
        order, item, _ = self._create_order()
        review2 = self._review(version=2)
        relation2 = OrderReviewSalesOrderRelation.objects.create(
            company=self.company, review=review2, sales_order=order,
            scope_mode="WHOLE_ORDER", order_version_snapshot=order.version,
            source_content_hash_snapshot=review2.source_content_hash,
            resolution_basis="RUNTIME_GATE", created_by=self.user,
            audit_hash="b" * 64,
        )
        OrderReviewScopeItem.objects.create(
            relation=relation2, sales_order_item=item,
            line_no_snapshot=item.line_no,
            external_line_no_snapshot=item.external_line_no,
            item_identity_hash="c" * 64,
        )
        self.assertEqual(order.order_review_relations.count(), 2)
        self.assertEqual(
            set(order.order_review_relations.values_list("review_id", flat=True)),
            {review1.pk, review2.pk},
        )

    def test_whole_order_scope_contains_all_current_items(self):
        self._review()
        order, _, _ = self._create_order()
        relation = OrderReviewSalesOrderRelation.objects.get(sales_order=order)
        self.assertEqual(relation.scope_mode, "WHOLE_ORDER")
        self.assertEqual(
            set(relation.scope_items.values_list("sales_order_item_id", flat=True)),
            set(order.items.values_list("id", flat=True)),
        )

    def test_selected_items_scope_contains_only_explicit_lines(self):
        self._review()
        order, _, _ = self._create_order(
            reviewScopeMode="SELECTED_ITEMS",
            reviewScopeItemLineNos=[20],
            reviewScopeReason="仅第二产品行进入本次评审范围",
        )
        relation = OrderReviewSalesOrderRelation.objects.get(sales_order=order)
        self.assertEqual(relation.scope_mode, "SELECTED_ITEMS")
        self.assertEqual(
            list(relation.scope_items.values_list("line_no_snapshot", flat=True)), [20],
        )

    def test_scope_item_from_another_order_is_blocked(self):
        self._review()
        order, _, _ = self._create_order()
        relation = OrderReviewSalesOrderRelation.objects.get(sales_order=order)
        other_order = self._direct_order("FOREIGN")
        foreign_item = self._direct_item(other_order)
        invalid = OrderReviewScopeItem(
            relation=relation, sales_order_item=foreign_item,
            line_no_snapshot=foreign_item.line_no,
            external_line_no_snapshot=foreign_item.external_line_no,
            item_identity_hash="d" * 64,
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_relation_company_must_match_review_and_order(self):
        review = self._review()
        order, _, _ = self._create_order()
        other_company = Company.objects.create(code="P1REL-OTHER", name="其它公司")
        invalid = OrderReviewSalesOrderRelation(
            company=other_company, review=review, sales_order=order,
            scope_mode="WHOLE_ORDER", order_version_snapshot=order.version,
            source_content_hash_snapshot=review.source_content_hash,
            resolution_basis="RUNTIME_GATE", created_by=self.user,
            audit_hash="f" * 64,
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_duplicate_scope_relation_is_blocked(self):
        self._review()
        order, item, _ = self._create_order()
        relation = OrderReviewSalesOrderRelation.objects.get(sales_order=order)
        duplicate = OrderReviewScopeItem(
            relation=relation, sales_order_item=item,
            line_no_snapshot=item.line_no,
            external_line_no_snapshot=item.external_line_no,
            item_identity_hash="e" * 64,
        )
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_failed_new_flow_does_not_change_historical_order(self):
        historical = self._direct_order("HISTORY")
        before = {
            "order_no": historical.order_no,
            "version": historical.version,
            "status": historical.status,
            "updated_at": historical.updated_at,
        }
        self._review(conclusion="REJECT", approved=True)
        with self.assertRaises(SalesBusinessError):
            self._create_order()
        historical.refresh_from_db()
        self.assertEqual(
            {
                "order_no": historical.order_no,
                "version": historical.version,
                "status": historical.status,
                "updated_at": historical.updated_at,
            },
            before,
        )
        self.assertEqual(OrderReviewSalesOrderRelation.objects.count(), 0)

    def test_online_unresolved_scope_is_blocked_atomically(self):
        self._review()
        with self.assertRaises(SalesBusinessError) as caught:
            self._create_order(reviewScopeMode="UNRESOLVED")
        self.assertEqual(caught.exception.code, "ORDER_REVIEW_SCOPE_MODE_REQUIRED")
        self.assertEqual(SalesOrder.objects.count(), 0)
        self.assertEqual(OrderReviewSalesOrderRelation.objects.count(), 0)

    def test_same_customer_project_with_different_formal_number_is_allowed(self):
        review = self._review()
        order, _, _ = self._create_order()
        self.assertNotEqual(order.order_no, review.source_order_no)
        self.assertEqual(order.customer.name, "测试客户")
        self.assertEqual(order.project_reference, "测试项目")
        self.assertTrue(OrderReviewSalesOrderRelation.objects.filter(
            review=review, sales_order=order,
        ).exists())

    def test_customer_identity_conflict_is_blocked_atomically(self):
        self._review()
        other = Customer.objects.create(
            company=self.company, code="P1REL-C-OTHER", name="其它客户",
        )
        before = self._protected_counts()
        with self.assertRaises(SalesBusinessError) as caught:
            self._create_order(customerId=other.pk)
        self.assertEqual(caught.exception.code, "CRM_SALES_ORDER_BUSINESS_IDENTITY_CONFLICT")
        self.assertEqual(self._protected_counts(), before)

    def test_project_or_contract_identity_conflict_is_blocked(self):
        self._review()
        with self.assertRaises(SalesBusinessError) as caught:
            self._create_order(projectReference="其它项目")
        self.assertEqual(caught.exception.code, "CRM_SALES_ORDER_BUSINESS_IDENTITY_CONFLICT")
        self.assertEqual(OrderReviewSalesOrderRelation.objects.count(), 0)

    def test_source_version_mismatch_is_blocked(self):
        self._review()
        with self.assertRaises(SalesBusinessError) as caught:
            self._create_order(sourceIntakeFacts={
                "sourceRecordId": self.source.pk,
                "sourceVersion": "R-STALE",
                "sourceContentHash": self.source.content_hash,
            })
        self.assertEqual(caught.exception.code, "CRM_ORDER_SOURCE_CONTEXT_AMBIGUOUS")
        self.assertEqual(OrderReviewSalesOrderRelation.objects.count(), 0)

    def test_source_hash_mismatch_is_blocked(self):
        self._review()
        with self.assertRaises(SalesBusinessError) as caught:
            self._create_order(sourceIntakeFacts={
                "sourceRecordId": self.source.pk,
                "sourceVersion": self.source.source_version,
                "sourceContentHash": "9" * 64,
            })
        self.assertEqual(caught.exception.code, "CRM_ORDER_SOURCE_HASH_MISMATCH")
        self.assertEqual(OrderReviewSalesOrderRelation.objects.count(), 0)

    def test_review_scope_business_objects_must_match_source_scope(self):
        self._review()
        payload = dict(self.source.source_payload)
        payload["formalSalesOrderScope"] = {
            "authority": "CRM_FORMAL_ORDER_SCOPE",
            "items": [
                {"key": "ONLY", "customerProductName": "测试产品", "quantity": "99", "unit": "件"},
            ],
        }
        self.source.source_payload = payload
        self.source.save(update_fields=["source_payload"])
        with self.assertRaises(SalesBusinessError) as caught:
            self._create_order()
        self.assertEqual(caught.exception.code, "CRM_SALES_ORDER_BUSINESS_IDENTITY_CONFLICT")
        self.assertEqual(OrderReviewSalesOrderRelation.objects.count(), 0)

    def test_multiple_customer_candidates_fail_closed(self):
        self._review()
        Customer.objects.create(
            company=self.company, code="P1REL-C-DUP", name=" 测试 客户 ",
        )
        self.assertEqual(crm_order_admission_candidates(self.company.pk), [])

    def test_multiple_formal_order_candidates_fail_closed(self):
        self._review()
        for suffix in ("A", "B"):
            candidate = self._direct_order(f"CANDIDATE-{suffix}")
            candidate.external_source_no = "CRM-P1-REL-001"
            candidate.project_reference = "测试项目"
            candidate.save(update_fields=["external_source_no", "project_reference", "updated_at"])
        before = self._protected_counts()
        with self.assertRaises(SalesBusinessError) as caught:
            self._create_order()
        self.assertEqual(caught.exception.code, "CRM_SALES_ORDER_CANDIDATE_NOT_UNIQUE")
        self.assertEqual(self._protected_counts(), before)

    def test_stale_external_source_no_cannot_admit_current_order(self):
        order = self._direct_order("STALE-NO")
        order.order_source = "crm"
        order.external_source_no = "CRM-P1-REL-001"
        order.save(update_fields=["order_source", "external_source_no", "updated_at"])
        with self.assertRaises(CRMOrderAdmissionError) as caught:
            require_current_crm_sales_order_admission(order=order)
        self.assertEqual(caught.exception.code, "CRM_ORDER_CURRENT_SOURCE_REQUIRED")

    def test_stale_delivery_source_record_cannot_admit_current_order(self):
        order = self._direct_order("STALE-DELIVERY")
        order.order_source = "crm"
        order.delivery_information = {
            "sourceRecordId": self.source.pk,
            "sourceVersion": self.source.source_version,
        }
        order.save(update_fields=["order_source", "delivery_information", "updated_at"])
        with self.assertRaises(CRMOrderAdmissionError) as caught:
            require_current_crm_sales_order_admission(order=order)
        self.assertEqual(caught.exception.code, "CRM_ORDER_CURRENT_SOURCE_REQUIRED")

    def test_historical_review_cannot_admit_current_order(self):
        self._review(version=1)
        order, _, _ = self._create_order()
        self._review(version=2)
        with self.assertRaises(CRMOrderAdmissionError) as caught:
            require_current_crm_sales_order_admission(order=order)
        self.assertEqual(
            caught.exception.code,
            "CRM_ORDER_HISTORICAL_REVIEW_NOT_CURRENT",
        )

    def test_no_current_relation_projects_admitted_false(self):
        order = self._direct_order("NO-CURRENT-SOURCE")
        facts = current_crm_sales_order_admission_facts(order)
        self.assertFalse(facts["admitted"])
        self.assertFalse(facts["submitAllowed"])
        self.assertIsNone(facts["currentSource"])

    def test_existing_relation_identity_conflict_fails_closed(self):
        self._review()
        order, _, _ = self._create_order()
        SalesOrder.objects.filter(pk=order.pk).update(
            project_reference="其它项目",
        )
        order.refresh_from_db()
        with self.assertRaises(CRMOrderAdmissionError) as caught:
            require_current_crm_sales_order_admission(order=order)
        self.assertEqual(
            caught.exception.code,
            "CRM_SALES_ORDER_BUSINESS_IDENTITY_CONFLICT",
        )

    def test_missing_relation_scope_fails_closed(self):
        self._review()
        order, _, _ = self._create_order()
        OrderReviewScopeItem.objects.filter(
            relation__sales_order=order,
        ).delete()
        with self.assertRaises(CRMOrderAdmissionError) as caught:
            require_current_crm_sales_order_admission(order=order)
        self.assertEqual(caught.exception.code, "CRM_ORDER_CURRENT_SCOPE_MISMATCH")

    def test_multiple_current_relations_fail_closed(self):
        self._review(version=1)
        order, _, _ = self._create_order()
        review2 = self._review(version=2)
        OrderReviewSalesOrderRelation.objects.create(
            company=self.company,
            review=review2,
            sales_order=order,
            scope_mode="WHOLE_ORDER",
            order_version_snapshot=order.version,
            source_content_hash_snapshot=review2.source_content_hash,
            resolution_basis="RUNTIME_GATE",
            created_by=self.user,
            audit_hash="8" * 64,
        )
        with self.assertRaises(CRMOrderAdmissionError) as caught:
            require_current_crm_sales_order_admission(order=order)
        self.assertEqual(
            caught.exception.code,
            "CRM_ORDER_CURRENT_RELATION_AMBIGUOUS",
        )

    def test_development_only_order_fails_closed(self):
        self._review()
        order, _, _ = self._create_order(
            business_purpose=SalesOrder.BusinessPurpose.DEVELOPMENT_VALIDATION,
        )
        SalesOrder.objects.filter(pk=order.pk).update(
            acceptance_marker="DEVELOPMENT_ONLY",
        )
        order.refresh_from_db()
        with self.assertRaises(CRMOrderAdmissionError) as caught:
            require_current_crm_sales_order_admission(order=order)
        self.assertEqual(
            caught.exception.code,
            "CRM_ORDER_FORMAL_REVIEW_NOT_APPLICABLE",
        )

    def test_valid_current_relation_admits_exact_order_and_scope(self):
        self._review()
        order, _, _ = self._create_order()
        result = require_current_crm_sales_order_admission(order=order)
        self.assertEqual(result.relation_id, order.order_review_relations.get().pk)
        self.assertEqual(result.admission.source_record_id, self.source.pk)
        self.assertTrue(result.identity["allowed"])

    def test_superseded_source_version_fails_closed(self):
        self._review()
        order, _, _ = self._create_order()
        EngineeringSourceRecord.objects.filter(pk=self.source.pk).update(
            status="superseded",
        )
        self.source.refresh_from_db()
        with self.assertRaises(CRMOrderAdmissionError) as caught:
            require_current_crm_sales_order_admission(order=order)
        self.assertEqual(caught.exception.code, "CRM_ORDER_SOURCE_NOT_CURRENT")

    def test_sales_order_submit_action_fails_closed_without_current_relation(self):
        process = ProcessDefinition.objects.get(
            definition_code="SALES_ORDER_TO_SUPPLY_PLAN",
        )
        submit_node = WorkflowNodeDefinition.objects.create(
            process_definition=process,
            node_code="SUBMIT",
            node_name="提交审核",
            sequence=2,
            business_action_code="sales.order.submit",
            active=True,
        )
        PositionWorkflowResponsibility.objects.create(
            position=self.position,
            responsibility=self.responsibility,
            workflow_node=submit_node,
            workflow_code="SALES_ORDER_TO_SUPPLY_PLAN",
            node_code="SUBMIT",
            ownership_type="OWNER",
            active=True,
        )
        order = self._direct_order("SUBMIT-BLOCKED")
        order.order_source = "crm"
        order.external_source_no = "CRM-P1-REL-001"
        order.delivery_information = {
            "sourceRecordId": self.source.pk,
            "sourceVersion": self.source.source_version,
        }
        order.save(update_fields=[
            "order_source", "external_source_no", "delivery_information",
            "updated_at",
        ])
        self._direct_item(order)
        with self.assertRaises(SalesBusinessError) as caught:
            perform_order_action(
                user=self.user,
                order_id=order.pk,
                action="submit",
                payload={
                    "idempotencyKey": "blocked-submit",
                    "requestId": "blocked-submit-request",
                },
                authorization={"allowed": True},
            )
        self.assertEqual(caught.exception.code, "CRM_ORDER_CURRENT_SOURCE_REQUIRED")
        order.refresh_from_db()
        self.assertEqual(order.status, "draft")

    def _protected_counts(self):
        return {
            "orders": SalesOrder.objects.count(),
            "relations": OrderReviewSalesOrderRelation.objects.count(),
            "reviews": OrderCrossFunctionalReview.objects.count(),
            "predecessors": PDEReviewPredecessorRelation.objects.count(),
            "authorizations": PDEEngineeringPreparationAuthorization.objects.count(),
            "oei": OrderEngineeringInstance.objects.count(),
        }

