from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from system.models import Company, OrganizationOperatingAuditRecord, Permission, User
from workflow_runtime.models import (
    ApprovalDecision,
    ApprovalTask,
    BusinessStateTransition,
    ProcessDefinition,
    WorkflowInstance,
    WorkflowNodeDefinition,
)

from .bom_version_control_service import (
    APPROVED_PROJECTION,
    BomVersionControlError,
    RELEASE_ACTION,
    RELEASE_PERMISSION,
    REVIEW_ACTION,
    REVIEW_PERMISSION,
    control_chain_readiness,
    release_readback,
    transition_bom_version,
)
from .models import (
    BOMVersion,
    EngineeringChangeNotice,
    EngineeringDocument,
    EngineeringDocumentVersion,
    ProductBOM,
    ProductDefinition,
    ProductManufacturingOutput,
)
from .production_foundation_service import EngineeringLifecycleService
from .views import EngineeringLifecycleView


class BomVersionControlChainTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="T001", name="测试公司")
        self.reviewer = User.objects.create_user(
            username="bom-reviewer", password="x", real_name="评审人",
            company_id=self.company.pk,
        )
        self.releaser = User.objects.create_user(
            username="bom-releaser", password="x", real_name="发布人",
            company_id=self.company.pk,
        )
        self.product = ProductDefinition.objects.create(
            company=self.company,
            product_code="P-CTRL",
            product_name="控制链测试产品",
            emd_material_code="FG-CTRL",
        )
        self.bom = ProductBOM.objects.create(
            company=self.company,
            product=self.product,
            applicability_scope="PRODUCT_DEFINITION",
            bom_code="BOM-CTRL",
            name="控制链测试BOM",
        )
        self.version = BOMVersion.objects.create(
            bom=self.bom,
            bom_version="V-CTRL",
            revision=1,
            status="draft",
            approval_state="not_submitted",
        )
        Permission.objects.get_or_create(
            code=REVIEW_PERMISSION,
            defaults={"name": "BOM版本正式评审", "module": "PDE"},
        )
        Permission.objects.get_or_create(
            code=RELEASE_PERMISSION,
            defaults={"name": "BOM版本正式发布", "module": "PDE"},
        )
        self.definition = ProcessDefinition.objects.create(
            definition_code="BOM_VERSION_REVIEW_TEST",
            definition_name="BOM版本正式评审",
            business_domain="PDE",
            document_type="BOMVersion",
            version=1,
            active=True,
            definition_hash="a" * 64,
        )
        WorkflowNodeDefinition.objects.create(
            process_definition=self.definition,
            node_code="REVIEW_BOM_VERSION",
            node_name="评审BOM版本",
            sequence=1,
            business_action_code=REVIEW_PERMISSION,
            active=True,
        )
        self.actor_contexts = {
            self.reviewer.pk: {
                "userId": self.reviewer.pk,
                "username": self.reviewer.username,
                "matchedRoleCodes": ["engineering_version_reviewer"],
                "departmentId": 10,
            },
            self.releaser.pk: {
                "userId": self.releaser.pk,
                "username": self.releaser.username,
                "matchedRoleCodes": ["engineering_version_releaser"],
                "departmentId": 20,
            },
        }

    def actor(self, version, user, permission):
        return self.actor_contexts[user.pk]

    def review(self, *, key="review-request-1", reason="正式评审通过"):
        with patch(
            "pde.bom_version_control_service._require_actor",
            side_effect=self.actor,
        ), patch(
            "pde.bom_version_control_service._assert_upstream_gates",
            return_value={},
        ):
            return transition_bom_version(
                object_id=self.version.pk,
                target_status="reviewed",
                action=REVIEW_ACTION,
                user=self.reviewer,
                reason=reason,
                idempotency_key=key,
            )

    def release(self, *, user=None, key="release-request-1", reason="正式发布"):
        with patch(
            "pde.bom_version_control_service._require_actor",
            side_effect=self.actor,
        ), patch(
            "pde.bom_version_control_service._assert_upstream_gates",
            return_value={},
        ):
            return transition_bom_version(
                object_id=self.version.pk,
                target_status="released",
                action=RELEASE_ACTION,
                user=user or self.releaser,
                reason=reason,
                idempotency_key=key,
            )

    def test_01_draft_cannot_release_directly(self):
        with self.assertRaises(BomVersionControlError) as caught:
            self.release()
        self.assertEqual(caught.exception.code, "BOM_VERSION_STATE_CONFLICT")
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, "draft")

    def test_02_draft_cannot_be_reviewed_when_workflow_decision_write_fails(self):
        with patch(
            "pde.bom_version_control_service._require_actor",
            side_effect=self.actor,
        ), patch(
            "pde.bom_version_control_service._assert_upstream_gates",
            return_value={},
        ), patch(
            "pde.bom_version_control_service.ApprovalDecision.objects.create",
            side_effect=RuntimeError("decision unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                transition_bom_version(
                    object_id=self.version.pk,
                    target_status="reviewed",
                    user=self.reviewer,
                    reason="评审",
                    idempotency_key="review-no-decision",
                )
        self.version.refresh_from_db()
        self.assertEqual((self.version.status, self.version.approval_state), ("draft", "not_submitted"))
        self.assertEqual(WorkflowInstance.objects.count(), 0)

    def test_03_approved_formal_review_allows_draft_to_reviewed(self):
        result = self.review()
        self.version.refresh_from_db()
        self.assertEqual((self.version.status, self.version.approval_state), ("reviewed", APPROVED_PROJECTION))
        self.assertEqual(result["workflow"]["statusCode"], "approved")
        self.assertEqual(ApprovalDecision.objects.get().decision, "approved")

        def eligible(company_id, version_id, permission_code):
            self.assertEqual(company_id, self.company.pk)
            self.assertEqual(version_id, self.version.pk)
            if permission_code == REVIEW_PERMISSION:
                return [self.actor_contexts[self.reviewer.pk]]
            return [self.actor_contexts[self.releaser.pk]]

        with patch(
            "pde.bom_version_control_service.eligible_action_actors",
            side_effect=eligible,
        ):
            readiness = control_chain_readiness(self.version)
        self.assertEqual(
            readiness["currentBusinessAction"],
            "正式评审已完成，等待独立发布授权",
        )

    def test_04_reviewed_without_release_permission_is_denied(self):
        self.review()
        denied = BomVersionControlError("PERMISSION_DENIED", "denied", 403)
        with patch("pde.bom_version_control_service._require_actor", side_effect=denied):
            with self.assertRaises(BomVersionControlError) as caught:
                transition_bom_version(
                    object_id=self.version.pk,
                    target_status="released",
                    user=self.releaser,
                    reason="发布",
                    idempotency_key="release-denied",
                )
        self.assertEqual(caught.exception.http_status, 403)

    def test_05_reviewed_without_workflow_approval_is_denied(self):
        BOMVersion.objects.filter(pk=self.version.pk).update(status="reviewed")
        self.version.refresh_from_db()
        with self.assertRaises(BomVersionControlError) as caught:
            self.release()
        self.assertEqual(caught.exception.code, "BOM_VERSION_FORMAL_REVIEW_NOT_APPROVED")

    def test_06_same_review_and_release_actor_fails_closed(self):
        self.review()
        with self.assertRaises(BomVersionControlError) as caught:
            self.release(user=self.reviewer)
        self.assertEqual(caught.exception.code, "BOM_VERSION_SEGREGATION_OF_DUTIES_FAILED")

    def test_07_distinct_qualified_actor_can_release(self):
        self.review()
        result = self.release()
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, "released")
        self.assertEqual(result["businessStateTransition"]["actorId"], self.releaser.pk)

    def test_08_each_successful_transition_writes_one_bst(self):
        self.review()
        self.assertEqual(BusinessStateTransition.objects.count(), 1)
        self.release()
        self.assertEqual(BusinessStateTransition.objects.count(), 2)

    def test_09_each_successful_action_writes_one_audit(self):
        self.review()
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 1)
        self.release()
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 2)

    def test_10_request_identity_is_persisted_and_linked(self):
        result = self.review(key="request-identity-exact")
        ledger = MasterDataWriteRequest.objects.get()
        self.assertEqual(ledger.idempotency_key, "request-identity-exact")
        self.assertEqual(ledger.result["requestIdentity"], "request-identity-exact")
        self.assertEqual(result["writeRequestId"], ledger.pk)

    def test_11_same_request_replay_does_not_duplicate_writes(self):
        first = self.review(key="review-replay")
        second = self.review(key="review-replay")
        self.assertFalse(first["idempotentReplay"])
        self.assertTrue(second["idempotentReplay"])
        self.assertEqual(ApprovalDecision.objects.count(), 1)
        self.assertEqual(BusinessStateTransition.objects.count(), 1)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 1)
        self.assertEqual(MasterDataWriteRequest.objects.count(), 1)

    def test_12_same_request_identity_with_different_payload_conflicts(self):
        self.review(key="payload-conflict", reason="原因A")
        with self.assertRaises(BomVersionControlError) as caught:
            self.review(key="payload-conflict", reason="原因B")
        self.assertEqual(caught.exception.code, "IDEMPOTENCY_PAYLOAD_CONFLICT")

    def test_13_network_interruption_retry_reads_original_result(self):
        first = self.review(key="network-retry")
        replay = self.review(key="network-retry")
        self.assertEqual(first["businessStateTransition"]["id"], replay["businessStateTransition"]["id"])
        self.assertEqual(first["workflow"]["decisionId"], replay["workflow"]["decisionId"])

    def test_14_changed_upstream_gate_blocks_transition(self):
        blocked = BomVersionControlError(
            "BOM_VERSION_UPSTREAM_GATE_BLOCKED", "changed", 422,
        )
        with patch(
            "pde.bom_version_control_service._require_actor",
            side_effect=self.actor,
        ), patch(
            "pde.bom_version_control_service._assert_upstream_gates",
            side_effect=blocked,
        ):
            with self.assertRaises(BomVersionControlError) as caught:
                transition_bom_version(
                    object_id=self.version.pk,
                    target_status="reviewed",
                    user=self.reviewer,
                    reason="评审",
                    idempotency_key="gate-changed",
                )
        self.assertEqual(caught.exception.http_status, 422)

    def test_15_competing_version_gate_blocks_release(self):
        self.review()
        blocked = BomVersionControlError(
            "BOM_VERSION_UPSTREAM_GATE_BLOCKED",
            "competing version",
            422,
            {"failedGates": [{"code": "NO_COMPETING_VERSION"}]},
        )
        with patch(
            "pde.bom_version_control_service._require_actor",
            side_effect=self.actor,
        ), patch(
            "pde.bom_version_control_service._assert_upstream_gates",
            side_effect=blocked,
        ):
            with self.assertRaises(BomVersionControlError) as caught:
                transition_bom_version(
                    object_id=self.version.pk,
                    target_status="released",
                    user=self.releaser,
                    reason="发布",
                    idempotency_key="competing-version",
                )
        self.assertEqual(caught.exception.details["failedGates"][0]["code"], "NO_COMPETING_VERSION")

    def test_16_concurrent_current_state_change_fails_closed(self):
        self.review()
        BOMVersion.objects.filter(pk=self.version.pk).update(status="released")
        with self.assertRaises(BomVersionControlError) as caught:
            self.release(key="stale-current-state")
        self.assertEqual(caught.exception.code, "BOM_VERSION_STATE_CONFLICT")

    def test_17_approval_state_matches_workflow_authority(self):
        self.review()
        self.version.refresh_from_db()
        workflow = WorkflowInstance.objects.get(document_id=self.version.pk)
        self.assertEqual(workflow.status, "approved")
        self.assertEqual(self.version.approval_state, APPROVED_PROJECTION)

    def test_18_release_actor_and_time_read_from_authoritative_ledgers(self):
        self.review()
        self.release(key="release-readback")
        self.version.refresh_from_db()
        facts = release_readback(self.version)
        self.assertTrue(facts["released"])
        self.assertEqual(facts["actorId"], self.releaser.pk)
        self.assertEqual(facts["actorRealName"], "发布人")
        self.assertTrue(facts["occurredAt"])
        self.assertEqual(facts["requestIdentity"], "release-readback")
        self.assertEqual(facts["actionCode"], RELEASE_ACTION)
        self.assertEqual(facts["decisionCode"], "released")
        self.assertTrue(facts["workflowInstanceNo"].startswith("WFI-BOM-"))

    def test_19_engineering_document_and_version_are_not_modified(self):
        before = (EngineeringDocument.objects.count(), EngineeringDocumentVersion.objects.count())
        self.review()
        self.release()
        self.assertEqual(before, (EngineeringDocument.objects.count(), EngineeringDocumentVersion.objects.count()))

    def test_20_manufacturing_output_remains_zero(self):
        self.review()
        self.release()
        self.assertEqual(ProductManufacturingOutput.objects.count(), 0)

    def test_21_mrp_and_ecn_are_not_triggered(self):
        before_ecn = EngineeringChangeNotice.objects.count()
        self.review()
        self.release()
        self.assertEqual(EngineeringChangeNotice.objects.count(), before_ecn)
        self.assertFalse(any(
            "mrp" in code.lower()
            for code in MasterDataWriteRequest.objects.values_list("action_code", flat=True)
        ))

    def test_missing_template_is_configuration_blocker_and_creates_nothing(self):
        self.definition.nodes.all().delete()
        self.definition.delete()
        readiness = control_chain_readiness(self.version)
        self.assertEqual(readiness["workflowRuntime"]["statusCode"], "BLOCKED")
        self.assertEqual(
            readiness["workflowRuntime"]["blocker"]["code"],
            "BOM_VERSION_WORKFLOW_TEMPLATE_MISSING",
        )
        self.assertEqual(WorkflowInstance.objects.count(), 0)
        self.assertEqual(ExternalIdentity.objects.count(), 0)

    def test_action_and_target_must_match(self):
        with self.assertRaises(BomVersionControlError) as caught:
            transition_bom_version(
                object_id=self.version.pk,
                target_status="reviewed",
                action=RELEASE_ACTION,
                user=self.reviewer,
                reason="错误动作",
                idempotency_key="action-target-conflict",
            )
        self.assertEqual(caught.exception.code, "BOM_VERSION_ACTION_TARGET_CONFLICT")

    def test_request_identity_is_required(self):
        with self.assertRaises(BomVersionControlError) as caught:
            transition_bom_version(
                object_id=self.version.pk,
                target_status="reviewed",
                user=self.reviewer,
                reason="缺少请求身份",
                idempotency_key="",
            )
        self.assertEqual(caught.exception.code, "IDEMPOTENCY_KEY_REQUIRED")

    def _api_response(self, side_effect):
        request = APIRequestFactory().post(
            f"/api/pde/a1-engineering/bom-versions/{self.version.pk}/transition/",
            {"targetStatus": "reviewed", "reason": "评审"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="api-status-test",
        )
        force_authenticate(request, user=self.reviewer)
        with patch.object(EngineeringLifecycleService, "transition", side_effect=side_effect):
            return EngineeringLifecycleView.as_view()(
                request, entity="bom-versions", object_id=self.version.pk,
            )

    def test_api_maps_state_and_idempotency_conflicts_to_409(self):
        response = self._api_response(
            BomVersionControlError("IDEMPOTENCY_PAYLOAD_CONFLICT", "conflict", 409)
        )
        self.assertEqual(response.status_code, 409)

    def test_api_maps_permission_and_scope_to_403(self):
        response = self._api_response(
            BomVersionControlError("PERMISSION_DENIED", "denied", 403)
        )
        self.assertEqual(response.status_code, 403)

    def test_api_maps_workflow_gate_and_sod_to_422(self):
        response = self._api_response(
            BomVersionControlError("BOM_VERSION_WORKFLOW_TEMPLATE_MISSING", "blocked", 422)
        )
        self.assertEqual(response.status_code, 422)

    def test_api_maps_control_dependency_failure_to_503_without_fallback(self):
        response = self._api_response(DatabaseError("unavailable"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "BOM_VERSION_CONTROL_DEPENDENCY_UNAVAILABLE")

