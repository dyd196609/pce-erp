"""Run the nine-entity formal import chain against an explicitly isolated DB.

The script refuses to run unless PCE_DATABASE_PATH is set and does not resolve
to the repository production database. Successful rows remain in that isolated
copy so API/DB readback and the later manual browser walkthrough use one reality.
"""

import csv
import io
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")

import django
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import load_workbook
from rest_framework.test import APIClient
from unittest.mock import patch

from masterdata.models import UnitOfMeasure
from pfm.models import Employee
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Position,
    PositionResponsibility, Responsibility, Role, RolePermission, User,
    UserRoleScopeAssignment,
)
from pde.production_foundation_service import ProductionFoundationError, ProductionFoundationService
from pde.formal_import_service import FormalImportService


def require_isolated_database():
    configured = os.environ.get("PCE_DATABASE_PATH")
    if not configured:
        raise RuntimeError("PCE_DATABASE_PATH must explicitly name a Fresh Isolated DB")
    actual = Path(configured).resolve()
    production = (Path(__file__).resolve().parents[1] / "db.sqlite3").resolve()
    if actual == production:
        raise RuntimeError("refusing to run formal import acceptance against Production DB")
    return actual


UPLOAD_BYTES = {}


def upload(body, entity):
    cache_key = (entity, body)
    if cache_key in UPLOAD_BYTES:
        return SimpleUploadedFile(
            f"{entity}.xlsx", UPLOAD_BYTES[cache_key],
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    records = list(csv.DictReader(io.StringIO(body)))
    schema = FormalImportService.schema(entity)
    workbook = load_workbook(io.BytesIO(FormalImportService.template_bytes(entity)))
    worksheet = workbook.active
    for row_index, record in enumerate(records, start=2):
        for column_index, field in enumerate(schema["fields"], start=1):
            value = record.get(field["name"], "")
            normalized = str(value).strip().lower()
            if field["type"] == "boolean":
                value = {"true": "是", "false": "否"}.get(normalized, value)
            elif field["choices"]:
                value = field["choiceLabels"].get(value, value)
            worksheet.cell(row_index, column_index, value)
    stream = io.BytesIO()
    workbook.save(stream)
    UPLOAD_BYTES[cache_key] = stream.getvalue()
    return SimpleUploadedFile(
        f"{entity}.xlsx", UPLOAD_BYTES[cache_key],
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def main():
    database = require_isolated_database()
    prefix = "W1FIBC"
    if True:  # visual scope for the complete isolated acceptance fixture
        # Use the copied production tenant so the browser proves continuity of the
        # already accepted 89/121/270 records as well as the newly imported row.
        # The database itself is isolated; no production identity is modified.
        company = Company.objects.get(code="COMP001")
        department = Department.objects.create(code="MFG", name="制造部", company=company)
        user = User.objects.create_user(username="wave1_formal_import_gate", password="test-only", company_id=company.pk)
        role = Role.objects.create(code=f"{prefix}-ROLE", name="Wave1正式导入角色")
        permission_codes = (
            "production.master_data.view", "masterdata.customer.maintain", "masterdata.supplier.maintain",
            "production.master_data.material.maintain", "production.master_data.product.maintain",
            "production.master_data.resource.maintain", "production.master_data.capacity.maintain",
        )
        for code in permission_codes:
            permission, _ = Permission.objects.get_or_create(code=code, defaults={"name": code, "module": "PRODUCTION"})
            RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(user=user, role=role, organization=company, scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION, business_hash="wave1-formal-import-gate")
        responsibility = Responsibility.objects.create(code=f"{prefix}-RESP", name="正式导入职责", status=Responsibility.Status.ACTIVE, is_active=True)
        position = Position.objects.create(code=f"{prefix}-POS", name="正式导入岗位", company=company, department=department, default_role=role)
        PositionResponsibility.objects.create(position=position, responsibility=responsibility, is_primary=True, active=True)
        Employee.objects.create(user=user, employee_no=f"{prefix}-E1", full_name="正式导入验收员", department_ref=department, position_ref=position, status="active")
        UnitOfMeasure.objects.create(code="PCS", name="件", symbol="pcs", dimension="count", company_id=company.pk)

        samples = {
            "customers": "code,name,is_active\nW1-CUST,Wave1客户,true\n",
            "suppliers": "code,name,delivery_address,category,credit_rating,lead_time,is_active\nW1-SUP,Wave1供应商,隔离交付地址,正式,A,2,true\n",
            "materials": "code,name,specification,unit,unit_status,material_type,is_purchased,is_produced,is_active\nW1-MAT,Wave1成品,,件,confirmed,finished,false,true,true\n",
            "products": "product_code,product_name,emd_material_code,specification,model,manufacturing_definition_mode,status,is_active\nW1-PROD,Wave1产品,W1-MAT,,,standard,draft,true\n",
            "workshops": "code,name,department_code,is_active\nW1-WS,Wave1车间,MFG,true\n",
            "work-centers": "code,name,department_code,workshop_code,standard_labor_capacity,machine_hours,unit_labor_cost,manufacturing_overhead,is_active\nW1-WC,Wave1工作中心,MFG,W1-WS,1,1,0,0,true\n",
            "operations": "code,name,workshop_code,work_center_code,operation_kind,calculation_basis,calculation_uom_code,default_transition_mode,is_active\nW1-OP,Wave1工序,W1-WS,W1-WC,atomic,count,PCS,GENERAL,true\n",
            "equipment": "code,name,equipment_type,work_center_code,capacity_per_hour,interface_identity,is_active\nW1-EQ,Wave1设备,通用,W1-WC,10,,true\n",
            "standard-capacities": "code,name,resource_scope,resource_code,uom_code,measurement_status,quantity,time_basis,time_basis_quantity,standard_hours,is_active\nW1-CAP,Wave1标准产能,equipment,W1-EQ,PCS,measured,10,hour,1,,true\n",
        }
        client = APIClient()
        client.force_authenticate(user)
        outcomes = {}
        audit_before = OrganizationOperatingAuditRecord.objects.count()
        for entity, body in samples.items():
            template = client.get(f"/api/pde/formal-import/{entity}/template/")
            assert template.status_code == 200, (entity, template.status_code)
            preview = client.post(f"/api/pde/formal-import/{entity}/preview/", {"file": upload(body, entity)}, format="multipart")
            assert preview.status_code == 200 and preview.data["canCommit"], (entity, preview.status_code, getattr(preview, "data", None))
            assert preview.data["writeCount"] == 0
            commit = client.post(f"/api/pde/formal-import/{entity}/commit/", {
                "file": upload(body, entity), "previewFingerprint": preview.data["previewFingerprint"],
                "idempotencyKey": f"{prefix}-{entity}", "confirmed": "true",
            }, format="multipart")
            assert commit.status_code == 201 and commit.data["created"] == 1, (entity, commit.status_code, getattr(commit, "data", None))
            replay_preview = client.post(f"/api/pde/formal-import/{entity}/preview/", {"file": upload(body, entity)}, format="multipart")
            assert replay_preview.data["counts"]["match"] == 1
            outcomes[entity] = {"template": "PASS", "xlsxUpload": "PASS", "previewZeroWrite": "PASS", "commit": "PASS", "readback": "PASS", "replayMatch": "PASS"}
        assert OrganizationOperatingAuditRecord.objects.count() - audit_before == 9

        invalid = client.post("/api/pde/formal-import/customers/preview/", {"file": upload("code,name,is_active\nBAD,,maybe\n", "customers")}, format="multipart")
        assert invalid.status_code == 200 and not invalid.data["canCommit"] and invalid.data["errors"]
        customer_count = len(client.get("/api/pde/a1-foundation/customers/").data["facts"]["customers"])

        readonly = User.objects.create_user(username="wave1_formal_import_readonly", password="test-only", company_id=company.pk)
        readonly_role = Role.objects.create(code=f"{prefix}-READ", name="Wave1正式导入只读角色")
        view_permission = Permission.objects.get(code="production.master_data.view")
        RolePermission.objects.create(role=readonly_role, permission=view_permission)
        UserRoleScopeAssignment.objects.create(user=readonly, role=readonly_role, organization=company, scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION, business_hash="wave1-formal-import-readonly")
        client.force_authenticate(readonly)
        denied_body = "code,name,is_active\nW1-DENIED,无权写入客户,true\n"
        denied_preview = client.post("/api/pde/formal-import/customers/preview/", {"file": upload(denied_body, "customers")}, format="multipart")
        denied = client.post("/api/pde/formal-import/customers/commit/", {"file": upload(denied_body, "customers"), "previewFingerprint": denied_preview.data["previewFingerprint"], "idempotencyKey": f"{prefix}-DENIED", "confirmed": "true"}, format="multipart")
        assert denied.status_code == 403
        client.force_authenticate(user)

        rollback_body = "code,name,is_active\nW1-RB1,回滚客户一,true\nW1-RB2,回滚客户二,true\n"
        rollback_preview = client.post("/api/pde/formal-import/customers/preview/", {"file": upload(rollback_body, "customers")}, format="multipart")
        original_write = ProductionFoundationService.write
        call_count = {"value": 0}
        def fail_second(*args, **kwargs):
            call_count["value"] += 1
            if call_count["value"] == 2:
                raise ProductionFoundationError("INJECTED_SECOND_ROW_FAILURE", "隔离验收注入第二行失败")
            return original_write(*args, **kwargs)
        with patch.object(ProductionFoundationService, "write", side_effect=fail_second):
            rolled_back = client.post("/api/pde/formal-import/customers/commit/", {"file": upload(rollback_body, "customers"), "previewFingerprint": rollback_preview.data["previewFingerprint"], "idempotencyKey": f"{prefix}-ROLLBACK", "confirmed": "true"}, format="multipart")
        assert rolled_back.status_code == 400 and rolled_back.data["code"] == "INJECTED_SECOND_ROW_FAILURE"
        final_customer_count = len(client.get("/api/pde/a1-foundation/customers/").data["facts"]["customers"])
        assert final_customer_count == customer_count
        print(json.dumps({
            "gate": "WAVE1_FORMAL_IMPORT_RUNTIME_ACCEPTANCE", "status": "PASS",
            "database": str(database), "productionDatabaseUsed": False,
            "entities": outcomes, "formalWrites": 9, "auditWrites": 9,
            "readOnlyWriteDenied": True, "secondRowFailureAtomicRollback": True,
            "transactionOutcome": "PERSISTED_IN_ISOLATED_DB_ONLY",
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"gate": "WAVE1_FORMAL_IMPORT_RUNTIME_ACCEPTANCE", "status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        sys.exit(1)
