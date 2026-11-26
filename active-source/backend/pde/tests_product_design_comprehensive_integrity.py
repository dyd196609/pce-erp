from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from openpyxl import Workbook

from masterdata.models import ExternalIdentity, Material, UnitOfMeasure

from .acceptance_isolation import verify_declared_acceptance_runtime
from .models import ProductCategory, ProductDesignItem, ProductDesignRevision
from .order_demand_preparation_service import prepare_order_demand
from .product_design_service import (
    ProductDesignError,
    _match_material_source,
    initialize_product_design_items,
    product_design_facts,
    product_design_list_field_contract,
    save_design_content,
    save_design_plan,
)
from .product_design_import_service import PREVIOUS_HEADERS, parse_product_design_import
from . import tests_order_demand_preparation as base_tests


class ProductDesignComprehensiveIntegrityTests(TestCase):
    def setUp(self):
        base_tests.OrderDemandPreparationTests.setUp(self)
        prepare_order_demand(user=self.user, idempotency_key="prepare-comprehensive")
        initialize_product_design_items(
            user=self.user, idempotency_key="initialize-comprehensive", expected_count=4,
        )
        self.millimeter = UnitOfMeasure.objects.create(
            company_id=self.company.pk, code="MM", name="毫米", symbol="mm",
            dimension=UnitOfMeasure.Dimension.LENGTH, conversion_factor=Decimal("1"),
        )
        self.centimeter = UnitOfMeasure.objects.create(
            company_id=self.company.pk, code="CM", name="厘米", symbol="cm",
            dimension=UnitOfMeasure.Dimension.LENGTH, conversion_base=self.millimeter,
            conversion_factor=Decimal("10"),
        )

    def _save(self, item, design_data, key):
        item.refresh_from_db()
        return save_design_content(
            user=self.user,
            payload={
                "designItemIds": [item.pk],
                "expectedVersions": {str(item.pk): item.version},
                "designNature": "FORMAL", "designData": design_data,
                "reason": "产品设计综合区隔离自动化验证",
            },
            idempotency_key=key,
        )[0]

    def test_source_material_code_uses_stable_external_identity_not_mutable_payload(self):
        material = Material.objects.create(
            company_id=self.company.pk, code="MAT-FORMAL-001",
            name="当前正式名称", specification="当前正式规格", unit="",
            material_type="semi", is_active=True, is_produced=True,
        )
        identity = ExternalIdentity.objects.create(
            organization_id=self.company.pk,
            source_system="PCE_FOUNDATION_WAVE1",
            source_type="APPROVED_XLSX",
            source_object_type="SEMI_FINISHED_MATERIAL_SOURCE",
            external_id="source.xlsx|materials|CODE:SRC-MATERIAL-001",
            target_entity_type="materials", target_entity_id=str(material.pk),
            mapping_status=ExternalIdentity.MappingStatus.MATCH,
            audit_metadata={"sourceCode": "SRC-MATERIAL-001"},
        )

        result = _match_material_source(self.company.pk, "SRC-MATERIAL-001")

        self.assertEqual(result["status"], "IDENTITY_MATCH")
        self.assertEqual(result["matchMethod"], "EXTERNAL_IDENTITY")
        self.assertEqual(result["matchedId"], material.pk)
        self.assertEqual(result["identityIds"], [identity.pk])

    def test_read_refreshes_stale_material_match_after_identity_is_maintained(self):
        item = ProductDesignItem.objects.order_by("pk").first()
        item.existing_design_data = {
            **(item.existing_design_data or {}),
            "materialProcessCode": "SRC-MATERIAL-LATE-MATCH",
        }
        item.match_results = {
            **(item.match_results or {}),
            "material": {
                "status": "NO_MATCH", "sourceValue": "SRC-MATERIAL-LATE-MATCH",
                "matchedId": None, "candidateIds": [],
            },
        }
        item.save(update_fields=["existing_design_data", "match_results"])
        material = Material.objects.create(
            company_id=self.company.pk, code="MAT-FORMAL-LATE-MATCH",
            name="纠正后的正式名称", specification="纠正后的正式规格", unit="",
            material_type="semi", is_active=True, is_produced=True,
        )
        ExternalIdentity.objects.create(
            organization_id=self.company.pk,
            source_system="PCE_FOUNDATION_WAVE1",
            source_type="APPROVED_XLSX",
            source_object_type="SEMI_FINISHED_MATERIAL_SOURCE",
            external_id="source.xlsx|materials|CODE:SRC-MATERIAL-LATE-MATCH",
            target_entity_type="materials", target_entity_id=str(material.pk),
            mapping_status=ExternalIdentity.MappingStatus.MATCH,
            audit_metadata={"sourceCode": "SRC-MATERIAL-LATE-MATCH"},
        )

        facts = product_design_facts(self.company.pk, user=self.user)
        row = next(value for value in facts["rows"] if value["id"] == item.pk)

        self.assertEqual(row["matchResults"]["material"]["status"], "IDENTITY_MATCH")
        self.assertEqual(row["matchResults"]["material"]["matchedId"], material.pk)
        self.assertEqual(row["listValues"]["materialCode"], "MAT-FORMAL-LATE-MATCH")
        self.assertEqual(row["listValues"]["materialName"], "纠正后的正式名称")
        self.assertEqual(row["listValues"]["materialSpecification"], "纠正后的正式规格")

    def test_source_material_identity_conflict_never_selects_an_arbitrary_material(self):
        direct = Material.objects.create(
            company_id=self.company.pk, code="SRC-MATERIAL-CONFLICT",
            name="正式编码对象", unit="", material_type="semi", is_active=True,
            is_produced=True,
        )
        mapped = Material.objects.create(
            company_id=self.company.pk, code="MAT-FORMAL-OTHER",
            name="身份映射对象", unit="", material_type="semi", is_active=True,
            is_produced=True,
        )
        ExternalIdentity.objects.create(
            organization_id=self.company.pk,
            source_system="PCE_FOUNDATION_WAVE1",
            source_type="APPROVED_XLSX",
            source_object_type="SEMI_FINISHED_MATERIAL_SOURCE",
            external_id="source.xlsx|materials|CODE:SRC-MATERIAL-CONFLICT",
            target_entity_type="materials", target_entity_id=str(mapped.pk),
            mapping_status=ExternalIdentity.MappingStatus.MATCH,
            audit_metadata={"sourceCode": "SRC-MATERIAL-CONFLICT"},
        )

        result = _match_material_source(self.company.pk, "SRC-MATERIAL-CONFLICT")

        self.assertEqual(result["status"], "MULTIPLE_MATCHES")
        self.assertIsNone(result["matchedId"])
        self.assertEqual(result["candidateIds"], sorted([direct.pk, mapped.pk]))

    def test_invalid_source_material_identity_is_reported_and_not_used(self):
        material = Material.objects.create(
            company_id=self.company.pk, code="MAT-FORMAL-INVALID",
            name="失效身份目标", unit="", material_type="semi", is_active=True,
            is_produced=True,
        )
        identity = ExternalIdentity.objects.create(
            organization_id=self.company.pk,
            source_system="PCE_FOUNDATION_WAVE1",
            source_type="APPROVED_XLSX",
            source_object_type="SEMI_FINISHED_MATERIAL_SOURCE",
            external_id="source.xlsx|materials|CODE:SRC-MATERIAL-INVALID",
            target_entity_type="materials", target_entity_id=str(material.pk),
            mapping_status=ExternalIdentity.MappingStatus.REVIEW,
            audit_metadata={"sourceCode": "SRC-MATERIAL-INVALID"},
        )

        result = _match_material_source(self.company.pk, "SRC-MATERIAL-INVALID")

        self.assertEqual(result["status"], "IDENTITY_INTEGRITY_ERROR")
        self.assertIsNone(result["matchedId"])
        self.assertEqual(result["invalidIdentityIds"], [identity.pk])

    def test_two_units_are_independent_and_dimension_unit_conversion_is_controlled(self):
        item = ProductDesignItem.objects.order_by("pk").first()
        self._save(item, {
            "physicalUomId": self.items[0].uom_id,
            "designUomId": self.millimeter.pk,
            "designLength": "2300", "designWidth": "800", "designThickness": "18",
        }, "dimension-unit-initial")
        facts = self._save(item, {"designUomId": self.centimeter.pk}, "dimension-unit-convert")
        row = next(value for value in facts["rows"] if value["id"] == item.pk)
        self.assertEqual(row["listValues"]["physicalUnit"], "套")
        self.assertEqual(row["listValues"]["designDimensionUnit"], "厘米")
        self.assertEqual(row["designRevision"]["designLength"], "230.000000")
        self.assertEqual(row["designRevision"]["designWidth"], "80.000000")
        self.assertEqual(row["designRevision"]["designThickness"], "1.800000")

    def test_unmaintained_dimension_unit_is_not_invented(self):
        item = ProductDesignItem.objects.order_by("pk")[1]
        facts = product_design_facts(self.company.pk, user=self.user)
        row = next(value for value in facts["rows"] if value["id"] == item.pk)
        self.assertEqual(row["listValues"]["designDimensionUnit"], "")

    def test_unknown_source_unit_and_mixed_semantics_block_batch_unit_change(self):
        unknown = ProductDesignItem.objects.order_by("pk").first()
        with self.assertRaises(ProductDesignError) as missing:
            save_design_content(
                user=self.user,
                payload={
                    "designItemIds": [unknown.pk],
                    "expectedVersions": {str(unknown.pk): unknown.version},
                    "designNature": "FORMAL", "designData": {"designUomId": self.millimeter.pk},
                    "reason": "未知原尺寸单位不能只贴新标签",
                }, idempotency_key="unknown-source-dimension-unit",
            )
        self.assertEqual(missing.exception.code, "DESIGN_UOM_SOURCE_UNKNOWN")
        first, second = list(ProductDesignItem.objects.order_by("pk")[:2])
        first.existing_design_data = {**first.existing_design_data, "dimensionSemantic": "墙厚"}
        second.existing_design_data = {**second.existing_design_data, "dimensionSemantic": "部件厚"}
        first.save(update_fields=["existing_design_data"])
        second.save(update_fields=["existing_design_data"])
        with self.assertRaises(ProductDesignError) as mixed:
            save_design_content(
                user=self.user,
                payload={
                    "designItemIds": [first.pk, second.pk],
                    "expectedVersions": {str(first.pk): first.version, str(second.pk): second.version},
                    "designNature": "FORMAL", "designData": {"designUomId": self.millimeter.pk},
                    "reason": "混合第三尺寸语义必须阻断",
                }, idempotency_key="mixed-dimension-semantics",
            )
        self.assertEqual(mixed.exception.code, "DESIGN_DIMENSION_SEMANTIC_MIXED")
        self.assertEqual(ProductDesignRevision.objects.count(), 0)

    def test_complete_contract_has_unique_labels_and_all_comprehensive_inputs(self):
        contract = product_design_list_field_contract()
        self.assertEqual(len(contract), 40)
        self.assertEqual(len({field["key"] for field in contract}), 40)
        self.assertEqual(len({field["label"] for field in contract}), 40)
        labels = [field["label"] for field in contract]
        self.assertIn("实物单位", labels)
        self.assertIn("设计尺寸单位", labels)
        self.assertIn("物料规格", labels)
        self.assertNotIn("材料规格", labels)
        self.assertNotIn("单位", labels)
        self.assertLess(labels.index("实物单位"), labels.index("设计尺寸单位"))
        self.assertEqual(
            [field["label"] for field in contract if field["key"] in {"designLength", "designWidth", "thirdDimension", "thirdDimensionSemantic", "designDimensionUnit"}],
            ["设计尺寸单位", "设计长度", "设计宽度", "第三尺寸", "第三尺寸语义"],
        )
        self.assertEqual(
            labels[labels.index("设计负责人"):labels.index("完成状态") + 1],
            ["设计负责人", "设计计划开工日期", "设计计划完工日期", "设计状态", "设计修订号", "完成状态"],
        )

    def test_group_plan_dates_are_read_only_projected_to_every_design_item(self):
        save_design_plan(
            user=self.user,
            payload={
                "designGroups": ["DES-01"],
                "designerEmployeeId": self.employee.pk,
                "plannedStartDate": "2026-09-23",
                "plannedFinishDate": "2026-09-29",
                "planType": "FORMAL",
                "adjustmentReason": "隔离库计划投影验证",
            },
            idempotency_key="plan-projection-contract",
        )
        facts = product_design_facts(self.company.pk, user=self.user)
        group_rows = [row for row in facts["rows"] if row["designGroup"] == "DES-01"]
        self.assertTrue(group_rows)
        self.assertTrue(all(row["listValues"]["plannedStartDate"] == "2026-09-23" for row in group_rows))
        self.assertTrue(all(row["listValues"]["plannedFinishDate"] == "2026-09-29" for row in group_rows))
        unplanned = [row for row in facts["rows"] if row["designGroup"] == "DES-02"]
        self.assertTrue(all(row["listValues"]["plannedStartDate"] == "" for row in unplanned))

    def test_two_item_description_only_save_refreshes_without_formal_product_or_unselected_changes(self):
        first, second = list(ProductDesignItem.objects.order_by("pk")[:2])
        before = {
            item.pk: {
                "version": item.version,
                "productDefinitionId": item.product_definition_id,
                "existing": item.existing_design_data,
            }
            for item in (first, second)
        }
        saved, replayed = save_design_content(
            user=self.user,
            payload={
                "designItemIds": [first.pk, second.pk],
                "expectedVersions": {str(first.pk): first.version, str(second.pk): second.version},
                "designNature": "FORMAL",
                "designData": {"designNotes": "两项目标仅修改设计说明"},
                "reason": "批量说明闭环隔离验证",
            },
            idempotency_key="two-item-description-only",
        )
        self.assertFalse(replayed)
        refreshed = product_design_facts(self.company.pk, user=self.user)
        selected = [row for row in refreshed["rows"] if row["id"] in {first.pk, second.pk}]
        self.assertEqual(len(selected), 2)
        self.assertTrue(all(row["designRevision"]["designNotes"] == "两项目标仅修改设计说明" for row in selected))
        self.assertTrue(all(row["productDefinitionId"] is None for row in selected))
        for item in (first, second):
            item.refresh_from_db()
            self.assertEqual(item.product_definition_id, before[item.pk]["productDefinitionId"])
            self.assertEqual(item.existing_design_data, before[item.pk]["existing"])
            self.assertEqual(item.version, before[item.pk]["version"] + 1)
        self.assertEqual(ProductDesignRevision.objects.filter(design_item_id__in=[first.pk, second.pk]).count(), 2)

    def test_three_stable_targets_keep_revision_ownership_after_readback_reordering(self):
        first, second, third, unselected = list(ProductDesignItem.objects.order_by("pk")[:4])
        target_ids = [third.pk, first.pk, second.pk]
        before_unselected = {
            "version": unselected.version,
            "existing": unselected.existing_design_data,
        }
        save_design_content(
            user=self.user,
            payload={
                "designItemIds": target_ids,
                "expectedVersions": {
                    str(item.pk): item.version for item in (third, first, second)
                },
                "designNature": "FORMAL",
                "designData": {"designNotes": "三项稳定ID回读验证"},
                "reason": "选择身份与行位置分离验证",
            },
            idempotency_key="three-stable-targets-readback",
        )
        refreshed = product_design_facts(self.company.pk, user=self.user)
        revision_owners = {
            row["id"] for row in refreshed["rows"]
            if (row.get("designRevision") or {}).get("designNotes") == "三项稳定ID回读验证"
        }
        self.assertEqual(revision_owners, set(target_ids))
        self.assertNotIn(unselected.pk, revision_owners)
        unselected.refresh_from_db()
        self.assertEqual(unselected.version, before_unselected["version"])
        self.assertEqual(unselected.existing_design_data, before_unselected["existing"])
        self.assertFalse(ProductDesignRevision.objects.filter(design_item=unselected).exists())

    def test_confirmed_category_range_uses_stable_ids_through_original_save_and_refresh(self):
        category_a = ProductCategory.objects.create(
            company=self.company, code="RANGE-A", name="范围分类A",
        )
        category_b = ProductCategory.objects.create(
            company=self.company, code="RANGE-B", name="范围分类B",
        )
        items = list(ProductDesignItem.objects.order_by("pk")[:4])
        for item in items[:3]:
            item.product_category = category_a
            item.save(update_fields=["product_category"])
        items[3].product_category = category_b
        items[3].save(update_fields=["product_category"])

        before = product_design_facts(self.company.pk, user=self.user)
        range_snapshot_ids = [
            row["id"] for row in before["rows"]
            if row["productCategoryId"] == category_a.pk
        ]
        self.assertEqual(set(range_snapshot_ids), {item.pk for item in items[:3]})
        expected_versions = {
            str(row["id"]): row["version"] for row in before["rows"]
            if row["id"] in range_snapshot_ids
        }
        save_design_content(
            user=self.user,
            payload={
                "designItemIds": range_snapshot_ids,
                "expectedVersions": expected_versions,
                "designNature": "FORMAL",
                "designData": {"designNotes": "分类范围确认后仅修改一个字段"},
                "reason": "范围快照走原保存服务隔离验证",
            },
            idempotency_key="confirmed-category-range-save-readback",
        )
        refreshed = product_design_facts(self.company.pk, user=self.user)
        changed_ids = {
            row["id"] for row in refreshed["rows"]
            if (row.get("designRevision") or {}).get("designNotes") == "分类范围确认后仅修改一个字段"
        }
        self.assertEqual(changed_ids, set(range_snapshot_ids))
        self.assertNotIn(items[3].pk, changed_ids)
        self.assertFalse(ProductDesignRevision.objects.filter(design_item=items[3]).exists())

    def test_range_snapshot_version_change_is_blocked_by_existing_optimistic_lock(self):
        item = ProductDesignItem.objects.order_by("pk").first()
        stale_version = item.version
        item.version += 1
        item.save(update_fields=["version"])
        with self.assertRaises(ProductDesignError) as conflict:
            save_design_content(
                user=self.user,
                payload={
                    "designItemIds": [item.pk],
                    "expectedVersions": {str(item.pk): stale_version},
                    "designNature": "FORMAL",
                    "designData": {"designNotes": "不得覆盖并发版本"},
                    "reason": "范围快照并发保护验证",
                },
                idempotency_key="range-snapshot-version-conflict",
            )
        self.assertEqual(conflict.exception.code, "DESIGN_ITEM_VERSION_CONFLICT")
        self.assertEqual(ProductDesignRevision.objects.count(), 0)

    def test_zero_target_batch_save_is_blocked_without_revision_write(self):
        with self.assertRaises(ProductDesignError) as blocked:
            save_design_content(
                user=self.user,
                payload={
                    "designItemIds": [],
                    "expectedVersions": {},
                    "designNature": "FORMAL",
                    "designData": {"designNotes": "不得写入"},
                    "reason": "零选择阻断验证",
                },
                idempotency_key="zero-target-block",
            )
        self.assertEqual(blocked.exception.code, "DESIGN_ITEM_SELECTION_INVALID")
        self.assertEqual(ProductDesignRevision.objects.count(), 0)

    def test_previous_material_specification_header_remains_a_compatible_alias(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "产品设计导入"
        for column, header in enumerate(PREVIOUS_HEADERS, 1):
            sheet.cell(5, column, header)
        stream = BytesIO()
        workbook.save(stream)
        uploaded = SimpleUploadedFile(
            "previous-product-design-template.xlsx",
            stream.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        preview = parse_product_design_import(uploaded, self.company.pk)
        self.assertEqual(preview["rowCount"], 0)
        self.assertIn("材料规格", PREVIOUS_HEADERS)
        self.assertNotIn("物料规格", PREVIOUS_HEADERS)

    def test_read_uses_persisted_order_relations_not_development_sample_names(self):
        self.order.contract_reference = "ORDINARY-CUSTOMER-CONTRACT"
        self.order.external_source_no = "RENAMED-SOURCE"
        self.order.save(update_fields=["contract_reference", "external_source_no"])
        ProductDesignItem.objects.update(item_name="行业中立客户订单工程")
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get("/api/pde/product-definitions/?readAt=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["recordCount"], 4)
        self.assertEqual(response.data["orderContext"]["orderNo"], self.order.order_no)
        writes = [
            query["sql"] for query in queries
            if query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE"))
        ]
        self.assertEqual(writes, [])

    def test_invalid_explicit_order_does_not_fall_back_to_another_order(self):
        response = self.client.get("/api/pde/product-definitions/?orderNo=NOT-EXIST")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["errorCode"], "PRODUCT_DESIGN_ORDER_NOT_FOUND")
        self.assertIsNone(response.data["recordCount"])


class DeclaredAcceptanceRuntimeIsolationTests(SimpleTestCase):
    def test_declared_profile_rejects_missing_identity_instead_of_default_fallback(self):
        with self.assertRaisesMessage(ValueError, "ACCEPTANCE_ISOLATION_DECLARATION_REQUIRED"):
            verify_declared_acceptance_runtime(
                {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "db.sqlite3"}},
                environ={"PCE_RUNTIME_PROFILE": "PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE"},
            )
