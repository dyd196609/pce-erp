from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase
from rest_framework.test import APIClient
from workflow_runtime.action_permissions import MODULE_ACTIONS
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import BusinessStateTransitionError

from supplier_performance.models import (
    SupplierPayableConfirmation,
    SupplierPaymentRequest,
    SupplierSettlementActionAudit,
)
from supplier_performance.services import (
    ensure_v831_demo_data,
    execute_v831_action,
    transition_payable_confirmation,
    transition_payment_request,
)


class SupplierSettlementWorkflowV831Tests(TestCase):
    def setUp(self):
        self.users = ensure_v831_demo_data()
        self.client = APIClient()

    def payable(self, status):
        return SupplierPayableConfirmation.objects.filter(status=status).first()

    def request(self, status):
        return SupplierPaymentRequest.objects.filter(status=status).first()

    def execute(self, action, obj, role):
        return execute_v831_action(
            user=self.users[role],
            action_code=action,
            object_id=obj.pk,
            reason="V83.1 automated test",
        )

    def test_payable_submit_review(self):
        result = self.execute("SCM_PAYABLE_SUBMIT_REVIEW", self.payable("draft"), "scm_payable_buyer")
        self.assertEqual(result["afterStatus"], "internal_review")

    def test_payable_approve(self):
        result = self.execute("SCM_PAYABLE_APPROVE", self.payable("internal_review"), "scm_payable_supervisor")
        self.assertEqual(result["afterStatus"], "confirmed")

    def test_payable_create_payment_request_qualification(self):
        result = self.execute("SCM_PAYABLE_CREATE_PAYMENT_REQUEST", self.payable("confirmed"), "scm_payable_supervisor")
        self.assertEqual(result["afterStatus"], "ready_for_payment_request")

    def test_request_submit(self):
        result = self.execute("SCM_PAYMENT_REQUEST_SUBMIT", self.request("draft"), "scm_payment_request_applicant")
        self.assertEqual(result["afterStatus"], "submitted")

    def test_request_approve(self):
        result = self.execute("SCM_PAYMENT_REQUEST_APPROVE", self.request("submitted"), "scm_payment_request_owner")
        self.assertEqual(result["afterStatus"], "approved")

    def test_request_return(self):
        result = self.execute("SCM_PAYMENT_REQUEST_RETURN", self.request("submitted"), "scm_payment_request_owner")
        self.assertEqual(result["afterStatus"], "draft")

    def test_registry_modules_exist(self):
        self.assertIn("supplier-payable-confirmation", MODULE_ACTIONS)
        self.assertIn("supplier-payment-request", MODULE_ACTIONS)

    def test_registry_has_six_actions(self):
        actions = MODULE_ACTIONS["supplier-payable-confirmation"] + MODULE_ACTIONS["supplier-payment-request"]
        self.assertEqual(len(actions), 6)

    def test_wrong_role_blocked(self):
        with self.assertRaises(PermissionError):
            self.execute("SCM_PAYABLE_APPROVE", self.payable("internal_review"), "scm_payable_buyer")

    def test_wrong_status_blocked(self):
        with self.assertRaises(PermissionError):
            self.execute("SCM_PAYABLE_APPROVE", self.payable("draft"), "scm_payable_supervisor")

    def test_unknown_action_blocked(self):
        with self.assertRaises(ValueError):
            self.execute("SCM_PAYABLE_UNKNOWN", self.payable("draft"), "scm_payable_buyer")

    def test_direct_payable_status_write_blocked(self):
        obj = self.payable("draft")
        obj.status = "confirmed"
        with self.assertRaises(ValidationError):
            obj.save()

    def test_direct_request_status_write_blocked(self):
        obj = self.request("draft")
        obj.status = "approved"
        with self.assertRaises(ValidationError):
            obj.save()

    def test_illegal_payable_jump_blocked(self):
        with transaction.atomic(), self.assertRaises(BusinessStateTransitionError):
            transition_payable_confirmation(
                self.payable("draft"), "confirmed", self.users["scm_payable_buyer"], "jump"
            )

    def test_illegal_request_jump_blocked(self):
        with transaction.atomic(), self.assertRaises(BusinessStateTransitionError):
            transition_payment_request(
                self.request("draft"), "approved", self.users["scm_payment_request_applicant"], "jump"
            )

    def test_action_creates_audit(self):
        obj = self.payable("draft")
        result = self.execute("SCM_PAYABLE_SUBMIT_REVIEW", obj, "scm_payable_buyer")
        audit = SupplierSettlementActionAudit.objects.get(action_no=result["actionNo"])
        self.assertEqual((audit.before_status, audit.after_status), ("draft", "internal_review"))

    def test_transition_references_action_audit(self):
        obj = self.request("draft")
        result = self.execute("SCM_PAYMENT_REQUEST_SUBMIT", obj, "scm_payment_request_applicant")
        transition = BusinessStateTransition.objects.filter(
            object_type="SupplierPaymentRequest", object_id=obj.pk
        ).order_by("-version").first()
        self.assertEqual(transition.audit_reference, result["auditReference"])

    def test_payable_workflow_facts(self):
        facts = self.client.get("/api/scm/supplier-payable-confirmations/").data["data"]["strictFacts"]
        self.assertEqual((facts["workflowActionCount"], facts["availableActionCount"]), (3, 3))

    def test_request_workflow_facts(self):
        facts = self.client.get("/api/scm/supplier-payment-requests/").data["data"]["strictFacts"]
        self.assertEqual((facts["workflowActionCount"], facts["availableActionCount"]), (3, 3))

    def test_acceptance_workflow_facts(self):
        data = self.client.get("/api/scm/supplier-payment-requests/").data["data"]
        keys = ["workflowActionCount", "availableActionCount", "executedActionCount", "auditRecordCount"]
        self.assertTrue(all(data["acceptanceFacts"][key] == data["strictFacts"][key] for key in keys))

    def test_action_api_requires_authentication(self):
        response = self.client.post("/api/scm/supplier-settlement-workflow-actions/", {
            "objectId": self.payable("draft").pk,
            "actionCode": "SCM_PAYABLE_SUBMIT_REVIEW",
        }, format="json")
        self.assertEqual(response.status_code, 403)

    def test_action_api_authenticated(self):
        self.client.force_authenticate(self.users["scm_payable_buyer"])
        response = self.client.post("/api/scm/supplier-settlement-workflow-actions/", {
            "objectId": self.payable("draft").pk,
            "actionCode": "SCM_PAYABLE_SUBMIT_REVIEW",
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["safety"]["paymentExecutionWriteCount"], 0)

    def test_action_api_get_permission_success(self):
        obj = self.payable("draft")
        self.client.force_authenticate(self.users["scm_payable_buyer"])
        response = self.client.get(
            "/api/scm/supplier-settlement-workflow-actions/",
            {
                "objectId": obj.pk,
                "actionCode": "SCM_PAYABLE_SUBMIT_REVIEW",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["permissionGranted"])

    def test_action_api_get_wrong_role_blocked(self):
        obj = self.payable("internal_review")
        self.client.force_authenticate(self.users["scm_payable_buyer"])
        response = self.client.get(
            "/api/scm/supplier-settlement-workflow-actions/",
            {
                "objectId": obj.pk,
                "actionCode": "SCM_PAYABLE_APPROVE",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_canary_cookie_executes_action_without_403(self):
        obj = self.payable("draft")
        session = self.client.get(
            "/api/workflow/action-permissions/canary-session",
            {"actor": "v831-payable-buyer"},
        )
        self.assertEqual(session.status_code, 200)
        preflight = self.client.get(
            "/api/scm/supplier-settlement-workflow-actions/",
            {
                "objectId": obj.pk,
                "actionCode": "SCM_PAYABLE_SUBMIT_REVIEW",
            },
        )
        self.assertEqual(preflight.status_code, 200)
        executed = self.client.post(
            "/api/scm/supplier-settlement-workflow-actions/",
            {
                "objectId": obj.pk,
                "actionCode": "SCM_PAYABLE_SUBMIT_REVIEW",
            },
            format="json",
        )
        self.assertEqual(executed.status_code, 200)

    def test_action_response_contract_complete(self):
        result = self.execute(
            "SCM_PAYMENT_REQUEST_SUBMIT",
            self.request("draft"),
            "scm_payment_request_applicant",
        )
        self.assertEqual(
            set(result),
            {
                "actionNo", "actionCode", "operator", "role",
                "beforeStatus", "afterStatus", "timestamp",
                "auditReference",
            },
        )

    def test_audit_count_increments_after_execution(self):
        before = SupplierSettlementActionAudit.objects.count()
        self.execute(
            "SCM_PAYABLE_APPROVE",
            self.payable("internal_review"),
            "scm_payable_supervisor",
        )
        self.assertEqual(SupplierSettlementActionAudit.objects.count(), before + 1)

    def test_detail_view_mode_five_surface_consistent(self):
        data = self.client.get(
            "/api/scm/supplier-payable-confirmations/"
        ).data["data"]
        self.assertEqual(
            [
                data["payableConfirmationFacts"]["detailViewMode"],
                data["diagnosticFacts"]["detailViewMode"],
                data["strictFacts"]["detailViewMode"],
                data["acceptanceFacts"]["detailViewMode"],
            ],
            ["business_card"] * 4,
        )

    def test_payable_business_detail_complete(self):
        row = self.client.get(
            "/api/scm/supplier-payable-confirmations/"
        ).data["data"]["results"][0]
        detail = row["businessDetail"]
        self.assertEqual(detail["detailViewMode"], "business_card")
        self.assertTrue(detail["basicInformation"]["number"])
        self.assertIn("finalAmount", detail["amountInformation"])

    def test_request_business_detail_complete(self):
        row = self.client.get(
            "/api/scm/supplier-payment-requests/"
        ).data["data"]["results"][0]
        detail = row["businessDetail"]
        self.assertTrue(detail["basicInformation"]["sourceDocument"])
        self.assertIn("operationRecords", detail)

    def test_business_source_chain_has_five_nodes(self):
        row = self.client.get(
            "/api/scm/supplier-payable-confirmations/"
        ).data["data"]["results"][0]
        labels = [
            item["label"] for item in row["businessDetail"]["businessSourceChain"]
        ]
        self.assertEqual(
            labels,
            ["采购订单", "收货", "质量检验", "入库", "供应商对账"],
        )

    def test_business_detail_does_not_expose_technical_fields(self):
        row = self.client.get(
            "/api/scm/supplier-payment-requests/"
        ).data["data"]["results"][0]
        serialized = str(row["businessDetail"])
        self.assertNotIn("statusCode", serialized)
        self.assertNotIn("sourceObjectRefs", serialized)

    def test_five_surface_workflow_counts(self):
        data = self.client.get("/api/scm/supplier-payable-confirmations/").data["data"]
        values = [
            data["payableConfirmationFacts"]["workflowActionCount"],
            data["diagnosticFacts"]["workflowActionCount"],
            data["strictFacts"]["workflowActionCount"],
            data["acceptanceFacts"]["workflowActionCount"],
        ]
        self.assertEqual(values, [3, 3, 3, 3])

    def test_danger_writes_zero(self):
        for endpoint, key in [
            ("/api/scm/supplier-payable-confirmations/", "payableConfirmationFacts"),
            ("/api/scm/supplier-payment-requests/", "paymentRequestFacts"),
        ]:
            facts = self.client.get(endpoint).data["data"][key]
            self.assertEqual((
                facts["paymentExecutionWriteCount"],
                facts["bankSendWriteCount"],
                facts["financialImpactWriteCount"],
            ), (0, 0, 0))
