from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from masterdata.models import ExternalIdentity, MasterDataWriteRequest, Material
from pde.crm_order_admission import (
    CRMOrderAdmissionError,
    current_crm_sales_order_admission_facts,
    require_current_crm_sales_order_admission,
)
from pde.models import (
    EngineeringSourceRecord,
    OrderCrossFunctionalReview,
    OrderReviewSalesOrderRelation,
    PDEEngineeringPreparationAuthorization,
    PDEReviewPredecessorRelation,
    ProductDesignItem,
)
from pfm.models import Employee
from system.models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    Permission,
    Position,
    PositionResponsibility,
    PositionWorkflowResponsibility,
    Responsibility,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)
from workflow_runtime.models import ProcessDefinition, WorkflowNodeDefinition

from .crm_source_establishment import (
    ACTION_CODE,
    SOURCE_OBJECT_TYPE,
    SOURCE_SYSTEM,
    SOURCE_TYPE,
    TARGET_ENTITY_TYPE,
    SalesOrderCRMSourceEstablishmentError,
    establish_sales_order_current_crm_source,
    resolve_current_crm_source,
)
from .models import (
    Customer,
    SalesOrder,
    SalesOrderItem,
    SalesOrderItemEngineeringAttribute,
)


class SalesOrderCRMSourceEstablishmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="CRM-SRC", name="CRM来源测试公司")
        cls.department = Department.objects.create(
            company=cls.company, code="CRM-SRC-SALES", name="营销部",
        )
        cls.position = Position.objects.create(
            company=cls.company, department=cls.department,
            code="CRM-SRC-POS", name="业务员",
        )
        cls.user = User.objects.create_user(
            username="crm_source_sales", password="unused", real_name="正式销售员工",
            company_id=cls.company.pk,
        )
        Employee.objects.create(
            user=cls.user, employee_no="CRM-SRC-E001", full_name="正式销售员工",
            status="active", department_ref=cls.department, position_ref=cls.position,
        )
        permission, _ = Permission.objects.get_or_create(
            code="sales.order.update",
            defaults={"name": "更新销售订单", "module": "SALES"},
        )
        role, _ = Role.objects.get_or_create(
            code="crm_source_sales_editor",
            defaults={"name": "CRM来源测试销售岗"},
        )
        RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=cls.user, role=role, organization=cls.company,
            scope_code="ORGANIZATION", active=True, version=1,
            business_hash="crm-source-establishment-test",
        )
        responsibility, _ = Responsibility.objects.update_or_create(
            code="RESP_SALES_ORDER_002",
            defaults={"name": "销售需求与订单协调", "is_active": True, "status": "ACTIVE"},
        )
        PositionResponsibility.objects.create(
            position=cls.position, responsibility=responsibility,
            active=True, is_primary=True,
        )
        process, _ = ProcessDefinition.objects.update_or_create(
            definition_code="SALES_ORDER_TO_SUPPLY_PLAN",
            defaults={
                "definition_name": "销售订单至供应计划主链",
                "business_domain": "SALES",
                "document_type": "SalesOrder",
                "version": 1,
                "active": True,
                "definition_hash": "crm-source-establishment-test",
            },
        )
        node, _ = WorkflowNodeDefinition.objects.update_or_create(
            process_definition=process,
            node_code="CRM_SOURCE_ESTABLISHMENT_UPDATE",
            defaults={
                "node_name": "建立当前CRM来源",
                "sequence": 902,
                "business_action_code": "sales.order.update",
                "active": True,
            },
        )
        PositionWorkflowResponsibility.objects.update_or_create(
            position=cls.position,
            workflow_code=process.definition_code,
            node_code=node.node_code,
            ownership_type="OWNER",
            defaults={
                "responsibility": responsibility,
                "workflow_node": node,
                "active": True,
            },
        )
        cls.customer = Customer.objects.create(
            company=cls.company, code="CRM-SRC-CUSTOMER", name="上海王燕",
        )
        cls.material = Material.objects.create(
            company_id=cls.company.pk, code="CRM-SRC-MATERIAL", name="订单工程产品",
            unit="件", material_type="finished", is_active=True,
        )

    def setUp(self):
        self.order = SalesOrder(
            company=self.company,
            department=self.department,
            customer=self.customer,
            order_no="SO-CRM-SOURCE-001",
            order_date=date.today(),
            required_delivery_date=date.today() + timedelta(days=20),
            order_type="project",
            order_source="crm",
            business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
            project_reference="上海 大居苑",
            external_source_no="1-4-正",
            status="draft",
            version=1,
            created_by=self.user,
        )
        self.order._business_state_initialization_authorized = True
        try:
            self.order.save(force_insert=True)
        finally:
            self.order._business_state_initialization_authorized = False
        self.items = []
        for line_no in range(1, 5):
            self.items.append(SalesOrderItem.objects.create(
                sales_order=self.order,
                line_no=line_no,
                material=self.material,
                engineering_mode="ORDER_ENGINEERED",
                quantity=Decimal("1"),
                required_date=self.order.required_delivery_date,
                customer_product_name=f"订单工程产品{line_no}",
                external_line_no=f"LINE-{line_no}",
            ))
        rows = [
            {"id": f"SOURCE-ROW-{line_no}", "product": "订单工程产品", "quantity": "1"}
            for line_no in range(1, 5)
        ]
        self.source = EngineeringSourceRecord.objects.create(
            company=self.company,
            source_no="CRM-SOURCE-001",
            source_name="CRM订单工程来源",
            source_type="controlled_import",
            source_version="R1",
            source_payload={
                "sourceClassification": "CONTROLLED_ENGINEERING_DRAFT",
                "formalSalesOrderCreated": False,
                "businessOrderReference": {
                    "sourceOrderNo": "1-4-正",
                    "customerName": "上海王燕",
                    "projectName": "上海大居苑",
                    "matchedSalesOrderId": None,
                    "stableOrderLinkStatus": "SOURCE_ORDER_NOT_ESTABLISHED",
                },
                "engineeringRows": rows,
            },
            content_hash="a" * 64,
            status="confirmed",
        )
        for line_no, item in enumerate(self.items, 1):
            attribute = SalesOrderItemEngineeringAttribute.objects.create(
                sales_order_item=item,
                sequence=1,
                raw_source="CRM-SOURCE-001",
                raw_sheet="工程来源",
                external_source=f"SOURCE-ROW-{line_no}",
                raw_field="sourceRow",
                raw_value={"id": f"SOURCE-ROW-{line_no}"},
                canonical_field="source_row",
                normalized_value=f"SOURCE-ROW-{line_no}",
                value_type="string",
                source_type="ENGINEERING_INPUT",
                created_by=self.user,
            )
            ProductDesignItem.objects.create(
                company=self.company,
                sales_order_item=item,
                source_record=self.source,
                source_attribute=attribute,
                item_no=f"CRM-SRC-DES-{line_no}",
                item_name=f"设计项{line_no}",
                original_requirement={"sourceRowId": f"SOURCE-ROW-{line_no}"},
                existing_design_data={},
                source_version=self.source.source_version,
                source_content_hash=self.source.content_hash,
                match_results={},
            )

    def _call(self, **overrides):
        values = {
            "actor": self.user,
            "order_id": self.order.pk,
            "expected_order_no": self.order.order_no,
            "source_record_id": self.source.pk,
            "expected_source_version": self.source.source_version,
            "expected_source_content_hash": self.source.content_hash,
            "expected_customer_name": "上海王燕",
            "expected_project_reference": "上海大居苑",
            "expected_external_source_no": "1-4-正",
            "expected_engineering_row_count": 4,
            "idempotency_key": "CRM-SOURCE-ESTABLISH-001",
            "reason": "建立真实订单的当前CRM来源",
        }
        values.update(overrides)
        return establish_sales_order_current_crm_source(**values)

    def _set_order_status(self, status):
        self.order.status = status
        self.order._business_state_transition_authorized = True
        try:
            self.order.save(update_fields=["status"])
        finally:
            self.order._business_state_transition_authorized = False

    def _current_identity_count(self):
        return ExternalIdentity.objects.filter(
            organization_id=self.company.pk,
            source_system=SOURCE_SYSTEM,
            source_type=SOURCE_TYPE,
            source_object_type=SOURCE_OBJECT_TYPE,
            target_entity_type=TARGET_ENTITY_TYPE,
            target_entity_id=str(self.order.pk),
            mapping_status=ExternalIdentity.MappingStatus.MATCH,
        ).count()

    def test_01_correct_source_establishes_one_current_relation(self):
        result = self._call()
        binding = resolve_current_crm_source(order=self.order)
        self.assertFalse(result["idempotent"])
        self.assertEqual(result["currentSourceCount"], 1)
        self.assertEqual(self._current_identity_count(), 1)
        self.assertEqual(binding.source.pk, self.source.pk)
        self.assertEqual(binding.scope["designDistribution"], {"1": 1, "2": 1, "3": 1, "4": 1})

    def test_02_customer_mismatch_fails_closed(self):
        payload = deepcopy(self.source.source_payload)
        payload["businessOrderReference"]["customerName"] = "其他客户"
        EngineeringSourceRecord.objects.filter(pk=self.source.pk).update(source_payload=payload)
        self.source.refresh_from_db()
        with self.assertRaises(SalesOrderCRMSourceEstablishmentError) as caught:
            self._call(expected_customer_name="其他客户")
        self.assertEqual(caught.exception.code, "CRM_SOURCE_BUSINESS_IDENTITY_MISMATCH")
        self.assertEqual(self._current_identity_count(), 0)

    def test_03_project_mismatch_fails_closed(self):
        payload = deepcopy(self.source.source_payload)
        payload["businessOrderReference"]["projectName"] = "其他项目"
        EngineeringSourceRecord.objects.filter(pk=self.source.pk).update(source_payload=payload)
        self.source.refresh_from_db()
        with self.assertRaises(SalesOrderCRMSourceEstablishmentError) as caught:
            self._call(expected_project_reference="其他项目")
        self.assertEqual(caught.exception.code, "CRM_SOURCE_BUSINESS_IDENTITY_MISMATCH")

    def test_04_external_source_mismatch_fails_closed(self):
        payload = deepcopy(self.source.source_payload)
        payload["businessOrderReference"]["sourceOrderNo"] = "OTHER"
        EngineeringSourceRecord.objects.filter(pk=self.source.pk).update(source_payload=payload)
        self.source.refresh_from_db()
        with self.assertRaises(SalesOrderCRMSourceEstablishmentError) as caught:
            self._call(expected_external_source_no="OTHER")
        self.assertEqual(caught.exception.code, "CRM_SOURCE_BUSINESS_IDENTITY_MISMATCH")

    def test_05_non_formal_sale_fails_closed(self):
        SalesOrder.objects.filter(pk=self.order.pk).update(
            business_purpose=SalesOrder.BusinessPurpose.DEVELOPMENT_VALIDATION,
        )
        self.order.refresh_from_db()
        with self.assertRaises(SalesOrderCRMSourceEstablishmentError) as caught:
            self._call()
        self.assertEqual(caught.exception.code, "CRM_SOURCE_FORMAL_SALE_REQUIRED")

    def test_06_cancelled_order_fails_closed(self):
        self._set_order_status("cancelled")
        with self.assertRaises(SalesOrderCRMSourceEstablishmentError) as caught:
            self._call()
        self.assertEqual(caught.exception.code, "CRM_SOURCE_CANCELLED_ORDER_FORBIDDEN")

    def test_07_multiple_current_sources_fail_closed(self):
        for index in (1, 2):
            ExternalIdentity.objects.create(
                organization_id=self.company.pk,
                source_system=SOURCE_SYSTEM,
                source_type=SOURCE_TYPE,
                source_object_type=SOURCE_OBJECT_TYPE,
                external_id=f"EngineeringSourceRecord:{100 + index}:R1",
                target_entity_type=TARGET_ENTITY_TYPE,
                target_entity_id=str(self.order.pk),
                mapping_status=ExternalIdentity.MappingStatus.MATCH,
                source_fingerprint=str(index) * 64,
                audit_metadata={"sourceRecordId": 100 + index},
            )
        with self.assertRaises(SalesOrderCRMSourceEstablishmentError) as caught:
            resolve_current_crm_source(order=self.order)
        self.assertEqual(caught.exception.code, "CRM_ORDER_CURRENT_SOURCE_AMBIGUOUS")

    def test_08_identical_replay_is_write_free(self):
        first = self._call()
        counts = {
            "identity": ExternalIdentity.objects.count(),
            "request": MasterDataWriteRequest.objects.count(),
            "audit": OrganizationOperatingAuditRecord.objects.count(),
        }
        second = self._call()
        self.assertTrue(second["idempotent"])
        self.assertEqual(second["sourceIdentityId"], first["sourceIdentityId"])
        self.assertEqual(second["organizationAuditId"], first["organizationAuditId"])
        self.assertEqual(counts, {
            "identity": ExternalIdentity.objects.count(),
            "request": MasterDataWriteRequest.objects.count(),
            "audit": OrganizationOperatingAuditRecord.objects.count(),
        })

    def test_09_source_history_is_not_overwritten(self):
        before = EngineeringSourceRecord.objects.filter(pk=self.source.pk).values().get()
        payload_before = deepcopy(self.source.source_payload)
        self._call()
        after = EngineeringSourceRecord.objects.filter(pk=self.source.pk).values().get()
        self.assertEqual(after, before)
        self.assertEqual(after["source_payload"], payload_before)

    def test_10_does_not_create_review(self):
        self._call()
        self.assertEqual(OrderCrossFunctionalReview.objects.count(), 0)

    def test_11_does_not_create_0032(self):
        self._call()
        self.assertEqual(OrderReviewSalesOrderRelation.objects.count(), 0)

    def test_12_does_not_create_0033(self):
        self._call()
        self.assertEqual(PDEReviewPredecessorRelation.objects.count(), 0)

    def test_13_does_not_create_authorization(self):
        self._call()
        self.assertEqual(PDEEngineeringPreparationAuthorization.objects.count(), 0)

    def test_14_gate_advances_to_review_missing_and_projects_current_source(self):
        self._call()
        with self.assertRaises(CRMOrderAdmissionError) as caught:
            require_current_crm_sales_order_admission(order=self.order)
        facts = current_crm_sales_order_admission_facts(self.order)
        self.assertEqual(caught.exception.code, "CRM_ORDER_REVIEW_MISSING")
        self.assertEqual(facts["statusCode"], "CRM_ORDER_REVIEW_MISSING")
        self.assertEqual(facts["currentSourceId"], self.source.pk)
        self.assertEqual(facts["currentSourceVersion"], self.source.source_version)
        self.assertIsNone(facts["currentReview"])
        self.assertIsNone(facts["currentRelation"])
        self.assertFalse(facts["admitted"])

    def test_15_pre_binding_historical_review_is_not_reused(self):
        historical = OrderCrossFunctionalReview.objects.create(
            company=self.company,
            source_record=self.source,
            review_type="CRM_ORDER_REVIEW",
            source_order_no="1-4-正",
            source_version=self.source.source_version,
            source_content_hash=self.source.content_hash,
            review_version=99,
            conclusion="ACCEPT",
            reviewer=self.user,
            idempotency_key="HISTORICAL-REVIEW",
            audit_hash="b" * 64,
            record_status="SUBMITTED",
        )
        self._call()
        with self.assertRaises(CRMOrderAdmissionError) as caught:
            require_current_crm_sales_order_admission(order=self.order)
        self.assertEqual(caught.exception.code, "CRM_ORDER_REVIEW_MISSING")
        self.assertNotEqual(
            (caught.exception.details.get("currentReview") or {}).get("reviewId"),
            historical.pk,
        )

    def test_16_admin_actor_is_forbidden(self):
        admin = User.objects.create_superuser(
            username="crm_source_admin",
            password="unused",
            real_name="管理员",
            company_id=self.company.pk,
        )
        with self.assertRaises(SalesOrderCRMSourceEstablishmentError) as caught:
            self._call(actor=admin)
        self.assertEqual(caught.exception.code, "SALES_IDENTITY_CORRECTION_ADMIN_FORBIDDEN")

    def test_17_audit_contains_actor_scope_and_zero_forbidden_writes(self):
        result = self._call()
        audit = OrganizationOperatingAuditRecord.objects.get(
            pk=result["organizationAuditId"],
        )
        request = MasterDataWriteRequest.objects.get(pk=result["writeRequestId"])
        self.assertEqual(audit.action_code, ACTION_CODE)
        self.assertEqual(audit.actor, self.user)
        self.assertEqual(audit.after_snapshot["actor"]["employeeNo"], "CRM-SRC-E001")
        self.assertEqual(audit.after_snapshot["relation0032WriteCount"], 0)
        self.assertEqual(audit.after_snapshot["relation0033WriteCount"], 0)
        self.assertEqual(audit.after_snapshot["authorizationWriteCount"], 0)
        self.assertEqual(request.status, MasterDataWriteRequest.Status.COMMITTED)
        self.assertEqual(request.source_identity_id, result["sourceIdentityId"])
