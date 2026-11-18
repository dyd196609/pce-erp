"""Exact, append-only per-line identity proofs under one approved order.

No persisted proof is rewritten. Every edge changes only the explicitly
maintained line's engineering mode/name and retains its original approval,
admission, MAKE fact, actor and item audit. There is no automatic conversion.
"""
from copy import deepcopy
from django.core.exceptions import ObjectDoesNotExist


def validate_chain(*, proof, relation, order, item, snapshot):
    from .models import CRMOrderVersionCarryForward, OrderEngineeringInstance
    from .crm_order_version_carry_forward import digest
    from .order_engineering_identity_carry import normalized
    from .production_foundation_service import _snapshot
    from .pde_engineering_preparation_admission import require_pde_engineering_preparation_admission, PDEEngineeringPreparationAdmissionError
    from sales.models import SalesOrderItemSupplyAdmission
    from sales.supply_admission_service import source_snapshot
    from system.models import OrganizationOperatingAuditRecord
    try:
        entries=proof.validation_results.get('engineeringIdentityCarry')
        if (not isinstance(entries,list) or len(entries)<2 or proof.content_snapshot!=snapshot
            or proof.content_hash!=digest(snapshot) or order.pk!=item.sales_order_id):return None
        identities=[e['salesOrderItemId'] for e in entries]
        lines={line.pk:line for line in order.items.select_related('sales_order')}
        if (len(set(identities))!=len(identities) or len(entries)>len(lines)
            or item.pk not in identities or not set(identities)<=set(lines)):return None
        current=proof;seen=set();remaining=len(entries)
        while remaining:
            if current.pk in seen:return None
            seen.add(current.pk)
            values=current.validation_results.get('engineeringIdentityCarry')
            if values!=entries[:remaining]:return None
            entry=values[-1];line=lines[entry['salesOrderItemId']]
            previous=CRMOrderVersionCarryForward.objects.get(pk=entry['previousProofId'],relation=relation,
                sales_order_id=order.pk,target_version=order.version,company_id=order.company_id)
            if (previous.pk>=current.pk or current.company_id!=order.company_id or current.sales_order_id!=order.pk
                or current.relation_id!=relation.pk or current.target_version!=order.version
                or current.original_version!=relation.order_version_snapshot
                or previous.original_version!=relation.order_version_snapshot
                or current.source_fingerprint!=relation.source_content_hash_snapshot
                or previous.source_fingerprint!=current.source_fingerprint
                or previous.scope_fingerprint!=current.scope_fingerprint
                or previous.approval_evidence!=current.approval_evidence
                or current.content_hash!=digest(current.content_snapshot)
                or previous.content_hash!=digest(previous.content_snapshot)
                or (previous.validation_results.get('engineeringIdentityCarry') or [])!=values[:-1]
                or {k:v for k,v in current.validation_results.items() if k!='engineeringIdentityCarry'}
                   !={k:v for k,v in previous.validation_results.items() if k!='engineeringIdentityCarry'}
                or current.version_differences!=[*previous.version_differences,{'action':'PDE_ENGINEERING_IDENTITY_CARRY',**entry}]):return None
            before_snapshot=previous.content_snapshot;after_snapshot=deepcopy(current.content_snapshot)
            old_line=next(x for x in before_snapshot['lines'] if x['id']==line.pk)
            new_line=next(x for x in after_snapshot['lines'] if x['id']==line.pk)
            if (old_line['engineering_mode']!='STANDARD' or new_line['engineering_mode']!='ORDER_ENGINEERED'
                or not new_line['customer_product_name'] or line.engineering_mode!='ORDER_ENGINEERED'
                or line.customer_product_name!=new_line['customer_product_name']):return None
            for key in ('engineering_mode','customer_product_name'):new_line[key]=old_line[key]
            if after_snapshot!=before_snapshot:return None
            admission=require_pde_engineering_preparation_admission(company_id=order.company_id,
                sales_order_item_id=line.pk,authorization_id=entry['authorizationId'])
            if admission.crm_order_relation_id!=relation.pk:return None
            instance=OrderEngineeringInstance.objects.get(pk=entry['oeiId'],sales_order_item=line,
                engineering_preparation_authorization_id=entry['authorizationId'])
            if (hasattr(instance,'admission_chain_revocation') or instance.company_id!=order.company_id
                or instance.source_record_id!=relation.review.source_record_id
                or not instance.product_category_id or not instance.selected_process_type_id
                or not instance.product_category.is_active or not instance.selected_process_type.is_active
                or entry.get('productCategoryId')!=instance.product_category_id
                or entry.get('processTypeId')!=instance.selected_process_type_id
                or entry.get('sourceRecordId')!=instance.source_record_id):return None
            audit=OrganizationOperatingAuditRecord.objects.get(pk=entry['itemAuditId'],organization_id=order.company_id,
                target_type='SalesOrderItem',target_id=line.pk,action_code='production.engineering.order.maintain',actor_id=current.created_by_id)
            before=audit.before_snapshot.get('state',{});after=audit.after_snapshot.get('state',{})
            if (not audit.after_snapshot.get('authorization',{}).get('allowed')
                or after!=normalized(_snapshot(line))
                or {k for k in set(before)|set(after) if before.get(k)!=after.get(k)}!={'engineering_mode','customer_product_name'}
                or before.get('engineering_mode')!='STANDARD'
                or before.get('customer_product_name')!=old_line['customer_product_name']):return None
            fact=SalesOrderItemSupplyAdmission.objects.get(pk=entry['supplyFactId'],sales_order_item=line,supply_type='MAKE')
            if {**fact.source_snapshot,'engineeringMode':'ORDER_ENGINEERED'}!=source_snapshot(line):return None
            current=previous;remaining-=1
        return proof
    except (ObjectDoesNotExist,KeyError,StopIteration,TypeError,ValueError,PDEEngineeringPreparationAdmissionError):
        return None
