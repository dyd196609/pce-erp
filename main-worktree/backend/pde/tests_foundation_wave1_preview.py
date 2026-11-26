from hashlib import sha256
import json
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import load_workbook

from masterdata.models import CodeRule, ExternalIdentity, Material, UnitOfMeasure
from procurement.models import Supplier
from sales.models import Customer
from system.models import Process, Workshop

from .foundation_import_preview_service import (
    APPROVED_SOURCES, FoundationImportPreviewService, _resolve_existing,
)
from .models import ProductDefinition, WorkCenter


SOURCE_ROOT = Path(r"D:\0  软件开发知识及测试数据\ChatGTP开发文件\全屋订制及整木基础数据导入")


def snapshot(model):
    rows = list(model.objects.order_by("pk").values())
    encoded = json.dumps(rows, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return len(rows), sha256(encoded).hexdigest()


class FoundationWave1PreviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for code, name, dimension in [("套", "套", "count"), ("个", "个", "count"), ("块", "块", "count"), ("张", "张", "count"), ("支", "支", "count"), ("kg", "千克", "mass")]:
            UnitOfMeasure.objects.get_or_create(
                code=code, company_id=1,
                defaults={"name": name, "dimension": dimension, "symbol": code},
            )
        Material.objects.create(code="QSFB4601001", name="清水封闭实木多层板", material_type="semi", company_id=1)
        Material.objects.create(code="OTHER-001", name="全桉全连芯超平20", material_type="raw", company_id=1)
        CodeRule.objects.update_or_create(
            entity_type="production_operation", company_id=1,
            defaults={"prefix": "PROC", "date_format": "%Y%m", "seq_length": 6, "current_seq": 7},
        )

    def preview(self, name):
        path = SOURCE_ROOT / name
        self.assertTrue(path.is_file(), f"approved source missing: {path}")
        uploaded = SimpleUploadedFile(name, path.read_bytes(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        return FoundationImportPreviewService.preview(uploaded_file=uploaded, organization_id=1)

    def protected_state(self):
        return {
            "materials": snapshot(Material), "uoms": snapshot(UnitOfMeasure),
            "products": snapshot(ProductDefinition), "operations": snapshot(Process),
            "workshops": snapshot(Workshop), "workCenters": snapshot(WorkCenter),
            "suppliers": snapshot(Supplier), "customers": snapshot(Customer),
            "codeRules": snapshot(CodeRule),
            "externalIdentities": snapshot(ExternalIdentity),
        }

    def create_identity(
        self, *, source_name="10采购物料.xlsx", suffix="CODE:1",
        target_entity_type="materials", target_entity_id="", organization_id=1,
        source_object_type="PURCHASE_MATERIAL_SOURCE", mapping_status="MATCH",
    ):
        source = APPROVED_SOURCES[source_name]
        return ExternalIdentity.objects.create(
            organization_id=organization_id,
            source_system="PCE_FOUNDATION_WAVE1",
            source_type="APPROVED_XLSX",
            source_object_type=source_object_type,
            external_id=f"{source.file_name}|{source.sheet}|{suffix}",
            target_entity_type=target_entity_type,
            target_entity_id=str(target_entity_id),
            mapping_status=mapping_status,
        )

    def test_05_semifinished_material_preview_is_read_only(self):
        before = self.protected_state()
        result = self.preview("05半成品板材.xlsx")
        self.assertEqual(result["statistics"]["total"], 61)
        self.assertEqual(result["statistics"]["sourceIdentityVerified"], 61)
        self.assertEqual(result["statistics"]["incompleteSource"], 3)
        self.assertEqual(len({row["sourceCode"] for row in result["rows"]}), 61)
        self.assertTrue(all(row["candidateObject"] == "MATERIAL" for row in result["rows"]))
        self.assertTrue(all(row["productDecision"] == "DEFERRED_NO_FORMAL_PRODUCT_SOURCE" for row in result["rows"]))
        self.assertTrue(all(row["rawUom"] == "" and row["uomStatus"] == "UNIT_NOT_CONFIRMED" for row in result["rows"]))
        exact = next(row for row in result["rows"] if row["sourceCode"] == "QSFB4601001")
        self.assertEqual(exact["recommendedDecision"], "EXISTING_REUSE")
        self.assertEqual(result["validationAction"]["formalBusinessWriteCount"], 0)
        readiness = result["commitReadiness"]
        self.assertEqual(readiness["status"], "PARTIAL")
        self.assertEqual(readiness["sourcePolicy"], "GENERATE_FORMAL_MATERIAL_CODE")
        self.assertEqual(readiness["formalCommitCandidates"], 58)
        self.assertEqual(readiness["excludedIncomplete"], 3)
        self.assertEqual(readiness["canonicalCodeReady"], 58)
        self.assertEqual(readiness["uomReady"], 58)
        self.assertEqual(readiness["readyForAuthorizedWrite"], 58)
        self.assertFalse(readiness["formalWriteAuthorized"])
        self.assertEqual(readiness["gateDecisions"], {
            "engineeringCodeCommitReadiness": "GO",
            "productionMigrationReadiness": "GO",
            "formalMasterDataWriteReadiness": "PARTIAL",
            "gitCommitAuthorization": "NOT_GRANTED",
            "productionMigrationAuthorization": "COMPLETE",
            "formalMasterDataWriteAuthorization": "NOT_GRANTED",
        })
        self.assertEqual(readiness["formalChain"]["idempotency"], "READY")
        self.assertEqual(readiness["formalChain"]["migration"], "APPLIED")
        self.assertTrue(readiness["formalWriteServiceReady"])
        self.assertEqual(readiness["sourceIdentityPersistenceBlocked"], 0)
        self.assertEqual(result["statistics"]["newMaterialCandidate"], 57)
        exceptions = readiness["rowExceptions"]
        self.assertEqual(
            [(item["sourceRow"], item["sourceCode"], item["sourceName"]) for item in exceptions],
            [(2, "DD4708003", "待定待定"), (3, "DD4708002", "待定待定"), (5, "DD4708001", "待定待定")],
        )
        self.assertTrue(all(not item["formalCommitCandidate"] for item in exceptions))
        self.assertTrue(all(item["blockerType"] == "SOURCE_DATA_BLOCKER" for item in exceptions))
        self.assertEqual(ProductDefinition.objects.count(), 0)
        self.assertEqual(self.protected_state(), before)

    def test_10_purchase_material_codes_are_verified_but_not_canonicalized(self):
        before = self.protected_state()
        result = self.preview("10采购物料.xlsx")
        self.assertEqual(result["statistics"]["total"], 132)
        self.assertEqual(result["statistics"]["sourceIdentityVerified"], 132)
        self.assertEqual(len({row["sourceCode"] for row in result["rows"]}), 132)
        self.assertEqual([row["sourceCode"] for row in result["rows"]], [str(value) for value in range(1, 133)])
        first = result["rows"][0]
        self.assertEqual(first["sourceCode"], "1")
        self.assertEqual(first["canonicalCode"], "")
        self.assertEqual(first["canonicalCodePolicy"], "GENERATE_FORMAL_MATERIAL_CODE")
        self.assertIsNone(first["existingCanonicalMatch"])
        similar_name = next(row for row in result["rows"] if row["sourceName"] == "全桉全连芯超平20")
        self.assertIsNone(similar_name["existingCanonicalMatch"], "name similarity must never reuse a Material")
        self.assertTrue(any(row["rawUom"] == "张" and row["uomStatus"] == "EXISTING_UOM_REUSE" for row in result["rows"]))
        self.assertTrue(any(row["rawUom"] == "KG" and row["uomDecision"] == "NORMALIZED_MATCH" for row in result["rows"]))
        square = next(row for row in result["rows"] if row["rawUom"] == "平方")
        self.assertEqual(square["uomDecision"], "NORMALIZED_MATCH")
        self.assertEqual(square["existingUomMatch"]["code"], "m2")
        for raw_uom in ["袋", "根", "桶"]:
            governed = next(row for row in result["rows"] if row["rawUom"] == raw_uom)
            self.assertIn(governed["uomStatus"], {"EXISTING_UOM_REUSE", "STANDARD_INITIALIZATION_READY"})
            self.assertEqual(governed["existingUomMatch"]["code"], raw_uom)
            self.assertFalse(any(
                row["rawUom"] == raw_uom and row.get("existingUomMatch", {}).get("code") == "个"
                for row in result["rows"] if row.get("existingUomMatch")
            ))
        self.assertFalse(UnitOfMeasure.objects.filter(code__in=["KG", "平方", "面积"]).exists())
        readiness = result["commitReadiness"]
        self.assertEqual(readiness["sourcePolicy"], "GENERATE_FORMAL_MATERIAL_CODE")
        self.assertEqual(readiness["formalCommitCandidates"], 132)
        self.assertEqual(readiness["canonicalCodeReady"], 132)
        self.assertEqual(readiness["sourceIdentityPersistenceBlocked"], 0)
        self.assertEqual(readiness["ready"], 132)
        self.assertEqual(readiness["review"], 0)
        self.assertEqual(readiness["uomReady"], 132)
        self.assertEqual(readiness["uomPending"], 0)
        self.assertEqual(readiness["readyForAuthorizedWrite"], 132)
        self.assertEqual(readiness["gateDecisions"]["formalMasterDataWriteReadiness"], "GO")
        self.assertEqual(readiness["gateDecisions"]["productionMigrationAuthorization"], "COMPLETE")
        self.assertEqual(readiness["gateDecisions"]["gitCommitAuthorization"], "NOT_GRANTED")
        self.assertEqual(readiness["gateDecisions"]["formalMasterDataWriteAuthorization"], "NOT_GRANTED")
        self.assertEqual(self.protected_state(), before)

    def test_material_external_identity_has_priority_over_formal_code_and_name(self):
        source_row = self.preview("10采购物料.xlsx")["rows"][0]
        formal = Material.objects.create(
            code="MAT-IDENTITY-001", name=f"{source_row['sourceName']}-正式名称已调整",
            material_type="raw", company_id=1,
        )
        self.create_identity(target_entity_id=formal.pk)
        before = self.protected_state()

        result = self.preview("10采购物料.xlsx")
        first = result["rows"][0]

        self.assertEqual(first["sourceIdentityStatus"], "SOURCE_IDENTITY_MATCHED")
        self.assertEqual(first["identityResolution"]["status"], "IDENTITY_MATCH")
        self.assertEqual(first["recommendedDecision"], "EXISTING_REUSE")
        self.assertEqual(first["canonicalCode"], "MAT-IDENTITY-001")
        self.assertEqual(first["validationStatus"], "SEMANTIC_REVIEW")
        self.assertFalse(first["commitReadiness"]["formalWriteEligible"])
        self.assertNotEqual(first["recommendedDecision"], "NEW_MATERIAL_CANDIDATE")
        self.assertEqual(result["statistics"]["newMaterialCandidate"], 131)
        self.assertEqual(self.protected_state(), before)

    def test_material_external_identity_with_same_payload_never_creates(self):
        source_row = self.preview("10采购物料.xlsx")["rows"][0]
        formal = Material.objects.create(
            code="MAT-IDENTITY-SAME", name=source_row["sourceName"],
            material_type="raw", company_id=1,
        )
        self.create_identity(target_entity_id=formal.pk)
        before = self.protected_state()

        first = self.preview("10采购物料.xlsx")["rows"][0]

        self.assertEqual(first["sourceIdentityStatus"], "SOURCE_IDENTITY_MATCHED")
        self.assertEqual(first["validationStatus"], "READY_FOR_DECISION")
        self.assertEqual(first["recommendedDecision"], "EXISTING_REUSE")
        self.assertEqual(first["canonicalCode"], "MAT-IDENTITY-SAME")
        self.assertNotEqual(first["recommendedDecision"], "NEW_MATERIAL_CANDIDATE")
        self.assertEqual(self.protected_state(), before)

    def test_dangling_and_wrong_type_identities_block_instead_of_create(self):
        self.create_identity(suffix="CODE:1", target_entity_id="999999")
        self.create_identity(
            suffix="CODE:2", target_entity_type="operations", target_entity_id="1",
        )
        before = self.protected_state()

        result = self.preview("10采购物料.xlsx")
        rows = {row["sourceCode"]: row for row in result["rows"]}

        for code in ("1", "2"):
            self.assertEqual(rows[code]["validationStatus"], "DATA_INTEGRITY_ERROR")
            self.assertEqual(rows[code]["recommendedDecision"], "UNRESOLVED")
            self.assertEqual(rows[code]["sourceIdentityStatus"], "SOURCE_IDENTITY_INTEGRITY_ERROR")
            self.assertFalse(rows[code]["commitReadiness"]["eligibleSourceRecord"])
        self.assertEqual(result["statistics"]["newMaterialCandidate"], 130)
        self.assertEqual(result["commitReadiness"]["blocked"], 2)
        self.assertEqual(self.protected_state(), before)

    def test_external_identity_isolated_by_organization(self):
        formal = Material.objects.create(
            code="MAT-OTHER-ORG", name="其他组织映射目标", material_type="raw", company_id=1,
        )
        self.create_identity(organization_id=2, target_entity_id=formal.pk)
        before = self.protected_state()

        first = self.preview("10采购物料.xlsx")["rows"][0]

        self.assertEqual(first["identityResolution"]["status"], "NO_MATCH")
        self.assertEqual(first["recommendedDecision"], "NEW_MATERIAL_CANDIDATE")
        self.assertIsNone(first["existingCanonicalMatch"])
        self.assertEqual(self.protected_state(), before)

    def test_unified_resolver_supports_operation_and_workshop_identity(self):
        source = APPROVED_SOURCES["01工序.xlsx"]
        facts = {
            "organizationId": 1,
            "operations": [{"id": 31, "code": "PROC000031", "name": "正式工序"}],
            "workshops": [{"id": 3, "code": "WS000003", "name": "正式车间"}],
            "externalIdentities": [
                {
                    "organization_id": 1, "source_system": "PCE_FOUNDATION_WAVE1",
                    "source_type": "APPROVED_XLSX",
                    "source_object_type": "MANUFACTURING_OPERATION_SOURCE",
                    "external_id": "01工序.xlsx|工序管理|ROW:2",
                    "target_entity_type": "operations", "target_entity_id": "31",
                    "mapping_status": "MATCH",
                },
                {
                    "organization_id": 1, "source_system": "PCE_FOUNDATION_WAVE1",
                    "source_type": "APPROVED_XLSX", "source_object_type": "WORKSHOP_SOURCE",
                    "external_id": "01工序.xlsx|工序管理|WORKSHOP:木工",
                    "target_entity_type": "workshops", "target_entity_id": "3",
                    "mapping_status": "MATCH",
                },
            ],
        }
        operation = _resolve_existing(
            source, facts, target_entity_type="operations",
            external_id="01工序.xlsx|工序管理|ROW:2", fallback_matches=[],
            source_name="来源工序",
        )
        workshop = _resolve_existing(
            source, facts, target_entity_type="workshops",
            external_id="01工序.xlsx|工序管理|WORKSHOP:木工", fallback_matches=[],
            source_name="木工", source_object_type="WORKSHOP_SOURCE",
        )

        self.assertEqual(operation["status"], "IDENTITY_MATCH")
        self.assertEqual(operation["match"]["code"], "PROC000031")
        self.assertTrue(operation["payloadChanged"])
        self.assertEqual(workshop["status"], "IDENTITY_MATCH")
        self.assertEqual(workshop["match"]["code"], "WS000003")

    def test_01_operation_preview_does_not_allocate_codes_or_resources(self):
        before = self.protected_state()
        result = self.preview("01工序.xlsx")
        self.assertEqual(result["statistics"]["total"], 32)
        self.assertEqual(result["statistics"]["sourceOperationCandidates"], 32)
        self.assertTrue(all(row["candidateObject"] == "OPERATION" for row in result["rows"]))
        self.assertTrue(all(row["canonicalCodeDisplay"] == "提交时由正式编码规则生成" for row in result["rows"]))
        self.assertTrue(all(row["workCenterStatus"] == "NOT_MAINTAINED" for row in result["rows"]))
        self.assertEqual(result["operationBoundary"]["workshopCandidates"], ["包装", "木工", "油漆"])
        self.assertFalse(result["operationBoundary"]["previewCalledNextCode"])
        self.assertEqual(result["operationBoundary"]["codeRule"]["current_seq"], 7)
        self.assertEqual(Process.objects.count(), 0)
        self.assertEqual(Workshop.objects.count(), 0)
        self.assertEqual(WorkCenter.objects.count(), 0)
        self.assertEqual(CodeRule.objects.get(entity_type="production_operation").current_seq, 7)
        readiness = result["commitReadiness"]
        self.assertEqual(readiness["sourcePolicy"], "FORMAL_OPERATION_AND_WORKSHOP_CODE_RULE_READY")
        self.assertEqual(readiness["canonicalCodeReady"], 32)
        self.assertEqual(readiness["uomReady"], 32)
        self.assertEqual(readiness["uomPending"], 0)
        self.assertEqual(readiness["workshopCandidateCount"], 3)
        self.assertEqual(readiness["workCenterCandidateCount"], 0)
        self.assertTrue(readiness["formalWriteServiceReady"])
        self.assertTrue(readiness["authorizationAuditReady"])
        self.assertEqual(readiness["ready"], 32)
        self.assertEqual(readiness["review"], 0)
        self.assertEqual(readiness["readyForAuthorizedWrite"], 32)
        self.assertEqual(readiness["gateDecisions"]["formalMasterDataWriteReadiness"], "GO")
        area = next(row for row in result["rows"] if row["rawUom"] == "面积")
        self.assertEqual(area["operationMeasurement"]["calculationBasis"], "area")
        self.assertIsNone(area["operationMeasurement"]["calculationUomId"])
        self.assertEqual(area["uomStatus"], "BASIS_ONLY_READY")
        self.assertTrue(area["commitReadiness"]["formalWriteEligible"])
        self.assertEqual(self.protected_state(), before)

    def test_05_codes_have_no_exact_match_in_approved_02_routing_reference(self):
        before = self.protected_state()
        workbook_05 = load_workbook(SOURCE_ROOT / "05半成品板材.xlsx", read_only=True, data_only=True)
        workbook_02 = load_workbook(SOURCE_ROOT / "02工艺路线.xlsx", read_only=True, data_only=True)
        try:
            rows_05 = list(workbook_05["半成品板材"].iter_rows(values_only=True))
            headers_05 = [str(value).strip() if value is not None else "" for value in rows_05[0]]
            code_index_05 = headers_05.index("半成品板材编码")
            codes_05 = {
                str(row[code_index_05]).strip() for row in rows_05[1:]
                if row[code_index_05] is not None and str(row[code_index_05]).strip()
            }

            sheet_02 = workbook_02.active
            header_row = next(
                row for row in sheet_02.iter_rows(values_only=True)
                if "半成品编码" in [str(value).strip() if value is not None else "" for value in row]
            )
            headers_02 = [str(value).strip() if value is not None else "" for value in header_row]
            code_index_02 = headers_02.index("半成品编码")
            codes_02 = {
                str(row[code_index_02]).strip() for row in sheet_02.iter_rows(values_only=True)
                if row[code_index_02] is not None and str(row[code_index_02]).strip() != "半成品编码"
            }
            self.assertEqual(len(codes_05), 61)
            self.assertEqual(len(codes_02), 42)
            self.assertEqual(codes_05 & codes_02, set())
        finally:
            workbook_05.close()
            workbook_02.close()
        self.assertEqual(self.protected_state(), before)
