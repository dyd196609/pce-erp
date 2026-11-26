from django.test import TestCase

from pfm.models import Employee
from system.authorization import AuthorizationService
from system.models import (
    Company,
    Department,
    Permission,
    Position,
    PositionResponsibility,
    Responsibility,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)
from workflow_runtime.models import ProcessDefinition, WorkflowNodeDefinition

from .bom_version_control_service import (
    RELEASE_PERMISSION,
    REVIEW_PERMISSION,
    eligible_action_actors,
    resolve_workflow_template,
)
from .bom_version_permission_catalog import ensure_bom_version_permission_catalog
from .production_foundation_service import EngineeringLifecycleService


class BomVersionPermissionCatalogTests(TestCase):
    def test_catalog_registers_only_two_permissions_and_no_authority(self):
        role_count = Role.objects.count()
        role_permission_count = RolePermission.objects.count()
        assignment_count = UserRoleScopeAssignment.objects.count()

        first = ensure_bom_version_permission_catalog()
        second = ensure_bom_version_permission_catalog()

        self.assertEqual(
            first["createdPermissions"],
            ["pde.bom_version.release", "pde.bom_version.review"],
        )
        self.assertEqual(
            second["existingPermissions"],
            ["pde.bom_version.release", "pde.bom_version.review"],
        )
        self.assertEqual(Role.objects.count(), role_count)
        self.assertEqual(RolePermission.objects.count(), role_permission_count)
        self.assertEqual(UserRoleScopeAssignment.objects.count(), assignment_count)

    def test_historical_lifecycle_metadata_uses_dedicated_release_permission(self):
        self.assertEqual(
            EngineeringLifecycleService.CONFIG["bom-versions"][2],
            RELEASE_PERMISSION,
        )


class BomVersionDedicatedActorTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="COMP-T", name="测试公司")
        self.review_department = Department.objects.create(
            company=self.company, code="DESIGN", name="设计部",
        )
        self.release_department = Department.objects.create(
            company=self.company, code="PROCESS", name="工艺部",
        )
        self.legacy_department = Department.objects.create(
            company=self.company, code="PLAN", name="计划部",
        )
        self.review_position = Position.objects.create(
            company=self.company, department=self.review_department,
            code="REVIEW-POS", name="BOM评审岗位",
        )
        self.release_position = Position.objects.create(
            company=self.company, department=self.release_department,
            code="RELEASE-POS", name="BOM发布岗位",
        )
        self.legacy_position = Position.objects.create(
            company=self.company, department=self.legacy_department,
            code="LEGACY-POS", name="计划操作岗位",
        )
        self.review_responsibility = Responsibility.objects.create(
            code="BOM_VERSION_FORMAL_REVIEW", name="BOM版本正式评审",
            status=Responsibility.Status.ACTIVE, is_active=True,
        )
        self.release_responsibility = Responsibility.objects.create(
            code="BOM_VERSION_FORMAL_RELEASE", name="BOM版本正式发布",
            status=Responsibility.Status.ACTIVE, is_active=True,
        )
        PositionResponsibility.objects.create(
            position=self.review_position, responsibility=self.review_responsibility,
            active=True,
        )
        PositionResponsibility.objects.create(
            position=self.release_position, responsibility=self.release_responsibility,
            active=True,
        )
        # Give the legacy position both formal responsibilities.  It must still
        # fail because generic engineering permissions are not BOM action grants.
        PositionResponsibility.objects.create(
            position=self.legacy_position, responsibility=self.review_responsibility,
            active=True,
        )
        PositionResponsibility.objects.create(
            position=self.legacy_position, responsibility=self.release_responsibility,
            active=True,
        )

        ensure_bom_version_permission_catalog()
        self.legacy_maintain, _ = Permission.objects.get_or_create(
            code="production.engineering.version.maintain",
            defaults={"name": "维护生产工程版本", "module": "PRODUCTION"},
        )
        self.legacy_release, _ = Permission.objects.get_or_create(
            code="production.engineering.version.release",
            defaults={"name": "发布或失效生产工程版本", "module": "PRODUCTION"},
        )
        self.review_role = self._role(
            "bom-review-role", "BOM版本正式评审员", REVIEW_PERMISSION,
        )
        self.release_role = self._role(
            "bom-release-role", "BOM版本正式发布员", RELEASE_PERMISSION,
        )
        self.legacy_role = Role.objects.create(
            code="PLAN_OPERATOR_V1_TEST", name="计划操作员测试",
        )
        RolePermission.objects.create(
            role=self.legacy_role, permission=self.legacy_maintain,
        )
        RolePermission.objects.create(
            role=self.legacy_role, permission=self.legacy_release,
        )

        self.reviewer = self._actor(
            "review-user", "评审人", self.review_department,
            self.review_position, self.review_role,
        )
        self.releaser = self._actor(
            "release-user", "发布人", self.release_department,
            self.release_position, self.release_role,
        )
        self.legacy_actor = self._actor(
            "legacy-user", "计划员", self.legacy_department,
            self.legacy_position, self.legacy_role,
        )

    def _role(self, code, name, permission_code):
        role = Role.objects.create(code=code, name=name)
        RolePermission.objects.create(
            role=role, permission=Permission.objects.get(code=permission_code),
        )
        return role

    def _actor(self, username, real_name, department, position, role):
        user = User.objects.create_user(
            username=username, password="x", real_name=real_name,
            company_id=self.company.pk,
        )
        Employee.objects.create(
            user=user, employee_no=f"EMP-{username}", full_name=real_name,
            status="active", department_ref=department, position_ref=position,
        )
        UserRoleScopeAssignment.objects.create(
            user=user, role=role, organization=self.company,
            scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            active=True, business_hash=(username + "0" * 64)[:64],
        )
        return user

    def test_dedicated_actions_resolve_only_matching_role_and_responsibility(self):
        review_actors = eligible_action_actors(
            self.company.pk, 3, REVIEW_PERMISSION,
        )
        release_actors = eligible_action_actors(
            self.company.pk, 3, RELEASE_PERMISSION,
        )

        self.assertEqual([row["userId"] for row in review_actors], [self.reviewer.pk])
        self.assertEqual([row["userId"] for row in release_actors], [self.releaser.pk])
        self.assertEqual(
            review_actors[0]["requiredResponsibilityCode"],
            "BOM_VERSION_FORMAL_REVIEW",
        )
        self.assertEqual(
            release_actors[0]["requiredResponsibilityCode"],
            "BOM_VERSION_FORMAL_RELEASE",
        )

    def test_generic_engineering_permissions_do_not_authorize_bom_actions(self):
        for action_code in (REVIEW_PERMISSION, RELEASE_PERMISSION):
            decision = AuthorizationService.decide(
                user=self.legacy_actor,
                action_code=action_code,
                organization_id=self.company.pk,
                business_object={"organizationId": self.company.pk},
            )
            self.assertFalse(decision["allowed"])
            self.assertEqual(decision["decisionCode"], "PERMISSION_DENIED")

    def test_workflow_node_must_use_exact_bom_review_action(self):
        definition = ProcessDefinition.objects.create(
            definition_code="PDE_BOM_VERSION_FORMAL_REVIEW",
            definition_name="BOM版本正式评审流程",
            business_domain="PDE", document_type="BOMVersion",
            version=1, active=True, definition_hash="a" * 64,
        )
        node = WorkflowNodeDefinition.objects.create(
            process_definition=definition,
            node_code="REVIEW_BOM_VERSION", node_name="BOM版本正式评审",
            sequence=1,
            business_action_code="production.engineering.version.maintain",
            active=True,
        )

        _, _, error = resolve_workflow_template()
        self.assertEqual(error["code"], "BOM_VERSION_WORKFLOW_NODE_ACTION_INVALID")
        self.assertEqual(error["expectedPermissionCode"], REVIEW_PERMISSION)

        node.business_action_code = REVIEW_PERMISSION
        node.save(update_fields=["business_action_code"])
        resolved_definition, resolved_node, error = resolve_workflow_template()
        self.assertIsNone(error)
        self.assertEqual(resolved_definition.pk, definition.pk)
        self.assertEqual(resolved_node.pk, node.pk)
