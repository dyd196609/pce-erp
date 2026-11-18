from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase
from django.utils import timezone

from masterdata.models import ExternalIdentity, Material, MasterDataWriteRequest, UnitOfMeasure
from pfm.models import Employee
from sales.crm_source_establishment import (
    SOURCE_OBJECT_TYPE,
    SOURCE_SYSTEM,
    SOURCE_TYPE,
    TARGET_ENTITY_TYPE,
)
from sales.models import (
    Customer,
    SalesOrder,
    SalesOrderItem,
    SalesOrderItemEngineeringAttribute,
)
from system.models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    Permission,
    Position,
    PositionWorkflowResponsibility,
    Responsibility,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)

from .crm_order_admission import (
    CRMOrderAdmissionError,
    current_crm_sales_order_admission_facts,
    require_current_order_admission,
)
from .legacy_inflight_order_adoption import (
    ACTION_CODE,
    ADMISSION_MODE,
    LegacyInFlightOrderAdoptionError,
    adopt_legacy_inflight_order,
    build_legacy_adoption_evidence,
    evidence_hash,
    require_active_legacy_adoption,
    revoke_legacy_inflight_order_adoption,
)
from .models import (
    BOMVersion,
    EngineeringCalculationRecord,
    EngineeringSourceRecord,
    LegacyInFlightOrderAdoption,
    LegacyInFlightOrderAdoptionRevocation,
    OrderCrossFunctionalReview,
    OrderEngineeringBaseline,
    OrderEngineeringBaselineItem,
    OrderEngineeringInstance,
    OrderReviewSalesOrderRelation,
    PDEEngineeringPreparationAuthorization,
    PDEReviewPredecessorRelation,
    ProductBOM,
    ProductCategory,
    ProductDefinition,
    ProductDesignCompletionRecord,
    ProductDesignItem,
    ProductVersion,
)


class LegacyInFlightOrderAdoptionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="LIA", name="历史在制承接测试公司")
        cls.department = Department.objects.create(
            company=cls.company, code="LIA-PLAN", name="计划物控部",
        )
        cls.position = Position.objects.create(
            company=cls.company, department=cls.department,
            code="LIA-PLAN-POS", name="历史在制承接计划岗",
        )
        cls.actor = User.objects.create_user(
            username="lia_plan_operator", password="unused", real_name="历史承接计划员",
            company_id=cls.company.pk,
        )
        Employee.objects.create(
            user=cls.actor, employee_no="LIA-E001", full_name="历史承接计划员",
            status="active", department_ref=cls.department, position_ref=cls.position,
        )
        permission, _ = Permission.objects.get_or_create(
            code="production.engineering.source.maintain",
            defaults={"name": "维护工程来源", "module": "production"},
        )
        cls.role = Role.objects.create(code="LIA_PLAN_ROLE", name="历史承接测试计划角色")
        RolePermission.objects.create(role=cls.role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=cls.actor, role=cls.role, organization=cls.company,
            scope_code="ORGANIZATION", active=True, version=1,
            business_hash="lia-plan-role",
        )
        cls.responsibility = Responsibility.objects.create(
            code="RESP_LIA_PLAN", name="历史在制订单正式承接",
            status="ACTIVE", is_active=True,
        )
        cls.workflow_mapping = PositionWorkflowResponsibility.objects.create(
            position=cls.position,
            responsibility=cls.responsibility,
            workflow_code="PLAN_DEMAND_TO_SUPPLY_PLAN",
            node_code="LEGACY_IN_FLIGHT_ADOPTION",
            ownership_type="OWNER",
            active=True,
        )
        cls.customer = Customer.objects.create(
            company=cls.company, code="LIA-C", name="上海王燕",
        )
        cls.uom = UnitOfMeasure.objects.create(
            company_id=cls.company.pk, code="LIA-PCS", name="件",
            dimension="count", decimal_places=6,
        )
        cls.material = Material.objects.create(
            company_id=cls.company.pk, code="LIA-FG", name="历史按单产品",
            unit="件", base_uom=cls.uom, material_type="finished",
            is_produced=True, is_active=True,
        )
        cls.category = ProductCategory.objects.create(
            company=cls.company, code="LIA-CAT", name="历史按单产品类",
            industry_type="general",
        )
        cls.product = ProductDefinition.objects.create(
            company=cls.company, category=cls.category, material=cls.material,
            product_code="LIA-P", product_name="历史按单产品",
            emd_material_code=cls.material.code,
            manufacturing_definition_mode="order_engineered",
        )
        cls.product_version = ProductVersion.objects.create(
            product=cls.product, version_no="V1",
        )
        cls.order = SalesOrder(
            company=cls.company,
            department=cls.department,
            customer=cls.customer,
            order_no="SO-LIA-001",
            order_date=date.today() - timedelta(days=30),
            required_delivery_date=date.today() + timedelta(days=30),
            order_type="project",
            order_source="crm",
            business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
            project_reference="上海 大居苑",
            external_source_no="1-4-正",
            status="engineering",
            version=1,
            created_by=cls.actor,
        )
        cls.order._business_state_initialization_authorized = True
        cls.order.save()
        cls.items = []
        cls.attributes = []
        for line_no in range(1, 5):
            item = SalesOrderItem.objects.create(
                sales_order=cls.order,
                line_no=line_no,
                material=cls.material,
                product_definition=cls.product,
                product_version=cls.product_version,
                engineering_mode="ORDER_ENGINEERED",
                quantity=Decimal("1"),
                uom=cls.uom,
                required_date=cls.order.required_delivery_date,
                customer_product_name=f"历史按单产品{line_no}",
                external_line_no=f"LIA-LINE-{line_no}",
            )
            cls.items.append(item)
        cls.source = EngineeringSourceRecord.objects.create(
            company=cls.company,
            source_no="LIA-SOURCE",
            source_name="历史订单工程来源",
            source_type="controlled_import",
            source_version="R-HISTORICAL",
            source_payload={
                "businessOrderReference": {
                    "sourceOrderNo": "1-4-正",
                    "customerName": "上海王燕",
                    "projectName": "上海大居苑",
                },
                "engineeringRows": [
                    {"id": f"LIA-ROW-{line_no}", "quantity": "1"}
                    for line_no in range(1, 5)
                ],
            },
            content_hash="a" * 64,
            status="confirmed",
        )
        cls.design_items = []
        for line_no, item in enumerate(cls.items, 1):
            attribute = SalesOrderItemEngineeringAttribute.objects.create(
                sales_order_item=item,
                sequence=1,
                raw_source="LIA-SOURCE",
                raw_field="sourceRow",
                raw_value={"id": f"LIA-ROW-{line_no}"},
                canonical_field="source_row",
                normalized_value=f"LIA-ROW-{line_no}",
                value_type="string",
                unit=cls.uom,
                source_type="ENGINEERING_INPUT",
                created_by=cls.actor,
            )
            cls.attributes.append(attribute)
            design = ProductDesignItem.objects.create(
                company=cls.company,
                sales_order_item=item,
                source_record=cls.source,
                source_attribute=attribute,
                item_no=f"LIA-DES-{line_no}",
                item_name=f"历史设计项{line_no}",
                original_requirement={"sourceRowId": f"LIA-ROW-{line_no}"},
                existing_design_data={"preserved": True},
                source_version=cls.source.source_version,
                source_content_hash=cls.source.content_hash,
                match_results={},
            )
            cls.design_items.append(design)
            ProductDesignCompletionRecord.objects.create(
                design_item=design,
                sequence=1,
                completion_nature="HISTORICAL_EVIDENCE",
                actual_completion_date=date.today() - timedelta(days=20),
                completion_basis="历史在制完成事实",
                recorded_by=cls.actor,
                action_code="pde.product_design.complete",
            )
        cls.baseline = OrderEngineeringBaseline(
            company=cls.company,
            sales_order=cls.order,
            baseline_no="EB-SO-LIA-001",
            sequence=1,
            status="draft",
            reason="历史完整基线",
            candidate_hash="b" * 64,
            snapshot_hash="c" * 64,
            scope_item_count=4,
            confirmable_item_count=4,
            blocker_count=0,
            blocker_summary={},
            version=1,
            created_by=cls.actor,
        )
        cls.baseline._business_state_initialization_authorized = True
        cls.baseline.save()
        for design, attribute in zip(cls.design_items, cls.attributes):
            OrderEngineeringBaselineItem.objects.create(
                baseline=cls.baseline,
                design_item=design,
                source_record=cls.source,
                source_attribute=attribute,
                source_type="PERSISTED_DESIGN_CONTENT",
                item_no_snapshot=design.item_no,
                item_name_snapshot=design.item_name,
                design_item_version=design.version,
                source_version_snapshot=cls.source.source_version,
                source_content_hash_snapshot=cls.source.content_hash,
                content_snapshot={"designItemId": design.pk},
                content_hash=(f"{design.pk:064x}"[-64:]),
                confirmable=True,
            )
        OrderEngineeringBaseline.objects.filter(pk=cls.baseline.pk).update(
            status="confirmed", confirmed_by=cls.actor, confirmed_at=timezone.now(),
        )
        cls.baseline.refresh_from_db()
        cls.instances = []
        cls.calculations = []
        for line_no, item in enumerate(cls.items, 1):
            instance = OrderEngineeringInstance.objects.create(
                company=cls.company,
                instance_no=f"OEI-LIA-{line_no}",
                sales_order_item=item,
                product=cls.product,
                baseline_product_version=cls.product_version,
                source_record=cls.source,
                status="calculated",
            )
            cls.instances.append(instance)
            calculation = EngineeringCalculationRecord.objects.create(
                company=cls.company,
                scope="order_engineering",
                source_record=cls.source,
                sales_order_item=item,
                engineering_instance=instance,
                calculation_no=f"CALC-LIA-{line_no}",
                rule_set_version="LIA-RULESET-V1",
                revision=1,
                idempotency_key=f"{line_no:064x}",
                input_hash="d" * 64,
                rule_graph_hash="e" * 64,
                result_hash=(f"{line_no + 10:064x}"[-64:]),
                status="completed",
                error_classification="none",
                started_at=timezone.now(),
                finished_at=timezone.now(),
            )
            cls.calculations.append(calculation)
        for offset in (2, 3):
            instance = cls.instances[offset]
            calculation = cls.calculations[offset]
            bom = ProductBOM.objects.create(
                applicability_scope="ORDER_ENGINEERING",
                order_engineering_instance=instance,
                company=cls.company,
                bom_code=f"OBOM-{instance.instance_no}",
                name=f"历史BOM-{offset + 1}",
                bom_type="manufacturing",
                status="draft",
                is_active=True,
            )
            BOMVersion.objects.create(
                bom=bom,
                bom_version=f"CALC-{calculation.pk}",
                revision=1,
                bom_scope="order_specific",
                order_engineering_instance=instance,
                source_calculation=calculation,
                preview_hash=(f"{offset + 20:064x}"[-64:]),
                generation_key=(f"{offset + 30:064x}"[-64:]),
                status="draft",
            )
        cls.review = OrderCrossFunctionalReview.objects.create(
            company=cls.company,
            source_record=cls.source,
            review_type="CRM_ORDER_REVIEW",
            source_order_no="1-4-正",
            source_version=cls.source.source_version,
            source_content_hash=cls.source.content_hash,
            review_version=1,
            conclusion="REJECT",
            review_opinion="历史拒绝原样保留",
            evidence={},
            missing_conditions=[],
            responsibility_feedback={},
            reviewer=cls.actor,
            idempotency_key="LIA-HISTORICAL-REVIEW",
            audit_hash="f" * 64,
            record_status="SUBMITTED",
            submitted_at=timezone.now(),
        )
        cls.identity = ExternalIdentity.objects.create(
            organization_id=cls.company.pk,
            source_system=SOURCE_SYSTEM,
            source_type=SOURCE_TYPE,
            source_object_type=SOURCE_OBJECT_TYPE,
            external_id=(
                f"EngineeringSourceRecord:{cls.source.pk}:{cls.source.source_version}"
            ),
            target_entity_type=TARGET_ENTITY_TYPE,
            target_entity_id=str(cls.order.pk),
            mapping_status=ExternalIdentity.MappingStatus.MATCH,
            source_fingerprint=cls.source.content_hash,
            audit_metadata={
                "sourceRecordId": cls.source.pk,
                "sourceVersion": cls.source.source_version,
                "sourceContentHash": cls.source.content_hash,
                "salesOrderId": cls.order.pk,
                "salesOrderNo": cls.order.order_no,
            },
        )
        cutoff = MigrationRecorder.Migration.objects.filter(
            app="pde", name="0032_order_review_sales_order_relation",
        ).values_list("applied", flat=True).get()
        cls.historical_at = cutoff - timedelta(days=1)
        SalesOrder.objects.filter(pk=cls.order.pk).update(created_at=cls.historical_at)
        ProductDesignItem.objects.filter(pk__in=[row.pk for row in cls.design_items]).update(
            created_at=cls.historical_at,
        )
        ProductDesignCompletionRecord.objects.filter(
            design_item_id__in=[row.pk for row in cls.design_items],
        ).update(recorded_at=cls.historical_at)
        OrderEngineeringBaseline.objects.filter(pk=cls.baseline.pk).update(
            created_at=cls.historical_at, confirmed_at=cls.historical_at,
        )
        OrderEngineeringInstance.objects.filter(pk__in=[row.pk for row in cls.instances]).update(
            created_at=cls.historical_at,
        )
        EngineeringCalculationRecord.objects.filter(
            pk__in=[row.pk for row in cls.calculations],
        ).update(
            created_at=cls.historical_at,
            started_at=cls.historical_at,
            finished_at=cls.historical_at,
        )
        OrderCrossFunctionalReview.objects.filter(pk=cls.review.pk).update(
            created_at=cls.historical_at,
            submitted_at=cls.historical_at,
        )
        cls.order.refresh_from_db()
        cls.baseline.refresh_from_db()
        cls.instances = list(OrderEngineeringInstance.objects.filter(
            pk__in=[row.pk for row in cls.instances],
        ).order_by("pk"))
        cls.calculations = list(EngineeringCalculationRecord.objects.filter(
            pk__in=[row.pk for row in cls.calculations],
        ).order_by("pk"))

    def _adopt(self, **overrides):
        values = {
            "actor": self.actor,
            "order_id": self.order.pk,
            "expected_order_no": self.order.order_no,
            "expected_source_record_id": self.source.pk,
            "expected_source_identity_id": self.identity.pk,
            "expected_engineering_baseline_id": self.baseline.pk,
            "expected_order_engineering_instance_ids": [row.pk for row in self.instances],
            "expected_engineering_calculation_ids": [row.pk for row in self.calculations],
            "idempotency_key": "SO-LIA-001-ADOPT-20261005",
            "business_reason": "经用户授权承接新Admission模型上线前已形成工程成果的真实历史订单。",
        }
        values.update(overrides)
        return adopt_legacy_inflight_order(**values)

    def _error(self, code, call=None):
        with self.assertRaises(LegacyInFlightOrderAdoptionError) as caught:
            (call or self._adopt)()
        self.assertEqual(caught.exception.code, code)

    def test_01_eligible_historical_order_is_adopted(self):
        result = self._adopt()
        self.assertEqual(result["admissionMode"], ADMISSION_MODE)
        self.assertEqual(LegacyInFlightOrderAdoption.objects.count(), 1)
        self.assertEqual(result["reviewWriteCount"], 0)

    def test_02_non_formal_business_purpose_fails_closed(self):
        SalesOrder.objects.filter(pk=self.order.pk).update(business_purpose="SYSTEM_TEST")
        self.order.refresh_from_db()
        self._error("LEGACY_ADOPTION_FORMAL_SALE_REQUIRED")

    def test_03_cancelled_order_fails_closed(self):
        self.order.status = "cancelled"
        self.order._business_state_transition_authorized = True
        self.order.save(update_fields=["status"])
        self._error("LEGACY_ADOPTION_CANCELLED_ORDER_FORBIDDEN")

    def test_04_missing_current_source_fails_closed(self):
        ExternalIdentity.objects.filter(pk=self.identity.pk).delete()
        self._error("LEGACY_ADOPTION_CURRENT_SOURCE_REQUIRED")

    def test_05_multiple_current_sources_fail_closed(self):
        ExternalIdentity.objects.create(
            organization_id=self.company.pk,
            source_system=SOURCE_SYSTEM,
            source_type=SOURCE_TYPE,
            source_object_type=SOURCE_OBJECT_TYPE,
            external_id="SECOND-CURRENT-SOURCE",
            target_entity_type=TARGET_ENTITY_TYPE,
            target_entity_id=str(self.order.pk),
            mapping_status=ExternalIdentity.MappingStatus.MATCH,
            source_fingerprint=self.source.content_hash,
            audit_metadata={"sourceRecordId": self.source.pk},
        )
        self._error("CRM_ORDER_CURRENT_SOURCE_AMBIGUOUS")

    def test_06_source_identity_fingerprint_mismatch_fails_closed(self):
        ExternalIdentity.objects.filter(pk=self.identity.pk).update(source_fingerprint="0" * 64)
        self._error("CRM_SOURCE_BINDING_STALE")

    def test_07_customer_conflict_fails_closed(self):
        customer = Customer.objects.create(company=self.company, code="LIA-C2", name="其他客户")
        SalesOrder.objects.filter(pk=self.order.pk).update(customer=customer)
        self.order.refresh_from_db()
        self._error("CRM_SOURCE_BUSINESS_IDENTITY_MISMATCH")

    def test_08_project_conflict_fails_closed(self):
        SalesOrder.objects.filter(pk=self.order.pk).update(project_reference="其他项目")
        self.order.refresh_from_db()
        self._error("CRM_SOURCE_BUSINESS_IDENTITY_MISMATCH")

    def test_09_external_source_number_conflict_fails_closed(self):
        SalesOrder.objects.filter(pk=self.order.pk).update(external_source_no="OTHER")
        self.order.refresh_from_db()
        self._error("CRM_SOURCE_BUSINESS_IDENTITY_MISMATCH")

    def test_10_admission_revocation_fails_closed(self):
        counts = {"relation0032": 0, "relation0033": 0, "authorization": 0, "admissionRevocation": 1}
        with patch("pde.legacy_inflight_order_adoption._relation_counts", return_value=counts):
            self._error("LEGACY_ADOPTION_ADMISSION_REVOCATION_PRESENT")

    def test_11_existing_0032_fails_closed(self):
        relation = OrderReviewSalesOrderRelation(
            company=self.company,
            review=self.review,
            sales_order=self.order,
            scope_mode="WHOLE_ORDER",
            order_version_snapshot=self.order.version,
            source_content_hash_snapshot=self.source.content_hash,
            resolution_basis="APPROVED_HISTORICAL_MANIFEST",
            scope_reason="test only",
            created_by=self.actor,
            audit_hash="1" * 64,
        )
        relation.save()
        self._error("LEGACY_ADOPTION_0032_PRESENT")

    def test_12_existing_0033_fails_closed(self):
        counts = {"relation0032": 0, "relation0033": 1, "authorization": 0, "admissionRevocation": 0}
        with patch("pde.legacy_inflight_order_adoption._relation_counts", return_value=counts):
            self._error("LEGACY_ADOPTION_0033_PRESENT")

    def test_13_existing_authorization_fails_closed(self):
        counts = {"relation0032": 0, "relation0033": 0, "authorization": 1, "admissionRevocation": 0}
        with patch("pde.legacy_inflight_order_adoption._relation_counts", return_value=counts):
            self._error("LEGACY_ADOPTION_AUTHORIZATION_PRESENT")

    def test_14_unconfirmed_baseline_fails_closed(self):
        OrderEngineeringBaseline.objects.filter(pk=self.baseline.pk).update(status="draft")
        self._error("LEGACY_ADOPTION_CONFIRMED_BASELINE_AMBIGUOUS")

    def test_15_incomplete_baseline_fails_closed(self):
        OrderEngineeringBaseline.objects.filter(pk=self.baseline.pk).update(blocker_count=1)
        self._error("LEGACY_ADOPTION_BASELINE_INCOMPLETE")

    def test_16_incomplete_oei_scope_fails_closed(self):
        OrderEngineeringInstance.objects.filter(pk=self.instances[0].pk).update(status="inactive")
        self._error("LEGACY_ADOPTION_OEI_SCOPE_INCOMPLETE")

    def test_17_incomplete_calculation_scope_fails_closed(self):
        EngineeringCalculationRecord.objects.filter(pk=self.calculations[0].pk).update(status="obsolete")
        self._error("LEGACY_ADOPTION_CALCULATION_SCOPE_INCOMPLETE")

    def test_18_post_cutoff_order_fails_closed(self):
        SalesOrder.objects.filter(pk=self.order.pk).update(created_at=timezone.now())
        self.order.refresh_from_db()
        self._error("LEGACY_ADOPTION_POST_MODEL_EVIDENCE_FORBIDDEN")

    def test_19_post_cutoff_design_fails_closed(self):
        ProductDesignItem.objects.filter(pk=self.design_items[0].pk).update(created_at=timezone.now())
        self._error("LEGACY_ADOPTION_POST_MODEL_EVIDENCE_FORBIDDEN")

    def test_20_post_cutoff_baseline_fails_closed(self):
        OrderEngineeringBaseline.objects.filter(pk=self.baseline.pk).update(created_at=timezone.now())
        self._error("LEGACY_ADOPTION_POST_MODEL_EVIDENCE_FORBIDDEN")

    def test_21_post_cutoff_oei_fails_closed(self):
        OrderEngineeringInstance.objects.filter(pk=self.instances[0].pk).update(created_at=timezone.now())
        self._error("LEGACY_ADOPTION_POST_MODEL_EVIDENCE_FORBIDDEN")

    def test_22_post_cutoff_calculation_fails_closed(self):
        EngineeringCalculationRecord.objects.filter(pk=self.calculations[0].pk).update(
            created_at=timezone.now(), finished_at=timezone.now(),
        )
        self._error("LEGACY_ADOPTION_POST_MODEL_EVIDENCE_FORBIDDEN")

    def test_23_new_order_with_partial_downstream_facts_cannot_adopt(self):
        SalesOrder.objects.filter(pk=self.order.pk).update(created_at=timezone.now())
        self.order.refresh_from_db()
        self._error("LEGACY_ADOPTION_POST_MODEL_EVIDENCE_FORBIDDEN")

    def test_24_repeated_execution_is_idempotent(self):
        first = self._adopt()
        second = self._adopt()
        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(first["legacyAdoptionId"], second["legacyAdoptionId"])
        self.assertEqual(LegacyInFlightOrderAdoption.objects.count(), 1)

    def test_25_evidence_hash_is_stable(self):
        first = build_legacy_adoption_evidence(order=self.order)
        second = build_legacy_adoption_evidence(order=self.order)
        self.assertEqual(first["evidenceHash"], second["evidenceHash"])
        self.assertEqual(first["evidenceHash"], evidence_hash(first["evidence"]))

    def test_26_adoption_cannot_be_updated_through_domain_model(self):
        adoption = LegacyInFlightOrderAdoption.objects.get(pk=self._adopt()["legacyAdoptionId"])
        adoption.business_reason = "attempted overwrite"
        with self.assertRaises(ValidationError):
            adoption.save()

    def test_27_adoption_cannot_be_deleted(self):
        adoption = LegacyInFlightOrderAdoption.objects.get(pk=self._adopt()["legacyAdoptionId"])
        with self.assertRaises(ValidationError):
            adoption.delete()

    def test_28_historical_reject_is_preserved_not_approval(self):
        result = self._adopt()
        exception = result["evidenceSnapshot"]["historicalReviewException"]
        self.assertEqual(exception["reviewId"], self.review.pk)
        self.assertEqual(exception["conclusion"], "REJECT")
        self.assertTrue(exception["preserved"])
        self.assertFalse(exception["usedAsApproval"])

    def test_29_no_standard_admission_objects_are_created(self):
        before = {
            "review": OrderCrossFunctionalReview.objects.count(),
            "relation": OrderReviewSalesOrderRelation.objects.count(),
            "predecessor": PDEReviewPredecessorRelation.objects.count(),
            "authorization": PDEEngineeringPreparationAuthorization.objects.count(),
        }
        self._adopt()
        after = {
            "review": OrderCrossFunctionalReview.objects.count(),
            "relation": OrderReviewSalesOrderRelation.objects.count(),
            "predecessor": PDEReviewPredecessorRelation.objects.count(),
            "authorization": PDEEngineeringPreparationAuthorization.objects.count(),
        }
        self.assertEqual(before, after)

    def test_30_protected_engineering_objects_are_not_modified(self):
        before = {
            "source": (self.source.status, self.source.content_hash, deepcopy(self.source.source_payload)),
            "baseline": (self.baseline.status, self.baseline.snapshot_hash),
            "oei": list(OrderEngineeringInstance.objects.values_list("pk", "status")),
            "calc": list(EngineeringCalculationRecord.objects.values_list("pk", "status", "result_hash")),
            "bom": list(ProductBOM.objects.values_list("pk", "status")),
            "bomVersion": list(BOMVersion.objects.values_list("pk", "status")),
        }
        self._adopt()
        self.source.refresh_from_db()
        self.baseline.refresh_from_db()
        after = {
            "source": (self.source.status, self.source.content_hash, deepcopy(self.source.source_payload)),
            "baseline": (self.baseline.status, self.baseline.snapshot_hash),
            "oei": list(OrderEngineeringInstance.objects.values_list("pk", "status")),
            "calc": list(EngineeringCalculationRecord.objects.values_list("pk", "status", "result_hash")),
            "bom": list(ProductBOM.objects.values_list("pk", "status")),
            "bomVersion": list(BOMVersion.objects.values_list("pk", "status")),
        }
        self.assertEqual(before, after)

    def test_31_scope_does_not_expand_to_new_order_line(self):
        self._adopt()
        SalesOrderItem.objects.create(
            sales_order=self.order, line_no=5, material=self.material,
            product_definition=self.product, product_version=self.product_version,
            engineering_mode="ORDER_ENGINEERED", quantity=1, uom=self.uom,
            required_date=self.order.required_delivery_date,
            customer_product_name="new line",
        )
        with self.assertRaises(LegacyInFlightOrderAdoptionError) as caught:
            require_active_legacy_adoption(order=self.order)
        self.assertEqual(caught.exception.code, "PDE_LEGACY_IN_FLIGHT_ORDER_SCOPE_DRIFT")

    def test_32_scope_rejects_unknown_calculation(self):
        self._adopt()
        with self.assertRaises(LegacyInFlightOrderAdoptionError) as caught:
            require_active_legacy_adoption(order=self.order, calculation_id=999999)
        self.assertEqual(caught.exception.code, "PDE_LEGACY_IN_FLIGHT_SCOPE_MISMATCH")

    def test_33_central_admission_returns_explicit_legacy_mode(self):
        result = self._adopt()
        admitted = require_current_order_admission(
            order=self.order,
            sales_order_item_id=self.items[0].pk,
            engineering_instance_id=self.instances[0].pk,
            calculation_id=self.calculations[0].pk,
        ).as_dict()
        self.assertEqual(admitted["admissionMode"], ADMISSION_MODE)
        self.assertEqual(admitted["legacyAdoptionId"], result["legacyAdoptionId"])
        self.assertIsNone(admitted["relationId"])

    def test_34_central_projection_keeps_standard_objects_null(self):
        self._adopt()
        facts = current_crm_sales_order_admission_facts(self.order)
        self.assertTrue(facts["admitted"])
        self.assertEqual(facts["admissionMode"], ADMISSION_MODE)
        self.assertIsNone(facts["currentReview"])
        self.assertIsNone(facts["currentRelation"])
        self.assertIsNone(facts["currentPredecessor"])
        self.assertIsNone(facts["currentAuthorization"])
        self.assertEqual(facts["historicalReviewException"]["conclusion"], "REJECT")

    def test_35_revocation_is_append_only_and_preserves_adoption(self):
        adoption_id = self._adopt()["legacyAdoptionId"]
        result = revoke_legacy_inflight_order_adoption(
            actor=self.actor,
            adoption_id=adoption_id,
            reason_code="EVIDENCE_INVALIDATED",
            reason="isolated revocation test",
            idempotency_key="LIA-REVOCATION-001",
        )
        self.assertEqual(LegacyInFlightOrderAdoption.objects.count(), 1)
        self.assertEqual(LegacyInFlightOrderAdoptionRevocation.objects.count(), 1)
        self.assertFalse(result["idempotent"])
        repeated = revoke_legacy_inflight_order_adoption(
            actor=self.actor,
            adoption_id=adoption_id,
            reason_code="EVIDENCE_INVALIDATED",
            reason="isolated revocation test",
            idempotency_key="LIA-REVOCATION-001",
        )
        self.assertTrue(repeated["idempotent"])

    def test_36_revoked_adoption_cannot_admit(self):
        adoption_id = self._adopt()["legacyAdoptionId"]
        revoke_legacy_inflight_order_adoption(
            actor=self.actor,
            adoption_id=adoption_id,
            reason_code="BUSINESS_IDENTITY_CONFLICT",
            reason="isolated identity conflict",
            idempotency_key="LIA-REVOCATION-002",
        )
        with self.assertRaises(CRMOrderAdmissionError) as caught:
            require_current_order_admission(order=self.order)
        self.assertEqual(caught.exception.code, "PDE_LEGACY_IN_FLIGHT_ADOPTION_REVOKED")

    def test_37_admin_actor_is_forbidden(self):
        admin = User.objects.create_superuser(
            username="lia_admin", password="unused", company_id=self.company.pk,
        )
        self._error(
            "LEGACY_ADOPTION_ADMIN_FORBIDDEN",
            call=lambda: self._adopt(actor=admin),
        )

    def test_38_actor_without_permission_is_forbidden(self):
        RolePermission.objects.filter(role=self.role).delete()
        self._error("LEGACY_ADOPTION_PERMISSION_DENIED")

    def test_39_actor_without_workflow_responsibility_is_forbidden(self):
        PositionWorkflowResponsibility.objects.filter(pk=self.workflow_mapping.pk).update(active=False)
        self._error("LEGACY_ADOPTION_WORKFLOW_RESPONSIBILITY_REQUIRED")

    def test_40_expected_scope_mismatch_fails_before_write(self):
        self._error(
            "LEGACY_ADOPTION_EXPECTED_SCOPE_MISMATCH",
            call=lambda: self._adopt(expected_engineering_baseline_id=999999),
        )
        self.assertEqual(LegacyInFlightOrderAdoption.objects.count(), 0)
        self.assertEqual(MasterDataWriteRequest.objects.filter(action_code=ACTION_CODE).count(), 0)

    def test_41_standard_gate_remains_fail_closed_without_adoption(self):
        with self.assertRaises(CRMOrderAdmissionError) as caught:
            require_current_order_admission(order=self.order)
        self.assertEqual(caught.exception.code, "CRM_ORDER_REVIEW_MISSING")

    def test_42_audit_and_action_request_are_complete(self):
        result = self._adopt()
        request = MasterDataWriteRequest.objects.get(pk=result["actionRequestId"])
        audit = OrganizationOperatingAuditRecord.objects.get(pk=result["auditId"])
        self.assertEqual(request.status, MasterDataWriteRequest.Status.COMMITTED)
        self.assertEqual(request.target_entity_id, str(result["legacyAdoptionId"]))
        self.assertEqual(audit.action_code, ACTION_CODE)
        self.assertEqual(audit.actor_id, self.actor.pk)

    def test_43_wrong_idempotency_replay_cannot_duplicate_adoption(self):
        self._adopt()
        self._error(
            "LEGACY_ADOPTION_ALREADY_EXISTS",
            call=lambda: self._adopt(idempotency_key="SO-LIA-001-SECOND-KEY"),
        )
        self.assertEqual(LegacyInFlightOrderAdoption.objects.count(), 1)

    def _additional_calculation(self, scope):
        original = self.calculations[0]
        return EngineeringCalculationRecord.objects.create(
            company=self.company, source_record=self.source, sales_order_item=self.items[0],
            engineering_instance=self.instances[0], scope=scope,
            origin_calculation=original if scope == "fact_extension" else None,
            supersedes=original if scope == "order_engineering" else None,
            calculation_no=f"LIA-ADDITIONAL-{scope}", rule_set_version="LIA-TEST-V1",
            revision=2 if scope == "order_engineering" else 1, status="completed",
            trace={"purpose": scope, "sourceSnapshot": {"sourceCalculationId": original.pk}},
            started_at=timezone.now(), finished_at=timezone.now(),
        )

    def test_44_non_main_completed_calculations_do_not_expand_frozen_main_scope(self):
        adoption_id = self._adopt()["legacyAdoptionId"]
        before = LegacyInFlightOrderAdoption.objects.filter(pk=adoption_id).values().get()
        extension = self._additional_calculation("fact_extension")
        requirement = self._additional_calculation("operation_requirement")
        admitted = require_current_order_admission(order=self.order,
            sales_order_item_id=self.items[0].pk, engineering_instance_id=self.instances[0].pk,
            calculation_id=self.calculations[0].pk).as_dict()
        self.assertEqual(admitted["admissionMode"], ADMISSION_MODE)
        self.assertEqual(admitted["scope"]["engineeringCalculationIds"], [row.pk for row in self.calculations])
        self.assertNotIn(extension.pk, admitted["scope"]["engineeringCalculationIds"])
        self.assertNotIn(requirement.pk, admitted["scope"]["engineeringCalculationIds"])
        self.assertEqual(before, LegacyInFlightOrderAdoption.objects.filter(pk=adoption_id).values().get())

    def test_45_real_new_main_calculation_still_blocks_without_scope_authorization(self):
        self._adopt()
        new_main = self._additional_calculation("order_engineering")
        for requested in (self.calculations[0].pk, new_main.pk):
            with self.subTest(requested=requested), self.assertRaises(CRMOrderAdmissionError) as caught:
                require_current_order_admission(order=self.order,
                    sales_order_item_id=self.items[0].pk, engineering_instance_id=self.instances[0].pk,
                    calculation_id=requested)
            self.assertEqual(caught.exception.code, "PDE_LEGACY_IN_FLIGHT_CALCULATION_SCOPE_DRIFT")

    def test_46_new_main_write_guard_preserves_real_legacy_scope_and_old_records(self):
        from .formal_engineering_continuation_service import _guard_consumed_legacy_revision
        from .engineering_calculation_service import EngineeringCalculationError
        adoption_id = self._adopt()["legacyAdoptionId"]
        self._additional_calculation("fact_extension")
        self._additional_calculation("operation_requirement")
        protected = {
            "adoption": LegacyInFlightOrderAdoption.objects.filter(pk=adoption_id).values().get(),
            "calculations": list(EngineeringCalculationRecord.objects.values().order_by("pk")),
            "audits": OrganizationOperatingAuditRecord.objects.count(),
            "requests": MasterDataWriteRequest.objects.count(),
        }
        with self.assertRaises(EngineeringCalculationError) as caught:
            _guard_consumed_legacy_revision(self.calculations[0], sales_item=self.items[0],
                instance=self.instances[0], baseline=self.baseline, company_id=self.company.pk)
        self.assertEqual(caught.exception.code, "LEGACY_MAIN_CALCULATION_CONTINUATION_REQUIRED")
        self.assertEqual(caught.exception.details["legacyAdoptionId"], adoption_id)
        self.assertEqual(caught.exception.details["previousCalculationId"], self.calculations[0].pk)
        self.assertEqual(caught.exception.details["businessWriteSideEffectCount"], 0)
        self.assertEqual(protected, {
            "adoption": LegacyInFlightOrderAdoption.objects.filter(pk=adoption_id).values().get(),
            "calculations": list(EngineeringCalculationRecord.objects.values().order_by("pk")),
            "audits": OrganizationOperatingAuditRecord.objects.count(),
            "requests": MasterDataWriteRequest.objects.count(),
        })
