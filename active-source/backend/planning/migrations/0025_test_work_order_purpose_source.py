"""One existing work-order header. Purpose is independent of lifecycle state."""
from django.db import migrations,models
import django.db.models.deletion
import hashlib,json

def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def classify(apps,schema_editor):
    WO=apps.get_model('planning','ProductionWorkOrder');Schedule=apps.get_model('planning','FormalProductionSchedule')
    Transition=apps.get_model('workflow_runtime','BusinessStateTransition');Audit=apps.get_model('system','OrganizationOperatingAuditRecord')
    for row in WO.objects.all():
        source=row.source_snapshot
        schedule=Schedule.objects.filter(pk=row.source_schedule_id,company_id=row.company_id,usage_purpose='PRODUCTION_USE',production_plan_id=row.production_plan_id).first()
        valid=bool(row.production_plan_id and schedule and digest(source)==row.snapshot_hash and source.get('productionPlanId')==row.production_plan_id and source.get('companyId')==row.company_id and source.get('sourceSchedule',{}).get('id')==row.source_schedule_id and source.get('sourceSchedule',{}).get('snapshotHash')==schedule.snapshot_hash)
        transitions=list(Transition.objects.filter(object_type='ProductionWorkOrder',object_id=row.pk).order_by('version','pk'))
        pairs=[('','draft')]+([('draft','released')] if row.status=='released' else [])
        valid=valid and row.status in ('draft','released') and len(transitions)==len(pairs) and row.version==len(pairs)-1
        for i,(t,pair) in enumerate(zip(transitions,pairs),1):
            aid=t.audit_reference.removeprefix('OrganizationOperatingAuditRecord:')
            audit=Audit.objects.filter(pk=aid,organization_id=row.company_id,target_type='ProductionWorkOrder',target_id=row.pk,actor_id=t.operator_id,action_code=t.action_code).first()
            after=audit.after_snapshot.get('state',{}) if audit else {}
            valid=valid and t.version==i and (t.source_state,t.target_state)==pair and after.get('status')==pair[1] and after.get('snapshotHash')==row.snapshot_hash and audit.after_snapshot.get('authorization',{}).get('allowed') is True
        operations=list(row.operations.order_by('sequence','pk'));frozen=source.get('operations',[])
        valid=valid and len(operations)==len(frozen) and len(operations)>0
        for operation,previous in zip(operations,frozen):valid=valid and operation.source_snapshot==previous and operation.snapshot_hash==digest(previous)
        if valid:WO.objects.filter(pk=row.pk).update(usage_purpose='PRODUCTION_USE')

GUARDS="""
CREATE TRIGGER wo_purpose_source_insert BEFORE INSERT ON planning_production_work_order BEGIN
 SELECT CASE WHEN NEW.usage_purpose='PRODUCTION_USE' AND NOT EXISTS(SELECT 1 FROM planning_formal_production_schedule s JOIN planning_production_plan p ON p.id=NEW.production_plan_id JOIN material m ON m.id=p.material_id JOIN planning_requirement q ON q.id=p.planning_requirement_id JOIN planning_demand d ON d.id=q.demand_id JOIN system_department dep ON dep.id=d.department_id WHERE s.id=NEW.source_schedule_id AND s.company_id=NEW.company_id AND s.usage_purpose='PRODUCTION_USE' AND s.production_plan_id=p.id AND m.company_id=NEW.company_id AND dep.company_id=NEW.company_id) THEN RAISE(ABORT,'WO_FORMAL_SOURCE_COMPANY') END;
 SELECT CASE WHEN NEW.usage_purpose='TEST_BUSINESS' AND NOT EXISTS(SELECT 1 FROM planning_formal_production_schedule s JOIN pde_order_routing_execution_arrangement a ON a.id=s.execution_arrangement_id WHERE s.id=NEW.source_schedule_id AND s.company_id=NEW.company_id AND s.usage_purpose='TEST_BUSINESS' AND s.status='saved' AND a.company_id=NEW.company_id AND a.usage_purpose='TEST_BUSINESS' AND NOT EXISTS(SELECT 1 FROM pde_order_routing_execution_arrangement n WHERE n.predecessor_id=a.id) AND json_extract(NEW.source_snapshot,'$.contractVersion')='PCE-TEST-WORK-ORDER-V1' AND json_extract(NEW.source_snapshot,'$.companyId')=NEW.company_id AND json_extract(NEW.source_snapshot,'$.sourceSchedule.id')=s.id AND json_extract(NEW.source_snapshot,'$.sourceSchedule.snapshotHash')=s.snapshot_hash AND json_extract(NEW.source_snapshot,'$.sourceSchedule.version')=s.version AND json_extract(NEW.source_snapshot,'$.scope.arrangementId')=a.id AND json_extract(NEW.source_snapshot,'$.scope.arrangementRevision')=a.arrangement_revision AND json_extract(NEW.source_snapshot,'$.scope.arrangementEditVersion')=a.edit_version AND json_extract(NEW.source_snapshot,'$.product.materialId')=NEW.material_id AND json_extract(NEW.source_snapshot,'$.product.uomId')=NEW.uom_id AND CAST(json_extract(NEW.source_snapshot,'$.product.quantity') AS NUMERIC)=NEW.quantity) THEN RAISE(ABORT,'WO_TEST_SOURCE_VERSION_COMPANY') END;
END;
CREATE TRIGGER wo_immutable_source_update BEFORE UPDATE ON planning_production_work_order BEGIN
 SELECT CASE WHEN NEW.usage_purpose<>OLD.usage_purpose OR NEW.company_id<>OLD.company_id OR NEW.production_plan_id IS NOT OLD.production_plan_id OR NEW.source_schedule_id<>OLD.source_schedule_id OR NEW.material_id<>OLD.material_id OR NEW.quantity<>OLD.quantity OR NEW.uom_id<>OLD.uom_id OR NEW.no<>OLD.no OR NEW.source_snapshot<>OLD.source_snapshot OR NEW.snapshot_hash<>OLD.snapshot_hash OR NEW.idempotency_key<>OLD.idempotency_key OR NEW.request_hash<>OLD.request_hash OR NEW.created_by_id<>OLD.created_by_id OR NEW.created_at<>OLD.created_at THEN RAISE(ABORT,'WO_IMMUTABLE_SOURCE') END;
END;
"""

class Migration(migrations.Migration):
    dependencies=[('planning','0024_test_schedule_purpose_source'),('planning','0013_production_work_orders')]
    operations=[
        migrations.AddField(model_name='productionworkorder',name='usage_purpose',field=models.CharField(max_length=20,default='UNCLASSIFIED')),
        migrations.AlterField(model_name='productionworkorder',name='production_plan',field=models.OneToOneField(to='planning.productionplan',on_delete=django.db.models.deletion.PROTECT,related_name='production_work_order',null=True,blank=True)),
        migrations.RunPython(classify,migrations.RunPython.noop),
        migrations.AddConstraint(model_name='productionworkorder',constraint=models.CheckConstraint(condition=(models.Q(usage_purpose='PRODUCTION_USE',production_plan__isnull=False)|models.Q(usage_purpose='TEST_BUSINESS',production_plan__isnull=True)|models.Q(usage_purpose='UNCLASSIFIED')),name='wo_purpose_plan_branch')),
        migrations.AddConstraint(model_name='productionworkorder',constraint=models.UniqueConstraint(fields=('source_schedule',),condition=models.Q(usage_purpose='TEST_BUSINESS'),name='test_wo_source_schedule_unique')),
        migrations.RunSQL(GUARDS,'DROP TRIGGER IF EXISTS wo_purpose_source_insert; DROP TRIGGER IF EXISTS wo_immutable_source_update;'),
    ]
