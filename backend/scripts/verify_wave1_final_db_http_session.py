"""Exercise the exact final manual backend/DB over HTTP before clean handoff."""

import argparse
import json
import os
from pathlib import Path

from verify_wave1_real_session_actor import HttpSession, customer_xlsx, multipart


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--username", default="wave1_import_maintenance_a4")
    args = parser.parse_args()
    password = os.environ["PCE_REHEARSAL_MAINTENANCE_PASSWORD"]
    session = HttpSession()
    login = session.post(f"{args.base_url}/api/auth/login/", json={"username": args.username, "password": password})
    login.raise_for_status()
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    context = session.get(f"{args.base_url}/api/pde/formal-import/current-context/", headers=headers)
    context.raise_for_status()
    actor = context.json()["requestActorTrace"]
    assert actor["requestUsername"] == args.username
    assert actor["resolvedEmployeeId"] and actor["positionId"] and actor["responsibilityId"]
    assert actor["permissionCode"] == "masterdata.customer.maintain"
    assert actor["importAuthorizationResult"] == "ALLOWED"
    template = session.get(f"{args.base_url}/api/pde/formal-import/customers/template/", headers=headers)
    template.raise_for_status()
    content = customer_xlsx(template.content, "A4-FINAL-DB-HTTP-PREFLIGHT")
    preview = session.post(f"{args.base_url}/api/pde/formal-import/customers/preview/", headers=headers, files=multipart(content, "A4-final-db-http-preflight.xlsx"), timeout=20)
    preview.raise_for_status()
    preview_data = preview.json()
    assert preview_data["counts"]["create"] == 1
    fields = {"previewFingerprint": preview_data["previewFingerprint"], "previewActorBinding": json.dumps(preview_data["previewActorBinding"], ensure_ascii=False), "idempotencyKey": "A4-FINAL-DB-HTTP-PREFLIGHT", "confirmed": "true"}
    commit = session.post(f"{args.base_url}/api/pde/formal-import/customers/commit/", headers=headers, data=fields, files=multipart(content, "A4-final-db-http-preflight.xlsx"), timeout=20)
    commit.raise_for_status()
    assert commit.json()["created"] == 1
    readback = session.get(f"{args.base_url}/api/pde/a1-foundation/customers/", headers=headers)
    readback.raise_for_status()
    assert "A4-FINAL-DB-HTTP-PREFLIGHT" in json.dumps(readback.json(), ensure_ascii=False)
    replay = session.post(f"{args.base_url}/api/pde/formal-import/customers/preview/", headers=headers, files=multipart(content, "A4-final-db-http-preflight.xlsx"), timeout=20)
    replay.raise_for_status()
    assert replay.json()["counts"]["match"] == 1
    print(json.dumps({"gate": "FINAL_DB_REAL_HTTP_SESSION", "status": "PASS", "baseUrl": args.base_url, "databasePath": actor["databasePath"], "actor": actor, "firstCommit": "PASS", "replayPreview": "MATCH=1", "readback": "PASS"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
