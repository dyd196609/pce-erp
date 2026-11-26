"""Explicit, source-backed first preparation; no historical completion inference."""
from django.db import transaction, OperationalError, IntegrityError
from time import sleep
from sales.models import SalesOrderItemEngineeringAttribute
from .models import OrderEngineeringInstance, EngineeringSourceRecord, ProductDesignItem
from .admission_chain_revocation import active_order_engineering_instances
from .pde_engineering_preparation_admission import require_pde_engineering_preparation_admission, PDEEngineeringPreparationAdmissionError

FIELDS = ("companyId", "orderEngineeringInstanceId", "salesOrderId", "salesOrderItemId", "sourceRecordId", "sourceVersion", "authorizationId")

def resolve(user, context, lock=False):
    from .product_design_service import ProductDesignError
    if any(context.get(k) in (None, "") for k in FIELDS):
        raise ProductDesignError("DESIGN_CONTEXT_REQUIRED", "请从工程实例进入，完整提供公司、订单、订单行、来源版本及授权。", 409)
    try:
        for key in FIELDS:
            if key != "sourceVersion":
                int(context[key])
    except (ValueError, TypeError) as exc:
        raise ProductDesignError("DESIGN_CONTEXT_INVALID", "工程上下文标识格式无效，请从工程实例重新进入。", 409) from exc
    q = OrderEngineeringInstance.objects.select_related("sales_order_item__sales_order", "source_record")
    if lock:
        q = q.select_for_update()
    instance = active_order_engineering_instances(q).filter(pk=context["orderEngineeringInstanceId"], company_id=user.company_id).first()
    if not instance:
        raise ProductDesignError("DESIGN_INSTANCE_NOT_FOUND", "工程实例不存在或不属于当前公司。", 404)
    item = instance.sales_order_item
    source = EngineeringSourceRecord.objects.select_for_update().get(pk=instance.source_record_id) if lock else instance.source_record
    actual = (user.company_id, instance.pk, item.sales_order_id, item.pk, source.pk, source.source_version, instance.engineering_preparation_authorization_id)
    if any(str(context[k]) != str(v) for k,v in zip(FIELDS, actual)) or source.company_id != user.company_id:
        raise ProductDesignError("DESIGN_CONTEXT_MISMATCH", "工程实例、公司、订单行、来源版本或授权绑定不一致。", 409)
    try:
        require_pde_engineering_preparation_admission(company_id=user.company_id, sales_order_item_id=item.pk, authorization_id=context["authorizationId"], lock=lock)
    except PDEEngineeringPreparationAdmissionError as e:
        raise ProductDesignError(e.code, e.message, e.http_status, e.details) from e
    from .order_engineering_intake_service import _authorization
    authorization = _authorization(context["authorizationId"])
    if authorization.predecessor_relation.pde_review.source_record_id != source.pk:
        raise ProductDesignError("DESIGN_AUTHORIZATION_SOURCE_MISMATCH", "授权覆盖来源与工程实例来源不一致。", 409)
    if source.status != "confirmed":
        raise ProductDesignError("DESIGN_SOURCE_INVALID", "工程来源尚未确认或已经失效。", 409)
    return instance, item, source

@transaction.atomic
def _prepare_atomic(user, context, key):
    from .product_design_service import ProductDesignError, _authorize, ACTION_INITIALIZE, _canonical_hash, _write_request, _commit_request, _audit_batch
    _authorize(user, ACTION_INITIALIZE)
    instance, line, source = resolve(user, context, lock=True)
    rows = (source.source_payload or {}).get("engineeringRows")
    if not isinstance(rows, list) or not rows:
        raise ProductDesignError("DESIGN_SOURCE_ROWS_REQUIRED", "来源缺少可追溯工程行，不能首次准备。", 409)
    # A multi-line source must identify the target line explicitly; never guess.
    if line.sales_order.items.count() > 1:
        if any(not r.get("salesOrderItemId") for r in rows):
            raise ProductDesignError("DESIGN_SOURCE_LINE_AMBIGUOUS", "多订单行来源未明确标注所属订单行，请先核定来源关联。", 409)
        rows = [r for r in rows if str(r["salesOrderItemId"]) == str(line.pk)]
    ids = [str(r.get("sourceRowId") or "").strip() for r in rows]
    if not ids or any(not x for x in ids) or len(set(ids)) != len(ids):
        raise ProductDesignError("DESIGN_SOURCE_ID_INVALID", "来源行标识缺失或重复，不能首次准备。", 409)
    request, created, _ = _write_request(user=user, action_code=ACTION_INITIALIZE, entity_type="ProductDesignItemBatch", key=key, request_body=dict(context))
    before = ProductDesignItem.objects.filter(sales_order_item=line).count()
    for sequence, (row, row_id) in enumerate(zip(rows, ids), 1):
        provenance = {"companyId": user.company_id, "sourceRecordId": source.pk, "sourceVersion": source.source_version, "sourceRowId": row_id, "sourceContentHash": source.content_hash, "salesOrderItemId": line.pk}
        stable = "PCE-SOURCE-ROW:" + _canonical_hash({k:v for k,v in provenance.items() if k != "sourceContentHash"})
        raw = {**row, "sourceProvenance": provenance}
        attr, made = SalesOrderItemEngineeringAttribute.objects.get_or_create(sales_order_item=line, canonical_field=stable, sequence=1, defaults={"raw_source": source.source_no, "external_source": stable, "raw_field": "engineeringRows", "raw_value": raw, "normalized_value": raw, "value_type": "json", "source_type": "ENGINEERING_INPUT", "created_by": user})
        if attr.raw_value != raw or attr.external_source != stable:
            raise ProductDesignError("DESIGN_SOURCE_BINDING_CONFLICT", "已有稳定来源行内容或绑定不一致，禁止覆盖。", 409)
        obj, made = ProductDesignItem.objects.get_or_create(source_attribute=attr, defaults={"company_id":user.company_id, "sales_order_item":line, "source_record":source, "source_version":source.source_version, "source_content_hash":source.content_hash, "item_no":f"{line.sales_order.order_no}-DES-{line.line_no:02d}-SRC-{attr.pk:04d}", "item_name":str(row.get("component") or row.get("product") or row_id), "original_requirement":raw, "existing_design_data":{}, "design_data_nature":"SIMULATED_FOR_TEST", "physical_quantity":row.get("quantity") or None, "physical_uom_snapshot":str(row.get("unit") or ""), "product_category_id":instance.product_category_id})
        if obj.company_id != user.company_id or obj.sales_order_item_id != line.pk or obj.source_record_id != source.pk or obj.source_version != source.source_version or obj.source_content_hash != source.content_hash:
            raise ProductDesignError("DESIGN_ITEM_BINDING_CONFLICT", "已有设计项归属或来源版本不一致，禁止重新初始化。", 409)
    items=list(ProductDesignItem.objects.filter(sales_order_item=line, source_record=source))
    if created:
        audit=_audit_batch(user, ACTION_INITIALIZE, items, "按真实来源行首次准备测试设计项；不登记设计完成。", {"count":before}, {"count":len(items), "context":dict(context)})
        _commit_request(request, {"targetId":line.pk,"auditId":audit.pk})
    from .product_design_service import product_design_facts
    return product_design_facts(user.company_id,user=user,order_no=line.sales_order.order_no,instance_context=context), not created


def prepare(user, context, key):
    """Retry the complete transaction, never a failed statement in a broken transaction."""
    from .product_design_service import ProductDesignError
    for attempt in range(5):
        try:
            return _prepare_atomic(user, context, key)
        except OperationalError as exc:
            if "locked" not in str(exc).lower() and "deadlock" not in str(exc).lower():
                raise
            if attempt == 4:
                raise ProductDesignError("DESIGN_PREPARATION_BUSY", "本单首次准备正在处理中，请稍后刷新核对后重试。", 409) from exc
        except IntegrityError as exc:
            if attempt == 4:
                raise ProductDesignError("DESIGN_PREPARATION_CONFLICT", "来源关联存在并发冲突，请刷新核对后重试。", 409) from exc
        sleep(0.1 * (attempt + 1))
