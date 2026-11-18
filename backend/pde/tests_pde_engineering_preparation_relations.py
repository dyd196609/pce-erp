from datetime import date, timedelta
from hashlib import sha256
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase
from rest_framework.test import APIClient

from masterdata.models import CodeRule, Material
from pfm.models import Employee
from sales.models import Customer, SalesOrder, SalesOrderItem
from sales.crm_source_context_correction import (
    ACTION_CODE as CRM_SOURCE_CORRECTION_ACTION,
    correct_sales_order_crm_source_context,
)
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Position,
    PositionResponsibility, Responsibility, User,
)
from workflow_runtime.models import (
    ApprovalDecision,
    ApprovalTask,
    BusinessStateTransition,
    ProcessDefinition,
    WorkflowInstance,
)
from workflow_runtime.state_transitions import (
    BusinessStateTransitionError,
    create_business_object_with_initial_state,
    transition_business_object,
)

from .models import (
    EngineeringSourceRecord,
    OrderCrossFunctionalReview,
    OrderReviewSalesOrderRelation,
    OrderReviewScopeItem,
    PDEAdmissionChainRevocation,
    PDEEngineeringPreparationAuthorization,
    PDEReviewPredecessorRelation,
    ManufacturingProcessType,
    OrderEngineeringInstance,
    ProductDesignItem,
    ProductCategory,
)
from .admission_chain_revocation import (
    PDEAdmissionChainRevocationError,
    revoke_pde_admission_chain,
)
from .crm_order_admission import (
    CRMOrderAdmissionError,
    current_crm_sales_order_admission_facts,
    require_current_crm_sales_order_admission,
)
from .order_engineering_intake_service import (
    OrderEngineeringIntakeError,
    OrderEngineeringIntakeService,
)
from .pde_engineering_preparation_admission import (
    PDEEngineeringPreparationAdmissionError,
    create_pde_engineering_preparation_authorization,
    create_pde_review_predecessor_relation,
    require_pde_engineering_preparation_admission,
)
from .order_review_approval import decide_final_approval
from .order_review_service import (
    ReviewBusinessError,
    _formal_sales_order_projection,
    build_review_facts,
)
from .order_demand_preparation_service import (
    PDE_PREDECESSOR_PENDING_MESSAGE,
    OrderDemandPreparationError,
    _target_facts,
    preparation_context_facts,
    preparation_facts,
)
from .production_foundation_service import (
    ProductionFoundationError,
    ProductionFoundationService,
)


class PDEEngineeringPreparationRelationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="PDE0033", name="0033测试公司")
        cls.department = Department.objects.create(
            company=cls.company, code="PDE0033-D", name="销售部",
        )
        cls.user = User.objects.create_superuser(
            username="pde0033", password="unused", real_name="0033测试人",
            company_id=cls.company.pk,
        )
        cls.position = Position.objects.create(
            company=cls.company, department=cls.department,
            code="PDE0033-P", name="工程准备岗",
        )
        Employee.objects.create(
            user=cls.user, employee_no="PDE0033-E", full_name="0033测试人",
            status="active", department_ref=cls.department,
            position_ref=cls.position,
        )
        cls.responsibility = Responsibility.objects.create(
            code="PDE0033-RESP", name="0033工程准备职责",
            status="ACTIVE", is_active=True,
        )
        PositionResponsibility.objects.create(
            position=cls.position, responsibility=cls.responsibility,
            is_primary=True, active=True,
        )
        cls.customer = Customer.objects.create(
            company=cls.company, code="PDE0033-C", name="测试客户",
        )
        cls.material = Material.objects.create(
            company_id=cls.company.pk, code="PDE0033-M", name="测试产品",
            unit="件", material_type="finished", is_active=True,
        )
        cls.source = EngineeringSourceRecord.objects.create(
            company=cls.company, source_no="PDE0033-S", source_name="受控来源",
            source_type="controlled_import", source_version="R1",
            content_hash="1" * 64, status="confirmed", source_payload={
                "businessOrderReference": {
                    "sourceOrderNo": "CRM-PDE0033",
                    "customerName": "测试客户",
                    "projectName": "测试项目",
                },
                "formalSalesOrderScope": {
                    "authority": "CRM_FORMAL_ORDER_SCOPE",
                    "items": [
                        {"key": "EXT-10", "customerProductName": "测试产品", "quantity": "1", "unit": "件"},
                    ],
                },
            },
        )
        cls.category = ProductCategory.objects.create(
            company=cls.company, code="PDE0033-CAT", name="测试分类",
        )
        cls.process_type = ManufacturingProcessType.objects.create(
            company=cls.company, code="PDE0033-PROC", name="测试工艺",
        )
        cls.process = ProcessDefinition.objects.create(
            definition_code="PDE0033-PROCESS", definition_name="0033测试审批",
            business_domain="PDE", document_type="PDEProductionFeasibilityReview",
            version=1, active=True, definition_hash="0033-process",
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.crm_review = self._review("CRM_ORDER_REVIEW", 1)
        self._approval(self.crm_review, "CRMOrderReview", "approved")
        self.order = create_business_object_with_initial_state(
            model=SalesOrder, initial_state="draft",
            company=self.company, department=self.department, customer=self.customer,
            order_no=f"PDE0033-O-{self._testMethodName}", order_date=date.today(),
            required_delivery_date=date.today() + timedelta(days=10),
            order_source="crm", external_source_no="CRM-PDE0033",
            business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
            project_reference="测试项目",
            created_by=self.user,
        )
        self.item = SalesOrderItem.objects.create(
            sales_order=self.order, line_no=10, external_line_no="EXT-10",
            material=self.material, quantity=1,
            required_date=self.order.required_delivery_date,
        )
        self.crm_relation = OrderReviewSalesOrderRelation.objects.create(
            company=self.company, review=self.crm_review, sales_order=self.order,
            scope_mode="WHOLE_ORDER", order_version_snapshot=self.order.version,
            source_content_hash_snapshot=self.source.content_hash,
            resolution_basis="RUNTIME_GATE", created_by=self.user,
            audit_hash=self._hash("crm-relation"),
        )
        OrderReviewScopeItem.objects.create(
            relation=self.crm_relation, sales_order_item=self.item,
            line_no_snapshot=self.item.line_no,
            external_line_no_snapshot=self.item.external_line_no,
            item_identity_hash=self._hash("scope-item"),
        )

    def _runtime_counts(self):
        return {
            "salesOrders": SalesOrder.objects.count(),
            "salesOrderItems": SalesOrderItem.objects.count(),
            "crmReviews": OrderCrossFunctionalReview.objects.filter(
                review_type="CRM_ORDER_REVIEW",
            ).count(),
            "crmRelations": OrderReviewSalesOrderRelation.objects.count(),
            "pdeReviews": OrderCrossFunctionalReview.objects.filter(
                review_type="PDE_PRODUCTION_FEASIBILITY",
            ).count(),
            "pdePredecessors": PDEReviewPredecessorRelation.objects.count(),
            "authorizations": PDEEngineeringPreparationAuthorization.objects.count(),
            "oei": OrderEngineeringInstance.objects.count(),
        }

    def test_runtime_closure_endpoints_project_formal_0032_context_without_writes(self):
        before = self._runtime_counts()

        requirements = self.client.get("/api/pde/product-requirements/")
        self.assertEqual(requirements.status_code, 200)
        self.assertEqual(requirements.data["factLoadStatus"], "loaded")
        self.assertEqual(requirements.data["rows"][0]["salesOrderItemId"], self.item.pk)
        self.assertEqual(requirements.data["rows"][0]["orderNo"], self.order.order_no)
        self.assertEqual(requirements.data["contextFacts"]["crmOrderRelationId"], self.crm_relation.pk)
        self.assertEqual(requirements.data["contextFacts"]["crmReviewId"], self.crm_review.pk)
        self.assertEqual(requirements.data["contextFacts"]["sourceVersion"], self.source.source_version)
        self.assertTrue(requirements.data["contextFacts"]["sourceContentHashVerified"])
        self.assertEqual(requirements.data["strictFacts"]["businessWriteCount"], 0)

        readiness = self.client.get("/api/pde/engineering-readiness/")
        self.assertEqual(readiness.status_code, 200)
        self.assertEqual(readiness.data["rows"][0]["orderNo"], self.order.order_no)
        self.assertEqual(readiness.data["strictFacts"]["crmOrderRelationId"], self.crm_relation.pk)
        self.assertEqual(readiness.data["strictFacts"]["salesOrderItemIds"], [self.item.pk])
        self.assertEqual(readiness.data["strictFacts"]["crmReviewId"], self.crm_review.pk)
        self.assertEqual(readiness.data["strictFacts"]["statusCode"], "PDE_REVIEW_PREDECESSOR_PENDING")
        self.assertEqual(readiness.data["strictFacts"]["businessWriteCount"], 0)
        self.assertFalse(readiness.data["strictFacts"]["pdeReviewCreated"])
        self.assertFalse(readiness.data["strictFacts"]["oeiCreated"])
        self.assertFalse(readiness.data["strictFacts"]["authorizationCreated"])

        self.assertEqual(before, self._runtime_counts())

    def test_runtime_closure_endpoints_require_authentication(self):
        anonymous = APIClient()
        self.assertIn(
            anonymous.get("/api/pde/product-requirements/").status_code,
            {401, 403},
        )
        self.assertIn(
            anonymous.get("/api/pde/engineering-readiness/").status_code,
            {401, 403},
        )

    def test_formal_pde_review_context_reads_0032_sales_order_scope_and_crm_review(self):
        before = self._runtime_counts()

        facts = build_review_facts(
            user=self.user,
            review_type="PDE_PRODUCTION_FEASIBILITY",
            crm_order_relation_id=self.crm_relation.pk,
            sales_order_id=self.order.pk,
            formal_context_required=True,
        )

        self.assertEqual(facts["source"]["id"], self.source.pk)
        self.assertEqual(facts["orderContext"]["sourceOrderNo"], self.crm_review.source_order_no)
        self.assertEqual(facts["orderContext"]["formalSalesOrderNo"], self.order.order_no)
        self.assertEqual(facts["orderContext"]["salesOrderId"], self.order.pk)
        self.assertEqual(facts["orderContext"]["salesOrderItemIds"], [self.item.pk])
        self.assertEqual(facts["orderContext"]["crmOrderRelationId"], self.crm_relation.pk)
        self.assertEqual(facts["orderContext"]["crmReviewId"], self.crm_review.pk)
        self.assertEqual(facts["crossReviewFeedback"]["id"], self.crm_review.pk)
        self.assertTrue(facts["orderContext"]["formalContextResolved"])

        response = self.client.get(
            "/api/pde/production-feasibility-reviews/",
            {
                "crmOrderRelationId": self.crm_relation.pk,
                "salesOrderId": self.order.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        api_facts = response.data["data"]
        self.assertEqual(api_facts["orderContext"]["sourceOrderNo"], self.crm_review.source_order_no)
        self.assertEqual(api_facts["orderContext"]["formalSalesOrderNo"], self.order.order_no)
        self.assertEqual(api_facts["orderContext"]["salesOrderItemIds"], [self.item.pk])
        self.assertEqual(api_facts["orderContext"]["crmOrderRelationId"], self.crm_relation.pk)
        self.assertEqual(api_facts["orderContext"]["crmReviewId"], self.crm_review.pk)
        self.assertTrue(api_facts["orderContext"]["formalContextResolved"])
        self.assertEqual(before, self._runtime_counts())

    def test_formal_pde_review_context_fails_closed_when_0032_is_not_unique(self):
        crm_review2 = self._review(
            "CRM_ORDER_REVIEW", 2, source_order_no="CRM-PDE0033-ALT",
        )
        self._approval(crm_review2, "CRMOrderReview", "approved")
        second_order = create_business_object_with_initial_state(
            model=SalesOrder, initial_state="draft",
            company=self.company, department=self.department, customer=self.customer,
            order_no=f"PDE0033-O2-{self._testMethodName}", order_date=date.today(),
            required_delivery_date=date.today() + timedelta(days=10),
            order_source="crm", external_source_no="CRM-PDE0033-2",
            business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
            created_by=self.user,
        )
        second_item = SalesOrderItem.objects.create(
            sales_order=second_order, line_no=20, external_line_no="EXT-20",
            material=self.material, quantity=1,
            required_date=second_order.required_delivery_date,
        )
        second_relation = OrderReviewSalesOrderRelation.objects.create(
            company=self.company, review=crm_review2, sales_order=second_order,
            scope_mode="WHOLE_ORDER", order_version_snapshot=second_order.version,
            source_content_hash_snapshot=self.source.content_hash,
            resolution_basis="RUNTIME_GATE", created_by=self.user,
            audit_hash=self._hash("crm-relation-2"),
        )
        OrderReviewScopeItem.objects.create(
            relation=second_relation, sales_order_item=second_item,
            line_no_snapshot=second_item.line_no,
            external_line_no_snapshot=second_item.external_line_no,
            item_identity_hash=self._hash("scope-item-2"),
        )

        with self.assertRaises(ReviewBusinessError) as caught:
            build_review_facts(
                user=self.user,
                review_type="PDE_PRODUCTION_FEASIBILITY",
                formal_context_required=True,
            )
        self.assertEqual(caught.exception.code, "CRM_ORDER_FORMAL_RELATION_NOT_UNIQUE")

        selected = build_review_facts(
            user=self.user,
            review_type="PDE_PRODUCTION_FEASIBILITY",
            crm_order_relation_id=self.crm_relation.pk,
            formal_context_required=True,
        )
        self.assertEqual(selected["orderContext"]["salesOrderId"], self.order.pk)

    def test_predecessor_accepts_formal_sales_order_identity_with_exact_0032_selector(self):
        pde_review = OrderCrossFunctionalReview.objects.create(
            company=self.company,
            source_record=self.source,
            review_type="PDE_PRODUCTION_FEASIBILITY",
            source_order_no=self.order.order_no,
            source_version=self.source.source_version,
            source_content_hash=self.source.content_hash,
            review_version=1,
            reviewer=self.user,
            idempotency_key=f"formal-context-{self._testMethodName}",
            audit_hash=self._hash("formal-context-review"),
            record_status="DRAFT",
        )

        predecessor = create_pde_review_predecessor_relation(
            pde_review=pde_review,
            user=self.user,
            crm_order_relation_id=self.crm_relation.pk,
        )

        self.assertEqual(predecessor.crm_order_relation_id, self.crm_relation.pk)
        self.assertEqual(predecessor.pde_review_id, pde_review.pk)

    def _hash(self, suffix):
        value = f"{self._testMethodName}:{suffix}"
        return sha256(value.encode()).hexdigest()

    def _review(
        self, review_type, version, *, conclusion="", status="SUBMITTED",
        source_order_no="CRM-PDE0033",
    ):
        return OrderCrossFunctionalReview.objects.create(
            company=self.company, source_record=self.source, review_type=review_type,
            source_order_no=source_order_no, source_version=self.source.source_version,
            source_content_hash=self.source.content_hash, review_version=version,
            conclusion=conclusion, reviewer=self.user,
            idempotency_key=f"{self._testMethodName}-{review_type}-{version}",
            audit_hash=self._hash(f"review-{review_type}-{version}"),
            record_status=status,
        )

    def _approval(self, review, document_type, status):
        workflow = WorkflowInstance.objects.create(
            instance_no=f"PDE0033-WF-{self._testMethodName}-{review.pk}",
            process_definition=self.process, document_type=document_type,
            document_id=review.pk, status=status, current_step=1,
            total_steps=1, version=1,
        )
        task = ApprovalTask.objects.create(
            task_no=f"PDE0033-TASK-{self._testMethodName}-{review.pk}",
            workflow_instance=workflow, step_no=1, required_role_code="TEST",
            status=status, version=1,
        )
        decision = ApprovalDecision.objects.create(
            task=task, decision_sequence=1, actor=self.user, decision=status,
            comment="0033 test", action_id=f"act-{self._testMethodName}-{review.pk}",
            idempotency_key=f"idem-{self._testMethodName}-{review.pk}",
            decision_hash=self._hash(f"decision-{review.pk}"),
        )
        return workflow, decision

    def _authorized_chain(self, *, pde_conclusion=""):
        pde_review = self._review(
            "PDE_PRODUCTION_FEASIBILITY", 1, conclusion=pde_conclusion,
        )
        predecessor = create_pde_review_predecessor_relation(
            pde_review=pde_review, user=self.user,
        )
        workflow, decision = self._approval(
            pde_review, "PDEProductionFeasibilityReview", "approved",
        )
        authorization = create_pde_engineering_preparation_authorization(
            pde_review=pde_review, workflow_instance=workflow,
            approval_decision=decision, user=self.user,
        )
        return pde_review, predecessor, authorization

    def test_dynamic_intake_reads_0032_and_stops_before_new_pde_relation(self):
        before = {
            "salesOrders": SalesOrder.objects.count(),
            "salesOrderItems": SalesOrderItem.objects.count(),
            "crmRelations": OrderReviewSalesOrderRelation.objects.count(),
            "pdeReviews": OrderCrossFunctionalReview.objects.filter(
                review_type="PDE_PRODUCTION_FEASIBILITY",
            ).count(),
            "pdePredecessors": PDEReviewPredecessorRelation.objects.count(),
            "authorizations": PDEEngineeringPreparationAuthorization.objects.count(),
            "oei": OrderEngineeringInstance.objects.count(),
        }

        context = preparation_context_facts(
            self.company.pk, sales_order_id=self.order.pk,
        )
        self.assertEqual(context["crmOrderRelationId"], self.crm_relation.pk)
        self.assertEqual(context["salesOrderId"], self.order.pk)
        self.assertEqual(context["salesOrderNo"], self.order.order_no)
        self.assertEqual(context["crmReviewId"], self.crm_review.pk)
        self.assertEqual(context["sourceRecordId"], self.source.pk)
        self.assertEqual(context["sourceVersion"], self.source.source_version)
        self.assertEqual(context["sourceContentHash"], self.source.content_hash)
        self.assertTrue(context["sourceContentHashVerified"])
        self.assertEqual(context["scopeMode"], "WHOLE_ORDER")
        self.assertEqual(context["scopeItemIds"], [self.item.pk])
        self.assertEqual(context["scopeItemCount"], 1)
        self.assertEqual(context["statusCode"], "PDE_REVIEW_PREDECESSOR_PENDING")
        self.assertEqual(context["statusMessage"], PDE_PREDECESSOR_PENDING_MESSAGE)
        self.assertFalse(context["canPrepare"])
        self.assertIsNone(context["pdePredecessorRelationId"])

        facts = preparation_facts(
            self.company.pk, crm_order_relation_id=self.crm_relation.pk,
        )
        self.assertEqual(facts["order"].pk, self.order.pk)
        self.assertEqual([row["id"] for row in facts["rows"]], [self.item.pk])
        self.assertIsNone(facts["review"])
        self.assertEqual(facts["statusMessage"], PDE_PREDECESSOR_PENDING_MESSAGE)
        self.assertEqual(facts["rows"][0]["nextActionLabel"], PDE_PREDECESSOR_PENDING_MESSAGE)

        with self.assertRaises(OrderDemandPreparationError) as caught:
            _target_facts(
                self.company.pk, crm_order_relation_id=self.crm_relation.pk,
            )
        self.assertEqual(caught.exception.code, "PDE_REVIEW_PREDECESSOR_REQUIRED")
        self.assertEqual(caught.exception.message, PDE_PREDECESSOR_PENDING_MESSAGE)
        self.assertEqual(before, {
            "salesOrders": SalesOrder.objects.count(),
            "salesOrderItems": SalesOrderItem.objects.count(),
            "crmRelations": OrderReviewSalesOrderRelation.objects.count(),
            "pdeReviews": OrderCrossFunctionalReview.objects.filter(
                review_type="PDE_PRODUCTION_FEASIBILITY",
            ).count(),
            "pdePredecessors": PDEReviewPredecessorRelation.objects.count(),
            "authorizations": PDEEngineeringPreparationAuthorization.objects.count(),
            "oei": OrderEngineeringInstance.objects.count(),
        })

    def test_dynamic_intake_uses_selected_0032_scope_not_order_shape(self):
        second_item = SalesOrderItem.objects.create(
            sales_order=self.order, line_no=20, external_line_no="EXT-20",
            material=self.material, quantity=2,
            required_date=self.order.required_delivery_date,
        )
        OrderReviewSalesOrderRelation.objects.filter(pk=self.crm_relation.pk).update(
            scope_mode="SELECTED_ITEMS", scope_reason="仅评审首行",
        )
        context = preparation_context_facts(
            self.company.pk, crm_order_relation_id=self.crm_relation.pk,
        )
        self.assertEqual(context["scopeMode"], "SELECTED_ITEMS")
        self.assertEqual(context["scopeItemIds"], [self.item.pk])
        self.assertNotIn(second_item.pk, context["scopeItemIds"])
        self.assertEqual(context["scopeItemCount"], 1)

    def test_exact_crm_relation_is_frozen_as_pde_predecessor(self):
        pde_review = self._review("PDE_PRODUCTION_FEASIBILITY", 1, status="DRAFT")
        predecessor = create_pde_review_predecessor_relation(
            pde_review=pde_review, user=self.user,
        )
        self.assertEqual(predecessor.crm_order_relation_id, self.crm_relation.pk)
        self.assertEqual(predecessor.crm_review_version_snapshot, self.crm_review.review_version)
        self.assertEqual(len(predecessor.scope_identity_hash_snapshot), 64)

    def test_missing_0032_relation_fails_closed(self):
        OrderReviewScopeItem.objects.filter(relation=self.crm_relation).delete()
        pde_review = self._review("PDE_PRODUCTION_FEASIBILITY", 1, status="DRAFT")
        with self.assertRaises(PDEEngineeringPreparationAdmissionError) as caught:
            create_pde_review_predecessor_relation(pde_review=pde_review, user=self.user)
        self.assertEqual(caught.exception.code, "CRM_ORDER_REVIEW_SCOPE_EMPTY")

    def test_final_approval_creates_immutable_authorization(self):
        _, predecessor, authorization = self._authorized_chain()
        self.assertEqual(authorization.predecessor_relation_id, predecessor.pk)
        self.assertEqual(authorization.authorization_basis, "FINAL_APPROVAL")
        authorization.order_version_snapshot += 1
        with self.assertRaises(ValidationError):
            authorization.save()

    def test_rejected_pde_review_cannot_authorize(self):
        pde_review = self._review(
            "PDE_PRODUCTION_FEASIBILITY", 1, conclusion="REJECT",
        )
        create_pde_review_predecessor_relation(pde_review=pde_review, user=self.user)
        workflow, decision = self._approval(
            pde_review, "PDEProductionFeasibilityReview", "approved",
        )
        with self.assertRaises(PDEEngineeringPreparationAdmissionError) as caught:
            create_pde_engineering_preparation_authorization(
                pde_review=pde_review, workflow_instance=workflow,
                approval_decision=decision, user=self.user,
            )
        self.assertEqual(caught.exception.code, "PDE_REVIEW_NOT_ADMISSIBLE")

    def test_pending_pde_workflow_cannot_authorize(self):
        pde_review = self._review("PDE_PRODUCTION_FEASIBILITY", 1)
        create_pde_review_predecessor_relation(pde_review=pde_review, user=self.user)
        workflow, decision = self._approval(
            pde_review, "PDEProductionFeasibilityReview", "pending",
        )
        with self.assertRaises(PDEEngineeringPreparationAdmissionError):
            create_pde_engineering_preparation_authorization(
                pde_review=pde_review, workflow_instance=workflow,
                approval_decision=decision, user=self.user,
            )

    def test_scope_item_admission_returns_exact_authorization(self):
        pde_review, _, authorization = self._authorized_chain()
        result = require_pde_engineering_preparation_admission(
            company_id=self.company.pk, sales_order_item_id=self.item.pk,
        )
        self.assertEqual(result.authorization_id, authorization.pk)
        self.assertEqual(result.pde_review_id, pde_review.pk)
        self.assertEqual(result.sales_order_item_id, self.item.pk)

    def test_item_outside_scope_is_blocked(self):
        _, _, authorization = self._authorized_chain()
        item2 = SalesOrderItem.objects.create(
            sales_order=self.order, line_no=20, material=self.material, quantity=1,
            required_date=self.order.required_delivery_date,
        )
        with self.assertRaises(PDEEngineeringPreparationAdmissionError) as caught:
            require_pde_engineering_preparation_admission(
                company_id=self.company.pk, sales_order_item_id=item2.pk,
                authorization_id=authorization.pk,
            )
        self.assertEqual(caught.exception.code, "SALES_ORDER_ITEM_OUT_OF_REVIEW_SCOPE")

    def test_missing_authorization_is_blocked(self):
        with self.assertRaises(PDEEngineeringPreparationAdmissionError) as caught:
            require_pde_engineering_preparation_admission(
                company_id=self.company.pk, sales_order_item_id=self.item.pk,
            )
        self.assertEqual(caught.exception.code, "PDE_ENGINEERING_AUTHORIZATION_NOT_UNIQUE")

    def test_wrong_company_is_blocked(self):
        self._authorized_chain()
        other = Company.objects.create(code=f"OTHER-{self._testMethodName}", name="其他公司")
        with self.assertRaises(PDEEngineeringPreparationAdmissionError):
            require_pde_engineering_preparation_admission(
                company_id=other.pk, sales_order_item_id=self.item.pk,
            )

    def test_predecessor_and_authorization_are_idempotent_for_same_facts(self):
        pde_review, predecessor, authorization = self._authorized_chain()
        same_predecessor = create_pde_review_predecessor_relation(
            pde_review=pde_review, user=self.user,
        )
        same_authorization = create_pde_engineering_preparation_authorization(
            pde_review=pde_review,
            workflow_instance=authorization.workflow_instance,
            approval_decision=authorization.approval_decision,
            user=self.user,
        )
        self.assertEqual(same_predecessor.pk, predecessor.pk)
        self.assertEqual(same_authorization.pk, authorization.pk)
        self.assertEqual(PDEReviewPredecessorRelation.objects.count(), 1)
        self.assertEqual(PDEEngineeringPreparationAuthorization.objects.count(), 1)

    def test_real_final_approval_transaction_persists_authorization(self):
        pde_review = self._review("PDE_PRODUCTION_FEASIBILITY", 1)
        predecessor = create_pde_review_predecessor_relation(
            pde_review=pde_review, user=self.user,
        )
        workflow = WorkflowInstance.objects.create(
            instance_no=f"PDE0033-WF-FINAL-{self._testMethodName}",
            process_definition=self.process,
            document_type="PDEProductionFeasibilityReview",
            document_id=pde_review.pk, status="pending", current_step=1,
            total_steps=1, version=1,
        )
        ApprovalTask.objects.create(
            task_no=f"PDE0033-TASK-FINAL-{self._testMethodName}",
            workflow_instance=workflow, step_no=1, required_role_code="TEST",
            status="pending", version=1,
        )
        with patch(
            "pde.order_review_approval.approval_authorization",
            return_value={"allowed": True},
        ):
            decide_final_approval(
                user=self.user, review_type="PDE_PRODUCTION_FEASIBILITY",
                review_id=pde_review.pk,
                data={
                    "expectedReviewVersion": 1,
                    "expectedSourceVersion": "R1",
                    "decision": "APPROVE",
                    "approvalOpinion": "同意进入工程准备",
                    "riskHandling": "",
                    "actionId": f"final-{self._testMethodName}",
                },
                idempotency_key=f"final-idem-{self._testMethodName}",
            )
        authorization = PDEEngineeringPreparationAuthorization.objects.get(
            predecessor_relation=predecessor,
        )
        self.assertEqual(authorization.workflow_instance_id, workflow.pk)
        self.assertEqual(authorization.approval_decision.decision, "approved")

    def test_crm_explicit_reject_blocks_new_predecessor(self):
        review = self._review("CRM_ORDER_REVIEW", 2, conclusion="REJECT")
        self._approval(review, "CRMOrderReview", "approved")
        pde_review = self._review("PDE_PRODUCTION_FEASIBILITY", 1, status="DRAFT")
        with self.assertRaises(PDEEngineeringPreparationAdmissionError) as caught:
            create_pde_review_predecessor_relation(pde_review=pde_review, user=self.user)
        self.assertEqual(caught.exception.code, "CRM_ORDER_REVIEW_EXPLICITLY_REJECTED")

    def test_crm_final_rejected_blocks_new_predecessor(self):
        review = self._review("CRM_ORDER_REVIEW", 2)
        self._approval(review, "CRMOrderReview", "rejected")
        pde_review = self._review("PDE_PRODUCTION_FEASIBILITY", 1, status="DRAFT")
        with self.assertRaises(PDEEngineeringPreparationAdmissionError) as caught:
            create_pde_review_predecessor_relation(pde_review=pde_review, user=self.user)
        self.assertEqual(caught.exception.code, "CRM_ORDER_FINAL_APPROVAL_REQUIRED")

    def test_crm_pending_blocks_new_predecessor(self):
        review = self._review("CRM_ORDER_REVIEW", 2)
        self._approval(review, "CRMOrderReview", "pending")
        pde_review = self._review("PDE_PRODUCTION_FEASIBILITY", 1, status="DRAFT")
        with self.assertRaises(PDEEngineeringPreparationAdmissionError) as caught:
            create_pde_review_predecessor_relation(pde_review=pde_review, user=self.user)
        self.assertEqual(caught.exception.code, "CRM_ORDER_FINAL_APPROVAL_REQUIRED")

    def test_gate_exact_new_crm_version_selects_its_0032_relation(self):
        crm2 = self._review("CRM_ORDER_REVIEW", 2)
        self._approval(crm2, "CRMOrderReview", "approved")
        relation2 = OrderReviewSalesOrderRelation.objects.create(
            company=self.company, review=crm2, sales_order=self.order,
            scope_mode="SELECTED_ITEMS", scope_reason="明确选择第一行",
            order_version_snapshot=self.order.version,
            source_content_hash_snapshot=crm2.source_content_hash,
            resolution_basis="RUNTIME_GATE", created_by=self.user,
            audit_hash=self._hash("crm-relation-v2"),
        )
        OrderReviewScopeItem.objects.create(
            relation=relation2, sales_order_item=self.item,
            line_no_snapshot=self.item.line_no,
            external_line_no_snapshot=self.item.external_line_no,
            item_identity_hash=self._hash("scope-v2"),
        )
        pde_review = self._review("PDE_PRODUCTION_FEASIBILITY", 1, status="DRAFT")
        predecessor = create_pde_review_predecessor_relation(
            pde_review=pde_review, user=self.user,
        )
        self.assertEqual(predecessor.crm_order_relation_id, relation2.pk)
        self.assertEqual(predecessor.crm_review_version_snapshot, 2)

    def test_unresolved_scope_blocks_new_predecessor(self):
        OrderReviewSalesOrderRelation.objects.filter(pk=self.crm_relation.pk).update(
            scope_mode="UNRESOLVED",
            resolution_basis="APPROVED_HISTORICAL_MANIFEST",
        )
        pde_review = self._review("PDE_PRODUCTION_FEASIBILITY", 1, status="DRAFT")
        with self.assertRaises(PDEEngineeringPreparationAdmissionError) as caught:
            create_pde_review_predecessor_relation(pde_review=pde_review, user=self.user)
        self.assertEqual(caught.exception.code, "CRM_ORDER_REVIEW_SCOPE_UNRESOLVED")

    def test_conditional_pde_review_cannot_authorize(self):
        pde_review = self._review(
            "PDE_PRODUCTION_FEASIBILITY", 1, conclusion="CONDITIONAL",
        )
        create_pde_review_predecessor_relation(pde_review=pde_review, user=self.user)
        workflow, decision = self._approval(
            pde_review, "PDEProductionFeasibilityReview", "approved",
        )
        with self.assertRaises(PDEEngineeringPreparationAdmissionError) as caught:
            create_pde_engineering_preparation_authorization(
                pde_review=pde_review, workflow_instance=workflow,
                approval_decision=decision, user=self.user,
            )
        self.assertEqual(caught.exception.code, "PDE_REVIEW_NOT_ADMISSIBLE")

    def test_legacy_accept_plus_final_approved_is_authorized(self):
        _, _, authorization = self._authorized_chain(pde_conclusion="ACCEPT")
        self.assertIsNotNone(authorization.pk)

    def test_higher_pde_review_without_authorization_does_not_replace_exact_chain(self):
        original_review, _, authorization = self._authorized_chain()
        self._review("PDE_PRODUCTION_FEASIBILITY", 2)
        admitted = require_pde_engineering_preparation_admission(
            company_id=self.company.pk, sales_order_item_id=self.item.pk,
            authorization_id=authorization.pk,
        )
        self.assertEqual(admitted.pde_review_id, original_review.pk)
        self.assertEqual(admitted.pde_review_version, 1)

    def _oei_payload(self, authorization_id=None):
        payload = {
            "company_id": self.company.pk,
            "instance_no": f"OEI-{self._testMethodName}",
            "sales_order_item_id": self.item.pk,
            "product_category_id": self.category.pk,
            "selected_process_type_id": self.process_type.pk,
            "source_record_id": self.source.pk,
        }
        if authorization_id is not None:
            payload["engineering_preparation_authorization_id"] = authorization_id
        return payload

    def _oei_identity(self):
        return {
            "sourceSystem": "TEST", "sourceType": "TEST",
            "sourceObjectType": "SalesOrderItem",
            "externalId": f"item:{self.item.pk}",
        }

    def test_direct_production_foundation_create_without_authorization_is_blocked(self):
        with self.assertRaises(ProductionFoundationError) as caught:
            ProductionFoundationService.write(
                "order-engineering-instances", user=self.user,
                payload=self._oei_payload(),
                idempotency_key=f"idem-{self._testMethodName}",
                source_identity=self._oei_identity(),
            )
        self.assertEqual(caught.exception.code, "PDE_ENGINEERING_AUTHORIZATION_NOT_UNIQUE")
        self.assertEqual(OrderEngineeringInstance.objects.count(), 0)

    def test_production_foundation_persists_exact_authorization(self):
        _, _, authorization = self._authorized_chain()
        result = ProductionFoundationService.write(
            "order-engineering-instances", user=self.user,
            payload=self._oei_payload(authorization.pk),
            idempotency_key=f"idem-{self._testMethodName}",
            source_identity=self._oei_identity(),
        )
        instance = OrderEngineeringInstance.objects.get(pk=result["row"]["id"])
        self.assertEqual(instance.engineering_preparation_authorization_id, authorization.pk)
        self.assertEqual(
            instance.engineering_preparation_authorization.predecessor_relation.pde_review.review_version,
            1,
        )

    def _order_engineering_code_rule(self):
        return CodeRule.objects.create(
            entity_type="production_order_engineering",
            prefix="OEI",
            date_format="%Y%m",
            seq_length=6,
            company_id=self.company.pk,
        )

    def test_confirmed_order_identity_creates_one_authorized_oei_idempotently(self):
        _, _, authorization = self._authorized_chain()
        self._order_engineering_code_rule()
        before_design_items = ProductDesignItem.objects.count()
        payload = {
            "user": self.user,
            "sales_order_item_id": self.item.pk,
            "customer_product_name": "本订单单独工程产品",
            "product_category_id": self.category.pk,
            "selected_process_type_id": self.process_type.pk,
            "source_record_id": self.source.pk,
            "authorization_id": authorization.pk,
            "idempotency_key": "order-engineering-intake-one",
            "reason": "人工确认按单工程身份",
        }
        created = OrderEngineeringIntakeService.confirm_identity_and_create(**payload)
        self.item.refresh_from_db()
        instance = OrderEngineeringInstance.objects.get(sales_order_item=self.item)
        self.assertFalse(created["idempotent"])
        self.assertEqual(self.item.engineering_mode, "ORDER_ENGINEERED")
        self.assertEqual(self.item.customer_product_name, "本订单单独工程产品")
        self.assertIsNone(self.item.product_definition_id)
        self.assertIsNone(self.item.product_version_id)
        self.assertEqual(instance.product_category_id, self.category.pk)
        self.assertEqual(instance.selected_process_type_id, self.process_type.pk)
        self.assertEqual(instance.source_record_id, self.source.pk)
        self.assertEqual(instance.engineering_preparation_authorization_id, authorization.pk)
        self.assertEqual(ProductDesignItem.objects.count(), before_design_items)

        replay = OrderEngineeringIntakeService.confirm_identity_and_create(**payload)
        self.assertTrue(replay["idempotent"])
        self.assertEqual(replay["oei"]["id"], instance.pk)
        self.assertEqual(OrderEngineeringInstance.objects.filter(sales_order_item=self.item).count(), 1)

    def test_order_identity_and_oei_roll_back_together(self):
        _, _, authorization = self._authorized_chain()
        self._order_engineering_code_rule()
        with patch(
            "pde.order_engineering_intake_service.ProductionFoundationService.write",
            side_effect=ProductionFoundationError("FORCED_FAILURE", "forced"),
        ):
            with self.assertRaises(OrderEngineeringIntakeError):
                OrderEngineeringIntakeService.confirm_identity_and_create(
                    user=self.user,
                    sales_order_item_id=self.item.pk,
                    customer_product_name="本订单单独工程产品",
                    product_category_id=self.category.pk,
                    selected_process_type_id=self.process_type.pk,
                    source_record_id=self.source.pk,
                    authorization_id=authorization.pk,
                    idempotency_key="order-engineering-intake-failure",
                )
        self.item.refresh_from_db()
        self.assertEqual(self.item.engineering_mode, "STANDARD")
        self.assertEqual(self.item.customer_product_name, "")
        self.assertFalse(OrderEngineeringInstance.objects.filter(sales_order_item=self.item).exists())

    def test_order_engineering_intake_endpoint_reads_back_exact_chain(self):
        _, _, authorization = self._authorized_chain()
        self._order_engineering_code_rule()
        response = self.client.post(
            "/api/pde/engineering-readiness/order-engineering-intake/",
            {
                "salesOrderItemId": self.item.pk,
                "customerProductName": "本订单单独工程产品",
                "productCategoryId": self.category.pk,
                "selectedProcessTypeId": self.process_type.pk,
                "sourceRecordId": self.source.pk,
                "authorizationId": authorization.pk,
                "reason": "人工确认按单工程身份",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="order-engineering-intake-endpoint",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["admission"]["crmOrderRelationId"], self.crm_relation.pk)
        self.assertEqual(response.data["oei"]["authorizationId"], authorization.pk)
        readback = self.client.get(
            "/api/pde/engineering-readiness/order-engineering-intake/",
            {"salesOrderItemId": self.item.pk},
        )
        self.assertEqual(readback.status_code, 200)
        self.assertEqual(readback.data["identity"]["engineeringModeCode"], "ORDER_ENGINEERED")
        self.assertEqual(readback.data["oei"]["id"], response.data["oei"]["id"])

    def test_legacy_oei_nullable_is_preserved_without_backfill(self):
        instance = OrderEngineeringInstance.objects.create(
            company=self.company, instance_no=f"LEGACY-{self._testMethodName}",
            sales_order_item=self.item, product_category=self.category,
            selected_process_type=self.process_type, source_record=self.source,
            engineering_preparation_authorization=None,
        )
        instance.full_clean()
        self.assertIsNone(instance.engineering_preparation_authorization_id)
        self.assertEqual(PDEEngineeringPreparationAuthorization.objects.count(), 0)

    def test_predecessor_failure_rolls_back_new_pde_review(self):
        before = OrderCrossFunctionalReview.objects.filter(
            review_type="PDE_PRODUCTION_FEASIBILITY",
        ).count()
        with self.assertRaises(PDEEngineeringPreparationAdmissionError):
            with transaction.atomic():
                pde_review = self._review(
                    "PDE_PRODUCTION_FEASIBILITY", 1, status="DRAFT",
                )
                OrderReviewScopeItem.objects.filter(relation=self.crm_relation).delete()
                create_pde_review_predecessor_relation(
                    pde_review=pde_review, user=self.user,
                )
        self.assertEqual(
            OrderCrossFunctionalReview.objects.filter(
                review_type="PDE_PRODUCTION_FEASIBILITY",
            ).count(),
            before,
        )

    def _revocation_fixture(self):
        pde_review, predecessor, authorization = self._authorized_chain()
        result = ProductionFoundationService.write(
            "order-engineering-instances",
            user=self.user,
            payload=self._oei_payload(authorization.pk),
            idempotency_key=f"oei-{self._testMethodName}",
            source_identity=self._oei_identity(),
        )
        instance = OrderEngineeringInstance.objects.get(pk=result["row"]["id"])
        development_order = create_business_object_with_initial_state(
            model=SalesOrder,
            initial_state="draft",
            company=self.company,
            department=self.department,
            customer=self.customer,
            order_no=f"DEV-{self._testMethodName}",
            order_date=date.today(),
            required_delivery_date=date.today() + timedelta(days=10),
            order_source="manual",
            business_purpose=SalesOrder.BusinessPurpose.DEVELOPMENT_VALIDATION,
            acceptance_marker="DEVELOPMENT_ONLY",
            created_by=self.user,
        )
        arguments = {
            "actor": self.user,
            "authorized_by": self.user,
            "relation_id": self.crm_relation.pk,
            "pde_review_id": pde_review.pk,
            "predecessor_id": predecessor.pk,
            "authorization_id": authorization.pk,
            "engineering_instance_id": instance.pk,
            "expected_order_id": self.order.pk,
            "expected_development_order_id": development_order.pk,
            "expected_source_record_id": self.source.pk,
            "idempotency_key": f"revoke-{self._testMethodName}",
            "reason": "测试：纠正CRM来源与正式订单业务身份冲突链",
        }
        return pde_review, predecessor, authorization, instance, arguments

    def test_revocation_is_immutable_transactional_and_idempotent(self):
        pde_review, predecessor, authorization, instance, arguments = (
            self._revocation_fixture()
        )
        protected = {
            "orderCustomerId": self.order.customer_id,
            "orderProject": self.order.project_reference,
            "orderContract": self.order.contract_reference,
            "crmReviewAuditHash": self.crm_review.audit_hash,
            "pdeReviewAuditHash": pde_review.audit_hash,
            "workflowId": authorization.workflow_instance_id,
            "decisionId": authorization.approval_decision_id,
        }
        history_counts = {
            "relations": OrderReviewSalesOrderRelation.objects.count(),
            "predecessors": PDEReviewPredecessorRelation.objects.count(),
            "authorizations": PDEEngineeringPreparationAuthorization.objects.count(),
            "oei": OrderEngineeringInstance.objects.count(),
        }

        result = revoke_pde_admission_chain(**arguments)

        instance.refresh_from_db()
        revocation = PDEAdmissionChainRevocation.objects.get(pk=result["revocationId"])
        self.assertEqual(instance.status, "inactive")
        self.assertEqual(revocation.crm_order_relation_id, self.crm_relation.pk)
        self.assertEqual(revocation.pde_review_id, pde_review.pk)
        self.assertEqual(revocation.predecessor_relation_id, predecessor.pk)
        self.assertEqual(revocation.authorization_id, authorization.pk)
        self.assertEqual(revocation.engineering_instance_id, instance.pk)
        self.assertEqual(revocation.reason_code, "BUSINESS_IDENTITY_CONFLICT")
        self.assertEqual(len(revocation.audit_hash), 64)
        self.assertEqual(
            BusinessStateTransition.objects.filter(
                object_type="OrderEngineeringInstance",
                object_id=instance.pk,
                source_state="draft",
                target_state="inactive",
                action_code="pde.admission_chain.revoke",
            ).count(),
            1,
        )
        self.assertEqual(
            OrganizationOperatingAuditRecord.objects.filter(
                pk=revocation.audit_record_id,
                action_code="pde.admission_chain.revoke",
            ).count(),
            1,
        )
        self.assertEqual(history_counts, {
            "relations": OrderReviewSalesOrderRelation.objects.count(),
            "predecessors": PDEReviewPredecessorRelation.objects.count(),
            "authorizations": PDEEngineeringPreparationAuthorization.objects.count(),
            "oei": OrderEngineeringInstance.objects.count(),
        })

        replay = revoke_pde_admission_chain(**arguments)
        self.assertTrue(replay["idempotent"])
        self.assertEqual(replay["businessWriteCount"], 0)
        self.assertEqual(PDEAdmissionChainRevocation.objects.count(), 1)
        self.assertEqual(
            BusinessStateTransition.objects.filter(
                object_type="OrderEngineeringInstance", object_id=instance.pk,
            ).count(),
            1,
        )

        self.order.refresh_from_db()
        self.crm_review.refresh_from_db()
        pde_review.refresh_from_db()
        self.assertEqual(protected, {
            "orderCustomerId": self.order.customer_id,
            "orderProject": self.order.project_reference,
            "orderContract": self.order.contract_reference,
            "crmReviewAuditHash": self.crm_review.audit_hash,
            "pdeReviewAuditHash": pde_review.audit_hash,
            "workflowId": authorization.workflow_instance_id,
            "decisionId": authorization.approval_decision_id,
        })
        revocation.reason = "不得覆盖"
        with self.assertRaises(ValidationError):
            revocation.save()
        with self.assertRaises(ValidationError):
            revocation.delete()

    def test_revoked_chain_is_excluded_from_all_formal_intake_reads(self):
        pde_review, _, authorization, instance, arguments = self._revocation_fixture()
        revoke_pde_admission_chain(**arguments)

        with self.assertRaises(PDEEngineeringPreparationAdmissionError) as caught:
            require_pde_engineering_preparation_admission(
                company_id=self.company.pk,
                sales_order_item_id=self.item.pk,
                authorization_id=authorization.pk,
            )
        self.assertEqual(caught.exception.code, "PDE_ADMISSION_CHAIN_REVOKED")
        with self.assertRaises(OrderEngineeringIntakeError) as intake:
            OrderEngineeringIntakeService.facts(
                user=self.user, sales_order_item_id=self.item.pk,
            )
        self.assertEqual(intake.exception.code, "PDE_ADMISSION_CHAIN_REVOKED")

        projection = _formal_sales_order_projection(
            review=self.crm_review, company_id=self.company.pk,
        )
        self.assertFalse(projection["formalSalesOrderEstablished"])
        self.assertTrue(projection["formalSalesOrderRevoked"])
        self.assertEqual(
            projection["revokedFormalSalesOrderRelationId"], self.crm_relation.pk,
        )

        context = preparation_context_facts(
            self.company.pk, sales_order_id=self.order.pk,
        )
        self.assertEqual(context["statusCode"], "PDE_ADMISSION_CHAIN_REVOKED")
        self.assertFalse(context["canPrepare"])
        self.assertIsNone(context["crmOrderRelationId"])
        self.assertIsNone(context["pdeReviewId"])
        self.assertEqual(context["scopeItemIds"], [])
        self.assertEqual(context["revokedEngineeringInstanceId"], instance.pk)
        self.assertEqual(context["revokedEngineeringInstanceStatusLabel"], "已失效")
        page = self.client.get(
            "/api/pde/engineering-readiness/",
            {"salesOrderId": self.order.pk},
        )
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.data["rows"], [])
        self.assertEqual(
            page.data["strictFacts"]["statusCode"],
            "PDE_ADMISSION_CHAIN_REVOKED",
        )
        self.assertEqual(page.data["strictFacts"]["businessWriteCount"], 0)
        self.assertEqual(pde_review.pk, context["revokedPdeReviewId"])

    def test_cancelled_order_is_not_a_current_formal_intake_candidate(self):
        with transaction.atomic():
            transition_business_object(
                business_object=self.order,
                object_type="SalesOrder",
                source_state="draft",
                target_state="cancelled",
                action_code="sales.order.cancel",
                operator=self.user,
                reason="测试：正式订单受控清退",
                audit_reference="TEST:cancelled-current-candidate",
                allowed_transitions={("draft", "cancelled")},
            )
        with self.assertRaises(OrderDemandPreparationError) as caught:
            preparation_facts(
                self.company.pk, sales_order_id=self.order.pk,
            )
        self.assertEqual(
            caught.exception.code,
            "CRM_ORDER_FORMAL_RELATION_REQUIRED",
        )
        page = self.client.get(
            "/api/pde/engineering-readiness/",
            {"salesOrderId": self.order.pk},
        )
        self.assertEqual(page.status_code, 409)
        self.assertNotIn(self.order.order_no, page.content.decode("utf-8"))

    def test_node11_excludes_revoked_inactive_order_engineering_instance(self):
        _, _, _, instance, arguments = self._revocation_fixture()
        before = self.client.get("/api/pde/engineering-documents/")
        self.assertEqual(before.status_code, 200)
        self.assertIn(
            instance.pk,
            [row.get("orderEngineeringInstanceId") for row in before.data["rows"]],
        )

        revoke_pde_admission_chain(**arguments)

        after = self.client.get("/api/pde/engineering-documents/")
        self.assertEqual(after.status_code, 200)
        self.assertNotIn(
            instance.pk,
            [row.get("orderEngineeringInstanceId") for row in after.data["rows"]],
        )
        self.assertNotIn(self.order.order_no, after.content.decode("utf-8"))

    def test_revoked_relation_cannot_admit_sales_order(self):
        _, _, _, _, arguments = self._revocation_fixture()
        result = revoke_pde_admission_chain(**arguments)

        with self.assertRaises(CRMOrderAdmissionError) as caught:
            require_current_crm_sales_order_admission(order=self.order)
        self.assertEqual(caught.exception.code, "CRM_ORDER_RELATION_REVOKED")
        facts = current_crm_sales_order_admission_facts(self.order)
        self.assertFalse(facts["admitted"])
        self.assertFalse(facts["submitAllowed"])
        self.assertIsNone(facts["currentSource"])
        self.assertEqual(
            facts["historicalSources"][0]["revocationId"],
            result["revocationId"],
        )

    def test_stale_source_context_correction_is_idempotent_and_protects_history(self):
        _, _, _, instance, arguments = self._revocation_fixture()
        revocation_result = revoke_pde_admission_chain(**arguments)
        self.order.delivery_information = {
            "sourceRecordId": self.source.pk,
            "sourceVersion": self.source.source_version,
            "sourceContentHash": self.source.content_hash,
            "committedDeliveryDate": "2026-12-31",
        }
        self.order.save(update_fields=["delivery_information", "updated_at"])
        protected = {
            "source": {
                "sourceNo": self.source.source_no,
                "version": self.source.source_version,
                "hash": self.source.content_hash,
                "payload": self.source.source_payload,
            },
            "reviewAuditHash": self.crm_review.audit_hash,
            "relationAuditHash": self.crm_relation.audit_hash,
            "revocationHash": PDEAdmissionChainRevocation.objects.get(
                pk=revocation_result["revocationId"],
            ).audit_hash,
        }
        audit_before = OrganizationOperatingAuditRecord.objects.filter(
            action_code=CRM_SOURCE_CORRECTION_ACTION,
        ).count()
        kwargs = {
            "actor": self.user,
            "order_id": self.order.pk,
            "expected_order_no": self.order.order_no,
            "expected_source_record_id": self.source.pk,
            "expected_source_version": self.source.source_version,
            "expected_external_source_no": "CRM-PDE0033",
            "expected_relation_id": self.crm_relation.pk,
            "expected_revocation_id": revocation_result["revocationId"],
            "idempotency_key": f"correct-{self._testMethodName}",
            "reason": "测试：解除已撤销历史链遗留的当前CRM来源上下文",
        }

        result = correct_sales_order_crm_source_context(**kwargs)
        replay = correct_sales_order_crm_source_context(**kwargs)

        self.assertFalse(result["idempotent"])
        self.assertEqual(result["businessWriteCount"], 2)
        self.assertTrue(replay["idempotent"])
        self.assertEqual(replay["businessWriteCount"], 0)
        self.assertEqual(result["organizationAuditId"], replay["organizationAuditId"])
        self.assertEqual(
            OrganizationOperatingAuditRecord.objects.filter(
                action_code=CRM_SOURCE_CORRECTION_ACTION,
            ).count(),
            audit_before + 1,
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.external_source_no, "")
        self.assertNotIn("sourceRecordId", self.order.delivery_information)
        self.assertNotIn("sourceVersion", self.order.delivery_information)
        self.assertNotIn("sourceContentHash", self.order.delivery_information)
        self.assertEqual(
            self.order.delivery_information["committedDeliveryDate"],
            "2026-12-31",
        )
        self.source.refresh_from_db()
        self.crm_review.refresh_from_db()
        self.crm_relation.refresh_from_db()
        instance.refresh_from_db()
        revocation = PDEAdmissionChainRevocation.objects.get(
            pk=revocation_result["revocationId"],
        )
        self.assertEqual(instance.status, "inactive")
        self.assertEqual(protected, {
            "source": {
                "sourceNo": self.source.source_no,
                "version": self.source.source_version,
                "hash": self.source.content_hash,
                "payload": self.source.source_payload,
            },
            "reviewAuditHash": self.crm_review.audit_hash,
            "relationAuditHash": self.crm_relation.audit_hash,
            "revocationHash": revocation.audit_hash,
        })

    def test_revocation_rolls_back_audit_fact_when_state_transition_fails(self):
        _, _, _, instance, arguments = self._revocation_fixture()
        audit_before = OrganizationOperatingAuditRecord.objects.filter(
            action_code="pde.admission_chain.revoke",
        ).count()
        with patch(
            "pde.admission_chain_revocation.transition_business_object",
            side_effect=BusinessStateTransitionError("forced"),
        ):
            with self.assertRaises(PDEAdmissionChainRevocationError) as caught:
                revoke_pde_admission_chain(**arguments)
        self.assertEqual(caught.exception.code, "OEI_STATE_TRANSITION_FAILED")
        instance.refresh_from_db()
        self.assertEqual(instance.status, "draft")
        self.assertEqual(PDEAdmissionChainRevocation.objects.count(), 0)
        self.assertEqual(
            OrganizationOperatingAuditRecord.objects.filter(
                action_code="pde.admission_chain.revoke",
            ).count(),
            audit_before,
        )

