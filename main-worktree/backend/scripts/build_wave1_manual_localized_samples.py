"""Build the three fresh user-manual XLSX samples from the formal schema authority."""

import argparse
import io
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")

import django
django.setup()

from openpyxl import load_workbook
from rest_framework.test import APIRequestFactory, force_authenticate
from pde.formal_import_service import FormalImportService
from pde.formal_import_views import FormalImportBaseView, FormalImportTemplateView


SAMPLES = {
    "customers": {
        "filename": "A2-客户人工导入样例.xlsx",
        "values": ["W1-M2-CUST-20260911", "Wave1 XLSX人工验收客户", "是"],
    },
    "materials": {
        "filename": "B2-物料人工导入样例.xlsx",
        "values": ["W1-M2-MT-20260911", "Wave1 XLSX人工验收物料", "人工验收规格", "件", "已确认", "成品", "否", "是", "是"],
    },
    "workshops": {
        "filename": "C2-车间人工导入样例.xlsx",
        "values": ["W1-M2-WS-20260911", "Wave1 XLSX人工验收车间", "MFG", "是"],
    },
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir")
    output_dir = Path(parser.parse_args().output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    factory = APIRequestFactory()
    user = SimpleNamespace(is_authenticated=True, company_id=1)
    for entity, sample in SAMPLES.items():
        request = factory.get(f"/api/pde/formal-import/{entity}/template/")
        force_authenticate(request, user=user)
        with patch.object(FormalImportBaseView, "authorize_read", return_value={"allowed": True}):
            response = FormalImportTemplateView.as_view()(request, entity=entity)
        if response.status_code != 200 or not response.content.startswith(b"PK\x03\x04"):
            raise RuntimeError(f"formal template download failed for {entity}")
        workbook = load_workbook(io.BytesIO(response.content))
        sheet = workbook.active
        for column, value in enumerate(sample["values"], start=1):
            sheet.cell(2, column, value)
        workbook.save(output_dir / sample["filename"])
        print(output_dir / sample["filename"])


if __name__ == "__main__":
    main()
