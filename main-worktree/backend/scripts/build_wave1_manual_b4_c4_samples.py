"""Build only the Material B4 and Workshop C4 manual samples.

The files are derived from the existing governed template bytes.  This script
does not bootstrap or mutate any actor, business row, or template definition.
"""

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


SAMPLES = {
    "materials": {
        "filename": "B4-物料人工导入样例.xlsx",
        "values": [
            "W1-B4-MAT-20260911",
            "Wave1 B4同一执行主体验收物料",
            "B4验收规格",
            "件",
            "已确认",
            "成品",
            "否",
            "是",
            "是",
        ],
    },
    "workshops": {
        "filename": "C4-车间人工导入样例.xlsx",
        "values": [
            "W1-C4-WS-20260911",
            "Wave1 C4同一执行主体验收车间",
            "W1AC-A4-20260911",
            "是",
        ],
    },
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir")
    output_dir = Path(parser.parse_args().output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for entity, sample in SAMPLES.items():
        workbook = load_workbook(io.BytesIO(FormalImportService.template_bytes(entity)))
        sheet = workbook.active
        for column, value in enumerate(sample["values"], start=1):
            sheet.cell(2, column, value)
        target = output_dir / sample["filename"]
        workbook.save(target)
        print(target)


if __name__ == "__main__":
    main()
