"""Verify XLSX/CSV dispatch through the formal preview API view with zero writes."""

import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")

import django
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import load_workbook
from rest_framework.test import APIRequestFactory, force_authenticate

from sales.models import Customer
from system.models import OrganizationOperatingAuditRecord
from pde.formal_import_service import FormalImportService
from pde.formal_import_views import FormalImportBaseView, FormalImportPreviewView


def xlsx_bytes():
    workbook = load_workbook(io.BytesIO(FormalImportService.template_bytes("customers")))
    worksheet = workbook.active
    for index, value in enumerate(["W1-DISPATCH-XLSX", "XLSX分流验证客户", "是"], start=1):
        worksheet.cell(2, index, value)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def preview(name, content, content_type):
    upload = SimpleUploadedFile(name, content, content_type=content_type)
    request = APIRequestFactory().post(
        "/api/pde/formal-import/customers/preview/", {"file": upload}, format="multipart"
    )
    force_authenticate(request, user=SimpleNamespace(is_authenticated=True, company_id=1))
    with patch.object(FormalImportBaseView, "authorize_read", return_value={"allowed": True}):
        return FormalImportPreviewView.as_view()(request, entity="customers")


def main():
    customers_before = Customer.objects.count()
    audits_before = OrganizationOperatingAuditRecord.objects.count()
    xlsx_content = xlsx_bytes()
    valid_xlsx = preview(
        "客户正式导入.xlsx", xlsx_content,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    assert valid_xlsx.status_code == 200 and valid_xlsx.data["fileType"] == "xlsx"
    assert valid_xlsx.data["worksheetName"] == "客户／经销商"
    assert not any("CSV必须使用UTF-8编码" in str(value) for value in valid_xlsx.data.values())

    valid_csv = preview("customers.csv", b"code,name,is_active\nW1-DISPATCH-CSV,CSV\xe5\x88\x86\xe6\xb5\x81\xe9\xaa\x8c\xe8\xaf\x81,true\n", "text/csv")
    assert valid_csv.status_code == 200 and valid_csv.data["fileType"] == "csv"

    non_utf8 = preview("customers.csv", b"code,name,is_active\nW1-BAD-CSV,\xff,true\n", "text/csv")
    assert non_utf8.status_code == 400 and non_utf8.data["code"] == "IMPORT_ENCODING_INVALID"

    fake_xlsx = preview("renamed.xlsx", b"code,name,is_active\nFAKE,not-a-workbook,true\n", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert fake_xlsx.status_code == 400 and fake_xlsx.data["code"] == "IMPORT_FILE_SIGNATURE_INVALID"
    assert "CSV必须使用UTF-8编码" not in fake_xlsx.data["message"]

    renamed_xlsx = preview("renamed.csv", xlsx_content, "text/csv")
    assert renamed_xlsx.status_code == 400 and renamed_xlsx.data["code"] == "IMPORT_FILE_SIGNATURE_INVALID"

    unsupported = preview("customers.ods", b"unsupported", "application/vnd.oasis.opendocument.spreadsheet")
    assert unsupported.status_code == 400 and unsupported.data["code"] == "IMPORT_FILE_TYPE_UNSUPPORTED"

    assert Customer.objects.count() == customers_before
    assert OrganizationOperatingAuditRecord.objects.count() == audits_before
    print(json.dumps({
        "gate": "verify:pce-formal-import-file-type-dispatch", "status": "PASS",
        "supportedImportFileTypes": [".xlsx", ".csv"],
        "validXlsxParser": "XLSX", "validUtf8CsvParser": "CSV",
        "nonUtf8Csv": "IMPORT_ENCODING_INVALID",
        "xlsxNeverCsvEncodingError": True,
        "fakeXlsxRejected": True, "renamedXlsxRejected": True,
        "unsupportedExtensionRejected": True,
        "businessWrites": 0, "auditWrites": 0,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"gate": "verify:pce-formal-import-file-type-dispatch", "status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        raise
