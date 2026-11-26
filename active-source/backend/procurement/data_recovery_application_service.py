"""Governed, idempotent Supplier/Procurement recovery application service.

The service is intentionally usable only with recovery_rehearsal_settings. It
creates no workflow or downstream execution facts and never updates an existing
formal Supplier, Material, Purchase Request, Purchase Order or Purchase Item.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import connection, transaction

from masterdata.models import ExternalIdentity, MasterDataWriteRequest, Material
from procurement.models import PurchaseOrder, PurchaseOrderItem, PurchaseRequest, PurchaseRequestItem, Supplier
from system.models import OrganizationOperatingAuditRecord


ACTION_CODE = "procurement.data_recovery.recover"
PRODUCTION_AUTHORIZATION_ID = "PRODUCTION-RECOVERY-MINIMAL-ENTRY-AND-EXECUTION-20260910-002"
FROZEN_LEDGER_SHA256 = "02558E51B4938412986BC6DBA34A8BEF8498773B1078B176C49EEE9C88DB04DE"
FROZEN_CHANGESET_SHA256 = "03C94AF79D7FBF930D166B30E9494F846C078D58A6A766665858B02823ED793D"
FROZEN_PO_COUNT = 104
FROZEN_ITEM_COUNT = 229
FROZEN_LEGACY_SOURCE_COUNT = 296
ALLOWED_ACTIONS = {"KEEP", "MATCH", "LINK", "RECOVER", "REVIEW", "BLOCK"}
DOWNSTREAM_TABLES = (
    "scm_purchase_receipt", "scm_purchase_inspection", "scm_warehouse_inbound",
    "scm_inventory_balance", "scm_inventory_transaction", "supplier_reconciliations",
    "supplier_payable_confirmations", "supplier_payment_requests",
    "supplier_payment_status_records", "supplier_settlement_completions",
    "payable_check_authority_records", "purchase_reconciliations",
)


class DataRecoveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class _AuthorizedProductionContext:
    authorization_id: str
    phase: str
    target_kind: str
    database: Path
    database_sha256: str
    ledger_sha256: str
    changeset_sha256: str
    source_snapshot: Path | None = None
    backup_sha256: str | None = None
    quiescence_proof_sha256: str | None = None
    dry_run_proof_sha256: str | None = None


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def _fingerprint(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest().upper()


def _file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _date(value):
    return date.fromisoformat(value) if value else None


def _datetime(value):
    return datetime.fromisoformat(value) if value else None


def _production_database_path():
    return (Path(settings.BASE_DIR) / "db.sqlite3").resolve()


def _assert_boundary(expected_run_id, production_context=None):
    actual = Path(settings.DATABASES["default"]["NAME"]).resolve()
    production = _production_database_path()
    if production_context is not None:
        if not isinstance(production_context, _AuthorizedProductionContext):
            raise DataRecoveryError("AUTHORIZED_PRODUCTION_CONTEXT_REQUIRED")
        if production_context.authorization_id != PRODUCTION_AUTHORIZATION_ID:
            raise DataRecoveryError("PRODUCTION_AUTHORIZATION_ID_MISMATCH")
        if production_context.database != actual:
            raise DataRecoveryError("PRODUCTION_TARGET_CONTEXT_MISMATCH")
        if production_context.target_kind == "production" and actual != production:
            raise DataRecoveryError("PRODUCTION_TARGET_IDENTITY_MISMATCH")
        if production_context.target_kind == "isolated-production-like":
            if actual == production or "recovery" not in str(actual).casefold():
                raise DataRecoveryError("ISOLATED_PRODUCTION_LIKE_TARGET_REQUIRED")
        return
    if not getattr(settings, "PCE_RECOVERY_REHEARSAL", False):
        raise DataRecoveryError("RECOVERY_REHEARSAL_SETTINGS_REQUIRED")
    if getattr(settings, "PCE_RECOVERY_RUN_ID", "") != expected_run_id:
        raise DataRecoveryError("RECOVERY_RUN_ID_MISMATCH")
    production = Path(settings.PCE_PRODUCTION_DATABASE_PATH).resolve()
    if actual == production or "recovery" not in str(actual).casefold():
        raise DataRecoveryError("PRODUCTION_BOUNDARY_VIOLATION")


def _model_snapshot(model, *, ids=None):
    query = model.objects.order_by("pk")
    if ids is not None:
        query = query.filter(pk__in=ids)
    return _fingerprint(list(query.values()))


def _table_snapshot(table):
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT * FROM "{table}" ORDER BY 1')
        columns = [item[0] for item in cursor.description]
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return {"count": len(data), "fingerprint": _fingerprint(data)}


def _baseline(existing_ids=None):
    all_po_ids = list(PurchaseOrder.objects.values_list("pk", flat=True))
    all_item_ids = list(PurchaseOrderItem.objects.values_list("pk", flat=True))
    po_ids = list(existing_ids[0]) if existing_ids else all_po_ids
    item_ids = list(existing_ids[1]) if existing_ids else all_item_ids
    return {
        "counts": {
            "suppliers": Supplier.objects.count(), "materials": Material.objects.count(),
            "purchaseRequests": PurchaseRequest.objects.count(),
            "purchaseRequestItems": PurchaseRequestItem.objects.count(),
            "formalPurchaseOrders": len(all_po_ids), "formalPurchaseItems": len(all_item_ids),
        },
        "existing": {
            "supplier": _model_snapshot(Supplier), "material": _model_snapshot(Material),
            "purchaseRequest": _model_snapshot(PurchaseRequest),
            "purchaseRequestItem": _model_snapshot(PurchaseRequestItem),
            "purchaseOrder": _model_snapshot(PurchaseOrder, ids=po_ids),
            "purchaseItem": _model_snapshot(PurchaseOrderItem, ids=item_ids),
            "purchaseOrderIds": po_ids, "purchaseItemIds": item_ids,
        },
        "downstream": {table: _table_snapshot(table) for table in DOWNSTREAM_TABLES},
    }


def _source_value_matches(actual, expected):
    if actual is None or expected is None:
        return actual is expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return Decimal(str(actual)) == Decimal(str(expected))
    return actual == expected


def _validate_source_snapshot_rows(source_snapshot, rows):
    source_snapshot = Path(source_snapshot).resolve()
    if not source_snapshot.is_file():
        raise DataRecoveryError("FROZEN_SOURCE_SNAPSHOT_REQUIRED")
    identities = [(row["Source Table"], row["Source Internal ID"]) for row in rows]
    if len(rows) != FROZEN_LEGACY_SOURCE_COUNT or len(set(identities)) != len(identities):
        raise DataRecoveryError("FROZEN_SOURCE_BUSINESS_IDENTITY_SET_MISMATCH")
    connection_ro = sqlite3.connect(f"file:{source_snapshot.as_posix()}?mode=ro", uri=True)
    connection_ro.row_factory = sqlite3.Row
    try:
        tables = {
            item[0] for item in connection_ro.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for row in rows:
            table = row["Source Table"]
            if table not in tables:
                raise DataRecoveryError("FROZEN_SOURCE_BUSINESS_IDENTITY_SET_MISMATCH")
            source = connection_ro.execute(
                f'SELECT * FROM "{table}" WHERE id=?', (row["Source Internal ID"],)
            ).fetchone()
            payload = row["Source Payload"]
            if source is None or any(
                key not in source.keys() or not _source_value_matches(source[key], expected)
                for key, expected in payload.items()
            ):
                raise DataRecoveryError("FROZEN_SOURCE_BUSINESS_IDENTITY_SET_MISMATCH")
    finally:
        connection_ro.close()


def _validated_source_snapshot(source_snapshot, expected_sha):
    source_snapshot = Path(source_snapshot).resolve() if source_snapshot else None
    if source_snapshot is None or not source_snapshot.is_file() or not expected_sha:
        raise DataRecoveryError("FROZEN_SOURCE_SNAPSHOT_REQUIRED")
    if _file_sha(source_snapshot) != expected_sha:
        raise DataRecoveryError("FROZEN_SOURCE_SNAPSHOT_SHA_MISMATCH")
    return source_snapshot


def _validate_ledger(document, expected_run_id, source_snapshot=None):
    if document.get("schemaVersion") != "1.0" or document.get("runId") != expected_run_id:
        raise DataRecoveryError("RECOVERY_LEDGER_SCHEMA_OR_RUN_MISMATCH")
    rows = document.get("rows")
    if not isinstance(rows, list) or not rows:
        raise DataRecoveryError("RECOVERY_LEDGER_EMPTY")
    if any(row.get("Target Action") not in ALLOWED_ACTIONS for row in rows):
        raise DataRecoveryError("RECOVERY_LEDGER_UNCLASSIFIED")
    recover = [row for row in rows if row["Target Action"] == "RECOVER"]
    if any(row["Target Business Object"] not in {"PurchaseOrder", "PurchaseOrderItem"} for row in recover):
        raise DataRecoveryError("UNAUTHORIZED_RECOVERY_OBJECT")
    legacy_rows = [row for row in recover if row["Source Type"] == "CURRENT_LEGACY_TABLE"]
    if source_snapshot is not None:
        _validate_source_snapshot_rows(source_snapshot, legacy_rows)
    source_sha_cache = {}
    for row in recover:
        if source_snapshot is not None and row["Source Type"] == "CURRENT_LEGACY_TABLE":
            continue
        source_path = Path(row["Source Database"])
        expected_sha = row["Provenance"].get("sourceSha256")
        actual_sha = source_sha_cache.get(source_path)
        if source_path.is_file() and actual_sha is None:
            actual_sha = source_sha_cache[source_path] = _file_sha(source_path)
        if not source_path.is_file() or actual_sha != expected_sha:
            raise DataRecoveryError(f"RECOVERY_SOURCE_SHA_MISMATCH:{source_path}")
    return recover


def _validate_frozen_selection(document, expected_run_id, source_snapshot=None):
    recover = _validate_ledger(document, expected_run_id, source_snapshot)
    order_rows = [row for row in recover if row["Target Business Object"] == "PurchaseOrder"]
    item_rows = [row for row in recover if row["Target Business Object"] == "PurchaseOrderItem"]
    if len(order_rows) != FROZEN_PO_COUNT:
        raise DataRecoveryError("FROZEN_PURCHASE_ORDER_COUNT_MISMATCH")
    if len(item_rows) != FROZEN_ITEM_COUNT:
        raise DataRecoveryError("FROZEN_PURCHASE_ITEM_COUNT_MISMATCH")
    if any(row["Target Action"] != "RECOVER" for row in order_rows + item_rows):
        raise DataRecoveryError("REVIEW_OR_BLOCK_SELECTED")
    return recover, order_rows, item_rows


def _load_json_proof(path, expected_sha, error_code):
    proof_path = Path(path).resolve() if path else None
    if not proof_path or not proof_path.is_file() or not expected_sha:
        raise DataRecoveryError(error_code)
    actual_sha = _file_sha(proof_path)
    if actual_sha != expected_sha:
        raise DataRecoveryError(f"{error_code}_SHA_MISMATCH")
    try:
        document = json.loads(proof_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DataRecoveryError(f"{error_code}_INVALID_JSON") from exc
    return proof_path, actual_sha, document


def _sqlite_gate_baseline(path):
    path = Path(path).resolve()
    uri = f"file:{path.as_posix()}?mode=ro"
    connection_ro = sqlite3.connect(uri, uri=True)
    try:
        cursor = connection_ro.cursor()
        counts = {
            table: cursor.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in (
                "supplier", "material", "scm_purchase_request", "scm_purchase_request_item",
                "purchase_order", "purchase_order_item", "scm_purchase_receipt",
                "scm_purchase_inspection", "scm_warehouse_inbound", "scm_inventory_balance",
                "scm_inventory_transaction", "supplier_reconciliations",
                "supplier_payable_confirmations", "supplier_payment_requests",
                "supplier_payment_status_records", "supplier_settlement_completions",
            )
        }
        orphan_count = len(cursor.execute("PRAGMA foreign_key_check").fetchall())
        return {"counts": counts, "foreignKeyOrphans": orphan_count}
    finally:
        connection_ro.close()


def _sqlite_identity_duplicates(path):
    path = Path(path).resolve()
    connection_ro = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        cursor = connection_ro.cursor()
        queries = {
            "purchaseOrder": "SELECT po_no FROM purchase_order WHERE po_no IS NOT NULL GROUP BY po_no HAVING COUNT(*)>1",
            "supplier": "SELECT company_id, code FROM supplier GROUP BY company_id, code HAVING COUNT(*)>1",
            "material": "SELECT company_id, code FROM material GROUP BY company_id, code HAVING COUNT(*)>1",
        }
        return {name: len(cursor.execute(query).fetchall()) for name, query in queries.items()}
    finally:
        connection_ro.close()


def _validate_production_gate(
    *, phase, target_kind, ledger_path, changeset_path, run_id, authorization_id,
    expected_database_sha, expected_ledger_sha, expected_changeset_sha,
    backup_path=None, expected_backup_sha=None, quiescence_proof_path=None,
    expected_quiescence_proof_sha=None, dry_run_proof_path=None,
    expected_dry_run_proof_sha=None,
):
    if phase not in {"precheck", "dry-run", "commit"}:
        raise DataRecoveryError("PRODUCTION_RECOVERY_PHASE_INVALID")
    if authorization_id != PRODUCTION_AUTHORIZATION_ID:
        raise DataRecoveryError("PRODUCTION_AUTHORIZATION_ID_MISMATCH")
    if target_kind not in {"production", "isolated-production-like"}:
        raise DataRecoveryError("PRODUCTION_TARGET_KIND_INVALID")
    actual = Path(settings.DATABASES["default"]["NAME"]).resolve()
    production = _production_database_path()
    if target_kind == "production" and actual != production:
        raise DataRecoveryError("PRODUCTION_TARGET_IDENTITY_MISMATCH")
    if target_kind == "isolated-production-like" and (
        actual == production or "recovery" not in str(actual).casefold()
    ):
        raise DataRecoveryError("ISOLATED_PRODUCTION_LIKE_TARGET_REQUIRED")
    actual_database_sha = _file_sha(actual)
    if not expected_database_sha or actual_database_sha != expected_database_sha:
        raise DataRecoveryError("PRODUCTION_DATABASE_SHA_MISMATCH")
    ledger_sha = _file_sha(ledger_path)
    changeset_sha = _file_sha(changeset_path)
    if expected_ledger_sha != FROZEN_LEDGER_SHA256 or ledger_sha != FROZEN_LEDGER_SHA256:
        raise DataRecoveryError("FROZEN_LEDGER_SHA_MISMATCH")
    if expected_changeset_sha != FROZEN_CHANGESET_SHA256 or changeset_sha != FROZEN_CHANGESET_SHA256:
        raise DataRecoveryError("FROZEN_CHANGESET_SHA_MISMATCH")
    document = json.loads(Path(ledger_path).read_text(encoding="utf-8"))
    backup_sha = quiescence_sha = dry_run_sha = None
    backup_baseline_matches = True
    backup = Path(backup_path).resolve() if backup_path else None
    if not backup or not backup.is_file() or backup == actual or not expected_backup_sha:
        raise DataRecoveryError("VALID_SAFETY_BACKUP_REQUIRED")
    backup_sha = _file_sha(backup)
    if backup_sha != expected_backup_sha:
        raise DataRecoveryError("SAFETY_BACKUP_SHA_MISMATCH")
    _validate_frozen_selection(document, run_id, backup)
    if phase in {"dry-run", "commit"}:
        backup_baseline_matches = _sqlite_gate_baseline(backup) == _sqlite_gate_baseline(actual)
        if phase == "dry-run" and not backup_baseline_matches:
            raise DataRecoveryError("SAFETY_BACKUP_LOGICAL_BASELINE_MISMATCH")
        _, quiescence_sha, quiescence = _load_json_proof(
            quiescence_proof_path, expected_quiescence_proof_sha,
            "PRODUCTION_WRITE_QUIESCENCE_NOT_PROVEN",
        )
        if (
            quiescence.get("status") != "PASS"
            or quiescence.get("targetPath") != str(actual)
            or quiescence.get("targetSha256") != actual_database_sha
            or quiescence.get("sqliteImmediateLockAcquired") is not True
            or quiescence.get("unknownWriterPids") != []
        ):
            raise DataRecoveryError("PRODUCTION_WRITE_QUIESCENCE_NOT_PROVEN")
    if phase == "commit":
        _, dry_run_sha, dry_run = _load_json_proof(
            dry_run_proof_path, expected_dry_run_proof_sha,
            "SUCCESSFUL_PRODUCTION_DRY_RUN_REQUIRED",
        )
        dry_counts = dry_run.get("counts", {})
        dry_run_database_matches = dry_run.get("databaseSha256") == actual_database_sha
        complete_replay_state = False
        if not dry_run_database_matches:
            complete_replay_state = _complete_replay_state(document, run_id, backup)
        if not backup_baseline_matches and not complete_replay_state:
            raise DataRecoveryError("SAFETY_BACKUP_LOGICAL_BASELINE_MISMATCH")
        if (
            dry_run.get("phase") != "dry-run"
            or dry_run.get("status") != "PASS"
            or dry_run.get("database") != str(actual)
            or not (dry_run_database_matches or complete_replay_state)
            or dry_run.get("ledgerSha256") != ledger_sha
            or dry_run.get("changesetSha256") != changeset_sha
            or dry_counts.get("purchaseOrdersCreated") != FROZEN_PO_COUNT
            or dry_counts.get("purchaseItemsCreated") != FROZEN_ITEM_COUNT
            or dry_counts.get("supplierCreated") != 0
            or dry_counts.get("materialCreated") != 0
            or dry_run.get("downstreamCreates") != 0
            or dry_run.get("reviewBlockSelected") != 0
            or dry_run.get("identityCollisions") != 0
            or dry_run.get("productionWrites") != 0
        ):
            raise DataRecoveryError("SUCCESSFUL_PRODUCTION_DRY_RUN_REQUIRED")
    settings.PCE_RECOVERY_RUN_ID = run_id
    return _AuthorizedProductionContext(
        authorization_id=authorization_id, phase=phase, target_kind=target_kind,
        database=actual, database_sha256=actual_database_sha,
        ledger_sha256=ledger_sha, changeset_sha256=changeset_sha,
        source_snapshot=backup,
        backup_sha256=backup_sha, quiescence_proof_sha256=quiescence_sha,
        dry_run_proof_sha256=dry_run_sha,
    )


def _production_preview(ledger_path, run_id, context):
    sha_before = _file_sha(context.database)
    document = json.loads(Path(ledger_path).read_text(encoding="utf-8"))
    _, order_rows, item_rows = _validate_frozen_selection(
        document, run_id, context.source_snapshot,
    )
    existing_source_bindings = 0
    po_collisions = 0
    missing_suppliers = 0
    missing_materials = 0
    missing_parents = 0
    frozen_po_numbers = {row["Target Payload"]["po_no"] for row in order_rows}
    for row in order_rows:
        existing_source_bindings += int(ExternalIdentity.objects.filter(**_source_lookup(row)).exists())
        payload = row["Target Payload"]
        po_collisions += int(PurchaseOrder.objects.filter(po_no=payload["po_no"]).exists())
        missing_suppliers += int(not Supplier.objects.filter(
            company_id=payload["company_id"], code=payload["supplier_code"]
        ).exists())
    for row in item_rows:
        existing_source_bindings += int(ExternalIdentity.objects.filter(**_source_lookup(row)).exists())
        payload = row["Target Payload"]
        missing_materials += int(not Material.objects.filter(
            company_id=1, code=payload["material_code"]
        ).exists())
        parent_number = _parent_po_number(row)
        missing_parents += int(
            parent_number not in frozen_po_numbers
            and not PurchaseOrder.objects.filter(po_no=parent_number).exists()
        )
    identity_collisions = existing_source_bindings + po_collisions + missing_suppliers + missing_materials + missing_parents
    sha_after = _file_sha(context.database)
    if sha_after != sha_before:
        raise DataRecoveryError("DRY_RUN_CHANGED_DATABASE")
    if identity_collisions:
        raise DataRecoveryError("FROZEN_RECOVERY_IDENTITY_COLLISION")
    return {
        "phase": "dry-run", "status": "PASS", "runId": run_id,
        "authorizationId": context.authorization_id, "targetKind": context.target_kind,
        "database": str(context.database), "databaseSha256": sha_after,
        "ledgerSha256": context.ledger_sha256, "changesetSha256": context.changeset_sha256,
        "backupSha256": context.backup_sha256,
        "quiescenceProofSha256": context.quiescence_proof_sha256,
        "counts": {"purchaseOrdersCreated": len(order_rows), "purchaseItemsCreated": len(item_rows),
                   "supplierCreated": 0, "materialCreated": 0, "purchaseRequestCreated": 0},
        "downstreamCreates": 0, "reviewBlockSelected": 0,
        "identityCollisions": 0, "productionWrites": 0,
    }


def _complete_replay_state(document, run_id, source_snapshot):
    _, order_rows, item_rows = _validate_frozen_selection(
        document, run_id, source_snapshot,
    )
    for row in order_rows:
        try:
            target = _existing_binding(row, PurchaseOrder)
        except DataRecoveryError as exc:
            if str(exc) == "IDEMPOTENT_REPLAY_TARGET_MISSING":
                return False
            raise
        if target is None or target.po_no != row["Target Payload"]["po_no"]:
            return False
    for row in item_rows:
        try:
            target = _existing_binding(row, PurchaseOrderItem)
        except DataRecoveryError as exc:
            if str(exc) == "IDEMPOTENT_REPLAY_TARGET_MISSING":
                return False
            raise
        if target is None or target.po.po_no != _parent_po_number(row):
            return False
    target_baseline = _sqlite_gate_baseline(settings.DATABASES["default"]["NAME"])
    source_baseline = _sqlite_gate_baseline(source_snapshot)
    target_duplicates = _sqlite_identity_duplicates(settings.DATABASES["default"]["NAME"])
    protected_tables = set(source_baseline["counts"]) - {"purchase_order", "purchase_order_item"}
    return (
        PurchaseOrder.objects.count() == 325
        and PurchaseOrderItem.objects.count() == 724
        and Supplier.objects.count() == 121
        and Material.objects.count() == 270
        and PurchaseRequest.objects.count() == 58
        and PurchaseRequestItem.objects.count() == 104
        and target_baseline["foreignKeyOrphans"] == 0
        and all(
            target_baseline["counts"][table] == source_baseline["counts"][table]
            for table in protected_tables
        )
        and not any(target_duplicates.values())
        and MasterDataWriteRequest.objects.filter(
            action_code=ACTION_CODE, idempotency_key__startswith=f"{run_id}:"
        ).count() == FROZEN_PO_COUNT + FROZEN_ITEM_COUNT
    )


def _source_lookup(row):
    return {
        "organization_id": int(row["Target Payload"].get("company_id") or 1),
        "source_system": f"{row['Source Type']}:{row['Provenance']['sourceSha256'][:16]}",
        "source_type": "DATA_RECOVERY_REHEARSAL",
        "source_object_type": row["Target Business Object"],
        "external_id": str(row["Source Business Key"]),
    }


def _bind_source(*, row, target, actor, created):
    lookup = _source_lookup(row)
    source_fingerprint = _fingerprint(row["Source Payload"])
    identity, identity_created = ExternalIdentity.objects.select_for_update().get_or_create(
        **lookup,
        defaults={
            "target_entity_type": f"procurement.{row['Target Business Object']}",
            "target_entity_id": str(target.pk), "mapping_status": ExternalIdentity.MappingStatus.MATCH,
            "source_fingerprint": source_fingerprint,
            "audit_metadata": {**row["Provenance"], "sourceDatabase": row["Source Database"],
                               "sourceTable": row["Source Table"], "sourceInternalId": row["Source Internal ID"],
                               "formalBusinessIdentity": row["Formal Business Identity"]},
        },
    )
    expected_type = f"procurement.{row['Target Business Object']}"
    if (identity.target_entity_type != expected_type or identity.target_entity_id != str(target.pk)
            or identity.source_fingerprint != source_fingerprint):
        raise DataRecoveryError("SOURCE_IDENTITY_TARGET_OR_PAYLOAD_CONFLICT")
    key = f"{settings.PCE_RECOVERY_RUN_ID}:{row['Source Type']}:{row['Target Business Object']}:{row['Source Internal ID']}"
    request_hash = _fingerprint(row["Target Payload"])
    request, request_created = MasterDataWriteRequest.objects.select_for_update().get_or_create(
        organization_id=lookup["organization_id"], action_code=ACTION_CODE,
        idempotency_key=key,
        defaults={
            "entity_type": row["Target Business Object"], "request_hash": request_hash,
            "source_identity": identity, "status": MasterDataWriteRequest.Status.COMMITTED,
            "target_entity_id": str(target.pk),
            "result": {"created": created, "targetId": target.pk, "runId": settings.PCE_RECOVERY_RUN_ID},
            "audit_metadata": {"sourceIdentityId": identity.pk, "recoveryRunId": settings.PCE_RECOVERY_RUN_ID},
        },
    )
    if (request.request_hash != request_hash or request.target_entity_id != str(target.pk)
            or request.source_identity_id != identity.pk):
        raise DataRecoveryError("IDEMPOTENCY_PAYLOAD_OR_TARGET_CONFLICT")
    if created and not identity_created:
        raise DataRecoveryError("NEW_TARGET_HAS_PREEXISTING_SOURCE_IDENTITY")
    if request_created:
        OrganizationOperatingAuditRecord.objects.create(
            action_code=ACTION_CODE, actor=actor, organization_id=lookup["organization_id"],
            target_type=row["Target Business Object"], target_id=target.pk,
            target_label=str(getattr(target, "po_no", None) or target.pk),
            reason="受控隔离库历史数据恢复演练；不重放业务工作流",
            before_snapshot={"state": "MISSING", "formalBusinessIdentity": row["Formal Business Identity"]},
            after_snapshot={"state": "RECOVERED" if created else "MATCHED", "sourceIdentityId": identity.pk,
                            "recoveryRunId": settings.PCE_RECOVERY_RUN_ID, "factSource": "server"},
        )
    return request_created


def _existing_binding(row, model):
    identity = ExternalIdentity.objects.filter(**_source_lookup(row)).first()
    if not identity:
        return None
    if identity.source_fingerprint != _fingerprint(row["Source Payload"]):
        raise DataRecoveryError("IDEMPOTENT_REPLAY_SOURCE_PAYLOAD_CHANGED")
    target = model.objects.filter(pk=identity.target_entity_id).first()
    if not target:
        raise DataRecoveryError("IDEMPOTENT_REPLAY_TARGET_MISSING")
    return target


def _recover_order(row, actor):
    existing = _existing_binding(row, PurchaseOrder)
    if existing:
        _bind_source(row=row, target=existing, actor=actor, created=False)
        return existing, False
    payload = row["Target Payload"]
    if payload.get("status") != "draft":
        raise DataRecoveryError("NON_DRAFT_RECOVERY_REQUIRES_WORKFLOW_EVIDENCE")
    supplier = Supplier.objects.get(company_id=payload["company_id"], code=payload["supplier_code"])
    if PurchaseOrder.objects.filter(po_no=payload["po_no"]).exists():
        raise DataRecoveryError("FORMAL_PURCHASE_NUMBER_COLLISION")
    target = PurchaseOrder.objects.create(
        po_no=payload["po_no"], supplier=supplier, order_date=_date(payload["order_date"]),
        expected_date=_date(payload.get("expected_date")),
        actual_receive_date=_date(payload.get("actual_receive_date")), status="draft",
        total_amount=Decimal(payload["total_amount"]), remark=payload.get("remark"),
        buyer=payload.get("buyer"), company_id=payload["company_id"], purchase_mode="LEGACY",
        source_type="DATA_RECOVERY_REHEARSAL",
        source_reference=f"{settings.PCE_RECOVERY_RUN_ID}:{row['Source Type']}:{row['Source Internal ID']}",
        source_trace={**row["Provenance"], "sourceDatabase": row["Source Database"],
                      "sourceTable": row["Source Table"], "sourceInternalId": row["Source Internal ID"],
                      "sourceBusinessKey": row["Source Business Key"]},
        price_trace_status="LEGACY_UNTRACED", supplier_code_snapshot=supplier.code,
        supplier_name_snapshot=supplier.name, supplier_contact_snapshot=supplier.contact_person or "",
        supplier_phone_snapshot=supplier.contact_phone or "", supplier_address_snapshot=supplier.address or "",
        delivery_address_snapshot=supplier.delivery_address or "",
    )
    created_at, updated_at = _datetime(payload.get("created_at")), _datetime(payload.get("updated_at"))
    if created_at or updated_at:
        PurchaseOrder.objects.filter(pk=target.pk).update(
            **({"created_at": created_at} if created_at else {}),
            **({"updated_at": updated_at} if updated_at else {}),
        )
        target.refresh_from_db()
    _bind_source(row=row, target=target, actor=actor, created=True)
    return target, True


def _parent_po_number(row):
    for part in str(row["Parent Identity"]).split("|"):
        if part.startswith("po:"):
            return part[3:]
    raise DataRecoveryError("ITEM_PARENT_BUSINESS_IDENTITY_MISSING")


def _recover_item(row, actor):
    existing = _existing_binding(row, PurchaseOrderItem)
    if existing:
        _bind_source(row=row, target=existing, actor=actor, created=False)
        return existing, False
    payload = row["Target Payload"]
    order = PurchaseOrder.objects.get(po_no=_parent_po_number(row))
    material = Material.objects.get(company_id=1, code=payload["material_code"])
    target = PurchaseOrderItem.objects.create(
        po=order, material=material, material_code_snapshot=material.code,
        material_name_snapshot=payload.get("material_name_snapshot") or material.name,
        specification_snapshot=payload.get("specification_snapshot") or material.specification or "",
        unit_snapshot=payload.get("unit_snapshot") or material.unit,
        product_name=payload.get("material_name_snapshot") or material.name,
        specification=payload.get("specification_snapshot"), quantity=Decimal(payload["quantity"]),
        unit_price=Decimal(payload["unit_price"]), amount=Decimal(payload["amount"]),
        actual_quantity=(Decimal(payload["actual_quantity"]) if payload.get("actual_quantity") is not None else None),
        actual_unit_price=(Decimal(payload["actual_unit_price"]) if payload.get("actual_unit_price") is not None else None),
        actual_amount=(Decimal(payload["actual_amount"]) if payload.get("actual_amount") is not None else None),
        actual_arrival_date=_date(payload.get("actual_arrival_date")),
        expected_date=_date(payload.get("expected_date")), remark=payload.get("remark"),
    )
    _bind_source(row=row, target=target, actor=actor, created=True)
    return target, True


class SupplierProcurementDataRecoveryService:
    @classmethod
    def preview(
        cls, ledger_path, run_id, production_context=None,
        source_snapshot=None, expected_source_snapshot_sha=None,
    ):
        _assert_boundary(run_id, production_context)
        if production_context is None and source_snapshot is not None:
            source_snapshot = _validated_source_snapshot(
                source_snapshot, expected_source_snapshot_sha,
            )
        document = json.loads(Path(ledger_path).read_text(encoding="utf-8"))
        recover = _validate_ledger(
            document, run_id,
            production_context.source_snapshot if production_context is not None else source_snapshot,
        )
        decisions = {}
        for row in document["rows"]:
            key = f"{row['Source Type']}::{row['Target Business Object']}::{row['Target Action']}"
            decisions[key] = decisions.get(key, 0) + 1
        return {"runId": run_id, "ledgerRows": len(document["rows"]), "recoverRows": len(recover),
                "unclassified": 0, "decisions": decisions, "database": str(settings.DATABASES["default"]["NAME"])}

    @classmethod
    @transaction.atomic
    def execute(
        cls, ledger_path, run_id, actor, production_context=None,
        source_snapshot=None, expected_source_snapshot_sha=None,
    ):
        _assert_boundary(run_id, production_context)
        if production_context is None and source_snapshot is not None:
            source_snapshot = _validated_source_snapshot(
                source_snapshot, expected_source_snapshot_sha,
            )
        document = json.loads(Path(ledger_path).read_text(encoding="utf-8"))
        if production_context is None:
            recover = _validate_ledger(document, run_id, source_snapshot)
        else:
            recover, _, _ = _validate_frozen_selection(
                document, run_id, production_context.source_snapshot,
            )
        before = _baseline()
        counts = {"purchaseOrdersCreated": 0, "purchaseItemsCreated": 0,
                  "purchaseOrdersReplayed": 0, "purchaseItemsReplayed": 0}
        order_rows = [row for row in recover if row["Target Business Object"] == "PurchaseOrder"]
        item_rows = [row for row in recover if row["Target Business Object"] == "PurchaseOrderItem"]
        for row in order_rows:
            _, created = _recover_order(row, actor)
            counts["purchaseOrdersCreated" if created else "purchaseOrdersReplayed"] += 1
        for row in item_rows:
            _, created = _recover_item(row, actor)
            counts["purchaseItemsCreated" if created else "purchaseItemsReplayed"] += 1
        after = _baseline((before["existing"]["purchaseOrderIds"], before["existing"]["purchaseItemIds"]))
        preservation = {
            key: before["existing"][key] == after["existing"][key]
            for key in ("supplier", "material", "purchaseRequest", "purchaseRequestItem", "purchaseOrder", "purchaseItem")
        }
        downstream_preserved = before["downstream"] == after["downstream"]
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA foreign_key_check")
            orphan_count = len(cursor.fetchall())
            cursor.execute("SELECT COUNT(*) FROM (SELECT po_no FROM purchase_order WHERE po_no IS NOT NULL GROUP BY po_no HAVING COUNT(*)>1)")
            duplicate_po = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM (SELECT company_id, code FROM supplier GROUP BY company_id, code HAVING COUNT(*)>1)")
            duplicate_supplier = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM (SELECT company_id, code FROM material GROUP BY company_id, code HAVING COUNT(*)>1)")
            duplicate_material = cursor.fetchone()[0]
        if not all(preservation.values()) or not downstream_preserved:
            raise DataRecoveryError("EXISTING_OR_DOWNSTREAM_FACT_CHANGED")
        if orphan_count or duplicate_po or duplicate_supplier or duplicate_material:
            raise DataRecoveryError("RECOVERY_INTEGRITY_GATE_FAILED")
        return {
            "runId": run_id, "counts": counts, "before": before, "after": after,
            "preservation": preservation, "downstreamPreserved": downstream_preserved,
            "inventoryDoubleCount": 0 if downstream_preserved else None,
            "payableDoubleCount": 0 if downstream_preserved else None,
            "foreignKeyOrphans": orphan_count,
            "formalBusinessIdentityDuplicates": {
                "purchaseOrder": duplicate_po, "supplier": duplicate_supplier, "material": duplicate_material,
            },
            "idempotencyWriteRequests": MasterDataWriteRequest.objects.filter(
                action_code=ACTION_CODE, idempotency_key__startswith=f"{run_id}:"
            ).count(),
        }

    @classmethod
    def production_phase(
        cls, *, phase, target_kind, ledger_path, changeset_path, run_id,
        authorization_id, expected_database_sha, expected_ledger_sha,
        expected_changeset_sha, actor=None, backup_path=None,
        expected_backup_sha=None, quiescence_proof_path=None,
        expected_quiescence_proof_sha=None, dry_run_proof_path=None,
        expected_dry_run_proof_sha=None,
    ):
        context = _validate_production_gate(
            phase=phase, target_kind=target_kind, ledger_path=ledger_path,
            changeset_path=changeset_path, run_id=run_id,
            authorization_id=authorization_id,
            expected_database_sha=expected_database_sha,
            expected_ledger_sha=expected_ledger_sha,
            expected_changeset_sha=expected_changeset_sha,
            backup_path=backup_path, expected_backup_sha=expected_backup_sha,
            quiescence_proof_path=quiescence_proof_path,
            expected_quiescence_proof_sha=expected_quiescence_proof_sha,
            dry_run_proof_path=dry_run_proof_path,
            expected_dry_run_proof_sha=expected_dry_run_proof_sha,
        )
        if phase == "precheck":
            preview = cls.preview(ledger_path, run_id, production_context=context)
            return {
                "phase": phase, "status": "PASS", "runId": run_id,
                "authorizationId": authorization_id, "targetKind": target_kind,
                "database": str(context.database), "databaseSha256": context.database_sha256,
                "ledgerSha256": context.ledger_sha256,
                "changesetSha256": context.changeset_sha256,
                "recoverPurchaseOrders": FROZEN_PO_COUNT,
                "recoverPurchaseItems": FROZEN_ITEM_COUNT,
                "ledgerRows": preview["ledgerRows"], "productionWrites": 0,
            }
        if phase == "dry-run":
            return _production_preview(ledger_path, run_id, context)
        if actor is None:
            raise DataRecoveryError("ACTIVE_ACTOR_REQUIRED_FOR_PRODUCTION_COMMIT")
        result = cls.execute(
            ledger_path, run_id, actor, production_context=context,
        )
        result.update({
            "phase": phase, "status": "PASS",
            "authorizationId": authorization_id, "targetKind": target_kind,
            "database": str(context.database), "databaseSha256Before": context.database_sha256,
            "ledgerSha256": context.ledger_sha256,
            "changesetSha256": context.changeset_sha256,
            "backupSha256": context.backup_sha256,
            "quiescenceProofSha256": context.quiescence_proof_sha256,
            "dryRunProofSha256": context.dry_run_proof_sha256,
        })
        return result
