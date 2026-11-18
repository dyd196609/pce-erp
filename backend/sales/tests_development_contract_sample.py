from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from masterdata.models import ExternalIdentity, MasterDataWriteRequest, Material, UnitOfMeasure
from pde.models import EngineeringSourceRecord
from pfm.models import Employee
from sales.development_contract_sample import EXPECTED_SOURCE_CONTENT_HASH, calculate_quote
from sales.models import Customer, SalesOrder, SalesOrderItemEngineeringAttribute
from system.models import (
    Company, Department, Permission, Position, PositionResponsibility, PositionWorkflowResponsibility,
    Responsibility, Role, RolePermission, UserRoleScopeAssignment,
)
from workflow_runtime.models import ProcessDefinition, WorkflowNodeDefinition


def source_rows():
    rows = []
    for index in range(5):
        rows.append({"id": f"DOOR-{index}", "sourceSheet": "房门单", "sourceRow": 11 + index, "product": "房门", "component": "单开门", "quantity": 1, "unit": "扇"})
    for index in range(3):
        rows.append({"id": f"CASING-{index}", "sourceSheet": "房门单", "sourceRow": 21 + index, "product": "房门", "component": "单面套", "quantity": 1, "unit": "套"})
    for index in range(62):
        rows.append({"id": f"CABINET-{index}", "sourceSheet": "三合一生产单", "sourceRow": 7 + index, "product": "柜体", "component": "见光板", "quantity": 1, "unit": "块"})
    rows.append({"id": "FINISH-1", "sourceSheet": "三合一生产单", "sourceRow": 70, "product": "饰面", "component": "木饰面L型", "quantity": 1, "unit": "块"})
    return rows


class DevelopmentContractSampleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(id=1, code="COMP001", name="掌云智造科技有限公司", is_active=True)
        self.user = get_user_model().objects.create_user(username="sample-viewer", password="test-only", real_name="样本查看", company_id=1, is_active=True, is_superuser=True)
        for index in range(1, 11):
            EngineeringSourceRecord.objects.create(company=self.company, source_no=f"SRC-{index}", source_name="占位来源", source_type="controlled_import", source_version="R0", content_hash=str(index) * 64, source_payload={"engineeringRows": []})
        self.source = EngineeringSourceRecord.objects.create(company=self.company, source_no="SRC-11", source_name="71行来源", source_type="controlled_import",
            source_version="R20260915144257758338", content_hash=EXPECTED_SOURCE_CONTENT_HASH, source_payload={"engineeringRows": source_rows()})
        self.client = APIClient(); self.client.force_authenticate(self.user)

    def test_quote_uses_line_calculation_and_rounding(self):
        lines = [{"code": code, "quantity": quantity, "unitPrice": price, "taxRate": "0.13", "priceTaxMode": "tax_inclusive"}
            for code, quantity, price in (("DEV-L01", "5", "2800"), ("DEV-L02", "3", "600"), ("DEV-L03", "1", "48000"), ("DEV-L04", "1", "1800"))]
        result = calculate_quote(lines)
        self.assertEqual(result["totals"], {"gross": "65600.00", "net": "58053.10", "tax": "7546.90"})

    def test_page_projection_maps_exactly_71_rows_without_writes(self):
        before = SalesOrder.objects.count()
        response = self.client.get(f"/api/sales/orders/source-intake/engineering-sources/{self.source.pk}/development-contract/")
        self.assertEqual(response.status_code, 200)
        preview = response.data["data"]["preview"]
        self.assertEqual(preview["pageId"], "sales-orders")
        self.assertEqual(preview["subview"], "development-contract")
        self.assertEqual([row["sourceRowCount"] for row in preview["contract"]["lines"]], [5, 3, 62, 1])
        all_ids = [value for row in preview["contract"]["lines"] for value in row["sourceRowIds"]]
        self.assertEqual(len(all_ids), 71); self.assertEqual(len(set(all_ids)), 71)
        self.assertEqual(preview["contract"]["totals"]["gross"], "65600.00")
        self.assertEqual(SalesOrder.objects.count(), before)

    def test_normal_entry_resolves_configured_source_without_writes(self):
        before = SalesOrder.objects.count()
        response = self.client.get("/api/sales/orders/source-intake/development-contract-entry/")
        self.assertEqual(response.status_code, 200)
        entry = response.data["data"]["entry"]
        self.assertEqual(entry["entryLabel"], "开发合同与报价")
        self.assertEqual(entry["contractNo"], "PCE-DEV-SC-20260915-001")
        self.assertEqual(entry["customerName"], "上海王燕")
        self.assertEqual(entry["projectName"], "上海 大居苑")
        self.assertEqual(entry["sourceOrderNo"], "1-4-正")
        self.assertEqual(entry["sourceRowCount"], 71)
        self.assertEqual(entry["commercialLineCount"], 4)
        self.assertEqual(entry["grossAmount"], "65600.00")
        self.assertEqual(entry["target"]["query"]["sourceRecord"], self.source.pk)
        self.assertFalse(entry["strictFacts"]["historicalFallbackUsed"])
        self.assertEqual(SalesOrder.objects.count(), before)

    def test_governed_save_uses_sales_order_authority_and_is_idempotent(self):
        self.user.is_superuser = False
        self.user.save(update_fields=["is_superuser"])
        department = Department.objects.create(company=self.company, code="YXB", name="营销部", is_active=True)
        role, _ = Role.objects.get_or_create(code="sales_order_operator", defaults={"name": "销售订单执行员"})
        position = Position.objects.create(
            company=self.company, department=department, code="YXB-SALES", name="业务员",
            default_role=None, is_active=True,
        )
        Employee.objects.create(
            user=self.user, employee_no="EMP-R13-SALES", full_name="样本销售员", status="active",
            department_ref=department, position_ref=position,
        )
        Employee.objects.create(
            employee_no="EMP103", full_name="冯美", status="active",
            department_ref=department, position_ref=position,
        )
        Customer.objects.create(company=self.company, code="DLR-S07-002", name="上海王燕", is_active=True)
        for code in ("sales.order.view", "sales.order.create", "sales.order.update"):
            permission, _ = Permission.objects.get_or_create(code=code, defaults={"name": code, "module": "SALES"})
            RolePermission.objects.get_or_create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=self.user, role=role, organization=self.company,
            scope_code="ORGANIZATION", active=True, version=1, business_hash="sample-contract-test",
        )
        responsibility, _ = Responsibility.objects.get_or_create(
            code="RESP_SALES_ORDER_002", defaults={"name": "销售需求与订单协调", "is_active": True, "status": "ACTIVE"},
        )
        PositionResponsibility.objects.get_or_create(
            position=position, responsibility=responsibility, defaults={"active": True},
        )
        process, _ = ProcessDefinition.objects.update_or_create(
            definition_code="SALES_ORDER_TO_SUPPLY_PLAN",
            defaults={"definition_name": "销售订单至供应计划主链", "business_domain": "SALES/PLAN",
                "document_type": "SalesOrder", "version": 1, "active": True, "definition_hash": "sample-contract-test"},
        )
        for sequence, (node_code, action_code) in enumerate((
            ("CREATE_SAMPLE", "sales.order.create"),
            ("UPDATE_SAMPLE", "sales.order.update"),
        ), 1):
            node = WorkflowNodeDefinition.objects.create(
                process_definition=process, node_code=node_code, node_name=node_code,
                sequence=sequence, business_action_code=action_code, active=True,
            )
            PositionWorkflowResponsibility.objects.create(
                position=position, workflow_code=process.definition_code, node_code=node_code,
                ownership_type="OWNER", responsibility=responsibility, workflow_node=node, active=True,
            )

        preview = self.client.get(
            f"/api/sales/orders/source-intake/engineering-sources/{self.source.pk}/development-contract/"
        ).data["data"]["preview"]
        self.assertTrue(preview["authorization"]["canSave"])
        with patch("sales.development_contract_sample._assert_b_database"):
            response = self.client.post(
                f"/api/sales/orders/source-intake/engineering-sources/{self.source.pk}/development-contract/",
                preview["contract"], format="json", HTTP_IDEMPOTENCY_KEY="sample-save-1",
            )
            replay = self.client.post(
                f"/api/sales/orders/source-intake/engineering-sources/{self.source.pk}/development-contract/",
                preview["contract"], format="json", HTTP_IDEMPOTENCY_KEY="sample-save-1",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.assertFalse(response.data["data"]["replayed"])
        self.assertTrue(replay.data["data"]["replayed"])
        self.assertEqual(SalesOrder.objects.count(), 1)
        order = SalesOrder.objects.get()
        self.assertEqual(order.contract_reference, "PCE-DEV-SC-20260915-001")
        self.assertEqual(order.items.count(), 4)
        self.assertEqual(SalesOrderItemEngineeringAttribute.objects.filter(sales_order_item__sales_order=order).count(), 71)
        self.assertEqual(Material.objects.filter(company_id=self.company.pk, code__startswith="DEV-SC-").count(), 4)
        self.assertEqual(UnitOfMeasure.objects.filter(company_id=self.company.pk, code="扇").count(), 1)
        self.assertEqual(ExternalIdentity.objects.filter(target_entity_id=str(order.pk)).count(), 1)
        self.assertEqual(MasterDataWriteRequest.objects.filter(status="COMMITTED").count(), 1)
