import inspect
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
    Responsibility,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)
from workflow_runtime.models import ApprovalDecision, BusinessStateTransition

from .engineering_document_version_permission_catalog import (
    ensure_engineering_document_version_permission_catalog,
)
from .engineering_document_version_release_service import (
    RELEASE_ACTION,
    EngineeringDocumentVersionReleaseError,
    eligible_release_actors,
    project_release_preflight,
    release_engineering_document_version,
)
from .engineering_document_version_review_service import (
    REVIEW_ACTION,
    review_engineering_document_version,
)
from .models import (
    BOMVersion,
    EngineeringDocument,
    EngineeringDocumentVersion,
    ProductBOM,
    ProductDefinition,
    ProductManufacturingOutput,
    ProductVersion,
    Routing,
    RoutingStep,
    RoutingVersion,
)
from .production_foundation_service import EngineeringLifecycleService
from system.models import Process


class EngineeringDocumentVersionReleaseTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(code="EDV-REL", name="工程资料发布测试公司")
        review_department = Department.objects.create(
            company=self.company, code="DESIGN", name="设计部",
        )
        review_position = Position.objects.create(
            company=self.company,
            department=review_department,
            code="DESIGN-MGR",
            name="设计经理",
        )
        review_responsibility = Responsibility.objects.create(
            code="RESP_EDV_RELEASE_TEST_REVIEW",
            name="工程资料版本正式评审",
            status=Responsibility.Status.ACTIVE,
            is_active=True,
        )
        PositionResponsibility.objects.create(
            position=review_position,
            responsibility=review_responsibility,
            active=True,
        )
        self.reviewer = User.objects.create_user(
            username="edv-release-reviewer",
            password="x",
            real_name="工程资料评审人",
            company_id=self.company.pk,
        )
        Employee.objects.create(
            user=self.reviewer,
            employee_no="EMP-EDV-REVIEW",
            full_name=self.reviewer.real_name,
            status="active",
            department_ref=review_department,
            position_ref=review_position,
        )

        publish_department = Department.objects.create(
            company=self.company, code="PLAN", name="计划物控部",
        )
        self.publish_position = Position.objects.create(
            company=self.company,
            department=publish_department,
            code="PLAN-OP",
            name="计划员",
        )
        self.publish_responsibility = Responsibility.objects.create(
            code="RESP_EDV_RELEASE_TEST_PLAN",
            name="工程资料版本发布执行",
            status=Responsibility.Status.ACTIVE,
            is_active=True,
        )
        self.position_responsibility = PositionResponsibility.objects.create(
            position=self.publish_position,
            responsibility=self.publish_responsibility,
            active=True,
        )
        self.publisher = User.objects.create_user(
            username="edv-release-publisher",
            password="x",
            real_name="工程资料发布人",
            company_id=self.company.pk,
        )
        self.publisher_employee = Employee.objects.create(
            user=self.publisher,
            employee_no="EMP-EDV-RELEASE",
            full_name=self.publisher.real_name,
            status="active",
            department_ref=publish_department,
            position_ref=self.publish_position,
        )
        self.outsider = User.objects.create_user(
            username="edv-release-outsider",
            password="x",
            real_name="无权人员",
            company_id=self.company.pk,
        )
        self.admin = User.objects.create_superuser(
            username="edv-release-admin",
            password="x",
            real_name="管理员",
            company_id=self.company.pk,
        )

        product = ProductDefinition.objects.create(
            company=self.company,
            product_code="EDV-REL-PRODUCT",
            product_name="发布测试产品",
            emd_material_code="EDV-REL-FG",
        )
        product_version = ProductVersion.objects.create(
            product=product, version_no="V1.0",
        )
        bom = ProductBOM.objects.create(
            company=self.company,
            product=product,
            bom_code="EDV-REL-BOM",
            name="发布测试BOM",
        )
        self.bom_version = BOMVersion.objects.create(
            bom=bom,
            product=product,
            product_version=product_version,
            bom_version="V1.0",
            status="released",
        )
        routing = Routing.objects.create(
            company=self.company,
            product=product,
            routing_code="EDV-REL-ROUTING",
            name="发布测试工艺路线",
            status="released",
        )
        routing_version = RoutingVersion.objects.create(
            routing=routing,
            product=product,
            product_version=product_version,
            routing_version="V1.0",
            revision=1,
            status="draft",
        )
        operation = Process.objects.create(
            company=self.company,
            code="EDV-REL-OP",
            name="发布测试工序",
        )
        RoutingStep.objects.create(
            routing_version=routing_version,
            sequence=1,
            operation=operation,
            standard_hours=Decimal("1.0000"),
        )
        routing_version.status = "released"
        routing_version.save(update_fields=["status"])
        document = EngineeringDocument.objects.create(
            document_no="EDV-REL-DOC",
            document_name="工程资料发布测试",
            document_type="technical",
            product=product,
            product_bom=bom,
            routing=routing,
        )
        self.version = EngineeringDocumentVersion.objects.create(
            document=document,
            document_name=document.document_name,
            document_version="V1.0",
            product_version=product_version,
            related_product=product,
            related_bom=self.bom_version,
            related_routing=routing_version,
        )

        ensure_engineering_document_version_permission_catalog()
        review_permission = Permission.objects.get(code=REVIEW_ACTION)
        review_role = Role.objects.create(code="edv-rel-review-role", name="工程资料评审员")
        RolePermission.objects.create(role=review_role, permission=review_permission)
        UserRoleScopeAssignment.objects.create(
            user=self.reviewer,
            role=review_role,
            organization=self.company,
            scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            active=True,
            business_hash="a" * 64,
        )
        from .engineering_document_version_workflow_catalog import CANONICAL_DEFINITION
        from system.models import PositionWorkflowResponsibility
        from workflow_runtime.models import ProcessDefinition
        definition = ProcessDefinition.objects.get(
            definition_code=CANONICAL_DEFINITION["definition_code"],
        )
        node = definition.nodes.get()
        PositionWorkflowResponsibility.objects.create(
            position=review_position,
            responsibility=review_responsibility,
            workflow_node=node,
            workflow_code=definition.definition_code,
            node_code=node.node_code,
            ownership_type=PositionWorkflowResponsibility.OwnershipType.REVIEWER,
            active=True,
        )
        release_permission, _ = Permission.objects.get_or_create(
            code=RELEASE_ACTION,
            defaults={"name": "工程资料版本正式发布", "module": "PDE"},
        )
        self.release_role = Role.objects.create(
            code="PLAN_OPERATOR_V1_TEST", name="计划发布员",
        )
        self.role_permission = RolePermission.objects.create(
            role=self.release_role, permission=release_permission,
        )
        self.scope_assignment = UserRoleScopeAssignment.objects.create(
            user=self.publisher,
            role=self.release_role,
            organization=self.company,
            scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            active=True,
            business_hash="b" * 64,
        )
        review_completeness = {
            "complete": True,
            "gates": [{
                "code": "TEST_EXACT_SOURCE_CHAIN",
                "label": "准确测试来源链",
                "statusCode": "PASS",
                "statusLabel": "通过",
                "evidence": "测试来源链完整",
                "details": {},
            }],
            "routingStepCount": 1,
            "exactChain": {},
            "manufacturingOutputCount": 0,
        }
        with patch(
            "pde.engineering_document_version_review_service.project_source_completeness",
            return_value=review_completeness,
        ):
            review_engineering_document_version(
                object_id=self.version.pk,
                user=self.reviewer,
                reason="工程资料版本正式评审通过",
                idempotency_key="edv-release-review",
                action=REVIEW_ACTION,
            )
        self.version.refresh_from_db()

    def release(self, *, user=None, key="edv-release-1", reason="确认工程资料版本正式发布"):
        return release_engineering_document_version(
            object_id=self.version.pk,
            user=user or self.publisher,
            reason=reason,
            idempotency_key=key,
            action=RELEASE_ACTION,
        )

    def test_preflight_is_read_only_and_ready_independent_of_current_browser_user(self):
        before = (
            BusinessStateTransition.objects.count(),
            OrganizationOperatingAuditRecord.objects.count(),
            MasterDataWriteRequest.objects.count(),
        )
        facts = project_release_preflight(self.version, self.admin)
        self.assertTrue(facts["readyForHumanRelease"])
        self.assertFalse(facts["currentBrowserOperable"])
        self.assertFalse(facts["releaseAllowed"])
        self.assertEqual(facts["decisionCode"], "PASS_READY_FOR_HUMAN_DOCUMENT_RELEASE")
        self.assertEqual([row["userId"] for row in facts["eligibleReleaseActors"]], [self.publisher.pk])
        self.assertEqual(before, (
            BusinessStateTransition.objects.count(),
            OrganizationOperatingAuditRecord.objects.count(),
            MasterDataWriteRequest.objects.count(),
        ))

    def test_eligible_publisher_evidence_contains_existing_formal_chain_ids(self):
        actors = eligible_release_actors(self.version)
        self.assertEqual(len(actors), 1)
        actor = actors[0]
        self.assertEqual(actor["userId"], self.publisher.pk)
        self.assertEqual(actor["employeeId"], self.publisher_employee.pk)
        self.assertEqual(actor["positionId"], self.publish_position.pk)
        self.assertIn(self.role_permission.pk, actor["rolePermissionIds"])
        self.assertIn(self.scope_assignment.pk, actor["userRoleScopeAssignmentIds"])
        self.assertIn(self.position_responsibility.pk, actor["positionResponsibilityIds"])

    def test_release_persists_transition_audit_request_and_no_manufacturing_output(self):
        review_decisions = ApprovalDecision.objects.count()
        result = self.release()
        self.version.refresh_from_db()
        self.version.document.refresh_from_db()
        self.assertEqual(self.version.status, "released")
        self.assertEqual(self.version.document.version, "V1.0")
        self.assertEqual(ApprovalDecision.objects.count(), review_decisions)
        self.assertEqual(ProductManufacturingOutput.objects.count(), 0)
        self.assertFalse(result["manufacturingReleaseExecuted"])
        transition = BusinessStateTransition.objects.get(action_code=RELEASE_ACTION)
        self.assertEqual((transition.source_state, transition.target_state), ("reviewed", "released"))
        self.assertEqual(transition.operator_id, self.publisher.pk)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(action_code=RELEASE_ACTION).count(), 1)
        self.assertEqual(MasterDataWriteRequest.objects.filter(action_code=RELEASE_ACTION, status="COMMITTED").count(), 1)

    def test_idempotent_replay_and_second_key_do_not_duplicate_release(self):
        first = self.release(key="edv-release-replay")
        second = self.release(key="edv-release-replay")
        self.assertFalse(first["idempotentReplay"])
        self.assertTrue(second["idempotentReplay"])
        self.assertEqual(BusinessStateTransition.objects.filter(action_code=RELEASE_ACTION).count(), 1)
        with self.assertRaises(EngineeringDocumentVersionReleaseError) as caught:
            self.release(key="edv-release-second")
        self.assertEqual(caught.exception.code, "ENGINEERING_DOCUMENT_VERSION_STATE_CONFLICT")
        self.assertEqual(BusinessStateTransition.objects.filter(action_code=RELEASE_ACTION).count(), 1)

    def test_concurrent_release_contract_has_atomic_lock_and_duplicate_fact_guard(self):
        source = inspect.getsource(release_engineering_document_version)
        self.assertIn("@transaction.atomic", source)
        self.assertIn("EngineeringDocumentVersion.objects.select_for_update()", source)
        self.assertIn("BusinessStateTransition.objects.select_for_update()", source)
        self.assertIn("ENGINEERING_DOCUMENT_VERSION_ALREADY_RELEASED", source)

    def test_reviewed_content_change_blocks_release(self):
        self.version.document_name = "评审后被修改"
        self.version.save(update_fields=["document_name", "updated_at"])
        with self.assertRaises(EngineeringDocumentVersionReleaseError) as caught:
            self.release(key="edv-release-content-invalid")
        self.assertEqual(
            caught.exception.code,
            "ENGINEERING_DOCUMENT_VERSION_REVIEW_CONTENT_INVALIDATED",
        )
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, "reviewed")

    def test_draft_and_missing_review_cannot_release(self):
        self.version.status = "draft"
        self.version.save(update_fields=["status"])
        with self.assertRaises(EngineeringDocumentVersionReleaseError) as caught:
            self.release(key="edv-release-draft")
        self.assertEqual(caught.exception.code, "ENGINEERING_DOCUMENT_VERSION_STATE_CONFLICT")

        unreviewed = EngineeringDocumentVersion.objects.create(
            document=self.version.document,
            document_name=self.version.document_name,
            document_version="V2.0",
            product_version=self.version.product_version,
            related_product=self.version.related_product,
            related_bom=self.version.related_bom,
            related_routing=self.version.related_routing,
            status="reviewed",
        )
        with self.assertRaises(EngineeringDocumentVersionReleaseError) as missing_review:
            release_engineering_document_version(
                object_id=unreviewed.pk,
                user=self.publisher,
                reason="缺少正式评审不得发布",
                idempotency_key="edv-release-no-review",
                action=RELEASE_ACTION,
            )
        self.assertEqual(
            missing_review.exception.code,
            "ENGINEERING_DOCUMENT_VERSION_FORMAL_REVIEW_REQUIRED",
        )

    def test_unauthorized_and_superuser_cannot_bypass_formal_chain(self):
        for user, key in ((self.outsider, "edv-outside"), (self.admin, "edv-admin")):
            with self.assertRaises(EngineeringDocumentVersionReleaseError) as caught:
                self.release(user=user, key=key)
            self.assertEqual(caught.exception.code, "PERMISSION_DENIED")
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, "reviewed")

    def test_reviewer_cannot_publish_even_with_release_permission(self):
        UserRoleScopeAssignment.objects.create(
            user=self.reviewer,
            role=self.release_role,
            organization=self.company,
            scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            active=True,
            business_hash="c" * 64,
        )
        PositionResponsibility.objects.get_or_create(
            position=self.reviewer.employee_profile.position_ref,
            responsibility=self.publish_responsibility,
            defaults={"active": True},
        )
        with self.assertRaises(EngineeringDocumentVersionReleaseError) as caught:
            self.release(user=self.reviewer, key="edv-reviewer-release")
        self.assertEqual(caught.exception.code, "REVIEW_RELEASE_DUTY_SEPARATION_REQUIRED")

    def test_generic_lifecycle_delegates_reviewed_to_dedicated_release(self):
        with patch(
            "pde.engineering_document_version_release_service.release_engineering_document_version",
            return_value={"delegated": True},
        ) as delegated:
            result = EngineeringLifecycleService.transition(
                "engineering-document-versions",
                object_id=self.version.pk,
                target_status="released",
                user=self.publisher,
                reason="正式发布",
                idempotency_key="edv-release-delegated",
                action=RELEASE_ACTION,
            )
        self.assertTrue(result["delegated"])
        delegated.assert_called_once()

    def test_http_release_contract_and_permission_denial(self):
        self.client.force_authenticate(user=self.publisher)
        response = self.client.post(
            f"/api/pde/engineering-document-versions/{self.version.pk}/release/",
            {"action": RELEASE_ACTION, "reason": "HTTP正式发布"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="edv-release-http",
        )
        self.assertEqual(response.status_code, 200)
        result = response.data["result"]
        self.assertEqual(result["engineeringDocumentVersion"]["status"], "released")
        self.assertEqual(result["businessStateTransition"]["toState"], "released")
        self.assertFalse(result["manufacturingReleaseExecuted"])

    def test_http_admin_denial_rolls_back_every_release_fact(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f"/api/pde/engineering-document-versions/{self.version.pk}/release/",
            {"action": RELEASE_ACTION, "reason": "管理员不得绕过"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="edv-release-admin-http",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "PERMISSION_DENIED")
        self.assertEqual(MasterDataWriteRequest.objects.filter(action_code=RELEASE_ACTION).count(), 0)
        self.assertEqual(BusinessStateTransition.objects.filter(action_code=RELEASE_ACTION).count(), 0)
        self.assertEqual(ProductManufacturingOutput.objects.count(), 0)
