"""One existing schedule header only. Existing applied schema is not replayed."""
from django.db import migrations,models
import django.db.models.deletion
import json,hashlib

def classify(apps,schema_editor):
    Schedule=apps.get_model('planning','FormalProductionSchedule')
    Plan=apps.get_model('planning','ProductionPlan')
    Transition=apps.get_model('workflow_runtime','BusinessStateTransition')
    Audit=apps.get_model('system','OrganizationOperatingAuditRecord')
    for row in Schedule.objects.all():
        payload=json.dumps(row.snapshot,sort_keys=True,ensure_ascii=False,separators=(',',':'),default=str,allow_nan=False)
        if not row.production_plan_id or not Plan.objects.filter(pk=row.production_plan_id,material__company_id=row.company_id,planning_requirement__material__company_id=row.company_id,planning_requirement__demand__department__company_id=row.company_id).exists() or hashlib.sha256(payload.encode()).hexdigest()!=row.snapshot_hash:
            continue
        transitions=list(Transition.objects.filter(object_type='FormalProductionSchedule',object_id=row.pk).order_by('version','pk'))
        pairs=[('','draft'),('draft','saved')]+([('saved','cancelled')] if row.status=='cancelled' else [])
        valid=row.status in ('saved','cancelled') and len(transitions)==len(pairs) and row.version==len(pairs)-1
        for i,(t,pair) in enumerate(zip(transitions,pairs),1):
            aid=t.audit_reference.removeprefix('OrganizationOperatingAuditRecord:')
            a=Audit.objects.filter(pk=aid,organization_id=row.company_id,target_type='FormalProductionSchedule',target_id=row.pk,actor_id=t.operator_id,action_code=t.action_code).first()
            after=a.after_snapshot.get('state',{}) if a else {}
            proof=after.get('actionPermissionDecision',{})
            valid=valid and t.version==i and (t.source_state,t.target_state)==pair and after.get('snapshotHash')==row.snapshot_hash and after.get('status')==pair[1] and proof.get('granted') is True and proof.get('action',{}).get('moduleCode')=='formal-production-schedule'
        if valid:Schedule.objects.filter(pk=row.pk).update(usage_purpose='PRODUCTION_USE')

GUARDS="""
CREATE TRIGGER schedule_branch_insert BEFORE INSERT ON planning_formal_production_schedule BEGIN
 SELECT CASE WHEN NEW.usage_purpose='PRODUCTION_USE' AND NOT EXISTS(SELECT 1 FROM planning_production_plan p JOIN material m ON m.id=p.material_id JOIN planning_requirement q ON q.id=p.planning_requirement_id JOIN material qm ON qm.id=q.material_id JOIN planning_demand d ON d.id=q.demand_id JOIN system_department dep ON dep.id=d.department_id WHERE p.id=NEW.production_plan_id AND m.company_id=NEW.company_id AND qm.company_id=NEW.company_id AND dep.company_id=NEW.company_id) THEN RAISE(ABORT,'SCHEDULE_FORMAL_COMPANY_SOURCE') END;
 SELECT CASE WHEN NEW.usage_purpose='TEST_BUSINESS' AND NOT EXISTS(SELECT 1 FROM pde_order_routing_execution_arrangement a WHERE a.id=NEW.execution_arrangement_id AND a.company_id=NEW.company_id AND a.usage_purpose='TEST_BUSINESS' AND json_extract(NEW.snapshot,'$.preview.scope.arrangementId')=a.id AND json_extract(NEW.snapshot,'$.preview.scope.arrangementRevision')=a.arrangement_revision AND json_extract(NEW.snapshot,'$.preview.scope.arrangementEditVersion')=a.edit_version AND json_extract(NEW.snapshot,'$.contractVersion')='PCE-TEST-SCHEDULE-V1') THEN RAISE(ABORT,'SCHEDULE_TEST_COMPANY_SOURCE_VERSION') END;
END;
CREATE TRIGGER schedule_branch_update BEFORE UPDATE ON planning_formal_production_schedule BEGIN
 SELECT CASE WHEN NEW.company_id<>OLD.company_id OR NEW.usage_purpose<>OLD.usage_purpose OR NEW.production_plan_id IS NOT OLD.production_plan_id OR NEW.execution_arrangement_id IS NOT OLD.execution_arrangement_id OR NEW.snapshot<>OLD.snapshot OR NEW.snapshot_hash<>OLD.snapshot_hash OR NEW.start_at<>OLD.start_at OR NEW.end_at<>OLD.end_at OR NEW.revision<>OLD.revision OR NEW.saved_start_date<>OLD.saved_start_date OR NEW.timezone<>OLD.timezone OR NEW.idempotency_key<>OLD.idempotency_key OR NEW.admission_token<>OLD.admission_token OR NEW.request_hash<>OLD.request_hash THEN RAISE(ABORT,'SCHEDULE_IMMUTABLE_SOURCE') END;
END;
"""

class Migration(migrations.Migration):
    dependencies=[('planning','0011_formal_production_scheduling'),('pde','0062_frozen_object_workload_scope')]
    operations=[
        migrations.AddField(model_name='formalproductionschedule',name='usage_purpose',field=models.CharField(max_length=20,default='UNCLASSIFIED')),
        migrations.AddField(model_name='formalproductionschedule',name='execution_arrangement',field=models.ForeignKey(to='pde.orderroutingexecutionarrangement',on_delete=django.db.models.deletion.PROTECT,null=True,blank=True)),
        migrations.AlterField(model_name='formalproductionschedule',name='production_plan',field=models.ForeignKey(to='planning.productionplan',on_delete=django.db.models.deletion.PROTECT,related_name='formal_schedules',null=True,blank=True)),
        migrations.RunPython(classify,migrations.RunPython.noop),
        migrations.AddConstraint(model_name='formalproductionschedule',constraint=models.CheckConstraint(condition=(models.Q(usage_purpose='PRODUCTION_USE',production_plan__isnull=False,execution_arrangement__isnull=True)|models.Q(usage_purpose='TEST_BUSINESS',production_plan__isnull=True,execution_arrangement__isnull=False)|models.Q(usage_purpose='UNCLASSIFIED',execution_arrangement__isnull=True)),name='schedule_purpose_source_branch')),
        migrations.AddConstraint(model_name='formalproductionschedule',constraint=models.UniqueConstraint(fields=('execution_arrangement','revision'),name='test_schedule_arr_revision')),
        migrations.AddConstraint(model_name='formalproductionschedule',constraint=models.UniqueConstraint(fields=('execution_arrangement',),condition=models.Q(status='saved',usage_purpose='TEST_BUSINESS'),name='test_schedule_one_saved_arr')),
        migrations.RunSQL(GUARDS,'DROP TRIGGER IF EXISTS schedule_branch_insert; DROP TRIGGER IF EXISTS schedule_branch_update;'),
    ]
