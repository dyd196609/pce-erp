"""Append-only provenance links; original organization audit facts are never edited."""
import hashlib
import json
import os
from pathlib import Path
from datetime import timezone
from django.utils.dateparse import parse_datetime
from django.db import connection, transaction
from .models import AuditSourceEvent, OrganizationOperatingAuditRecord, User

def content_hash(payload):
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def normalized(payload):
    row=dict(payload)
    for key in ('before_snapshot','after_snapshot'):
        if isinstance(row[key],str):row[key]=json.loads(row[key])
    stamp=row['created_at']
    if isinstance(stamp,str):stamp=parse_datetime(stamp)
    if stamp is None:raise ValueError('Original audit occurrence time required')
    if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
    row['created_at']=stamp.astimezone(timezone.utc).isoformat()
    return row

@transaction.atomic
def attach_event(*, actor, namespace, original_id, original_payload, source_sha256, active_audit_id=None):
    declared=os.environ.get('PCE_AUDIT_CONTINUATION_DATABASE','')
    if not actor.is_superuser or not declared or Path(declared).resolve()!=Path(connection.settings_dict['NAME']).resolve():
        raise PermissionError('Explicit database-bound administrative audit continuation required')
    if original_payload['organization_id']!=actor.company_id or original_payload['id']!=original_id:
        raise ValueError('Audit tenant or source identity mismatch')
    source_actor=User.objects.get(pk=original_payload['actor_id'],company_id=actor.company_id)
    if original_payload['target_type']=='User':
        User.objects.get(pk=original_payload['target_id'],company_id=actor.company_id)
    if active_audit_id is not None:
        native=OrganizationOperatingAuditRecord.objects.get(pk=active_audit_id,organization_id=actor.company_id)
        actual={key:getattr(native,key) for key in original_payload}
        if normalized(actual)!=normalized(original_payload):
            raise ValueError('Native audit reference does not match original event')
    if len(source_sha256)!=64 or any(c not in '0123456789abcdef' for c in source_sha256) or not namespace or len(namespace)>100:
        raise ValueError('Audit source provenance required')
    digest=content_hash(original_payload)
    row,created=AuditSourceEvent.objects.get_or_create(organization_id=actor.company_id,source_namespace=namespace,source_audit_id=original_id,
        defaults={'original_payload':original_payload,'content_hash':digest,'source_sha256':source_sha256,'active_audit_id':active_audit_id,'registered_by':actor})
    if row.content_hash!=digest or row.active_audit_id!=active_audit_id:
        raise ValueError('Existing provenance identity has conflicting content; no overwrite allowed')
    return row,created

def project_events(*,company_id):
    rows=[]
    for event in AuditSourceEvent.objects.filter(organization_id=company_id).order_by('source_namespace','source_audit_id'):
        raw=event.original_payload
        if event.content_hash!=content_hash(raw):
            raise ValueError('Audit provenance content verification failed')
        actor=User.objects.get(pk=raw['actor_id'],company_id=company_id)
        decode=lambda value: json.loads(value) if isinstance(value,str) else value
        rows.append({'id':event.active_audit_id if event.active_audit_id else 'source:'+str(event.pk),
            'actionCode':raw['action_code'],'actorName':actor.real_name or actor.username,'targetType':raw['target_type'],
            'targetId':raw['target_id'],'targetLabel':raw['target_label'],'reason':raw['reason'],
            'before':decode(raw['before_snapshot']),'after':decode(raw['after_snapshot']),'createdAt':raw['created_at'],
            'sourceLabel':event.source_namespace+' / 原审计 '+str(event.source_audit_id),
            'sourceEventIdentity':event.source_namespace+':'+str(event.source_audit_id),'sourceContentHash':event.content_hash,
            'nativeAuditId':event.active_audit_id,'sourceDatabaseSHA256':event.source_sha256})
    return rows
