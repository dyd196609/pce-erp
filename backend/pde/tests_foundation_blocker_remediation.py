from concurrent.futures import ThreadPoolExecutor
import time

from django.db import IntegrityError, OperationalError, close_old_connections
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from masterdata.models import (
    CodeRule, ExternalIdentity, MasterDataWriteRequest, Material, UnitOfMeasure,
)
from masterdata.uom_governance import UnitOfMeasureNormalizer
from pfm.models import Employee
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Position,
    PositionResponsibility, Process, Responsibility, Role, RolePermission, User,
    UserRoleScopeAssignment, Workshop,
)

from .models import WorkCenter, WorkCenterOperationCapability
from .production_foundation_service import ProductionFoundationError, ProductionFoundationService


class FoundationFormalWriteChainTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.company = Company.objects.create(code="FW1", name="Foundation Wave 1隔离测试公司")
        self.department = Department.objects.create(
            code="MFG", name="制造部", company=self.company,
            department_type=Department.DepartmentType.FUNCTIONAL,
        )
        self.user = User.objects.create_user(
            username="fw1_maintainer", password="test-only", real_name="制造基础维护员",
            company_id=self.company.pk,
        )
        role = Role.objects.create(code="FW1_MAINTAINER", name="制造基础维护角色")
        for code in (
            "production.master_data.material.maintain",
            "production.master_data.resource.maintain",
        ):
            permission, _ = Permission.objects.get_or_create(
                code=code, defaults={"name": code, "module": "PRODUCTION"},
            )
            RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=self.user, role=role, organization=self.company,
            scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            business_hash="fw1-isolated-test",
        )
        responsibility, _ = Responsibility.objects.get_or_create(
            code="ENTERPRISE_MASTER_DATA_MAINTAINER",
            defaults={
                "name": "企业主数据维护职责",
                "status": Responsibility.Status.ACTIVE,
                "is_active": True,
            },
        )
        position = Position.objects.create(
            code="FW1-POS", name="制造基础维护岗", company=self.company,
            department=self.department, default_role=role,
        )
        PositionResponsibility.objects.create(
            position=position, responsibility=responsibility, is_primary=True, active=True,
        )
        Employee.objects.create(
            user=self.user, employee_no="FW1-E001", full_name="制造基础维护员",
            department_ref=self.department, position_ref=position, status="active",
        )
        self.material_rule = CodeRule.objects.update_or_create(
            company_id=self.company.pk, entity_type="production_material",
            defaults={"prefix": "MAT", "date_format": "", "seq_length": 6, "current_seq": 0},
        )[0]
        self.workshop_rule = CodeRule.objects.update_or_create(
            company_id=self.company.pk, entity_type="production_workshop",
            defaults={"prefix": "WS", "date_format": "", "seq_length": 6, "current_seq": 0},
        )[0]
        self.work_center_rule = CodeRule.objects.update_or_create(
            company_id=self.company.pk, entity_type="production_work_center",
            defaults={"prefix": "WC", "date_format": "", "seq_length": 6, "current_seq": 0},
        )[0]

    def source(self, external_id="ROW-1"):
        return {
            "sourceSystem": "FW1_TEST",
            "sourceType": "XLSX",
            "sourceObjectType": "PURCHASE_MATERIAL_SOURCE",
            "externalId": external_id,
            "sourceFingerprint": "a" * 64,
            "auditMetadata": {"sheet": "采购物料", "row": 2},
        }

    def material_payload(self, name="隔离测试物料"):
        return {
            "company_id": self.company.pk, "name": name, "unit": "",
            "unit_status": "not_confirmed", "material_type": "raw",
            "is_purchased": True, "is_produced": False, "reason": "隔离测试",
        }

    def test_create_generates_material_code_and_persists_identity_audit_and_readback(self):
        result = ProductionFoundationService.write(
            "materials", user=self.user, payload=self.material_payload(),
            idempotency_key="FW1-CREATE-1", source_identity=self.source(),
        )
        material = Material.objects.get(pk=result["row"]["id"])
        identity = ExternalIdentity.objects.get()
        ledger = MasterDataWriteRequest.objects.get()
        self.assertEqual(material.code, "MAT000001")
        self.assertEqual(result["row"]["code"], material.code)
        self.assertEqual(identity.mapping_status, "MATCH")
        self.assertEqual(identity.target_entity_id, str(material.pk))
        self.assertEqual(ledger.status, "COMMITTED")
        self.assertEqual(ledger.target_entity_id, str(material.pk))
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 1)

    def test_duplicate_source_and_request_are_idempotent(self):
        first = ProductionFoundationService.write(
            "materials", user=self.user, payload=self.material_payload(),
            idempotency_key="FW1-IDEM-1", source_identity=self.source(),
        )
        second = ProductionFoundationService.write(
            "materials", user=self.user, payload=self.material_payload(),
            idempotency_key="FW1-IDEM-1", source_identity=self.source(),
        )
        third = ProductionFoundationService.write(
            "materials", user=self.user, payload=self.material_payload(),
            idempotency_key="FW1-IDEM-2", source_identity=self.source(),
        )
        self.assertEqual(first["row"]["id"], second["row"]["id"])
        self.assertEqual(first["row"]["id"], third["row"]["id"])
        self.assertTrue(second["idempotentReplay"])
        self.assertTrue(third["idempotentReplay"])
        self.assertEqual(Material.objects.count(), 1)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 1)
        self.assertEqual(MasterDataWriteRequest.objects.count(), 2)
        self.material_rule.refresh_from_db()
        self.assertEqual(self.material_rule.current_seq, 1)

    def test_same_idempotency_key_with_different_payload_is_rejected(self):
        ProductionFoundationService.write(
            "materials", user=self.user, payload=self.material_payload(),
            idempotency_key="FW1-CONFLICT", source_identity=self.source(),
        )
        with self.assertRaises(ProductionFoundationError) as caught:
            ProductionFoundationService.write(
                "materials", user=self.user, payload=self.material_payload("不同物料"),
                idempotency_key="FW1-CONFLICT", source_identity=self.source(),
            )
        self.assertEqual(caught.exception.code, "IDEMPOTENCY_PAYLOAD_CONFLICT")
        self.assertEqual(Material.objects.count(), 1)

    def test_validation_failure_rolls_back_code_identity_ledger_and_audit(self):
        payload = self.material_payload()
        payload.update({"unit_status": "confirmed", "unit": ""})
        with self.assertRaises(ProductionFoundationError) as caught:
            ProductionFoundationService.write(
                "materials", user=self.user, payload=payload,
                idempotency_key="FW1-ROLLBACK", source_identity=self.source("ROW-ROLLBACK"),
            )
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(Material.objects.count(), 0)
        self.assertEqual(ExternalIdentity.objects.count(), 0)
        self.assertEqual(MasterDataWriteRequest.objects.count(), 0)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)
        self.material_rule.refresh_from_db()
        self.assertEqual(self.material_rule.current_seq, 0)

    def test_authorization_failure_rolls_back_everything(self):
        denied = User.objects.create_user(
            username="fw1_denied", password="test-only", company_id=self.company.pk,
        )
        with self.assertRaises(ProductionFoundationError):
            ProductionFoundationService.write(
                "materials", user=denied, payload=self.material_payload(),
                idempotency_key="FW1-DENIED", source_identity=self.source("ROW-DENIED"),
            )
        self.assertEqual(Material.objects.count(), 0)
        self.assertEqual(ExternalIdentity.objects.count(), 0)
        self.assertEqual(MasterDataWriteRequest.objects.count(), 0)

    def test_workshop_uses_same_write_chain_and_its_own_encoder(self):
        source = self.source("WORKSHOP-木工")
        source["sourceObjectType"] = "WORKSHOP_SOURCE"
        result = ProductionFoundationService.write(
            "workshops", user=self.user,
            payload={"company_id": self.company.pk, "name": "木工", "is_active": True, "reason": "隔离测试"},
            idempotency_key="FW1-WS-1", source_identity=source,
        )
        self.assertEqual(result["row"]["code"], "WS000001")
        self.assertEqual(Workshop.objects.count(), 1)
        self.assertEqual(ExternalIdentity.objects.get().target_entity_type, "workshops")

    def test_work_center_code_is_server_generated_idempotent_and_immutable(self):
        workshop = Workshop.objects.create(
            company=self.company, department=self.department,
            code="FW1-WS-WC", name="工作中心隔离测试车间",
        )
        baseline = {
            "workshops": Workshop.objects.count(),
            "operations": Process.objects.count(),
            "capabilities": WorkCenterOperationCapability.objects.count(),
        }
        first_payload = {
            "company_id": self.company.pk,
            "code": "CLIENT-MUST-NOT-OWN-CODE",
            "name": "隔离测试工作中心一",
            "department_id": self.department.pk,
            "workshop_id": workshop.pk,
            "resource_capabilities": {},
            "capacity_policy": {},
            "is_active": True,
            "reason": "验证工作中心正式自动编码",
        }
        first_source = {
            **self.source("WORK-CENTER-1"),
            "sourceObjectType": "WORK_CENTER_SOURCE",
        }
        first = ProductionFoundationService.write(
            "work-centers", user=self.user, payload=first_payload,
            idempotency_key="FW1-WC-1", source_identity=first_source,
        )
        replay = ProductionFoundationService.write(
            "work-centers", user=self.user, payload=first_payload,
            idempotency_key="FW1-WC-1", source_identity=first_source,
        )
        second = ProductionFoundationService.write(
            "work-centers", user=self.user,
            payload={
                "company_id": self.company.pk,
                "name": "隔离测试工作中心二",
                "department_id": self.department.pk,
                "workshop_id": workshop.pk,
                "resource_capabilities": {},
                "capacity_policy": {},
                "is_active": True,
                "reason": "验证连续正式自动编码",
            },
            idempotency_key="FW1-WC-2",
            source_identity={
                **self.source("WORK-CENTER-2"),
                "sourceObjectType": "WORK_CENTER_SOURCE",
            },
        )
        updated = ProductionFoundationService.write(
            "work-centers", user=self.user,
            payload={
                "code": "CLIENT-RENUMBER-BLOCKED",
                "name": "隔离测试工作中心一（已编辑）",
                "reason": "验证编辑保持正式编码",
            },
            idempotency_key="FW1-WC-UPDATE-1", source_identity=None,
            object_id=first["row"]["id"],
        )

        self.assertEqual(first["row"]["code"], "WC000001")
        self.assertEqual(second["row"]["code"], "WC000002")
        self.assertEqual(replay["row"]["id"], first["row"]["id"])
        self.assertTrue(replay["idempotentReplay"])
        self.assertEqual(updated["row"]["code"], first["row"]["code"])
        self.assertEqual(
            WorkCenter.objects.get(pk=first["row"]["id"]).code,
            first["row"]["code"],
        )
        self.assertEqual(WorkCenter.objects.count(), 2)
        self.work_center_rule.refresh_from_db()
        self.assertEqual(self.work_center_rule.current_seq, 2)
        self.assertEqual(Workshop.objects.count(), baseline["workshops"])
        self.assertEqual(Process.objects.count(), baseline["operations"])
        self.assertEqual(
            WorkCenterOperationCapability.objects.count(), baseline["capabilities"],
        )

    def test_work_center_validation_failure_does_not_consume_code(self):
        with self.assertRaises(ProductionFoundationError) as caught:
            ProductionFoundationService.write(
                "work-centers", user=self.user,
                payload={
                    "company_id": self.company.pk,
                    "name": "",
                    "reason": "验证失败不消耗编码",
                },
                idempotency_key="FW1-WC-INVALID",
                source_identity={
                    **self.source("WORK-CENTER-INVALID"),
                    "sourceObjectType": "WORK_CENTER_SOURCE",
                },
            )
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(WorkCenter.objects.count(), 0)
        self.work_center_rule.refresh_from_db()
        self.assertEqual(self.work_center_rule.current_seq, 0)

    def test_concurrent_work_center_creates_allocate_unique_codes(self):
        user_id = self.user.pk
        company_id = self.company.pk

        def create_work_center(index):
            close_old_connections()
            for attempt in range(50):
                try:
                    user = User.objects.get(pk=user_id)
                    result = ProductionFoundationService.write(
                        "work-centers", user=user,
                        payload={
                            "company_id": company_id,
                            "name": f"并发隔离工作中心{index}",
                            "resource_capabilities": {},
                            "capacity_policy": {},
                            "is_active": True,
                            "reason": "并发自动编码隔离验证",
                        },
                        idempotency_key=f"FW1-WC-CONCURRENT-{index}",
                        source_identity={
                            "sourceSystem": "FW1_TEST",
                            "sourceType": "CONCURRENT_TEST",
                            "sourceObjectType": "WORK_CENTER_SOURCE",
                            "externalId": f"WORK-CENTER-CONCURRENT-{index}",
                            "sourceFingerprint": f"{index:064d}",
                            "auditMetadata": {"isolated": True},
                        },
                    )
                    close_old_connections()
                    return result["row"]["code"]
                except OperationalError:
                    close_old_connections()
                    if attempt == 49:
                        raise
                    time.sleep(0.02)

        with ThreadPoolExecutor(max_workers=4) as pool:
            codes = list(pool.map(create_work_center, range(8)))

        self.assertEqual(len(codes), 8)
        self.assertEqual(len(set(codes)), 8)
        self.assertEqual(WorkCenter.objects.count(), 8)
        self.assertEqual(
            sorted(codes), [f"WC{sequence:06d}" for sequence in range(1, 9)],
        )
        self.work_center_rule.refresh_from_db()
        self.assertEqual(self.work_center_rule.current_seq, 8)

    def test_formal_create_api_requires_and_reuses_idempotency_key(self):
        client = APIClient()
        client.force_authenticate(self.user)
        missing = client.post(
            "/api/pde/a1-foundation/materials/", self.material_payload(), format="json",
        )
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.data["code"], "IDEMPOTENCY_KEY_REQUIRED")
        payload = {**self.material_payload(), "idempotencyKey": "FW1-API-1"}
        first = client.post("/api/pde/a1-foundation/materials/", payload, format="json")
        second = client.post("/api/pde/a1-foundation/materials/", payload, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.data["row"]["id"], second.data["row"]["id"])
        self.assertTrue(second.data["idempotentReplay"])
        self.assertEqual(Material.objects.count(), 1)

    def test_concurrent_code_allocation_produces_unique_numbers(self):
        CodeRule.objects.create(
            company_id=self.company.pk, entity_type="fw1_concurrent",
            prefix="C", date_format="", seq_length=4, current_seq=0,
        )

        def allocate(_):
            close_old_connections()
            for attempt in range(30):
                try:
                    value = CodeRule.next_code(
                        entity_type="fw1_concurrent", company_id=self.company.pk,
                    )
                    close_old_connections()
                    return value
                except OperationalError:
                    close_old_connections()
                    if attempt == 29:
                        raise
                    time.sleep(0.01)

        with ThreadPoolExecutor(max_workers=4) as pool:
            codes = list(pool.map(allocate, range(8)))
        self.assertEqual(len(codes), 8)
        self.assertEqual(len(set(codes)), 8)
        self.assertEqual(CodeRule.objects.get(entity_type="fw1_concurrent").current_seq, 8)


class FoundationUomGovernanceTests(TestCase):
    def setUp(self):
        self.units = [
            {"id": 1, "code": "kg", "name": "千克", "symbol": "kg", "dimension": "mass"},
            {"id": 2, "code": "m", "name": "米", "symbol": "m", "dimension": "length"},
        ]

    def test_exact_normalized_review_and_invalid_classes(self):
        self.assertEqual(UnitOfMeasureNormalizer.resolve("kg", self.units)["classification"], "EXACT_MATCH")
        self.assertEqual(UnitOfMeasureNormalizer.resolve("KG", self.units)["classification"], "NORMALIZED_MATCH")
        self.assertEqual(UnitOfMeasureNormalizer.resolve("公斤", self.units)["classification"], "NORMALIZED_MATCH")
        area = UnitOfMeasureNormalizer.resolve("面积", self.units)
        self.assertEqual(area["classification"], "SEMANTIC_REVIEW")
        self.assertEqual(area["dimension"], "area")
        square = UnitOfMeasureNormalizer.resolve("平方", self.units)
        self.assertEqual(square["classification"], "NORMALIZED_MATCH")
        self.assertEqual(square["match"]["code"], "m2")
        self.assertTrue(square["match"]["standardInitialization"])
        bag = UnitOfMeasureNormalizer.resolve("袋", self.units)
        self.assertEqual(bag["classification"], "NORMALIZED_MATCH")
        self.assertTrue(bag["requiresItemConversion"])
        self.assertEqual(UnitOfMeasureNormalizer.resolve("未知单位", self.units)["classification"], "INVALID")

    def test_operation_basis_is_ready_without_optional_concrete_uom(self):
        operation = Process(name="面积核算工序", calculation_basis=Process.CalculationBasis.AREA)
        self.assertEqual(operation.calculation_measurement_status, "BASIS_ONLY_READY")
        operation.calculation_basis = Process.CalculationBasis.UNDETERMINED
        self.assertEqual(operation.calculation_measurement_status, "UNDETERMINED")

    def test_external_identity_has_database_uniqueness(self):
        values = {
            "organization_id": 1, "source_system": "A", "source_type": "XLSX",
            "source_object_type": "MATERIAL", "external_id": "1",
            "target_entity_type": "materials", "mapping_status": "CREATE",
        }
        ExternalIdentity.objects.create(**values)
        with self.assertRaises(IntegrityError):
            ExternalIdentity.objects.create(**values)
