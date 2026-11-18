"""Explicit source-row membership using the original identity/audit ledger.

Frozen sources and approved order scope are never edited. No matching by
material, position or quantity is performed. Quantities only validate a
responsible actor's explicit selection against the existing formal scope.
"""
import hashlib
import json
from collections import defaultdict
from decimal import Decimal
from django.db import transaction
from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from sales.models import SalesOrderItem
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord
from .models import OrderReviewSalesOrderRelation
from .order_engineering_intake_service import ACTION_CODE
from .product_design_service import ProductDesignError

SYSTEM = 'PDE_SOURCE_ROW_BINDING'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def fail(code, message, status=409):
    raise ProductDesignError(code, message, status)


def source_rows(source):
    rows=(source.source_payload or {}).get('engineeringRows')
    if not isinstance(rows,list) or not rows or any(not isinstance(r,dict) or not str(r.get('sourceRowId') or '').strip() for r in rows):
        fail('DESIGN_SOURCE_ID_INVALID','来源缺少明确、稳定的明细身份。')
    keys=[str(r['sourceRowId']) for r in rows]
    if len(set(keys))!=len(keys):fail('DESIGN_SOURCE_ID_INVALID','来源明细身份重复，须先正式核定。')
    return {str(r['sourceRowId']):r for r in rows}


def identity_key(source, key):
    return dict(organization_id=source.company_id,source_system=SYSTEM,
        source_type='FORMAL_SOURCE_ROW',source_object_type='EngineeringSourceRow',
        external_id=f'{source.pk}:{source.source_version}:{key}')


def approved_scope(source, instance):
    from .pde_engineering_preparation_admission import require_pde_engineering_preparation_admission
    admission=require_pde_engineering_preparation_admission(company_id=source.company_id,
        sales_order_item_id=instance.sales_order_item_id,
        authorization_id=instance.engineering_preparation_authorization_id)
    relation=OrderReviewSalesOrderRelation.objects.get(pk=admission.crm_order_relation_id)
    if relation.review.source_record_id!=source.pk or relation.source_content_hash_snapshot!=source.content_hash:
        fail('DESIGN_SOURCE_BINDING_SCOPE_INVALID','来源与当前批准范围不一致。')
    scope=list(relation.scope_items.select_related('sales_order_item__material','sales_order_item__uom'))
    keys=set(source_rows(source))
    if relation.scope_mode=='SELECTED_ITEMS':keys &= {s.external_line_no_snapshot for s in scope}
    if not keys:fail('DESIGN_SOURCE_BINDING_SCOPE_INVALID','当前批准范围没有可核定来源行。')
    return relation,scope,keys


def existing_mapping(source, instance):
    relation,scope,keys=approved_scope(source,instance);rows=source_rows(source)
    lines={s.sales_order_item_id:s.sales_order_item for s in scope};mapping={};authorities={}
    def accept(key,item_id,authority):
        if key not in keys:return
        if item_id not in lines:fail('DESIGN_SOURCE_BINDING_SCOPE_INVALID','已有来源关联超出当前批准订单行范围。')
        if key in mapping and mapping[key]!=item_id:fail('DESIGN_SOURCE_BINDING_CONFLICT','已有权威来源关联互相冲突，禁止覆盖。')
        mapping[key]=item_id;authorities[key]=authority
    # Reuse original explicit frozen membership and the approved external
    # source keys; never manufacture these keys for an old order.
    for key,row in rows.items():
        if row.get('salesOrderItemId'):
            try:accept(key,int(row['salesOrderItemId']),'FROZEN_SOURCE')
            except (ValueError,TypeError):fail('DESIGN_SOURCE_BINDING_SCOPE_INVALID','原来源订单行标识无效。')
    for s in scope:
        key=s.external_line_no_snapshot
        if key in keys:
            if sum(x.external_line_no_snapshot==key for x in scope)!=1:
                fail('DESIGN_SOURCE_LINE_AMBIGUOUS','批准外部行身份不唯一，不能推定对应关系。')
            accept(key,s.sales_order_item_id,'APPROVED_EXTERNAL_LINE')
    from .models import ProductDesignItem
    from .product_design_service import _canonical_hash
    unproved_existing_design=False
    for design in ProductDesignItem.objects.filter(company_id=source.company_id,source_record=source).select_related('source_attribute'):
        attribute=design.source_attribute;raw=attribute.raw_value
        if not isinstance(raw,dict) or not attribute.external_source.startswith('PCE-SOURCE-ROW:'):
            unproved_existing_design=True;continue
        proof=raw.get('sourceProvenance') or {};row_key=str(raw.get('sourceRowId') or '')
        if row_key not in keys:continue
        expected={'companyId':source.company_id,'sourceRecordId':source.pk,'sourceVersion':source.source_version,
            'sourceRowId':rows[row_key]['sourceRowId'],'sourceContentHash':source.content_hash,'salesOrderItemId':design.sales_order_item_id}
        stable='PCE-SOURCE-ROW:'+_canonical_hash({k:v for k,v in expected.items() if k!='sourceContentHash'})
        bare={k:v for k,v in raw.items() if k!='sourceProvenance'}
        if (proof!=expected or attribute.external_source!=stable or attribute.canonical_field!=stable
            or attribute.sales_order_item_id!=design.sales_order_item_id or design.original_requirement!=raw
            or design.source_version!=source.source_version or design.source_content_hash!=source.content_hash
            or bare not in (rows[row_key],{**rows[row_key],'salesOrderItemId':design.sales_order_item_id})):
            fail('DESIGN_SOURCE_BINDING_EXISTING_PROOF_INVALID','已有来源设计关联证明不一致，禁止重新猜配。')
        accept(row_key,design.sales_order_item_id,'NATIVE_SOURCE_DESIGN_PROVENANCE')
    for key in keys:
        identity=ExternalIdentity.objects.filter(**identity_key(source,key)).first()
        if not identity:continue
        proof=identity.audit_metadata;payload=proof.get('binding',{})
        try:item_id=int(identity.target_entity_id)
        except (ValueError,TypeError):fail('DESIGN_SOURCE_BINDING_INVALID','登记关联目标无效。')
        if (identity.mapping_status!='MATCH' or identity.target_entity_type!='SalesOrderItem'
            or identity.source_fingerprint!=source.content_hash or payload.get('companyId')!=source.company_id
            or payload.get('sourceRecordId')!=source.pk or payload.get('sourceVersion')!=source.source_version
            or payload.get('sourceContentHash')!=source.content_hash or payload.get('sourceRowId')!=key
            or payload.get('salesOrderId')!=relation.sales_order_id or payload.get('salesOrderItemId')!=item_id
            or payload.get('relationId')!=relation.pk or proof.get('bindingHash')!=digest(payload)):
            fail('DESIGN_SOURCE_BINDING_INVALID','来源关联内容、版本或目标核验失败。')
        audit=OrganizationOperatingAuditRecord.objects.filter(pk=proof.get('auditId'),organization_id=source.company_id,
            target_type='ExternalIdentity',target_id=identity.pk,action_code=ACTION_CODE,actor_id=proof.get('actorId')).first()
        if not audit or not audit.after_snapshot.get('authorization',{}).get('allowed') or audit.after_snapshot.get('state')!=payload:
            fail('DESIGN_SOURCE_BINDING_AUDIT_REQUIRED','来源关联缺少一致的原生权限和登记审计。')
        accept(key,item_id,'FORMAL_ROW_REGISTRATION')
    if unproved_existing_design and set(mapping)!=keys:
        fail('DESIGN_SOURCE_BINDING_EXISTING_PROOF_REQUIRED','已有后序设计引用但缺少可证明的逐行关系，须先正式核定历史来源，不能直接新绑。')
    return relation,scope,keys,mapping,authorities


def rows_for_line(source, line, instance):
    relation,scope,keys,mapping,authorities=existing_mapping(source,instance)
    if any(key not in mapping for key in keys):
        fail('DESIGN_SOURCE_LINE_AMBIGUOUS','多订单行来源尚未逐行正式关联，请由工程接入责任人核定。')
    rows=source_rows(source)
    selected=[{**rows[key],'salesOrderItemId':line.pk} for key in rows if key in keys and mapping[key]==line.pk]
    if not selected:fail('DESIGN_SOURCE_ROWS_REQUIRED','当前订单行没有已核定来源明细。')
    return selected


def binding_facts(source, instance):
    from .models import ProductDesignItem
    relation,scope,keys,mapping,authorities=existing_mapping(source,instance)
    rows=[]
    for key in sorted(keys):
        identity=ExternalIdentity.objects.filter(**identity_key(source,key)).first()
        design=ProductDesignItem.objects.select_related('source_attribute').filter(company_id=source.company_id,
            source_record=source,sales_order_item_id=mapping.get(key),
            source_attribute__raw_value__sourceRowId=source_rows(source)[key]['sourceRowId']).first() if key in mapping else None
        rows.append({'sourceRowId':key,'salesOrderItemId':mapping.get(key),
            'authority':authorities.get(key),'status':'BOUND' if key in mapping else 'PENDING',
            'sourceIdentityId':identity.pk if identity else None,
            'auditId':identity.audit_metadata.get('auditId') if identity else None,
            'registeredById':identity.audit_metadata.get('actorId') if identity else None,
            'registeredAt':identity.first_seen.isoformat() if identity else None,
            'sourceDesignItemId':design.pk if design else None,
            'sourceAttributeId':design.source_attribute_id if design else None,
            'reason':identity.audit_metadata.get('binding',{}).get('reason') if identity else None})
    facts={'contractVersion':'PCE-SOURCE-ROW-LINE-BINDING-V1','factSource':'server',
        'companyId':source.company_id,'salesOrderId':relation.sales_order_id,
        'sourceRecordId':source.pk,'sourceVersion':source.source_version,'sourceContentHash':source.content_hash,
        'status':'BOUND' if set(mapping)==keys else 'PENDING','rows':rows,'businessWriteCount':0}
    from workflow_runtime.fact_loads import build_fact_load_facts
    facts.update(build_fact_load_facts(fact_load_status='loaded',api_url='/api/pde/engineering-readiness/order-engineering-intake/',
        http_status=200,error_code='',error_message='',tenant_id=str(source.company_id),
        batch_id=f'Source:{source.pk}:v{source.source_version}:Order:{relation.sales_order_id}'))
    return facts


def read_for_item(*,user,sales_order_item_id):
    from .order_lifecycle_source_projection import terminal_closure_read
    from .order_engineering_intake_service import _item_queryset
    from .admission_chain_revocation import active_order_engineering_instances
    from .models import OrderEngineeringInstance
    item=_item_queryset().filter(pk=sales_order_item_id,sales_order__company_id=user.company_id).first()
    if not item:fail('SALES_ORDER_ITEM_NOT_FOUND','订单行不存在或不属于当前公司。',404)
    decision=AuthorizationService.decide(user=user,action_code=ACTION_CODE,organization_id=user.company_id,
        business_object={'organizationId':user.company_id,'salesOrderId':item.sales_order_id,'salesOrderItemId':item.pk})
    if not decision.get('allowed'):fail('PERMISSION_DENIED','当前身份无工程接入读取权限。',403)
    instances=OrderEngineeringInstance.objects.select_related('source_record')
    if item.sales_order.status=='closed':
        # Closed orders have no active execution instance. Historical reads
        # still require its original unrevoked instance and exact proof; the
        # execution query/helper and all registration guards stay unchanged.
        instances=instances.filter(admission_chain_revocation__isnull=True).exclude(status='inactive')
    else:
        instances=active_order_engineering_instances(instances)
    instance=instances.filter(sales_order_item=item).first()
    if not instance:fail('DESIGN_INSTANCE_NOT_FOUND','当前订单行尚无有效工程接入实例。',409)
    # Scoped, read-only original-source verification permits historical trace
    # after actual order completion, never another engineering write.
    def read_bound_rows(source, line):
        return binding_facts(source,instance)
    try:
        return terminal_closure_read(read_bound_rows)(instance.source_record,item)
    except ValueError as exc:
        from .crm_order_version_carry_forward import CarryForwardError
        if isinstance(exc,CarryForwardError):fail('DESIGN_SOURCE_BINDING_SCOPE_INVALID','终态来源追溯缺少可核定的原批准证明。')
        raise


@transaction.atomic
def register(*,user,context,bindings,idempotency_key,reason):
    from .product_design_instance_service import resolve
    from .production_foundation_service import _actor_chain,_audit
    from .crm_sales_order_identity import formal_order_source_scope,normalize_business_text
    instance,line,source=resolve(user,context,lock=True)
    if context.get('sourceContentHash')!=source.content_hash:
        fail('DESIGN_SOURCE_BINDING_SOURCE_CHANGED','来源内容证明已变化，请重新核对本次登记依据。')
    # Serialize all registrations on this approved order and source.
    list(SalesOrderItem.objects.select_for_update().filter(sales_order_id=line.sales_order_id))
    decision=AuthorizationService.decide(user=user,action_code=ACTION_CODE,organization_id=source.company_id,
        business_object={'organizationId':source.company_id,'salesOrderId':line.sales_order_id,'salesOrderItemId':line.pk})
    if not decision.get('allowed'):fail('PERMISSION_DENIED','当前身份无工程接入维护权限。',403)
    chain=_actor_chain(user)
    key=str(idempotency_key or '').strip();reason=str(reason or '').strip()
    if not key or len(key)>160 or not reason or len(reason)>300:
        fail('DESIGN_SOURCE_BINDING_INTENT_REQUIRED','逐行登记必须提供有效幂等键和明确依据。',400)
    relation,scope,allowed,mapping,authorities=existing_mapping(source,instance)
    rows=source_rows(source);lines={s.sales_order_item_id:s.sales_order_item for s in scope}
    try:
        pairs=[(str(b['sourceRowId']),int(b['salesOrderItemId'])) for b in bindings]
    except (KeyError,TypeError,ValueError):fail('DESIGN_SOURCE_BINDING_INPUT_INVALID','请明确选择来源明细与订单行。',400)
    if not pairs or len(pairs)>200 or len({k for k,_ in pairs})!=len(pairs) or {k for k,_ in pairs}!=allowed:
        fail('DESIGN_SOURCE_BINDING_SCOPE_INVALID','登记须完整且唯一覆盖当前批准来源范围。')
    proposal=dict(pairs)
    if any(v not in lines for v in proposal.values()):fail('DESIGN_SOURCE_BINDING_SCOPE_INVALID','所选订单行不属于当前批准范围。')
    if any(proposal[k]!=v for k,v in mapping.items()):
        fail('DESIGN_SOURCE_BINDING_CONFLICT','已有正式关联不得直接改指向；请走正式更正或版本机制。')
    formal=formal_order_source_scope(source)
    formal_rows={str(r.get('key') or r.get('sourceKey')):r for r in (formal or {}).get('items',[])}
    totals=defaultdict(Decimal)
    for row_key,item_id in pairs:
        entry=formal_rows.get(row_key);item=lines[item_id]
        if not entry:fail('DESIGN_SOURCE_BINDING_SCOPE_INVALID','来源明细未在正式批准范围中登记。')
        quantity=Decimal(str(entry['quantity']))
        material=entry.get('materialId');unit=entry.get('uomId')
        if ((material is not None and int(material)!=item.material_id)
            or (unit is not None and int(unit)!=item.uom_id)
            or normalize_business_text(entry.get('materialName') or entry.get('productName') or entry.get('customerProductName') or '')!=normalize_business_text(item.material.name)
            or str(entry.get('unit') or entry.get('uomCode') or '') not in (item.uom.code,item.uom.name)
            or quantity<=0):fail('DESIGN_SOURCE_BINDING_QUANTITY_INVALID','所选关联与原正式范围物料、单位或数量不符。')
        totals[item_id]+=quantity
    if set(totals)!=set(lines) or any(totals[i]!=lines[i].quantity for i in totals):
        fail('DESIGN_SOURCE_BINDING_QUANTITY_INVALID','逐行关联不符合原批准数量范围；不新增拆分或合并规则。')
    body={'context':dict(context),'bindings':sorted(pairs),'reason':reason};request_hash=digest(body)
    previous=MasterDataWriteRequest.objects.filter(organization_id=source.company_id,action_code=ACTION_CODE,idempotency_key=key).first()
    if previous:
        if previous.entity_type!=SYSTEM or previous.request_hash!=request_hash or previous.status!='COMMITTED':
            fail('IDEMPOTENCY_PAYLOAD_CONFLICT','同一幂等键不能提交其他关联或依据。')
        return {**previous.result,'idempotent':True,'businessWriteCount':0}
    identities=[];created=0
    for row_key,item_id in sorted(pairs):
        if row_key in mapping:continue
        payload={'companyId':source.company_id,'salesOrderId':line.sales_order_id,'salesOrderItemId':item_id,
            'sourceRecordId':source.pk,'sourceVersion':source.source_version,'sourceContentHash':source.content_hash,
            'sourceRowId':row_key,'relationId':relation.pk,'reason':reason}
        identity=ExternalIdentity.objects.create(**identity_key(source,row_key),target_entity_type='SalesOrderItem',
            target_entity_id=str(item_id),mapping_status='MATCH',source_fingerprint=source.content_hash)
        audit=_audit(user=user,organization_id=source.company_id,action_code=ACTION_CODE,instance=identity,
            before={},after=payload,reason=reason,authorization=decision,execution_chain=chain,
            audit_context={'idempotencyKey':key,'contract':'PCE-SOURCE-ROW-LINE-BINDING-V1'})
        identity.audit_metadata={'binding':payload,'bindingHash':digest(payload),'auditId':audit.pk,'actorId':user.pk}
        identity.save(update_fields=['audit_metadata']);identities.append(identity);created+=1
    result={'sourceRecordId':source.pk,'sourceVersion':source.source_version,'salesOrderId':line.sales_order_id,
        'bindings':[{'sourceRowId':k,'salesOrderItemId':v} for k,v in sorted(pairs)],
        'idempotent':not created,'businessWriteCount':created,'reusedExistingAuthority':len(pairs)-created}
    result['sourceRowBindings']=binding_facts(source,instance)
    if identities:
        MasterDataWriteRequest.objects.create(organization_id=source.company_id,action_code=ACTION_CODE,entity_type=SYSTEM,
            idempotency_key=key,request_hash=request_hash,source_identity=identities[0],status='COMMITTED',
            target_entity_id=str(line.sales_order_id),result=result,audit_metadata={'operatorId':user.pk})
    return result
