"""Preview the three localized manual samples against an isolated DB with zero writes."""

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")

import django
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile

from pde.formal_import_service import FormalImportService
from pde.production_foundation_service import ENTITY_CONFIG
from system.models import Company, OrganizationOperatingAuditRecord


SAMPLES = {
    "customers": "A2-客户人工导入样例.xlsx",
    "materials": "B2-物料人工导入样例.xlsx",
    "workshops": "C2-车间人工导入样例.xlsx",
}


def require_isolated_database():
    configured = os.environ.get("PCE_DATABASE_PATH")
    if not configured:
        raise RuntimeError("PCE_DATABASE_PATH must explicitly name the isolated manual DB")
    actual = Path(configured).resolve()
    production = (Path(__file__).resolve().parents[1] / "db.sqlite3").resolve()
    if actual == production:
        raise RuntimeError("refusing to preview manual samples against Production DB")
    return actual


def entity_count(entity, company_id):
    model = ENTITY_CONFIG[entity][0]
    field_names = {field.name for field in model._meta.fields}
    if "company" in field_names or "company_id" in field_names:
        return model.objects.filter(company_id=company_id).count()
    return model.objects.filter(work_center__company_id=company_id).count()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sample_dir")
    sample_dir = Path(parser.parse_args().sample_dir).resolve()
    database = require_isolated_database()
    company = Company.objects.get(code="COMP001")
    audits_before = OrganizationOperatingAuditRecord.objects.count()
    counts_before = {entity: entity_count(entity, company.pk) for entity in SAMPLES}
    outcomes = {}
    for entity, filename in SAMPLES.items():
        path = sample_dir / filename
        uploaded = SimpleUploadedFile(filename, path.read_bytes(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        preview = FormalImportService.preview(entity, uploaded_file=uploaded, organization_id=company.pk)
        expected = {"total": 1, "ready": 1, "review": 0, "blocked": 0, "create": 1, "match": 0, "validationErrors": 0, "identityConflicts": 0}
        assert preview["counts"] == expected, (entity, preview["counts"])
        assert preview["canCommit"] is True and preview["writeCount"] == 0
        outcomes[entity] = {"file": filename, "preview": "PASS", "decision": "CREATE", "writeCount": 0}
    counts_after = {entity: entity_count(entity, company.pk) for entity in SAMPLES}
    assert counts_after == counts_before
    assert OrganizationOperatingAuditRecord.objects.count() == audits_before
    print(json.dumps({
        "gate": "WAVE1_MANUAL_SAMPLE_READINESS", "status": "PASS",
        "database": str(database), "productionDatabaseUsed": False,
        "entityCountsBefore": counts_before, "entityCountsAfter": counts_after,
        "businessWrites": 0, "auditWrites": 0, "samples": outcomes,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"gate": "WAVE1_MANUAL_SAMPLE_READINESS", "status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        sys.exit(1)
