"""Read-only evidence for the D1-D3 organization import business decision."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/evidence/pce-organization-import-business-decision-20260915"
DB = Path("D:/Dev-PCE/Acceptance/PDE-Operable-20260912/pde-operable-acceptance.sqlite3")
BACKUP = OUT / "pde-operable-acceptance.before-d1-d3.sqlite3"
SOURCE = ROOT / "docs/evidence/pce-organization-import-reference-20260914/baseline/部门填写原件.xlsx"

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")
os.environ["PCE_DATABASE_IDENTITY"] = "PDE-OPERABLE-ACCEPTANCE-20260912"
os.environ["PCE_DATABASE_PATH"] = str(DB)
os.environ["PCE_NON_PRODUCTION_ACCEPTANCE"] = "1"

import django

django.setup()

from django.db import connection
from system.models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    OrganizationUnit,
    Process,
    ProcessTeamCapability,
    Team,
    TeamMembership,
    User,
)
from system.organization_import_service import OrganizationImportService as Service
from system.tests_organization_import_v1 import NamedBytesIO


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def backup_mgc():
    with sqlite3.connect(f"file:{BACKUP.as_posix()}?mode=ro", uri=True) as database:
        database.row_factory = sqlite3.Row
        row = database.execute(
            """
            SELECT id, company_id, code, name, parent_id, organization_unit_id,
                   effective_from, effective_to, is_active
            FROM system_department WHERE company_id = 1 AND code = 'MGC'
            """
        ).fetchone()
        company = database.execute(
            "SELECT id, code, name, is_active FROM system_company WHERE id = 1"
        ).fetchone()
        return {"company": dict(company), "mgc": dict(row)}


with connection.cursor() as cursor:
    cursor.execute("PRAGMA query_only=ON")

actor = User.objects.get(pk=1, is_superuser=True, is_active=True)
source_content = SOURCE.read_bytes()
preview, _ = Service.preview(
    "departments",
    uploaded_file=NamedBytesIO(source_content, SOURCE.name),
    user=actor,
)
company = Company.objects.get(pk=1)
mgc = Department.objects.select_related("parent", "organization_unit").get(
    company_id=1, code="MGC"
)
audit = OrganizationOperatingAuditRecord.objects.get(
    pk=2462, action_code="SAVE_COMPANY_NAME_CORRECTION"
)
before = backup_mgc()
after_mgc = {
    "id": mgc.pk,
    "company_id": mgc.company_id,
    "code": mgc.code,
    "name": mgc.name,
    "parent_id": mgc.parent_id,
    "organization_unit_id": mgc.organization_unit_id,
    "effective_from": mgc.effective_from.isoformat() if mgc.effective_from else None,
    "effective_to": mgc.effective_to.isoformat() if mgc.effective_to else None,
    "is_active": mgc.is_active,
}
result = {
    "evidenceType": "FINAL_ACTUAL_READBACK",
    "databaseIdentity": "PDE-OPERABLE-ACCEPTANCE-20260912",
    "databasePath": str(DB),
    "databaseSha256After": sha256(DB),
    "recoverableBackup": {
        "path": str(BACKUP),
        "sha256": sha256(BACKUP),
    },
    "source": {
        "path": str(SOURCE),
        "sha256": sha256(SOURCE),
        "unchangedDuringReplay": SOURCE.read_bytes() == source_content,
        "rows": [
            {
                "rowNumber": row["rowNumber"],
                "code": row["identity"],
                "name": row["objectName"],
                "company": row["rawData"].get("company_code"),
                "parentRaw": row["rawData"].get("parent_code"),
                "parentResolved": row["data"].get("parent_code"),
                "effectiveToRaw": str(row["rawData"].get("effective_to") or ""),
                "decision": row["decision"],
                "state": row["state"],
                "existingId": row["existingId"],
                "errors": [item["errorType"] for item in row["errors"]],
                "excludedDifferences": row["differences"],
            }
            for row in preview["rows"]
        ],
    },
    "preview": {
        "counts": preview["counts"],
        "canCommit": preview["canCommit"],
        "writeCount": preview["writeCount"],
        "targetCompany": preview["targetContext"]["targetCompany"],
    },
    "companyCorrection": {
        "before": before["company"],
        "after": {
            "id": company.pk,
            "code": company.code,
            "name": company.name,
            "is_active": company.is_active,
        },
        "auditId": audit.pk,
        "actionCode": audit.action_code,
        "actorId": audit.actor_id,
        "organizationId": audit.organization_id,
        "beforeSnapshot": audit.before_snapshot,
        "afterSnapshot": audit.after_snapshot,
        "companyOrganizationUnits": list(
            OrganizationUnit.objects.filter(company_id=1, unit_type="COMPANY")
            .order_by("pk").values("id", "code", "name")
        ),
    },
    "mgcNoChange": {
        "before": before["mgc"],
        "after": after_mgc,
        "identical": before["mgc"] == after_mgc,
        "parentCode": mgc.parent.code if mgc.parent_id else None,
        "organizationUnitCode": mgc.organization_unit.code if mgc.organization_unit_id else None,
    },
    "operationTeamSeparation": {
        "operations": list(
            Process.objects.filter(company_id=1, name__in=["开料", "拼皮"])
            .order_by("pk").values("id", "code", "name", "team_id", "workshop_id")
        ),
        "teamCount": Team.objects.filter(company_id=1).count(),
        "teamMembershipCount": TeamMembership.objects.filter(team__company_id=1).count(),
        "operationTeamCapabilityCount": ProcessTeamCapability.objects.filter(
            operation__company_id=1
        ).count(),
        "newTablesAvailable": True,
    },
}

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "ACTUAL_READBACK_AND_PREVIEW.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
)
print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
