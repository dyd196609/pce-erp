"""Build only the Customer A4 manual sample from the governed XLSX template."""

import argparse
import io
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")

import django
django.setup()

from openpyxl import load_workbook

from pde.formal_import_service import FormalImportService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir")
    output_dir = Path(parser.parse_args().output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    content = FormalImportService.template_bytes("customers")
    workbook = load_workbook(io.BytesIO(content))
    sheet = workbook.active
    values = ["W1-A4-CUST-20260911", "Wave1 A4真实身份绑定验收客户", "是"]
    for column, value in enumerate(values, start=1):
        sheet.cell(2, column, value)
    target = output_dir / "A4-客户人工导入样例.xlsx"
    workbook.save(target)
    print(target)


if __name__ == "__main__":
    main()
