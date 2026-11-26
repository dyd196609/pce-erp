"""Parse the real Template Download view bytes for all nine entities."""

import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")

import django
django.setup()

from openpyxl import load_workbook
from rest_framework.test import APIRequestFactory, force_authenticate
from pde.formal_import_service import FORMAL_IMPORT_SCHEMAS, FormalImportService
from pde.formal_import_views import FormalImportBaseView, FormalImportTemplateView


APPROVED_ENGLISH = {"A", "B", "C", "D"}
CJK = re.compile(r"[\u3400-\u9fff]")


def main():
    failures = []
    results = {}
    factory = APIRequestFactory()
    user = SimpleNamespace(is_authenticated=True, company_id=1)
    with tempfile.TemporaryDirectory(prefix="pce-real-template-") as temporary_directory:
        for entity, schema in FORMAL_IMPORT_SCHEMAS.items():
            request = factory.get(f"/api/pde/formal-import/{entity}/template/")
            force_authenticate(request, user=user)
            with patch.object(FormalImportBaseView, "authorize_read", return_value={"allowed": True}):
                response = FormalImportTemplateView.as_view()(request, entity=entity)
            content = bytes(response.content)
            output_path = Path(temporary_directory) / f"{entity}.xlsx"
            output_path.write_bytes(content)
            if response.status_code != 200:
                failures.append(f"{entity}: template download view returned {response.status_code}")
                continue
            if response.get("Content-Type") != "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
                failures.append(f"{entity}: template response is not XLSX")
            if not content.startswith(b"PK\x03\x04"):
                failures.append(f"{entity}: downloaded bytes do not have an XLSX signature")
                continue
            workbook = load_workbook(output_path, data_only=False)
            expected_sheet = FormalImportService.worksheet_name(schema)
            sheet = workbook.active
            headers = [cell.value for cell in sheet[1]]
            expected_headers = [field["label"] for field in schema["fields"]]
            if workbook.sheetnames != [expected_sheet] or not CJK.search(expected_sheet):
                failures.append(f"{entity}: worksheet is not canonical Chinese")
            if headers != expected_headers or any(header in {field["name"] for field in schema["fields"]} for header in headers):
                failures.append(f"{entity}: visible headers are not canonical Chinese labels")
            forbidden = {
                str(code) for field in schema["fields"] for code in field["choices"]
                if str(code) not in APPROVED_ENGLISH
            } | {"true", "false", "TRUE", "FALSE"}
            visible_values = {str(cell.value) for row in sheet.iter_rows() for cell in row if cell.value is not None}
            exposed = sorted(forbidden & visible_values)
            if exposed:
                failures.append(f"{entity}: internal display codes exposed: {exposed}")
            required_validations = sum(bool(field["choices"]) or field["type"] == "boolean" for field in schema["fields"])
            if len(sheet.data_validations.dataValidation) != required_validations:
                failures.append(f"{entity}: localized validation list count mismatch")
            roundtrip = io.BytesIO()
            workbook.save(roundtrip)
            reopened = load_workbook(io.BytesIO(roundtrip.getvalue()), data_only=False)
            if reopened.sheetnames != [expected_sheet] or [cell.value for cell in reopened.active[1]] != expected_headers:
                failures.append(f"{entity}: workbook round-trip changed sheet or headers")
            results[entity] = {
                "downloadView": "FormalImportTemplateView",
                "responseContentType": response.get("Content-Type"),
                "xlsxMagic": content[:4].hex(),
                "worksheet": expected_sheet,
                "headers": headers,
                "localizedValidations": required_validations,
                "roundTrip": "PASS",
            }
    payload = {
        "gate": "verify:pce-import-template-localization",
        "status": "FAIL" if failures else "PASS",
        "templatesParsed": len(results),
        "testedFileEqualsUserDownloadGenerationPath": True,
        "results": results,
        "unapprovedTechnicalEnglish": 0 if not failures else None,
        "failures": failures,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
