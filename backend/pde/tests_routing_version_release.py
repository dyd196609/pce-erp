import inspect
from unittest.mock import patch

from django.test import TestCase

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
from workflow_runtime.models import (
    ApprovalDecision,
    ApprovalTask,
    BusinessStateTransition,
    ProcessDefinition,
    WorkflowInstance,
    WorkflowNodeDefinition,
)

from .models import ManufacturingProcessType, ProductCategory, Routing, RoutingVersion
from .routing_version_release_service import (
    RELEASE_ACTION,
    RELEASE_PERMISSION,
    REQUIRED_RESPONSIBILITY_CODE,
    RoutingVersionReleaseError,
    eligible_release_actors,
    project_release_preflight,
    release_routing_version,
)
from .routing_version_review_service import (
    APPROVED_PROJECTION,
    REVIEW_ACTION,
    REVIEW_PERMISSION,
    review_routing_version,
)


class RoutingVersionReleaseTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="REL01", name="路线发布测试公司")
        self.reviewer = User.objects.create_user(
            username="release-test-reviewer",
            password="x",
            real_name="路线评审人",
            company_id=self.company.pk,
        )
        self.publisher = User.objects.create_user(
            username="release-test-publisher",
            password="x",
            real_name="路线发布人",
            company_id=self.company.pk,
        )
        self.outsider = User.objects.create_user(
            username="release-test-generic",
            password="x",
            real_name="通用权限人员",
            company_id=self.company.pk,
        )
        self.admin = User.objects.create_superuser(
            username="release-test-admin",
            password="x",
            real_name="管理员",
            company_id=self.company.pk,
        )
        category = ProductCategory.objects.create(
            company=self.company,
            code="CAT-RELEASE",
            name="路线发布测试分类",
        )
        process_type = ManufacturingProcessType.objects.create(
            company=self.company,
            code="PROC-RELEASE",
            name="路线发布测试工艺",
        )
        self.routing = Routing.objects.create(
            company=self.company,
            routing_code="RT-RELEASE",
            name="路线发布测试",
            applicability_scope="PRODUCT_CATEGORY",
            product_category=category,
            manufacturing_process_type=process_type,
            status="released",
        )
        self.history = RoutingVersion.objects.create(
            routing=self.routing,
            routing_version="V1.0",
            revision=1,
            status="released",
            approval_state=APPROVED_PROJECTION,
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
        definition = ProcessDefinition.objects.create(
            definition_code="ROUTING_VERSION_RELEASE_TEST_REVIEW",
            definition_name="工艺路线版本正式评审",
            business_domain="PDE",
            document_type="RoutingVersion",
            version=1,
            active=True,
            definition_hash="f" * 64,
        )
        WorkflowNodeDefinition.objects.create(
            process_definition=definition,
            node_code="REVIEW_ROUTING_VERSION",
            node_name="评审工艺路线版本",
            sequence=1,
            business_action_code=REVIEW_PERMISSION,
            active=True,
        )
        self.completeness = {
            "complete": True,
            "gates": [{
                "code": "TEST_COMPLETE",
                "label": "测试完整性",
                "statusCode": "PASS",
                "statusLabel": "通过",
                "evidence": "28道工序及适用性结论有效",
                "details": {},
            }],
            "stepCount": 28,
            "contextCount": 1,
            "sourceRoutingVersionId": self.history.pk,
            "applicabilityRows": [],
        }
        self.review_actor = {
            "userId": self.reviewer.pk,
            "username": self.reviewer.username,
            "realName": self.reviewer.real_name,
            "matchedRoleCodes": ["routing_version_reviewer"],
            "positionCode": "GYB-MGR",
        }
        self._review()

    def _review(self):
        with patch(
            "pde.routing_version_review_service.eligible_review_actors",
            return_value=[self.review_actor],
        ), patch(
            "pde.routing_version_review_service.project_draft_completeness",
            return_value=self.completeness,
        ):
            review_routing_version(
                object_id=self.version.pk,
                user=self.reviewer,
                reason="正式评审通过",
                idempotency_key="release-test-review",
                action=REVIEW_ACTION,
            )
        self.version.refresh_from_db()

    def _appoint(self, user=None):
        user = user or self.publisher
        permission, _ = Permission.objects.get_or_create(
            code=RELEASE_PERMISSION,
            defaults={"name": "工艺路线版本正式发布", "module": "PDE"},
        )
        role = Role.objects.create(
            code=f"routing_version_publisher_{user.pk}",
            name=f"工艺路线版本发布人{user.pk}",
        )
        RolePermission.objects.create(role=role, permission=permission)
        department = Department.objects.create(
            company=self.company,
            code=f"GYB{user.pk}",
            name=f"工艺部{user.pk}",
        )
        position = Position.objects.create(
            company=self.company,
            department=department,
            code=f"GYB-{user.pk}",
            name=f"工艺发布岗位{user.pk}",
        )
        responsibility, _ = Responsibility.objects.get_or_create(
            code=REQUIRED_RESPONSIBILITY_CODE,
            defaults={
                "name": "工艺路线版本正式发布",
                "description": "执行已通过正式评审的工艺路线版本发布",
                "category": "PDE产品研发与工程管理",
                "is_active": True,
                "status": Responsibility.Status.ACTIVE,
            },
        )
        PositionResponsibility.objects.create(
            position=position,
            responsibility=responsibility,
            active=True,
            is_primary=True,
        )
        Employee.objects.create(
            user=user,
            employee_no=f"REL-{user.pk}",
            full_name=user.real_name,
            status="active",
            department_ref=department,
            position_ref=position,
        )
        UserRoleScopeAssignment.objects.create(
            user=user,
            role=role,
            organization=self.company,
            scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            active=True,
            business_hash="a" * 64,
        )
        return role

    def _release(self, key="routing-release-1", user=None, reason="确认正式发布"):
        with patch(
            "pde.routing_version_release_service.project_draft_completeness",
            return_value=self.completeness,
        ):
            return release_routing_version(
                object_id=self.version.pk,
                user=user or self.publisher,
                reason=reason,
                idempotency_key=key,
                action=RELEASE_ACTION,
            )

    def test_preflight_reports_human_publisher_authorization_required(self):
        Permission.objects.create(
            code=RELEASE_PERMISSION,
            name="工艺路线版本正式发布",
            module="PDE",
        )
        before = (
            BusinessStateTransition.objects.count(),
            OrganizationOperatingAuditRecord.objects.count(),
            MasterDataWriteRequest.objects.count(),
        )
        with patch(
            "pde.routing_version_release_service.project_draft_completeness",
            return_value=self.completeness,
        ):
            facts = project_release_preflight(self.version, self.publisher)
        self.assertFalse(facts["releaseAllowed"])
        self.assertTrue(facts["humanPublisherAuthorizationRequired"])
        self.assertEqual(facts["decisionCode"], "HUMAN_PUBLISHER_AUTHORIZATION_REQUIRED")
        self.assertEqual(facts["firstBlockerCode"], "RELEASE_RESPONSIBILITY_REGISTERED")
        self.assertEqual(before, (
            BusinessStateTransition.objects.count(),
            OrganizationOperatingAuditRecord.objects.count(),
            MasterDataWriteRequest.objects.count(),
        ))

    def test_release_uses_dedicated_transition_and_preserves_review_and_history(self):
        self._appoint()
        review_decision_count = ApprovalDecision.objects.count()
        result = self._release()

        self.version.refresh_from_db()
        self.history.refresh_from_db()
        self.assertEqual(self.version.status, "released")
        self.assertEqual(self.version.approval_state, APPROVED_PROJECTION)
        self.assertEqual((self.version.routing_version, self.version.revision), ("V2.0", 2))
        self.assertEqual((self.history.status, self.history.routing_version), ("released", "V1.0"))
        self.assertEqual(ApprovalDecision.objects.count(), review_decision_count)
        release_transition = BusinessStateTransition.objects.get(action_code=RELEASE_ACTION)
        self.assertEqual((release_transition.source_state, release_transition.target_state), ("reviewed", "released"))
        self.assertEqual(release_transition.operator_id, self.publisher.pk)
        self.assertEqual(result["businessStateTransition"]["toState"], "released")
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(action_code=RELEASE_ACTION).count(), 1)

    def test_idempotent_replay_and_second_request_do_not_duplicate_release_fact(self):
        self._appoint()
        first = self._release(key="routing-release-replay")
        second = self._release(key="routing-release-replay")
        self.assertFalse(first["idempotentReplay"])
        self.assertTrue(second["idempotentReplay"])
        self.assertEqual(BusinessStateTransition.objects.filter(action_code=RELEASE_ACTION).count(), 1)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(action_code=RELEASE_ACTION).count(), 1)
        with self.assertRaises(RoutingVersionReleaseError) as caught:
            self._release(key="routing-release-second")
        self.assertEqual(caught.exception.code, "ROUTING_VERSION_STATE_CONFLICT")
        self.assertEqual(BusinessStateTransition.objects.filter(action_code=RELEASE_ACTION).count(), 1)

    def test_concurrent_release_contract_uses_atomic_row_locks_and_duplicate_fact_guard(self):
        source = inspect.getsource(release_routing_version)
        self.assertIn("@transaction.atomic", source)
        self.assertIn("RoutingVersion.objects.select_for_update()", source)
        self.assertIn("BusinessStateTransition.objects.select_for_update()", source)
        self.assertIn("ROUTING_VERSION_ALREADY_RELEASED", source)

    def test_review_content_hash_mismatch_blocks_release(self):
        self._appoint()
        audit = OrganizationOperatingAuditRecord.objects.get(action_code=REVIEW_ACTION)
        audit.after_snapshot = {**audit.after_snapshot, "reviewContentHash": "0" * 64}
        audit.save(update_fields=["after_snapshot"])
        with self.assertRaises(RoutingVersionReleaseError) as caught:
            self._release(key="routing-release-invalidated")
        self.assertEqual(caught.exception.code, "ROUTING_VERSION_REVIEW_CONTENT_INVALIDATED")
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, "reviewed")
        self.assertFalse(BusinessStateTransition.objects.filter(action_code=RELEASE_ACTION).exists())

    def test_unreviewed_version_cannot_release(self):
        self._appoint()
        unreviewed = RoutingVersion.objects.create(
            routing=self.routing,
            routing_version="V3.0",
            revision=3,
            status="draft",
            approval_state="not_submitted",
        )
        with self.assertRaises(RoutingVersionReleaseError) as caught:
            release_routing_version(
                object_id=unreviewed.pk,
                user=self.publisher,
                reason="不得发布",
                idempotency_key="routing-release-unreviewed",
                action=RELEASE_ACTION,
            )
        self.assertEqual(caught.exception.code, "ROUTING_VERSION_STATE_CONFLICT")

    def test_generic_permission_and_superuser_cannot_bypass_dedicated_chain(self):
        generic_permission, _ = Permission.objects.get_or_create(
            code="production.engineering.version.release",
            defaults={"name": "通用工程版本发布", "module": "PDE"},
        )
        generic_role = Role.objects.create(code="generic_release", name="通用版本发布")
        RolePermission.objects.create(role=generic_role, permission=generic_permission)
        UserRoleScopeAssignment.objects.create(
            user=self.outsider,
            role=generic_role,
            organization=self.company,
            scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            active=True,
            business_hash="b" * 64,
        )
        for user, key in ((self.outsider, "generic-denied"), (self.admin, "admin-denied")):
            with self.assertRaises(RoutingVersionReleaseError) as caught:
                self._release(key=key, user=user)
            self.assertEqual(caught.exception.code, "PERMISSION_DENIED")
        self.assertEqual(eligible_release_actors(self.company.pk, self.version.pk), [])

    def test_reviewer_cannot_be_the_publisher(self):
        self._appoint(self.reviewer)
        with self.assertRaises(RoutingVersionReleaseError) as caught:
            self._release(key="same-person-denied", user=self.reviewer)
        self.assertEqual(caught.exception.code, "REVIEW_RELEASE_DUTY_SEPARATION_REQUIRED")
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, "reviewed")

