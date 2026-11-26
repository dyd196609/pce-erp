from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from masterdata.models import MasterDataWriteRequest
from pfm.models import Employee
from system.models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    Permission,
    Position,
    PositionResponsibility,
    PositionWorkflowResponsibility,
    Process,
    Responsibility,
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
)

from .engineering_document_version_permission_catalog import (
    ensure_engineering_document_version_permission_catalog,
)
from .engineering_document_version_review_service import (
    REVIEW_ACTION,
    EngineeringDocumentVersionReviewError,
    eligible_review_actors,
    project_review_preflight,
    review_engineering_document_version,
)
from .engineering_document_version_workflow_catalog import CANONICAL_DEFINITION
from .models import (
    BOMVersion,
    EngineeringDocument,
    EngineeringDocumentVersion,
    ProductBOM,
    ProductDefinition,
    ProductVersion,
    Routing,
    RoutingStep,
    RoutingVersion,
)
from .production_foundation_service import EngineeringLifecycleService


class EngineeringDocumentVersionReviewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(code="EDV-REVIEW", name="工程资料评审测试公司")
        self.department = Department.objects.create(
            company=self.company,
            code="DESIGN",
            name="设计部",
        )
        self.position = Position.objects.create(
            company=self.company,
            department=self.department,
            code="DESIGN-MGR",
            name="设计经理",
        )
        self.responsibility = Responsibility.objects.create(
            code="RESP_EDV_REVIEW_TEST",
            name="工程资料版本正式评审",
            status=Responsibility.Status.ACTIVE,
            is_active=True,
        )
        PositionResponsibility.objects.create(
            position=self.position,
            responsibility=self.responsibility,
            active=True,
        )
        self.reviewer = User.objects.create_user(
            username="edv-reviewer",
            password="x",
            real_name="工程资料评审人",
            company_id=self.company.pk,
        )
        Employee.objects.create(
            user=self.reviewer,
            employee_no="EMP-EDV-REVIEW",
            full_name="工程资料评审人",
            status="active",
            department_ref=self.department,
            position_ref=self.position,
        )

        product = ProductDefinition.objects.create(
            company=self.company,
            product_code="EDV-PRODUCT",
            product_name="测试产品",
            emd_material_code="EDV-FG",
        )
        product_version = ProductVersion.objects.create(
            product=product,
            version_no="V1.0",
        )
        bom = ProductBOM.objects.create(
            company=self.company,
            product=product,
            bom_code="EDV-BOM",
            name="测试BOM",
        )
        bom_version = BOMVersion.objects.create(
            bom=bom,
            product=product,
            product_version=product_version,
            bom_version="V1.0",
            status="released",
        )
        routing = Routing.objects.create(
            company=self.company,
            product=product,
            routing_code="EDV-ROUTING",
            name="测试工艺路线",
            status="released",
        )
        routing_version = RoutingVersion.objects.create(
            routing=routing,
            product=product,
            product_version=product_version,
            routing_version="V1.0",
            status="draft",
        )
        operation = Process.objects.create(
            company=self.company,
            code="EDV-OP-001",
            name="工程资料评审测试工序",
        )
        RoutingStep.objects.create(
            routing_version=routing_version,
            sequence=1,
            operation=operation,
            standard_hours=Decimal("1.2500"),
            setup_hours=Decimal("0.2500"),
            transfer_hours=Decimal("0.1250"),
        )
        routing_version.status = "released"
        routing_version.save(update_fields=["status"])
        document = EngineeringDocument.objects.create(
            document_no="EDV-DOC-001",
            document_name="测试工程资料",
            document_type="technical",
            product=product,
            product_bom=bom,
            routing=routing,
        )
        self.version = EngineeringDocumentVersion.objects.create(
            document=document,
            document_name="测试工程资料",
            document_version="V1.0",
            product_version=product_version,
            related_product=product,
            related_bom=bom_version,
            related_routing=routing_version,
        )

        ensure_engineering_document_version_permission_catalog()
        permission = Permission.objects.get(code=REVIEW_ACTION)
        self.role = Role.objects.create(code="edv-review-role", name="工程资料版本正式评审员")
        RolePermission.objects.create(role=self.role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=self.reviewer,
            role=self.role,
            organization=self.company,
            scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            active=True,
            business_hash="e" * 64,
        )
        definition = ProcessDefinition.objects.get(
            definition_code=CANONICAL_DEFINITION["definition_code"],
        )
        node = definition.nodes.get()
        self.mapping = PositionWorkflowResponsibility.objects.create(
            position=self.position,
            responsibility=self.responsibility,
            workflow_node=node,
            workflow_code=definition.definition_code,
            node_code=node.node_code,
            ownership_type=PositionWorkflowResponsibility.OwnershipType.REVIEWER,
            active=True,
        )
        self.completeness = {
            "complete": True,
            "gates": [{
                "code": "TEST_EXACT_SOURCE_CHAIN",
                "label": "准确测试来源链",
                "statusCode": "PASS",
                "statusLabel": "通过",
                "evidence": "测试来源链完整",
                "details": {},
            }],
            "routingStepCount": 28,
            "exactChain": {},
            "manufacturingOutputCount": 0,
        }

    def review(self, key="edv-review-1", reason="工程资料版本V1.0评审通过"):
        with patch(
            "pde.engineering_document_version_review_service.project_source_completeness",
            return_value=self.completeness,
        ):
            return review_engineering_document_version(
                object_id=self.version.pk,
                user=self.reviewer,
                reason=reason,
                idempotency_key=key,
                action=REVIEW_ACTION,
            )

    def test_catalog_is_idempotent_and_does_not_grant_personnel_authority(self):
        role_count = Role.objects.count()
        assignment_count = UserRoleScopeAssignment.objects.count()
        first = ensure_engineering_document_version_permission_catalog()
        second = ensure_engineering_document_version_permission_catalog()
        self.assertEqual(first["existingPermissions"], [REVIEW_ACTION])
        self.assertEqual(second["existingPermissions"], [REVIEW_ACTION])
        self.assertEqual(Role.objects.count(), role_count)
        self.assertEqual(UserRoleScopeAssignment.objects.count(), assignment_count)
        self.assertEqual(first["userAuthorityWrites"], 0)

    def test_complete_responsibility_chain_resolves_non_admin_reviewer(self):
        actors = eligible_review_actors(self.version)
        self.assertEqual([row["userId"] for row in actors], [self.reviewer.pk])
        self.assertEqual(actors[0]["workflowResponsibilityId"], self.mapping.pk)
        self.assertEqual(actors[0]["ownershipType"], "REVIEWER")
        self.assertEqual(actors[0]["responsibilityCode"], self.responsibility.code)

    def test_missing_workflow_responsibility_blocks_actor_resolution(self):
        self.mapping.active = False
        self.mapping.save(update_fields=["active"])
        self.assertEqual(eligible_review_actors(self.version), [])

    def test_preflight_is_read_only_and_separates_current_browser_actor(self):
        before = (
            WorkflowInstance.objects.count(),
            ApprovalDecision.objects.count(),
            BusinessStateTransition.objects.count(),
            OrganizationOperatingAuditRecord.objects.count(),
            MasterDataWriteRequest.objects.count(),
        )
        with patch(
            "pde.engineering_document_version_review_service.project_source_completeness",
            return_value=self.completeness,
        ):
            facts = project_review_preflight(self.version, self.reviewer)
        self.assertTrue(facts["readyForHumanReview"])
        self.assertTrue(facts["reviewAllowed"])
        self.assertTrue(facts["currentBrowserOperable"])
        self.assertEqual(before, (
            WorkflowInstance.objects.count(),
            ApprovalDecision.objects.count(),
            BusinessStateTransition.objects.count(),
            OrganizationOperatingAuditRecord.objects.count(),
            MasterDataWriteRequest.objects.count(),
        ))

    def test_formal_review_writes_shared_ledgers_without_release(self):
        result = self.review()
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, "reviewed")
        self.assertEqual(WorkflowInstance.objects.count(), 1)
        self.assertEqual(ApprovalTask.objects.count(), 1)
        self.assertEqual(ApprovalDecision.objects.count(), 1)
        self.assertEqual(BusinessStateTransition.objects.count(), 1)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 1)
        self.assertEqual(MasterDataWriteRequest.objects.count(), 1)
        self.assertEqual(result["workflow"]["statusCode"], "approved")
        self.assertFalse(result["engineeringDocumentReleaseExecuted"])
        self.assertFalse(result["manufacturingReleaseExecuted"])

    def test_idempotent_retry_does_not_duplicate_review_facts(self):
        first = self.review(key="edv-review-replay")
        second = self.review(key="edv-review-replay")
        self.assertFalse(first["idempotentReplay"])
        self.assertTrue(second["idempotentReplay"])
        self.assertEqual(ApprovalDecision.objects.count(), 1)
        self.assertEqual(BusinessStateTransition.objects.count(), 1)

    def test_unassigned_user_and_superuser_cannot_bypass(self):
        unassigned = User.objects.create_user(
            username="edv-unassigned",
            password="x",
            company_id=self.company.pk,
        )
        admin = User.objects.create_superuser(
            username="edv-admin",
            password="x",
            company_id=self.company.pk,
        )
        for actor in (unassigned, admin):
            with self.assertRaises(EngineeringDocumentVersionReviewError) as caught:
                with patch(
                    "pde.engineering_document_version_review_service.project_source_completeness",
                    return_value=self.completeness,
                ):
                    review_engineering_document_version(
                        object_id=self.version.pk,
                        user=actor,
                        reason="不得绕过",
                        idempotency_key=f"edv-denied-{actor.pk}",
                        action=REVIEW_ACTION,
                    )
            self.assertEqual(caught.exception.code, "PERMISSION_DENIED")
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, "draft")
        self.assertEqual(WorkflowInstance.objects.count(), 0)

    def test_generic_lifecycle_delegates_draft_to_reviewed(self):
        with patch(
            "pde.engineering_document_version_review_service.review_engineering_document_version",
            return_value={"delegated": True},
        ) as delegated:
            result = EngineeringLifecycleService.transition(
                "engineering-document-versions",
                object_id=self.version.pk,
                target_status="reviewed",
                user=self.reviewer,
                reason="正式评审",
                idempotency_key="edv-generic-delegation",
                action=REVIEW_ACTION,
            )
        self.assertTrue(result["delegated"])
        delegated.assert_called_once()

    def test_http_success_contract_contains_committed_workflow_and_transition(self):
        self.client.force_authenticate(user=self.reviewer)
        with patch(
            "pde.engineering_document_version_review_service.project_source_completeness",
            return_value=self.completeness,
        ):
            response = self.client.post(
                f"/api/pde/engineering-document-versions/{self.version.pk}/review/",
                {
                    "action": REVIEW_ACTION,
                    "reason": "HTTP合同评审通过",
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY="edv-http-success",
            )
        self.assertEqual(response.status_code, 200)
        result = response.data["result"]
        self.assertEqual(result["engineeringDocumentVersion"]["status"], "reviewed")
        self.assertEqual(result["workflow"]["statusCode"], "approved")
        self.assertEqual(result["businessStateTransition"]["fromState"], "draft")
        self.assertEqual(result["businessStateTransition"]["toState"], "reviewed")
        self.assertGreater(result["auditId"], 0)
        self.assertGreater(result["writeRequestId"], 0)

    def test_http_success_persists_decimal_routing_step_snapshot(self):
        self.client.force_authenticate(user=self.reviewer)
        with patch(
            "pde.engineering_document_version_review_service.project_source_completeness",
            return_value=self.completeness,
        ):
            response = self.client.post(
                f"/api/pde/engineering-document-versions/{self.version.pk}/review/",
                {
                    "action": REVIEW_ACTION,
                    "reason": "包含Decimal工时的正式评审",
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY="edv-http-decimal-snapshot",
            )
        self.assertEqual(response.status_code, 200)
        audit = OrganizationOperatingAuditRecord.objects.get(pk=response.data["result"]["auditId"])
        step = audit.after_snapshot["reviewContentSnapshot"]["routingSteps"][0]
        self.assertEqual(step["standard_hours"], "1.2500")
        self.assertEqual(step["setup_hours"], "0.2500")
        self.assertEqual(step["transfer_hours"], "0.1250")
        self.assertEqual(ApprovalDecision.objects.get().comment, "包含Decimal工时的正式评审")

    def test_http_failure_contract_preserves_error_code_and_rolls_back(self):
        outsider = User.objects.create_user(
            username="edv-http-outsider",
            password="x",
            company_id=self.company.pk,
        )
        self.client.force_authenticate(user=outsider)
        with patch(
            "pde.engineering_document_version_review_service.project_source_completeness",
            return_value=self.completeness,
        ):
            response = self.client.post(
                f"/api/pde/engineering-document-versions/{self.version.pk}/review/",
                {"action": REVIEW_ACTION, "reason": "不得越权"},
                format="json",
                HTTP_IDEMPOTENCY_KEY="edv-http-denied",
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "PERMISSION_DENIED")
        self.assertIn("完整责任链", response.data["error"]["message"])
        self.assertEqual(response.data["databaseBusinessWriteCount"], 0)
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, "draft")
        self.assertEqual(WorkflowInstance.objects.count(), 0)
        self.assertEqual(MasterDataWriteRequest.objects.count(), 0)

    def test_http_validation_and_conflict_contracts_return_business_errors(self):
        self.client.force_authenticate(user=self.reviewer)
        missing_reason = self.client.post(
            f"/api/pde/engineering-document-versions/{self.version.pk}/review/",
            {"action": REVIEW_ACTION, "reason": ""},
            format="json",
            HTTP_IDEMPOTENCY_KEY="edv-http-no-reason",
        )
        self.assertEqual(missing_reason.status_code, 422)
        self.assertEqual(
            missing_reason.data["error"]["code"],
            "ENGINEERING_DOCUMENT_VERSION_REVIEW_REASON_REQUIRED",
        )

        self.version.status = "reviewed"
        self.version.save(update_fields=["status"])
        state_conflict = self.client.post(
            f"/api/pde/engineering-document-versions/{self.version.pk}/review/",
            {"action": REVIEW_ACTION, "reason": "重复提交"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="edv-http-state-conflict",
        )
        self.assertEqual(state_conflict.status_code, 409)
        self.assertEqual(
            state_conflict.data["error"]["code"],
            "ENGINEERING_DOCUMENT_VERSION_STATE_CONFLICT",
        )
        self.assertEqual(MasterDataWriteRequest.objects.count(), 0)
