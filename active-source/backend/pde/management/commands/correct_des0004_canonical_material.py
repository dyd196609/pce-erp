import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from masterdata.models import MasterDataWriteRequest, Material
from pde.acceptance_isolation import verify_acceptance_connections
from pde.models import ProductDesignItem
from pde.product_design_service import ACTION_DESIGN_SAVE, save_design_content
from system.models import OrganizationOperatingAuditRecord, User


ORDER_NO = "SO202609180003"
ITEM_NO = "SO202609180003-DES-01-SRC-0004"
SOURCE_MATERIAL_ID = 111
CANONICAL_MATERIAL_ID = 130
IDEMPOTENCY_KEY = "SO202609180003:DES0004:MATERIAL-111-TO-130:V1"
REASON = (
    "用户确认门板正式用料为“清水封闭实木多层板”；DES-01-SRC-0004当前引用"
    "“清水开放实木多层板”与真实业务材料事实不一致。LC-M045属于色板编号，“清水封闭”"
    "属于表面工艺，二者均不作为板材Master身份推导依据。本次仅纠正门扇板材Material引用，"
    "不修改颜色、色板或油漆工艺事实。"
)


def _revision_snapshot(revision):
    if revision is None:
        return None
    return {
        "id": revision.pk,
        "revision": revision.revision,
        "designNature": revision.design_nature,
        "designLength": str(revision.design_length) if revision.design_length is not None else None,
        "designWidth": str(revision.design_width) if revision.design_width is not None else None,
        "designThickness": str(revision.design_thickness) if revision.design_thickness is not None else None,
        "designUomId": revision.design_uom_id,
        "materialId": revision.material_id,
        "materialProcessTypeId": revision.material_process_type_id,
        "paintProcessTypeId": revision.paint_process_type_id,
        "edgeMethodId": revision.edge_method_id,
        "designData": revision.design_data,
        "sourceProvenance": revision.source_provenance,
        "masterMatchResults": revision.master_match_results,
        "legacySourceRecordId": revision.legacy_source_record_id,
        "changeReason": revision.change_reason,
        "createdById": revision.created_by_id,
    }


def _item():
    row = ProductDesignItem.objects.select_related(
        "sales_order_item__sales_order",
    ).filter(
        item_no=ITEM_NO,
        sales_order_item__sales_order__order_no=ORDER_NO,
    ).first()
    if row is None:
        raise CommandError(f"Formal design item not found: {ITEM_NO}")
    return row


def _readback(item):
    revisions = list(item.design_revisions.select_related("material").order_by("revision"))
    latest = revisions[-1] if revisions else None
    ledger = MasterDataWriteRequest.objects.filter(
        organization_id=item.company_id,
        action_code=ACTION_DESIGN_SAVE,
        idempotency_key=IDEMPOTENCY_KEY,
    ).first()
    audit_id = (ledger.result or {}).get("auditId") if ledger else None
    audit = OrganizationOperatingAuditRecord.objects.filter(pk=audit_id).first()
    prior = revisions[-2] if len(revisions) >= 2 else None
    return {
        "database": str(Path(settings.DATABASES["default"]["NAME"]).resolve()),
        "orderNo": ORDER_NO,
        "designItemId": item.pk,
        "designItemNo": item.item_no,
        "itemVersion": item.version,
        "revisionCount": len(revisions),
        "revisionNumbers": [row.revision for row in revisions],
        "historicalRevisionMaterialIds": [
            {"revision": row.revision, "materialId": row.material_id}
            for row in revisions[:-1]
        ],
        "priorRevision": _revision_snapshot(prior),
        "latestRevision": _revision_snapshot(latest),
        "ledger": {
            "id": ledger.pk if ledger else None,
            "status": ledger.status if ledger else None,
            "targetEntityId": ledger.target_entity_id if ledger else None,
            "result": ledger.result if ledger else None,
        },
        "audit": {
            "id": audit.pk if audit else None,
            "actionCode": audit.action_code if audit else None,
            "actorId": audit.actor_id if audit else None,
            "reason": audit.reason if audit else None,
            "before": audit.before_snapshot if audit else None,
            "after": audit.after_snapshot if audit else None,
        },
    }


class Command(BaseCommand):
    help = "Correct DES-01-SRC-0004 from Material 111 to canonical Material 130."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--readback", action="store_true")

    def handle(self, *args, **options):
        try:
            verify_acceptance_connections(settings.DATABASES)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        item = _item()
        source = Material.objects.filter(pk=SOURCE_MATERIAL_ID).first()
        canonical = Material.objects.filter(pk=CANONICAL_MATERIAL_ID, is_active=True).first()
        if source is None or canonical is None:
            raise CommandError("The fixed source/canonical Material identity is unavailable.")

        if options["readback"]:
            result = _readback(item)
            latest = result["latestRevision"] or {}
            ledger = result["ledger"]
            if latest.get("materialId") != CANONICAL_MATERIAL_ID:
                raise CommandError("Readback failed: latest revision is not canonical Material 130.")
            if ledger.get("status") != MasterDataWriteRequest.Status.COMMITTED:
                raise CommandError("Readback failed: committed idempotency ledger is missing.")
            self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            return

        latest = item.design_revisions.order_by("-revision").first()
        preview = {
            "database": str(Path(settings.DATABASES["default"]["NAME"]).resolve()),
            "mode": "APPLY" if options["apply"] else "PREVIEW_ONLY",
            "actor": options["actor"],
            "orderNo": ORDER_NO,
            "designItemId": item.pk,
            "designItemNo": item.item_no,
            "itemVersion": item.version,
            "latestRevision": _revision_snapshot(latest),
            "correction": {
                "fromMaterialId": SOURCE_MATERIAL_ID,
                "toMaterialId": CANONICAL_MATERIAL_ID,
                "toMaterialCode": canonical.code,
                "toMaterialName": canonical.name,
                "reason": REASON,
                "idempotencyKey": IDEMPOTENCY_KEY,
            },
        }
        if not options["apply"]:
            self.stdout.write(json.dumps(preview, ensure_ascii=False, indent=2, default=str))
            return

        user = User.objects.filter(username=options["actor"], is_active=True).first()
        if user is None:
            raise CommandError("The requested active actor does not exist.")
        if user.company_id != item.company_id:
            raise CommandError("The requested actor is outside the design item's organization.")
        if latest is None or latest.material_id not in {SOURCE_MATERIAL_ID, CANONICAL_MATERIAL_ID}:
            raise CommandError("Latest formal design revision is outside the authorized correction state.")

        _, replayed = save_design_content(
            user=user,
            payload={
                "designItemId": item.pk,
                "expectedVersions": {str(item.pk): item.version},
                "designData": {"materialId": CANONICAL_MATERIAL_ID},
                "designNature": "FORMAL",
                "reason": REASON,
            },
            idempotency_key=IDEMPOTENCY_KEY,
        )
        item.refresh_from_db()
        result = _readback(item)
        result.update({"mode": "APPLY", "replayed": replayed})
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
