"""Read-only evidence for the three-target product-design selection incident."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path


EXPECTED_DATABASE = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
).resolve()
EXPECTED_IDENTITY = "PDE-OPERABLE-ACCEPTANCE-20260912"
TARGET_ITEM_NOS = (
    "SO202609180003-DES-01-SRC-0005",
    "SO202609180003-DES-01-SRC-0006",
    "SO202609180003-DES-01-SRC-0007",
)
DISPLAYED_WRONG_ITEM_NOS = (
    "SO202609180003-DES-01-SRC-0007",
    "SO202609180003-DES-02-SRC-0008",
    "SO202609180003-DES-02-SRC-0009",
)
PROTECTED_ITEM_NO = "SO202609180003-DES-01-SRC-0003"
DESIGN_SAVE_ACTION = "pde.product_design.content.save"


def json_value(raw, fallback):
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw or "")
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


database = Path(os.environ.get("PCE_DATABASE_PATH", "")).resolve()
if database != EXPECTED_DATABASE or not database.is_file():
    raise RuntimeError("READ_ONLY_ACCEPTANCE_DATABASE_MISMATCH")
if os.environ.get("PCE_DATABASE_IDENTITY") != EXPECTED_IDENTITY:
    raise RuntimeError("READ_ONLY_ACCEPTANCE_IDENTITY_MISMATCH")

connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
connection.row_factory = sqlite3.Row
all_item_nos = tuple(dict.fromkeys((PROTECTED_ITEM_NO,) + TARGET_ITEM_NOS + DISPLAYED_WRONG_ITEM_NOS))
placeholders = ",".join("?" for _ in all_item_nos)

try:
    items = [
        dict(row)
        for row in connection.execute(
            f"SELECT id, item_no, version, updated_at FROM pde_product_design_item "
            f"WHERE item_no IN ({placeholders}) ORDER BY item_no",
            all_item_nos,
        ).fetchall()
    ]
    item_by_id = {row["id"]: row["item_no"] for row in items}
    revisions = []
    for row in connection.execute(
        f"SELECT r.id, r.design_item_id, r.revision, r.design_length, r.design_width, "
        f"r.design_thickness, r.change_reason, r.design_data, r.created_at "
        f"FROM pde_product_design_revision r "
        f"JOIN pde_product_design_item i ON i.id = r.design_item_id "
        f"WHERE i.item_no IN ({placeholders}) ORDER BY r.created_at DESC, r.id DESC",
        all_item_nos,
    ).fetchall():
        record = dict(row)
        design_data = json_value(record.pop("design_data"), {})
        record["itemNo"] = item_by_id[record["design_item_id"]]
        record["designNotes"] = design_data.get("designNotes")
        revisions.append(record)

    latest_by_item = {}
    for revision in revisions:
        latest_by_item.setdefault(revision["itemNo"], revision)

    audits = []
    for row in connection.execute(
        "SELECT id, target_id, target_label, reason, before_snapshot, after_snapshot, created_at "
        "FROM system_organization_operating_audits WHERE action_code = ? "
        "ORDER BY created_at DESC, id DESC LIMIT 20",
        (DESIGN_SAVE_ACTION,),
    ).fetchall():
        audit = dict(row)
        before = json_value(audit.pop("before_snapshot"), [])
        after = json_value(audit.pop("after_snapshot"), {})
        changed_revision_ids = [int(value) for value in after.get("changedRevisionIds", [])]
        changed = [revision for revision in revisions if revision["id"] in changed_revision_ids]
        audit.update(
            {
                "changedRevisionIds": changed_revision_ids,
                "changedItemNosInScope": [revision["itemNo"] for revision in changed],
                "changedDesignNotesInScope": sorted(
                    {revision["designNotes"] for revision in changed if revision["designNotes"] is not None}
                ),
                "beforeDesignItemIds": [
                    value.get("designItemId")
                    for value in before
                    if isinstance(value, dict) and value.get("designItemId") is not None
                ],
                "unchangedItemIds": after.get("unchangedItemIds", []),
                "requestHash": after.get("requestHash"),
            }
        )
        audits.append(audit)

    matching_revisions = [
        revision for revision in revisions if revision.get("designNotes") == "见图纸说明1"
    ]
    matching_revision_ids = {revision["id"] for revision in matching_revisions}
    matching_audits = [
        audit for audit in audits if matching_revision_ids.intersection(audit["changedRevisionIds"])
    ]
    payload = {
        "runtime": {
            "profile": os.environ.get("PCE_RUNTIME_PROFILE"),
            "databaseIdentity": os.environ.get("PCE_DATABASE_IDENTITY"),
            "database": str(database),
            "databaseSha256AtRead": hashlib.sha256(database.read_bytes()).hexdigest(),
        },
        "comparison": {
            "originalSelectionTargets": list(TARGET_ITEM_NOS),
            "confirmationDialogTargets": list(TARGET_ITEM_NOS),
            "actualRevisionTargetsForDesignNotes": [row["itemNo"] for row in matching_revisions],
            "postSaveDisplayedSelectionTargets": list(DISPLAYED_WRONG_ITEM_NOS),
        },
        "items": items,
        "latestRevisions": [
            latest_by_item.get(item_no, {"itemNo": item_no, "revision": None})
            for item_no in all_item_nos
        ],
        "matchingDesignNoteRevisions": matching_revisions,
        "matchingDesignSaveAudits": matching_audits,
        "readOnly": True,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
finally:
    connection.close()
