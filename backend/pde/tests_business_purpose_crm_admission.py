from datetime import date

from django.test import TestCase

from sales.models import Customer, SalesOrder
from system.models import Company, Department, User

from .crm_order_admission import (
    CRMOrderAdmissionError,
    candidate_analysis_crm_sales_order_admission_facts,
    current_crm_sales_order_admission_facts,
    require_current_crm_sales_order_admission,
)
from .models import EngineeringSourceRecord, OrderCrossFunctionalReview, OrderReviewSalesOrderRelation


class BusinessPurposeCRMAdmissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="BP-CRM", name="用途CRM准入测试公司")
        cls.department = Department.objects.create(
            company=cls.company,
            code="BP-CRM-SALES",
            name="销售部",
        )
        cls.customer = Customer.objects.create(
            company=cls.company,
            code="BP-CRM-C",
            name="用途CRM准入测试客户",
        )
        cls.user = User.objects.create_user(
            username="bp-crm-user",
            password="test",
            real_name="用途CRM测试用户",
            company_id=cls.company.pk,
        )

    def _order(self, *, order_no, purpose=None, marker=""):
        order = SalesOrder(
            company=self.company,
            department=self.department,
            customer=self.customer,
            order_no=order_no,
            order_date=date(2026, 10, 3),
            required_delivery_date=date(2026, 11, 3),
            order_type="standard",
            order_source="crm",
            business_purpose=purpose,
            project_reference="BP-CRM-PROJECT",
            contract_reference="BP-CRM-CONTRACT",
            status="draft",
            acceptance_marker=marker,
            created_by=self.user,
        )
        order._business_state_initialization_authorized = True
        order.save()
        return order

    def test_development_validation_makes_formal_review_not_applicable(self):
        order = self._order(
            order_no="BP-CRM-DEV",
            purpose=SalesOrder.BusinessPurpose.DEVELOPMENT_VALIDATION,
            marker="DEVELOPMENT_ONLY",
        )
        counts_before = (
            EngineeringSourceRecord.objects.count(),
            OrderCrossFunctionalReview.objects.count(),
            OrderReviewSalesOrderRelation.objects.count(),
        )

        with self.assertRaises(CRMOrderAdmissionError) as caught:
            require_current_crm_sales_order_admission(order=order, lock=True)
        facts = current_crm_sales_order_admission_facts(order)

        self.assertEqual(caught.exception.code, "CRM_ORDER_FORMAL_REVIEW_NOT_APPLICABLE")
        self.assertEqual(facts["statusLabel"], "正式CRM订单评审不适用")
        self.assertFalse(facts["formalReviewApplicable"])
        self.assertTrue(facts["developmentValidationAllowed"])
        self.assertFalse(facts["submitAllowed"])
        self.assertEqual(facts["businessPurpose"]["factSource"], "PERSISTED_BUSINESS_PURPOSE")
        self.assertEqual(
            counts_before,
            (
                EngineeringSourceRecord.objects.count(),
                OrderCrossFunctionalReview.objects.count(),
                OrderReviewSalesOrderRelation.objects.count(),
            ),
        )

    def test_formal_sale_without_current_source_remains_blocked(self):
        order = self._order(
            order_no="BP-CRM-FORMAL",
            purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
        )

        with self.assertRaises(CRMOrderAdmissionError) as caught:
            require_current_crm_sales_order_admission(order=order)
        facts = current_crm_sales_order_admission_facts(order)

        self.assertEqual(caught.exception.code, "CRM_ORDER_CURRENT_SOURCE_REQUIRED")
        self.assertTrue(facts["formalReviewApplicable"])
        self.assertFalse(facts["submitAllowed"])
        self.assertEqual(facts["businessPurpose"]["businessPurpose"], "FORMAL_SALE")

    def test_null_purpose_fails_closed_even_when_legacy_mapping_exists(self):
        order = self._order(order_no="BP-CRM-NULL", marker="DEVELOPMENT_ONLY")

        with self.assertRaises(CRMOrderAdmissionError) as caught:
            require_current_crm_sales_order_admission(order=order)
        facts = current_crm_sales_order_admission_facts(order)
        candidate_facts = candidate_analysis_crm_sales_order_admission_facts(order)

        self.assertEqual(caught.exception.code, "BUSINESS_PURPOSE_REQUIRED")
        self.assertEqual(facts["statusLabel"], "订单业务用途待确认")
        self.assertEqual(facts["businessPurpose"]["factSource"], "LEGACY_MAPPING")
        self.assertFalse(facts["submitAllowed"])
        self.assertEqual(candidate_facts["statusCode"], "CRM_ORDER_DEVELOPMENT_ONLY")

    def test_system_test_is_isolated_from_formal_crm_review(self):
        order = self._order(
            order_no="BP-CRM-TEST",
            purpose=SalesOrder.BusinessPurpose.SYSTEM_TEST,
        )

        with self.assertRaises(CRMOrderAdmissionError) as caught:
            require_current_crm_sales_order_admission(order=order)

        self.assertEqual(caught.exception.code, "CRM_ORDER_SYSTEM_TEST_ISOLATED")

