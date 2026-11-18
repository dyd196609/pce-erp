from django.test import TestCase

from system.models import Company, User
from workflow_runtime.models import (
    ApprovalDecision, ApprovalTask, ProcessDefinition, WorkflowInstance,
)

from .crm_order_admission import CRMOrderAdmissionError, require_crm_order_admission
from .models import EngineeringSourceRecord, OrderCrossFunctionalReview


class CRMOrderAdmissionP0Tests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="P0GATE", name="P0准入测试公司")
        self.user = User.objects.create_user(
            username="p0_gate_user", password="unused", real_name="P0测试人",
            company_id=self.company.pk, is_superuser=True,
        )
        self.source = EngineeringSourceRecord.objects.create(
            company=self.company, source_no="P0-SOURCE", source_name="P0订单来源",
            source_type="controlled_import", source_version="R1", content_hash="1" * 64,
            status="confirmed", source_payload={},
        )
        self.process = ProcessDefinition.objects.create(
            definition_code="CRM_ORDER_REVIEW_P0_GATE_TEST",
            definition_name="P0 CRM订单评审", business_domain="CRM",
            document_type="CRMOrderReview", version=1, active=True,
            definition_hash="p0-gate",
        )

    def _review(self, *, conclusion, workflow_status, decision=None):
        review = OrderCrossFunctionalReview.objects.create(
            company=self.company, source_record=self.source,
            review_type="CRM_ORDER_REVIEW", source_order_no="CRM-P0-001",
            source_version="R1", source_content_hash="1" * 64,
            review_version=1, conclusion=conclusion, reviewer=self.user,
            idempotency_key=f"review-{conclusion or 'blank'}-{workflow_status}",
            audit_hash=("a" if conclusion else "b") * 64,
            record_status="SUBMITTED",
        )
        workflow = WorkflowInstance.objects.create(
            instance_no=f"WF-{review.pk}", process_definition=self.process,
            document_type="CRMOrderReview", document_id=review.pk,
            status=workflow_status, current_step=1, total_steps=1, version=1,
        )
        if decision:
            task = ApprovalTask.objects.create(
                task_no=f"TASK-{review.pk}", workflow_instance=workflow,
                step_no=1, required_role_code="CRM_REVIEWER",
                status=decision, version=1,
            )
            ApprovalDecision.objects.create(
                task=task, decision_sequence=1, actor=self.user, decision=decision,
                comment=decision, action_id=f"action-{review.pk}",
                idempotency_key=f"decision-{review.pk}", decision_hash="d" * 64,
            )
        return review

    def _admit(self, **overrides):
        context = {
            "company_id": self.company.pk,
            "source_record_id": self.source.pk,
            "source_order_no": "CRM-P0-001",
            "source_version": "R1",
        }
        context.update(overrides)
        return require_crm_order_admission(**context)

    def test_reject_and_approved_is_hard_blocked(self):
        self._review(conclusion="REJECT", workflow_status="approved", decision="approved")
        with self.assertRaises(CRMOrderAdmissionError) as caught:
            self._admit()
        self.assertEqual(caught.exception.code, "CRM_ORDER_REVIEW_EXPLICITLY_REJECTED")

    def test_reject_and_rejected_is_hard_blocked(self):
        self._review(conclusion="REJECT", workflow_status="rejected", decision="rejected")
        with self.assertRaises(CRMOrderAdmissionError) as caught:
            self._admit()
        self.assertEqual(caught.exception.code, "CRM_ORDER_REVIEW_EXPLICITLY_REJECTED")

    def test_itemized_blank_conclusion_and_approved_is_admitted(self):
        review = self._review(conclusion="", workflow_status="approved", decision="approved")
        result = self._admit()
        self.assertEqual(result.review_id, review.pk)
        self.assertTrue(result.as_dict()["admitted"])

    def test_pending_approval_is_blocked(self):
        self._review(conclusion="", workflow_status="pending")
        with self.assertRaises(CRMOrderAdmissionError) as caught:
            self._admit()
        self.assertEqual(caught.exception.code, "CRM_ORDER_FINAL_APPROVAL_REQUIRED")

    def test_non_unique_source_context_is_blocked(self):
        second = EngineeringSourceRecord.objects.create(
            company=self.company, source_no="P0-SOURCE-2", source_name="P0订单来源2",
            source_type="controlled_import", source_version="R1", content_hash="2" * 64,
            status="confirmed", source_payload={},
        )
        with self.assertRaises(CRMOrderAdmissionError) as caught:
            self._admit(source_record_id=[self.source.pk, second.pk])
        self.assertEqual(caught.exception.code, "CRM_ORDER_SOURCE_CONTEXT_AMBIGUOUS")
