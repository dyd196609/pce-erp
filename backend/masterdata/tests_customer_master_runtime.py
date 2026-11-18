from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from sales.models import Customer
from system.models import Company, User

from .enterprise_master_data import ENTITY_DEFINITIONS
from .views import EnterpriseMasterDataFactsView


class CustomerMasterRuntimeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="CUSTOMER-RT", name="客户运行时测试公司")
        cls.other_company = Company.objects.create(code="CUSTOMER-X", name="客户隔离测试公司")
        cls.user = User.objects.create_user(
            username="customer-runtime-user",
            real_name="客户运行时测试用户",
            company_id=cls.company.pk,
        )
        cls.customer = Customer.objects.create(
            company=cls.company,
            code="CUST-RUNTIME-001",
            name="正式客户运行时事实",
        )
        Customer.objects.create(
            company=cls.other_company,
            code="CUST-OTHER-001",
            name="其他公司客户",
        )

    def test_customer_definition_contains_no_fixture_rows(self):
        self.assertEqual(ENTITY_DEFINITIONS["customers"]["rows"], [])

    def test_customer_page_reads_tenant_scoped_sales_customer(self):
        request = APIRequestFactory().get(
            "/api/masterdata/enterprise/customers/facts/"
        )
        force_authenticate(request, user=self.user)
        response = EnterpriseMasterDataFactsView.as_view()(
            request, entity_code="customers"
        )
        response.render()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["recordCount"], 1)
        self.assertEqual(response.data["rows"][0]["customerCode"], self.customer.code)
        self.assertEqual(response.data["dataSource"], "sales.Customer")
        self.assertEqual(response.data["databaseTable"], "sales_customer")
        self.assertTrue(response.data["formalFact"])
        self.assertFalse(response.data["demoFixtureIncluded"])
        self.assertEqual(response.data["businessProgressWriteCount"], 0)
