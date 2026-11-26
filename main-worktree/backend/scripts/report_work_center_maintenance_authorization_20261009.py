"""Read-only authorization evidence for WorkCenter maintenance on 2026-10-09."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DATABASE = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
)
sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")
os.environ["PCE_RUNTIME_PROFILE"] = "PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE"
os.environ["PCE_DATABASE_IDENTITY"] = "PDE-OPERABLE-ACCEPTANCE-20260912"
os.environ["PCE_NON_PRODUCTION_ACCEPTANCE"] = "1"
os.environ["PCE_RUNTIME_LAUNCHER_VERIFIED"] = "1"
os.environ["PCE_DATABASE_PATH"] = str(DATABASE)

import django  # noqa: E402

django.setup()

from pde.production_foundation_service import ProductionFoundationService  # noqa: E402
from system.models import User  # noqa: E402


def main() -> None:
    rows = []
    for user in User.objects.filter(company_id=1, is_active=True).order_by("id"):
        decision = ProductionFoundationService.maintenance_authorization(
            "work-centers", user=user,
        )
        if user.username != "admin" and not decision["allowed"]:
            continue
        rows.append(
            {
                "userId": user.pk,
                "username": user.username,
                "realName": user.real_name,
                "allowed": decision["allowed"],
                "permissionAllowed": decision["permissionAllowed"],
                "decisionCode": decision["decisionCode"],
                "reason": decision["reason"],
                "actionCode": decision["actionCode"],
                "requiredScope": decision["requiredScope"],
                "executionChainComplete": decision["executionChainComplete"],
                "executionChain": decision["executionChain"],
            }
        )
    print(json.dumps({"database": str(DATABASE), "decisions": rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
