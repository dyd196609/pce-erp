from django.test import TestCase
from rest_framework.test import APIClient

from pfm.models import Employee
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Position,
    PositionResponsibility, PositionWorkflowResponsibility, Responsibility, Role,
    RolePermission, User, UserRoleScopeAssignment,
)
from workflow_runtime.definition_service import WorkflowDefinitionError, WorkflowDefinitionOperatingService
from workflow_runtime.models import ProcessDefinition, WorkflowNodeDefinition


class FormalProcessDefinitionV1Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(id=1, code="T01", name="测试公司")
        cls.admin = User.objects.create_superuser(
            username="workflow-admin", password="secret", real_name="流程管理员", company_id=cls.company.pk
        )
        Permission.objects.get_or_create(
            code="procurement.purchase_request.create",
            defaults={"name": "采购申请新建", "module": "SCM"},
        )
        Permission.objects.get_or_create(
            code="purchase_request.submit",
            defaults={"name": "采购申请提交", "module": "SCM"},
        )

    def process_payload(self, **overrides):
        return {
            "definitionCode": "PROCUREMENT_REQUEST_FLOW",
            "definitionName": "采购申请流程",
            "businessDomain": "SCM",
            "documentType": "PURCHASE_REQUEST",
            "version": 1,
            "active": True,
            "description": "采购申请正式流程",
            "reason": "建立正式流程",
            **overrides,
        }

    def save_process(self):
        return WorkflowDefinitionOperatingService.execute(
            user=self.admin, action="SAVE_PROCESS_DEFINITION", payload=self.process_payload()
        )["definition"]

    def node_payload(self, definition_id, **overrides):
        return {
            "processDefinitionId": definition_id,
            "nodeCode": "CREATE_REQUEST",
            "nodeName": "新建采购申请",
            "sequence": 1,
            "businessActionCode": "procurement.purchase_request.create",
            "active": True,
            "description": "通过采购申请正式入口新建",
            "reason": "建立正式节点",
            **overrides,
        }

    def test_formal_actions_create_definition_and_node_with_hash_and_audit(self):
        responsibility_count = PositionWorkflowResponsibility.objects.count()
        definition_count = ProcessDefinition.objects.count()
        node_count = WorkflowNodeDefinition.objects.count()
        audit_count = OrganizationOperatingAuditRecord.objects.count()
        definition = self.save_process()
        result = WorkflowDefinitionOperatingService.execute(
            user=self.admin,
            action="SAVE_WORKFLOW_NODE",
            payload=self.node_payload(definition["id"]),
        )

        self.assertEqual(ProcessDefinition.objects.count(), definition_count + 1)
        self.assertEqual(WorkflowNodeDefinition.objects.count(), node_count + 1)
        self.assertEqual(
            ProcessDefinition.objects.filter(
                definition_code=definition["definitionCode"]
            ).count(),
            1,
        )
        self.assertEqual(
            len(ProcessDefinition.objects.get(pk=definition["id"]).definition_hash), 64
        )
        self.assertEqual(result["node"]["businessActionCode"], "procurement.purchase_request.create")
        self.assertEqual(
            set(OrganizationOperatingAuditRecord.objects.filter(
                pk__gt=0
            ).order_by("pk").values_list("action_code", flat=True)[audit_count:]),
            {"SAVE_PROCESS_DEFINITION", "SAVE_WORKFLOW_NODE"},
        )
        self.assertEqual(PositionWorkflowResponsibility.objects.count(), responsibility_count)

    def test_definition_code_and_node_code_are_unique(self):
        definition = self.save_process()
        with self.assertRaises(WorkflowDefinitionError):
            WorkflowDefinitionOperatingService.execute(
                user=self.admin, action="SAVE_PROCESS_DEFINITION", payload=self.process_payload()
            )
        WorkflowDefinitionOperatingService.execute(
            user=self.admin, action="SAVE_WORKFLOW_NODE", payload=self.node_payload(definition["id"])
        )
        with self.assertRaises(WorkflowDefinitionError):
            WorkflowDefinitionOperatingService.execute(
                user=self.admin,
                action="SAVE_WORKFLOW_NODE",
                payload=self.node_payload(definition["id"], sequence=2),
            )

    def test_node_rejects_unregistered_business_action_and_duplicate_sequence(self):
        definition = self.save_process()
        with self.assertRaises(WorkflowDefinitionError) as missing:
            WorkflowDefinitionOperatingService.execute(
                user=self.admin,
                action="SAVE_WORKFLOW_NODE",
                payload=self.node_payload(definition["id"], businessActionCode="missing.action"),
            )
        self.assertEqual(missing.exception.code, "BUSINESS_ACTION_NOT_FOUND")
        WorkflowDefinitionOperatingService.execute(
            user=self.admin, action="SAVE_WORKFLOW_NODE", payload=self.node_payload(definition["id"])
        )
        with self.assertRaises(WorkflowDefinitionError):
            WorkflowDefinitionOperatingService.execute(
                user=self.admin,
                action="SAVE_WORKFLOW_NODE",
                payload=self.node_payload(
                    definition["id"], nodeCode="SUBMIT_REQUEST", nodeName="提交采购申请",
                    businessActionCode="purchase_request.submit",
                ),
            )

    def test_catalog_api_lists_details_and_nodes(self):
        definition = self.save_process()
        WorkflowDefinitionOperatingService.execute(
            user=self.admin, action="SAVE_WORKFLOW_NODE", payload=self.node_payload(definition["id"])
        )
        client = APIClient()
        client.force_authenticate(self.admin)

        listing = client.get("/api/workflow/definitions/")
        detail = client.get(f"/api/workflow/definitions/{definition['id']}/")
        nodes = client.get(f"/api/workflow/definitions/{definition['id']}/nodes/")

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["data"]["total"], ProcessDefinition.objects.count())
        matches = [
            row for row in listing.data["data"]["definitions"]
            if row["definitionCode"] == definition["definitionCode"]
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["documentType"], self.process_payload()["documentType"])
        self.assertEqual(detail.data["data"]["definition"]["nodeCount"], 1)
        self.assertEqual(nodes.data["data"]["total"], 1)
        self.assertFalse(listing.data["meta"]["productionUserDataWritten"])

    def test_execution_resolution_uses_formal_permission_position_employee_account_chain(self):
        definition = self.save_process()
        node = WorkflowDefinitionOperatingService.execute(
            user=self.admin, action="SAVE_WORKFLOW_NODE",
            payload=self.node_payload(definition["id"]),
        )["node"]
        department = Department.objects.create(
            code="WF-PUR", name="采购部", company=self.company,
        )
        role = Role.objects.create(code="workflow_buyer", name="流程采购员")
        permission = Permission.objects.get(code="procurement.purchase_request.create")
        RolePermission.objects.create(role=role, permission=permission)
        position = Position.objects.create(
            code="WF-BUYER", name="采购员", company=self.company,
            department=department, default_role=role,
        )
        responsibility = Responsibility.objects.create(
            code="WF_PURCHASE_REQUEST", name="采购申请创建责任",
            status=Responsibility.Status.ACTIVE, is_active=True,
        )
        PositionResponsibility.objects.create(
            position=position, responsibility=responsibility, active=True,
        )
        account = User.objects.create_user(
            username="workflow-buyer", password="secret", real_name="流程采购员",
            company_id=self.company.pk,
        )
        employee = Employee.objects.create(
            employee_no="WF-EMP", full_name="流程采购员工",
            department_ref=department, position_ref=position, user=account, status="active",
        )
        UserRoleScopeAssignment.objects.create(
            user=account, role=role, organization=self.company,
            scope_code="ORGANIZATION", business_hash="workflow-buyer-authority",
        )
        PositionWorkflowResponsibility.objects.create(
            position=position, responsibility=responsibility,
            workflow_node_id=node["id"], workflow_code="PROCUREMENT_REQUEST_FLOW",
            node_code="CREATE_REQUEST", ownership_type="EXECUTOR", active=True,
        )
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.get(
            f"/api/workflow/definitions/{definition['id']}/execution-resolution/"
        )

        self.assertEqual(response.status_code, 200)
        result = response.data["data"]
        self.assertEqual(result["metrics"]["executableNodeCount"], 1)
        self.assertTrue(result["nodes"][0]["executable"])
        self.assertEqual(result["nodes"][0]["positions"][0]["code"], position.code)
        self.assertEqual(result["nodes"][0]["employees"][0]["id"], employee.pk)
        self.assertEqual(result["nodes"][0]["accounts"][0]["username"], account.username)

    def test_non_privileged_user_is_denied_without_writes(self):
        user = User.objects.create_user(
            username="workflow-viewer", password="secret", real_name="普通用户", company_id=self.company.pk
        )
        client = APIClient()
        client.force_authenticate(user)
        before = ProcessDefinition.objects.count()
        response = client.post(
            "/api/workflow/definitions/",
            {"action": "SAVE_PROCESS_DEFINITION", "payload": self.process_payload()},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "PERMISSION_DENIED")
        self.assertEqual(ProcessDefinition.objects.count(), before)
