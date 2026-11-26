from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from workflow_runtime.fact_loads import FACT_LOAD_CONTRACT_VERSION

from .engineering_calculation_service import EngineeringCalculationError
from .views import EngineeringCalculationReadinessView, ProductDefinitionListView, _facts, _read_failure


class MultiModuleReadRecoveryContractTests(SimpleTestCase):
    def test_successful_empty_and_nonempty_reads_are_distinct(self):
        request = RequestFactory().get("/api/pde/example/")
        request.user = SimpleNamespace(company_id=1)

        empty = _facts("example", [], request)
        populated = _facts("example", [{"id": 1}], request)

        self.assertEqual(empty["factLoadStatus"], "empty_valid")
        self.assertEqual(empty["apiFacts"]["recordCount"], 0)
        self.assertEqual(populated["factLoadStatus"], "loaded")
        self.assertEqual(populated["apiFacts"]["recordCount"], 1)

    def test_failed_read_never_reports_zero_or_empty_success(self):
        request = RequestFactory().get("/api/pde/product-definitions/")
        request.user = SimpleNamespace(company_id=1)

        response = _read_failure(
            request,
            status_code=503,
            error_code="SERVER_FACT_READ_FAILED",
            error_message="Server fact read failed",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["factLoadContractVersion"], FACT_LOAD_CONTRACT_VERSION)
        self.assertEqual(response.data["factLoadStatus"], "read_failed")
        self.assertIsNone(response.data["resultCount"])
        self.assertIsNone(response.data["recordCount"])
        self.assertEqual(response.data["error"]["code"], "SERVER_FACT_READ_FAILED")

    def test_schema_failure_preserves_diagnostic_details_without_empty_facts(self):
        request = RequestFactory().get("/api/pde/a1-foundation/")
        request.user = SimpleNamespace(company_id=1)

        response = _read_failure(
            request,
            status_code=503,
            error_code="PRODUCTION_FOUNDATION_SCHEMA_UNAVAILABLE",
            error_message="企业基础资料服务端结构未就绪，当前数据数量未知。",
            details={"missingTables": ["pde_product_design_item"]},
            extra={"recordCounts": None, "facts": None},
        )

        self.assertEqual(response.data["factLoadStatus"], "read_failed")
        self.assertIsNone(response.data["recordCounts"])
        self.assertIsNone(response.data["facts"])
        self.assertEqual(
            response.data["error"]["details"]["missingTables"],
            ["pde_product_design_item"],
        )

    def test_product_design_without_identity_is_401_not_empty(self):
        request = APIRequestFactory().get("/api/pde/product-definitions/")
        response = ProductDefinitionListView.as_view()(request)

        self.assertEqual(response.status_code, 401)

    @patch("pde.views.EngineeringCalculationReadinessService.build")
    def test_engineering_permission_denial_is_403_not_login_or_empty(self, build):
        build.side_effect = EngineeringCalculationError(
            "PERMISSION_DENIED", "当前账号无查看权限"
        )
        request = APIRequestFactory().get(
            "/api/pde/a1-engineering/calculations/readiness/",
            {"subview": "semi-finished-structure"},
        )
        force_authenticate(
            request,
            user=SimpleNamespace(company_id=1, is_authenticated=True),
        )

        response = EngineeringCalculationReadinessView.as_view()(request)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["factLoadStatus"], "read_failed")
        self.assertIsNone(response.data["resultCount"])
