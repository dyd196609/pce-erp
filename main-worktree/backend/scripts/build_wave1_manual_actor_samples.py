"""Build fresh A3/B3/C3 samples from the real Template Download code path."""

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

from pde.formal_import_views import FormalImportBaseView, FormalImportTemplateView


SAMPLES = {
    "customers": {
        "filename": "A3-客户人工导入样例.xlsx",
        "values": ["W1-A3-CUST-20260911", "Wave1 A3执行主体验收客户", "是"],
    },
    "materials": {
        "filename": "B3-物料人工导入样例.xlsx",
        "values": [
            "W1-A3-MAT-20260911", "Wave1 A3执行主体验收物料", "A3验收规格",
            "件", "已确认", "成品", "否", "是", "是",
        ],
    },
    "workshops": {
        "filename": "C3-车间人工导入样例.xlsx",
        "values": [
            "W1-A3-WS-20260911", "Wave1 A3执行主体验收车间",
            "W1AC-A3-20260911", "是",
        ],
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
            raise RuntimeError(f"formal Template Download failed for {entity}")
        workbook = load_workbook(io.BytesIO(response.content))
        worksheet = workbook.active
        for column, value in enumerate(sample["values"], start=1):
            worksheet.cell(2, column, value)
        workbook.save(output_dir / sample["filename"])
        print(output_dir / sample["filename"])


if __name__ == "__main__":
    main()
