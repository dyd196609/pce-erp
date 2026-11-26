from unittest.mock import patch

from django.test import TestCase

from masterdata.models import MasterDataWriteRequest
from system.models import (
    Company,
    OrganizationOperatingAuditRecord,
    Permission,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)
from workflow_runtime.models import (
    ApprovalDecision,
    ApprovalTask,
    BusinessStateTransition,
    ProcessDefinition,
    WorkflowInstance,
    WorkflowNodeDefinition,
)

from .models import ManufacturingProcessType, ProductCategory, Routing, RoutingVersion
from .production_foundation_service import EngineeringLifecycleService, ProductionFoundationError
from .routing_version_permission_catalog import ensure_routing_version_permission_catalog
from .routing_version_workflow_catalog import (
    CANONICAL_DEFINITION,
    CANONICAL_NODE,
    ensure_routing_version_workflow_catalog,
)
from .routing_version_review_service import (
    APPROVED_PROJECTION,
    REVIEW_ACTION,
    REVIEW_PERMISSION,
    RoutingVersionReviewError,
    project_review_preflight,
    review_routing_version,
)
from .routing_version_release_service import RELEASE_PERMISSION


class RoutingVersionPermissionCatalogTests(TestCase):
    def test_catalog_registers_permission_and_system_workflow_without_authority(self):
        role_count = Role.objects.count()
        role_permission_count = RolePermission.objects.count()
        assignment_count = UserRoleScopeAssignment.objects.count()

        first = ensure_routing_version_permission_catalog()
        second = ensure_routing_version_permission_catalog()

        self.assertEqual(first["createdPermissions"], sorted([REVIEW_PERMISSION, RELEASE_PERMISSION]))
        self.assertEqual(second["existingPermissions"], sorted([REVIEW_PERMISSION, RELEASE_PERMISSION]))
        self.assertTrue(first["workflowTemplate"]["created"])
        self.assertFalse(second["workflowTemplate"]["created"])
        definition = ProcessDefinition.objects.get(
            definition_code=CANONICAL_DEFINITION["definition_code"],
        )
        node = definition.nodes.get()
        self.assertEqual(definition.document_type, "RoutingVersion")
        self.assertEqual(node.node_code, CANONICAL_NODE["node_code"])
        self.assertEqual(node.business_action_code, REVIEW_PERMISSION)
        self.assertEqual(len(definition.definition_hash), 64)
        self.assertEqual(first["workflowTemplate"]["sourceCode"], "SYSTEM_CATALOG")
        self.assertEqual(WorkflowInstance.objects.count(), 0)
        self.assertEqual(ApprovalTask.objects.count(), 0)
        self.assertEqual(ApprovalDecision.objects.count(), 0)
        self.assertEqual(BusinessStateTransition.objects.count(), 0)
        self.assertEqual(Role.objects.count(), role_count)
        self.assertEqual(RolePermission.objects.count(), role_permission_count)
        self.assertEqual(UserRoleScopeAssignment.objects.count(), assignment_count)

    def test_catalog_refuses_conflicting_active_routing_workflow(self):
        Permission.objects.create(
            code=REVIEW_PERMISSION,
            name="工艺路线版本正式评审",
            module="PDE",
        )
        ProcessDefinition.objects.create(
            definition_code="OTHER_ROUTING_VERSION_REVIEW",
            definition_name="冲突流程",
            business_domain="PDE",
            document_type="RoutingVersion",
            version=1,
            active=True,
            definition_hash="x" * 64,
        )
        with self.assertRaisesMessage(ValueError, "双重权威"):
            ensure_routing_version_workflow_catalog()
        self.assertFalse(ProcessDefinition.objects.filter(
            definition_code=CANONICAL_DEFINITION["definition_code"],
        ).exists())


class RoutingVersionReviewTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="RT01", name="路线评审测试公司")
        self.reviewer = User.objects.create_user(
            username="routing-reviewer",
            password="x",
            real_name="路线评审人",
            company_id=self.company.pk,
        )
        self.product_category = ProductCategory.objects.create(
            company=self.company,
            code="CAT-REVIEW",
            name="路线评审测试分类",
        )
        self.process_type = ManufacturingProcessType.objects.create(
            company=self.company,
            code="PROC-REVIEW",
            name="路线评审测试工艺",
        )
        self.routing = Routing.objects.create(
            company=self.company,
            routing_code="RT-REVIEW",
            name="路线评审测试",
            applicability_scope="PRODUCT_CATEGORY",
            product_category=self.product_category,
            manufacturing_process_type=self.process_type,
            status="released",
        )
        self.version = RoutingVersion.objects.create(
            routing=self.routing,
            routing_version="V2.0",
            revision=2,
            status="draft",
            approval_state="not_submitted",
        )
        Permission.objects.create(
            code=REVIEW_PERMISSION,
            name="工艺路线版本正式评审",
            module="PDE",
        )
        self.definition = ProcessDefinition.objects.create(
            definition_code="ROUTING_VERSION_REVIEW_TEST",
            definition_name="工艺路线版本正式评审",
            business_domain="PDE",
            document_type="RoutingVersion",
            version=1,
            active=True,
            definition_hash="r" * 64,
        )
        WorkflowNodeDefinition.objects.create(
            process_definition=self.definition,
            node_code="REVIEW_ROUTING_VERSION",
            node_name="评审工艺路线版本",
            sequence=1,
            business_action_code=REVIEW_PERMISSION,
            active=True,
        )
        self.actor = {
            "userId": self.reviewer.pk,
            "username": self.reviewer.username,
            "realName": self.reviewer.real_name,
            "matchedRoleCodes": ["routing_version_reviewer"],
            "positionCode": "GYB-MGR",
        }
        self.completeness = {
            "complete": True,
            "gates": [{
                "code": "TEST_COMPLETE",
                "label": "测试完整性",
                "statusCode": "PASS",
                "statusLabel": "通过",
                "evidence": "完整",
                "details": {},
            }],
            "stepCount": 28,
            "contextCount": 1,
            "sourceRoutingVersionId": 31,
            "applicabilityRows": [],
        }

    def review(self, key="routing-review-1", reason="路线结构与适用性评审通过"):
        with patch(
            "pde.routing_version_review_service.eligible_review_actors",
            return_value=[self.actor],
        ), patch(
            "pde.routing_version_review_service.project_draft_completeness",
            return_value=self.completeness,
        ):
            return review_routing_version(
                object_id=self.version.pk,
                user=self.reviewer,
                reason=reason,
                idempotency_key=key,
                action=REVIEW_ACTION,
            )

    def test_formal_review_writes_shared_workflow_and_reviewed_projection(self):
        result = self.review()
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, "reviewed")
        self.assertEqual(self.version.approval_state, APPROVED_PROJECTION)
        self.assertEqual(WorkflowInstance.objects.count(), 1)
        self.assertEqual(ApprovalTask.objects.count(), 1)
        self.assertEqual(ApprovalDecision.objects.count(), 1)
        self.assertEqual(BusinessStateTransition.objects.count(), 1)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 1)
        self.assertEqual(MasterDataWriteRequest.objects.count(), 1)
        self.assertEqual(result["workflow"]["statusCode"], "approved")
        self.assertEqual(result["businessStateTransition"]["toState"], "reviewed")

    def test_idempotent_retry_does_not_duplicate_formal_facts(self):
        first = self.review(key="routing-review-replay")
        second = self.review(key="routing-review-replay")
        self.assertFalse(first["idempotentReplay"])
        self.assertTrue(second["idempotentReplay"])
        self.assertEqual(ApprovalDecision.objects.count(), 1)
        self.assertEqual(BusinessStateTransition.objects.count(), 1)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 1)
        self.assertEqual(MasterDataWriteRequest.objects.count(), 1)

    def test_different_payload_on_same_request_identity_is_rejected(self):
        self.review(key="routing-review-conflict", reason="意见A")
        with self.assertRaises(RoutingVersionReviewError) as caught:
            self.review(key="routing-review-conflict", reason="意见B")
        self.assertEqual(caught.exception.code, "IDEMPOTENCY_PAYLOAD_CONFLICT")

    def test_workflow_failure_rolls_back_all_review_writes(self):
        with patch(
            "pde.routing_version_review_service.eligible_review_actors",
            return_value=[self.actor],
        ), patch(
            "pde.routing_version_review_service.project_draft_completeness",
            return_value=self.completeness,
        ), patch(
            "pde.routing_version_review_service.ApprovalDecision.objects.create",
            side_effect=RuntimeError("decision unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                review_routing_version(
                    object_id=self.version.pk,
                    user=self.reviewer,
                    reason="评审",
                    idempotency_key="routing-review-rollback",
                )
        self.version.refresh_from_db()
        self.assertEqual((self.version.status, self.version.approval_state), ("draft", "not_submitted"))
        self.assertEqual(WorkflowInstance.objects.count(), 0)
        self.assertEqual(MasterDataWriteRequest.objects.count(), 0)

    def test_missing_template_blocks_without_changing_version(self):
        WorkflowNodeDefinition.objects.filter(process_definition=self.definition).delete()
        self.definition.delete()
        with patch(
            "pde.routing_version_review_service.eligible_review_actors",
            return_value=[self.actor],
        ), patch(
            "pde.routing_version_review_service.project_draft_completeness",
            return_value=self.completeness,
        ):
            with self.assertRaises(RoutingVersionReviewError) as caught:
                review_routing_version(
                    object_id=self.version.pk,
                    user=self.reviewer,
                    reason="评审",
                    idempotency_key="routing-review-no-template",
                )
        self.assertEqual(caught.exception.code, "ROUTING_VERSION_WORKFLOW_TEMPLATE_MISSING")
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, "draft")

    def test_preflight_is_read_only(self):
        before = (
            WorkflowInstance.objects.count(),
            ApprovalDecision.objects.count(),
            BusinessStateTransition.objects.count(),
            OrganizationOperatingAuditRecord.objects.count(),
            MasterDataWriteRequest.objects.count(),
        )
        with patch(
            "pde.routing_version_review_service.eligible_review_actors",
            return_value=[self.actor],
        ), patch(
            "pde.routing_version_review_service.project_draft_completeness",
            return_value=self.completeness,
        ):
            facts = project_review_preflight(self.version, self.reviewer)
        self.assertTrue(facts["reviewAllowed"])
        self.assertEqual(before, (
            WorkflowInstance.objects.count(),
            ApprovalDecision.objects.count(),
            BusinessStateTransition.objects.count(),
            OrganizationOperatingAuditRecord.objects.count(),
            MasterDataWriteRequest.objects.count(),
        ))

    def test_generic_lifecycle_delegates_review_and_blocks_release(self):
        with patch(
            "pde.routing_version_review_service.review_routing_version",
            return_value={"delegated": True},
        ) as delegated:
            result = EngineeringLifecycleService.transition(
                "routing-versions",
                object_id=self.version.pk,
                target_status="reviewed",
                user=self.reviewer,
                reason="评审",
                idempotency_key="generic-delegation",
                action=REVIEW_ACTION,
            )
        self.assertTrue(result["delegated"])
        delegated.assert_called_once()
        with self.assertRaises(ProductionFoundationError) as caught:
            EngineeringLifecycleService.transition(
                "routing-versions",
                object_id=self.version.pk,
                target_status="released",
                user=self.reviewer,
                reason="不得发布",
            )
        self.assertEqual(caught.exception.code, "ROUTING_VERSION_DEDICATED_CONTROL_REQUIRED")

