"""Prove A3/B3/C3 Preview readiness and maintenance actor context with zero writes."""

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

from pde.formal_import_actor_context import resolve_formal_import_actor
from pde.formal_import_service import FormalImportService
from pde.production_foundation_service import ENTITY_CONFIG
from system.models import Company, OrganizationOperatingAuditRecord, User


SAMPLES = {
    "customers": ("A3-客户人工导入样例.xlsx", "masterdata.customer.maintain"),
    "materials": ("B3-物料人工导入样例.xlsx", "production.master_data.material.maintain"),
    "workshops": ("C3-车间人工导入样例.xlsx", "production.master_data.resource.maintain"),
}


def entity_count(entity, company_id):
    model = ENTITY_CONFIG[entity][0]
    names = {field.name for field in model._meta.fields}
    if "company" in names or "company_id" in names:
        return model.objects.filter(company_id=company_id).count()
    return model.objects.filter(work_center__company_id=company_id).count()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sample_dir")
    parser.add_argument("--username", default="wave1_import_maintenance_a3")
    args = parser.parse_args()
    configured = os.environ.get("PCE_DATABASE_PATH")
    if not configured:
        raise RuntimeError("PCE_DATABASE_PATH must explicitly name the isolated manual DB")
    database = Path(configured).resolve()
    production = (Path(__file__).resolve().parents[1] / "db.sqlite3").resolve()
    if database == production:
        raise RuntimeError("refusing to use the Production DB")
    sample_dir = Path(args.sample_dir).resolve()
    company = Company.objects.get(code="COMP001")
    user = User.objects.get(username=args.username)
    audits_before = OrganizationOperatingAuditRecord.objects.count()
    counts_before = {entity: entity_count(entity, company.pk) for entity in SAMPLES}
    results = {}
    for entity, (filename, action_code) in SAMPLES.items():
        actor = resolve_formal_import_actor(
            user=user, organization_id=company.pk, action_code=action_code,
        )
        path = sample_dir / filename
        uploaded = SimpleUploadedFile(
            filename, path.read_bytes(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        preview = FormalImportService.preview(
            entity, uploaded_file=uploaded, organization_id=company.pk,
        )
        assert preview["canCommit"] and preview["counts"]["create"] == 1
        assert preview["counts"]["match"] == 0 and preview["writeCount"] == 0
        results[entity] = {
            "file": filename, "preview": "PASS", "create": 1, "match": 0,
            "actorContext": actor,
        }
    counts_after = {entity: entity_count(entity, company.pk) for entity in SAMPLES}
    assert counts_after == counts_before
    assert OrganizationOperatingAuditRecord.objects.count() == audits_before
    print(json.dumps({
        "gate": "WAVE1_MANUAL_ACTOR_READINESS", "status": "PASS",
        "database": str(database), "productionDatabaseUsed": False,
        "countsBefore": counts_before, "countsAfter": counts_after,
        "businessWrites": 0, "auditWrites": 0, "results": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
