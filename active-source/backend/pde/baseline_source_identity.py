"""Read typed calculation identity from confirmed facts; never invent coordinates."""
from hashlib import sha256
import json

from .engineering_calculation_service import EngineeringCalculationError


def _hash(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), default=str).encode()).hexdigest()


def resolve_baseline_source_identity(item):
    snapshot = item.content_snapshot
    if not isinstance(snapshot, dict) or _hash(snapshot) != item.content_hash:
        raise EngineeringCalculationError("BASELINE_ITEM_CONTENT_HASH_MISMATCH", "基线对象快照内容校验失败。")
    design = snapshot.get("designItem") or {}
    source = snapshot.get("source") or {}
    revision = snapshot.get("revision") or {}
    if not all(isinstance(value, dict) for value in (design, source, revision)):
        raise EngineeringCalculationError("BASELINE_SOURCE_SNAPSHOT_INVALID", "基线来源或修订快照格式不完整。")
    existing = design.get("existingDesignData") or {}
    if not isinstance(existing, dict) or not isinstance(existing.get("provenance") or {}, dict):
        raise EngineeringCalculationError("BASELINE_SOURCE_SNAPSHOT_INVALID", "基线来源追溯格式不完整。")
    provenance = existing.get("provenance") or {}
    raw = source.get("rawValue") or {}
    native = isinstance(raw, dict) and raw.get("sourceType") == "USER_ENTRY"
    if isinstance(raw, dict) and str(source.get('externalSource') or '').startswith('PCE-SOURCE-ROW:'):
        baseline, obj, attribute, record = item.baseline, item.design_item, item.source_attribute, item.source_record
        line = obj.sales_order_item
        proof = raw.get('sourceProvenance') or {}
        expected = {'companyId': baseline.company_id, 'sourceRecordId': record.pk,
                    'sourceVersion': record.source_version, 'sourceRowId': raw.get('sourceRowId'),
                    'sourceContentHash': record.content_hash, 'salesOrderItemId': line.pk}
        stable = 'PCE-SOURCE-ROW:' + _hash({k:v for k,v in expected.items() if k != 'sourceContentHash'})
        if (not expected['sourceRowId'] or proof != expected or source['externalSource'] != stable
                or attribute.external_source != stable or attribute.canonical_field != stable
                or attribute.raw_value != raw or source.get('recordId') != record.pk
                or source.get('attributeId') != attribute.pk or design.get('id') != obj.pk
                or obj.company_id != baseline.company_id or record.company_id != baseline.company_id
                or line.sales_order.company_id != baseline.company_id or line.sales_order_id != baseline.sales_order_id
                or attribute.sales_order_item_id != line.pk or obj.source_record_id != record.pk
                or obj.source_attribute_id != attribute.pk or source.get('sourceVersion') != record.source_version
                or item.source_version_snapshot != record.source_version
                or source.get('sourceContentHash') != record.content_hash or item.source_content_hash_snapshot != record.content_hash
                or not item.design_revision_id or revision.get('id') != item.design_revision_id
                or item.design_revision.design_item_id != obj.pk or revision.get('revision') != item.design_revision_no):
            raise EngineeringCalculationError('BASELINE_SOURCE_ROW_MISMATCH', '来源行、公司、订单或精确冻结修订不一致。')
        from .product_version_management_service import _content_snapshot
        if _hash(_content_snapshot(obj,item.design_revision)['revision']) != _hash(revision):
            raise EngineeringCalculationError('BASELINE_NATIVE_REVISION_CONTENT_MISMATCH','精确修订内容与冻结事实不一致。')
        identity = {'type':'PCE_SOURCE_ROW_REVISION','companyId':baseline.company_id,'salesOrderId':line.sales_order_id,
                    'salesOrderItemId':line.pk,'sourceRecordId':record.pk,'sourceVersion':record.source_version,
                    'sourceRowId':raw['sourceRowId'],'sourceAttributeId':attribute.pk,'designItemId':obj.pk,
                    'designRevisionId':item.design_revision_id,'designRevision':item.design_revision_no}
        return {**identity,'sourceKey':stable+':revision:'+str(item.design_revision_id),'sourceSheet':None,'sourceRow':None}
    if not native:
        # Keep the existing import locator contract; a design revision does not
        # relabel its original Excel material as native input.
        if provenance.get("sourceType") == "USER_ENTRY":
            raise EngineeringCalculationError("BASELINE_NATIVE_SOURCE_MISMATCH", "原生来源登记与冻结追溯类型不一致。")
        sheet = str(provenance.get("sourceSheet") or source.get("rawSheet") or "")
        row = provenance.get("sourceRow")
        if not sheet or row in (None, ""):
            raise EngineeringCalculationError("BASELINE_STABLE_SOURCE_IDENTITY_REQUIRED", "导入来源缺少真实工作表或来源行身份。",
                                              {"baselineItemId": item.pk, "designItemId": item.design_item_id})
        return {"type": "EXCEL_SOURCE_ROW", "sourceKey": f"{sheet}:{row}",
                "sourceSheet": sheet, "sourceRow": row}

    baseline, obj, attribute, record = item.baseline, item.design_item, item.source_attribute, item.source_record
    line = obj.sales_order_item
    if (obj.company_id != baseline.company_id or line.sales_order.company_id != baseline.company_id
            or line.sales_order_id != baseline.sales_order_id or record.company_id != baseline.company_id
            or attribute.sales_order_item_id != line.pk or obj.source_record_id != record.pk
            or obj.source_attribute_id != attribute.pk or design.get("id") != obj.pk
            or source.get("recordId") != record.pk or source.get("attributeId") != attribute.pk):
        raise EngineeringCalculationError("BASELINE_NATIVE_SOURCE_SCOPE_MISMATCH", "原生来源、设计对象和工程基线不属于同一公司与订单行。")
    if (not source.get("externalSource") or source["externalSource"] != attribute.external_source
            or provenance.get("sourceType") != "USER_ENTRY"
            or provenance.get("sourceObject") != source["externalSource"]
            or _hash(raw) != _hash(attribute.raw_value)
            or source.get("sourceVersion") != item.source_version_snapshot
            or source.get("sourceContentHash") != item.source_content_hash_snapshot):
        raise EngineeringCalculationError("BASELINE_NATIVE_SOURCE_MISMATCH", "原生来源登记、版本或内容与冻结事实不一致。")
    if not item.design_revision_id or not revision.get("id"):
        raise EngineeringCalculationError("BASELINE_NATIVE_REVISION_REQUIRED", "原生设计核算需要基线冻结的精确设计修订。")
    saved_revision = item.design_revision
    if (saved_revision.design_item_id != obj.pk or revision["id"] != saved_revision.pk
            or item.design_revision_id != saved_revision.pk
            or revision.get("revision") != saved_revision.revision
            or item.design_revision_no != saved_revision.revision):
        raise EngineeringCalculationError("BASELINE_NATIVE_REVISION_MISMATCH", "冻结修订引用与设计对象不一致。")
    # Reuse the authoritative baseline serializer for the immutable revision;
    # current design version/newer revisions cannot replace this pinned revision.
    from .product_version_management_service import _content_snapshot
    if _hash(_content_snapshot(obj, saved_revision)["revision"]) != _hash(revision):
        raise EngineeringCalculationError("BASELINE_NATIVE_REVISION_CONTENT_MISMATCH", "冻结设计修订内容与精确修订记录不一致。")
    identity = {"type": "NATIVE_DESIGN_REVISION", "companyId": baseline.company_id,
                "salesOrderId": baseline.sales_order_id, "salesOrderItemId": line.pk,
                "sourceRecordId": record.pk, "sourceAttributeId": attribute.pk,
                "registeredSourceObject": source["externalSource"],
                "designItemId": obj.pk, "designRevisionId": saved_revision.pk,
                "designRevision": saved_revision.revision}
    # The key contains typed, scoped references, not a content digest. Content
    # hashes above are independent consistency checks, not identity substitutes.
    key = "pce:native-design-revision:" + ":".join(str(identity[field]) for field in (
        "companyId", "salesOrderId", "salesOrderItemId", "sourceRecordId",
        "sourceAttributeId", "designItemId", "designRevisionId", "designRevision"))
    return {**identity, "sourceKey": key, "sourceSheet": None, "sourceRow": None,
            "baselineId": baseline.pk, "baselineItemId": item.pk,
            "contentHash": item.content_hash}
