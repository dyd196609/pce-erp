"""Read-only STRICT gate for PDE node 11 engineering-release readiness."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = Path(os.environ.get(
    "PCE_DATABASE_PATH",
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3",
)).resolve()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def scalar(connection: sqlite3.Connection, sql: str, params=()):
    return connection.execute(sql, params).fetchone()[0]


def main() -> None:
    require(DATABASE.is_file(), f"formal database not found: {DATABASE}")
    before = sha256(DATABASE)
    connection = sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro&immutable=1", uri=True)
    try:
        counts = {
            table: scalar(connection, f"SELECT COUNT(*) FROM {table}")
            for table in (
                "pde_engineering_document",
                "pde_engineering_document_version",
                "pde_product_manufacturing_output",
                "pde_product_bom",
                "pde_bom_version",
                "pde_routing",
                "pde_routing_version",
                "pde_work_center",
                "pde_engineering_operation_requirement",
            )
        }
        require(counts["pde_engineering_document"] == 1, "registered engineering document count must be 1")
        require(counts["pde_engineering_document_version"] == 1, "registered document version count must be 1")
        require(counts["pde_product_manufacturing_output"] == 0, "unexpected manufacturing output write")
        require(counts["pde_product_bom"] == 3, "ProductBOM protected count changed")
        require(counts["pde_bom_version"] == 3, "BOMVersion protected count changed")
        require(counts["pde_routing"] == 42, "Routing protected count changed")
        require(counts["pde_routing_version"] == 42, "RoutingVersion protected count changed")
        require(counts["pde_work_center"] == 0, "WorkCenter must remain zero")
        require(
            counts["pde_engineering_operation_requirement"] == 0,
            "EngineeringOperationRequirement must remain zero",
        )

        purpose = scalar(
            connection,
            "SELECT business_purpose FROM sales_order WHERE order_no=?",
            ("SO202609180003",),
        )
        require(purpose == "FORMAL_SALE", "formal sales-order purpose changed")

        oei_count = scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM pde_order_engineering_instance o
            JOIN sales_order_item si ON si.id=o.sales_order_item_id
            JOIN sales_order so ON so.id=si.sales_order_id
            WHERE so.order_no=?
            """,
            ("SO202609180003",),
        )
        category_only_count = scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM pde_order_engineering_instance o
            JOIN sales_order_item si ON si.id=o.sales_order_item_id
            JOIN sales_order so ON so.id=si.sales_order_id
            WHERE so.order_no=? AND o.product_id IS NULL
              AND o.product_category_id IS NOT NULL AND o.selected_process_type_id IS NOT NULL
            """,
            ("SO202609180003",),
        )
        require(oei_count == 4, "SO202609180003 OEI count changed")
        require(category_only_count == 4, "category-only order-engineering identity changed")

        calculation = connection.execute(
            """
            SELECT COUNT(*),
                   SUM((SELECT COUNT(*) FROM pde_engineering_calculation_detail d
                        WHERE d.calculation_id=c.id)),
                   SUM((SELECT COUNT(*) FROM pde_engineering_derived_fact f
                        WHERE f.calculation_id=c.id))
            FROM pde_engineering_calculation_record c
            JOIN pde_order_engineering_instance o ON o.id=c.engineering_instance_id
            JOIN sales_order_item si ON si.id=o.sales_order_item_id
            JOIN sales_order so ON so.id=si.sales_order_id
            WHERE so.order_no=? AND c.status='completed'
            """,
            ("SO202609180003",),
        ).fetchone()
        require(calculation == (4, 388, 388), f"engineering calculation facts changed: {calculation}")

        bom_rows = connection.execute(
            """
            SELECT b.id, v.id, v.status, v.revision
            FROM pde_product_bom b
            JOIN pde_bom_version v ON v.bom_id=b.id
            JOIN pde_order_engineering_instance o ON o.id=b.order_engineering_instance_id
            JOIN sales_order_item si ON si.id=o.sales_order_item_id
            JOIN sales_order so ON so.id=si.sales_order_id
            WHERE so.order_no=?
            ORDER BY b.id
            """,
            ("SO202609180003",),
        ).fetchall()
        require(len(bom_rows) == 3, "SO202609180003 formal BOM count changed")
        require(all(row[2] == "draft" for row in bom_rows), "formal BOM versions must remain unchanged")

        line1 = connection.execute(
            """
            SELECT co.code, si.id, o.id, o.instance_no,
                   b.id, b.bom_code, v.id, v.bom_version, v.revision, v.status,
                   c.id, c.calculation_no, c.status
            FROM sales_order so
            JOIN system_company co ON co.id=so.company_id
            JOIN sales_order_item si ON si.sales_order_id=so.id AND si.line_no=1
            JOIN pde_order_engineering_instance o ON o.sales_order_item_id=si.id
            JOIN pde_product_bom b ON b.order_engineering_instance_id=o.id
            JOIN pde_bom_version v ON v.bom_id=b.id
            JOIN pde_engineering_calculation_record c ON c.id=v.source_calculation_id
            WHERE so.order_no=?
            """,
            ("SO202609180003",),
        ).fetchone()
        require(
            line1 == (
                "COMP001", 3, 2, "OEI202609000001",
                3, "OBOM-OEI202609000001", 3, "CALC-3", 1, "draft",
                3, "EC202609000002", "completed",
            ),
            f"line1 upstream identity changed: {line1}",
        )

        registered_document = connection.execute(
            """
            SELECT d.document_no, d.document_name, d.document_type, d.status,
                   d.release_subject_type, d.product_id,
                   d.order_engineering_instance_id, d.product_bom_id, d.routing_id,
                   d.version,
                   dv.document_name, dv.document_version, dv.status,
                   dv.release_subject_type, dv.product_version_id, dv.related_product_id,
                   dv.order_engineering_instance_id, dv.order_engineering_baseline_id,
                   dv.engineering_calculation_id, dv.related_bom_id, dv.related_routing_id
            FROM pde_engineering_document d
            JOIN pde_engineering_document_version dv ON dv.document_id=d.id
            WHERE d.document_no=?
            """,
            ("ED-SO202609180003-L01-001",),
        ).fetchone()
        require(
            registered_document == (
                "ED-SO202609180003-L01-001", "清水封闭房门工艺技术资料",
                "technical", "draft", "ORDER_ENGINEERED_PRODUCT", None,
                2, 3, 31, "",
                "清水封闭房门工艺技术资料", "V1.0", "draft",
                "ORDER_ENGINEERED_PRODUCT", None, None,
                2, 2, 3, 3, 31,
            ),
            f"registered engineering document/version mismatch: {registered_document}",
        )

        routing_rows = connection.execute(
            """
            SELECT si.line_no, rv.id, r.routing_code, rv.revision, rv.status
            FROM pde_order_engineering_instance o
            JOIN sales_order_item si ON si.id=o.sales_order_item_id
            JOIN sales_order so ON so.id=si.sales_order_id
            JOIN pde_routing r
              ON r.company_id=o.company_id
             AND r.applicability_scope='PRODUCT_CATEGORY'
             AND r.product_category_id=o.product_category_id
             AND r.manufacturing_process_type_id=o.selected_process_type_id
             AND r.status='released' AND r.is_active=1
            JOIN pde_routing_version rv ON rv.routing_id=r.id AND rv.status='released'
            WHERE so.order_no=?
            ORDER BY si.line_no
            """,
            ("SO202609180003",),
        ).fetchall()
        require([row[1] for row in routing_rows] == [31, 31, 5, 6], routing_rows)
        require(all(row[3] == 1 and row[4] == "released" for row in routing_rows), routing_rows)
        line1_routing = connection.execute(
            """
            SELECT r.id, r.routing_code, r.name, r.status,
                   rv.id, rv.routing_version, rv.revision, rv.status,
                   (SELECT COUNT(*) FROM pde_routing_step rs WHERE rs.routing_version_id=rv.id)
            FROM pde_order_engineering_instance o
            JOIN sales_order_item si ON si.id=o.sales_order_item_id
            JOIN sales_order so ON so.id=si.sales_order_id
            JOIN pde_routing r
              ON r.company_id=o.company_id
             AND r.applicability_scope='PRODUCT_CATEGORY'
             AND r.product_category_id=o.product_category_id
             AND r.manufacturing_process_type_id=o.selected_process_type_id
             AND r.status='released' AND r.is_active=1
            JOIN pde_routing_version rv ON rv.routing_id=r.id AND rv.status='released'
            WHERE so.order_no=? AND si.line_no=1
            """,
            ("SO202609180003",),
        ).fetchone()
        require(
            line1_routing == (
                31, "QSFB/FM", "清水封闭房门", "released",
                31, "SYSTEM_INITIAL_VERSION", 1, "released", 28,
            ),
            f"line1 routing identity changed: {line1_routing}",
        )

        production_migration_apply_count = scalar(
            connection,
            "SELECT COUNT(*) FROM django_migrations WHERE app='pde' AND name=?",
            ("0035_order_engineered_release_subject_contract",),
        )
        require(
            production_migration_apply_count == 1,
            "release-subject schema must remain applied in the formal database",
        )

        models = (ROOT / "backend/pde/models.py").read_text(encoding="utf-8")
        views = (ROOT / "backend/pde/views.py").read_text(encoding="utf-8")
        registration = (
            ROOT / "backend/pde/order_engineering_document_registration_service.py"
        ).read_text(encoding="utf-8")
        page = (ROOT / "frontend/src/meta/pages/pdePageDefinitions.js").read_text(encoding="utf-8")
        migration = (
            ROOT / "backend/pde/migrations/0035_order_engineered_release_subject_contract.py"
        ).read_text(encoding="utf-8")
        require("class ProductManufacturingOutput" in models, "release record model missing")
        require("class ManufacturingReleaseSubjectType" in models, "release subject type missing")
        for field in (
            "release_subject_type = models.CharField",
            "product_version = models.ForeignKey",
            "order_engineering_baseline = models.ForeignKey",
            "engineering_calculation = models.ForeignKey",
            "bom_version = models.ForeignKey",
            "routing_version = models.ForeignKey",
            "engineering_document_version = models.ForeignKey",
        ):
            require(field in models, f"exact version reference missing: {field}")
        require("已发布产品版本不可原地覆盖" in models, "ProductVersion immutability missing")
        require("已发布工程资料版本不可原地覆盖" in models, "document version immutability missing")
        require("已发布制造定义不可原地覆盖" in models, "release record immutability missing")
        require("routingResolverIsPersistedReleaseBinding\": False" in views, "resolver boundary missing")
        require("databaseBusinessWriteCount\": 0" in views, "zero-write fact missing")
        require("schemaGapRequired\": False" in views, "resolved identity-contract projection missing")
        require("def _document_scope_facts(instance)" in views, "document ownership resolver missing")
        require("documentOwnershipConflictCount" in views, "document conflict fail-closed fact missing")
        require("暂无可发布工程资料" in views, "empty business state missing")
        require("publicationExecutedThisRound\": False" in views, "publication execution boundary missing")
        require(
            'ProductionFoundationService.write(\n                    "engineering-documents"' in registration,
            "controlled document registration write missing",
        )
        require(
            'ProductionFoundationService.write(\n                "engineering-document-versions"' in registration,
            "controlled first-version registration write missing",
        )
        require(
            '"document_version"' not in registration.split(
                'ProductionFoundationService.write(\n                "engineering-document-versions"', 1
            )[1].split("source_identity=", 1)[0],
            "first-version payload must omit document_version",
        )
        require("EngineeringLifecycleService" not in registration, "registration must not call lifecycle transitions")
        require("ProductManufacturingOutput.objects.create" not in registration, "registration must not create manufacturing output")
        require("制造发布主体" in page and "订单工程产品" in page, "release subject UI missing")
        require("title: '工程资料发布'" in page, "node 11 visible title mismatch")
        require("可发布资料数量" in page and "已发布资料数量" in page, "document count columns missing")
        require("资料编号" in page and "资料版本状态" in page, "registered document readback columns missing")
        require("发布阻断原因" in page and "制造发布记录" in page, "release readiness columns missing")
        require("pde_mfg_release_subject_xor" in migration, "database subject XOR missing")
        require("pde_docver_release_subject_xor" in migration, "document subject XOR missing")
    finally:
        connection.close()

    after = sha256(DATABASE)
    require(before == after, "formal database hash changed during read-only gate")
    print("PDE_NODE11_ENGINEERING_RELEASE_STRICT_GATE=PASS")
    print(f"DATABASE_SHA256_BEFORE={before}")
    print(f"DATABASE_SHA256_AFTER={after}")
    print("DATABASE_BUSINESS_WRITE=0")
    print("SO202609180003=4_OEI/4_COMPLETED_CALCULATIONS/388_DETAILS/388_DERIVED_FACTS")
    print("ROUTING_VERSION_IDS=31,31,5,6")
    print("ENGINEERING_DOCUMENT_COUNT=1")
    print("ENGINEERING_DOCUMENT_VERSION_COUNT=1")
    print("PRODUCT_MANUFACTURING_OUTPUT_COUNT=0")
    print("FORMAL_RELEASE_OBJECTS=0")
    print("ORDER_ENGINEERED_RELEASE_IDENTITY_CONTRACT=GO")
    print("CATEGORY_ONLY_RELEASE_MODEL_GAP=0")
    print("FORMAL_MANUFACTURING_ELIGIBILITY=GO")
    print("LINE1=COMP001/SO202609180003/1/OEI202609000001/PRODUCT_BOM_3/CALC-3/ROUTING_31/ROUTING_VERSION_31/28_STEPS")
    print("ACTUAL_ENGINEERING_DOCUMENT_PUBLICATION_COUNT=0")
    print("PUBLICATION_EXECUTED_THIS_ROUND=FALSE")
    print("PRODUCTION_MIGRATION_APPLY=UNCHANGED/ALREADY_APPLIED")


if __name__ == "__main__":
    main()
